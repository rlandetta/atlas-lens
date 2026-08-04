import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.routes import web


class LensPersistenceRoutesTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.coverage_store_path = self.root / "lens_coverages.json"
        self.media_root = self.root / "media"
        self.dispatch_store_path = self.root / "dispatch_shipments.json"
        self.patches = [
            patch("app.config.LENS_COVERAGE_STORE_PATH", str(self.coverage_store_path)),
            patch("app.config.LENS_MEDIA_ROOT", str(self.media_root)),
            patch("app.config.DISPATCH_STORE_PATH", str(self.dispatch_store_path)),
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

    def add_photo(self, coverage_id, **overrides):
        payload = {
            "id": "photo-1",
            "name": "IMG001.jpg",
            "size": 3,
            "type": "image/jpeg",
            "width": 100,
            "height": 80,
            "data_url": "data:image/jpeg;base64,abc",
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

    def test_photo_persistence_excludes_data_url_and_marks_unavailable(self):
        coverage_id = self.create_coverage()
        self.add_photo(coverage_id)

        stored = self.app.extensions["lens"]["coverage_store"].get(coverage_id)
        photo = stored["photos"][0]

        self.assertEqual(photo["filename"], "IMG001.jpg")
        self.assertEqual(photo["storage_path"], "")
        self.assertFalse(photo["available_on_disk"])
        self.assertNotIn("data_url", photo)
        self.assertNotIn("data:image", self.coverage_store_path.read_text(encoding="utf-8"))

    def test_photo_with_relative_path_is_available_when_file_exists(self):
        media_file = self.media_root / "cov" / "IMG001.jpg"
        media_file.parent.mkdir(parents=True)
        media_file.write_bytes(b"jpg")
        coverage_id = self.create_coverage()
        self.add_photo(coverage_id, storage_path="cov/IMG001.jpg")

        photo = self.app.extensions["lens"]["coverage_store"].get(coverage_id)["photos"][0]

        self.assertEqual(photo["storage_path"], "cov/IMG001.jpg")
        self.assertTrue(photo["available_on_disk"])

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

    def test_delete_coverage_persists(self):
        coverage_id = self.create_coverage()

        response = self.client.post(f"/coverages/{coverage_id}/delete")

        self.assertEqual(response.status_code, 302)
        self.assertIsNone(self.app.extensions["lens"]["coverage_store"].get(coverage_id))

    def test_dispatch_marks_unavailable_photo_as_not_selectable(self):
        coverage_id = self.create_coverage()
        self.add_photo(coverage_id)
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

    def test_coverage_detail_enables_dispatch_button_with_approved_caption(self):
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

    def test_coverage_detail_disables_dispatch_button_without_approved_caption(self):
        coverage_id = self.create_coverage()
        self.add_photo(coverage_id)

        body = self.client.get(f"/coverages/{coverage_id}").get_data(as_text=True)

        self.assertIn("Crear despacho", body)
        self.assertIn("Apruebe al menos una fotografía para crear un despacho.", body)
        self.assertNotIn(f'href="/dispatch/new?coverage_id={coverage_id}"', body)

    def test_dispatch_new_shows_unavailable_approved_photo_disabled(self):
        coverage_id = self.create_coverage()
        self.add_photo(coverage_id)
        self.client.post(
            f"/coverages/{coverage_id}/photos/photo-1/caption",
            json={
                "caption_narrative": "Caption aprobado.",
                "caption_status": "Aprobado",
            },
        )

        body = self.client.get(f"/dispatch/new?coverage_id={coverage_id}").get_data(as_text=True)

        self.assertIn("Cobertura preseleccionada", body)
        self.assertIn("IMG001.jpg", body)
        self.assertIn("Archivo no disponible para envío", body)
        self.assertIn('value="photo-1"  disabled', body)

    def test_dispatch_new_shows_available_approved_photo_selectable_and_excludes_unapproved(self):
        media_file = self.media_root / "cov" / "IMG001.jpg"
        media_file.parent.mkdir(parents=True)
        media_file.write_bytes(b"jpg")
        coverage_id = self.create_coverage()
        self.add_photo(
            coverage_id,
            id="photo-approved",
            name="IMG001.jpg",
            storage_path="cov/IMG001.jpg",
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
        self.assertNotIn("IMG002.jpg", body)


if __name__ == "__main__":
    unittest.main()
