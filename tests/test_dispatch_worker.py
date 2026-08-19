import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app.dispatch import DispatchShipmentStore
from app.dispatch_worker import main
from app.dispatch.smtp_transport import SMTPTransportError
from app.lens import LensCoverageStore
from app.settings import OutboundChannelDraft, SettingsService, SettingsStore


class DispatchWorkerTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.store_path = self.root / "dispatch_shipments.json"
        self.settings_path = self.root / "settings.json"
        self.links_path = self.root / "links.json"
        self.lens_path = self.root / "lens.json"
        self.media_root = self.root / "media"
        self.delivery_root = self.root / "deliveries"
        self.guayaquil = ZoneInfo("America/Guayaquil")

    def tearDown(self):
        self.temp_dir.cleanup()

    def shipment(self, shipment_id="ship-1", **overrides):
        shipment = {
            "id": shipment_id,
            "name": shipment_id,
            "status": "Programado",
            "scheduled_at": "2000-01-01T09:00:00-05:00",
            "timezone": "America/Guayaquil",
            "channel": "Manual",
            "recipients": [{"name": "Mesa", "email": "desk@example.com"}],
            "photo_ids": ["photo-1", "photo-2"],
            "attempt_count": 0,
            "last_attempt_at": "",
            "last_error": "",
            "created_at": "2000-01-01T08:00:00-05:00",
            "updated_at": "2000-01-01T08:00:00-05:00",
            "history": [],
        }
        shipment.update(overrides)
        return shipment

    def write_store(self, shipments):
        self.store_path.write_text(
            json.dumps({"shipments": shipments}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def run_worker(self, *args):
        stdout = io.StringIO()
        stderr = io.StringIO()
        exit_code = main([*args, "--store-path", str(self.store_path)], out=stdout, err=stderr)
        return exit_code, stdout.getvalue(), stderr.getvalue()

    def run_cleanup_worker(self, *args, delivery_root, links_store):
        stdout = io.StringIO()
        stderr = io.StringIO()
        exit_code = main(
            [
                *args,
                "--store-path",
                str(self.store_path),
                "--delivery-root",
                str(delivery_root),
                "--links-store-path",
                str(links_store),
            ],
            out=stdout,
            err=stderr,
        )
        return exit_code, stdout.getvalue(), stderr.getvalue()

    def process_patches(self):
        return [
            patch("app.config.DISPATCH_STORE_PATH", str(self.store_path)),
            patch("app.config.SETTINGS_STORE_PATH", str(self.settings_path)),
            patch("app.config.DELIVERY_LINKS_STORE_PATH", str(self.links_path)),
            patch("app.config.LENS_COVERAGE_STORE_PATH", str(self.lens_path)),
            patch("app.config.LENS_MEDIA_ROOT", str(self.media_root)),
            patch("app.config.DELIVERY_ROOT", str(self.delivery_root)),
            patch("app.config.PUBLIC_BASE_URL", "https://atlas.example"),
        ]

    def write_lens_and_settings(self):
        photo_path = self.media_root / "coverages" / "cov-1" / "photo-1_IMG001.jpg"
        photo_path.parent.mkdir(parents=True)
        photo_path.write_bytes(b"jpeg-one")
        coverage_store = LensCoverageStore(self.lens_path, self.media_root)
        coverage_store.set("cov-1", {
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
        })
        SettingsService(SettingsStore(self.settings_path)).create_outbound_channel(
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

    def test_dry_run_without_shipments(self):
        exit_code, stdout, stderr = self.run_worker("--dry-run")

        self.assertEqual(exit_code, 0)
        self.assertIn("No hay despachos vencidos", stdout)
        self.assertIn("revisados=0 vencidos=0 futuros=0 inválidos=0", stdout)
        self.assertEqual(stderr, "")

    def test_dry_run_with_future_shipment(self):
        self.write_store([self.shipment(scheduled_at="2099-01-01T09:00:00-05:00")])

        exit_code, stdout, _ = self.run_worker("--dry-run")

        self.assertEqual(exit_code, 0)
        self.assertIn("vencidos=0", stdout)
        self.assertIn("futuros=1", stdout)

    def test_dry_run_with_due_shipment(self):
        self.write_store([self.shipment(name="Despacho vencido")])

        exit_code, stdout, _ = self.run_worker("--dry-run")

        self.assertEqual(exit_code, 0)
        self.assertIn("Despachos vencidos", stdout)
        self.assertIn("ID: ship-1", stdout)
        self.assertIn("nombre: Despacho vencido", stdout)
        self.assertIn("destinatarios: 1", stdout)
        self.assertIn("fotografías: 2", stdout)

    def test_dry_run_does_not_modify_json(self):
        self.write_store([self.shipment()])
        before = self.store_path.read_text(encoding="utf-8")

        exit_code, _, _ = self.run_worker("--dry-run")

        self.assertEqual(exit_code, 0)
        self.assertEqual(self.store_path.read_text(encoding="utf-8"), before)

    def test_invalid_shipment_does_not_stop_others(self):
        self.write_store([
            self.shipment("ship-invalid", scheduled_at="not-a-date"),
            self.shipment("ship-due"),
        ])

        exit_code, stdout, _ = self.run_worker("--dry-run")

        self.assertEqual(exit_code, 0)
        self.assertIn("ID: ship-due", stdout)
        self.assertIn("ID: ship-invalid | error: scheduled_at inválido.", stdout)
        self.assertIn("inválidos=1", stdout)

    def test_claim_changes_due_shipment_to_sending(self):
        self.write_store([self.shipment()])

        exit_code, stdout, _ = self.run_worker("--claim")

        self.assertEqual(exit_code, 0)
        self.assertIn("RECLAMADO: ship-1", stdout)
        shipment = DispatchShipmentStore(self.store_path).get("ship-1")
        self.assertEqual(shipment["status"], "Enviando")
        self.assertEqual(shipment["attempt_count"], 1)

    def test_claim_does_not_duplicate_execution(self):
        self.write_store([self.shipment()])

        first_code, first_stdout, _ = self.run_worker("--claim")
        second_code, second_stdout, _ = self.run_worker("--claim")

        self.assertEqual(first_code, 0)
        self.assertEqual(second_code, 0)
        self.assertIn("RECLAMADO: ship-1", first_stdout)
        self.assertIn("No hay despachos vencidos", second_stdout)
        shipment = DispatchShipmentStore(self.store_path).get("ship-1")
        self.assertEqual(shipment["attempt_count"], 1)

    def test_missing_store_returns_success(self):
        exit_code, stdout, stderr = self.run_worker("--dry-run")

        self.assertEqual(exit_code, 0)
        self.assertIn("revisados=0", stdout)
        self.assertEqual(stderr, "")

    def test_invalid_json_returns_error_code(self):
        self.store_path.write_text("{invalid", encoding="utf-8")

        exit_code, stdout, stderr = self.run_worker("--dry-run")

        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("JSON inválido", stderr)

    def test_claim_exit_code_success(self):
        self.write_store([self.shipment(scheduled_at="2099-01-01T09:00:00-05:00")])

        exit_code, stdout, stderr = self.run_worker("--claim")

        self.assertEqual(exit_code, 0)
        self.assertIn("No hay despachos vencidos", stdout)
        self.assertEqual(stderr, "")

    def test_cleanup_deliveries_dry_run_does_not_delete_candidate(self):
        delivery_root = Path(self.temp_dir.name) / "deliveries"
        candidate = delivery_root / "ship-old"
        candidate.mkdir(parents=True)
        (candidate / "package.zip").write_bytes(b"zip")
        links_store = Path(self.temp_dir.name) / "links.json"

        exit_code, stdout, stderr = self.run_cleanup_worker(
            "--cleanup-deliveries",
            "--dry-run",
            delivery_root=delivery_root,
            links_store=links_store,
        )

        self.assertEqual(exit_code, 0)
        self.assertTrue(candidate.exists())
        self.assertIn("DRY-RUN", stdout)
        self.assertEqual(stderr, "")

    def test_cleanup_deliveries_removes_only_packages_without_active_link(self):
        delivery_root = Path(self.temp_dir.name) / "deliveries"
        stale = delivery_root / "ship-stale"
        active = delivery_root / "ship-active"
        stale.mkdir(parents=True)
        active.mkdir(parents=True)
        links_store = Path(self.temp_dir.name) / "links.json"
        links_store.write_text(
            json.dumps({
                "links": [{
                    "id": "link-1",
                    "shipment_id": "ship-active",
                    "token": "secure-token",
                    "created_at": "2026-08-07T00:00:00+00:00",
                    "expires_at": "",
                    "revoked_at": "",
                    "download_count": 0,
                    "last_download_at": "",
                    "password_hash": "",
                    "is_active": True,
                }]
            }),
            encoding="utf-8",
        )

        exit_code, stdout, stderr = self.run_cleanup_worker(
            "--cleanup-deliveries",
            delivery_root=delivery_root,
            links_store=links_store,
        )

        self.assertEqual(exit_code, 0)
        self.assertFalse(stale.exists())
        self.assertTrue(active.exists())
        self.assertIn("ELIMINADO", stdout)
        self.assertEqual(stderr, "")

    def test_process_due_dry_run_does_not_mutate_or_send(self):
        self.write_store([
            self.shipment(
                coverage_id="cov-1",
                photo_ids=["photo-1"],
                delivery_method="download_link_email",
                channel_id="xinhua-smtp",
                channel_name_snapshot="Xinhua SMTP",
                include_caption_docx=False,
            )
        ])
        self.write_lens_and_settings()
        before = self.store_path.read_text(encoding="utf-8")
        patches = self.process_patches()
        for item in patches:
            item.start()
        try:
            with patch("app.dispatch.smtp_transport.SMTPLinkTransport.send_link") as send_link:
                exit_code, stdout, stderr = self.run_worker("--process-due", "--dry-run")
        finally:
            for item in reversed(patches):
                item.stop()

        self.assertEqual(exit_code, 0)
        self.assertIn("Modo dry-run", stdout)
        self.assertEqual(stderr, "")
        self.assertFalse(send_link.called)
        self.assertEqual(self.store_path.read_text(encoding="utf-8"), before)

    def test_process_due_download_link_email_generates_link_and_sends(self):
        self.write_store([
            self.shipment(
                coverage_id="cov-1",
                photo_ids=["photo-1"],
                delivery_method="download_link_email",
                channel_id="xinhua-smtp",
                channel_name_snapshot="Xinhua SMTP",
                include_caption_docx=False,
            )
        ])
        self.write_lens_and_settings()
        patches = self.process_patches()
        for item in patches:
            item.start()
        try:
            with patch("app.dispatch.smtp_transport.SMTPLinkTransport.send_link") as send_link:
                exit_code, stdout, stderr = self.run_worker("--process-due")
        finally:
            for item in reversed(patches):
                item.stop()

        self.assertEqual(exit_code, 0)
        self.assertIn("PROCESADO: ship-1", stdout)
        self.assertEqual(stderr, "")
        self.assertTrue(send_link.called)
        shipment = DispatchShipmentStore(self.store_path).get("ship-1")
        self.assertEqual(shipment["status"], "Enviado")
        self.assertTrue(shipment["delivery_link_id"])
        link_store = json.loads(self.links_path.read_text(encoding="utf-8"))
        self.assertEqual(len(link_store["links"]), 1)
        self.assertTrue(send_link.call_args.kwargs["download_url"].startswith("https://atlas.example/d/"))

    def test_process_due_module_path_is_app_dispatch_worker(self):
        from app.dispatch.worker import main as package_main

        self.assertIs(package_main, main)

    def test_process_due_failure_transitions_to_error_without_stopping(self):
        self.write_store([
            self.shipment(
                "ship-fail",
                coverage_id="cov-1",
                photo_ids=["photo-1"],
                delivery_method="download_link_email",
                channel_id="xinhua-smtp",
                channel_name_snapshot="Xinhua SMTP",
                include_caption_docx=False,
            ),
            self.shipment(
                "ship-ok",
                coverage_id="cov-1",
                photo_ids=["photo-1"],
                delivery_method="download_link_email",
                channel_id="xinhua-smtp",
                channel_name_snapshot="Xinhua SMTP",
                include_caption_docx=False,
            ),
        ])
        self.write_lens_and_settings()
        patches = self.process_patches()
        for item in patches:
            item.start()
        try:
            with patch("app.dispatch.smtp_transport.SMTPLinkTransport.send_link") as send_link:
                send_link.side_effect = [SMTPTransportError("SMTP rechazado."), {"recipients": ["desk@example.com"], "subject": "Cobertura"}]
                exit_code, stdout, stderr = self.run_worker("--process-due")
        finally:
            for item in reversed(patches):
                item.stop()

        self.assertEqual(exit_code, 0)
        self.assertIn("ERROR: ship-fail", stdout)
        self.assertIn("PROCESADO: ship-ok", stdout)
        self.assertEqual(stderr, "")
        store = DispatchShipmentStore(self.store_path)
        failed_shipment = store.get("ship-fail")
        ok_shipment = store.get("ship-ok")
        self.assertEqual(failed_shipment["status"], "Error")
        self.assertEqual(failed_shipment["last_error"], "SMTP rechazado.")
        self.assertEqual(ok_shipment["status"], "Enviado")

    def test_process_due_does_not_send_twice_on_repeated_runs(self):
        self.write_store([
            self.shipment(
                coverage_id="cov-1",
                photo_ids=["photo-1"],
                delivery_method="download_link_email",
                channel_id="xinhua-smtp",
                channel_name_snapshot="Xinhua SMTP",
                include_caption_docx=False,
            )
        ])
        self.write_lens_and_settings()
        patches = self.process_patches()
        for item in patches:
            item.start()
        try:
            with patch("app.dispatch.smtp_transport.SMTPLinkTransport.send_link") as send_link:
                first_code, first_stdout, _ = self.run_worker("--process-due")
                second_code, second_stdout, _ = self.run_worker("--process-due")
        finally:
            for item in reversed(patches):
                item.stop()

        self.assertEqual(first_code, 0)
        self.assertEqual(second_code, 0)
        self.assertIn("PROCESADO: ship-1", first_stdout)
        self.assertIn("No hay despachos vencidos para procesar.", second_stdout)
        self.assertEqual(send_link.call_count, 1)
        shipment = DispatchShipmentStore(self.store_path).get("ship-1")
        self.assertEqual(shipment["status"], "Enviado")

    def test_process_due_processes_multiple_due_shipments(self):
        self.write_store([
            self.shipment(
                "ship-a",
                coverage_id="cov-1",
                photo_ids=["photo-1"],
                delivery_method="download_link_email",
                channel_id="xinhua-smtp",
                channel_name_snapshot="Xinhua SMTP",
                include_caption_docx=False,
            ),
            self.shipment(
                "ship-b",
                coverage_id="cov-1",
                photo_ids=["photo-1"],
                delivery_method="download_link_email",
                channel_id="xinhua-smtp",
                channel_name_snapshot="Xinhua SMTP",
                include_caption_docx=False,
            ),
        ])
        self.write_lens_and_settings()
        patches = self.process_patches()
        for item in patches:
            item.start()
        try:
            with patch("app.dispatch.smtp_transport.SMTPLinkTransport.send_link") as send_link:
                exit_code, stdout, stderr = self.run_worker("--process-due")
        finally:
            for item in reversed(patches):
                item.stop()

        self.assertEqual(exit_code, 0)
        self.assertEqual(send_link.call_count, 2)
        self.assertIn("procesados=2", stdout)
        store = DispatchShipmentStore(self.store_path)
        self.assertEqual(store.get("ship-a")["status"], "Enviado")
        self.assertEqual(store.get("ship-b")["status"], "Enviado")

    def test_process_due_uses_guayaquil_offset_for_due_comparison(self):
        past_local = datetime.now(self.guayaquil) - timedelta(minutes=1)
        self.write_store([self.shipment(scheduled_at=past_local.isoformat(), timezone="America/Guayaquil")])

        exit_code, stdout, _ = self.run_worker("--dry-run")

        self.assertEqual(exit_code, 0)
        self.assertIn("vencidos=1", stdout)


if __name__ == "__main__":
    unittest.main()
