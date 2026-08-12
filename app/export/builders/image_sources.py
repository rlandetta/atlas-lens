from __future__ import annotations

import base64
import binascii
from pathlib import Path

from app import config
from app.export.models import ExportPhoto


class ImageSourceError(ValueError):
    pass


def photo_label(photo: ExportPhoto) -> str:
    return f"{photo.filename} (id: {photo.id or 'sin-id'})"


def decode_data_url(data_url: str) -> tuple[bytes, str]:
    if not data_url or "," not in data_url:
        return b"", "image/jpeg"
    header, encoded = data_url.split(",", 1)
    content_type = header.split(";")[0].replace("data:", "") or "image/jpeg"
    try:
        return base64.b64decode(encoded, validate=True), content_type
    except (binascii.Error, ValueError):
        return b"", content_type


def normalize_relative_path(value: str) -> str:
    path = str(value or "").strip().replace("\\", "/")
    if not path or Path(path).is_absolute() or path.startswith("../") or "/../" in path:
        return ""
    return path


def resolve_storage_path(storage_path: str) -> Path | None:
    relative_path = normalize_relative_path(storage_path)
    if not relative_path:
        return None
    media_root = Path(config.LENS_MEDIA_ROOT).resolve()
    candidate = (media_root / relative_path).resolve()
    try:
        if not candidate.is_relative_to(media_root):
            return None
    except ValueError:
        return None
    if not candidate.is_file() or candidate.is_symlink():
        return None
    return candidate


def resolve_flow_path(flow_path: str) -> Path | None:
    path = Path(str(flow_path or "").strip())
    if not path.is_absolute():
        return None
    candidate = path.resolve()
    if not candidate.is_file() or candidate.is_symlink():
        return None
    return candidate


def content_type_from_path(path: Path, fallback: str) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    return fallback or "image/jpeg"


def load_image_source(photo: ExportPhoto) -> tuple[bytes, str]:
    image_bytes, content_type = decode_data_url(photo.data_url)
    if image_bytes:
        return image_bytes, content_type

    if not photo.available_on_disk:
        return b"", content_type

    source = resolve_storage_path(photo.storage_path) or resolve_flow_path(photo.flow_path)
    if source is None:
        return b"", content_type
    return source.read_bytes(), content_type_from_path(source, str(photo.metadata.get("type", content_type)))


def load_required_image_source(photo: ExportPhoto) -> tuple[bytes, str]:
    try:
        image_bytes, content_type = load_image_source(photo)
    except OSError as exc:
        raise ImageSourceError(f"No se pudo leer el archivo original de {photo_label(photo)}.") from exc
    if not image_bytes:
        raise ImageSourceError(f"No se pudo resolver el archivo original de {photo_label(photo)}.")
    return image_bytes, content_type
