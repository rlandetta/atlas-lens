import copy
import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.dispatch import DispatchShipmentStore, ShipmentService
from app.lens_read_service import LensReadService


class DispatchRoutesTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app()
        self.app.config.update(TESTING=True)
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
                        "caption_narrative": "Persona participa en evento.",
                        "caption_status": "Aprobado",
                    },
                    {
                        "id": "photo-review",
                        "name": "IMG002.jpg",
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
        store = DispatchShipmentStore(Path(self.temp_dir.name) / "dispatch_shipments.json")
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
        self.assertIn("Nombre | correo@dominio.com", body)
        self.assertIn("Guardar como borrador", body)
        self.assertIn("Programar envío", body)
        self.assertIn("America/Guayaquil", body)

    def test_get_dispatch_new_with_valid_coverage_id(self):
        response = self.client.get("/dispatch/new?coverage_id=cov-1")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Cobertura preseleccionada", body)
        self.assertIn("IMG001.jpg", body)
        self.assertNotIn("IMG002.jpg", body)
        self.assertNotIn("IMG003.jpg", body)

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
        }
        form.update(overrides)
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
        self.assertEqual(shipments[0]["scheduled_at"], "")
        self.assertEqual(shipments[0]["timezone"], "America/Guayaquil")

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
        response = self.post_new(photo_ids=[])

        self.assertEqual(response.status_code, 400)
        self.assertIn("Selecciona al menos una fotografía.", response.get_data(as_text=True))

    def test_post_dispatch_new_rejects_unapproved_photo(self):
        response = self.post_new(photo_ids=["photo-review"])

        self.assertEqual(response.status_code, 400)
        self.assertIn("La fotografía no tiene caption aprobado.", response.get_data(as_text=True))

    def test_post_dispatch_new_rejects_empty_caption(self):
        response = self.post_new(photo_ids=["photo-empty"])

        self.assertEqual(response.status_code, 400)
        self.assertIn("La fotografía aprobada no está disponible.", response.get_data(as_text=True))

    def test_post_dispatch_new_missing_recipients(self):
        response = self.post_new(recipients="")

        self.assertEqual(response.status_code, 400)
        self.assertIn("Agrega al menos un destinatario.", response.get_data(as_text=True))

    def test_post_dispatch_new_rejects_invalid_recipient_format(self):
        response = self.post_new(recipients="Mesa Xinhua desk@xinhua.com")

        self.assertEqual(response.status_code, 400)
        self.assertIn("Cada destinatario debe usar el formato", response.get_data(as_text=True))

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

    def test_get_dispatch_detail_missing(self):
        response = self.client.get("/dispatch/missing")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
