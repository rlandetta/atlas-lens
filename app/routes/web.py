from datetime import datetime, timezone
import base64
import binascii
import logging
import os
import random
import re
import tempfile
import unicodedata
from pathlib import Path
from copy import deepcopy

from flask import Blueprint, abort, current_app, jsonify, redirect, render_template, request, send_file, url_for

from app.ai import AIError, AIService
from app.ai.context_engine import get_coverage_context_data, normalize_context_payload
from app.config import AI_ENABLED, FLOW_EVENTS_ROOT
from app.media import resolve_legacy_flow_photo_source, resolve_photo_source
from app.dispatch import DispatchHandoffService
from app.export.models import ExportRequest, ExportResult
from app.export.naming import ExportNamingService
from app.export.service import ExportService, ExportValidationError, ExportWarningRequired
from app.suggestion_store import get_all_suggestions, remember_coverage_values

web_bp = Blueprint("web", __name__)
LOGGER = logging.getLogger(__name__)

ALLOWED_PHOTO_TYPES = {
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
    "image/webp": {".webp"},
}

REQUIRED_COVERAGE_FIELDS = (
    "coverage_name",
    "submit_date",
    "event_date",
    "city",
    "country",
    "agency",
    "photographer",
    "editor",
)

LOCALITY_TYPES = {"auto", "city", "locality"}

COUNTRY_GROUPS = (
    (
        "Sudamérica",
        (
            "Argentina",
            "Bolivia",
            "Brasil",
            "Chile",
            "Colombia",
            "Ecuador",
            "Guyana",
            "Paraguay",
            "Perú",
            "Surinam",
            "Uruguay",
            "Venezuela",
        ),
    ),
    (
        "Centroamérica",
        (
            "Belice",
            "Costa Rica",
            "El Salvador",
            "Guatemala",
            "Honduras",
            "Nicaragua",
            "Panamá",
        ),
    ),
    (
        "Caribe",
        (
            "Cuba",
            "Haití",
            "República Dominicana",
            "Puerto Rico",
        ),
    ),
)

# Temporary in-memory storage while there is no database.
coverages = {}
coverage_store = None


def configure_coverage_store(store) -> None:
    global coverage_store
    coverage_store = store
    coverages.clear()
    coverages.update(store.list_coverages())


def persist_coverage(coverage_id: str) -> None:
    if coverage_store is not None and coverage_id in coverages:
        coverage_store.set(coverage_id, coverages[coverage_id])


def persist_all_coverages() -> None:
    if coverage_store is not None:
        coverage_store.save_all(coverages)


def delete_persisted_coverage(coverage_id: str) -> None:
    if coverage_store is not None:
        coverage_store.delete(coverage_id)


def delete_persisted_coverage_media(coverage_id: str) -> None:
    if coverage_store is not None:
        coverage_store.delete_coverage_media(coverage_id)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_coverage_id(coverage_name: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    suffix = f"{random.randint(1000, 9999)}"
    return f"cov-{timestamp}-{suffix}"


def build_editorial_title(coverage_name: str, country: str) -> str:
    normalized_name = " ".join(coverage_name.strip().split())
    name_block = re.sub(r"[-\s]+", "-", normalized_name).upper()
    country_block = " ".join(country.strip().split()).upper()
    return f"{name_block} · {country_block}"


def collect_coverage_form_data() -> dict[str, str]:
    form_data = {
        field: request.form.get(field, "").strip()
        for field in REQUIRED_COVERAGE_FIELDS
    }
    form_data["locality_type"] = normalize_locality_type(request.form.get("locality_type", "auto"))
    return form_data


def validate_coverage_data(form_data: dict[str, str]) -> str | None:
    if any(not form_data.get(field) for field in REQUIRED_COVERAGE_FIELDS):
        return "Completa todos los campos obligatorios."
    return None


def normalize_locality_type(value: str) -> str:
    normalized = str(value or "auto").strip().lower()
    return normalized if normalized in LOCALITY_TYPES else "auto"


def normalize_initial_source(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_value = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    return re.sub(r"[^A-Za-z\s]", " ", ascii_value).strip()


def build_editor_initials(editor_name: str) -> str:
    normalized = normalize_initial_source(editor_name)
    parts = [
        part
        for part in normalized.split()
        if part
    ]

    if len(parts) == 1 and 1 <= len(parts[0]) <= 4:
        return parts[0].lower()

    initials = "".join(part[0] for part in parts).lower()
    return initials or "xx"


def attach_editor_metadata(form_data: dict) -> dict:
    editor_name = form_data.get("editor_name") or form_data.get("editor", "")
    form_data["editor_name"] = editor_name
    form_data["editor_initials"] = build_editor_initials(editor_name)
    return form_data


def apply_coverage_edit_fields(coverage: dict, form_data: dict[str, str]) -> dict:
    updated = deepcopy(coverage)
    for field in REQUIRED_COVERAGE_FIELDS:
        updated[field] = form_data[field]
    updated["locality_type"] = normalize_locality_type(
        form_data.get("locality_type", updated.get("locality_type", "auto"))
    )
    attach_editor_metadata(updated)
    return updated


def attach_default_ai_context(coverage: dict) -> dict:
    context = get_coverage_context_data(coverage)
    context.setdefault("known_people", "")
    context.setdefault("organizations", "")
    context.setdefault("keywords", "")
    context.setdefault("notes", "")
    return coverage


def ensure_coverage_photos(coverage: dict) -> list[dict]:
    photos = coverage.setdefault("photos", [])
    return photos if isinstance(photos, list) else []


def parse_optional_int(value):
    if value in (None, ""):
        return None

    return int(value)


def parse_optional_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def max_photo_bytes() -> int:
    return int(current_app.config.get("LENS_MAX_PHOTO_BYTES", 25 * 1024 * 1024))


def sanitize_filename(filename: str, fallback_extension: str) -> str:
    name = Path(str(filename or "")).name.strip()
    name = name.replace("\\", "")
    stem = Path(name).stem
    extension = Path(name).suffix.lower() or fallback_extension
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip(".-")
    if not stem:
        stem = "photo"
    return f"{stem}{extension}"


def validate_photo_identity(value: str, field_name: str) -> str:
    if coverage_store is None:
        sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value).strip()).strip(".-")
    else:
        sanitized = coverage_store.sanitize_path_component(value)
    if not sanitized:
        raise ValueError(f"{field_name} inválido.")
    return sanitized


def parse_photo_data_url(data_url: str, expected_mime: str) -> bytes:
    prefix = f"data:{expected_mime};base64,"
    if not isinstance(data_url, str) or not data_url.startswith(prefix):
        raise ValueError("El archivo no coincide con el tipo de imagen declarado.")
    encoded_payload = data_url[len(prefix):]
    try:
        return base64.b64decode(encoded_payload, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("La imagen contiene base64 inválido.") from error


def validate_image_signature(content: bytes, mime_type: str) -> None:
    if mime_type == "image/jpeg" and content.startswith(b"\xff\xd8\xff"):
        return
    if mime_type == "image/png" and content.startswith(b"\x89PNG\r\n\x1a\n"):
        return
    if (
        mime_type == "image/webp"
        and len(content) >= 12
        and content[:4] == b"RIFF"
        and content[8:12] == b"WEBP"
    ):
        return
    raise ValueError("El contenido no corresponde a una imagen permitida.")


def build_photo_storage_path(coverage_id: str, photo_id: str, filename: str) -> str:
    safe_coverage_id = validate_photo_identity(coverage_id, "coverage_id")
    safe_photo_id = validate_photo_identity(photo_id, "photo_id")
    safe_filename = sanitize_filename(filename, Path(filename).suffix.lower())
    return f"coverages/{safe_coverage_id}/{safe_photo_id}_{safe_filename}"


def write_photo_content(storage_path: str, content: bytes) -> None:
    if coverage_store is None:
        raise RuntimeError("El almacenamiento de fotografías no está configurado.")

    destination = coverage_store.resolve_storage_path(storage_path)
    if destination is None:
        raise ValueError("La ruta de almacenamiento de la fotografía no es segura.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "wb",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(content)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, destination)
        if not destination.is_file() or destination.is_symlink():
            raise OSError("No se pudo confirmar el archivo de fotografía guardado.")
    except Exception:
        if temp_path and temp_path.exists():
            temp_path.unlink()
        if destination.exists() and not destination.is_symlink() and destination.is_file():
            destination.unlink()
        raise


def build_persisted_photo(coverage_id: str, payload: dict) -> dict:
    photo_id = str(payload["id"])
    original_name = str(payload.get("filename") or payload["name"])
    mime_type = str(payload["type"]).strip().lower()
    if mime_type not in ALLOWED_PHOTO_TYPES:
        raise ValueError("Formato de imagen no permitido.")

    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_PHOTO_TYPES[mime_type]:
        raise ValueError("La extensión del archivo no coincide con un formato permitido.")

    declared_size = int(payload["size"])
    if declared_size <= 0:
        raise ValueError("El tamaño de la imagen no es válido.")
    if declared_size > max_photo_bytes():
        raise OverflowError("La imagen supera el tamaño máximo permitido.")

    content = parse_photo_data_url(str(payload["data_url"]), mime_type)
    if len(content) != declared_size:
        raise ValueError("El tamaño declarado no coincide con el archivo recibido.")
    validate_image_signature(content, mime_type)

    filename = sanitize_filename(original_name, extension)
    storage_path = build_photo_storage_path(coverage_id, photo_id, filename)
    write_photo_content(storage_path, content)

    timestamp = utc_now_iso()
    return {
        "id": validate_photo_identity(photo_id, "photo_id"),
        "name": filename,
        "filename": filename,
        "storage_path": storage_path,
        "size": declared_size,
        "type": mime_type,
        "width": parse_optional_int(payload.get("width")),
        "height": parse_optional_int(payload.get("height")),
        "caption_narrative": str(payload.get("caption_narrative", "")),
        "caption_status": normalize_caption_status(str(payload.get("caption_status", "Sin editar"))),
        "is_drone": parse_optional_bool(payload.get("is_drone", False)),
        "created_at": str(payload.get("created_at") or timestamp),
        "updated_at": str(payload.get("updated_at") or timestamp),
        "available_on_disk": True,
    }


def normalize_caption_status(value: str) -> str:
    allowed_statuses = {"Sin editar", "En edición", "Revisado", "Aprobado"}
    return value if value in allowed_statuses else "Sin editar"


def find_coverage_photo(coverage: dict, photo_id: str) -> dict | None:
    return next(
        (
            existing_photo
            for existing_photo in ensure_coverage_photos(coverage)
            if existing_photo.get("id") == photo_id
        ),
        None,
    )


def is_photo_dispatch_eligible_entry(photo: dict) -> bool:
    if resolve_coverage_photo_source(photo) is None:
        return False
    return (
        bool(str(photo.get("caption_narrative", "")).strip())
        and photo.get("available_on_disk", True) is not False
    )


def has_dispatch_ready_caption(coverage: dict) -> bool:
    return any(
        is_photo_dispatch_eligible_entry(photo)
        for photo in ensure_coverage_photos(coverage)
    )


def get_dispatch_eligible_photo_count(coverage: dict) -> int:
    return sum(
        1
        for photo in ensure_coverage_photos(coverage)
        if is_photo_dispatch_eligible_entry(photo)
    )


def format_source_label(source: str) -> str:
    clean_source = " ".join(str(source or "").replace("_", "-").split()).strip()
    if not clean_source:
        return "Sin cámara"
    return " ".join(part.upper() if any(character.isdigit() for character in part) else part.capitalize() for part in clean_source.split("-"))


def format_datetime_label(value: str) -> str:
    if not value:
        return "Sin registro"
    try:
        timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return "Sin registro"
    return timestamp.astimezone(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")


def format_elapsed_label(value: str) -> str:
    if not value:
        return "Sin recepción previa"
    try:
        timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return "Sin recepción previa"
    seconds = max(0, int((datetime.now(timezone.utc) - timestamp).total_seconds()))
    if seconds < 60:
        return f"hace {seconds} s"
    minutes = seconds // 60
    if minutes < 60:
        return f"hace {minutes} min"
    hours = minutes // 60
    if hours < 24:
        return f"hace {hours} h"
    days = hours // 24
    return f"hace {days} d"


def format_file_size_label(path_value: str) -> str:
    try:
        size = Path(path_value).stat().st_size
    except OSError:
        return "Tamaño no disponible"
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def thumbnail_service():
    return current_app.extensions.get("media", {}).get("thumbnail_service")


def flow_events_root() -> str:
    return str(current_app.config.get("FLOW_EVENTS_ROOT") or FLOW_EVENTS_ROOT)


def ensure_media_thumbnail(source_path: Path | None) -> Path | None:
    service = thumbnail_service()
    if source_path is None or service is None:
        return None
    return service.ensure_thumbnail(source_path)


def update_ingest_photo_path(photo: dict, resolved_path: Path) -> None:
    store = ingest_store()
    if store is None:
        return
    old_path = str(photo.get("path") or photo.get("flow_path") or "")
    photo_id = str(photo.get("id") or photo.get("flow_photo_id") or "")
    session_id = str(photo.get("session_id") or photo.get("flow_session_id") or "")
    next_path = str(resolved_path)

    def mutation(payload):
        changed = False
        for ingest_photo in payload.get("photos", []):
            if photo_id and str(ingest_photo.get("id", "")) != photo_id:
                continue
            if session_id and str(ingest_photo.get("session_id", "")) != session_id:
                continue
            if old_path and str(ingest_photo.get("path", "")) != old_path:
                continue
            ingest_photo["path"] = next_path
            changed = True
        return changed

    if store.mutate(mutation):
        photo["path"] = next_path


def resolve_ingest_photo_source(photo: dict) -> Path | None:
    source = resolve_photo_source(photo, ingest_photos=list_ingest_photos())
    if source is not None:
        return source
    resolved = resolve_legacy_flow_photo_source(photo, events_root=flow_events_root())
    if resolved is None:
        return None
    update_ingest_photo_path(photo, resolved)
    return resolved


def repair_coverage_flow_photo_path(photo: dict, resolved_path: Path) -> bool:
    next_path = str(resolved_path)
    old_photo = deepcopy(photo)
    if str(photo.get("flow_path", "")) == next_path:
        return False
    update_ingest_photo_path(old_photo, resolved_path)
    photo["flow_path"] = next_path
    photo["available_on_disk"] = True
    try:
        photo["size"] = resolved_path.stat().st_size
    except OSError:
        pass
    return True


def resolve_coverage_photo_source(photo: dict) -> Path | None:
    source = resolve_photo_source(
        photo,
        coverage_store=coverage_store,
        ingest_photos=list_ingest_photos(),
    )
    if source is not None:
        return source
    resolved = resolve_legacy_flow_photo_source(photo, events_root=flow_events_root())
    if resolved is None:
        return None
    return resolved


def resolve_and_repair_coverage_photo_source(coverage_id: str, photo: dict) -> tuple[Path | None, bool]:
    source = resolve_photo_source(
        photo,
        coverage_store=coverage_store,
        ingest_photos=list_ingest_photos(),
    )
    if source is not None:
        return source, False
    resolved = resolve_legacy_flow_photo_source(photo, events_root=flow_events_root())
    if resolved is None:
        return None, False
    return resolved, repair_coverage_flow_photo_path(photo, resolved)


def source_file_size(path_value: Path | None) -> int | None:
    if path_value is None:
        return None
    try:
        return path_value.stat().st_size
    except OSError:
        return None


def build_flow_photo_item(photo: dict) -> dict:
    received_at = str(photo.get("received_at", ""))
    source_path = resolve_ingest_photo_source(photo)
    thumbnail = ensure_media_thumbnail(source_path)
    return {
        "filename": str(photo.get("filename") or Path(str(photo.get("path", ""))).name or "Fotografía"),
        "source": format_source_label(str(photo.get("source") or photo.get("camera") or "")),
        "received_at": format_datetime_label(received_at),
        "size": format_file_size_label(str(source_path)) if source_path is not None else "Tamaño no disponible",
        "thumbnail_url": url_for("web.flow_photo_thumbnail", photo_id=str(photo.get("id", ""))) if thumbnail is not None else "",
    }


def ingest_store():
    return current_app.extensions.get("ingest", {}).get("store")


def list_ingest_sessions() -> list[dict]:
    store = ingest_store()
    return store.list_sessions() if store else []


def list_ingest_photos() -> list[dict]:
    store = ingest_store()
    return store.list_photos() if store else []


def find_ingest_session(session_id: str) -> dict | None:
    return next((session for session in list_ingest_sessions() if str(session.get("id", "")) == session_id), None)


def list_ingest_session_photos(session_id: str) -> list[dict]:
    photos = [
        photo
        for photo in list_ingest_photos()
        if str(photo.get("session_id", "")) == session_id
    ]
    return sorted(photos, key=lambda item: str(item.get("received_at", "")))


def flow_date_value(value: str) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return ""


def build_flow_coverage_name(session: dict) -> str:
    date_value = flow_date_value(str(session.get("last_received_at") or session.get("started_at") or ""))
    suffix = date_value or str(session.get("id", "sesión")).replace("session-", "")[:8]
    return f"FLOW {suffix}"


def build_flow_coverage_form_data(session: dict) -> dict[str, str]:
    return {
        "coverage_name": build_flow_coverage_name(session),
        "agency": "Por definir",
        "event_date": flow_date_value(str(session.get("started_at", ""))),
        "submit_date": flow_date_value(str(session.get("last_received_at") or session.get("started_at") or "")),
        "city": "Por definir",
        "country": "Por definir",
        "locality_type": "auto",
        "photographer": "Por definir",
        "editor": "flow",
    }


def build_lens_photo_from_ingest(photo: dict, session_id: str, coverage: dict | None = None) -> dict:
    filename = str(photo.get("filename") or Path(str(photo.get("path", ""))).name or photo.get("id", "Fotografía"))
    path = str(photo.get("path", ""))
    path_object = Path(path)
    received_at = str(photo.get("received_at") or utc_now_iso())
    captured_at = str(photo.get("captured_at") or "")
    camera = str(photo.get("camera") or photo.get("source") or "")
    coverage_data = coverage or {}
    try:
        size = path_object.stat().st_size if path_object.is_file() else None
    except OSError:
        size = None
    return {
        "id": validate_photo_identity(str(photo.get("id", "")), "photo_id"),
        "name": filename,
        "filename": filename,
        "storage_path": "",
        "flow_path": path,
        "flow_session_id": session_id,
        "flow_photo_id": str(photo.get("id", "")),
        "source": camera,
        "camera": camera,
        "size": parse_optional_int(size),
        "type": "image/jpeg",
        "coverage_name": str(coverage_data.get("coverage_name", "")),
        "photographer": str(coverage_data.get("photographer", "")),
        "event_date": str(coverage_data.get("event_date", "")),
        "received_at": received_at,
        "captured_at": captured_at,
        "caption_narrative": "",
        "caption_status": "Sin editar",
        "created_at": received_at,
        "updated_at": received_at,
        "available_on_disk": path_object.is_file() and not path_object.is_symlink(),
    }


def registered_flow_photo(photo: dict) -> dict | None:
    flow_photo_id = str(photo.get("flow_photo_id", ""))
    flow_session_id = str(photo.get("flow_session_id", ""))
    flow_path = str(photo.get("flow_path", ""))
    for ingest_photo in list_ingest_photos():
        if (
            str(ingest_photo.get("id", "")) == flow_photo_id
            and str(ingest_photo.get("session_id", "")) == flow_session_id
            and str(ingest_photo.get("path", "")) == flow_path
        ):
            return ingest_photo
    return None


def resolve_flow_photo_path(photo: dict) -> Path | None:
    return resolve_coverage_photo_source(photo)


def sync_flow_coverage_photos(coverage_id: str, coverage: dict) -> bool:
    session_id = str(coverage.get("flow_session_id", ""))
    if not session_id:
        return False
    photos = ensure_coverage_photos(coverage)
    existing_flow_photo_ids = {str(photo.get("flow_photo_id", "")) for photo in photos if str(photo.get("flow_photo_id", ""))}
    changed = False
    for ingest_photo in list_ingest_session_photos(session_id):
        if str(ingest_photo.get("id", "")) in existing_flow_photo_ids:
            continue
        photos.append(build_lens_photo_from_ingest(ingest_photo, session_id, coverage))
        existing_flow_photo_ids.add(str(ingest_photo.get("id", "")))
        changed = True
    if changed:
        persist_coverage(coverage_id)
    return changed


def sync_flow_linked_coverages() -> None:
    for coverage_id, coverage in list(coverages.items()):
        sync_flow_coverage_photos(coverage_id, coverage)


def mark_ingest_session_coverage(session_id: str, coverage_id: str) -> dict | None:
    store = ingest_store()
    if store is None:
        return None

    def mutation(payload):
        for session in payload["sessions"]:
            if str(session.get("id", "")) == session_id:
                session["coverage_id"] = coverage_id
                return session
        return None

    return store.mutate(mutation)


def clear_ingest_session_coverage(session_id: str, coverage_id: str) -> dict | None:
    store = ingest_store()
    if store is None or not session_id:
        return None

    def mutation(payload):
        for session in payload["sessions"]:
            if (
                str(session.get("id", "")) == session_id
                and str(session.get("coverage_id", "")) == coverage_id
            ):
                session["coverage_id"] = ""
                return session
        return None

    return store.mutate(mutation)


def create_lens_coverage_from_flow_session(session: dict, form_data: dict[str, str]) -> str:
    session_id = str(session.get("id", ""))
    session_photos = list_ingest_session_photos(session_id)
    coverage_id = build_coverage_id(form_data["coverage_name"])
    coverage = dict(form_data)
    coverage["flow_session_id"] = session_id
    coverage["photos"] = [
        build_lens_photo_from_ingest(photo, session_id, coverage)
        for photo in session_photos
    ]
    attach_editor_metadata(coverage)
    attach_default_ai_context(coverage)
    remember_coverage_values(coverage)
    coverages[coverage_id] = coverage
    try:
        persist_coverage(coverage_id)
        mark_ingest_session_coverage(session_id, coverage_id)
    except Exception:
        coverages.pop(coverage_id, None)
        raise
    LOGGER.info(
        "FLOW session %s opened in LENS coverage %s with %s photos",
        session_id,
        coverage_id,
        len(coverage["photos"]),
    )
    return coverage_id


def build_flow_summary() -> dict:
    ingest = current_app.extensions.get("ingest", {})
    service = ingest.get("ingest_service")
    store = ingest.get("store")
    if service is None or store is None:
        return {
            "status": "En espera",
            "active_sessions_count": 0,
            "active_photo_count": 0,
            "active_sources": [],
            "last_received_at": "",
            "last_received_label": "Sin registro",
            "elapsed_label": "Sin recepción previa",
            "recent_sessions_count": 0,
            "recent_sessions": [],
            "active_photos": [],
        }

    service.get_active_session()
    sync_flow_linked_coverages()
    sessions = store.list_sessions()
    photos = store.list_photos()
    active_sessions = sorted(
        [session for session in sessions if session.get("status") == "active"],
        key=lambda item: str(item.get("last_received_at") or item.get("started_at") or ""),
        reverse=True,
    )
    active_session = active_sessions[0] if active_sessions else None
    active_photos = [photo for photo in photos if active_session and photo.get("session_id") == active_session.get("id")]
    active_photos.sort(key=lambda item: str(item.get("received_at", "")), reverse=True)
    last_received_at = ""
    if active_session:
        last_received_at = str(active_session.get("last_received_at") or active_session.get("started_at") or "")
    elif sessions:
        last_received_at = max(str(session.get("last_received_at") or session.get("started_at") or "") for session in sessions)
    sources = active_session.get("sources", []) if active_session else []
    recent_sessions = [
        {
            "id": str(session.get("id", "")),
            "status": str(session.get("status", "")).capitalize() or "Sin estado",
            "photo_count": int(session.get("photo_count") or 0),
            "sources": [format_source_label(source) for source in session.get("sources", [])],
            "started_at": format_datetime_label(str(session.get("started_at", ""))),
            "last_received_at": format_datetime_label(str(session.get("last_received_at", ""))),
            "coverage_id": str(session.get("coverage_id", "")),
            "coverage_name": str(coverages.get(str(session.get("coverage_id", "")), {}).get("coverage_name", "")),
            "create_url": url_for("web.flow_new_coverage", session_id=str(session.get("id", ""))),
            "open_lens_url": url_for("web.flow_open_lens", session_id=str(session.get("id", ""))),
            "lens_url": url_for("web.coverage_detail", coverage_id=str(session.get("coverage_id", ""))) if str(session.get("coverage_id", "")) in coverages else "",
        }
        for session in sorted(
            sessions,
            key=lambda item: str(item.get("last_received_at") or item.get("started_at") or ""),
            reverse=True,
        )[:6]
    ]
    return {
        "status": "Recibiendo" if active_session else "En espera",
        "active_sessions_count": len(active_sessions),
        "active_photo_count": len(active_photos) if active_session else 0,
        "active_sources": [format_source_label(source) for source in sources],
        "last_received_at": last_received_at,
        "last_received_label": format_datetime_label(last_received_at),
        "elapsed_label": format_elapsed_label(last_received_at),
        "recent_sessions_count": len(sessions),
        "recent_sessions": recent_sessions,
        "active_photos": [build_flow_photo_item(photo) for photo in active_photos[:12]],
    }


def build_dispatch_state(coverage: dict) -> dict:
    eligible_photo_count = get_dispatch_eligible_photo_count(coverage)
    return {
        "eligible_photo_count": eligible_photo_count,
        "can_create_dispatch": eligible_photo_count > 0,
    }


def list_related_dispatches(coverage_id: str) -> list[dict]:
    dispatch_service = current_app.extensions.get("dispatch", {}).get("shipment_service")
    if dispatch_service is None:
        return []
    return [
        shipment
        for shipment in dispatch_service.list_shipments()
        if str(shipment.get("coverage_id", "")) == coverage_id
    ]


def build_lens_coverage_items() -> list[dict]:
    return [
        {
            "coverage_id": coverage_id,
            "coverage": coverage,
            "title": build_editorial_title(coverage["coverage_name"], coverage["country"]),
            "photo_count": len(ensure_coverage_photos(coverage)),
            "related_dispatch_count": len(list_related_dispatches(coverage_id)),
            "status": "En preparación",
        }
        for coverage_id, coverage in coverages.items()
    ]


def serialize_photos_for_detail(coverage_id: str, photos: list[dict]) -> list[dict]:
    serialized = []
    changed = False
    for photo in photos:
        source_path, repaired = resolve_and_repair_coverage_photo_source(coverage_id, photo)
        changed = changed or repaired
        item = deepcopy(photo)
        thumbnail = ensure_media_thumbnail(source_path)
        size = source_file_size(source_path)
        if size is not None:
            item["size"] = size
        if thumbnail is not None:
            thumbnail_url = url_for(
                "web.coverage_photo_thumbnail",
                coverage_id=coverage_id,
                photo_id=str(photo.get("id", "")),
            )
            item["media_url"] = thumbnail_url
            item["thumbnail_url"] = thumbnail_url
        else:
            item["media_url"] = ""
            item["thumbnail_url"] = ""
        serialized.append(item)
    if changed:
        persist_coverage(coverage_id)
    return serialized


def ai_disabled_response():
    return jsonify({
        "ok": False,
        "error": {
            "code": "AI_DISABLED",
            "message": "La generación mediante IA no está habilitada.",
        },
    }), 403


def get_photo_sequence(coverage: dict, photo_id: str) -> int:
    for index, photo in enumerate(ensure_coverage_photos(coverage), start=1):
        if photo.get("id") == photo_id:
            return index
    return 0



def build_export_request(payload: dict, coverage_id: str, coverage: dict) -> ExportRequest:
    formats = payload.get("formats", ["docx"])
    if isinstance(formats, str):
        formats = [formats]

    return ExportRequest(
        coverage_id=coverage_id,
        formats=tuple(str(export_format).lower() for export_format in formats if export_format),
        include_photos=bool(payload.get("include_photos", True)),
        include_captions=bool(payload.get("include_captions", True)),
        include_metadata=bool(payload.get("include_metadata", False)),
        include_manifest=bool(payload.get("include_manifest", False)),
        output_name=str(payload.get("output_name", "")),
        template="xinhua",
        scope="coverage",
        requested_by=str(coverage.get("editor", "Sistema")),
        destination=str(payload.get("destination", "download")),
    )


def serialize_export_result(result: ExportResult) -> dict:
    return {
        "filename": result.filename,
        "formats_generated": list(result.formats_generated),
        "files_created": list(result.files_created),
        "archive_path": result.archive_path,
        "zip": result.zip_filename,
        "destination": result.destination,
        "photo_count": result.photo_count,
        "total_size": result.total_size,
        "warnings": list(result.warnings),
        "duration": result.duration,
        "files": [
            {
                "filename": export_file.filename,
                "format": export_file.format,
                "type": export_file.type,
                "mimetype": export_file.mimetype,
                "size": export_file.size,
                "path": export_file.path,
            }
            for export_file in result.files
        ],
    }


def serialize_export_download(result: ExportResult) -> dict:
    payload = serialize_export_result(result)
    payload["files"] = [
        {
            "filename": export_file.filename,
            "format": export_file.format,
            "type": export_file.type,
            "mimetype": export_file.mimetype,
            "size": export_file.size,
            "path": export_file.path,
            "content_base64": base64.b64encode(export_file.content).decode("ascii"),
        }
        for export_file in result.files
    ]
    return payload


def build_export_history(coverage: dict) -> list[dict]:
    history = coverage.setdefault("export_history", [])
    return history if isinstance(history, list) else []

def build_detail_context(coverage_id: str, coverage: dict, edit_error: str | None = None, open_edit_dialog: bool = False) -> dict:
    photos = ensure_coverage_photos(coverage)
    attach_default_ai_context(coverage)
    dispatch_state = build_dispatch_state(coverage)
    return {
        "coverage_id": coverage_id,
        "coverage": coverage,
        "title": build_editorial_title(coverage["coverage_name"], coverage["country"]),
        "photos": serialize_photos_for_detail(coverage_id, photos),
        "export_history": build_export_history(coverage),
        "export_default_name": ExportNamingService().build_names(coverage).base_name,
        "can_create_dispatch": dispatch_state["can_create_dispatch"],
        "dispatch_eligible_photo_count": dispatch_state["eligible_photo_count"],
        "country_groups": COUNTRY_GROUPS,
        "suggestions": get_all_suggestions(),
        "ai_enabled": AI_ENABLED,
        "edit_error": edit_error,
        "open_edit_dialog": open_edit_dialog,
    }


@web_bp.get("/")
def home() -> str:
    sync_flow_linked_coverages()
    coverage_count = len(coverages)
    photo_count = sum(len(ensure_coverage_photos(coverage)) for coverage in coverages.values())
    dispatch_service = current_app.extensions.get("dispatch", {}).get("shipment_service")
    dispatch_count = len(dispatch_service.list_shipments()) if dispatch_service else 0
    active_dispatch_count = len([
        shipment
        for shipment in (dispatch_service.list_shipments() if dispatch_service else [])
        if shipment.get("status") in {"Borrador", "Programado", "Enviando", "Error"}
    ])
    return render_template(
        "index.html",
        coverage_count=coverage_count,
        photo_count=photo_count,
        dispatch_count=dispatch_count,
        active_dispatch_count=active_dispatch_count,
        flow_summary=build_flow_summary(),
    )


@web_bp.get("/lens")
def lens_home() -> str:
    sync_flow_linked_coverages()
    return render_template("lens_index.html", coverages=build_lens_coverage_items())


@web_bp.get("/flow")
def flow_home() -> str:
    return render_template("flow/index.html", flow_summary=build_flow_summary())


@web_bp.route("/flow/sessions/<session_id>/coverage/new", methods=["GET", "POST"])
def flow_new_coverage(session_id: str) -> str:
    session = find_ingest_session(session_id)
    if session is None:
        abort(404)

    existing_coverage_id = str(session.get("coverage_id", ""))
    if existing_coverage_id and existing_coverage_id in coverages:
        sync_flow_coverage_photos(existing_coverage_id, coverages[existing_coverage_id])
        return redirect(url_for("web.coverage_detail", coverage_id=existing_coverage_id))

    session_photos = list_ingest_session_photos(session_id)
    if request.method == "GET":
        return render_template(
            "flow/new_coverage.html",
            session=session,
            photo_count=len(session_photos),
            sources=[format_source_label(source) for source in session.get("sources", [])],
            form_data=build_flow_coverage_form_data(session),
            error_message=None,
            country_groups=COUNTRY_GROUPS,
            suggestions=get_all_suggestions(),
        )

    form_data = collect_coverage_form_data()
    error_message = validate_coverage_data(form_data)
    if error_message:
        return render_template(
            "flow/new_coverage.html",
            session=session,
            photo_count=len(session_photos),
            sources=[format_source_label(source) for source in session.get("sources", [])],
            form_data=form_data,
            error_message=error_message,
            country_groups=COUNTRY_GROUPS,
            suggestions=get_all_suggestions(),
        ), 400

    coverage_id = create_lens_coverage_from_flow_session(session, form_data)
    return redirect(url_for("web.coverage_detail", coverage_id=coverage_id))


@web_bp.post("/flow/sessions/<session_id>/lens/open")
def flow_open_lens(session_id: str) -> str:
    session = find_ingest_session(session_id)
    if session is None:
        abort(404)

    existing_coverage_id = str(session.get("coverage_id", ""))
    if existing_coverage_id and existing_coverage_id in coverages:
        sync_flow_coverage_photos(existing_coverage_id, coverages[existing_coverage_id])
        return redirect(url_for("web.coverage_detail", coverage_id=existing_coverage_id))

    form_data = build_flow_coverage_form_data(session)
    coverage_id = create_lens_coverage_from_flow_session(session, form_data)
    return redirect(url_for("web.coverage_detail", coverage_id=coverage_id))


@web_bp.route("/coverages/new", methods=["GET", "POST"])
def new_coverage() -> str:
    if request.method == "GET":
        return render_template(
            "new_coverage.html",
            form_data={},
            error_message=None,
            country_groups=COUNTRY_GROUPS,
            suggestions=get_all_suggestions(),
        )

    form_data = collect_coverage_form_data()
    error_message = validate_coverage_data(form_data)

    if error_message:
        return render_template(
            "new_coverage.html",
            form_data=form_data,
            error_message=error_message,
            country_groups=COUNTRY_GROUPS,
            suggestions=get_all_suggestions(),
        )

    coverage_id = build_coverage_id(form_data["coverage_name"])
    form_data["photos"] = []
    attach_editor_metadata(form_data)
    attach_default_ai_context(form_data)
    remember_coverage_values(form_data)
    coverages[coverage_id] = form_data
    persist_coverage(coverage_id)
    return redirect(url_for("web.coverage_detail", coverage_id=coverage_id))


@web_bp.get("/coverages/<coverage_id>")
def coverage_detail(coverage_id: str) -> str:
    coverage = coverages.get(coverage_id)
    if coverage is None:
        abort(404)
    sync_flow_coverage_photos(coverage_id, coverage)

    open_edit_dialog = request.args.get("edit") == "1"
    return render_template(
        "coverage_detail.html",
        **build_detail_context(
            coverage_id,
            coverage,
            open_edit_dialog=open_edit_dialog,
        ),
    )


@web_bp.post("/coverages/<coverage_id>/edit")
def edit_coverage(coverage_id: str) -> str:
    if coverage_id not in coverages:
        abort(404)

    form_data = collect_coverage_form_data()
    error_message = validate_coverage_data(form_data)

    if error_message:
        preview_coverage = apply_coverage_edit_fields(coverages[coverage_id], form_data)
        return render_template(
            "coverage_detail.html",
            **build_detail_context(
                coverage_id,
                preview_coverage,
                edit_error=error_message,
                open_edit_dialog=True,
            ),
        )

    remember_coverage_values(form_data)
    if coverage_store is not None:
        updated = coverage_store.mutate(
            coverage_id,
            lambda current: apply_coverage_edit_fields(current, form_data),
        )
        if updated is None:
            abort(404)
        coverages[coverage_id] = updated
    else:
        coverages[coverage_id] = apply_coverage_edit_fields(coverages[coverage_id], form_data)
    return redirect(url_for("web.coverage_detail", coverage_id=coverage_id))


@web_bp.post("/coverages/<coverage_id>/ai-context")
def save_coverage_ai_context(coverage_id: str) -> str:
    if not AI_ENABLED:
        return ai_disabled_response()

    coverage = coverages.get(coverage_id)
    if coverage is None:
        abort(404)

    coverage["ai_context"] = normalize_context_payload(request.form)
    persist_coverage(coverage_id)
    return redirect(url_for("web.coverage_detail", coverage_id=coverage_id))


@web_bp.post("/coverages/<coverage_id>/delete")
def delete_coverage(coverage_id: str) -> str:
    coverage = coverages.get(coverage_id)
    if coverage is None:
        abort(404)

    typed_id = str(request.form.get("confirm_coverage_id", "") or "").strip()
    expected_id = str(coverage_id or "").strip()
    if typed_id != expected_id:
        return "El ID ingresado no coincide con la cobertura. La cobertura no fue eliminada.", 400

    preserve_flow_originals = str(request.form.get("preserve_flow_originals", "") or "").strip().lower()
    if preserve_flow_originals not in {"accepted", "true", "on", "1"}:
        return "Debe confirmar que comprende que las fotografías originales de FLOW se conservarán.", 400

    related_dispatch_count = len(list_related_dispatches(coverage_id))
    flow_session_id = str(coverage.get("flow_session_id", ""))
    del coverages[coverage_id]
    delete_persisted_coverage(coverage_id)
    clear_ingest_session_coverage(flow_session_id, coverage_id)
    LOGGER.info(
        "LENS coverage %s deleted; FLOW originals, media cache, exports and %s related dispatch(es) preserved",
        coverage_id,
        related_dispatch_count,
    )
    return redirect(url_for("web.lens_home"))


@web_bp.post("/coverages/<coverage_id>/exports")
def create_coverage_export(coverage_id: str):
    coverage = coverages.get(coverage_id)
    if coverage is None:
        abort(404)

    payload = request.get_json(silent=True) or {}
    export_request = build_export_request(payload, coverage_id, coverage)
    service = ExportService()

    try:
        result = service.create_export(
            coverage_id=coverage_id,
            coverage=coverage,
            request=export_request,
            confirm_warnings=bool(payload.get("confirm_warnings", False)),
        )
    except ExportWarningRequired as warning:
        return jsonify({
            "ok": False,
            "requires_confirmation": True,
            "warnings": warning.warnings,
        }), 409
    except ExportValidationError as error:
        return jsonify({
            "ok": False,
            "error": error.message,
        }), error.status_code

    if export_request.destination == "dispatch":
        dispatch_payload = DispatchHandoffService().prepare(coverage, result)
        persist_coverage(coverage_id)
        return jsonify({
            "ok": True,
            "destination": "dispatch",
            "result": serialize_export_result(result),
            "dispatch": dispatch_payload,
        })

    persist_coverage(coverage_id)
    return jsonify({
        "ok": True,
        "destination": "download",
        "result": serialize_export_download(result),
    })


@web_bp.post("/coverages/<coverage_id>/photos")
def add_coverage_photo(coverage_id: str):
    coverage = coverages.get(coverage_id)
    if coverage is None:
        abort(404)

    payload = request.get_json(silent=True) or {}
    required_fields = ("id", "name", "size", "type", "data_url")
    if any(not payload.get(field) for field in required_fields):
        return jsonify({"error": "Photo payload is incomplete."}), 400

    photos = ensure_coverage_photos(coverage)
    if any(existing_photo.get("id") == str(payload["id"]) for existing_photo in photos):
        existing_photo = find_coverage_photo(coverage, str(payload["id"]))
        persist_coverage(coverage_id)
        return jsonify({"photo": existing_photo, "total": len(photos)})

    try:
        photo = build_persisted_photo(coverage_id, payload)
    except (TypeError, ValueError):
        return jsonify({"error": "No se pudo guardar la fotografía. Verifica formato, tamaño y contenido."}), 400
    except OverflowError:
        return jsonify({"error": "La fotografía supera el tamaño máximo permitido."}), 413
    except OSError:
        return jsonify({"error": "No se pudo escribir la fotografía en el almacenamiento de ATLAS."}), 500

    photos.append(photo)
    try:
        persist_coverage(coverage_id)
    except Exception:
        photos.remove(photo)
        if coverage_store is not None:
            coverage_store.delete_photo_file(photo.get("storage_path", ""))
        raise
    return jsonify({"photo": photo, "total": len(photos)}), 201


@web_bp.get("/flow/photos/<photo_id>/thumbnail")
def flow_photo_thumbnail(photo_id: str):
    photo = next((item for item in list_ingest_photos() if str(item.get("id", "")) == photo_id), None)
    if photo is None:
        abort(404)
    thumbnail = ensure_media_thumbnail(resolve_ingest_photo_source(photo))
    if thumbnail is None:
        abort(404)
    return send_file(thumbnail, mimetype="image/jpeg", conditional=True, max_age=86400)


@web_bp.get("/coverages/<coverage_id>/photos/<photo_id>/thumbnail")
def coverage_photo_thumbnail(coverage_id: str, photo_id: str):
    coverage = coverages.get(coverage_id)
    if coverage is None:
        abort(404)

    photo = find_coverage_photo(coverage, photo_id)
    if photo is None:
        abort(404)

    source_path, repaired = resolve_and_repair_coverage_photo_source(coverage_id, photo)
    if repaired:
        persist_coverage(coverage_id)
    thumbnail = ensure_media_thumbnail(source_path)
    if thumbnail is None:
        abort(404)
    return send_file(thumbnail, mimetype="image/jpeg", conditional=True, max_age=86400)


@web_bp.get("/coverages/<coverage_id>/photos/<photo_id>/media")
def coverage_photo_media(coverage_id: str, photo_id: str):
    coverage = coverages.get(coverage_id)
    if coverage is None:
        abort(404)

    photo = find_coverage_photo(coverage, photo_id)
    if photo is None:
        abort(404)

    media_path, repaired = resolve_and_repair_coverage_photo_source(coverage_id, photo)
    if repaired:
        persist_coverage(coverage_id)
    if media_path is None:
        abort(404)

    mimetype = str(photo.get("type", "")).strip() or None
    return send_file(media_path, mimetype=mimetype)


@web_bp.post("/coverages/<coverage_id>/photos/<photo_id>/caption")
def save_coverage_photo_caption(coverage_id: str, photo_id: str):
    coverage = coverages.get(coverage_id)
    if coverage is None:
        abort(404)

    payload = request.get_json(silent=True) or {}
    caption_narrative = str(payload.get("caption_narrative", ""))
    caption_status = normalize_caption_status(str(payload.get("caption_status", "Sin editar")))
    is_drone = parse_optional_bool(payload.get("is_drone", False))

    def update_caption(current_coverage: dict) -> dict:
        photo = find_coverage_photo(current_coverage, photo_id)
        if photo is None:
            raise KeyError(photo_id)
        photo["caption_narrative"] = caption_narrative
        photo["caption_status"] = caption_status
        photo["is_drone"] = is_drone
        photo["updated_at"] = utc_now_iso()
        return current_coverage

    try:
        if coverage_store is not None:
            updated_coverage = coverage_store.mutate(coverage_id, update_caption)
            if updated_coverage is None:
                abort(404)
            coverages[coverage_id] = updated_coverage
            coverage = updated_coverage
        else:
            update_caption(coverage)
    except KeyError:
        abort(404)

    photo = find_coverage_photo(coverage, photo_id)
    dispatch_state = build_dispatch_state(coverage)
    return jsonify({
        "saved": True,
        "photo_id": photo_id,
        "caption_narrative": photo["caption_narrative"],
        "caption_status": photo["caption_status"],
        "is_drone": bool(photo.get("is_drone", False)),
        "eligible_photo_count": dispatch_state["eligible_photo_count"],
        "can_create_dispatch": dispatch_state["can_create_dispatch"],
    })


@web_bp.post("/coverages/<coverage_id>/captions/copy-caption-empty")
def copy_caption_to_empty_photos(coverage_id: str):
    coverage = coverages.get(coverage_id)
    if coverage is None:
        abort(404)

    payload = request.get_json(silent=True) or {}
    source_photo_id = str(payload.get("source_photo_id", ""))
    source_caption = str(payload.get("caption_narrative", "")).strip()
    source_status = normalize_caption_status(str(payload.get("caption_status", "Revisado")))

    if not source_photo_id or not source_caption:
        return jsonify({"error": "Source photo caption is required."}), 400

    photos = ensure_coverage_photos(coverage)
    if not any(photo.get("id") == source_photo_id for photo in photos):
        abort(404)

    updated_photo_ids = []
    for photo in photos:
        current_caption = str(photo.get("caption_narrative", "")).strip()
        if photo.get("id") == source_photo_id or current_caption:
            continue

        photo["caption_narrative"] = source_caption
        photo["caption_status"] = source_status
        photo["updated_at"] = utc_now_iso()
        updated_photo_ids.append(str(photo.get("id")))

    persist_coverage(coverage_id)
    return jsonify({
        "updated_photo_ids": updated_photo_ids,
        "updated_count": len(updated_photo_ids),
    })


@web_bp.post("/coverages/<coverage_id>/photos/<photo_id>/generate-narration")
def generate_photo_narration(coverage_id: str, photo_id: str):
    if not AI_ENABLED:
        return ai_disabled_response()

    coverage = coverages.get(coverage_id)
    if coverage is None:
        abort(404)

    photo = find_coverage_photo(coverage, photo_id)
    if photo is None:
        abort(404)

    payload = request.get_json(silent=True) or {}
    service = AIService()

    try:
        result = service.generate_narration(
            coverage_id=coverage_id,
            photo_id=photo_id,
            coverage=coverage,
            photo=photo,
            photo_sequence=get_photo_sequence(coverage, photo_id),
            simulate_error=bool(payload.get("simulate_error")),
        )
    except AIError as error:
        return jsonify({
            "ok": False,
            "error": {
                "code": error.code,
                "message": error.message,
            },
            "provider": error.provider,
        }), error.status_code

    return jsonify({
        "ok": True,
        "narration": result.narration,
        "provider": result.provider,
        "model": result.model,
        "warnings": result.warnings,
    })


@web_bp.get("/coverages/<coverage_id>/photos/<photo_id>/ai-context")
def get_photo_ai_context(coverage_id: str, photo_id: str):
    if not AI_ENABLED:
        return ai_disabled_response()

    coverage = coverages.get(coverage_id)
    if coverage is None:
        abort(404)

    photo = find_coverage_photo(coverage, photo_id)
    if photo is None:
        abort(404)

    service = AIService()
    return jsonify({
        "ok": True,
        "context": service.build_context_preview(
            coverage_id=coverage_id,
            photo_id=photo_id,
            coverage=coverage,
            photo=photo,
            photo_sequence=get_photo_sequence(coverage, photo_id),
        ),
    })


@web_bp.post("/coverages/<coverage_id>/photos/<photo_id>/delete")
def delete_coverage_photo(coverage_id: str, photo_id: str):
    coverage = coverages.get(coverage_id)
    if coverage is None:
        abort(404)

    photos = ensure_coverage_photos(coverage)
    next_photos = [
        photo
        for photo in photos
        if photo.get("id") != photo_id
    ]

    if len(next_photos) == len(photos):
        abort(404)

    photo = next(
        existing_photo
        for existing_photo in photos
        if existing_photo.get("id") == photo_id
    )
    if coverage_store is not None:
        coverage_store.delete_photo_file(str(photo.get("storage_path", "")))
    coverage["photos"] = next_photos
    persist_coverage(coverage_id)
    return jsonify({"total": len(next_photos)})
