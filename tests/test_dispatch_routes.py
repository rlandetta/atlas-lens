import base64
import copy
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.dispatch import DispatchShipmentStore, ShipmentService
from app.dispatch.scheduler import DispatchScheduler
from app.lens_read_service import LensReadService
from app.routes import web
from app.settings import OutboundChannelDraft


class DispatchRoutesTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.lens_media_root = self.root / "lens_media"
        self.dispatch_store_path = self.root / "dispatch_shipments.json"
        self.settings_store_path = self.root / "settings.json"
        self.lens_store_path = self.root / "lens_coverages.json"
        self.ingest_store_path = self.root / "ingest.json"
        self.thumbnail_root = self.root / "thumbnails"
        self.patches = [
            patch("app.config.DISPATCH_STORE_PATH", str(self.dispatch_store_path)),
            patch("app.config.SETTINGS_STORE_PATH", str(self.settings_store_path)),
            patch("app.config.LENS_COVERAGE_STORE_PATH", str(self.lens_store_path)),
            patch("app.config.LENS_MEDIA_ROOT", str(self.lens_media_root)),
            patch("app.config.INGEST_STORE_PATH", str(self.ingest_store_path)),
            patch("app.config.THUMBNAIL_ROOT", str(self.thumbnail_root)),
        ]
        for item in self.patches:
            item.start()
        self.app = create_app()
        self.app.config.update(TESTING=True)
        approved_file = self.lens_media_root / "coverages" / "cov-1" / "photo-approved_IMG001.jpg"
        approved_file.parent.mkdir(parents=True)
        approved_file.write_bytes(self.valid_image_bytes())
        self.coverages = {
            "cov-1": {
                "coverage_name": "Cobertura Quito",
                "submit_date": "2026-08-01",
                "event_date": "2026-08-01",
                "city": "Quito",
                "country": "Ecuador",
                "agency": "Xinhua",
                "photographer": "Ricardo Landeta",
                "editor": "rl",
                "photos": [
                    {
                        "id": "photo-approved",
                        "name": "IMG001.jpg",
                        "filename": "IMG001.jpg",
                        "storage_path": "coverages/cov-1/photo-approved_IMG001.jpg",
                        "available_on_disk": True,
                        "caption_narrative": "Persona participa en evento.",
                        "caption_status": "Aprobado",
                    },
                    {
                        "id": "photo-review",
                        "name": "IMG002.jpg",
                        "filename": "IMG002.jpg",
                        "caption_narrative": "Persona observa actividad.",
                        "caption_status": "Revisado",
                    },
                    {
                        "id": "photo-empty",
                        "name": "IMG003.jpg",
                        "caption_narrative": "",
                        "caption_status": "Aprobado",
                    },
                ],
            }
        }
        self.original_coverages = copy.deepcopy(self.coverages)
        store = DispatchShipmentStore(self.dispatch_store_path)
        coverage_provider = lambda: self.coverages
        lens_reader = LensReadService(coverage_provider)
        self.shipment_service = ShipmentService(store=store, lens_reader=lens_reader)
        self.app.extensions["dispatch"] = {
            "coverage_provider": coverage_provider,
            "store": store,
            "lens_reader": lens_reader,
            "shipment_service": self.shipment_service,
        }
        self.client = self.app.test_client()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp_dir.cleanup()

    def create_shipment(self):
        return self.shipment_service.create_shipment(
            name="Despacho Quito",
            coverage_id="cov-1",
            photo_ids=["photo-approved"],
            recipients=[{"name": "Mesa", "email": "desk@example.com"}],
            delivery_note="Lista.",
            channel="manual",
        )

    def save_shipment_changes(self, shipment, **updates):
        next_shipment = copy.deepcopy(shipment)
        next_shipment.update(updates)
        return self.shipment_service.store.update(next_shipment["id"], next_shipment)

    def create_docx_shipment_from_route(self, **overrides):
        response = self.post_new(**overrides)
        self.assertEqual(response.status_code, 302)
        return self.shipment_service.list_shipments()[0]

    def create_outbound_channel(self, **overrides):
        defaults = {
            "id": "xinhua",
            "name": "Xinhua",
            "display_name": "Xinhua News Agency",
            "channel_type": "smtp",
            "sender_email": "atlas@lavoceria.com",
            "reply_to": "",
            "smtp_host": "smtp.zoho.com",
            "smtp_port": 465,
            "smtp_security": "ssl",
            "smtp_username": "atlas@lavoceria.com",
            "credential_ref": "ATLAS_SMTP_CHANNEL_XINHUA",
            "is_active": True,
            "is_default": True,
        }
        defaults.update(overrides)
        return self.app.extensions["settings"]["settings_service"].create_outbound_channel(
            OutboundChannelDraft(**defaults)
        )

    def test_dispatch_blueprint_is_registered(self):
        self.assertIn("dispatch.index", self.app.view_functions)
        self.assertIn("dispatch.new", self.app.view_functions)
        self.assertIn("dispatch.detail", self.app.view_functions)
        self.assertIn("dispatch.edit", self.app.view_functions)
        self.assertIn("dispatch.duplicate", self.app.view_functions)
        self.assertIn("dispatch.cancel", self.app.view_functions)
        self.assertIn("dispatch.delete", self.app.view_functions)

    def test_get_dispatch_index(self):
        response = self.client.get("/dispatch/")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("ATLAS", body)
        self.assertIn("Despachos", body)
        self.assertIn("Filtros de despachos", body)
        self.assertIn("Todos", body)
        self.assertIn("Borradores", body)
        self.assertIn("Programados", body)
        self.assertIn("Enviando", body)
        self.assertIn("Enviados", body)
        self.assertIn("Error", body)
        self.assertIn("Cancelados", body)
        self.assertIn("No hay despachos todavía", body)
        self.assertNotIn("Cobertura activa", body)

    def test_home_dashboard_and_lens_route_are_separate(self):
        dashboard = self.client.get("/")
        lens = self.client.get("/lens")

        self.assertEqual(dashboard.status_code, 200)
        dashboard_body = dashboard.get_data(as_text=True)
        self.assertIn("BIENVENIDO A ATLAS", dashboard_body)
        self.assertIn("Centro editorial", dashboard_body)
        self.assertIn("MÓDULOS ACTIVOS", dashboard_body)
        self.assertIn("SETTINGS", dashboard_body)
        self.assertIn("FLOW", dashboard_body)
        self.assertIn("Abrir LENS", dashboard_body)
        self.assertIn("Abrir DISPATCH", dashboard_body)
        self.assertIn("Abrir FLOW", dashboard_body)
        self.assertNotIn("Abrir SETTINGS", dashboard_body)
        self.assertNotIn("atlas-module-card--settings", dashboard_body)
        self.assertIn('href="/lens"', dashboard_body)
        self.assertIn('href="/dispatch/"', dashboard_body)
        self.assertIn('href="/flow"', dashboard_body)
        self.assertIn('href="/settings/"', dashboard_body)
        self.assertLess(dashboard_body.index('href="/flow"'), dashboard_body.index('href="/lens"'))
        self.assertLess(dashboard_body.index('href="/lens"'), dashboard_body.index('href="/dispatch/"'))
        self.assertLess(dashboard_body.index('href="/dispatch/"'), dashboard_body.index('href="/settings/"'))
        self.assertLess(dashboard_body.index('atlas-module-card--flow'), dashboard_body.index('atlas-module-card--lens'))
        self.assertLess(dashboard_body.index('atlas-module-card--lens'), dashboard_body.index('atlas-module-card--dispatch'))
        self.assertIn("PRÓXIMOS MÓDULOS", dashboard_body)
        self.assertIn("NEXUS", dashboard_body)
        self.assertIn("PULSE", dashboard_body)
        self.assertIn("ARCHIVE", dashboard_body)
        self.assertIn("Próximamente", dashboard_body)
        self.assertEqual(lens.status_code, 200)
        self.assertIn("Coberturas", lens.get_data(as_text=True))

    def valid_image_bytes(self):
        return base64.b64decode(
            "/9j/4AAQSkZJRgABAQEAAQABAAD/2wBDAAMCAgICAgMCAgIDAwMDBAYEBAQEBAgGBgUGCQgKCgkICQkKDA8MCgsOCwkJDRENDg8QEBEQCgwSExIQEw8QEBD/2wBDAQMDAwQDBAgEBAgQCwkLEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBD/wAARCAASACADAREAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAn/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFgEBAQEAAAAAAAAAAAAAAAAAAAYH/8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAwDAQACEQMRAD8AnE1hLgAAAAAAAAAAP//Z"
        )

    def write_valid_jpeg(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.valid_image_bytes())

    def register_ingest_photo(self, filename="IMG001.jpg", source="canon-r6", received_at=None, valid_jpeg=False):
        photo_path = self.root / "events" / "2026" / "08" / "08" / "sabado" / "ricardo" / source / "JPG" / filename
        photo_path.parent.mkdir(parents=True, exist_ok=True)
        if valid_jpeg:
            self.write_valid_jpeg(photo_path)
        else:
            photo_path.write_bytes(f"jpg-{filename}".encode())
        return self.app.extensions["ingest"]["ingest_service"].register_received_photo({
            "filename": filename,
            "path": str(photo_path),
            "source": source,
            "received_at": (received_at or datetime.now(timezone.utc)).isoformat(),
        })

    def flow_coverage_form(self, **overrides):
        data = {
            "coverage_name": "OPERATIVOS",
            "agency": "Xinhua",
            "event_date": "2026-08-08",
            "submit_date": "2026-08-08",
            "city": "Quito",
            "country": "Ecuador",
            "photographer": "Ricardo Landeta",
            "editor": "rl",
        }
        data.update(overrides)
        return data

    def convert_first_flow_session(self, **form_overrides):
        session = self.app.extensions["ingest"]["store"].list_sessions()[0]
        response = self.client.post(
            f"/flow/sessions/{session['id']}/coverage/new",
            data=self.flow_coverage_form(**form_overrides),
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        return session, response

    def test_dashboard_flow_with_active_session(self):
        self.register_ingest_photo()

        response = self.client.get("/")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("FLOW", body)
        self.assertIn("Recibiendo", body)
        self.assertIn("Sesión activa", body)
        self.assertIn("Canon R6", body)
        self.assertIn("Última foto:", body)
        self.assertIn("Abrir FLOW", body)

    def test_dashboard_flow_without_active_session(self):
        response = self.client.get("/")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("FLOW", body)
        self.assertIn("En espera", body)
        self.assertIn("0 sesiones activas", body)
        self.assertIn("Última recepción: Sin recepción previa", body)

    def test_flow_route_returns_200(self):
        response = self.client.get("/flow")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Sesiones de ingreso fotográfico", body)
        self.assertIn("ÚLTIMAS FOTOGRAFÍAS", body)
        self.assertIn("Todavía no hay fotografías en la sesión activa.", body)

    def test_flow_route_shows_real_session_and_photo_count(self):
        self.register_ingest_photo(filename="IMG001.jpg", source="canon-r6")
        self.register_ingest_photo(filename="IMG002.jpg", source="sony-a9")

        response = self.client.get("/flow")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("SESIÓN ACTIVA", body)
        self.assertIn("2", body)
        self.assertIn("Canon R6", body)
        self.assertIn("Sony A9", body)
        self.assertIn("2 fotografías", body)
        self.assertIn("IMG001.jpg", body)
        self.assertIn("IMG002.jpg", body)
        self.assertNotIn(str(self.root), body)

    def test_flow_route_limits_latest_photos_to_12(self):
        base_time = datetime.now(timezone.utc)
        for index in range(13):
            self.register_ingest_photo(
                filename=f"IMG{index + 1:03}.jpg",
                source="canon-r6",
                received_at=base_time.replace(microsecond=0) if index == 0 else base_time.replace(microsecond=0),
            )

        response = self.client.get("/flow")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(body.count("flow-photo-card"), 12)
        self.assertIn("12 de 13", body)

    def test_flow_session_can_create_lens_coverage_without_copying_originals(self):
        first = self.register_ingest_photo(filename="IMG001.jpg", source="canon-r6")
        second = self.register_ingest_photo(filename="IMG002.jpg", source="canon-1dx")
        first_path = Path(first["path"])
        before_hash = first_path.read_bytes()

        session, response = self.convert_first_flow_session()

        coverage_id = response.headers["Location"].rsplit("/", 1)[-1]
        coverage = self.app.extensions["lens"]["coverage_store"].get(coverage_id)
        refreshed_session = self.app.extensions["ingest"]["store"].list_sessions()[0]

        self.assertIn("/coverages/", response.headers["Location"])
        self.assertEqual(coverage["flow_session_id"], session["id"])
        self.assertEqual(len(coverage["photos"]), 2)
        self.assertEqual({photo["flow_path"] for photo in coverage["photos"]}, {first["path"], second["path"]})
        self.assertEqual({photo["source"] for photo in coverage["photos"]}, {"canon-r6", "canon-1dx"})
        self.assertEqual(refreshed_session["coverage_id"], coverage_id)
        self.assertTrue(first_path.exists())
        self.assertEqual(first_path.read_bytes(), before_hash)

    def test_flow_session_second_conversion_redirects_without_duplicate_coverage(self):
        self.register_ingest_photo(filename="IMG001.jpg")
        session, first_response = self.convert_first_flow_session()
        first_coverage_id = first_response.headers["Location"].rsplit("/", 1)[-1]

        second_response = self.client.post(
            f"/flow/sessions/{session['id']}/coverage/new",
            data=self.flow_coverage_form(coverage_name="OTRA"),
            follow_redirects=False,
        )

        self.assertEqual(second_response.status_code, 302)
        self.assertTrue(second_response.headers["Location"].endswith(f"/coverages/{first_coverage_id}"))
        self.assertEqual(len(self.app.extensions["lens"]["coverage_store"].list_coverages()), 1)

    def test_active_flow_session_can_convert_and_later_photos_sync_to_same_coverage(self):
        first_time = datetime.now(timezone.utc)
        self.register_ingest_photo(filename="IMG001.jpg", source="canon-r6", received_at=first_time)
        session, response = self.convert_first_flow_session()
        coverage_id = response.headers["Location"].rsplit("/", 1)[-1]

        later = first_time + timedelta(minutes=5)
        new_photo = self.register_ingest_photo(filename="IMG002.jpg", source="sony-a9", received_at=later)
        detail = self.client.get(f"/coverages/{coverage_id}")
        coverage = self.app.extensions["lens"]["coverage_store"].get(coverage_id)

        self.assertEqual(detail.status_code, 200)
        self.assertEqual(self.app.extensions["ingest"]["store"].list_sessions()[0]["coverage_id"], coverage_id)
        self.assertEqual(len(coverage["photos"]), 2)
        self.assertIn(new_photo["path"], {photo["flow_path"] for photo in coverage["photos"]})
        self.assertEqual(coverage["flow_session_id"], session["id"])

    def test_flow_offers_open_in_lens_after_conversion(self):
        self.register_ingest_photo(filename="IMG001.jpg")
        _, response = self.convert_first_flow_session()
        coverage_id = response.headers["Location"].rsplit("/", 1)[-1]

        flow_response = self.client.get("/flow")
        body = flow_response.get_data(as_text=True)

        self.assertEqual(flow_response.status_code, 200)
        self.assertIn("Cobertura: OPERATIVOS", body)
        self.assertIn("Abrir en LENS", body)
        self.assertIn(f'href="/coverages/{coverage_id}"', body)

    def register_lens_web_coverage(self):
        coverage = copy.deepcopy(self.coverages["cov-1"])
        web.coverages["cov-1"] = coverage
        self.app.extensions["lens"]["coverage_store"].set("cov-1", coverage)

    def test_thumbnail_endpoint_generates_from_storage_path(self):
        self.register_lens_web_coverage()

        response = self.client.get("/coverages/cov-1/photos/photo-approved/thumbnail")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/jpeg")
        self.assertEqual(len(list(self.thumbnail_root.glob("*.jpg"))), 1)
        response.close()

    def test_thumbnail_endpoint_generates_from_flow_path(self):
        photo = self.register_ingest_photo(filename="FLOW001.jpg", valid_jpeg=True)

        response = self.client.get(f"/flow/photos/{photo['id']}/thumbnail")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/jpeg")
        self.assertEqual(len(list(self.thumbnail_root.glob("*.jpg"))), 1)
        response.close()

    def test_flow_and_lens_reuse_same_thumbnail_cache(self):
        photo = self.register_ingest_photo(filename="FLOW002.jpg", valid_jpeg=True)
        _, conversion = self.convert_first_flow_session()
        coverage_id = conversion.headers["Location"].rsplit("/", 1)[-1]

        flow_response = self.client.get(f"/flow/photos/{photo['id']}/thumbnail")
        coverage_response = self.client.get(f"/coverages/{coverage_id}/photos/{photo['id']}/thumbnail")

        self.assertEqual(flow_response.status_code, 200)
        self.assertEqual(coverage_response.status_code, 200)
        self.assertEqual(len(list(self.thumbnail_root.glob("*.jpg"))), 1)
        flow_response.close()
        coverage_response.close()

    def test_thumbnail_generation_does_not_modify_original(self):
        photo = self.register_ingest_photo(filename="FLOW003.jpg", valid_jpeg=True)
        source_path = Path(photo["path"])
        before = source_path.read_bytes()
        before_stat = source_path.stat()

        response = self.client.get(f"/flow/photos/{photo['id']}/thumbnail")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(source_path.read_bytes(), before)
        self.assertEqual(source_path.stat().st_size, before_stat.st_size)
        response.close()

    def test_flow_shows_real_size_when_file_exists(self):
        photo = self.register_ingest_photo(filename="FLOW004.jpg", valid_jpeg=True)
        expected_size = Path(photo["path"]).stat().st_size

        body = self.client.get("/flow").get_data(as_text=True)

        self.assertIn(f"{expected_size} B", body)
        self.assertNotIn("0 B", body)

    def test_missing_flow_file_uses_placeholder_without_error(self):
        photo = self.register_ingest_photo(filename="FLOW005.jpg", valid_jpeg=True)
        Path(photo["path"]).unlink()

        body = self.client.get("/flow").get_data(as_text=True)
        thumbnail = self.client.get(f"/flow/photos/{photo['id']}/thumbnail")

        self.assertIn("Miniatura pendiente", body)
        self.assertEqual(thumbnail.status_code, 404)

    def test_thumbnail_routes_reject_path_traversal(self):
        flow_response = self.client.get("/flow/photos/..%2Fsecret/thumbnail")
        coverage_response = self.client.get("/coverages/cov-1/photos/..%2Fsecret/thumbnail")

        self.assertEqual(flow_response.status_code, 404)
        self.assertEqual(coverage_response.status_code, 404)

    def test_traditional_lens_photo_still_uses_thumbnail_url(self):
        self.register_lens_web_coverage()

        body = self.client.get("/coverages/cov-1").get_data(as_text=True)
        thumbnail = self.client.get("/coverages/cov-1/photos/photo-approved/thumbnail")
        media = self.client.get("/coverages/cov-1/photos/photo-approved/media")

        self.assertIn("/coverages/cov-1/photos/photo-approved/thumbnail", body)
        self.assertEqual(thumbnail.status_code, 200)
        self.assertEqual(media.status_code, 200)
        thumbnail.close()
        media.close()

    def test_flow_coverage_in_lens_has_valid_thumbnail_url(self):
        photo = self.register_ingest_photo(filename="FLOW006.jpg", valid_jpeg=True)
        _, conversion = self.convert_first_flow_session()
        coverage_id = conversion.headers["Location"].rsplit("/", 1)[-1]

        body = self.client.get(f"/coverages/{coverage_id}").get_data(as_text=True)
        thumbnail = self.client.get(f"/coverages/{coverage_id}/photos/{photo['id']}/thumbnail")

        self.assertIn(f"/coverages/{coverage_id}/photos/{photo['id']}/thumbnail", body)
        self.assertEqual(thumbnail.status_code, 200)
        thumbnail.close()

    def test_get_dispatch_index_with_history_table(self):
        self.create_shipment()

        response = self.client.get("/dispatch/")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Historial de despachos", body)
        self.assertIn("dispatch-shipment-row", body)
        self.assertIn("Despacho Quito", body)
        self.assertIn("Cobertura Quito", body)
        self.assertIn(">Ver</a>", body)
        self.assertIn("Editar", body)
        self.assertIn("Duplicar", body)
        self.assertIn("Eliminar", body)
        self.assertIn("Sin programación", body)
        self.assertNotIn("<table>", body)
        self.assertNotIn("Ver detalle", body)
        self.assertNotIn("T", body.split("Historial de despachos", 1)[-1])

    def test_dispatch_index_links_to_new_shipment(self):
        response = self.client.get("/dispatch/")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn('href="/dispatch/new"', body)
        self.assertIn("Nuevo despacho", body)

    def test_get_dispatch_new(self):
        response = self.client.get("/dispatch/new")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Nuevo despacho", body)
        self.assertIn("Cobertura Quito", body)
        self.assertIn("Selecciona una cobertura", body)
        self.assertIn('name="recipient_name[]"', body)
        self.assertIn('name="recipient_email[]"', body)
        self.assertIn("Agregar destinatario", body)
        self.assertNotIn("Nombre | correo@dominio.com", body)
        self.assertIn("Guardar como borrador", body)
        self.assertIn("Enviar ahora", body)
        self.assertIn("Programar envío", body)
        self.assertIn("America/Guayaquil", body)
        self.assertNotIn("Cambiar zona horaria", body)
        self.assertNotIn("Detectada automáticamente", body)
        self.assertIn("Este despacho se guardará como borrador.", body)
        self.assertIn("Incluir documento Word con captions", body)
        self.assertIn('src="/static/js/dispatch_form.js"', body)
        self.assertIn('class="dispatch-schedule-mode delivery-mode-options"', body)
        self.assertIn('class="dispatch-mode-help delivery-mode-summary"', body)
        self.assertIn('data-scheduled-delivery-fields hidden', body)
        self.assertIn('id="scheduled_date" name="scheduled_date" type="date" value="" disabled', body)
        self.assertIn('id="scheduled_time" name="scheduled_time" type="time" value="" disabled', body)
        self.assertNotIn('data-timezone-panel', body)
        self.assertNotIn("Cambiar", body.split("Entrega", 1)[-1].split("Fotografías con caption", 1)[0])
        self.assertEqual(body.count('name="timezone"'), 1)
        self.assertIn('class="coverage-summary-grid"', body)
        self.assertIn('data-content-summary', body)
        self.assertIn("Documento Word incluido", body)

    def test_get_dispatch_new_immediate_hides_date_time_and_uses_single_timezone_control(self):
        response = self.client.post("/dispatch/new", data=self.valid_form(mode="immediate", name=""), follow_redirects=False)

        self.assertEqual(response.status_code, 400)
        body = response.get_data(as_text=True)
        self.assertIn('id="dispatch_mode_immediate" type="radio" name="mode" value="immediate" checked', body)
        self.assertIn("Este despacho se preparará para envío inmediato.", body)
        self.assertIn("Preparar envío ahora", body)
        self.assertNotIn("Cambiar zona horaria", body)
        self.assertIn('data-scheduled-delivery-fields hidden', body)
        self.assertIn('id="scheduled_date" name="scheduled_date" type="date" value="" disabled', body)
        self.assertIn('id="scheduled_time" name="scheduled_time" type="time" value="" disabled', body)
        self.assertNotIn('data-timezone-panel', body)
        self.assertIn('id="timezone" name="timezone" data-preserve-timezone="true" disabled', body)
        self.assertEqual(body.count('name="timezone"'), 1)

    def test_get_dispatch_new_schedule_shows_date_time_and_single_timezone_reference(self):
        response = self.client.post(
            "/dispatch/new",
            data=self.valid_form(
                mode="schedule",
                name="",
                scheduled_date="2099-08-04",
                scheduled_time="09:45",
            ),
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 400)
        body = response.get_data(as_text=True)
        self.assertIn('id="dispatch_mode_schedule" type="radio" name="mode" value="schedule" checked', body)
        self.assertIn('data-scheduled-delivery-fields', body)
        self.assertNotIn('data-scheduled-delivery-fields hidden', body)
        self.assertIn('id="scheduled_date" name="scheduled_date" type="date" value="2099-08-04"', body)
        self.assertIn('id="scheduled_time" name="scheduled_time" type="time" value="09:45"', body)
        self.assertNotIn('data-timezone-panel', body)
        self.assertNotIn('Cambiar zona horaria', body)
        self.assertEqual(body.count('name="timezone"'), 1)
        self.assertEqual(body.count("<label for=\"timezone\">"), 1)

    def test_get_dispatch_new_with_valid_coverage_id(self):
        response = self.client.get("/dispatch/new?coverage_id=cov-1")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Cobertura", body)
        self.assertIn("IMG001.jpg", body)
        self.assertIn("IMG002.jpg", body)
        self.assertIn("IMG003.jpg", body)
        self.assertIn('value="photo-approved" checked', body)

    def test_get_dispatch_new_with_invalid_coverage_id(self):
        response = self.client.get("/dispatch/new?coverage_id=missing")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("La cobertura indicada no existe.", body)
        self.assertIn("Selecciona una cobertura", body)

    def test_post_dispatch_new_with_invalid_query_coverage_does_not_create(self):
        response = self.client.post(
            "/dispatch/new?coverage_id=missing",
            data=self.valid_form(),
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("La cobertura indicada no existe.", response.get_data(as_text=True))
        self.assertEqual(self.shipment_service.list_shipments(), [])

    def valid_form(self, **overrides):
        form = {
            "name": "Despacho desde formulario",
            "coverage_id": "cov-1",
            "photo_ids": ["photo-approved"],
            "recipient_name[]": ["Mesa Xinhua"],
            "recipient_email[]": ["desk@xinhua.com"],
            "delivery_note": "Lista para despacho.",
            "channel": "Manual",
            "mode": "draft",
            "scheduled_date": "",
            "scheduled_time": "",
            "timezone": "America/Guayaquil",
            "include_caption_docx": "1",
        }
        form.update(overrides)
        form = {
            key: value
            for key, value in form.items()
            if value is not None
        }
        return form

    def post_new(self, **overrides):
        return self.client.post(
            "/dispatch/new",
            data=self.valid_form(**overrides),
            follow_redirects=False,
        )

    def test_post_dispatch_new_valid_redirects_and_persists(self):
        response = self.post_new()

        self.assertEqual(response.status_code, 302)
        self.assertIn("/dispatch/ship-", response.headers["Location"])
        shipments = self.shipment_service.list_shipments()
        self.assertEqual(len(shipments), 1)
        self.assertEqual(shipments[0]["name"], "Despacho desde formulario")
        self.assertEqual(shipments[0]["status"], "Borrador")
        self.assertEqual(shipments[0]["channel"], "Enlace de descarga")
        self.assertEqual(shipments[0]["delivery_method"], "download_link")
        self.assertEqual(shipments[0]["recipients"], [{"name": "Mesa Xinhua", "email": "desk@xinhua.com"}])
        self.assertTrue(shipments[0]["include_caption_docx"])
        self.assertEqual(shipments[0]["export_reference"]["caption_docx"]["generator"], "ExportService")
        self.assertEqual(shipments[0]["scheduled_at"], "")
        self.assertEqual(shipments[0]["timezone"], "America/Guayaquil")
        self.assertEqual(shipments[0]["requested_delivery_mode"], "draft")

    def test_post_dispatch_new_ignores_empty_recipient_rows(self):
        response = self.post_new(
            **{
                "recipient_name[]": ["Mesa Xinhua", ""],
                "recipient_email[]": ["desk@xinhua.com", ""],
            }
        )

        self.assertEqual(response.status_code, 302)
        shipment = self.shipment_service.list_shipments()[0]
        self.assertEqual(shipment["recipients"], [{"name": "Mesa Xinhua", "email": "desk@xinhua.com"}])

    def test_post_dispatch_new_allows_unchecking_caption_docx_when_photo_is_selected(self):
        response = self.post_new(include_caption_docx=None)

        self.assertEqual(response.status_code, 302)
        shipment = self.shipment_service.list_shipments()[0]
        self.assertFalse(shipment["include_caption_docx"])
        self.assertFalse(shipment["export_reference"]["caption_docx"]["include"])

    def test_post_dispatch_new_allows_caption_docx_without_selected_photos(self):
        response = self.post_new(photo_ids=[])

        self.assertEqual(response.status_code, 302)
        shipment = self.shipment_service.list_shipments()[0]
        self.assertEqual(shipment["photo_ids"], [])
        self.assertTrue(shipment["include_caption_docx"])
        self.assertEqual(shipment["export_reference"]["caption_docx"]["photo_scope"], "all_eligible")

    def test_post_dispatch_new_valid_schedule_redirects_and_persists(self):
        response = self.post_new(
            mode="schedule",
            scheduled_date="2099-08-04",
            scheduled_time="09:45",
            timezone="America/Guayaquil",
        )

        self.assertEqual(response.status_code, 302)
        shipment = self.shipment_service.list_shipments()[0]
        self.assertEqual(shipment["status"], "Programado")
        self.assertEqual(shipment["scheduled_at"], "2099-08-04T14:45:00+00:00")
        self.assertEqual(shipment["timezone"], "America/Guayaquil")
        self.assertEqual(shipment["requested_delivery_mode"], "schedule")

    def test_post_dispatch_new_valid_schedule_accepts_browser_timezone_and_stores_utc(self):
        response = self.post_new(
            mode="schedule",
            scheduled_date="2099-08-04",
            scheduled_time="09:45",
            timezone="Europe/Madrid",
        )

        self.assertEqual(response.status_code, 302)
        shipment = self.shipment_service.list_shipments()[0]
        self.assertEqual(shipment["timezone"], "Europe/Madrid")
        self.assertEqual(datetime.fromisoformat(shipment["scheduled_at"]).tzinfo, timezone.utc)
        self.assertIn("T07:45:00+00:00", shipment["scheduled_at"])

    def test_post_dispatch_new_immediate_creates_due_programmed_without_marking_sent(self):
        with patch("app.routes.dispatch.datetime") as datetime_mock:
            datetime_mock.now.return_value = datetime(2026, 8, 4, 14, 45, tzinfo=timezone.utc)
            datetime_mock.fromisoformat.side_effect = datetime.fromisoformat
            response = self.post_new(mode="immediate", timezone="America/Guayaquil")

        self.assertEqual(response.status_code, 302)
        shipment = self.shipment_service.list_shipments()[0]
        self.assertEqual(shipment["status"], "Programado")
        self.assertEqual(shipment["requested_delivery_mode"], "immediate")
        self.assertEqual(shipment["scheduled_at"], "2026-08-04T14:45:00+00:00")
        self.assertEqual(shipment["timezone"], "America/Guayaquil")
        self.assertEqual(shipment["sent_at"], "")
        scheduler = DispatchScheduler(self.shipment_service.store)
        due = scheduler.list_due_shipments(datetime(2026, 8, 4, 14, 45, tzinfo=timezone.utc))
        self.assertEqual([item["id"] for item in due], [shipment["id"]])

    def test_post_dispatch_new_rejects_past_schedule(self):
        response = self.post_new(
            mode="schedule",
            scheduled_date="2000-01-01",
            scheduled_time="09:45",
            timezone="America/Guayaquil",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("La fecha y hora de envío no puede estar en el pasado.", response.get_data(as_text=True))

    def test_post_dispatch_new_rejects_invalid_timezone(self):
        response = self.post_new(
            mode="schedule",
            scheduled_date="2099-08-04",
            scheduled_time="09:45",
            timezone="Invalid/Zone",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("La zona horaria seleccionada no es válida.", response.get_data(as_text=True))

    def test_post_dispatch_new_missing_name(self):
        response = self.post_new(name="")

        self.assertEqual(response.status_code, 400)
        body = response.get_data(as_text=True)
        self.assertIn("El nombre del despacho es obligatorio.", body)
        self.assertIn('value="Mesa Xinhua"', body)
        self.assertIn('value="desk@xinhua.com"', body)

    def test_post_dispatch_new_missing_coverage(self):
        response = self.post_new(coverage_id="")

        self.assertEqual(response.status_code, 400)
        self.assertIn("Selecciona una cobertura.", response.get_data(as_text=True))

    def test_post_dispatch_new_missing_photos(self):
        response = self.post_new(photo_ids=[], include_caption_docx=None)

        self.assertEqual(response.status_code, 400)
        self.assertIn("Seleccione al menos una fotografía o incluya el documento Word con captions.", response.get_data(as_text=True))

    def test_post_dispatch_new_accepts_legacy_status_when_caption_and_file_are_available(self):
        review_file = self.lens_media_root / "coverages" / "cov-1" / "photo-review_IMG002.jpg"
        review_file.write_bytes(b"\xff\xd8\xff\xe0ATLASJPEG\xff\xd9")
        self.coverages["cov-1"]["photos"][1]["storage_path"] = "coverages/cov-1/photo-review_IMG002.jpg"
        self.coverages["cov-1"]["photos"][1]["available_on_disk"] = True
        response = self.post_new(photo_ids=["photo-review"])

        self.assertEqual(response.status_code, 302)

    def test_post_dispatch_new_rejects_empty_caption(self):
        response = self.post_new(photo_ids=["photo-empty"])

        self.assertEqual(response.status_code, 400)
        self.assertIn("Selecciona únicamente fotografías con caption y archivo disponible para envío.", response.get_data(as_text=True))

    def test_post_dispatch_new_missing_recipients(self):
        channel = self.create_outbound_channel()
        response = self.post_new(
            delivery_method="download_link_email",
            channel="Correo (SMTP)",
            channel_id=channel["id"],
            **{"recipient_name[]": [""], "recipient_email[]": [""]},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Agrega al menos un destinatario.", response.get_data(as_text=True))

    def test_post_dispatch_new_rejects_incomplete_recipient_rows(self):
        response = self.post_new(**{"recipient_name[]": ["Mesa Xinhua"], "recipient_email[]": [""]})

        self.assertEqual(response.status_code, 400)
        body = response.get_data(as_text=True)
        self.assertIn("Corrige los destinatarios marcados.", body)
        self.assertIn("El correo electrónico es obligatorio.", body)
        self.assertIn('value="Mesa Xinhua"', body)

    def test_post_dispatch_new_rejects_recipient_pipe_character(self):
        response = self.post_new(**{"recipient_name[]": ["Mesa | Xinhua"], "recipient_email[]": ["desk@xinhua.com"]})

        self.assertEqual(response.status_code, 400)
        self.assertIn("No use el carácter |. Escriba nombre y correo en campos separados.", response.get_data(as_text=True))

    def test_dispatch_form_javascript_supports_recipient_rows(self):
        script = (Path(__file__).parents[1] / "app" / "static" / "js" / "dispatch_form.js").read_text()

        self.assertIn("data-recipient-add", script)
        self.assertIn("data-recipient-remove", script)
        self.assertIn("cloneNode", script)
        self.assertIn("renumberRecipients", script)
        self.assertIn('replaceAll("|", "")', script)
        self.assertIn("Intl.DateTimeFormat().resolvedOptions().timeZone", script)
        self.assertIn("Preparar envío ahora", script)
        self.assertIn("Este despacho se preparará para envío inmediato", script)
        self.assertIn("applyDeliveryModeState", script)
        self.assertIn("data-scheduled-delivery-fields", script)
        self.assertIn("data-content-summary", script)
        self.assertNotIn("data-timezone-toggle", script)
        self.assertIn("setScheduleInputsEnabled", script)
        self.assertIn("aria-hidden", script)
        self.assertIn("input.disabled = !enabled", script)

    def test_dispatch_new_uses_compact_photo_grid_markup(self):
        response = self.client.get("/dispatch/new?coverage_id=cov-1")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn('class="dispatch-photo-options"', body)
        self.assertIn('class="dispatch-photo-option', body)
        self.assertIn('class="dispatch-photo-thumb"', body)
        self.assertIn('name="photo_ids" value="photo-approved" checked', body)

    def test_dispatch_photo_selection_css_is_compact_and_responsive(self):
        stylesheet = (Path(__file__).parents[1] / "app" / "static" / "css" / "main.css").read_text()

        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr));", stylesheet)
        self.assertIn("-webkit-line-clamp: 3;", stylesheet)
        self.assertIn("text-overflow: ellipsis;", stylesheet)
        self.assertIn("height: 80px;", stylesheet)
        self.assertIn("width: 110px;", stylesheet)
        self.assertIn(".dispatch-photo-options,\n    .dispatch-recipient-row {\n        grid-template-columns: 1fr;", stylesheet)
        self.assertIn(".atlas-grid--2", stylesheet)
        self.assertIn("--page-max-width: 1450px;", stylesheet)
        self.assertIn(".atlas-dashboard-hero", stylesheet)
        self.assertIn(".atlas-module-grid", stylesheet)
        self.assertIn(".atlas-upcoming-grid", stylesheet)
        self.assertIn(".atlas-module-card__cta", stylesheet)
        self.assertIn("@media (max-width: 1024px)", stylesheet)
        self.assertIn("@media (max-width: 720px)", stylesheet)

    def test_delivery_public_background_assets_are_lightweight_and_accessible(self):
        root = Path(__file__).parents[1]
        stylesheet = (root / "app" / "static" / "css" / "main.css").read_text()
        script = (root / "app" / "static" / "js" / "delivery_backgrounds.js").read_text()

        self.assertIn(".delivery-background-layer", stylesheet)
        self.assertIn("filter: blur(22px) saturate(0.54) brightness(0.42);", stylesheet)
        self.assertIn("overflow-y: auto;", stylesheet)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr));", stylesheet)
        self.assertIn("grid-template-columns: 56px minmax(0, 1fr) auto;", stylesheet)
        self.assertIn("@media (prefers-reduced-motion: reduce)", stylesheet)
        self.assertIn("@keyframes deliveryKenBurns", stylesheet)
        self.assertIn("data-delivery-backgrounds", script)
        self.assertIn("DOMContentLoaded", script)
        self.assertIn("setInterval", script)
        self.assertIn("9000", script)
        self.assertIn("prefers-reduced-motion: reduce", script)
        self.assertLess((root / "app" / "static" / "js" / "delivery_backgrounds.js").stat().st_size, 5 * 1024)
        self.assertIn(".atlas-container", stylesheet)
        self.assertIn(".app-header-inner", stylesheet)
        self.assertIn(".atlas-panel--compact", stylesheet)
        self.assertIn(".coverage-summary-grid", stylesheet)
        self.assertIn(".scheduled-delivery-fields", stylesheet)
        self.assertIn(".dispatch-new-page .form-card", stylesheet)

    def test_post_dispatch_new_rejects_missing_coverage(self):
        response = self.post_new(coverage_id="missing")

        self.assertEqual(response.status_code, 400)
        self.assertIn("La cobertura no existe.", response.get_data(as_text=True))

    def test_post_dispatch_new_rejects_missing_photo(self):
        response = self.post_new(photo_ids=["missing-photo"])

        self.assertEqual(response.status_code, 400)
        self.assertIn("La fotografía no existe.", response.get_data(as_text=True))

    def test_post_dispatch_new_does_not_mutate_lens_data(self):
        self.post_new()

        self.assertEqual(self.coverages, self.original_coverages)

    def test_lens_route_uses_atlas_shell_with_lens_active(self):
        response = self.client.get("/lens")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("ATLAS", body)
        self.assertRegex(
            body,
            r'class="atlas-nav-link is-active"[\s\S]*aria-current="page"[\s\S]*>LENS</a>',
        )

    def test_dispatch_route_uses_atlas_shell_with_dispatch_active(self):
        response = self.client.get("/dispatch/")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn('class="app-header"', body)
        self.assertIn('class="atlas-container app-header-inner"', body)
        self.assertIn('class="atlas-container view-content dispatch-page"', body)
        self.assertRegex(
            body,
            r'class="atlas-nav-link is-active"[\s\S]*aria-current="page"[\s\S]*>DISPATCH</a>',
        )
        self.assertNotIn("Cobertura activa", body)

    def test_get_dispatch_detail_existing(self):
        shipment = self.create_shipment()

        response = self.client.get(f"/dispatch/{shipment['id']}")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Despacho Quito", body)
        self.assertIn("Borrador", body)
        self.assertIn("Cobertura Quito", body)
        self.assertIn("Mesa", body)
        self.assertIn("Información técnica", body)
        self.assertIn("Historial", body)
        self.assertIn("IMG001.jpg", body)
        self.assertIn("Persona participa en evento.", body)
        self.assertIn("Aprobado", body)
        self.assertIn("/coverages/cov-1/photos/photo-approved/media", body)
        self.assertIn("Fotografías (1)", body)
        self.assertIn("Destinatarios</dt>", body)
        self.assertNotIn("handoff", body.lower())
        self.assertNotIn("{&#39;", body)
        self.assertNotIn("ExportService", body)
        self.assertNotIn("No programado", body)
        self.assertNotIn("Sin intentos", body)
        self.assertNotIn("No enviado", body)
        self.assertNotIn("Sin errores", body)
        self.assertNotIn("+00:00", body)
        self.assertNotIn("T18:", body)

    def test_dispatch_detail_draft_operational_summary(self):
        shipment = self.create_docx_shipment_from_route(channel_id="xinhua")

        body = self.client.get(f"/dispatch/{shipment['id']}").get_data(as_text=True)

        self.assertIn("Borrador con 1 fotografía y un documento Word para 1 destinatario.", body)

    def test_dispatch_detail_programmed_operational_summary(self):
        shipment = self.create_docx_shipment_from_route(
            mode="schedule",
            scheduled_date="2099-08-04",
            scheduled_time="09:45",
        )

        body = self.client.get(f"/dispatch/{shipment['id']}").get_data(as_text=True)

        self.assertIn(
            "Se enviarán 1 fotografía y un documento Word a 1 destinatario el 4 de agosto de 2099 a las 09:45 (America/Guayaquil).",
            body,
        )

    def test_dispatch_detail_immediate_pending_summary(self):
        shipment = self.create_docx_shipment_from_route(mode="immediate")

        body = self.client.get(f"/dispatch/{shipment['id']}").get_data(as_text=True)

        self.assertIn("Se prepararán 1 fotografía y un documento Word para 1 destinatario", body)
        form_body = self.client.post(
            "/dispatch/new",
            data=self.valid_form(mode="immediate", name=""),
            follow_redirects=False,
        ).get_data(as_text=True)
        self.assertIn("Este despacho se preparará para envío inmediato.", form_body)

    def test_dispatch_detail_sent_operational_summary_uses_sent_at(self):
        shipment = self.create_docx_shipment_from_route()
        shipment = self.save_shipment_changes(
            shipment,
            status="Enviado",
            sent_at="2026-08-05T14:45:00+00:00",
        )

        body = self.client.get(f"/dispatch/{shipment['id']}").get_data(as_text=True)

        self.assertIn(
            "Se enviaron 1 fotografía y un documento Word a 1 destinatario el 5 de agosto de 2026 a las 09:45.",
            body,
        )

    def test_dispatch_detail_error_operational_summary_with_secondary_error(self):
        shipment = self.create_docx_shipment_from_route(
            mode="schedule",
            scheduled_date="2099-08-04",
            scheduled_time="09:45",
        )
        shipment = self.save_shipment_changes(
            shipment,
            status="Error",
            last_error="SMTP no configurado.",
        )

        body = self.client.get(f"/dispatch/{shipment['id']}").get_data(as_text=True)

        self.assertIn("El despacho de 1 fotografía y un documento Word para 1 destinatario no pudo completarse.", body)
        self.assertIn("<small>SMTP no configurado.</small>", body)

    def test_dispatch_detail_cancelled_operational_summary(self):
        shipment = self.create_docx_shipment_from_route(
            mode="schedule",
            scheduled_date="2099-08-04",
            scheduled_time="09:45",
        )
        shipment = self.save_shipment_changes(shipment, status="Cancelado")

        body = self.client.get(f"/dispatch/{shipment['id']}").get_data(as_text=True)

        self.assertIn("La programación de 1 fotografía y un documento Word para 1 destinatario fue cancelada.", body)

    def test_dispatch_detail_recipient_summary_for_multiple_recipients(self):
        shipment = self.create_docx_shipment_from_route()
        shipment = self.save_shipment_changes(
            shipment,
            status="Enviando",
            recipients=[
                {"name": "Ricardo Landetta", "email": "rlandetta@gmail.com"},
                {"name": "", "email": "desk@xinhua.com"},
                {"name": "AFP Photo Desk", "email": "photo@afp.com"},
            ],
        )

        body = self.client.get(f"/dispatch/{shipment['id']}").get_data(as_text=True)

        self.assertIn("Se están enviando 1 fotografía y un documento Word a 3 destinatarios.", body)
        self.assertNotIn("[{", body)
        self.assertNotIn("{&#39;", body)

    def test_dispatch_detail_excludes_docx_text_when_not_included(self):
        shipment = self.create_shipment()

        body = self.client.get(f"/dispatch/{shipment['id']}").get_data(as_text=True)

        self.assertIn("Borrador con 1 fotografía para 1 destinatario.", body)
        self.assertNotIn("1 fotografía y un documento Word", body)

    def test_dispatch_detail_presents_docx_humanly(self):
        shipment = self.create_docx_shipment_from_route()

        body = self.client.get(f"/dispatch/{shipment['id']}").get_data(as_text=True)

        self.assertIn("Información del envío", body)
        self.assertIn("Documento Word", body)
        self.assertIn("Sí", body)
        self.assertIn("Fotografías</dt>", body)
        self.assertIn("<dd>1</dd>", body)
        self.assertNotIn("Contenido del despacho", body)
        self.assertNotIn("Alcance del documento", body)
        self.assertNotIn("Fotografías seleccionadas", body)
        self.assertNotIn("Fotografías incluidas", body)
        self.assertNotIn("caption_docx", body)
        self.assertNotIn("photo_scope", body)
        self.assertNotIn("include", body)
        self.assertNotIn("generator", body)

    def test_dispatch_detail_presents_scheduled_date_in_guayaquil(self):
        shipment = self.create_docx_shipment_from_route(
            mode="schedule",
            scheduled_date="2099-08-04",
            scheduled_time="09:45",
            timezone="America/Guayaquil",
        )

        body = self.client.get(f"/dispatch/{shipment['id']}").get_data(as_text=True)

        self.assertIn("Programado para", body)
        self.assertIn("4 de agosto de 2099, 09:45", body)
        self.assertIn("America/Guayaquil (UTC-5)", body)
        self.assertIn("14:45 UTC", body)
        self.assertNotIn("2099-08-04T14:45:00+00:00", body)

    def test_dispatch_detail_truncates_long_caption_excerpt(self):
        long_caption = (
            "Policías verifican documentos y realizan inspecciones a motociclistas durante un operativo "
            "de control en el sector de La Carolina, como parte de las acciones preventivas desplegadas "
            "por las autoridades locales durante la jornada."
        )
        self.coverages["cov-1"]["photos"][0]["caption_narrative"] = long_caption
        shipment = self.create_shipment()

        body = self.client.get(f"/dispatch/{shipment['id']}").get_data(as_text=True)

        self.assertIn("Policías verifican documentos", body)
        self.assertIn("…", body)
        self.assertNotIn("durante la jornada.", body)

    def test_dispatch_index_filters_by_status_and_handles_invalid_status(self):
        draft = self.create_docx_shipment_from_route()
        scheduled = self.create_docx_shipment_from_route(
            name="Despacho programado",
            mode="schedule",
            scheduled_date="2099-08-04",
            scheduled_time="09:45",
        )

        body = self.client.get("/dispatch/?status=Programado").get_data(as_text=True)

        self.assertIn("Programados", body)
        self.assertIn("Despacho programado", body)
        self.assertNotIn(f"<h3>{draft['name']}</h3>", body)
        self.assertIn('href="/dispatch/?status=Programado" class="dispatch-filter-chip is-active"', body)

        invalid_body = self.client.get("/dispatch/?status=Invalido").get_data(as_text=True)
        self.assertIn("Despacho programado", invalid_body)
        self.assertIn(draft["name"], invalid_body)
        self.assertIn('href="/dispatch/" class="dispatch-filter-chip is-active"', invalid_body)

    def test_dispatch_index_orders_programmed_before_drafts_and_errors(self):
        draft = self.create_docx_shipment_from_route(name="Borrador final")
        error = self.save_shipment_changes(self.create_docx_shipment_from_route(name="Error medio"), status="Error")
        scheduled = self.create_docx_shipment_from_route(
            name="Programado primero",
            mode="schedule",
            scheduled_date="2099-08-04",
            scheduled_time="09:45",
        )

        body = self.client.get("/dispatch/").get_data(as_text=True)

        self.assertLess(body.index(scheduled["name"]), body.index(draft["name"]))
        self.assertLess(body.index(draft["name"]), body.index(error["name"]))

    def test_dispatch_index_empty_filtered_state_is_clear(self):
        self.create_docx_shipment_from_route()

        body = self.client.get("/dispatch/?status=Programado").get_data(as_text=True)

        self.assertIn("No hay despachos con este estado", body)
        self.assertNotIn("<table>", body)

    def test_get_dispatch_edit_loads_existing_data(self):
        shipment = self.create_docx_shipment_from_route()

        response = self.client.get(f"/dispatch/{shipment['id']}/edit")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Editar despacho", body)
        self.assertIn('action="/dispatch/' + shipment["id"] + '/edit"', body)
        self.assertIn('value="Despacho desde formulario"', body)
        self.assertIn('value="Mesa Xinhua"', body)
        self.assertIn("Guardar cambios", body)

    def test_post_dispatch_edit_updates_fields_preserves_identity_and_history(self):
        shipment = self.create_docx_shipment_from_route()
        created_at = shipment["created_at"]

        response = self.client.post(
            f"/dispatch/{shipment['id']}/edit",
            data=self.valid_form(name="Despacho editado", delivery_note="Nota editada."),
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        updated = self.shipment_service.get_shipment(shipment["id"])
        self.assertEqual(updated["id"], shipment["id"])
        self.assertEqual(updated["created_at"], created_at)
        self.assertNotEqual(updated["updated_at"], shipment["updated_at"])
        self.assertEqual(updated["name"], "Despacho editado")
        self.assertEqual(updated["delivery_note"], "Nota editada.")
        self.assertEqual(updated["history"][0]["note"], "Despacho editado.")

    def test_post_dispatch_edit_updates_schedule_history_note(self):
        shipment = self.create_docx_shipment_from_route()

        response = self.client.post(
            f"/dispatch/{shipment['id']}/edit",
            data=self.valid_form(
                mode="schedule",
                scheduled_date="2099-08-04",
                scheduled_time="09:45",
            ),
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        updated = self.shipment_service.get_shipment(shipment["id"])
        self.assertEqual(updated["status"], "Programado")
        self.assertEqual(updated["scheduled_at"], "2099-08-04T14:45:00+00:00")
        self.assertEqual(updated["history"][0]["note"], "Programación actualizada.")

    def test_dispatch_edit_rejects_sending_and_sent(self):
        sending = self.save_shipment_changes(self.create_docx_shipment_from_route(name="Enviando"), status="Enviando")
        sent = self.save_shipment_changes(self.create_docx_shipment_from_route(name="Enviado"), status="Enviado")

        self.assertEqual(self.client.get(f"/dispatch/{sending['id']}/edit").status_code, 403)
        self.assertEqual(self.client.post(f"/dispatch/{sent['id']}/edit", data=self.valid_form()).status_code, 403)

    def test_dispatch_duplicate_creates_draft_copy_and_redirects_to_edit(self):
        shipment = self.create_docx_shipment_from_route(
            mode="schedule",
            scheduled_date="2099-08-04",
            scheduled_time="09:45",
        )

        response = self.client.post(f"/dispatch/{shipment['id']}/duplicate", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        shipments = self.shipment_service.list_shipments()
        duplicated = next(item for item in shipments if item["id"] != shipment["id"])
        self.assertIn(f"/dispatch/{duplicated['id']}/edit", response.headers["Location"])
        self.assertEqual(duplicated["name"], "Copia de Despacho desde formulario")
        self.assertEqual(duplicated["status"], "Borrador")
        self.assertEqual(duplicated["scheduled_at"], "")
        self.assertEqual(duplicated["sent_at"], "")
        self.assertEqual(duplicated["attempt_count"], 0)
        self.assertEqual(duplicated["last_error"], "")
        self.assertEqual(duplicated["coverage_id"], shipment["coverage_id"])
        self.assertEqual(duplicated["photo_ids"], shipment["photo_ids"])
        self.assertIn(f"Despacho duplicado desde {shipment['id']}.", duplicated["history"][0]["note"])

    def test_dispatch_cancel_only_programmed(self):
        scheduled = self.create_docx_shipment_from_route(
            mode="schedule",
            scheduled_date="2099-08-04",
            scheduled_time="09:45",
        )
        draft = self.create_docx_shipment_from_route(name="Borrador")

        response = self.client.post(f"/dispatch/{scheduled['id']}/cancel", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        cancelled = self.shipment_service.get_shipment(scheduled["id"])
        self.assertEqual(cancelled["status"], "Cancelado")
        self.assertEqual(cancelled["scheduled_at"], scheduled["scheduled_at"])
        self.assertEqual(cancelled["history"][0]["note"], "Programación cancelada por el usuario.")
        self.assertEqual(self.client.post(f"/dispatch/{draft['id']}/cancel").status_code, 403)

    def test_dispatch_delete_allows_draft_and_cancelled_only_and_never_by_get(self):
        draft = self.create_docx_shipment_from_route()
        cancelled = self.save_shipment_changes(self.create_docx_shipment_from_route(name="Cancelado"), status="Cancelado")
        protected = {
            "Programado": self.create_docx_shipment_from_route(
                name="Programado",
                mode="schedule",
                scheduled_date="2099-08-04",
                scheduled_time="09:45",
            ),
            "Enviando": self.save_shipment_changes(self.create_docx_shipment_from_route(name="Enviando"), status="Enviando"),
            "Enviado": self.save_shipment_changes(self.create_docx_shipment_from_route(name="Enviado"), status="Enviado"),
            "Entregado": self.save_shipment_changes(self.create_docx_shipment_from_route(name="Entregado"), status="Entregado"),
            "Error": self.save_shipment_changes(self.create_docx_shipment_from_route(name="Error"), status="Error"),
        }

        self.assertEqual(self.client.get(f"/dispatch/{draft['id']}/delete").status_code, 405)
        self.assertEqual(self.client.get(f"/dispatch/{cancelled['id']}/delete").status_code, 405)
        for shipment in protected.values():
            self.assertEqual(self.client.post(f"/dispatch/{shipment['id']}/delete").status_code, 403)
            self.assertIsNotNone(self.shipment_service.get_shipment(shipment["id"]))

        draft_response = self.client.post(f"/dispatch/{draft['id']}/delete", follow_redirects=False)
        cancelled_response = self.client.post(f"/dispatch/{cancelled['id']}/delete", follow_redirects=False)

        self.assertEqual(draft_response.status_code, 302)
        self.assertEqual(cancelled_response.status_code, 302)
        self.assertIsNone(self.shipment_service.get_shipment(draft["id"]))
        self.assertIsNone(self.shipment_service.get_shipment(cancelled["id"]))
        self.assertEqual(self.coverages, self.original_coverages)

    def test_dispatch_cancelled_delete_actions_are_visible_in_index_and_detail(self):
        cancelled = self.save_shipment_changes(self.create_docx_shipment_from_route(name="Cancelado"), status="Cancelado")

        index_body = self.client.get("/dispatch/?status=Cancelado").get_data(as_text=True)
        detail_body = self.client.get(f"/dispatch/{cancelled['id']}").get_data(as_text=True)

        self.assertIn("Eliminar cancelados", index_body)
        self.assertIn("¿Eliminar este despacho cancelado?", index_body)
        self.assertIn("Eliminar", index_body)
        self.assertIn("Duplicar", index_body)
        self.assertIn("¿Eliminar este despacho cancelado?", detail_body)
        self.assertIn("Eliminar", detail_body)
        self.assertIn("Duplicar", detail_body)
        self.assertNotIn("Editar", detail_body)
        self.assertNotIn("Cancelar programación", detail_body)

    def test_dispatch_bulk_delete_cancelled_removes_only_cancelled(self):
        cancelled_one = self.save_shipment_changes(self.create_docx_shipment_from_route(name="Cancelado 1"), status="Cancelado")
        cancelled_two = self.save_shipment_changes(self.create_docx_shipment_from_route(name="Cancelado 2"), status="Cancelado")
        draft = self.create_docx_shipment_from_route(name="Borrador")
        scheduled = self.create_docx_shipment_from_route(
            name="Programado",
            mode="schedule",
            scheduled_date="2099-08-04",
            scheduled_time="09:45",
        )

        response = self.client.post("/dispatch/delete-cancelled", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertIsNone(self.shipment_service.get_shipment(cancelled_one["id"]))
        self.assertIsNone(self.shipment_service.get_shipment(cancelled_two["id"]))
        self.assertIsNotNone(self.shipment_service.get_shipment(draft["id"]))
        self.assertIsNotNone(self.shipment_service.get_shipment(scheduled["id"]))
        self.assertEqual(self.coverages, self.original_coverages)

    def test_dispatch_bulk_delete_cancelled_with_none_is_controlled(self):
        draft = self.create_docx_shipment_from_route(name="Borrador")

        response = self.client.post("/dispatch/delete-cancelled", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(self.shipment_service.get_shipment(draft["id"]))

    def test_dispatch_detail_shows_only_allowed_actions_by_status(self):
        draft = self.create_docx_shipment_from_route()
        scheduled = self.create_docx_shipment_from_route(
            name="Programado",
            mode="schedule",
            scheduled_date="2099-08-04",
            scheduled_time="09:45",
        )
        sent = self.save_shipment_changes(self.create_docx_shipment_from_route(name="Enviado"), status="Enviado")
        sending = self.save_shipment_changes(self.create_docx_shipment_from_route(name="Enviando"), status="Enviando")

        draft_body = self.client.get(f"/dispatch/{draft['id']}").get_data(as_text=True)
        self.assertIn("Editar", draft_body)
        self.assertIn("Duplicar", draft_body)
        self.assertIn("Eliminar", draft_body)
        self.assertNotIn("Cancelar programación", draft_body)

        scheduled_body = self.client.get(f"/dispatch/{scheduled['id']}").get_data(as_text=True)
        self.assertIn("Editar", scheduled_body)
        self.assertIn("Duplicar", scheduled_body)
        self.assertIn("Cancelar programación", scheduled_body)
        self.assertNotIn("Eliminar", scheduled_body)

        sent_body = self.client.get(f"/dispatch/{sent['id']}").get_data(as_text=True)
        self.assertNotIn("Editar", sent_body)
        self.assertIn("Duplicar", sent_body)
        self.assertNotIn("Eliminar", sent_body)

        sending_body = self.client.get(f"/dispatch/{sending['id']}").get_data(as_text=True)
        self.assertNotIn("Editar", sending_body)
        self.assertNotIn("Duplicar", sending_body)
        self.assertNotIn("Eliminar", sending_body)

    def test_dispatch_new_lists_active_settings_channels_and_uses_default(self):
        default = self.create_outbound_channel(id="xinhua", name="Xinhua", credential_ref="ATLAS_SMTP_CHANNEL_XINHUA", is_default=True)
        self.create_outbound_channel(id="inactive", name="Inactivo", sender_email="inactive@example.com", credential_ref="ATLAS_SMTP_INACTIVE", is_active=False, is_default=False)

        body = self.client.get("/dispatch/new").get_data(as_text=True)

        self.assertIn('value="download_link" selected', body)
        self.assertIn("Enlace de descarga + correo", body)
        self.assertNotIn(">SFTP</option>", body)
        self.assertNotIn("API · Próximamente", body)
        self.assertNotIn("Inactivo", body)
        self.assertNotIn("No hay canales SMTP activos", body)

        response = self.post_new(delivery_method="download_link_email", channel="Correo (SMTP)", channel_id=default["id"])
        self.assertEqual(response.status_code, 302)
        shipment = self.shipment_service.list_shipments()[0]
        self.assertEqual(shipment["channel_id"], default["id"])
        self.assertEqual(shipment["channel_name_snapshot"], "Xinhua")
        self.assertEqual(shipment["delivery_method"], "download_link_email")

    def test_dispatch_new_shows_settings_link_when_no_channels_exist(self):
        body = self.client.get("/dispatch/new").get_data(as_text=True)

        self.assertIn("No hay canales SMTP activos", body)
        self.assertIn('href="/settings/channels"', body)
        self.assertIn('name="channel"', body)

    def test_dispatch_snapshot_survives_deleted_settings_channel(self):
        self.create_outbound_channel(id="xinhua", name="Xinhua", credential_ref="ATLAS_SMTP_CHANNEL_XINHUA")
        shipment = self.create_docx_shipment_from_route(delivery_method="download_link_email", channel="Correo (SMTP)", channel_id="xinhua")
        self.app.extensions["settings"]["settings_service"].delete_outbound_channel("xinhua")

        body = self.client.get(f"/dispatch/{shipment['id']}").get_data(as_text=True)

        self.assertIn("Xinhua", body)
        self.assertEqual(self.shipment_service.get_shipment(shipment["id"])["channel_name_snapshot"], "Xinhua")

    def test_dispatch_legacy_channel_string_still_displays(self):
        shipment = self.create_shipment()

        body = self.client.get(f"/dispatch/{shipment['id']}").get_data(as_text=True)

        self.assertIn("manual", body)

    def test_get_dispatch_detail_missing(self):
        response = self.client.get("/dispatch/missing")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
