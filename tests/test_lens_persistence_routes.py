import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.routes import web


class LensPersistenceRoutesTest(unittest.TestCase):
    jpeg_bytes = base64.b64decode(
        "/9j/4AAQSkZJRgABAQEAAQABAAD/2wBDAAMCAgICAgMCAgIDAwMDBAYEBAQEBAgGBgUGCQgKCgkICQkKDA8MCgsOCwkJDRENDg8QEBEQCgwSExIQEw8QEBD/2wBDAQMDAwQDBAgEBAgQCwkLEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBD/wAARCAASACADAREAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAn/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFgEBAQEAAAAAAAAAAAAAAAAAAAYH/8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAwDAQACEQMRAD8AnE1hLgAAAAAAAAAAP//Z"
    )
    png_bytes = b"\x89PNG\r\n\x1a\nATLASPNG"

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.coverage_store_path = self.root / "lens_coverages.json"
        self.media_root = self.root / "media"
        self.thumbnail_root = self.root / "thumbnails"
        self.dispatch_store_path = self.root / "dispatch_shipments.json"
        self.settings_store_path = self.root / "settings.json"
        self.patches = [
            patch("app.config.LENS_COVERAGE_STORE_PATH", str(self.coverage_store_path)),
            patch("app.config.LENS_MEDIA_ROOT", str(self.media_root)),
            patch("app.config.DISPATCH_STORE_PATH", str(self.dispatch_store_path)),
            patch("app.config.SETTINGS_STORE_PATH", str(self.settings_store_path)),
            patch("app.config.THUMBNAIL_ROOT", str(self.thumbnail_root)),
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

    def create_coverage(self):
        response = self.client.post(
            "/coverages/new",
            data={
                "coverage_name": "Cobertura Persistida",
                "submit_date": "2026-08-03",
                "event_date": "2026-08-03",
                "city": "Quito",
                "country": "Ecuador",
                "agency": "Xinhua",
                "photographer": "Ricardo Landeta",
                "editor": "rl",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        return response.headers["Location"].rsplit("/", 1)[-1]

    def edit_coverage(self, coverage_id, **overrides):
        data = {
            "coverage_name": "Cobertura Persistida Editada",
            "submit_date": "2026-08-04",
            "event_date": "2026-08-04",
            "city": "Guayaquil",
            "country": "Ecuador",
            "agency": "AFP",
            "photographer": "Nuevo Fotógrafo",
            "editor": "ab",
        }
        data.update(overrides)
        return self.client.post(
            f"/coverages/{coverage_id}/edit",
            data=data,
            follow_redirects=False,
        )

    def add_photo(self, coverage_id, **overrides):
        content = overrides.pop("content", self.jpeg_bytes)
        mime_type = overrides.get("type", "image/jpeg")
        payload = {
            "id": "photo-1",
            "name": "IMG001.jpg",
            "size": len(content),
            "type": mime_type,
            "width": 100,
            "height": 80,
            "data_url": f"data:{mime_type};base64,{base64.b64encode(content).decode('ascii')}",
        }
        payload.update(overrides)
        response = self.client.post(f"/coverages/{coverage_id}/photos", json=payload)
        self.assertEqual(response.status_code, 201)
        return response

    def test_create_reload_and_dispatch_visibility(self):
        coverage_id = self.create_coverage()

        reloaded = create_app()
        reloaded.config.update(TESTING=True)
        body = reloaded.test_client().get("/dispatch/new").get_data(as_text=True)

        self.assertIn("Cobertura Persistida", body)
        self.assertIn(coverage_id, web.coverages)

    def test_photo_upload_persists_file_relative_path_and_excludes_data_url(self):
        coverage_id = self.create_coverage()
        self.add_photo(coverage_id)

        stored = self.app.extensions["lens"]["coverage_store"].get(coverage_id)
        photo = stored["photos"][0]

        self.assertEqual(photo["filename"], "IMG001.jpg")
        self.assertEqual(photo["storage_path"], f"coverages/{coverage_id}/photo-1_IMG001.jpg")
        self.assertFalse(Path(photo["storage_path"]).is_absolute())
        self.assertTrue((self.media_root / photo["storage_path"]).is_file())
        self.assertTrue(photo["available_on_disk"])
        self.assertNotIn("data_url", photo)
        self.assertNotIn("data:image", self.coverage_store_path.read_text(encoding="utf-8"))
        self.assertNotIn("base64", self.coverage_store_path.read_text(encoding="utf-8"))

    def test_dangerous_filename_is_sanitized(self):
        coverage_id = self.create_coverage()
        self.add_photo(coverage_id, name="../evil photo!!.jpg", filename="../evil photo!!.jpg")

        photo = self.app.extensions["lens"]["coverage_store"].get(coverage_id)["photos"][0]

        self.assertNotIn("..", photo["storage_path"])
        self.assertIn("photo-1_evil-photo.jpg", photo["storage_path"])
        self.assertTrue((self.media_root / photo["storage_path"]).is_file())

    def test_too_large_photo_is_rejected(self):
        self.app.config["LENS_MAX_PHOTO_BYTES"] = 4
        coverage_id = self.create_coverage()

        response = self.client.post(
            f"/coverages/{coverage_id}/photos",
            json={
                "id": "photo-large",
                "name": "large.jpg",
                "size": len(self.jpeg_bytes),
                "type": "image/jpeg",
                "data_url": f"data:image/jpeg;base64,{base64.b64encode(self.jpeg_bytes).decode('ascii')}",
            },
        )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(self.app.extensions["lens"]["coverage_store"].get(coverage_id)["photos"], [])

    def test_unsupported_photo_format_is_rejected(self):
        coverage_id = self.create_coverage()

        response = self.client.post(
            f"/coverages/{coverage_id}/photos",
            json={
                "id": "photo-gif",
                "name": "bad.gif",
                "size": 10,
                "type": "image/gif",
                "data_url": "data:image/gif;base64,R0lGODlhAA==",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.app.extensions["lens"]["coverage_store"].get(coverage_id)["photos"], [])

    def test_caption_and_status_are_persisted_after_reload(self):
        coverage_id = self.create_coverage()
        self.add_photo(coverage_id)

        response = self.client.post(
            f"/coverages/{coverage_id}/photos/photo-1/caption",
            json={
                "caption_narrative": "Caption aprobado.",
                "caption_status": "Aprobado",
            },
        )

        self.assertEqual(response.status_code, 200)
        reloaded = create_app()
        photo = reloaded.extensions["lens"]["coverage_store"].get(coverage_id)["photos"][0]
        self.assertEqual(photo["caption_narrative"], "Caption aprobado.")
        self.assertEqual(photo["caption_status"], "Aprobado")

    def test_caption_status_selector_is_visible_in_lens(self):
        coverage_id = self.create_coverage()
        self.add_photo(coverage_id)

        body = self.client.get(f"/coverages/{coverage_id}").get_data(as_text=True)

        self.assertIn('label for="caption-review-status-field"', body)
        self.assertIn("Estado editorial", body)
        self.assertIn('<select id="caption-review-status-field">', body)
        self.assertIn('<option value="Sin editar">Sin editar</option>', body)
        self.assertIn('<option value="En edición">En edición</option>', body)
        self.assertIn('<option value="Revisado">Revisado</option>', body)
        self.assertIn('<option value="Aprobado">Aprobado</option>', body)

    def test_empty_caption_keeps_dispatch_button_disabled(self):
        coverage_id = self.create_coverage()
        self.add_photo(coverage_id)

        response = self.client.get(f"/coverages/{coverage_id}")
        body = response.get_data(as_text=True)

        self.assertIn('id="create-dispatch-link"', body)
        self.assertIn('id="create-dispatch-disabled-button"', body)
        self.assertIn("Agregue un caption a por lo menos una fotografía para crear el despacho.", body)
        self.assertIn('id="create-dispatch-link" href=', body)
        self.assertIn("hidden>Crear despacho</a>", body)

    def test_saving_first_eligible_caption_reports_dispatch_enabled(self):
        coverage_id = self.create_coverage()
        self.add_photo(coverage_id)

        response = self.client.post(
            f"/coverages/{coverage_id}/photos/photo-1/caption",
            json={
                "caption_narrative": "Caption listo.",
                "caption_status": "Sin editar",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["saved"])
        self.assertEqual(payload["eligible_photo_count"], 1)
        self.assertTrue(payload["can_create_dispatch"])

    def test_clearing_last_eligible_caption_reports_dispatch_disabled(self):
        coverage_id = self.create_coverage()
        self.add_photo(coverage_id)
        self.client.post(
            f"/coverages/{coverage_id}/photos/photo-1/caption",
            json={
                "caption_narrative": "Caption listo.",
                "caption_status": "Aprobado",
            },
        )

        response = self.client.post(
            f"/coverages/{coverage_id}/photos/photo-1/caption",
            json={
                "caption_narrative": "",
                "caption_status": "Aprobado",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["eligible_photo_count"], 0)
        self.assertFalse(payload["can_create_dispatch"])

    def test_caption_status_does_not_affect_dispatch_eligibility(self):
        coverage_id = self.create_coverage()
        self.add_photo(coverage_id)

        response = self.client.post(
            f"/coverages/{coverage_id}/photos/photo-1/caption",
            json={
                "caption_narrative": "Caption listo.",
                "caption_status": "Sin editar",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["can_create_dispatch"])
        body = self.client.get(f"/coverages/{coverage_id}").get_data(as_text=True)
        self.assertIn(f'href="/dispatch/new?coverage_id={coverage_id}"', body)

    def test_copy_caption_persists(self):
        coverage_id = self.create_coverage()
        self.add_photo(coverage_id, id="photo-source", name="IMG001.jpg")
        self.add_photo(coverage_id, id="photo-empty", name="IMG002.jpg")
        self.client.post(
            f"/coverages/{coverage_id}/photos/photo-source/caption",
            json={
                "caption_narrative": "Caption fuente.",
                "caption_status": "Aprobado",
            },
        )

        response = self.client.post(
            f"/coverages/{coverage_id}/captions/copy-caption-empty",
            json={
                "source_photo_id": "photo-source",
                "caption_narrative": "Caption fuente.",
                "caption_status": "Aprobado",
            },
        )

        self.assertEqual(response.status_code, 200)
        photos = self.app.extensions["lens"]["coverage_store"].get(coverage_id)["photos"]
        copied = next(photo for photo in photos if photo["id"] == "photo-empty")
        self.assertEqual(copied["caption_narrative"], "Caption fuente.")
        self.assertEqual(copied["caption_status"], "Aprobado")

    def test_export_history_persists(self):
        coverage_id = self.create_coverage()
        self.add_photo(coverage_id)
        self.client.post(
            f"/coverages/{coverage_id}/photos/photo-1/caption",
            json={
                "caption_narrative": "Caption para exportar.",
                "caption_status": "Aprobado",
            },
        )

        response = self.client.post(
            f"/coverages/{coverage_id}/exports",
            json={
                "formats": ["html"],
                "include_captions": True,
                "include_photos": False,
                "destination": "download",
            },
        )

        self.assertEqual(response.status_code, 200)
        stored = self.app.extensions["lens"]["coverage_store"].get(coverage_id)
        self.assertEqual(stored["export_history"][0]["format"], "HTML")

    def test_edit_coverage_preserves_photos_storage_caption_history_and_ai_context(self):
        coverage_id = self.create_coverage()
        self.add_photo(coverage_id)
        self.client.post(
            f"/coverages/{coverage_id}/photos/photo-1/caption",
            json={
                "caption_narrative": "Caption conservado.",
                "caption_status": "Sin editar",
            },
        )
        web.coverages[coverage_id]["export_history"] = [{"format": "DOCX", "created_at": "2026-08-04T00:00:00+00:00"}]
        web.coverages[coverage_id]["ai_context"] = {"notes": "Contexto interno"}
        web.persist_coverage(coverage_id)
        before = self.app.extensions["lens"]["coverage_store"].get(coverage_id)
        before_photo = before["photos"][0]

        response = self.edit_coverage(coverage_id)

        self.assertEqual(response.status_code, 302)
        stored = self.app.extensions["lens"]["coverage_store"].get(coverage_id)
        photo = stored["photos"][0]
        self.assertEqual(stored["agency"], "AFP")
        self.assertEqual(stored["photographer"], "Nuevo Fotógrafo")
        self.assertEqual(stored["editor"], "ab")
        self.assertEqual(photo["id"], before_photo["id"])
        self.assertEqual(photo["storage_path"], before_photo["storage_path"])
        self.assertEqual(photo["available_on_disk"], before_photo["available_on_disk"])
        self.assertEqual(photo["caption_narrative"], "Caption conservado.")
        self.assertEqual(stored["export_history"], before["export_history"])
        self.assertEqual(stored["ai_context"], before["ai_context"])

    def test_thumbnail_still_responds_after_edit_coverage(self):
        coverage_id = self.create_coverage()
        self.add_photo(coverage_id)
        before = self.app.extensions["lens"]["coverage_store"].get(coverage_id)["photos"][0]["storage_path"]

        self.edit_coverage(coverage_id)
        response = self.client.get(f"/coverages/{coverage_id}/photos/photo-1/media")
        after = self.app.extensions["lens"]["coverage_store"].get(coverage_id)["photos"][0]["storage_path"]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(after, before)
        response.close()

    def test_two_consecutive_caption_autosaves_keep_latest_values(self):
        coverage_id = self.create_coverage()
        self.add_photo(coverage_id)

        self.client.post(
            f"/coverages/{coverage_id}/photos/photo-1/caption",
            json={
                "caption_narrative": "Caption uno.",
                "caption_status": "Sin editar",
            },
        )
        response = self.client.post(
            f"/coverages/{coverage_id}/photos/photo-1/caption",
            json={
                "caption_narrative": "Caption dos.",
                "caption_status": "Revisado",
            },
        )

        self.assertEqual(response.status_code, 200)
        photo = self.app.extensions["lens"]["coverage_store"].get(coverage_id)["photos"][0]
        self.assertEqual(photo["caption_narrative"], "Caption dos.")
        self.assertEqual(photo["caption_status"], "Revisado")

    def test_caption_autosave_and_near_edit_do_not_overwrite_each_other(self):
        coverage_id = self.create_coverage()
        self.add_photo(coverage_id)

        caption_response = self.client.post(
            f"/coverages/{coverage_id}/photos/photo-1/caption",
            json={
                "caption_narrative": "Caption simultáneo.",
                "caption_status": "Sin editar",
            },
        )
        edit_response = self.edit_coverage(coverage_id, agency="Reuters")

        self.assertEqual(caption_response.status_code, 200)
        self.assertEqual(edit_response.status_code, 302)
        stored = self.app.extensions["lens"]["coverage_store"].get(coverage_id)
        self.assertEqual(stored["agency"], "Reuters")
        self.assertEqual(stored["photos"][0]["caption_narrative"], "Caption simultáneo.")

    def test_restart_reload_keeps_dispatch_button_and_images_consistent(self):
        coverage_id = self.create_coverage()
        self.add_photo(coverage_id)
        self.client.post(
            f"/coverages/{coverage_id}/photos/photo-1/caption",
            json={
                "caption_narrative": "Caption persistido.",
                "caption_status": "Sin editar",
            },
        )

        reloaded = create_app()
        reloaded.config.update(TESTING=True)
        client = reloaded.test_client()
        body = client.get(f"/coverages/{coverage_id}").get_data(as_text=True)
        media_response = client.get(f"/coverages/{coverage_id}/photos/photo-1/media")

        self.assertIn(f'href="/dispatch/new?coverage_id={coverage_id}"', body)
        self.assertIn("/photos/photo-1/thumbnail", body)
        self.assertEqual(media_response.status_code, 200)
        media_response.close()

    def test_delete_coverage_persists(self):
        coverage_id = self.create_coverage()

        response = self.client.post(f"/coverages/{coverage_id}/delete")

        self.assertEqual(response.status_code, 302)
        self.assertIsNone(self.app.extensions["lens"]["coverage_store"].get(coverage_id))

    def test_delete_photo_removes_file(self):
        coverage_id = self.create_coverage()
        self.add_photo(coverage_id)
        photo = self.app.extensions["lens"]["coverage_store"].get(coverage_id)["photos"][0]
        media_file = self.media_root / photo["storage_path"]

        response = self.client.post(f"/coverages/{coverage_id}/photos/photo-1/delete")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(media_file.exists())
        self.assertEqual(self.app.extensions["lens"]["coverage_store"].get(coverage_id)["photos"], [])

    def test_delete_coverage_removes_media_directory(self):
        coverage_id = self.create_coverage()
        self.add_photo(coverage_id)
        media_dir = self.media_root / "coverages" / coverage_id

        response = self.client.post(f"/coverages/{coverage_id}/delete")

        self.assertEqual(response.status_code, 302)
        self.assertFalse(media_dir.exists())

    def test_legacy_photo_without_file_is_not_sendable(self):
        coverage_id = self.create_coverage()
        web.coverages[coverage_id]["photos"].append({
            "id": "legacy-photo",
            "name": "legacy.jpg",
            "filename": "legacy.jpg",
            "storage_path": "",
            "caption_narrative": "Caption aprobado.",
            "caption_status": "Aprobado",
            "available_on_disk": False,
        })
        web.persist_coverage(coverage_id)

        body = self.client.get(f"/dispatch/new?coverage_id={coverage_id}").get_data(as_text=True)

        self.assertIn("legacy.jpg", body)
        self.assertIn("Archivo no disponible para envío", body)

    def test_dispatch_marks_unavailable_photo_as_not_selectable(self):
        coverage_id = self.create_coverage()
        web.coverages[coverage_id]["photos"].append({
            "id": "photo-1",
            "name": "IMG001.jpg",
            "filename": "IMG001.jpg",
            "storage_path": "",
            "caption_narrative": "",
            "caption_status": "Sin editar",
            "available_on_disk": False,
        })
        web.persist_coverage(coverage_id)
        self.client.post(
            f"/coverages/{coverage_id}/photos/photo-1/caption",
            json={
                "caption_narrative": "Caption aprobado.",
                "caption_status": "Aprobado",
            },
        )

        body = self.client.get(f"/dispatch/new?coverage_id={coverage_id}").get_data(as_text=True)

        self.assertIn("IMG001.jpg", body)
        self.assertIn("Archivo no disponible para envío", body)
        self.assertIn('value="photo-1"  disabled', body)

    def test_coverage_detail_enables_dispatch_button_with_caption_and_file(self):
        coverage_id = self.create_coverage()
        self.add_photo(coverage_id)
        self.client.post(
            f"/coverages/{coverage_id}/photos/photo-1/caption",
            json={
                "caption_narrative": "Caption aprobado.",
                "caption_status": "Aprobado",
            },
        )

        body = self.client.get(f"/coverages/{coverage_id}").get_data(as_text=True)

        self.assertIn("Crear despacho", body)
        self.assertIn(f'href="/dispatch/new?coverage_id={coverage_id}"', body)

    def test_coverage_detail_disables_dispatch_button_without_caption(self):
        coverage_id = self.create_coverage()
        self.add_photo(coverage_id)

        body = self.client.get(f"/coverages/{coverage_id}").get_data(as_text=True)

        self.assertIn("Crear despacho", body)
        self.assertIn("Agregue un caption a por lo menos una fotografía para crear el despacho.", body)
        self.assertIn(f'href="/dispatch/new?coverage_id={coverage_id}"', body)
        self.assertIn('id="create-dispatch-link"', body)
        self.assertIn("hidden>Crear despacho</a>", body)

    def test_dispatch_new_shows_unavailable_approved_photo_disabled(self):
        coverage_id = self.create_coverage()
        web.coverages[coverage_id]["photos"].append({
            "id": "photo-1",
            "name": "IMG001.jpg",
            "filename": "IMG001.jpg",
            "storage_path": "",
            "caption_narrative": "",
            "caption_status": "Sin editar",
            "available_on_disk": False,
        })
        web.persist_coverage(coverage_id)
        self.client.post(
            f"/coverages/{coverage_id}/photos/photo-1/caption",
            json={
                "caption_narrative": "Caption aprobado.",
                "caption_status": "Aprobado",
            },
        )

        body = self.client.get(f"/dispatch/new?coverage_id={coverage_id}").get_data(as_text=True)

        self.assertIn("Cobertura", body)
        self.assertIn("IMG001.jpg", body)
        self.assertIn("Archivo no disponible para envío", body)
        self.assertIn('value="photo-1"  disabled', body)

    def test_dispatch_new_shows_available_caption_photos_selectable_regardless_of_status(self):
        coverage_id = self.create_coverage()
        self.add_photo(
            coverage_id,
            id="photo-approved",
            name="IMG001.jpg",
        )
        self.add_photo(coverage_id, id="photo-review", name="IMG002.jpg")
        self.client.post(
            f"/coverages/{coverage_id}/photos/photo-approved/caption",
            json={
                "caption_narrative": "Caption aprobado.",
                "caption_status": "Aprobado",
            },
        )
        self.client.post(
            f"/coverages/{coverage_id}/photos/photo-review/caption",
            json={
                "caption_narrative": "Caption revisado.",
                "caption_status": "Revisado",
            },
        )

        body = self.client.get(f"/dispatch/new?coverage_id={coverage_id}").get_data(as_text=True)

        self.assertIn("IMG001.jpg", body)
        self.assertIn('value="photo-approved"', body)
        self.assertNotIn('value="photo-approved"  disabled', body)
        self.assertIn("IMG002.jpg", body)
        self.assertIn('value="photo-review"', body)
        self.assertNotIn('value="photo-review"  disabled', body)
        self.assertIn('/photos/photo-approved/media', body)

    def test_safe_thumbnail_route_serves_only_photo_media_from_store(self):
        coverage_id = self.create_coverage()
        self.add_photo(coverage_id)
        media_response = self.client.get(f"/coverages/{coverage_id}/photos/photo-1/media")
        missing_response = self.client.get(f"/coverages/{coverage_id}/photos/missing/media")

        self.assertEqual(media_response.status_code, 200)
        self.assertEqual(missing_response.status_code, 404)
        media_response.close()

    def test_uploaded_photo_survives_restart_and_dispatch_allows_selection(self):
        coverage_id = self.create_coverage()
        self.add_photo(coverage_id)
        self.client.post(
            f"/coverages/{coverage_id}/photos/photo-1/caption",
            json={
                "caption_narrative": "Caption aprobado.",
                "caption_status": "Aprobado",
            },
        )

        reloaded = create_app()
        reloaded.config.update(TESTING=True)
        body = reloaded.test_client().get(f"/dispatch/new?coverage_id={coverage_id}").get_data(as_text=True)

        self.assertIn("IMG001.jpg", body)
        self.assertIn('value="photo-1"', body)
        self.assertNotIn('value="photo-1"  disabled', body)

    def test_storage_symlink_cannot_escape_media_root(self):
        outside_file = self.root / "outside.jpg"
        outside_file.write_bytes(b"outside")
        symlink_path = self.media_root / "coverages" / "cov-link" / "photo.jpg"
        symlink_path.parent.mkdir(parents=True)
        symlink_path.symlink_to(outside_file)
        store = self.app.extensions["lens"]["coverage_store"]

        self.assertFalse(store.is_stored_file_available("coverages/cov-link/photo.jpg"))
        self.assertFalse(store.delete_photo_file("coverages/cov-link/photo.jpg"))
        self.assertTrue(outside_file.exists())

    def test_dispatch_rejects_photo_with_storage_path_escape(self):
        coverage_id = self.create_coverage()
        web.coverages[coverage_id]["photos"].append({
            "id": "escape-photo",
            "name": "escape.jpg",
            "filename": "escape.jpg",
            "storage_path": "../outside.jpg",
            "caption_narrative": "Caption aprobado.",
            "caption_status": "Aprobado",
            "available_on_disk": True,
        })
        web.persist_coverage(coverage_id)

        body = self.client.get(f"/dispatch/new?coverage_id={coverage_id}").get_data(as_text=True)

        self.assertIn("escape.jpg", body)
        self.assertIn("Archivo no disponible para envío", body)
        self.assertIn('value="escape-photo"  disabled', body)

    def test_dispatch_new_prefills_name_from_coverage(self):
        coverage_id = self.create_coverage()

        body = self.client.get(f"/dispatch/new?coverage_id={coverage_id}").get_data(as_text=True)

        self.assertIn('id="name" name="name" type="text" value="Cobertura Persistida"', body)

    def test_dispatch_new_preserves_edited_name_after_error(self):
        coverage_id = self.create_coverage()

        response = self.client.post(
            f"/dispatch/new?coverage_id={coverage_id}",
            data={
                "name": "Nombre editado",
                "coverage_id": coverage_id,
                "photo_ids": [],
                "recipients": "",
                "delivery_note": "",
                "channel": "Manual",
                "mode": "draft",
                "scheduled_date": "",
                "scheduled_time": "",
                "timezone": "America/Guayaquil",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('value="Nombre editado"', response.get_data(as_text=True))

    def test_schedule_fields_hide_for_draft_and_show_for_schedule(self):
        coverage_id = self.create_coverage()
        draft_body = self.client.get(f"/dispatch/new?coverage_id={coverage_id}").get_data(as_text=True)

        schedule_response = self.client.post(
            f"/dispatch/new?coverage_id={coverage_id}",
            data={
                "name": "Nombre",
                "coverage_id": coverage_id,
                "photo_ids": [],
                "recipients": "",
                "delivery_note": "",
                "channel": "Manual",
                "mode": "schedule",
                "scheduled_date": "",
                "scheduled_time": "",
                "timezone": "America/Guayaquil",
            },
        )
        schedule_body = schedule_response.get_data(as_text=True)

        self.assertIn("data-scheduled-delivery-fields hidden", draft_body)
        self.assertIn('data-scheduled-delivery-fields aria-hidden="false"', schedule_body)


if __name__ == "__main__":
    unittest.main()
