import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.dispatch import DispatchShipmentStore, ShipmentService
from app.lens_read_service import LensReadService


class DispatchRoutesTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.lens_media_root = self.root / "lens_media"
        self.dispatch_store_path = self.root / "dispatch_shipments.json"
        self.lens_store_path = self.root / "lens_coverages.json"
        self.patches = [
            patch("app.config.DISPATCH_STORE_PATH", str(self.dispatch_store_path)),
            patch("app.config.LENS_COVERAGE_STORE_PATH", str(self.lens_store_path)),
            patch("app.config.LENS_MEDIA_ROOT", str(self.lens_media_root)),
        ]
        for item in self.patches:
            item.start()
        self.app = create_app()
        self.app.config.update(TESTING=True)
        approved_file = self.lens_media_root / "coverages" / "cov-1" / "photo-approved_IMG001.jpg"
        approved_file.parent.mkdir(parents=True)
        approved_file.write_bytes(b"\xff\xd8\xff\xe0ATLASJPEG\xff\xd9")
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

    def create_docx_shipment_from_route(self, **overrides):
        response = self.post_new(**overrides)
        self.assertEqual(response.status_code, 302)
        return self.shipment_service.list_shipments()[0]

    def test_dispatch_blueprint_is_registered(self):
        self.assertIn("dispatch.index", self.app.view_functions)
        self.assertIn("dispatch.new", self.app.view_functions)
        self.assertIn("dispatch.detail", self.app.view_functions)

    def test_get_dispatch_index(self):
        response = self.client.get("/dispatch/")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("ATLAS", body)
        self.assertIn("Despachos", body)
        self.assertIn("Resumen por estado", body)
        self.assertIn("Borrador", body)
        self.assertIn("Preparando", body)
        self.assertIn("Listo", body)
        self.assertIn("Programado", body)
        self.assertIn("Enviando", body)
        self.assertIn("Enviado", body)
        self.assertIn("Entregado", body)
        self.assertIn("Error", body)
        self.assertIn("Cancelado", body)
        self.assertIn("No hay despachos todavía", body)
        self.assertNotIn("Cobertura activa", body)

    def test_get_dispatch_index_with_history_table(self):
        self.create_shipment()

        response = self.client.get("/dispatch/")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("<table>", body)
        self.assertIn("Historial de despachos", body)
        self.assertIn("Despacho Quito", body)
        self.assertIn("Cobertura Quito", body)
        self.assertIn("Ver detalle", body)

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
        self.assertIn("Ejemplo: Mesa Xinhua | desk@xinhua.com", body)
        self.assertIn("Guardar como borrador", body)
        self.assertIn("Programar envío", body)
        self.assertIn("America/Guayaquil", body)
        self.assertIn("Incluir documento Word con captions", body)

    def test_get_dispatch_new_with_valid_coverage_id(self):
        response = self.client.get("/dispatch/new?coverage_id=cov-1")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Cobertura preseleccionada", body)
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
            "recipients": "Mesa Xinhua | desk@xinhua.com",
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
        self.assertEqual(shipments[0]["channel"], "Manual")
        self.assertTrue(shipments[0]["include_caption_docx"])
        self.assertEqual(shipments[0]["export_reference"]["caption_docx"]["generator"], "ExportService")
        self.assertEqual(shipments[0]["scheduled_at"], "")
        self.assertEqual(shipments[0]["timezone"], "America/Guayaquil")

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
        self.assertEqual(shipment["scheduled_at"], "2099-08-04T09:45:00-05:00")
        self.assertEqual(shipment["timezone"], "America/Guayaquil")

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
        self.assertIn("Mesa Xinhua | desk@xinhua.com", body)

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
        response = self.post_new(recipients="")

        self.assertEqual(response.status_code, 400)
        self.assertIn("Agrega al menos un destinatario.", response.get_data(as_text=True))

    def test_post_dispatch_new_rejects_invalid_recipient_format(self):
        response = self.post_new(recipients="Mesa Xinhua desk@xinhua.com")

        self.assertEqual(response.status_code, 400)
        self.assertIn("Cada destinatario debe usar el formato", response.get_data(as_text=True))
        self.assertIn("Ejemplo: Mesa Xinhua | desk@xinhua.com", response.get_data(as_text=True))

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
        response = self.client.get("/")

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
        self.assertIn("Historial de estados", body)
        self.assertIn("IMG001.jpg", body)
        self.assertIn("Persona participa en evento.", body)
        self.assertIn("Aprobado", body)
        self.assertIn("/coverages/cov-1/photos/photo-approved/media", body)
        self.assertIn("Fotografías</dt>", body)
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

    def test_dispatch_detail_presents_docx_humanly(self):
        shipment = self.create_docx_shipment_from_route()

        body = self.client.get(f"/dispatch/{shipment['id']}").get_data(as_text=True)

        self.assertIn("Contenido del despacho", body)
        self.assertIn("Documento Word con captions", body)
        self.assertIn("Incluido", body)
        self.assertIn("Alcance del documento", body)
        self.assertIn("Fotografías seleccionadas", body)
        self.assertIn("Fotografías incluidas", body)
        self.assertIn("<dd>1</dd>", body)
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
        self.assertNotIn("2099-08-04T09:45:00-05:00", body)

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

    def test_get_dispatch_detail_missing(self):
        response = self.client.get("/dispatch/missing")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
