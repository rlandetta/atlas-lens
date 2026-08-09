from __future__ import annotations

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


class ThumbnailService:
    def __init__(self, root: str | os.PathLike[str]):
        self.root = Path(root)

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
