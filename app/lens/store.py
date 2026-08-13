from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any


class LensCoverageStoreError(ValueError):
    pass


class LensCoverageStore:
    def __init__(self, path: str | os.PathLike[str], media_root: str | os.PathLike[str]):
        self.path = Path(path)
        self.media_root = Path(media_root)
        self.lock_path = self.path.with_name(f"{self.path.name}.lock")

    def load(self) -> dict[str, dict[str, Any]]:
        with self._locked(shared=True):
            return self._load_unlocked()

    def _load_unlocked(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        if self.path.stat().st_size == 0:
            return {}

        try:
            with self.path.open("r", encoding="utf-8") as source:
                payload = json.load(source)
        except json.JSONDecodeError as error:
            raise LensCoverageStoreError(
                f"El archivo de coberturas contiene JSON inválido: {self.path}"
            ) from error

        if not isinstance(payload, dict) or not isinstance(payload.get("coverages"), dict):
            raise LensCoverageStoreError(
                f"El archivo de coberturas tiene una estructura inválida: {self.path}"
            )
        return {
            str(coverage_id): self.normalize_coverage(coverage)
            for coverage_id, coverage in payload["coverages"].items()
            if isinstance(coverage, dict)
        }

    def save_all(self, coverages: dict[str, dict[str, Any]]) -> None:
        with self._locked(shared=False):
            self._save_unlocked(coverages)

    def _save_unlocked(self, coverages: dict[str, dict[str, Any]]) -> None:
        if not isinstance(coverages, dict):
            raise LensCoverageStoreError("No se puede guardar una estructura de coberturas inválida.")

        payload = {
            "coverages": {
                str(coverage_id): self.normalize_coverage(coverage)
                for coverage_id, coverage in coverages.items()
                if isinstance(coverage, dict)
            }
        }
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

    def list_coverages(self) -> dict[str, dict[str, Any]]:
        return deepcopy(self.load())

    def get(self, coverage_id: str) -> dict[str, Any] | None:
        return deepcopy(self.load().get(coverage_id))

    def set(self, coverage_id: str, coverage: dict[str, Any]) -> dict[str, Any]:
        with self._locked(shared=False):
            coverages = self._load_unlocked()
            normalized = self.normalize_coverage(coverage)
            coverages[str(coverage_id)] = normalized
            self._save_unlocked(coverages)
        return deepcopy(normalized)

    def delete(self, coverage_id: str) -> None:
        with self._locked(shared=False):
            coverages = self._load_unlocked()
            coverages.pop(str(coverage_id), None)
            self._save_unlocked(coverages)

    def mutate(self, coverage_id: str, callback) -> dict[str, Any] | None:
        with self._locked(shared=False):
            coverages = self._load_unlocked()
            current = coverages.get(str(coverage_id))
            if current is None:
                return None
            next_coverage = callback(deepcopy(current))
            if next_coverage is None:
                return None
            normalized = self.normalize_coverage(next_coverage)
            coverages[str(coverage_id)] = normalized
            self._save_unlocked(coverages)
            return deepcopy(normalized)

    def normalize_coverage(self, coverage: dict[str, Any]) -> dict[str, Any]:
        normalized = deepcopy(coverage)
        photos = normalized.get("photos", [])
        normalized["photos"] = [
            self.normalize_photo(photo)
            for photo in photos
            if isinstance(photo, dict)
        ] if isinstance(photos, list) else []
        return normalized

    def normalize_photo(self, photo: dict[str, Any]) -> dict[str, Any]:
        timestamp = datetime.now(timezone.utc).isoformat()
        filename = str(photo.get("filename") or photo.get("name") or photo.get("id", ""))
        storage_path = self.normalize_storage_path(str(
            photo.get("storage_path") or photo.get("relative_path") or photo.get("file_path") or ""
        ))
        flow_path = str(photo.get("flow_path", "")).strip()
        source = str(photo.get("source") or photo.get("camera") or "")
        available_on_disk = bool(
            photo.get("available_on_disk", True) is not False
            and (
                (
                    storage_path
                    and self.is_stored_file_available(storage_path)
                )
                or (
                    flow_path
                    and Path(flow_path).is_absolute()
                    and Path(flow_path).is_file()
                    and not Path(flow_path).is_symlink()
                )
            )
        )
        return {
            "id": str(photo.get("id", "")),
            "name": filename,
            "filename": filename,
            "storage_path": storage_path,
            "flow_path": flow_path if Path(flow_path).is_absolute() else "",
            "flow_session_id": str(photo.get("flow_session_id", "")),
            "flow_photo_id": str(photo.get("flow_photo_id", "")),
            "source": source,
            "camera": source,
            "size": self.optional_int(photo.get("size")),
            "type": str(photo.get("type", "image/jpeg") or "image/jpeg"),
            "width": self.optional_int(photo.get("width")),
            "height": self.optional_int(photo.get("height")),
            "coverage_name": str(photo.get("coverage_name", "")),
            "photographer": str(photo.get("photographer", "")),
            "event_date": str(photo.get("event_date", "")),
            "received_at": str(photo.get("received_at", "")),
            "captured_at": str(photo.get("captured_at", "")),
            "caption_narrative": str(photo.get("caption_narrative", "")),
            "caption_status": str(photo.get("caption_status", "Sin editar") or "Sin editar"),
            "created_at": str(photo.get("created_at") or timestamp),
            "updated_at": str(photo.get("updated_at") or timestamp),
            "available_on_disk": available_on_disk,
        }

    @staticmethod
    def optional_int(value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def normalize_storage_path(value: str) -> str:
        path = value.strip().replace("\\", "/")
        if not path:
            return ""
        if Path(path).is_absolute() or path.startswith("../") or "/../" in path:
            return ""
        return path

    def resolve_storage_path(self, storage_path: str) -> Path | None:
        normalized = self.normalize_storage_path(storage_path)
        if not normalized:
            return None
        root = self.media_root.resolve()
        candidate = (root / normalized).resolve()
        try:
            if not candidate.is_relative_to(root):
                return None
        except ValueError:
            return None
        return candidate

    def is_stored_file_available(self, storage_path: str) -> bool:
        path = self.resolve_storage_path(storage_path)
        return bool(path and path.is_file() and not path.is_symlink())

    def delete_photo_file(self, storage_path: str) -> bool:
        path = self.resolve_storage_path(storage_path)
        if not path or not path.exists() or not path.is_file() or path.is_symlink():
            return False
        path.unlink()
        return True

    def delete_coverage_media(self, coverage_id: str) -> None:
        safe_id = self.sanitize_path_component(coverage_id)
        if not safe_id:
            return
        root = self.media_root.resolve()
        target = (root / "coverages" / safe_id).resolve()
        try:
            if not target.is_relative_to(root / "coverages"):
                return
        except ValueError:
            return
        if not target.exists() or target.is_symlink() or not target.is_dir():
            return
        shutil.rmtree(target)

    @staticmethod
    def sanitize_path_component(value: str) -> str:
        import re

        sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value).strip())
        sanitized = sanitized.strip(".-")
        if not sanitized or sanitized in {".", ".."}:
            return ""
        return sanitized
