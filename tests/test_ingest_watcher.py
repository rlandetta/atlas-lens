from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from app.ingest import IngestService, IngestStore
from app.ingest.watcher import IngestWatcher


class IngestWatcherTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.events = self.root / "events"
        self.events.mkdir()
        self.store = IngestStore(self.root / "ingest.json")
        self.service = IngestService(self.store, session_timeout_minutes=60)
        self.watcher = IngestWatcher(self.service, [self.events])
        self.watcher.scan_once()

    def tearDown(self):
        self.temp_dir.cleanup()

    def camera_dir(self, camera: str = "canon-r6", event: str = "sabado") -> Path:
        path = self.events / "2026" / "08" / "08" / event / "ricardo" / camera / "JPG"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_file(self, directory: Path, filename: str, content: bytes = b"jpg") -> Path:
        path = directory / filename
        path.write_bytes(content)
        return path

    def stabilize(self, watcher: IngestWatcher | None = None):
        target = watcher or self.watcher
        target.scan_once()
        return target.scan_once()

    def test_ignores_existing_photos_before_startup(self):
        store = IngestStore(self.root / "baseline-ingest.json")
        service = IngestService(store, session_timeout_minutes=60)
        existing_path = self.write_file(self.camera_dir(), "OLD001.JPG")
        watcher = IngestWatcher(service, [self.events])

        self.assertEqual(watcher.scan_once(), [])
        self.assertEqual(watcher.scan_once(), [])

        self.assertTrue(existing_path.exists())
        self.assertEqual(store.list_photos(), [])

    def test_detects_new_jpg_inside_deep_subdirectories(self):
        self.write_file(self.camera_dir(), "IMG001.JPG")

        registered = self.stabilize()

        self.assertEqual(len(registered), 1)
        self.assertEqual(registered[0]["filename"], "IMG001.JPG")
        self.assertEqual(len(self.store.list_photos()), 1)

    def test_detects_canon_r6_from_path(self):
        self.write_file(self.camera_dir("canon-r6"), "IMG001.JPG")

        registered = self.stabilize()

        self.assertEqual(len(registered), 1)
        self.assertEqual(registered[0]["source"], "canon-r6")

    def test_detects_other_camera_without_configuration(self):
        self.write_file(self.camera_dir("sony-a9"), "IMG001.JPG")

        registered = self.stabilize()

        self.assertEqual(len(registered), 1)
        self.assertEqual(registered[0]["source"], "sony-a9")

    def test_ignores_txt(self):
        self.write_file(self.camera_dir(), "notes.txt")

        registered = self.stabilize()

        self.assertEqual(registered, [])
        self.assertEqual(self.store.list_photos(), [])

    def test_waits_for_stable_size(self):
        path = self.write_file(self.camera_dir(), "IMG001.jpg", b"partial")
        self.assertEqual(self.watcher.scan_once(), [])
        path.write_bytes(b"partial-more")

        self.assertEqual(self.watcher.scan_once(), [])
        registered = self.watcher.scan_once()

        self.assertEqual(len(registered), 1)
        self.assertEqual(registered[0]["filename"], "IMG001.jpg")

    def test_does_not_register_duplicate_after_restart(self):
        path = self.write_file(self.camera_dir(), "IMG001.jpg")
        self.stabilize()
        restarted = IngestWatcher(self.service, [self.events])

        registered = self.stabilize(restarted)

        self.assertEqual(registered, [])
        self.assertEqual([photo["path"] for photo in self.store.list_photos()], [str(path.resolve())])

    def test_missing_directory_does_not_break_scan(self):
        missing = self.root / "missing-events"
        watcher = IngestWatcher(self.service, [missing, self.events])
        watcher.scan_once()
        self.write_file(self.camera_dir(), "IMG001.jpeg")

        registered = self.stabilize(watcher)

        self.assertEqual(len(registered), 1)
        self.assertEqual(registered[0]["source"], "canon-r6")

    def test_startup_summary_reports_events_recursive_mode(self):
        summary, available_count, missing_directories = self.watcher.startup_summary(interval_seconds=2)

        self.assertIn("ATLAS FLOW WATCHER", summary)
        self.assertIn("✓ events", summary)
        self.assertIn(str(self.events), summary)
        self.assertIn("Modo: recursivo", summary)
        self.assertIn("Polling: 2 s", summary)
        self.assertIn("Session timeout: 60 min", summary)
        self.assertEqual(available_count, 1)
        self.assertEqual(missing_directories, [])

    def test_two_cameras_share_same_active_session(self):
        self.write_file(self.camera_dir("canon-r6"), "IMG001.jpg")
        first = self.stabilize()[0]
        self.write_file(self.camera_dir("nikon-z9", event="sabado"), "IMG002.jpg")
        second = self.stabilize()[0]

        sessions = self.store.list_sessions()
        self.assertEqual(first["session_id"], second["session_id"])
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["sources"], ["canon-r6", "nikon-z9"])
        self.assertEqual(sessions[0]["photo_count"], 2)

    def test_original_is_not_moved_or_modified(self):
        path = self.write_file(self.camera_dir(), "IMG001.jpg", b"original")
        before_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        before_mtime = path.stat().st_mtime_ns

        self.stabilize()

        self.assertTrue(path.exists())
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before_hash)
        self.assertEqual(path.stat().st_mtime_ns, before_mtime)


if __name__ == "__main__":
    unittest.main()
