import base64
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app


class AtlasRoutingPhase1Test(unittest.TestCase):
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
    )

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.patchers = []

    def tearDown(self):
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.temp_dir.cleanup()

    def create_test_app(self, prefix: str):
        values = {
            "ATLAS_URL_PREFIX": prefix,
            "AI_ENABLED": True,
            "AI_PROVIDER": "mock",
            "LENS_COVERAGE_STORE_PATH": str(self.root / f"lens_coverages{prefix.replace('/', '_')}.json"),
            "LENS_MEDIA_ROOT": str(self.root / f"lens_media{prefix.replace('/', '_')}"),
            "INGEST_STORE_PATH": str(self.root / f"ingest{prefix.replace('/', '_')}.json"),
            "DISPATCH_STORE_PATH": str(self.root / f"dispatch_shipments{prefix.replace('/', '_')}.json"),
            "DELIVERY_LINKS_STORE_PATH": str(self.root / f"delivery_links{prefix.replace('/', '_')}.json"),
            "DELIVERY_ROOT": str(self.root / f"deliveries{prefix.replace('/', '_')}"),
            "SETTINGS_STORE_PATH": str(self.root / f"settings{prefix.replace('/', '_')}.json"),
            "THUMBNAIL_ROOT": str(self.root / f"thumbnails{prefix.replace('/', '_')}"),
            "PUBLIC_BASE_URL": "",
        }
        for name, value in values.items():
            patcher = patch(f"app.config.{name}", value)
            patcher.start()
            self.patchers.append(patcher)
        app = create_app()
        app.config.update(TESTING=True)

        # app.routes.web imports AI_ENABLED as a module constant, so keep the
        # route-level switch aligned with the patched config for these tests.
        import app.routes.web as web

        web.AI_ENABLED = True
        return app

    def coverage_form(self, **overrides):
        data = {
            "coverage_name": "Cobertura Routing",
            "submit_date": "2026-08-16",
            "event_date": "2026-08-16",
            "city": "Quito",
            "country": "Ecuador",
            "locality_type": "auto",
            "agency": "Xinhua",
            "photographer": "Ricardo Landeta",
            "editor": "rl",
        }
        data.update(overrides)
        return data

    def create_coverage(self, client, base_path: str):
        response = client.post(
            f"{base_path}/coverages/new",
            data=self.coverage_form(),
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        coverage_id = response.headers["Location"].rstrip("/").rsplit("/", 1)[-1]
        return coverage_id, response

    def add_photo(self, client, base_path: str, coverage_id: str, photo_id: str = "photo-1"):
        payload = {
            "id": photo_id,
            "name": "IMG001.png",
            "size": len(self.png_bytes),
            "type": "image/png",
            "width": 1,
            "height": 1,
            "data_url": f"data:image/png;base64,{base64.b64encode(self.png_bytes).decode('ascii')}",
        }
        response = client.post(f"{base_path}/coverages/{coverage_id}/photos", json=payload)
        self.assertEqual(response.status_code, 201)
        return response

    def save_caption(self, client, base_path: str, coverage_id: str, photo_id: str = "photo-1", caption: str = "Caption inicial."):
        response = client.post(
            f"{base_path}/coverages/{coverage_id}/photos/{photo_id}/caption",
            json={
                "caption_narrative": caption,
                "caption_status": "Aprobado",
                "is_drone": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        return response

    def test_mode_a_current_production_entrypoints_with_lens_prefix(self):
        app = self.create_test_app("/lens")
        client = app.test_client()
        coverage_id, _ = self.create_coverage(client, "/lens")

        expectations = {
            "/lens/": "Dashboard",
            "/lens/flow": "FLOW",
            "/lens/lens": "Nueva cobertura",
            f"/lens/coverages/{coverage_id}": "Cobertura Routing",
            "/lens/dispatch/": "DISPATCH",
            "/lens/settings/": "SETTINGS",
        }
        for path, marker in expectations.items():
            with self.subTest(path=path):
                response = client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn(marker, response.get_data(as_text=True))

        static_response = client.get("/lens/static/css/main.css")
        self.assertEqual(static_response.status_code, 200)
        static_response.close()

    def test_mode_a_current_production_lens_critical_actions_keep_method_and_body(self):
        app = self.create_test_app("/lens")
        client = app.test_client()
        coverage_id, create_response = self.create_coverage(client, "/lens")
        self.assertTrue(create_response.headers["Location"].startswith("/lens/coverages/"))

        edit_response = client.post(
            f"/lens/coverages/{coverage_id}/edit",
            data=self.coverage_form(coverage_name="Cobertura Editada", city="Guayaquil"),
            follow_redirects=False,
        )
        self.assertEqual(edit_response.status_code, 302)
        detail_body = client.get(f"/lens/coverages/{coverage_id}").get_data(as_text=True)
        self.assertIn("Cobertura Editada", detail_body)

        self.add_photo(client, "/lens", coverage_id)
        caption_response = self.save_caption(client, "/lens", coverage_id, caption="Primer autoguardado.")
        self.assertTrue(caption_response.get_json()["saved"])
        autosave_response = self.save_caption(client, "/lens", coverage_id, caption="Segundo autoguardado.")
        self.assertEqual(autosave_response.get_json()["caption_narrative"], "Segundo autoguardado.")

        media_response = client.get(f"/lens/coverages/{coverage_id}/photos/photo-1/media")
        self.assertEqual(media_response.status_code, 200)
        media_response.close()
        thumbnail_response = client.get(f"/lens/coverages/{coverage_id}/photos/photo-1/thumbnail")
        self.assertEqual(thumbnail_response.status_code, 200)
        thumbnail_response.close()

        ai_context_response = client.get(f"/lens/coverages/{coverage_id}/photos/photo-1/ai-context")
        self.assertEqual(ai_context_response.status_code, 200)
        self.assertTrue(ai_context_response.get_json()["ok"])
        ai_response = client.post(f"/lens/coverages/{coverage_id}/photos/photo-1/generate-narration", json={})
        self.assertEqual(ai_response.status_code, 200)
        self.assertTrue(ai_response.get_json()["ok"])

        export_response = client.post(
            f"/lens/coverages/{coverage_id}/exports",
            json={
                "formats": ["docx"],
                "include_captions": True,
                "include_photos": False,
                "destination": "download",
            },
        )
        self.assertEqual(export_response.status_code, 200)
        self.assertTrue(export_response.get_json()["ok"])

        delete_photo_response = client.post(f"/lens/coverages/{coverage_id}/photos/photo-1/delete", json={})
        self.assertEqual(delete_photo_response.status_code, 200)
        self.assertEqual(delete_photo_response.get_json()["total"], 0)

        delete_response = client.post(
            f"/lens/coverages/{coverage_id}/delete",
            data={
                "confirm_coverage_id": coverage_id,
                "preserve_flow_originals": "accepted",
            },
            follow_redirects=False,
        )
        self.assertEqual(delete_response.status_code, 302)
        self.assertEqual(delete_response.headers["Location"], "/lens/lens")

    def test_mode_a_flow_dispatch_settings_and_public_delivery_posts_keep_body(self):
        app = self.create_test_app("/lens")
        client = app.test_client()
        coverage_id, _ = self.create_coverage(client, "/lens")
        self.add_photo(client, "/lens", coverage_id, photo_id="photo-approved")
        self.save_caption(client, "/lens", coverage_id, photo_id="photo-approved", caption="Caption aprobado.")

        dispatch_response = client.post(
            "/lens/dispatch/new",
            data={
                "name": "Despacho Routing",
                "coverage_id": coverage_id,
                "photo_ids": ["photo-approved"],
                "recipient_name[]": ["Mesa Xinhua"],
                "recipient_email[]": ["desk@xinhua.com"],
                "delivery_note": "Lista para despacho.",
                "channel": "Manual",
                "delivery_method": "download_link",
                "link_expires_in": "7",
                "mode": "immediate",
                "scheduled_date": "",
                "scheduled_time": "",
                "timezone": "America/Guayaquil",
                "include_caption_docx": "1",
            },
            follow_redirects=False,
        )
        self.assertEqual(dispatch_response.status_code, 302)
        shipment_id = dispatch_response.headers["Location"].rstrip("/").rsplit("/", 1)[-1]
        shipment = app.extensions["dispatch"]["shipment_service"].get_shipment(shipment_id)
        self.assertEqual(shipment["name"], "Despacho Routing")
        self.assertEqual(shipment["delivery_method"], "download_link")

        link = app.extensions["dispatch"]["delivery_link_service"].get_active_for_shipment(shipment_id)
        self.assertIsNotNone(link)
        public_response = client.get(f"/lens/d/{link['token']}")
        self.assertEqual(public_response.status_code, 200)

        channel_response = client.post(
            "/lens/settings/channels/new",
            data={
                "id": "xinhua",
                "name": "Xinhua",
                "display_name": "Xinhua News Agency",
                "channel_type": "smtp",
                "sender_email": "notificaciones@ayampi.com",
                "reply_to": "desk@xinhua.com",
                "smtp_host": "smtp.zoho.com",
                "smtp_port": "465",
                "smtp_security": "ssl",
                "smtp_username": "notificaciones@ayampi.com",
                "credential_ref": "ATLAS_SMTP_CHANNEL_XINHUA",
                "is_active": "1",
                "is_default": "1",
            },
            follow_redirects=False,
        )
        self.assertEqual(channel_response.status_code, 302)
        self.assertEqual(app.extensions["settings"]["settings_service"].list_outbound_channels()[0]["id"], "xinhua")

    def test_mode_a_flow_to_lens_handoff_keeps_post_body(self):
        app = self.create_test_app("/lens")
        client = app.test_client()
        ingest_store = app.extensions["ingest"]["store"]
        ingest_store.save({
            "sessions": [
                {
                    "id": "session-routing",
                    "created_at": "2026-08-16T00:00:00+00:00",
                    "updated_at": "2026-08-16T00:00:00+00:00",
                    "status": "ready",
                    "sources": [],
                    "photos": [],
                }
            ],
            "photos": [],
        })

        response = client.post("/lens/flow/sessions/session-routing/lens/open", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/lens/coverages/", response.headers["Location"])

    def test_mode_b_canonical_target_routes_without_prefix(self):
        app = self.create_test_app("")
        client = app.test_client()
        coverage_id, _ = self.create_coverage(client, "")
        link_token = self.create_public_delivery_token(client, app, coverage_id, "")

        expectations = {
            "/": 200,
            "/flow/": 200,
            "/lens/": 200,
            "/lens/coverages/new": 200,
            f"/lens/coverages/{coverage_id}": 200,
            "/dispatch/": 200,
            "/settings/": 200,
            "/static/css/main.css": 200,
            f"/d/{link_token}": 200,
        }
        for path, status_code in expectations.items():
            with self.subTest(path=path):
                response = client.get(path)
                self.assertEqual(response.status_code, status_code)
                response.close()

    def test_current_unprefixed_legacy_coverages_routes_are_direct_handlers(self):
        app = self.create_test_app("")
        client = app.test_client()
        coverage_id, create_response = self.create_coverage(client, "")

        self.assertEqual(create_response.status_code, 302)
        self.assertTrue(create_response.headers["Location"].startswith("/coverages/"))
        self.assertEqual(client.get(f"/coverages/{coverage_id}").status_code, 200)
        self.assertEqual(client.get("/coverages/new").status_code, 200)

        edit_response = client.post(
            f"/coverages/{coverage_id}/edit",
            data=self.coverage_form(coverage_name="Legacy Edit"),
            follow_redirects=False,
        )
        self.assertEqual(edit_response.status_code, 302)
        self.assertEqual(edit_response.headers["Location"], f"/coverages/{coverage_id}")

    def test_templates_render_url_for_data_attributes_for_lens_actions(self):
        app = self.create_test_app("/lens")
        client = app.test_client()
        coverage_id, _ = self.create_coverage(client, "/lens")
        body = client.get(f"/lens/coverages/{coverage_id}").get_data(as_text=True)

        expected_fragments = [
            f'data-photos-url="/lens/coverages/{coverage_id}/photos"',
            f'data-photo-delete-url-template="/lens/coverages/{coverage_id}/photos/__PHOTO_ID__/delete"',
            f'data-photo-caption-url-template="/lens/coverages/{coverage_id}/photos/__PHOTO_ID__/caption"',
            f'data-copy-caption-url="/lens/coverages/{coverage_id}/captions/copy-caption-empty"',
            f'data-photo-ai-url-template="/lens/coverages/{coverage_id}/photos/__PHOTO_ID__/generate-narration"',
            f'data-photo-ai-context-url-template="/lens/coverages/{coverage_id}/photos/__PHOTO_ID__/ai-context"',
            f'data-export-url="/lens/coverages/{coverage_id}/exports"',
            f'action="/lens/coverages/{coverage_id}/edit"',
        ]
        for fragment in expected_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, body)

    def test_javascript_uses_data_attributes_instead_of_hardcoded_route_roots(self):
        files = {
            "coverage_delete.js": Path("app/static/js/coverage_delete.js").read_text(encoding="utf-8"),
            "photo_workspace.js": Path("app/static/js/photo_workspace.js").read_text(encoding="utf-8"),
            "export_panel.js": Path("app/static/js/export_panel.js").read_text(encoding="utf-8"),
        }
        self.assertIn("button.dataset.deleteAction", files["coverage_delete.js"])
        self.assertIn("fetch(deleteForm.action", files["coverage_delete.js"])
        self.assertIn("photoWorkspace.dataset.photosUrl", files["photo_workspace.js"])
        self.assertIn("photoWorkspace.dataset.photoDeleteUrlTemplate", files["photo_workspace.js"])
        self.assertIn("photoWorkspace.dataset.photoCaptionUrlTemplate", files["photo_workspace.js"])
        self.assertIn("photoWorkspace.dataset.copyCaptionUrl", files["photo_workspace.js"])
        self.assertIn("photoWorkspace.dataset.photoAiUrlTemplate", files["photo_workspace.js"])
        self.assertIn("photoWorkspace.dataset.photoAiContextUrlTemplate", files["photo_workspace.js"])
        self.assertIn("exportSection.dataset.exportUrl", files["export_panel.js"])

        route_literal = re.compile(r"['\"]/(?:lens/)?(?:coverages|dispatch|settings|flow|d)/")
        for filename, source in files.items():
            with self.subTest(filename=filename):
                self.assertIsNone(route_literal.search(source))

    def create_public_delivery_token(self, client, app, coverage_id: str, base_path: str) -> str:
        self.add_photo(client, base_path, coverage_id, photo_id="photo-public")
        self.save_caption(client, base_path, coverage_id, photo_id="photo-public", caption="Caption publico.")
        response = client.post(
            f"{base_path}/dispatch/new",
            data={
                "name": "Despacho Publico",
                "coverage_id": coverage_id,
                "photo_ids": ["photo-public"],
                "recipient_name[]": ["Mesa Xinhua"],
                "recipient_email[]": ["desk@xinhua.com"],
                "delivery_note": "Entrega publica.",
                "channel": "Manual",
                "delivery_method": "download_link",
                "link_expires_in": "7",
                "mode": "immediate",
                "scheduled_date": "",
                "scheduled_time": "",
                "timezone": "America/Guayaquil",
                "include_caption_docx": "1",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        shipment_id = response.headers["Location"].rstrip("/").rsplit("/", 1)[-1]
        link = app.extensions["dispatch"]["delivery_link_service"].get_active_for_shipment(shipment_id)
        self.assertIsNotNone(link)
        return link["token"]


if __name__ == "__main__":
    unittest.main()
