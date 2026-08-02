from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

from app.dispatch.models import DispatchStoreError


class DispatchShipmentStore:
    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path)
        self.lock_path = self.path.with_name(f"{self.path.name}.lock")

    def load(self) -> dict[str, list[dict[str, Any]]]:
        with self._locked(shared=True):
            return self._load_unlocked()

    def _load_unlocked(self) -> dict[str, list[dict[str, Any]]]:
        if not self.path.exists():
            return {"shipments": []}
        if self.path.stat().st_size == 0:
            return {"shipments": []}

        try:
            with self.path.open("r", encoding="utf-8") as source:
                payload = json.load(source)
        except json.JSONDecodeError as error:
            raise DispatchStoreError(
                f"El archivo de despachos contiene JSON inválido: {self.path}"
            ) from error

        if not isinstance(payload, dict) or not isinstance(payload.get("shipments"), list):
            raise DispatchStoreError(
                f"El archivo de despachos tiene una estructura inválida: {self.path}"
            )
        return payload

    def save(self, payload: dict[str, list[dict[str, Any]]]) -> None:
        with self._locked(shared=False):
            self._save_unlocked(payload)

    def _save_unlocked(self, payload: dict[str, list[dict[str, Any]]]) -> None:
        if not isinstance(payload, dict) or not isinstance(payload.get("shipments"), list):
            raise DispatchStoreError("No se puede guardar una estructura de despachos inválida.")

        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temp_file:
                temp_path = Path(temp_file.name)
                json.dump(payload, temp_file, ensure_ascii=False, indent=2)
                temp_file.write("\n")
                temp_file.flush()
                os.fsync(temp_file.fileno())
            os.replace(temp_path, self.path)
        except Exception:
            if temp_path and temp_path.exists():
                temp_path.unlink()
            raise

    @contextmanager
    def _locked(self, *, shared: bool):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a", encoding="utf-8") as lock_file:
            operation = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
            fcntl.flock(lock_file.fileno(), operation)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def list_shipments(self) -> list[dict[str, Any]]:
        with self._locked(shared=True):
            return deepcopy(self._load_unlocked()["shipments"])

    def get(self, shipment_id: str) -> dict[str, Any] | None:
        with self._locked(shared=True):
            for shipment in self._load_unlocked()["shipments"]:
                if shipment.get("id") == shipment_id:
                    return deepcopy(shipment)
        return None

    def create(self, shipment: dict[str, Any]) -> dict[str, Any]:
        with self._locked(shared=False):
            payload = self._load_unlocked()
            if any(existing.get("id") == shipment.get("id") for existing in payload["shipments"]):
                raise DispatchStoreError("Ya existe un despacho con ese identificador.")
            payload["shipments"].insert(0, deepcopy(shipment))
            self._save_unlocked(payload)
        return deepcopy(shipment)

    def update(self, shipment_id: str, next_shipment: dict[str, Any]) -> dict[str, Any]:
        with self._locked(shared=False):
            payload = self._load_unlocked()
            for index, shipment in enumerate(payload["shipments"]):
                if shipment.get("id") == shipment_id:
                    payload["shipments"][index] = deepcopy(next_shipment)
                    self._save_unlocked(payload)
                    return deepcopy(next_shipment)
        raise DispatchStoreError("No existe el despacho solicitado.")
