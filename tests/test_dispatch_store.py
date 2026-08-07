import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path

from app.dispatch import DispatchShipmentStore, DispatchStoreError


class DispatchShipmentStoreTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store_path = Path(self.temp_dir.name) / "nested" / "dispatch_shipments.json"
        self.store = DispatchShipmentStore(self.store_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_load_missing_file_returns_empty_shipments(self):
        self.assertEqual(self.store.load(), {"shipments": []})

    def test_load_empty_file_returns_empty_shipments(self):
        self.store_path.parent.mkdir(parents=True)
        self.store_path.write_text("", encoding="utf-8")

        self.assertEqual(self.store.load(), {"shipments": []})

    def test_invalid_json_raises_and_preserves_original(self):
        self.store_path.parent.mkdir(parents=True)
        self.store_path.write_text("{invalid", encoding="utf-8")

        with self.assertRaises(DispatchStoreError):
            self.store.load()

        self.assertEqual(self.store_path.read_text(encoding="utf-8"), "{invalid")

    def test_invalid_structure_raises(self):
        self.store_path.parent.mkdir(parents=True)
        self.store_path.write_text(json.dumps({"items": []}), encoding="utf-8")

        with self.assertRaises(DispatchStoreError):
            self.store.load()

    def test_save_creates_missing_directory_and_writes_atomically(self):
        self.store.save({"shipments": [{"id": "ship-1"}]})

        self.assertTrue(self.store_path.exists())
        self.assertEqual(self.store.load()["shipments"][0]["id"], "ship-1")
        leftovers = list(self.store_path.parent.glob("*.tmp"))
        self.assertEqual(leftovers, [])

    def test_create_read_and_update_shipment(self):
        self.store.create({"id": "ship-1", "name": "Despacho"})

        shipment = self.store.get("ship-1")
        self.assertEqual(shipment["name"], "Despacho")

        updated = {**shipment, "name": "Despacho actualizado"}
        self.store.update("ship-1", updated)

        self.assertEqual(self.store.get("ship-1")["name"], "Despacho actualizado")

    def test_delete_removes_only_requested_shipment(self):
        self.store.create({"id": "ship-1", "name": "Uno"})
        self.store.create({"id": "ship-2", "name": "Dos"})

        removed = self.store.delete("ship-1")

        self.assertEqual(removed["id"], "ship-1")
        self.assertIsNone(self.store.get("ship-1"))
        self.assertEqual(self.store.get("ship-2")["name"], "Dos")

    def test_delete_missing_raises(self):
        with self.assertRaises(DispatchStoreError):
            self.store.delete("missing")

    def test_lock_acquisition_and_release(self):
        acquired = threading.Event()
        release = threading.Event()

        def wait_for_lock():
            with self.store._locked(shared=False):
                acquired.set()
                release.wait(timeout=2)

        with self.store._locked(shared=False):
            thread = threading.Thread(target=wait_for_lock)
            thread.start()
            time.sleep(0.05)
            self.assertFalse(acquired.is_set())

        self.assertTrue(acquired.wait(timeout=2))
        release.set()
        thread.join(timeout=2)
        self.assertFalse(thread.is_alive())

    def test_lock_is_released_after_exception(self):
        with self.assertRaises(RuntimeError):
            with self.store._locked(shared=False):
                raise RuntimeError("boom")

        with self.store._locked(shared=False):
            self.assertTrue(True)

    def test_concurrent_creates_do_not_lose_records(self):
        start = threading.Barrier(3)
        errors = []

        def create_shipment(shipment_id):
            try:
                start.wait(timeout=2)
                self.store.create({"id": shipment_id, "name": shipment_id})
            except Exception as error:
                errors.append(error)

        threads = [
            threading.Thread(target=create_shipment, args=(f"ship-{index}",))
            for index in range(2)
        ]
        for thread in threads:
            thread.start()
        start.wait(timeout=2)
        for thread in threads:
            thread.join(timeout=2)

        self.assertEqual(errors, [])
        self.assertEqual(
            {shipment["id"] for shipment in self.store.list_shipments()},
            {"ship-0", "ship-1"},
        )


if __name__ == "__main__":
    unittest.main()
