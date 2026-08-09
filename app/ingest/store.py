from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import fcntl
import json
import os
from pathlib import Path
import tempfile
from typing import Any


class IngestStoreError(ValueError):
    pass


class IngestStore:
    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path)
        self.lock_path = self.path.with_name(f"{self.path.name}.lock")

    def load(self) -> dict[str, list[dict[str, Any]]]:
        with self._locked(shared=True):
            return self._load_unlocked()

    def _load_unlocked(self) -> dict[str, list[dict[str, Any]]]:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return {"sessions": [], "photos": []}
        try:
            with self.path.open("r", encoding="utf-8") as source:
                payload = json.load(source)
        except json.JSONDecodeError as error:
            raise IngestStoreError(f"El archivo de INGEST contiene JSON inválido: {self.path}") from error
        if not isinstance(payload, dict):
            raise IngestStoreError(f"El archivo de INGEST tiene estructura inválida: {self.path}")
        sessions = payload.get("sessions", [])
        photos = payload.get("photos", [])
        if not isinstance(sessions, list) or not isinstance(photos, list):
            raise IngestStoreError(f"El archivo de INGEST tiene estructura inválida: {self.path}")
        return {
            "sessions": [deepcopy(item) for item in sessions if isinstance(item, dict)],
            "photos": [deepcopy(item) for item in photos if isinstance(item, dict)],
        }

    def save(self, payload: dict[str, list[dict[str, Any]]]) -> None:
        with self._locked(shared=False):
            self._save_unlocked(payload)

    def _save_unlocked(self, payload: dict[str, list[dict[str, Any]]]) -> None:
        if not isinstance(payload, dict) or not isinstance(payload.get("sessions"), list) or not isinstance(payload.get("photos"), list):
            raise IngestStoreError("No se puede guardar una estructura de INGEST inválida.")
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

    def mutate(self, callback):
        with self._locked(shared=False):
            payload = self._load_unlocked()
            result = callback(payload)
            self._save_unlocked(payload)
            return deepcopy(result)

    def list_sessions(self) -> list[dict[str, Any]]:
        return deepcopy(self.load()["sessions"])

    def list_photos(self) -> list[dict[str, Any]]:
        return deepcopy(self.load()["photos"])
