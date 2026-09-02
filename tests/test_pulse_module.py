import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.pulse.budget import XBudgetController
from app.pulse.service import PulseService
from app.pulse.store import PulseStore


class PulseModuleTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.patches = [
            patch("app.config.PULSE_STORE_PATH", str(self.root / "pulse.json")),
            patch("app.config.LENS_COVERAGE_STORE_PATH", str(self.root / "lens_coverages.json")),
            patch("app.config.LENS_MEDIA_ROOT", str(self.root / "media")),
            patch("app.config.DISPATCH_STORE_PATH", str(self.root / "dispatch.json")),
            patch("app.config.SETTINGS_STORE_PATH", str(self.root / "settings.json")),
            patch("app.config.THUMBNAIL_ROOT", str(self.root / "thumbnails")),
        ]
        for item in self.patches:
            item.start()
        self.app = create_app()
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp_dir.cleanup()

    def test_pulse_dashboard_uses_demo_backend_data(self):
        response = self.client.get("/pulse/")

        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Radar informativo", body)
        self.assertIn("Datos demo controlados", body)
        self.assertIn("Confidence Score", body)

    def test_x_budget_controller_blocks_at_internal_limit(self):
        controller = XBudgetController(monthly_budget=10.0, internal_hard_limit=9.0)

        status = controller.status([
            {"created_at": "2026-08-01T00:00:00+00:00", "estimated_cost": 9.0}
        ])

        self.assertEqual(status["state"], "BLOQUEADO")
        self.assertTrue(status["blocked"])
        self.assertFalse(controller.can_spend([
            {"created_at": "2026-08-01T00:00:00+00:00", "estimated_cost": 8.95}
        ], 0.10))

    def test_signal_ingest_deduplicates_and_groups_event(self):
        store = PulseStore(self.root / "pulse-service.json")
        service = PulseService(store)

        first = service.ingest_signal({
            "source": "Medio Local",
            "source_type": "medio",
            "source_id": "src-local",
            "text": "Reporte de cierre vial por lluvias",
            "url": "https://example.local/a",
            "location": "Quito",
            "keywords": ["lluvias", "cierre vial"],
            "raw_payload_hash": "same-payload",
        })
        second = service.ingest_signal({
            "source": "Medio Local",
            "source_type": "medio",
            "source_id": "src-local",
            "text": "Reporte de cierre vial por lluvias",
            "url": "https://example.local/a",
            "location": "Quito",
            "keywords": ["lluvias", "cierre vial"],
            "raw_payload_hash": "same-payload",
        })

        payload = store.snapshot()
        self.assertEqual(first["event_id"], second["event_id"])
        self.assertEqual(second["duplicate_of"], first["id"])
        self.assertEqual(len(payload["events"]), 1)

    def test_create_nexus_coverage_bridge_from_pulse_event(self):
        response = self.client.post("/pulse/events/pulse-demo-001/coverage", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        coverage_id = response.headers["Location"].rsplit("/", 1)[-1]
        coverage = self.app.extensions["lens"]["coverage_store"].get(coverage_id)
        self.assertIsNotNone(coverage)
        self.assertEqual(coverage["pulse_event_id"], "pulse-demo-001")
        self.assertEqual(coverage["agency"], "ATLAS NEXUS")


if __name__ == "__main__":
    unittest.main()
