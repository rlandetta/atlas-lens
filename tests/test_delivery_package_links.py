import json
import tempfile
import unittest
import zipfile
import copy
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.dispatch import DeliveryLinkService, DeliveryLinkStore, DeliveryPackageService, DispatchShipmentStore, ShipmentService
from app.dispatch.delivery_links import DeliveryLinkStore as RawDeliveryLinkStore
from app.dispatch.delivery_package import DeliveryPackageError
from app.dispatch.delivery_previews import DeliveryPreview, DeliveryPreviewService
from app.dispatch.smtp_transport import SMTPTransportError
from app.lens_read_service import LensReadService
from app.settings import OutboundChannelDraft


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

    def test_manifest_total_bytes_excludes_zip_size(self):
        package = DeliveryPackageService(delivery_root=self.delivery_root, media_root=self.media_root).prepare_package(
            shipment=self.shipment,
            coverage=self.coverage,
        )

        manifest = json.loads(package.manifest_path.read_text(encoding="utf-8"))
        files_size = sum(item["size"] for item in manifest["files"])
        self.assertEqual(manifest["total_bytes"], files_size)
        self.assertNotEqual(manifest["total_bytes"], files_size + manifest["zip"]["size"])

    def test_package_rejects_storage_path_traversal(self):
        coverage = json.loads(json.dumps(self.coverage))
        coverage["photos"][0]["storage_path"] = "../outside.jpg"
        with self.assertRaises(DeliveryPackageError):
            DeliveryPackageService(delivery_root=self.delivery_root, media_root=self.media_root).prepare_package(
                shipment=self.shipment,
                coverage=coverage,
            )

    def test_package_copies_flow_path_photo(self):
        flow_path = self.root / "events" / "IMG_FLOW.jpg"
        flow_path.parent.mkdir(parents=True)
        flow_path.write_bytes(b"flow-jpeg")
        coverage = json.loads(json.dumps(self.coverage))
        coverage["photos"] = [
            {
                "id": "photo-flow",
                "name": "IMG_FLOW.jpg",
                "filename": "IMG_FLOW.jpg",
                "storage_path": "",
                "flow_path": str(flow_path),
                "caption_narrative": "Persona participa en cobertura FLOW.",
                "caption_status": "Aprobado",
                "available_on_disk": True,
            }
        ]
        shipment = {
            **self.shipment,
            "photo_ids": ["photo-flow"],
        }

        package = DeliveryPackageService(delivery_root=self.delivery_root, media_root=self.media_root).prepare_package(
            shipment=shipment,
            coverage=coverage,
        )

        copied = next(item for item in package.files if item.filename == "IMG_FLOW.jpg")
        self.assertEqual((package.root / copied.path).read_bytes(), b"flow-jpeg")
        self.assertEqual(flow_path.read_bytes(), b"flow-jpeg")

    def test_package_copies_archived_flow_photo_from_common_resolver(self):
        events_path = self.root / "storage" / "events" / "2026" / "08" / "12" / "sabado" / "ricardo" / "canon-r6" / "JPG" / "_21A1622.JPG"
        archive_path = self.root / "storage" / "archive" / "2026" / "08" / "12" / "canon-r6" / "_21A1622.JPG"
        archive_path.parent.mkdir(parents=True)
        archive_path.write_bytes(b"archived-flow-jpeg")
        coverage = json.loads(json.dumps(self.coverage))
        coverage["photos"] = [
            {
                "id": "photo-flow",
                "name": "_21A1622.JPG",
                "filename": "_21A1622.JPG",
                "storage_path": "",
                "flow_path": str(events_path),
                "caption_narrative": "Persona participa en cobertura FLOW.",
                "caption_status": "Aprobado",
                "available_on_disk": True,
            }
        ]
        shipment = {
            **self.shipment,
            "photo_ids": ["photo-flow"],
        }

        package = DeliveryPackageService(delivery_root=self.delivery_root, media_root=self.media_root).prepare_package(
            shipment=shipment,
            coverage=coverage,
        )

        copied = next(item for item in package.files if item.filename == "_21A1622.JPG")
        self.assertEqual((package.root / copied.path).read_bytes(), b"archived-flow-jpeg")


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

    def write_preview_manifest(self, shipment_id, previews):
        previews_dir = self.delivery_root / shipment_id / "previews"
        previews_dir.mkdir(parents=True, exist_ok=True)
        preview_groups = previews if isinstance(previews, dict) else {"previews": previews}
        for group in preview_groups.values():
            if not isinstance(group, list):
                continue
            for preview in group:
                if isinstance(preview, dict) and preview.get("filename"):
                    (previews_dir / preview["filename"]).write_bytes(b"preview-jpeg")
        (previews_dir / "previews.json").write_text(
            json.dumps(preview_groups, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def expand_coverage_photos(self, count):
        coverage = self.app.extensions["lens"]["coverage_store"].get("cov-1")
        photos = []
        for index in range(1, count + 1):
            photo_id = f"photo-{index}"
            filename = f"IMG{index:03}.jpg"
            storage_path = f"coverages/cov-1/{photo_id}_{filename}"
            target = self.media_root / storage_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(f"jpeg-{index}".encode())
            photos.append({
                "id": photo_id,
                "name": filename,
                "filename": filename,
                "storage_path": storage_path,
                "caption_narrative": f"Persona participa en evento {index}.",
                "caption_status": "Aprobado",
                "available_on_disk": True,
            })
        coverage["photos"] = photos
        self.app.extensions["lens"]["coverage_store"].set("cov-1", coverage)
        return [photo["id"] for photo in photos]

    def create_smtp_channel(self):
        return self.app.extensions["settings"]["settings_service"].create_outbound_channel(
            OutboundChannelDraft(
                id="xinhua-smtp",
                name="Xinhua SMTP",
                display_name="Xinhua News Agency",
                channel_type="smtp",
                sender_email="atlas@example.com",
                reply_to="",
                smtp_host="smtp.example.com",
                smtp_port=465,
                smtp_security="ssl",
                smtp_username="atlas@example.com",
                credential_ref="ATLAS_SMTP_TEST",
                is_active=True,
                is_default=True,
            )
        )

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

    def test_package_download_creates_activity_event(self):
        shipment, link = self.create_ready_link_shipment()

        self.client.get(f"/d/{link['token']}/download")

        refreshed = self.app.extensions["dispatch"]["delivery_link_service"].get_active_for_shipment(shipment["id"])
        self.assertEqual(len(refreshed["download_events"]), 1)
        event = refreshed["download_events"][0]
        self.assertEqual(event["download_type"], "PACKAGE")
        self.assertTrue(event["downloaded_at"])
        self.assertEqual(event["country"], "")

    def test_photo_download_creates_activity_event(self):
        shipment, link = self.create_ready_link_shipment()

        self.client.get(f"/d/{link['token']}/file/photo-1")

        refreshed = self.app.extensions["dispatch"]["delivery_link_service"].get_active_for_shipment(shipment["id"])
        event = refreshed["download_events"][0]
        self.assertEqual(event["download_type"], "PHOTO")
        self.assertEqual(event["filename"], "IMG001.jpg")

    def test_document_download_creates_activity_event(self):
        shipment, link = self.create_ready_link_shipment()
        manifest = self.app.extensions["dispatch"]["delivery_package_service"].load_manifest(shipment["id"])
        docx_item = next(item for item in manifest["files"] if item["type"] == "document")

        self.client.get(f"/d/{link['token']}/file/{docx_item['id']}")

        refreshed = self.app.extensions["dispatch"]["delivery_link_service"].get_active_for_shipment(shipment["id"])
        event = refreshed["download_events"][0]
        self.assertEqual(event["download_type"], "DOCUMENT")
        self.assertEqual(event["filename"], docx_item["filename"])

    def test_activity_events_ordered_most_recent_first_and_capped_at_ten_in_ui(self):
        shipment, link = self.create_ready_link_shipment()

        for _ in range(12):
            self.client.get(f"/d/{link['token']}/download")

        detail_body = self.client.get(f"/dispatch/{shipment['id']}").get_data(as_text=True)
        self.assertIn("Mostrando las 10 descargas más recientes", detail_body)
        self.assertEqual(detail_body.count("Descargó: paquete completo"), 10)

        refreshed = self.app.extensions["dispatch"]["delivery_link_service"].get_active_for_shipment(shipment["id"])
        self.assertEqual(len(refreshed["download_events"]), 12)
        timestamps = [event["downloaded_at"] for event in refreshed["download_events"]]
        self.assertEqual(timestamps, sorted(timestamps, reverse=True))

    def test_download_activity_falls_back_to_location_unavailable(self):
        shipment, link = self.create_ready_link_shipment()

        self.client.get(f"/d/{link['token']}/download")

        detail_body = self.client.get(f"/dispatch/{shipment['id']}").get_data(as_text=True)
        self.assertIn("Ubicación no disponible", detail_body)

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

    def test_public_landing_works_without_previews_and_keeps_downloads(self):
        shipment, link = self.create_ready_link_shipment()

        landing = self.client.get(f"/d/{link['token']}")
        zip_response = self.client.get(f"/d/{link['token']}/download")
        file_response = self.client.get(f"/d/{link['token']}/file/photo-1")

        self.assertEqual(landing.status_code, 200)
        body = landing.get_data(as_text=True)
        self.assertIn("data-delivery-backgrounds='[]'", body)
        self.assertIn("delivery_backgrounds.js", body)
        self.assertIn("Descargar todo", body)
        self.assertIn("ATLAS DISPATCH", body)
        self.assertNotIn("<img", body)
        self.assertEqual(zip_response.status_code, 200)
        self.assertEqual(file_response.status_code, 200)
        self.assertEqual(self.app.extensions["lens"]["coverage_store"].get("cov-1")["photos"][0]["storage_path"], "coverages/cov-1/photo-1_IMG001.jpg")
        manifest = self.app.extensions["dispatch"]["delivery_package_service"].load_manifest(shipment["id"])
        self.assertFalse(any(str(item.get("path", "")).startswith("previews/") for item in manifest["files"]))
        with zipfile.ZipFile(self.delivery_root / shipment["id"] / "package.zip") as archive:
            self.assertFalse(any(name.startswith("previews/") for name in archive.namelist()))

    def test_public_landing_generates_8_thumbnails_and_4_backgrounds(self):
        photo_ids = self.expand_coverage_photos(8)
        response = self.client.post("/dispatch/new", data=self.valid_form(photo_ids=photo_ids), follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        shipment = self.app.extensions["dispatch"]["shipment_service"].list_shipments()[0]
        link = self.app.extensions["dispatch"]["delivery_link_service"].get_active_for_shipment(shipment["id"])

        def fake_create_preview(service, package_root, previews_dir, item, *, kind, max_long_edge, quality):
            safe_file_id = service.build_preview_id(kind, item["id"]).split(":", 1)[1]
            filename = f"{kind}-{safe_file_id}.jpg"
            destination = previews_dir / filename
            destination.write_bytes(b"preview-jpeg")
            return DeliveryPreview(
                id=service.build_preview_id(kind, safe_file_id),
                file_id=item["id"],
                filename=filename,
                path=f"previews/{filename}",
                kind=kind,
                width=max_long_edge,
                height=max_long_edge // 2,
                size=destination.stat().st_size,
            )

        with patch.object(DeliveryPreviewService, "pillow_available", return_value=True), patch.object(DeliveryPreviewService, "create_preview", fake_create_preview):
            response = self.client.get(f"/d/{link['token']}")

        self.assertEqual(response.status_code, 200)
        body = unescape(response.get_data(as_text=True))
        self.assertEqual(body.count('loading="lazy"'), 8)
        self.assertIn(f"/d/{link['token']}/preview/thumbnail:photo-1", body)
        self.assertIn(f"/d/{link['token']}/preview/background:photo-1", body)
        self.assertNotIn(f"/d/{link['token']}/file/photo-1", body.split("<img", 1)[-1].split(">", 1)[0])
        self.assertEqual(body.count("/preview/background:photo-"), 4)
        payload = self.app.extensions["dispatch"]["delivery_preview_service"].load_previews(shipment["id"])
        self.assertEqual(len(payload["thumbnails"]), 8)
        self.assertEqual(len(payload["backgrounds"]), 4)
        for index in range(1, 9):
            self.assertEqual(self.client.get(f"/d/{link['token']}/preview/thumbnail:photo-{index}").status_code, 200)
        for preview in payload["backgrounds"]:
            self.assertEqual(self.client.get(f"/d/{link['token']}/preview/{preview['id']}").status_code, 200)


    def test_legacy_uuid_preview_manifest_still_serves_existing_preview(self):
        shipment, link = self.create_ready_link_shipment()
        legacy_id = "9a6aaf80-1c14-4575-ab9f-42e9c3325e4d"
        self.write_preview_manifest(shipment["id"], [
            {"id": legacy_id, "file_id": "photo-1", "filename": f"{legacy_id}.jpg", "path": f"previews/{legacy_id}.jpg", "size": 12},
        ])

        response = self.client.get(f"/d/{link['token']}")
        preview_response = self.client.get(f"/d/{link['token']}/preview/{legacy_id}")

        self.assertEqual(response.status_code, 200)
        self.assertIn(f"/d/{link['token']}/preview/{legacy_id}", unescape(response.get_data(as_text=True)))
        self.assertEqual(preview_response.status_code, 200)

    def test_preview_route_is_token_bound_safe_and_decorative(self):
        shipment, link = self.create_ready_link_shipment()
        self.write_preview_manifest(shipment["id"], [
            {"id": "thumbnail:photo-1", "file_id": "photo-1", "filename": "thumbnail-photo-1.jpg", "path": "previews/thumbnail-photo-1.jpg", "kind": "thumbnail", "size": 12},
        ])

        preview_response = self.client.get(f"/d/{link['token']}/preview/thumbnail:photo-1")
        traversal_response = self.client.get(f"/d/{link['token']}/preview/../../package.zip")
        missing_response = self.client.get(f"/d/{link['token']}/preview/missing")
        zip_response = self.client.get(f"/d/{link['token']}/download")
        file_response = self.client.get(f"/d/{link['token']}/file/photo-1")

        self.assertEqual(preview_response.status_code, 200)
        self.assertEqual(preview_response.mimetype, "image/jpeg")
        self.assertIn("max-age=86400", preview_response.headers["Cache-Control"])
        self.assertEqual(traversal_response.status_code, 404)
        self.assertEqual(missing_response.status_code, 404)
        self.assertEqual(zip_response.status_code, 200)
        self.assertEqual(file_response.status_code, 200)

    def test_expired_and_revoked_links_do_not_expose_previews(self):
        shipment, link = self.create_ready_link_shipment()
        self.write_preview_manifest(shipment["id"], [
            {"id": "thumbnail:photo-1", "file_id": "photo-1", "filename": "thumbnail-photo-1.jpg", "path": "previews/thumbnail-photo-1.jpg", "kind": "thumbnail", "size": 12},
        ])
        expired = self.app.extensions["dispatch"]["delivery_link_store"].update(
            link["id"],
            {"expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()},
        )

        self.assertEqual(self.client.get(f"/d/{expired['token']}").status_code, 404)
        self.assertEqual(self.client.get(f"/d/{expired['token']}/preview/thumbnail:photo-1").status_code, 404)

        new_link = self.app.extensions["dispatch"]["delivery_link_service"].regenerate_for_shipment(shipment["id"])
        self.app.extensions["dispatch"]["delivery_link_service"].revoke_for_shipment(shipment["id"])
        self.assertEqual(self.client.get(f"/d/{new_link['token']}").status_code, 404)
        self.assertEqual(self.client.get(f"/d/{new_link['token']}/preview/thumbnail:photo-1").status_code, 404)

    def test_download_link_email_sends_only_link_and_marks_sent(self):
        channel = self.create_smtp_channel()
        sent_payload = {}

        class FakeSMTPTransport:
            def send_link(self, *, channel, shipment, download_url):
                sent_payload["channel"] = channel
                sent_payload["shipment"] = shipment
                sent_payload["download_url"] = download_url
                return {"recipients": ["desk@example.com"], "subject": "Cobertura"}

        self.app.extensions["dispatch"]["smtp_transport"] = FakeSMTPTransport()

        response = self.client.post(
            "/dispatch/new",
            data=self.valid_form(
                delivery_method="download_link_email",
                channel="Correo (SMTP)",
                channel_id=channel["id"],
            ),
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        shipment = self.app.extensions["dispatch"]["shipment_service"].list_shipments()[0]
        link = self.app.extensions["dispatch"]["delivery_link_service"].get_active_for_shipment(shipment["id"])
        self.assertIsNotNone(link)
        self.assertEqual(shipment["status"], "Enviado")
        self.assertTrue(shipment["sent_at"])
        self.assertEqual(sent_payload["channel"]["id"], channel["id"])
        self.assertEqual(sent_payload["shipment"]["id"], shipment["id"])
        self.assertEqual(sent_payload["download_url"], link["url"])

    def test_download_link_email_error_preserves_link_without_lens_mutation(self):
        channel = self.create_smtp_channel()
        original_coverage = json.loads(json.dumps(self.app.extensions["lens"]["coverage_store"].get("cov-1")))

        class FailingSMTPTransport:
            def send_link(self, *, channel, shipment, download_url):
                raise SMTPTransportError("SMTP rechazado.")

        self.app.extensions["dispatch"]["smtp_transport"] = FailingSMTPTransport()

        response = self.client.post(
            "/dispatch/new",
            data=self.valid_form(
                delivery_method="download_link_email",
                channel="Correo (SMTP)",
                channel_id=channel["id"],
            ),
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        shipment = self.app.extensions["dispatch"]["shipment_service"].list_shipments()[0]
        link = self.app.extensions["dispatch"]["delivery_link_service"].get_active_for_shipment(shipment["id"])
        self.assertIsNotNone(link)
        self.assertEqual(shipment["status"], "Error")
        self.assertEqual(shipment["last_error"], "SMTP rechazado.")
        detail = self.client.get(f"/dispatch/{shipment['id']}").get_data(as_text=True)
        self.assertIn("Enlace generado correctamente; el correo no pudo enviarse.", detail)
        self.assertEqual(self.app.extensions["lens"]["coverage_store"].get("cov-1"), original_coverage)


    def test_public_landing_shows_delivery_size_label_without_duplicating_zip(self):
        shipment, link = self.create_ready_link_shipment()

        manifest = self.app.extensions["dispatch"]["delivery_package_service"].load_manifest(shipment["id"])
        files_size = sum(item["size"] for item in manifest["files"])
        self.assertEqual(manifest["total_bytes"], files_size)

        body = self.client.get(f"/d/{link['token']}").get_data(as_text=True)
        self.assertIn("Tamaño de la entrega", body)
        self.assertNotIn("Tamaño total", body)

    def test_dispatch_detail_shows_copy_link_and_delivery_metrics(self):
        shipment, link = self.create_ready_link_shipment()

        body = self.client.get(f"/dispatch/{shipment['id']}").get_data(as_text=True)

        self.assertIn("Copiar enlace", body)
        self.assertIn("data-copy-link-button", body)
        self.assertIn("Tamaño de la entrega", body)
        self.assertIn("ACTIVO", body)
        self.assertIn(f'href="/coverages/{shipment["coverage_id"]}"', body)
        self.assertIn("Volver a cobertura", body)

    def test_dispatch_detail_hides_back_to_coverage_for_historical_shipment_without_coverage_id(self):
        shipment, _link = self.create_ready_link_shipment()
        legacy_shipment = copy.deepcopy(shipment)
        legacy_shipment.pop("coverage_id", None)
        self.app.extensions["dispatch"]["store"].update(shipment["id"], legacy_shipment)

        response = self.client.get(f"/dispatch/{shipment['id']}")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Volver a cobertura", body)
        self.assertIn("Sin descargas", body)


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
