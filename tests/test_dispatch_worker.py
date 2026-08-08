import io
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.dispatch import DispatchShipmentStore
from app.dispatch_worker import main


class DispatchWorkerTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store_path = Path(self.temp_dir.name) / "dispatch_shipments.json"
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


if __name__ == "__main__":
    unittest.main()
