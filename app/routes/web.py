from datetime import datetime, timezone
import random
import re
import unicodedata

from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for

from app.ai import AIError, AIService
from app.ai.context_engine import get_coverage_context_data, normalize_context_payload
from app.config import AI_ENABLED
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


def build_detail_context(coverage_id: str, coverage: dict, edit_error: str | None = None, open_edit_dialog: bool = False) -> dict:
    photos = ensure_coverage_photos(coverage)
    attach_default_ai_context(coverage)
    return {
        "coverage_id": coverage_id,
        "coverage": coverage,
        "title": build_editorial_title(coverage["coverage_name"], coverage["country"]),
        "photos": photos,
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
    return redirect(url_for("web.coverage_detail", coverage_id=coverage_id))


@web_bp.post("/coverages/<coverage_id>/ai-context")
def save_coverage_ai_context(coverage_id: str) -> str:
    if not AI_ENABLED:
        return ai_disabled_response()

    coverage = coverages.get(coverage_id)
    if coverage is None:
        abort(404)

    coverage["ai_context"] = normalize_context_payload(request.form)
    return redirect(url_for("web.coverage_detail", coverage_id=coverage_id))


@web_bp.post("/coverages/<coverage_id>/delete")
def delete_coverage(coverage_id: str) -> str:
    if coverage_id not in coverages:
        abort(404)

    del coverages[coverage_id]
    return redirect(url_for("web.home"))


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
        photo = {
            "id": str(payload["id"]),
            "name": str(payload["name"]),
            "size": int(payload["size"]),
            "type": str(payload["type"]),
            "width": parse_optional_int(payload.get("width")),
            "height": parse_optional_int(payload.get("height")),
            "data_url": str(payload["data_url"]),
            "caption_narrative": str(payload.get("caption_narrative", "")),
            "caption_status": normalize_caption_status(str(payload.get("caption_status", "Sin editar"))),
        }
    except (TypeError, ValueError):
        return jsonify({"error": "Photo payload contains invalid numeric metadata."}), 400

    photos = ensure_coverage_photos(coverage)
    if any(existing_photo["id"] == photo["id"] for existing_photo in photos):
        return jsonify({"photo": photo, "total": len(photos)})

    photos.append(photo)
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
    return jsonify({
        "photo_id": photo_id,
        "caption_narrative": photo["caption_narrative"],
        "caption_status": photo["caption_status"],
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
    return jsonify({"total": len(next_photos)})
