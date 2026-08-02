import copy
import unittest

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


if __name__ == "__main__":
    unittest.main()

