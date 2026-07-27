from datetime import datetime, timezone
import random
import re

from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for

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

AGENCY_OPTIONS = ("Xinhua", "La Vocería", "Otra")

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
    if any(not value for value in form_data.values()):
        return "Completa todos los campos obligatorios."
    return None


def ensure_coverage_photos(coverage: dict) -> list[dict]:
    photos = coverage.setdefault("photos", [])
    return photos if isinstance(photos, list) else []


def parse_optional_int(value):
    if value in (None, ""):
        return None

    return int(value)


def build_detail_context(coverage_id: str, coverage: dict, edit_error: str | None = None, open_edit_dialog: bool = False) -> dict:
    photos = ensure_coverage_photos(coverage)
    return {
        "coverage_id": coverage_id,
        "coverage": coverage,
        "title": build_editorial_title(coverage["coverage_name"], coverage["country"]),
        "photos": photos,
        "country_groups": COUNTRY_GROUPS,
        "agency_options": AGENCY_OPTIONS,
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
            agency_options=AGENCY_OPTIONS,
        )

    form_data = collect_coverage_form_data()
    error_message = validate_coverage_data(form_data)

    if error_message:
        return render_template(
            "new_coverage.html",
            form_data=form_data,
            error_message=error_message,
            country_groups=COUNTRY_GROUPS,
            agency_options=AGENCY_OPTIONS,
        )

    coverage_id = build_coverage_id(form_data["coverage_name"])
    form_data["photos"] = []
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
    coverages[coverage_id] = form_data
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
        }
    except (TypeError, ValueError):
        return jsonify({"error": "Photo payload contains invalid numeric metadata."}), 400

    photos = ensure_coverage_photos(coverage)
    if any(existing_photo["id"] == photo["id"] for existing_photo in photos):
        return jsonify({"photo": photo, "total": len(photos)})

    photos.append(photo)
    return jsonify({"photo": photo, "total": len(photos)}), 201


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
