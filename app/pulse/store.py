from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import fcntl
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from app.pulse.models import PulseStoreError, empty_pulse_payload, normalize_payload


class PulseStore:
    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path)
        self.lock_path = self.path.with_name(f"{self.path.name}.lock")

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

    def load(self) -> dict[str, Any]:
        with self._locked(shared=True):
            return self._load_unlocked()

    def _load_unlocked(self) -> dict[str, Any]:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return empty_pulse_payload()
        try:
            with self.path.open("r", encoding="utf-8") as source:
                payload = json.load(source)
        except json.JSONDecodeError as error:
            raise PulseStoreError(f"El archivo de PULSE contiene JSON inválido: {self.path}") from error
        return normalize_payload(payload)

    def save(self, payload: dict[str, Any]) -> None:
        normalized = normalize_payload(payload)
        with self._locked(shared=False):
            self._save_unlocked(normalized)

    def _save_unlocked(self, payload: dict[str, Any]) -> None:
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

    def snapshot(self) -> dict[str, Any]:
        return deepcopy(self.load())

    def upsert_event(self, event: dict[str, Any]) -> dict[str, Any]:
        normalized = normalize_payload({"events": {event.get("id", ""): event}})["events"].popitem()[1]
        with self._locked(shared=False):
            payload = self._load_unlocked()
            payload["events"][normalized["id"]] = normalized
            self._save_unlocked(payload)
        return deepcopy(normalized)

    def mutate_event(self, event_id: str, callback) -> dict[str, Any] | None:
        with self._locked(shared=False):
            payload = self._load_unlocked()
            event = payload["events"].get(event_id)
            if event is None:
                return None
            updated = callback(deepcopy(event))
            if updated is None:
                return None
            payload["events"][event_id] = normalize_payload({"events": {event_id: updated}})["events"][event_id]
            self._save_unlocked(payload)
            return deepcopy(payload["events"][event_id])
