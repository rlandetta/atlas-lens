import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app


class UrlPrefixTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def create_test_app(self, prefix=""):
        patches = [
            patch("app.config.ATLAS_URL_PREFIX", prefix),
            patch("app.config.LENS_COVERAGE_STORE_PATH", str(self.root / "lens_coverages.json")),
            patch("app.config.LENS_MEDIA_ROOT", str(self.root / "lens_media")),
            patch("app.config.INGEST_STORE_PATH", str(self.root / "ingest.json")),
            patch("app.config.DISPATCH_STORE_PATH", str(self.root / "dispatch_shipments.json")),
            patch("app.config.DELIVERY_LINKS_STORE_PATH", str(self.root / "delivery_links.json")),
            patch("app.config.DELIVERY_ROOT", str(self.root / "deliveries")),
            patch("app.config.SETTINGS_STORE_PATH", str(self.root / "settings.json")),
            patch("app.config.THUMBNAIL_ROOT", str(self.root / "thumbnails")),
        ]
        for item in patches:
            item.start()
        self.addCleanup(lambda: [item.stop() for item in reversed(patches)])
        app = create_app()
        app.config.update(TESTING=True)
        return app

    def create_coverage(self, client, base_path=""):
        response = client.post(
            f"{base_path}/coverages/new",
            data={
                "coverage_name": "Cobertura Prefix",
                "submit_date": "2026-08-13",
                "event_date": "2026-08-13",
                "city": "Quito",
                "country": "Ecuador",
                "agency": "Xinhua",
                "photographer": "Ricardo Landeta",
                "editor": "rl",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        return response.headers["Location"]

    def test_urls_without_prefix_stay_at_root(self):
        app = self.create_test_app("")
        client = app.test_client()

        body = client.get("/lens").get_data(as_text=True)
        location = self.create_coverage(client)

        self.assertIn('href="/static/css/main.css"', body)
        self.assertIn('href="/flow"', body)
        self.assertIn('href="/lens"', body)
        self.assertIn('href="/dispatch/"', body)
        self.assertIn('href="/settings/"', body)
        self.assertTrue(location.startswith("/coverages/"))
        self.assertEqual(client.get("/flow").status_code, 200)
        self.assertEqual(client.get("/dispatch/").status_code, 200)

    def test_urls_with_prefix_use_script_name(self):
        app = self.create_test_app("/lens")
        client = app.test_client()

        body = client.get("/lens/lens").get_data(as_text=True)
        location = self.create_coverage(client, "/lens")
        detail = client.get(location).get_data(as_text=True)

        self.assertIn('href="/lens/static/css/main.css"', body)
        self.assertIn('href="/lens/flow"', body)
        self.assertIn('href="/lens/lens"', body)
        self.assertIn('href="/lens/dispatch/"', body)
        self.assertIn('href="/lens/settings/"', body)
        self.assertTrue(location.startswith("/lens/coverages/"))
        self.assertIn('href="/lens/dispatch/new?coverage_id=', detail)
        static_response = client.get("/lens/static/css/main.css")
        self.assertEqual(static_response.status_code, 200)
        static_response.close()
        self.assertEqual(client.get("/lens/flow").status_code, 200)
        self.assertEqual(client.get("/lens/dispatch/").status_code, 200)

    def test_delete_coverage_urls_with_prefix_use_script_name(self):
        app = self.create_test_app("/lens")
        client = app.test_client()
        location = self.create_coverage(client, "/lens")
        coverage_id = location.rsplit("/", 1)[-1]

        body = client.get("/lens/lens").get_data(as_text=True)
        response = client.post(
            f"/lens/coverages/{coverage_id}/delete",
            data={
                "confirm_coverage_id": coverage_id,
                "preserve_flow_originals": "accepted",
            },
            follow_redirects=False,
        )

        self.assertIn(f'data-delete-action="/lens/coverages/{coverage_id}/delete"', body)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/lens/lens")


if __name__ == "__main__":
    unittest.main()
