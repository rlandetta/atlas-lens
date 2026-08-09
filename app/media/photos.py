from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import base64
import logging
import os
from pathlib import Path
from typing import Iterable, Mapping, Any

LOGGER = logging.getLogger(__name__)
THUMBNAIL_MAX_SIDE = 640
THUMBNAIL_QUALITY = 70
PLACEHOLDER_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEAAQABAAD/2wBDAAMCAgICAgMCAgIDAwMDBAYEBAQEBAgGBgUGCQgKCgkICQkKDA8MCgsOCwkJDRENDg8QEBEQCgwSExIQEw8QEBD/2wBDAQMDAwQDBAgEBAgQCwkLEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBD/wAARCAASACADAREAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAn/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFgEBAQEAAAAAAAAAAAAAAAAAAAYH/8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAwDAQACEQMRAD8AnE1hLgAAAAAAAAAAP//Z"
)


class PhotoSourceError(ValueError):
    pass


def _existing_regular_file(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()


def _matching_ingest_photo(photo: Mapping[str, Any], ingest_photos: Iterable[Mapping[str, Any]] | None) -> bool:
    flow_path = str(photo.get("flow_path") or photo.get("path") or "")
    flow_photo_id = str(photo.get("flow_photo_id") or photo.get("id") or "")
    flow_session_id = str(photo.get("flow_session_id") or photo.get("session_id") or "")
    if not flow_path or ingest_photos is None:
        return False
    for ingest_photo in ingest_photos:
        if str(ingest_photo.get("path", "")) != flow_path:
            continue
        if flow_photo_id and str(ingest_photo.get("id", "")) != flow_photo_id:
            continue
        if flow_session_id and str(ingest_photo.get("session_id", "")) != flow_session_id:
            continue
        return True
    return False


def resolve_photo_source(
    photo: Mapping[str, Any],
    *,
    coverage_store=None,
    ingest_photos: Iterable[Mapping[str, Any]] | None = None,
) -> Path | None:
    storage_path = str(photo.get("storage_path", "")).strip()
    if storage_path and coverage_store is not None and coverage_store.is_stored_file_available(storage_path):
        candidate = coverage_store.resolve_storage_path(storage_path)
        if candidate is not None and _existing_regular_file(candidate):
            return candidate

    flow_path = str(photo.get("flow_path") or photo.get("path") or "").strip()
    if not flow_path:
        return None
    candidate = Path(flow_path)
    if not candidate.is_absolute() or not _existing_regular_file(candidate):
        return None
    if ingest_photos is not None and not _matching_ingest_photo(photo, ingest_photos):
        return None
    return candidate


def _safe_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def _flow_filename(photo: Mapping[str, Any]) -> str:
    return str(
        Path(str(photo.get("flow_path") or photo.get("path") or "")).name
        or photo.get("filename")
        or photo.get("name")
        or ""
    ).strip()


def _flow_source(photo: Mapping[str, Any]) -> str:
    return str(photo.get("source") or photo.get("camera") or "").strip()


def _flow_received_date_parts(photo: Mapping[str, Any]) -> tuple[str, str, str] | None:
    raw_value = str(photo.get("received_at") or photo.get("created_at") or "").strip()
    if not raw_value:
        return None
    try:
        value = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (f"{value.year:04}", f"{value.month:02}", f"{value.day:02}")


def _candidate_matches_metadata(candidate: Path, photo: Mapping[str, Any]) -> bool:
    parts = set(candidate.parts)
    source = _flow_source(photo)
    if source and source not in parts:
        return False
    date_parts = _flow_received_date_parts(photo)
    if date_parts and not all(part in candidate.parts for part in date_parts):
        return False
    return True


def resolve_legacy_flow_photo_source(
    photo: Mapping[str, Any],
    *,
    events_root: str | os.PathLike[str],
) -> Path | None:
    flow_path = str(photo.get("flow_path") or photo.get("path") or "").strip()
    if not flow_path:
        return None
    original = Path(flow_path)
    if original.is_absolute() and _existing_regular_file(original):
        return original

    filename = _flow_filename(photo)
    if not filename:
        return None
    root = Path(events_root)
    if not root.is_dir() or root.is_symlink():
        return None

    matches: list[Path] = []
    try:
        candidates = root.rglob(filename)
        for candidate in candidates:
            if not _existing_regular_file(candidate):
                continue
            if not _safe_relative_to(candidate, root):
                continue
            if not _candidate_matches_metadata(candidate, photo):
                continue
            matches.append(candidate.resolve())
    except OSError as error:
        LOGGER.warning("No se pudo buscar flow_path legado en events para %s: %s", filename, error)
        return None

    unique_matches = sorted({str(match): match for match in matches}.values(), key=lambda item: str(item))
    if len(unique_matches) == 1:
        return unique_matches[0]
    if len(unique_matches) > 1:
        LOGGER.warning("flow_path legado ambiguo para %s: %s coincidencias en events", filename, len(unique_matches))
    return None


class ThumbnailService:
    def __init__(self, root: str | os.PathLike[str], *, base_path: str | os.PathLike[str] | None = None):
        root_path = Path(root).expanduser()
        if not root_path.is_absolute():
            root_path = Path(base_path or os.getcwd()) / root_path
        self.root = root_path.resolve()

    def thumbnail_path_for(self, source_path: Path) -> Path | None:
        try:
            stat = source_path.stat()
            resolved = source_path.resolve(strict=True)
        except OSError:
            return None
        digest = sha256(f"{resolved}:{stat.st_mtime_ns}:{stat.st_size}".encode("utf-8")).hexdigest()[:32]
        return self.root / f"photo-{digest}.jpg"

    def ensure_thumbnail(self, source_path: Path) -> Path | None:
        target = self.thumbnail_path_for(source_path)
        if target is None:
            return None
        if target.is_file() and not target.is_symlink():
            return target
        try:
            from PIL import Image, ImageOps

            self.root.mkdir(parents=True, exist_ok=True)
            temp_path = target.with_name(f".{target.name}.tmp")
            with Image.open(source_path) as image:
                image = ImageOps.exif_transpose(image)
                image.thumbnail((THUMBNAIL_MAX_SIDE, THUMBNAIL_MAX_SIDE))
                if image.mode not in ("RGB", "L"):
                    image = image.convert("RGB")
                elif image.mode == "L":
                    image = image.convert("RGB")
                image.save(temp_path, format="JPEG", quality=THUMBNAIL_QUALITY, optimize=True)
            os.replace(temp_path, target)
            return target
        except ModuleNotFoundError as error:
            if error.name != "PIL":
                LOGGER.warning("No se pudo generar miniatura para %s: %s", source_path, error)
                return None
            self.root.mkdir(parents=True, exist_ok=True)
            target.write_bytes(PLACEHOLDER_JPEG)
            return target
        except Exception as error:
            LOGGER.warning("No se pudo generar miniatura para %s: %s", source_path, error)
            try:
                temp_path.unlink()  # type: ignore[name-defined]
            except Exception:
                pass
            return None
