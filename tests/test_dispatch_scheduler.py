import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from app.dispatch import (
    DispatchScheduler,
    DispatchTransitionError,
    DispatchShipmentStore,
)


class DispatchSchedulerTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = DispatchShipmentStore(Path(self.temp_dir.name) / "dispatch_shipments.json")
        self.scheduler = DispatchScheduler(self.store)
        self.guayaquil = ZoneInfo("America/Guayaquil")

    def tearDown(self):
        self.temp_dir.cleanup()

    def shipment(self, shipment_id="ship-1", **overrides):
        scheduled_at = datetime(2026, 8, 4, 9, 45, tzinfo=self.guayaquil).isoformat()
        shipment = {
            "id": shipment_id,
            "name": shipment_id,
            "coverage_id": "cov-1",
            "photo_ids": ["photo-1"],
            "photo_snapshots": [],
            "coverage_snapshot": {},
            "recipients": [{"name": "Mesa", "email": "desk@example.com"}],
            "delivery_note": "",
            "channel": "Manual",
            "status": "Programado",
            "scheduled_at": scheduled_at,
            "timezone": "America/Guayaquil",
            "sent_at": "",
            "last_attempt_at": "",
            "attempt_count": 0,
            "last_error": "",
            "created_at": "2026-08-03T10:00:00+00:00",
            "updated_at": "2026-08-03T10:00:00+00:00",
            "history": [],
        }
        shipment.update(overrides)
        return shipment

    def test_lists_due_shipment_when_scheduled_at_equals_now(self):
        now = datetime(2026, 8, 4, 9, 45, tzinfo=self.guayaquil)
        self.store.create(self.shipment(scheduled_at=now.isoformat()))

        due = self.scheduler.list_due_shipments(now)

        self.assertEqual([shipment["id"] for shipment in due], ["ship-1"])

    def test_lists_due_shipment_with_minus_five_offset(self):
        now = datetime(2026, 8, 4, 9, 45, tzinfo=self.guayaquil)
        self.store.create(self.shipment(scheduled_at="2026-08-04T09:45:00-05:00"))

        due = self.scheduler.list_due_shipments(now)

        self.assertEqual(due[0]["scheduled_at"], "2026-08-04T09:45:00-05:00")

    def test_lists_due_shipment_with_equivalent_utc_timestamp(self):
        now = datetime(2026, 8, 4, 9, 45, tzinfo=self.guayaquil)
        self.store.create(self.shipment(scheduled_at="2026-08-04T14:45:00+00:00"))

        due = self.scheduler.list_due_shipments(now)

        self.assertEqual(len(due), 1)

    def test_future_shipment_is_not_due(self):
        now = datetime(2026, 8, 4, 9, 45, tzinfo=self.guayaquil)
        future = now + timedelta(minutes=1)
        self.store.create(self.shipment(scheduled_at=future.isoformat()))

        self.assertEqual(self.scheduler.list_due_shipments(now), [])

    def test_programmed_shipment_without_scheduled_at_is_ignored_and_reported(self):
        now = datetime(2026, 8, 4, 9, 45, tzinfo=self.guayaquil)
        self.store.create(self.shipment(scheduled_at=""))

        due = self.scheduler.list_due_shipments(now)

        self.assertEqual(due, [])
        self.assertEqual(self.scheduler.invalid_shipments[0]["id"], "ship-1")

    def test_cancelled_due_shipment_is_not_due(self):
        now = datetime(2026, 8, 4, 9, 45, tzinfo=self.guayaquil)
        self.store.create(self.shipment(status="Cancelado", scheduled_at=now.isoformat()))

        self.assertEqual(self.scheduler.list_due_shipments(now), [])

    def test_claim_for_execution_updates_attempt_once(self):
        now = datetime(2026, 8, 4, 9, 45, tzinfo=self.guayaquil)
        self.store.create(self.shipment(scheduled_at=now.isoformat()))

        claimed = self.scheduler.claim_for_execution("ship-1", now)

        self.assertEqual(claimed["status"], "Enviando")
        self.assertEqual(claimed["attempt_count"], 1)
        self.assertTrue(claimed["last_attempt_at"])

    def test_two_threads_can_claim_only_once(self):
        now = datetime(2026, 8, 4, 9, 45, tzinfo=self.guayaquil)
        self.store.create(self.shipment(scheduled_at=now.isoformat()))
        start = threading.Barrier(3)
        results = []

        def claim():
            start.wait(timeout=2)
            results.append(self.scheduler.claim_for_execution("ship-1", now))

        threads = [threading.Thread(target=claim) for _ in range(2)]
        for thread in threads:
            thread.start()
        start.wait(timeout=2)
        for thread in threads:
            thread.join(timeout=2)

        self.assertEqual(len([result for result in results if result is not None]), 1)
        self.assertEqual(self.store.get("ship-1")["attempt_count"], 1)

    def test_mark_attempt_does_not_increment_attempt_count(self):
        now = datetime(2026, 8, 4, 9, 45, tzinfo=self.guayaquil)
        self.store.create(self.shipment(scheduled_at=now.isoformat()))
        self.scheduler.claim_for_execution("ship-1", now)

        attempted = self.scheduler.mark_attempt("ship-1", "Reintento manual registrado.")

        self.assertEqual(attempted["attempt_count"], 1)
        self.assertEqual(attempted["last_error"], "Reintento manual registrado.")

    def test_mark_sent_requires_sending_state(self):
        self.store.create(self.shipment(status="Programado"))

        with self.assertRaises(DispatchTransitionError):
            self.scheduler.mark_sent("ship-1")

    def test_mark_sent_sets_sent_at_and_clears_error(self):
        now = datetime(2026, 8, 4, 9, 45, tzinfo=self.guayaquil)
        self.store.create(self.shipment(scheduled_at=now.isoformat(), last_error="Error anterior"))
        self.scheduler.claim_for_execution("ship-1", now)

        sent = self.scheduler.mark_sent("ship-1")

        self.assertEqual(sent["status"], "Enviado")
        self.assertTrue(sent["sent_at"])
        self.assertEqual(sent["last_error"], "")

    def test_mark_error_preserves_attempt_count(self):
        now = datetime(2026, 8, 4, 9, 45, tzinfo=self.guayaquil)
        self.store.create(self.shipment(scheduled_at=now.isoformat()))
        claimed = self.scheduler.claim_for_execution("ship-1", now)

        failed = self.scheduler.mark_error("ship-1", "")

        self.assertEqual(failed["status"], "Error")
        self.assertEqual(failed["attempt_count"], claimed["attempt_count"])
        self.assertEqual(failed["last_error"], "Error de despacho sin detalle adicional.")

    def test_cancel_schedule(self):
        self.store.create(self.shipment())

        cancelled = self.scheduler.cancel_schedule("ship-1")

        self.assertEqual(cancelled["status"], "Cancelado")

    def test_legacy_json_without_new_fields_is_compatible(self):
        self.store.save({
            "shipments": [
                {
                    "id": "ship-old",
                    "name": "Antiguo",
                    "status": "Borrador",
                    "created_at": "2026-08-03T10:00:00+00:00",
                    "updated_at": "2026-08-03T10:00:00+00:00",
                }
            ]
        })

        shipment = self.store.get("ship-old")

        self.assertEqual(shipment["scheduled_at"], "")
        self.assertEqual(shipment["timezone"], "America/Guayaquil")
        self.assertEqual(shipment["attempt_count"], 0)

    def test_timezone_guayaquil_is_preserved(self):
        self.store.create(self.shipment(timezone="America/Guayaquil"))

        self.assertEqual(self.store.get("ship-1")["timezone"], "America/Guayaquil")


if __name__ == "__main__":
    unittest.main()
