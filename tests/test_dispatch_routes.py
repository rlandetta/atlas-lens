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
                    }
                ],
            }
        }
        store = DispatchShipmentStore(Path(self.temp_dir.name) / "dispatch_shipments.json")
        lens_reader = LensReadService(lambda: self.coverages)
        self.shipment_service = ShipmentService(store=store, lens_reader=lens_reader)
        self.app.extensions["dispatch"] = {
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
        self.assertIn("dispatch.detail", self.app.view_functions)

    def test_get_dispatch_index(self):
        response = self.client.get("/dispatch/")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Despachos", body)
        self.assertIn("Resumen por estado", body)
        self.assertIn("Borrador", body)
        self.assertIn("Preparando", body)
        self.assertIn("Listo", body)
        self.assertIn("Enviado", body)
        self.assertIn("Entregado", body)
        self.assertIn("Error", body)
        self.assertIn("No hay despachos todavía", body)

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
