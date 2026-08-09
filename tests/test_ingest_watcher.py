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
        self.canon_r6 = self.root / "canon-r6"
        self.canon_1dx = self.root / "canon-1dx"
        self.canon_r6.mkdir()
        self.canon_1dx.mkdir()
        self.store = IngestStore(self.root / "ingest.json")
        self.service = IngestService(self.store, session_timeout_minutes=60)
        self.watcher = IngestWatcher(self.service, [self.canon_r6, self.canon_1dx])

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_file(self, directory: Path, filename: str, content: bytes = b"jpg") -> Path:
        path = directory / filename
        path.write_bytes(content)
        return path

    def stabilize(self, watcher: IngestWatcher | None = None):
        target = watcher or self.watcher
        target.scan_once()
        return target.scan_once()

    def test_detects_new_jpg(self):
        self.write_file(self.canon_r6, "IMG001.JPG")

        registered = self.stabilize()

        self.assertEqual(len(registered), 1)
        self.assertEqual(registered[0]["filename"], "IMG001.JPG")
        self.assertEqual(registered[0]["source"], "canon-r6")
        self.assertEqual(len(self.store.list_photos()), 1)

    def test_ignores_txt(self):
        self.write_file(self.canon_r6, "notes.txt")

        registered = self.stabilize()

        self.assertEqual(registered, [])
        self.assertEqual(self.store.list_photos(), [])

    def test_waits_for_stable_size(self):
        path = self.write_file(self.canon_r6, "IMG001.jpg", b"partial")
        self.assertEqual(self.watcher.scan_once(), [])
        path.write_bytes(b"partial-more")

        self.assertEqual(self.watcher.scan_once(), [])
        registered = self.watcher.scan_once()

        self.assertEqual(len(registered), 1)
        self.assertEqual(registered[0]["filename"], "IMG001.jpg")

    def test_does_not_register_duplicate_after_restart(self):
        path = self.write_file(self.canon_r6, "IMG001.jpg")
        self.stabilize()
        restarted = IngestWatcher(self.service, [self.canon_r6])

        registered = self.stabilize(restarted)

        self.assertEqual(registered, [])
        self.assertEqual([photo["path"] for photo in self.store.list_photos()], [str(path.resolve())])

    def test_missing_directory_does_not_break_scan(self):
        missing = self.root / "missing-camera"
        watcher = IngestWatcher(self.service, [missing, self.canon_r6])
        self.write_file(self.canon_r6, "IMG001.jpeg")

        registered = self.stabilize(watcher)

        self.assertEqual(len(registered), 1)
        self.assertEqual(registered[0]["source"], "canon-r6")


    def test_r6_existing_and_1dx_missing_still_registers_r6_photo(self):
        missing_1dx = self.root / "canon-1dx-missing"
        watcher = IngestWatcher(self.service, [self.canon_r6, missing_1dx])
        self.write_file(self.canon_r6, "IMG001.jpg")

        summary, available_count, missing_directories = watcher.startup_summary(interval_seconds=2)
        registered = self.stabilize(watcher)

        self.assertIn("ATLAS FLOW WATCHER", summary)
        self.assertIn("✓ canon-r6", summary)
        self.assertIn(str(self.canon_r6), summary)
        self.assertIn("⚠ canon-1dx-missing", summary)
        self.assertIn("carpeta no disponible", summary)
        self.assertIn("Watching: 1 camera(s)", summary)
        self.assertIn("Polling: 2 s", summary)
        self.assertEqual(available_count, 1)
        self.assertEqual(missing_directories, [missing_1dx])
        self.assertEqual(len(registered), 1)
        self.assertEqual(registered[0]["filename"], "IMG001.jpg")
        self.assertEqual(registered[0]["source"], "canon-r6")

    def test_two_cameras_share_same_active_session(self):
        self.write_file(self.canon_r6, "IMG001.jpg")
        first = self.stabilize()[0]
        self.write_file(self.canon_1dx, "IMG002.jpg")
        second = self.stabilize()[0]

        sessions = self.store.list_sessions()
        self.assertEqual(first["session_id"], second["session_id"])
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["sources"], ["canon-1dx", "canon-r6"])
        self.assertEqual(sessions[0]["photo_count"], 2)

    def test_original_is_not_moved_or_modified(self):
        path = self.write_file(self.canon_r6, "IMG001.jpg", b"original")
        before_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        before_mtime = path.stat().st_mtime_ns

        self.stabilize()

        self.assertTrue(path.exists())
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before_hash)
        self.assertEqual(path.stat().st_mtime_ns, before_mtime)
