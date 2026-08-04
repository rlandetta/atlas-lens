from datetime import datetime, timezone
import base64
import binascii
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
from app.config import AI_ENABLED
from app.dispatch import DispatchHandoffService
from app.export.models import ExportRequest, ExportResult
from app.export.naming import ExportNamingService
from app.export.service import ExportService, ExportValidationError, ExportWarningRequired
from app.suggestion_store import get_all_suggestions, remember_coverage_values

web_bp = Blueprint("web", __name__)

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
    return {
        field: request.form.get(field, "").strip()
        for field in REQUIRED_COVERAGE_FIELDS
    }


def validate_coverage_data(form_data: dict[str, str]) -> str | None:
    if any(not form_data.get(field) for field in REQUIRED_COVERAGE_FIELDS):
        return "Completa todos los campos obligatorios."
    return None


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
    storage_path = str(photo.get("storage_path", "")).strip()
    if coverage_store is not None and not coverage_store.is_stored_file_available(storage_path):
        return False
    return (
        bool(str(photo.get("caption_narrative", "")).strip())
        and photo.get("available_on_disk", True) is not False
        and bool(storage_path)
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


def build_dispatch_state(coverage: dict) -> dict:
    eligible_photo_count = get_dispatch_eligible_photo_count(coverage)
    return {
        "eligible_photo_count": eligible_photo_count,
        "can_create_dispatch": eligible_photo_count > 0,
    }


def serialize_photos_for_detail(coverage_id: str, photos: list[dict]) -> list[dict]:
    serialized = []
    for photo in photos:
        item = deepcopy(photo)
        storage_path = str(photo.get("storage_path", "")).strip()
        if coverage_store is not None and coverage_store.is_stored_file_available(storage_path):
            item["media_url"] = url_for(
                "web.coverage_photo_media",
                coverage_id=coverage_id,
                photo_id=str(photo.get("id", "")),
            )
        else:
            item["media_url"] = ""
        serialized.append(item)
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
    coverage_items = [
        {
            "coverage_id": coverage_id,
            "coverage": coverage,
            "title": build_editorial_title(coverage["coverage_name"], coverage["country"]),
            "photo_count": len(ensure_coverage_photos(coverage)),
            "status": "En preparación",
        }
        for coverage_id, coverage in coverages.items()
    ]
    return render_template("index.html", coverages=coverage_items)


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
    if coverage_id not in coverages:
        abort(404)

    del coverages[coverage_id]
    delete_persisted_coverage(coverage_id)
    delete_persisted_coverage_media(coverage_id)
    return redirect(url_for("web.home"))


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


@web_bp.get("/coverages/<coverage_id>/photos/<photo_id>/media")
def coverage_photo_media(coverage_id: str, photo_id: str):
    coverage = coverages.get(coverage_id)
    if coverage is None or coverage_store is None:
        abort(404)

    photo = find_coverage_photo(coverage, photo_id)
    if photo is None:
        abort(404)

    storage_path = str(photo.get("storage_path", "")).strip()
    media_path = coverage_store.resolve_storage_path(storage_path)
    if (
        media_path is None
        or not media_path.is_file()
        or media_path.is_symlink()
        or not coverage_store.is_stored_file_available(storage_path)
    ):
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

    def update_caption(current_coverage: dict) -> dict:
        photo = find_coverage_photo(current_coverage, photo_id)
        if photo is None:
            raise KeyError(photo_id)
        photo["caption_narrative"] = caption_narrative
        photo["caption_status"] = caption_status
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
