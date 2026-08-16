from __future__ import annotations

import base64
import binascii
import io
import logging
from pathlib import Path
from typing import Any, Mapping

from app import config
from app.export.models import ExportPhoto
from app.media import ThumbnailService

LOGGER = logging.getLogger(__name__)
DOCX_IMAGE_MAX_SIDE = 800
DOCX_IMAGE_QUALITY = 80
PROJECT_ROOT = Path(__file__).resolve().parents[3]


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


def is_regular_nonempty_file(path: Path) -> bool:
    try:
        return path.is_file() and not path.is_symlink() and path.stat().st_size > 0
    except OSError:
        return False


def resolve_storage_path(storage_path: str, *, media_root: str | Path | None = None) -> Path | None:
    relative_path = normalize_relative_path(storage_path)
    if not relative_path:
        return None
    root = Path(media_root or config.LENS_MEDIA_ROOT).resolve()
    candidate = root / relative_path
    resolved = candidate.resolve()
    try:
        if not resolved.is_relative_to(root):
            return None
    except ValueError:
        return None
    if not is_regular_nonempty_file(candidate):
        return None
    return resolved


def archived_flow_path(flow_path: str) -> Path | None:
    path = Path(str(flow_path or "").strip())
    if not path.is_absolute():
        return None
    parts = path.parts
    try:
        events_index = parts.index("events")
    except ValueError:
        return None
    relative_parts = parts[events_index + 1:]
    if len(relative_parts) != 8:
        return None
    year, month, day, _event, _photographer, camera, jpg_dir, filename = relative_parts
    if jpg_dir != "JPG" or not filename:
        return None
    return Path(*parts[:events_index], "archive", year, month, day, camera, filename)


def resolve_flow_path(flow_path: str) -> Path | None:
    path = Path(str(flow_path or "").strip())
    if not path.is_absolute():
        return None
    if path.exists():
        if is_regular_nonempty_file(path):
            return path.resolve()
        return None

    archive_candidate = archived_flow_path(str(path))
    if archive_candidate is not None and is_regular_nonempty_file(archive_candidate):
        return archive_candidate.resolve()
    return None


def photo_field(photo: ExportPhoto | Mapping[str, Any], name: str, default: Any = "") -> Any:
    if isinstance(photo, Mapping):
        return photo.get(name, default)
    return getattr(photo, name, default)


def resolve_original_path(
    photo: ExportPhoto | Mapping[str, Any],
    *,
    media_root: str | Path | None = None,
) -> Path | None:
    flow_path = str(photo_field(photo, "flow_path", "") or "").strip()
    if flow_path:
        return resolve_flow_path(flow_path)

    return resolve_storage_path(
        str(photo_field(photo, "storage_path", "") or ""),
        media_root=media_root,
    )


def content_type_from_path(path: Path, fallback: str) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    return fallback or "image/jpeg"


def thumbnail_root_path() -> Path:
    root = Path(config.THUMBNAIL_ROOT)
    if root.is_absolute():
        return root
    return PROJECT_ROOT / root


def load_existing_thumbnail(source_path: Path) -> bytes:
    service = ThumbnailService(thumbnail_root_path())
    thumbnail_path = service.thumbnail_path_for(source_path)
    if thumbnail_path is None or not is_regular_nonempty_file(thumbnail_path):
        return b""
    return thumbnail_path.read_bytes()


def build_docx_jpeg_preview(image_bytes: bytes, source_name: str) -> bytes:
    try:
        from PIL import Image, ImageOps
    except ModuleNotFoundError as error:
        if error.name == "PIL":
            LOGGER.warning("No se pudo reducir imagen DOCX para %s: Pillow no está disponible.", source_name)
            return b""
        raise

    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail((DOCX_IMAGE_MAX_SIDE, DOCX_IMAGE_MAX_SIDE))
            if image.mode != "RGB":
                image = image.convert("RGB")
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=DOCX_IMAGE_QUALITY, optimize=True)
            return output.getvalue()
    except Exception as error:
        LOGGER.warning("No se pudo reducir imagen DOCX para %s: %s", source_name, error)
        return b""


def load_docx_image_source(photo: ExportPhoto) -> tuple[bytes, str]:
    source = resolve_original_path(photo)
    if source is not None:
        try:
            thumbnail_bytes = load_existing_thumbnail(source)
            if thumbnail_bytes:
                return thumbnail_bytes, "image/jpeg"

            original_bytes = source.read_bytes()
            preview_bytes = build_docx_jpeg_preview(original_bytes, photo_label(photo))
            if preview_bytes:
                LOGGER.info("Imagen DOCX reducida en memoria para %s.", photo_label(photo))
                return preview_bytes, "image/jpeg"
        except OSError as error:
            LOGGER.warning("No se pudo leer imagen local para DOCX de %s: %s", photo_label(photo), error)

    image_bytes, content_type = decode_data_url(photo.data_url)
    if not image_bytes:
        return b"", content_type
    preview_bytes = build_docx_jpeg_preview(image_bytes, photo_label(photo))
    if preview_bytes:
        return preview_bytes, "image/jpeg"
    return b"", content_type


def load_image_source(photo: ExportPhoto) -> tuple[bytes, str]:
    fallback_content_type = str(photo.metadata.get("type", "image/jpeg"))
    if str(photo.flow_path or "").strip():
        source = resolve_original_path(photo)
        if source is None:
            return b"", fallback_content_type
        return source.read_bytes(), content_type_from_path(source, fallback_content_type)

    image_bytes, content_type = decode_data_url(photo.data_url)
    if image_bytes:
        return image_bytes, content_type

    if not photo.available_on_disk:
        return b"", content_type

    source = resolve_original_path(photo)
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
