import copy
import tempfile
import unittest
from pathlib import Path

from app.dispatch import (
    DispatchHandoffService,
    DispatchTransitionError,
    DispatchValidationError,
    ShipmentService,
)
from app.dispatch.store import DispatchShipmentStore
from app.export.models import ExportFile, ExportResult
from app.lens_read_service import LensReadService


def build_coverages():
    return {
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
                    "data_url": "data:image/jpeg;base64,abc",
                },
                {
                    "id": "photo-review",
                    "name": "IMG002.jpg",
                    "caption_narrative": "Persona observa actividad.",
                    "caption_status": "Revisado",
                    "data_url": "data:image/jpeg;base64,def",
                },
                {
                    "id": "photo-empty",
                    "name": "IMG003.jpg",
                    "caption_narrative": "",
                    "caption_status": "Aprobado",
                    "data_url": "data:image/jpeg;base64,ghi",
                },
            ],
        }
    }


class ShipmentServiceTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.coverages = build_coverages()
        self.original_coverages = copy.deepcopy(self.coverages)
        store = DispatchShipmentStore(Path(self.temp_dir.name) / "dispatch_shipments.json")
        reader = LensReadService(lambda: self.coverages)
        self.service = ShipmentService(store=store, lens_reader=reader)

    def tearDown(self):
        self.temp_dir.cleanup()

    def create_shipment(self):
        return self.service.create_shipment(
            name="Despacho Xinhua",
            coverage_id="cov-1",
            photo_ids=["photo-approved"],
            recipients=[{"name": "Mesa", "email": "desk@example.com"}],
            delivery_note="Lista para despacho.",
            export_reference={"zip": "coverage.zip"},
        )

    def test_create_and_read_shipment(self):
        shipment = self.create_shipment()

        self.assertEqual(shipment["status"], "Borrador")
        self.assertEqual(shipment["coverage_id"], "cov-1")
        self.assertEqual(shipment["photo_ids"], ["photo-approved"])
        self.assertEqual(shipment["export_reference"], {"zip": "coverage.zip"})
        self.assertEqual(shipment["scheduled_at"], "")
        self.assertEqual(shipment["timezone"], "America/Guayaquil")
        self.assertEqual(shipment["attempt_count"], 0)
        self.assertFalse(shipment["include_caption_docx"])
        self.assertNotIn("data_url", shipment["photo_snapshots"][0])
        self.assertEqual(self.service.get_shipment(shipment["id"])["id"], shipment["id"])

    def test_create_shipment_with_caption_docx_only(self):
        shipment = self.service.create_shipment(
            name="Despacho Word",
            coverage_id="cov-1",
            photo_ids=[],
            recipients=[{"name": "Mesa", "email": "desk@example.com"}],
            include_caption_docx=True,
            export_reference={
                "caption_docx": {
                    "include": True,
                    "format": "docx",
                    "photo_scope": "all_eligible",
                    "generator": "ExportService",
                }
            },
        )

        self.assertEqual(shipment["photo_ids"], [])
        self.assertTrue(shipment["include_caption_docx"])
        self.assertEqual(shipment["export_reference"]["caption_docx"]["generator"], "ExportService")

    def test_create_scheduled_shipment(self):
        shipment = self.service.create_shipment(
            name="Despacho programado",
            coverage_id="cov-1",
            photo_ids=["photo-approved"],
            recipients=[{"name": "Mesa", "email": "desk@example.com"}],
            status="Programado",
            scheduled_at="2026-08-04T09:45:00-05:00",
            timezone="America/Guayaquil",
        )

        self.assertEqual(shipment["status"], "Programado")
        self.assertEqual(shipment["scheduled_at"], "2026-08-04T09:45:00-05:00")
        self.assertEqual(shipment["timezone"], "America/Guayaquil")

    def test_update_shipment(self):
        shipment = self.create_shipment()

        updated = self.service.update_shipment(shipment["id"], {"delivery_note": "Nota nueva"})

        self.assertEqual(updated["delivery_note"], "Nota nueva")
        self.assertNotEqual(updated["updated_at"], shipment["updated_at"])

    def test_duplicate_shipment_copies_safe_fields_and_resets_delivery_state(self):
        shipment = self.service.create_shipment(
            name="Despacho programado",
            coverage_id="cov-1",
            photo_ids=["photo-approved"],
            recipients=[{"name": "Mesa", "email": "desk@example.com"}],
            delivery_note="Lista.",
            status="Programado",
            scheduled_at="2026-08-04T09:45:00-05:00",
            include_caption_docx=True,
            requested_delivery_mode="schedule",
        )

        duplicated = self.service.duplicate_shipment(shipment["id"])

        self.assertNotEqual(duplicated["id"], shipment["id"])
        self.assertEqual(duplicated["name"], "Copia de Despacho programado")
        self.assertEqual(duplicated["status"], "Borrador")
        self.assertEqual(duplicated["scheduled_at"], "")
        self.assertEqual(duplicated["sent_at"], "")
        self.assertEqual(duplicated["attempt_count"], 0)
        self.assertEqual(duplicated["last_error"], "")
        self.assertEqual(duplicated["coverage_id"], shipment["coverage_id"])
        self.assertEqual(duplicated["photo_ids"], shipment["photo_ids"])
        self.assertTrue(duplicated["include_caption_docx"])
        self.assertIn(shipment["id"], duplicated["history"][0]["note"])

    def test_delete_draft_allows_only_borrador(self):
        draft = self.create_shipment()
        scheduled = self.service.create_shipment(
            name="Despacho programado",
            coverage_id="cov-1",
            photo_ids=["photo-approved"],
            recipients=[{"name": "Mesa", "email": "desk@example.com"}],
            status="Programado",
            scheduled_at="2026-08-04T09:45:00-05:00",
        )

        removed = self.service.delete_draft(draft["id"])

        self.assertEqual(removed["id"], draft["id"])
        self.assertIsNone(self.service.get_shipment(draft["id"]))
        self.assertIsNotNone(self.service.get_shipment(scheduled["id"]))
        with self.assertRaises(DispatchValidationError):
            self.service.delete_draft(scheduled["id"])

    def test_valid_transition(self):
        shipment = self.create_shipment()

        updated = self.service.transition_status(shipment["id"], "Preparando")

        self.assertEqual(updated["status"], "Preparando")
        self.assertEqual(updated["history"][0]["status"], "Preparando")

    def test_invalid_transition(self):
        shipment = self.create_shipment()

        with self.assertRaises(DispatchTransitionError):
            self.service.transition_status(shipment["id"], "Enviado")

    def test_accepts_caption_regardless_of_legacy_status(self):
        shipment = self.service.create_shipment(
            name="Despacho",
            coverage_id="cov-1",
            photo_ids=["photo-review"],
            recipients=[{"name": "Mesa", "email": "desk@example.com"}],
        )

        self.assertEqual(shipment["photo_ids"], ["photo-review"])

    def test_rejects_empty_caption(self):
        with self.assertRaises(DispatchValidationError):
            self.service.create_shipment(
                name="Despacho",
                coverage_id="cov-1",
                photo_ids=["photo-empty"],
                recipients=[{"name": "Mesa", "email": "desk@example.com"}],
            )

    def test_rejects_missing_coverage(self):
        with self.assertRaises(DispatchValidationError):
            self.service.create_shipment(
                name="Despacho",
                coverage_id="missing",
                photo_ids=["photo-approved"],
                recipients=[{"name": "Mesa", "email": "desk@example.com"}],
            )

    def test_rejects_missing_photo(self):
        with self.assertRaises(DispatchValidationError):
            self.service.create_shipment(
                name="Despacho",
                coverage_id="cov-1",
                photo_ids=["missing"],
                recipients=[{"name": "Mesa", "email": "desk@example.com"}],
            )

    def test_does_not_mutate_lens_data(self):
        self.create_shipment()

        self.assertEqual(self.coverages, self.original_coverages)


class DispatchHandoffServiceCompatibilityTest(unittest.TestCase):
    def test_prepare_keeps_existing_payload_shape_and_queue_behavior(self):
        coverage = {}
        result = ExportResult(
            filename="captions.docx",
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            content=b"docx",
            files=(
                ExportFile(
                    format="docx",
                    filename="captions.docx",
                    mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    content=b"docx",
                    path="captions.docx",
                ),
            ),
            formats_generated=("docx",),
            files_created=("captions.docx",),
            zip_filename="",
            photo_count=1,
        )

        payload = DispatchHandoffService().prepare(coverage, result)

        self.assertEqual(payload["status"], "prepared")
        self.assertEqual(payload["destination"], "dispatch")
        self.assertEqual(payload["formats"], ["docx"])
        self.assertEqual(payload["files"][0]["filename"], "captions.docx")
        self.assertIn("created_at", payload)
        self.assertIn("dispatch_queue", coverage)
        self.assertEqual(coverage["dispatch_queue"][0], payload)


if __name__ == "__main__":
    unittest.main()
