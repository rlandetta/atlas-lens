import json
import tempfile
import threading
import unittest
from pathlib import Path

from app.lens import LensCoverageStore, LensCoverageStoreError


class LensCoverageStoreTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.media_root = self.root / "media"
        self.store_path = self.root / "lens_coverages.json"
        self.store = LensCoverageStore(self.store_path, self.media_root)

    def tearDown(self):
        self.temp_dir.cleanup()

    def coverage(self):
        return {
            "coverage_name": "Cobertura Persistida",
            "submit_date": "2026-08-03",
            "event_date": "2026-08-03",
            "city": "Quito",
            "country": "Ecuador",
            "agency": "Xinhua",
            "photographer": "Ricardo Landeta",
            "editor": "rl",
            "photos": [],
        }

    def test_missing_file_returns_empty_coverages(self):
        self.assertEqual(self.store.load(), {})

    def test_invalid_json_raises_and_preserves_original(self):
        self.store_path.write_text("{invalid", encoding="utf-8")

        with self.assertRaises(LensCoverageStoreError):
            self.store.load()

        self.assertEqual(self.store_path.read_text(encoding="utf-8"), "{invalid")

    def test_create_and_reload_coverage(self):
        self.store.set("cov-1", self.coverage())
        reloaded = LensCoverageStore(self.store_path, self.media_root)

        coverages = reloaded.list_coverages()

        self.assertEqual(coverages["cov-1"]["coverage_name"], "Cobertura Persistida")

    def test_persists_relative_photo_path_and_excludes_data_url(self):
        photo_path = self.media_root / "cov-1" / "IMG001.jpg"
        photo_path.parent.mkdir(parents=True)
        photo_path.write_bytes(b"jpg")
        coverage = self.coverage()
        coverage["photos"] = [
            {
                "id": "photo-1",
                "name": "IMG001.jpg",
                "storage_path": "cov-1/IMG001.jpg",
                "size": 3,
                "type": "image/jpeg",
                "width": 100,
                "height": 80,
                "caption_narrative": "Caption.",
                "caption_status": "Aprobado",
                "data_url": "data:image/jpeg;base64,abc",
            }
        ]

        self.store.set("cov-1", coverage)
        photo = self.store.get("cov-1")["photos"][0]
        raw = self.store_path.read_text(encoding="utf-8")

        self.assertEqual(photo["storage_path"], "cov-1/IMG001.jpg")
        self.assertTrue(photo["available_on_disk"])
        self.assertNotIn("data_url", photo)
        self.assertNotIn("base64", raw)

    def test_photo_without_file_is_marked_unavailable(self):
        coverage = self.coverage()
        coverage["photos"] = [
            {
                "id": "photo-1",
                "name": "IMG001.jpg",
                "storage_path": "cov-1/IMG001.jpg",
                "caption_narrative": "Caption.",
                "caption_status": "Aprobado",
            }
        ]

        self.store.set("cov-1", coverage)
        photo = self.store.get("cov-1")["photos"][0]

        self.assertFalse(photo["available_on_disk"])

    def test_flow_photo_metadata_is_preserved(self):
        flow_file = self.root / "events" / "IMG001.jpg"
        flow_file.parent.mkdir(parents=True)
        flow_file.write_bytes(b"jpg")
        coverage = self.coverage()
        coverage["photos"] = [
            {
                "id": "photo-flow",
                "name": "IMG001.jpg",
                "filename": "IMG001.jpg",
                "flow_path": str(flow_file),
                "flow_session_id": "session-1",
                "flow_photo_id": "photo-flow",
                "source": "canon-r6",
                "camera": "canon-r6",
                "coverage_name": "OPERATIVOS",
                "photographer": "Ricardo Landeta",
                "event_date": "2026-08-08",
                "received_at": "2026-08-08T14:00:00+00:00",
                "captured_at": "2026-08-08T13:55:00+00:00",
            }
        ]

        self.store.set("cov-1", coverage)
        photo = self.store.get("cov-1")["photos"][0]

        self.assertEqual(photo["flow_path"], str(flow_file))
        self.assertEqual(photo["flow_session_id"], "session-1")
        self.assertEqual(photo["flow_photo_id"], "photo-flow")
        self.assertEqual(photo["source"], "canon-r6")
        self.assertEqual(photo["camera"], "canon-r6")
        self.assertEqual(photo["coverage_name"], "OPERATIVOS")
        self.assertEqual(photo["photographer"], "Ricardo Landeta")
        self.assertEqual(photo["event_date"], "2026-08-08")
        self.assertEqual(photo["received_at"], "2026-08-08T14:00:00+00:00")
        self.assertEqual(photo["captured_at"], "2026-08-08T13:55:00+00:00")
        self.assertTrue(photo["available_on_disk"])

    def test_caption_and_status_persist(self):
        coverage = self.coverage()
        coverage["photos"] = [
            {
                "id": "photo-1",
                "name": "IMG001.jpg",
                "caption_narrative": "Caption inicial.",
                "caption_status": "Revisado",
            }
        ]
        self.store.set("cov-1", coverage)

        updated = self.store.mutate(
            "cov-1",
            lambda item: {
                **item,
                "photos": [
                    {
                        **item["photos"][0],
                        "caption_narrative": "Caption aprobado.",
                        "caption_status": "Aprobado",
                    }
                ],
            },
        )

        self.assertEqual(updated["photos"][0]["caption_narrative"], "Caption aprobado.")
        self.assertEqual(self.store.get("cov-1")["photos"][0]["caption_status"], "Aprobado")

    def test_delete_coverage(self):
        self.store.set("cov-1", self.coverage())

        self.store.delete("cov-1")

        self.assertEqual(self.store.list_coverages(), {})

    def test_concurrent_updates_do_not_corrupt_json(self):
        barrier = threading.Barrier(3)
        errors = []

        def write_coverage(index):
            try:
                barrier.wait(timeout=2)
                self.store.set(f"cov-{index}", {**self.coverage(), "coverage_name": f"Cobertura {index}"})
            except Exception as error:
                errors.append(error)

        threads = [threading.Thread(target=write_coverage, args=(index,)) for index in range(2)]
        for thread in threads:
            thread.start()
        barrier.wait(timeout=2)
        for thread in threads:
            thread.join(timeout=2)

        payload = json.loads(self.store_path.read_text(encoding="utf-8"))
        self.assertEqual(errors, [])
        self.assertEqual(set(payload["coverages"]), {"cov-0", "cov-1"})


if __name__ == "__main__":
    unittest.main()
