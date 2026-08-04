from datetime import datetime, timezone
import base64
import random
import re
import unicodedata

from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for

from app.ai import AIError, AIService
from app.ai.context_engine import get_coverage_context_data, normalize_context_payload
from app.config import AI_ENABLED
from app.dispatch import DispatchHandoffService
from app.export.models import ExportRequest, ExportResult
from app.export.naming import ExportNamingService
from app.export.service import ExportService, ExportValidationError, ExportWarningRequired
from app.suggestion_store import get_all_suggestions, remember_coverage_values

web_bp = Blueprint("web", __name__)

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
    return {
        "coverage_id": coverage_id,
        "coverage": coverage,
        "title": build_editorial_title(coverage["coverage_name"], coverage["country"]),
        "photos": photos,
        "export_history": build_export_history(coverage),
        "export_default_name": ExportNamingService().build_names(coverage).base_name,
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
        form_data["photos"] = ensure_coverage_photos(coverages[coverage_id])
        form_data["ai_context"] = get_coverage_context_data(coverages[coverage_id])
        attach_editor_metadata(form_data)
        return render_template(
            "coverage_detail.html",
            **build_detail_context(
                coverage_id,
                form_data,
                edit_error=error_message,
                open_edit_dialog=True,
            ),
        )

    form_data["photos"] = ensure_coverage_photos(coverages[coverage_id])
    form_data["ai_context"] = get_coverage_context_data(coverages[coverage_id])
    attach_editor_metadata(form_data)
    remember_coverage_values(form_data)
    coverages[coverage_id] = form_data
    persist_coverage(coverage_id)
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

    try:
        timestamp = utc_now_iso()
        photo = {
            "id": str(payload["id"]),
            "name": str(payload["name"]),
            "filename": str(payload.get("filename") or payload["name"]),
            "storage_path": str(payload.get("storage_path") or payload.get("relative_path") or ""),
            "size": int(payload["size"]),
            "type": str(payload["type"]),
            "width": parse_optional_int(payload.get("width")),
            "height": parse_optional_int(payload.get("height")),
            "data_url": str(payload["data_url"]),
            "caption_narrative": str(payload.get("caption_narrative", "")),
            "caption_status": normalize_caption_status(str(payload.get("caption_status", "Sin editar"))),
            "created_at": str(payload.get("created_at") or timestamp),
            "updated_at": str(payload.get("updated_at") or timestamp),
            "available_on_disk": payload.get("available_on_disk", True),
        }
    except (TypeError, ValueError):
        return jsonify({"error": "Photo payload contains invalid numeric metadata."}), 400

    photos = ensure_coverage_photos(coverage)
    if any(existing_photo["id"] == photo["id"] for existing_photo in photos):
        persist_coverage(coverage_id)
        return jsonify({"photo": photo, "total": len(photos)})

    photos.append(photo)
    persist_coverage(coverage_id)
    return jsonify({"photo": photo, "total": len(photos)}), 201


@web_bp.post("/coverages/<coverage_id>/photos/<photo_id>/caption")
def save_coverage_photo_caption(coverage_id: str, photo_id: str):
    coverage = coverages.get(coverage_id)
    if coverage is None:
        abort(404)

    payload = request.get_json(silent=True) or {}
    photos = ensure_coverage_photos(coverage)
    photo = next(
        (
            existing_photo
            for existing_photo in photos
            if existing_photo.get("id") == photo_id
        ),
        None,
    )

    if photo is None:
        abort(404)

    photo["caption_narrative"] = str(payload.get("caption_narrative", ""))
    photo["caption_status"] = normalize_caption_status(str(payload.get("caption_status", "Sin editar")))
    photo["updated_at"] = utc_now_iso()
    persist_coverage(coverage_id)
    return jsonify({
        "photo_id": photo_id,
        "caption_narrative": photo["caption_narrative"],
        "caption_status": photo["caption_status"],
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

    coverage["photos"] = next_photos
    persist_coverage(coverage_id)
    return jsonify({"total": len(next_photos)})
