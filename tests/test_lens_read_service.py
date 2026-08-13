import copy
import tempfile
import unittest
from pathlib import Path

from app.lens_read_service import LensReadError, LensReadService


class LensReadServiceTest(unittest.TestCase):
    def test_reads_from_injected_function_and_returns_copies(self):
        coverages = {
            "cov": {
                "photos": [
                    {
                        "id": "p1",
                        "caption_status": "Aprobado",
                        "caption_narrative": "Caption aprobado.",
                    }
                ]
            }
        }
        original = copy.deepcopy(coverages)
        service = LensReadService(lambda: coverages)

        coverage = service.get_coverage("cov")
        coverage["photos"][0]["caption_status"] = "Error"
        photos = service.get_approved_photos_by_ids("cov", ["p1"])
        photos[0]["caption_status"] = "Error"

        self.assertEqual(coverages, original)

    def test_missing_photo_raises_clear_error(self):
        service = LensReadService({"cov": {"photos": []}})

        with self.assertRaises(LensReadError):
            service.get_photo("cov", "missing")

    def test_flow_archive_photo_is_approved_by_common_resolver(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            events_path = root / "storage" / "events" / "2026" / "08" / "12" / "sabado" / "ricardo" / "canon-r6" / "JPG" / "_21A1622.JPG"
            archive_path = root / "storage" / "archive" / "2026" / "08" / "12" / "canon-r6" / "_21A1622.JPG"
            archive_path.parent.mkdir(parents=True)
            archive_path.write_bytes(b"archived-flow-jpeg")
            service = LensReadService({
                "cov": {
                    "photos": [
                        {
                            "id": "p1",
                            "filename": "_21A1622.JPG",
                            "flow_path": str(events_path),
                            "caption_narrative": "Caption aprobado.",
                            "caption_status": "Aprobado",
                            "available_on_disk": False,
                        }
                    ]
                }
            })

            photos = service.get_approved_photos_by_ids("cov", ["p1"])

        self.assertEqual(photos[0]["id"], "p1")


if __name__ == "__main__":
    unittest.main()
