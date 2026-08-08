import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.dispatch import DeliveryLinkService, DeliveryLinkStore, DeliveryPackageService, DispatchShipmentStore, ShipmentService
from app.dispatch.delivery_links import DeliveryLinkStore as RawDeliveryLinkStore
from app.dispatch.delivery_package import DeliveryPackageError
from app.lens_read_service import LensReadService


class DeliveryPackageServiceTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.media_root = self.root / "media"
        self.delivery_root = self.root / "deliveries"
        photo_path = self.media_root / "coverages" / "cov-1" / "photo-1_IMG001.jpg"
        photo_path.parent.mkdir(parents=True)
        photo_path.write_bytes(b"jpeg-one")
        unused_path = self.media_root / "coverages" / "cov-1" / "photo-2_IMG002.jpg"
        unused_path.write_bytes(b"jpeg-two")
        self.coverage = {
            "coverage_name": "Cobertura Quito",
            "city": "Quito",
            "country": "Ecuador",
            "agency": "Xinhua",
            "photographer": "Ricardo Landeta",
            "editor": "rl",
            "submit_date": "2026-08-07",
            "event_date": "2026-08-07",
            "photos": [
                {
                    "id": "photo-1",
                    "name": "IMG001.jpg",
                    "filename": "IMG001.jpg",
                    "storage_path": "coverages/cov-1/photo-1_IMG001.jpg",
                    "caption_narrative": "Persona participa en evento.",
                    "caption_status": "Aprobado",
                    "available_on_disk": True,
                },
                {
                    "id": "photo-2",
                    "name": "IMG002.jpg",
                    "filename": "IMG002.jpg",
                    "storage_path": "coverages/cov-1/photo-2_IMG002.jpg",
                    "caption_narrative": "Persona observa actividad.",
                    "caption_status": "Aprobado",
                    "available_on_disk": True,
                },
            ],
        }
        self.shipment = {
            "id": "ship-1",
            "coverage_id": "cov-1",
            "photo_ids": ["photo-1"],
            "include_caption_docx": True,
            "export_reference": {"caption_docx": {"photo_scope": "selected"}},
            "coverage_snapshot": {"coverage_name": "Cobertura Quito"},
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_package_copies_selected_photo_generates_docx_zip_manifest_and_preserves_lens(self):
        original = (self.media_root / "coverages" / "cov-1" / "photo-1_IMG001.jpg").read_bytes()
        package = DeliveryPackageService(delivery_root=self.delivery_root, media_root=self.media_root).prepare_package(
            shipment=self.shipment,
            coverage=self.coverage,
        )

        names = {item.filename for item in package.files}
        self.assertIn("IMG001.jpg", names)
        self.assertNotIn("IMG002.jpg", names)
        self.assertTrue(any(item.filename.endswith("_Captions.docx") for item in package.files))
        self.assertTrue(package.zip_path.is_file())
        manifest = json.loads(package.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["shipment_id"], "ship-1")
        self.assertEqual(manifest["coverage_id"], "cov-1")
        self.assertGreater(manifest["total_bytes"], 0)
        self.assertEqual((self.media_root / "coverages" / "cov-1" / "photo-1_IMG001.jpg").read_bytes(), original)

    def test_package_rejects_storage_path_traversal(self):
        coverage = json.loads(json.dumps(self.coverage))
        coverage["photos"][0]["storage_path"] = "../outside.jpg"
        with self.assertRaises(DeliveryPackageError):
            DeliveryPackageService(delivery_root=self.delivery_root, media_root=self.media_root).prepare_package(
                shipment=self.shipment,
                coverage=coverage,
            )


class DeliveryLinksAndRoutesTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.store_path = self.root / "dispatch.json"
        self.settings_path = self.root / "settings.json"
        self.links_path = self.root / "links.json"
        self.lens_path = self.root / "lens.json"
        self.media_root = self.root / "media"
        self.delivery_root = self.root / "deliveries"
        self.patches = [
            patch("app.config.DISPATCH_STORE_PATH", str(self.store_path)),
            patch("app.config.SETTINGS_STORE_PATH", str(self.settings_path)),
            patch("app.config.DELIVERY_LINKS_STORE_PATH", str(self.links_path)),
            patch("app.config.LENS_COVERAGE_STORE_PATH", str(self.lens_path)),
            patch("app.config.LENS_MEDIA_ROOT", str(self.media_root)),
            patch("app.config.DELIVERY_ROOT", str(self.delivery_root)),
            patch("app.config.PUBLIC_BASE_URL", "https://atlas.lavoceria.com"),
        ]
        for item in self.patches:
            item.start()
        self.app = create_app()
        self.app.config.update(TESTING=True)
        photo_path = self.media_root / "coverages" / "cov-1" / "photo-1_IMG001.jpg"
        photo_path.parent.mkdir(parents=True)
        photo_path.write_bytes(b"jpeg-one")
        coverage = {
            "coverage_name": "Cobertura Quito",
            "submit_date": "2026-08-07",
            "event_date": "2026-08-07",
            "city": "Quito",
            "country": "Ecuador",
            "agency": "Xinhua",
            "photographer": "Ricardo Landeta",
            "editor": "rl",
            "photos": [{
                "id": "photo-1",
                "name": "IMG001.jpg",
                "filename": "IMG001.jpg",
                "storage_path": "coverages/cov-1/photo-1_IMG001.jpg",
                "caption_narrative": "Persona participa en evento.",
                "caption_status": "Aprobado",
                "available_on_disk": True,
            }],
        }
        self.app.extensions["lens"]["coverage_store"].set("cov-1", coverage)
        self.client = self.app.test_client()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp_dir.cleanup()

    def valid_form(self, **overrides):
        form = {
            "name": "Despacho link",
            "coverage_id": "cov-1",
            "photo_ids": ["photo-1"],
            "recipient_name[]": ["Mesa"],
            "recipient_email[]": ["desk@example.com"],
            "delivery_note": "Lista.",
            "delivery_method": "download_link",
            "link_expires_in": "7",
            "channel": "Enlace de descarga",
            "mode": "immediate",
            "timezone": "America/Guayaquil",
            "include_caption_docx": "1",
        }
        form.update(overrides)
        return form

    def create_ready_link_shipment(self):
        response = self.client.post("/dispatch/new", data=self.valid_form(), follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        shipment = self.app.extensions["dispatch"]["shipment_service"].list_shipments()[0]
        link = self.app.extensions["dispatch"]["delivery_link_service"].get_active_for_shipment(shipment["id"])
        self.assertIsNotNone(link)
        return shipment, link

    def test_download_link_token_public_base_url_downloads_and_counter(self):
        shipment, link = self.create_ready_link_shipment()
        self.assertNotIn(shipment["id"], link["token"])
        self.assertTrue(link["url"].startswith("https://atlas.lavoceria.com/d/"))

        landing = self.client.get(f"/d/{link['token']}")
        self.assertEqual(landing.status_code, 200)
        self.assertIn("Descargar todo", landing.get_data(as_text=True))

        zip_response = self.client.get(f"/d/{link['token']}/download")
        self.assertEqual(zip_response.status_code, 200)
        refreshed = self.app.extensions["dispatch"]["delivery_link_service"].get_active_for_shipment(shipment["id"])
        self.assertEqual(refreshed["download_count"], 1)
        self.assertTrue(refreshed["last_download_at"])

    def test_revoked_and_expired_links_are_rejected_and_regenerate_invalidates_previous(self):
        shipment, link = self.create_ready_link_shipment()
        self.client.post(f"/dispatch/{shipment['id']}/delivery-link/revoke")
        self.assertEqual(self.client.get(f"/d/{link['token']}").status_code, 404)

        self.client.post(f"/dispatch/{shipment['id']}/delivery-link/regenerate")
        new_link = self.app.extensions["dispatch"]["delivery_link_service"].get_active_for_shipment(shipment["id"])
        self.assertNotEqual(link["token"], new_link["token"])
        self.assertEqual(self.client.get(f"/d/{new_link['token']}").status_code, 200)

        expired = self.app.extensions["dispatch"]["delivery_link_store"].update(
            new_link["id"],
            {"expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()},
        )
        self.assertIsNone(self.app.extensions["dispatch"]["delivery_link_service"].get_by_token(expired["token"]))

    def test_download_routes_reject_path_traversal_file_ids(self):
        _, link = self.create_ready_link_shipment()
        self.assertEqual(self.client.get(f"/d/{link['token']}/file/../../etc/passwd").status_code, 404)


class DeliveryLinkStoreTest(unittest.TestCase):
    def test_token_store_uses_atomic_json_and_no_password_required(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = DeliveryLinkStore(Path(temp_dir) / "links.json")
            service = DeliveryLinkService(store, "")
            link = service.create_link("ship-1", expires_in="none")
            raw = (Path(temp_dir) / "links.json").read_text(encoding="utf-8")
            self.assertIn("token", raw)
            self.assertNotIn("password", raw.lower().replace("password_hash", ""))
            self.assertEqual(link["expires_at"], "")
            self.assertTrue(RawDeliveryLinkStore.is_usable(link))


if __name__ == "__main__":
    unittest.main()

class SFTPTransportTest(unittest.TestCase):
    def test_missing_paramiko_reports_controlled_error(self):
        from app.dispatch.sftp_transport import SFTPTransport, SFTPTransportError

        transport = SFTPTransport(settings_service=None)
        if transport.is_available:
            self.skipTest("paramiko está instalado en este entorno")
        with self.assertRaises(SFTPTransportError):
            transport.upload_package(channel={}, package_root=Path("/tmp"), files=[])
