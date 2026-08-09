from __future__ import annotations

import hashlib
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import INGEST_SESSION_TIMEOUT_MINUTES
from app.ingest import IngestService, IngestStore


class IngestServiceTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.store = IngestStore(self.root / "ingest.json")
        self.service = IngestService(self.store, session_timeout_minutes=60)
        self.first_received_at = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.temp_dir.cleanup()

    def register_photo(self, filename="IMG001.jpg", source="cam-a", received_at=None):
        path = self.root / "incoming" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(f"original-{filename}".encode())
        return self.service.register_received_photo({
            "filename": filename,
            "path": str(path),
            "source": source,
            "received_at": (received_at or self.first_received_at).isoformat(),
        })

    def test_first_photo_creates_session(self):
        photo = self.register_photo()
        sessions = self.store.list_sessions()

        self.assertEqual(len(sessions), 1)
        self.assertEqual(photo["session_id"], sessions[0]["id"])
        self.assertEqual(sessions[0]["status"], "active")
        self.assertEqual(sessions[0]["photo_count"], 1)
        self.assertEqual(sessions[0]["sources"], ["cam-a"])

    def test_second_photo_inside_60_minutes_uses_same_session(self):
        first = self.register_photo(filename="IMG001.jpg", received_at=self.first_received_at)
        second = self.register_photo(filename="IMG002.jpg", received_at=self.first_received_at + timedelta(minutes=59))

        self.assertEqual(first["session_id"], second["session_id"])
        sessions = self.store.list_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["photo_count"], 2)

    def test_other_camera_inside_60_minutes_uses_same_session(self):
        first = self.register_photo(filename="IMG001.jpg", source="cam-a", received_at=self.first_received_at)
        second = self.register_photo(filename="IMG002.jpg", source="cam-b", received_at=self.first_received_at + timedelta(minutes=20))

        sessions = self.store.list_sessions()
        self.assertEqual(first["session_id"], second["session_id"])
        self.assertEqual(sessions[0]["sources"], ["cam-a", "cam-b"])

    def test_photo_after_60_minutes_creates_new_session(self):
        first = self.register_photo(filename="IMG001.jpg", received_at=self.first_received_at)
        second = self.register_photo(filename="IMG002.jpg", received_at=self.first_received_at + timedelta(minutes=60, seconds=1))

        sessions = self.store.list_sessions()
        self.assertNotEqual(first["session_id"], second["session_id"])
        self.assertEqual(len(sessions), 2)
        self.assertEqual(sessions[0]["status"], "closed")
        self.assertEqual(sessions[1]["status"], "active")

    def test_original_file_is_not_modified(self):
        path = self.root / "incoming" / "IMG001.jpg"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"original-content")
        before_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        before_mtime = path.stat().st_mtime_ns

        self.service.register_received_photo({
            "filename": "IMG001.jpg",
            "path": str(path),
            "source": "cam-a",
            "received_at": self.first_received_at.isoformat(),
        })

        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before_hash)
        self.assertEqual(path.stat().st_mtime_ns, before_mtime)

    def test_timeout_default_is_configured_to_60_minutes(self):
        self.assertEqual(INGEST_SESSION_TIMEOUT_MINUTES, 60)
