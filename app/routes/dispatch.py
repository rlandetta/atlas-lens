from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Mapping, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for

from app.dispatch import DispatchValidationError

dispatch_bp = Blueprint("dispatch", __name__, url_prefix="/dispatch")

CHANNEL_OPTIONS = ("Manual", "Correo", "FTP", "SFTP", "API")
DEFAULT_TIMEZONE = "America/Guayaquil"
TIMEZONE_OPTIONS = (DEFAULT_TIMEZONE,)
CREATE_MODES = ("draft", "schedule")


class WebCoverageProvider:
    def __call__(self) -> Mapping[str, dict[str, Any]]:
        from app.routes.web import coverages

        return coverages


def get_dispatch_services() -> dict[str, Any]:
    return current_app.extensions["dispatch"]


def get_coverage_provider():
    services = get_dispatch_services()
    provider = services.get("coverage_provider")
    if provider is not None:
        return provider
    return services["lens_reader"].coverage_source


def read_coverages() -> Mapping[str, dict[str, Any]]:
    provider = get_coverage_provider()
    coverages = provider() if callable(provider) else provider
    if not isinstance(coverages, Mapping):
        return {}
    return coverages


def list_coverage_options() -> list[dict[str, str]]:
    options = []
    for coverage_id, coverage in read_coverages().items():
        options.append({
            "id": str(coverage_id),
            "name": str(coverage.get("coverage_name", "") or coverage_id),
            "city": str(coverage.get("city", "")),
            "country": str(coverage.get("country", "")),
        })
    return sorted(options, key=lambda item: item["name"].casefold())


def get_approved_photo_options(coverage_id: str) -> list[dict[str, str]]:
    if not coverage_id:
        return []
    try:
        photos = get_dispatch_services()["lens_reader"].get_approved_photos(coverage_id)
    except Exception:
        return []
    return [
        {
            "id": str(photo.get("id", "")),
            "name": str(photo.get("name", "") or photo.get("id", "")),
        }
        for photo in photos
        if photo.get("id")
    ]


def parse_recipients(raw_recipients: str) -> list[dict[str, str]]:
    lines = [line.strip() for line in raw_recipients.splitlines() if line.strip()]
    if not lines:
        raise DispatchValidationError("Agrega al menos un destinatario.")

    recipients = []
    for line in lines:
        if "|" not in line:
            raise DispatchValidationError("Cada destinatario debe usar el formato Nombre | correo@dominio.com.")
        name, email = [part.strip() for part in line.split("|", 1)]
        if not name or not email:
            raise DispatchValidationError("Cada destinatario debe incluir nombre y correo electrónico.")
        if "@" not in email or email.startswith("@") or email.endswith("@") or "." not in email.rsplit("@", 1)[-1]:
            raise DispatchValidationError("Cada destinatario debe incluir un correo electrónico válido.")
        recipients.append({"name": name, "email": email})
    return recipients


def parse_schedule(form_data: dict[str, Any]) -> tuple[str, str, str]:
    mode = str(form_data.get("mode", "draft")).strip() or "draft"
    if mode not in CREATE_MODES:
        raise DispatchValidationError("Selecciona un modo de creación válido.")
    if mode == "draft":
        return "Borrador", "", DEFAULT_TIMEZONE

    timezone_name = str(form_data.get("timezone", DEFAULT_TIMEZONE)).strip() or DEFAULT_TIMEZONE
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as error:
        raise DispatchValidationError("La zona horaria seleccionada no es válida.") from error

    scheduled_date = str(form_data.get("scheduled_date", "")).strip()
    scheduled_time = str(form_data.get("scheduled_time", "")).strip()
    if not scheduled_date:
        raise DispatchValidationError("La fecha de envío es obligatoria para programar.")
    if not scheduled_time:
        raise DispatchValidationError("La hora de envío es obligatoria para programar.")
    try:
        scheduled_at = datetime.fromisoformat(f"{scheduled_date}T{scheduled_time}").replace(tzinfo=timezone)
    except ValueError as error:
        raise DispatchValidationError("La fecha y hora de envío no son válidas.") from error

    if scheduled_at <= datetime.now(timezone):
        raise DispatchValidationError("La fecha y hora de envío no puede estar en el pasado.")
    return "Programado", scheduled_at.isoformat(), timezone_name


def build_form_context(form_data: dict[str, Any] | None = None, errors: list[str] | None = None) -> dict[str, Any]:
    form_data = deepcopy(form_data or {})
    requested_coverage_id = str(request.args.get("coverage_id", "")).strip()
    if requested_coverage_id and not form_data.get("coverage_id"):
        form_data["coverage_id"] = requested_coverage_id

    coverage_options = list_coverage_options()
    valid_coverage_ids = {item["id"] for item in coverage_options}
    selected_coverage_id = str(form_data.get("coverage_id", "")).strip()
    context_errors = list(errors or [])

    if requested_coverage_id and requested_coverage_id not in valid_coverage_ids:
        context_errors.append("La cobertura indicada no existe.")
        selected_coverage_id = ""
        form_data["coverage_id"] = ""

    selected_coverage = next(
        (item for item in coverage_options if item["id"] == selected_coverage_id),
        None,
    )
    return {
        "channel_options": CHANNEL_OPTIONS,
        "coverage_options": coverage_options,
        "coverage_locked": bool(requested_coverage_id and selected_coverage),
        "timezone_options": TIMEZONE_OPTIONS,
        "errors": context_errors,
        "form_data": form_data,
        "photo_options": get_approved_photo_options(selected_coverage_id),
        "selected_coverage": selected_coverage,
        "selected_photo_ids": set(form_data.get("photo_ids", [])),
    }


@dispatch_bp.get("/")
def index() -> str:
    shipment_service = get_dispatch_services()["shipment_service"]
    return render_template(
        "dispatch/index.html",
        shipments=shipment_service.list_shipments(),
    )


@dispatch_bp.route("/new", methods=["GET", "POST"])
def new() -> str:
    if request.method == "GET":
        return render_template("dispatch/new.html", **build_form_context())

    form_data = {
        "name": request.form.get("name", "").strip(),
        "coverage_id": request.form.get("coverage_id", "").strip(),
        "photo_ids": request.form.getlist("photo_ids"),
        "recipients": request.form.get("recipients", "").strip(),
        "delivery_note": request.form.get("delivery_note", "").strip(),
        "channel": request.form.get("channel", "").strip(),
        "mode": request.form.get("mode", "draft").strip() or "draft",
        "scheduled_date": request.form.get("scheduled_date", "").strip(),
        "scheduled_time": request.form.get("scheduled_time", "").strip(),
        "timezone": request.form.get("timezone", DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE,
    }

    errors = []
    requested_coverage_id = str(request.args.get("coverage_id", "")).strip()
    if requested_coverage_id:
        if requested_coverage_id not in read_coverages():
            errors.append("La cobertura indicada no existe.")
            form_data["coverage_id"] = ""
        else:
            form_data["coverage_id"] = requested_coverage_id

    recipients = []
    if not form_data["name"]:
        errors.append("El nombre del despacho es obligatorio.")
    if not form_data["coverage_id"]:
        errors.append("Selecciona una cobertura.")
    if not form_data["photo_ids"]:
        errors.append("Selecciona al menos una fotografía.")
    if form_data["channel"] not in CHANNEL_OPTIONS:
        errors.append("Selecciona un canal válido.")
    try:
        recipients = parse_recipients(form_data["recipients"])
    except DispatchValidationError as error:
        errors.append(str(error))
    status = "Borrador"
    scheduled_at = ""
    timezone_name = DEFAULT_TIMEZONE
    try:
        status, scheduled_at, timezone_name = parse_schedule(form_data)
    except DispatchValidationError as error:
        errors.append(str(error))

    if errors:
        return render_template(
            "dispatch/new.html",
            **build_form_context(form_data, errors),
        ), 400

    try:
        shipment = get_dispatch_services()["shipment_service"].create_shipment(
            name=form_data["name"],
            coverage_id=form_data["coverage_id"],
            photo_ids=form_data["photo_ids"],
            recipients=recipients,
            delivery_note=form_data["delivery_note"],
            channel=form_data["channel"],
            status=status,
            scheduled_at=scheduled_at,
            timezone=timezone_name,
        )
    except DispatchValidationError as error:
        return render_template(
            "dispatch/new.html",
            **build_form_context(form_data, [str(error)]),
        ), 400

    return redirect(url_for("dispatch.detail", shipment_id=shipment["id"]))


@dispatch_bp.get("/<shipment_id>")
def detail(shipment_id: str) -> str:
    shipment_service = get_dispatch_services()["shipment_service"]
    shipment = shipment_service.get_shipment(shipment_id)
    if shipment is None:
        abort(404)
    return render_template("dispatch/detail.html", shipment=shipment)
