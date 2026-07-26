from datetime import datetime, timezone
import random
import re

from flask import Blueprint, abort, redirect, render_template, request, url_for

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


def build_detail_context(coverage_id: str, coverage: dict[str, str], edit_error: str | None = None, open_edit_dialog: bool = False) -> dict:
    return {
        "coverage_id": coverage_id,
        "coverage": coverage,
        "title": build_editorial_title(coverage["coverage_name"], coverage["country"]),
        "country_groups": COUNTRY_GROUPS,
        "agency_options": AGENCY_OPTIONS,
        "edit_error": edit_error,
        "open_edit_dialog": open_edit_dialog,
    }


@web_bp.get("/")
def home() -> str:
    return render_template("index.html")


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
    coverages[coverage_id] = form_data
    return redirect(url_for("web.coverage_detail", coverage_id=coverage_id))


@web_bp.get("/coverages/<coverage_id>")
def coverage_detail(coverage_id: str) -> str:
    coverage = coverages.get(coverage_id)
    if coverage is None:
        abort(404)

    return render_template("coverage_detail.html", **build_detail_context(coverage_id, coverage))


@web_bp.post("/coverages/<coverage_id>/edit")
def edit_coverage(coverage_id: str) -> str:
    if coverage_id not in coverages:
        abort(404)

    form_data = collect_coverage_form_data()
    error_message = validate_coverage_data(form_data)

    if error_message:
        return render_template(
            "coverage_detail.html",
            **build_detail_context(
                coverage_id,
                form_data,
                edit_error=error_message,
                open_edit_dialog=True,
            ),
        )

    coverages[coverage_id] = form_data
    return redirect(url_for("web.coverage_detail", coverage_id=coverage_id))
