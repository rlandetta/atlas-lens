import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.ingest.watcher import IngestWatcher
from app.routes import web


class FlowSessionDeleteTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.events_root = self.root / "events"
        self.trash_root = self.root / "trash"
        self.ingest_store_path = self.root / "ingest.json"
        self.dispatch_store_path = self.root / "dispatch.json"
        self.patches = [
            patch("app.config.ATLAS_URL_PREFIX", ""),
            patch("app.config.FLOW_EVENTS_ROOT", str(self.events_root)),
            patch("app.config.FLOW_TRASH_ROOT", str(self.trash_root)),
            patch("app.config.FLOW_WATCH_DIRECTORIES", [str(self.events_root)]),
            patch("app.config.INGEST_STORE_PATH", str(self.ingest_store_path)),
            patch("app.config.LENS_COVERAGE_STORE_PATH", str(self.root / "coverages.json")),
            patch("app.config.LENS_MEDIA_ROOT", str(self.root / "lens_media")),
            patch("app.config.THUMBNAIL_ROOT", str(self.root / "thumbnails")),
            patch("app.config.DISPATCH_STORE_PATH", str(self.dispatch_store_path)),
            patch("app.config.DELIVERY_LINKS_STORE_PATH", str(self.root / "delivery_links.json")),
            patch("app.config.DELIVERY_ROOT", str(self.root / "deliveries")),
            patch("app.config.SETTINGS_STORE_PATH", str(self.root / "settings.json")),
        ]
        for patcher in self.patches:
            patcher.start()
        self.app = create_app()
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()

    def tearDown(self):
        for patcher in reversed(self.patches):
            patcher.stop()
        self.temp_dir.cleanup()

    def photo_path(self, session_id, filename):
        path = self.events_root / "2026" / "08" / "17" / session_id / "canon-r6" / "JPG" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"original-{session_id}-{filename}".encode("utf-8"))
        return path

    def seed_session(self, session_id="session-free", filenames=("IMG001.jpg", "IMG002.jpg")):
        photos = []
        for index, filename in enumerate(filenames, start=1):
            path = self.photo_path(session_id, filename)
            photos.append({
                "id": f"{session_id}-photo-{index}",
                "session_id": session_id,
                "filename": filename,
                "path": str(path),
                "source": "canon-r6",
                "received_at": datetime(2026, 8, 17, 12, index, tzinfo=timezone.utc).isoformat(),
            })
        payload = {
            "sessions": [
                {
                    "id": session_id,
                    "status": "closed",
                    "photo_count": len(photos),
                    "sources": ["canon-r6"],
                    "started_at": "2026-08-17T12:00:00+00:00",
                    "last_received_at": "2026-08-17T12:02:00+00:00",
                    "coverage_id": "",
                }
            ],
            "photos": photos,
        }
        self.app.extensions["ingest"]["store"].save(payload)
        return payload

    def append_session(self, session_id, filenames):
        store = self.app.extensions["ingest"]["store"]
        payload = store.load()
        photos = []
        for index, filename in enumerate(filenames, start=1):
            path = self.photo_path(session_id, filename)
            photo = {
                "id": f"{session_id}-photo-{index}",
                "session_id": session_id,
                "filename": filename,
                "path": str(path),
                "source": "canon-r6",
                "received_at": datetime(2026, 8, 17, 13, index, tzinfo=timezone.utc).isoformat(),
            }
            payload["photos"].append(photo)
            photos.append(photo)
        payload["sessions"].append({
            "id": session_id,
            "status": "closed",
            "photo_count": len(photos),
            "sources": ["canon-r6"],
            "started_at": "2026-08-17T13:00:00+00:00",
            "last_received_at": "2026-08-17T13:02:00+00:00",
            "coverage_id": "",
        })
        store.save(payload)
        return photos

    def add_lens_coverage(self, coverage_id, title, photos):
        web.coverages[coverage_id] = {
            "coverage_name": title,
            "submit_date": "2026-08-17",
            "event_date": "2026-08-17",
            "city": "Quito",
            "country": "Ecuador",
            "agency": "Xinhua",
            "photographer": "Ricardo Landeta",
            "editor": "rl",
            "photos": [
                {
                    "id": f"{coverage_id}-{photo['id']}",
                    "filename": photo["filename"],
                    "flow_session_id": photo["session_id"],
                    "flow_photo_id": photo["id"],
                    "flow_path": photo["path"],
                    "caption_status": "Sin editar",
                }
                for photo in photos
            ],
        }

    def test_delete_session_without_lens_dependencies_removes_session_photos_and_originals(self):
        payload = self.seed_session()
        original_paths = [Path(photo["path"]) for photo in payload["photos"]]

        response = self.client.post("/flow/sessions/session-free/delete")
        body = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(body["deleted_photos"], 2)
        self.assertEqual(body["moved_to_trash"], 2)
        stored = self.app.extensions["ingest"]["store"].load()
        self.assertEqual(stored["sessions"], [])
        self.assertEqual(stored["photos"], [])
        self.assertTrue(all(not path.exists() for path in original_paths))
        trashed = sorted(self.trash_root.rglob("*.jpg"))
        self.assertEqual(len(trashed), 2)
        self.assertEqual(len(list(self.trash_root.rglob("manifest.json"))), 1)

    def test_delete_blocks_session_with_one_lens_photo(self):
        payload = self.seed_session()
        self.add_lens_coverage("cov-one", "MITAD-DEL-MUNDO-QUITO · ECUADOR", [payload["photos"][0]])

        response = self.client.post("/flow/sessions/session-free/delete")
        body = response.get_json()

        self.assertEqual(response.status_code, 409)
        self.assertFalse(body["ok"])
        self.assertEqual(body["reason"], "photos_in_use")
        self.assertEqual(body["total_photos"], 2)
        self.assertEqual(body["used_photos"], 1)
        self.assertEqual(body["coverages"][0]["photo_count"], 1)
        self.assertEqual(self.app.extensions["ingest"]["store"].load(), payload)

    def test_delete_check_reports_multiple_photos_coverages_and_deduplicates_global_count(self):
        payload = self.seed_session(filenames=("IMG001.jpg", "IMG002.jpg", "IMG003.jpg"))
        first, second, third = payload["photos"]
        self.add_lens_coverage("cov-a", "MITAD-DEL-MUNDO-QUITO · ECUADOR", [first, second])
        self.add_lens_coverage("cov-b", "QUITO-DRONE · ECUADOR", [first, third])

        response = self.client.get("/flow/sessions/session-free/delete-check")
        body = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertFalse(body["ok"])
        self.assertEqual(body["total_photos"], 3)
        self.assertEqual(body["used_photos"], 3)
        self.assertEqual({item["coverage_id"] for item in body["coverages"]}, {"cov-a", "cov-b"})
        self.assertEqual({item["photo_count"] for item in body["coverages"]}, {2})
        self.assertEqual({item["url"] for item in body["coverages"]}, {"/lens/coverages/cov-a", "/lens/coverages/cov-b"})

    def test_same_photo_used_in_two_coverages_counts_once_globally(self):
        payload = self.seed_session(filenames=("IMG001.jpg", "IMG002.jpg"))
        first = payload["photos"][0]
        self.add_lens_coverage("cov-a", "Cobertura A", [first])
        self.add_lens_coverage("cov-b", "Cobertura B", [first])

        body = self.client.get("/flow/sessions/session-free/delete-check").get_json()

        self.assertEqual(body["used_photos"], 1)
        self.assertEqual(len(body["coverages"]), 2)
        self.assertEqual([item["photo_count"] for item in body["coverages"]], [1, 1])

    def test_missing_session_and_path_traversal_return_404(self):
        self.seed_session()

        missing = self.client.get("/flow/sessions/session-missing/delete-check")
        traversal = self.client.get("/flow/sessions/..%2Fsecret/delete-check")

        self.assertEqual(missing.status_code, 404)
        self.assertEqual(traversal.status_code, 404)

    def test_delete_check_does_not_modify_ingest_lens_or_dispatch_data(self):
        payload = self.seed_session()
        self.add_lens_coverage("cov-one", "Cobertura Uno", [payload["photos"][0]])
        self.app.extensions["dispatch"]["store"].save({
            "shipments": [
                {
                    "id": "ship-1",
                    "name": "Despacho",
                    "coverage_id": "cov-one",
                    "photo_ids": [],
                }
            ]
        })
        before_ingest = self.app.extensions["ingest"]["store"].load()
        before_coverages = copy.deepcopy(web.coverages)
        before_dispatch = self.app.extensions["dispatch"]["store"].load()

        response = self.client.get("/flow/sessions/session-free/delete-check")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.app.extensions["ingest"]["store"].load(), before_ingest)
        self.assertEqual(web.coverages, before_coverages)
        self.assertEqual(self.app.extensions["dispatch"]["store"].load(), before_dispatch)

    def test_post_revalidates_and_blocks_dependency_added_after_delete_check(self):
        payload = self.seed_session()
        check = self.client.get("/flow/sessions/session-free/delete-check")
        self.assertTrue(check.get_json()["ok"])
        self.add_lens_coverage("cov-race", "Cobertura Race", [payload["photos"][0]])

        response = self.client.post("/flow/sessions/session-free/delete")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["reason"], "photos_in_use")
        self.assertEqual(self.app.extensions["ingest"]["store"].load(), payload)

    def test_delete_does_not_affect_other_sessions_lens_coverages_or_dispatches(self):
        payload = self.seed_session("session-delete", ("IMG001.jpg",))
        other_photos = self.append_session("session-keep", ("IMG101.jpg",))
        self.add_lens_coverage("cov-other", "Cobertura Otra", other_photos)
        before_coverages = copy.deepcopy(web.coverages)
        self.app.extensions["dispatch"]["store"].save({
            "shipments": [
                {
                    "id": "ship-keep",
                    "name": "Despacho Keep",
                    "coverage_id": "cov-other",
                    "photo_ids": [other_photos[0]["id"]],
                }
            ]
        })
        before_dispatch = self.app.extensions["dispatch"]["store"].load()

        response = self.client.post("/flow/sessions/session-delete/delete")

        self.assertEqual(response.status_code, 200)
        stored = self.app.extensions["ingest"]["store"].load()
        self.assertEqual([session["id"] for session in stored["sessions"]], ["session-keep"])
        self.assertEqual([photo["id"] for photo in stored["photos"]], [other_photos[0]["id"]])
        self.assertFalse(Path(payload["photos"][0]["path"]).exists())
        self.assertTrue(Path(other_photos[0]["path"]).exists())
        self.assertEqual(len(list(self.trash_root.rglob("IMG001.jpg"))), 1)
        self.assertEqual(web.coverages, before_coverages)
        self.assertEqual(self.app.extensions["dispatch"]["store"].load(), before_dispatch)

    def test_flow_renders_delete_button_lens_usage_indicator_and_data_urls(self):
        payload = self.seed_session()
        self.add_lens_coverage("cov-ui", "Cobertura UI", [payload["photos"][0]])

        response = self.client.get("/flow/")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Eliminar sesión", body)
        self.assertIn("1 fotografía usada en LENS", body)
        self.assertIn('data-delete-check-url="/flow/sessions/session-free/delete-check"', body)
        self.assertIn('data-delete-url="/flow/sessions/session-free/delete"', body)
        self.assertIn('static/js/flow_session_delete.js', body)
        self.assertIn("data-flow-delete-coverages-panel hidden", body)

    def test_flow_delete_javascript_separates_lens_and_filesystem_errors(self):
        script = Path("app/static/js/flow_session_delete.js").read_text(encoding="utf-8")

        self.assertIn('payload.reason !== "photos_in_use"', script)
        self.assertIn("No se pudo eliminar la sesión", script)
        self.assertIn("siendo utilizadas por coberturas", script)
        self.assertIn("coveragePanel.hidden = true", script)
        self.assertIn("coveragePanel.hidden = coverages.length === 0", script)

    def test_delete_check_coverage_links_use_canonical_lens_coverages(self):
        payload = self.seed_session()
        self.add_lens_coverage("cov-link", "Cobertura Link", [payload["photos"][0]])

        response = self.client.get("/flow/sessions/session-free/delete-check")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["coverages"][0]["url"], "/lens/coverages/cov-link")

    def test_delete_endpoint_preserves_canonical_flow_architecture(self):
        self.seed_session()

        check = self.client.get("/flow/sessions/session-free/delete-check")
        delete = self.client.post("/flow/sessions/session-free/delete")

        self.assertEqual(check.status_code, 200)
        self.assertEqual(delete.status_code, 200)
        self.assertTrue(delete.get_json()["ok"])

    def test_delete_response_does_not_expose_filesystem_paths(self):
        self.seed_session()

        response = self.client.post("/flow/sessions/session-free/delete")
        serialized = json.dumps(response.get_json())

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(str(self.root), serialized)

    def test_deleted_files_do_not_reappear_when_watcher_scans_events(self):
        self.seed_session(filenames=("IMG001.jpg", "IMG002.jpg", "IMG003.jpg"))
        response = self.client.post("/flow/sessions/session-free/delete")
        watcher = IngestWatcher(self.app.extensions["ingest"]["ingest_service"], [self.events_root])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(watcher.scan_once(), [])
        self.assertEqual(watcher.scan_once(), [])
        stored = self.app.extensions["ingest"]["store"].load()
        self.assertEqual(stored["sessions"], [])
        self.assertEqual(stored["photos"], [])

    def test_dashboard_and_flow_show_empty_after_delete(self):
        self.seed_session()

        response = self.client.post("/flow/sessions/session-free/delete")
        dashboard = self.client.get("/").get_data(as_text=True)
        flow = self.client.get("/flow/").get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("<dt>En espera</dt>", dashboard)
        self.assertIn("<dd>0</dd>", dashboard)
        self.assertIn("Sin sesión activa", flow)
        self.assertIn("Todavía no hay sesiones de ingreso registradas.", flow)

    def test_filesystem_preflight_failure_keeps_store_and_files_in_place(self):
        payload = self.seed_session()
        before = self.app.extensions["ingest"]["store"].load()
        with patch("app.routes.web.os.access", return_value=False):
            response = self.client.post("/flow/sessions/session-free/delete")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["reason"], "filesystem_error")
        self.assertEqual(self.app.extensions["ingest"]["store"].load(), before)
        self.assertTrue(all(Path(photo["path"]).exists() for photo in payload["photos"]))

    def test_move_failure_rolls_back_files_and_keeps_store(self):
        payload = self.seed_session(filenames=("IMG001.jpg", "IMG002.jpg"))
        before = self.app.extensions["ingest"]["store"].load()
        original_replace = Path.replace
        calls = {"count": 0}

        def flaky_replace(path, target):
            calls["count"] += 1
            if calls["count"] == 2:
                raise OSError("simulated move failure")
            return original_replace(path, target)

        with patch.object(Path, "replace", flaky_replace):
            response = self.client.post("/flow/sessions/session-free/delete")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.app.extensions["ingest"]["store"].load(), before)
        self.assertTrue(all(Path(photo["path"]).exists() for photo in payload["photos"]))
        self.assertEqual(list(self.trash_root.rglob("*.jpg")), [])

    def test_path_outside_flow_events_root_aborts(self):
        payload = self.seed_session()
        outside = self.root / "outside" / "IMG999.jpg"
        outside.parent.mkdir()
        outside.write_bytes(b"outside")
        payload["photos"][0]["path"] = str(outside)
        self.app.extensions["ingest"]["store"].save(payload)

        response = self.client.post("/flow/sessions/session-free/delete")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["reason"], "filesystem_error")
        self.assertEqual(self.app.extensions["ingest"]["store"].load(), payload)
        self.assertTrue(outside.exists())

    def test_symlink_source_aborts(self):
        payload = self.seed_session()
        target = Path(payload["photos"][0]["path"])
        target.unlink()
        target.symlink_to(self.photo_path("session-free", "REAL.jpg"))

        response = self.client.post("/flow/sessions/session-free/delete")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["reason"], "filesystem_error")
        self.assertEqual(self.app.extensions["ingest"]["store"].load(), payload)

    def test_trash_collision_aborts_safely(self):
        self.seed_session()
        with patch("app.routes.web.build_flow_trash_batch_root", return_value=self.trash_root / "fixed"):
            (self.trash_root / "fixed").mkdir(parents=True)
            response = self.client.post("/flow/sessions/session-free/delete")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["reason"], "filesystem_error")
        self.assertEqual(len(self.app.extensions["ingest"]["store"].load()["sessions"]), 1)

    def test_same_basename_in_distinct_folders_is_preserved_in_trash(self):
        payload = self.seed_session("session-free", ())
        first = self.photo_path("session-free", "IMG001.jpg")
        second = self.events_root / "2026" / "08" / "18" / "session-free" / "canon-r6" / "JPG" / "IMG001.jpg"
        second.parent.mkdir(parents=True)
        second.write_bytes(b"second")
        payload["sessions"][0]["photo_count"] = 2
        payload["photos"] = [
            {
                "id": "photo-1",
                "session_id": "session-free",
                "filename": "IMG001.jpg",
                "path": str(first),
                "source": "canon-r6",
                "received_at": "2026-08-17T12:01:00+00:00",
            },
            {
                "id": "photo-2",
                "session_id": "session-free",
                "filename": "IMG001.jpg",
                "path": str(second),
                "source": "canon-r6",
                "received_at": "2026-08-17T12:02:00+00:00",
            },
        ]
        self.app.extensions["ingest"]["store"].save(payload)

        response = self.client.post("/flow/sessions/session-free/delete")

        self.assertEqual(response.status_code, 200)
        trashed = sorted(path.relative_to(self.trash_root).as_posix() for path in self.trash_root.rglob("IMG001.jpg"))
        self.assertEqual(len(trashed), 2)
        self.assertNotEqual(trashed[0], trashed[1])

    def test_active_receiving_session_is_blocked(self):
        payload = self.seed_session()
        payload["sessions"][0]["status"] = "active"
        payload["sessions"][0]["last_received_at"] = datetime.now(timezone.utc).isoformat()
        self.app.extensions["ingest"]["store"].save(payload)

        response = self.client.post("/flow/sessions/session-free/delete")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["reason"], "session_active")
        self.assertEqual(self.app.extensions["ingest"]["store"].load(), payload)

    def test_expired_active_session_is_closed_and_can_be_deleted(self):
        payload = self.seed_session()
        payload["sessions"][0]["status"] = "active"
        payload["sessions"][0]["last_received_at"] = "2020-01-01T00:00:00+00:00"
        self.app.extensions["ingest"]["store"].save(payload)

        response = self.client.post("/flow/sessions/session-free/delete")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.app.extensions["ingest"]["store"].load()["sessions"], [])

    def test_new_photo_after_delete_creates_new_session_from_zero(self):
        old_payload = self.seed_session()
        old_session_id = old_payload["sessions"][0]["id"]
        self.client.post("/flow/sessions/session-free/delete")
        new_path = self.photo_path("new-arrival", "IMG100.jpg")

        photo = self.app.extensions["ingest"]["ingest_service"].register_received_photo({
            "filename": "IMG100.jpg",
            "path": str(new_path),
            "source": "canon-r6",
            "received_at": datetime.now(timezone.utc).isoformat(),
        })
        stored = self.app.extensions["ingest"]["store"].load()

        self.assertNotEqual(photo["session_id"], old_session_id)
        self.assertEqual(len(stored["sessions"]), 1)
        self.assertEqual(stored["sessions"][0]["photo_count"], 1)
        self.assertEqual(len(stored["photos"]), 1)

    def test_trash_root_is_not_observed_by_watcher(self):
        self.seed_session()
        response = self.client.post("/flow/sessions/session-free/delete")
        trashed = next(self.trash_root.rglob("*.jpg"))
        watcher = IngestWatcher(self.app.extensions["ingest"]["ingest_service"], [self.events_root])

        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(trashed.parents, self.events_root)
        self.assertEqual(watcher.scan_once(), [])
        self.assertEqual(watcher.scan_once(), [])

    def test_lens_dependency_does_not_move_to_trash(self):
        payload = self.seed_session()
        self.add_lens_coverage("cov-one", "Cobertura Uno", [payload["photos"][0]])

        response = self.client.post("/flow/sessions/session-free/delete")

        self.assertEqual(response.status_code, 409)
        self.assertFalse(self.trash_root.exists())
        self.assertTrue(all(Path(photo["path"]).exists() for photo in payload["photos"]))

    def test_bug_reproduction_many_files_do_not_reappear_after_delete_and_watcher_scans(self):
        filenames = tuple(f"IMG{index:03}.jpg" for index in range(1, 32))
        self.seed_session(filenames=filenames)

        response = self.client.post("/flow/sessions/session-free/delete")
        watcher = IngestWatcher(self.app.extensions["ingest"]["ingest_service"], [self.events_root])

        self.assertEqual(response.status_code, 200)
        for _ in range(3):
            self.assertEqual(watcher.scan_once(), [])
        stored = self.app.extensions["ingest"]["store"].load()
        self.assertEqual(stored["sessions"], [])
        self.assertEqual(stored["photos"], [])
        self.assertEqual(len(list(self.trash_root.rglob("*.jpg"))), len(filenames))
