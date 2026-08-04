from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Mapping, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for

from app.dispatch import DispatchValidationError

dispatch_bp = Blueprint("dispatch", __name__, url_prefix="/dispatch")

CHANNEL_OPTIONS = ("Manual", "Correo", "FTP", "SFTP", "API")
DEFAULT_TIMEZONE = "America/Guayaquil"
TIMEZONE_OPTIONS = (DEFAULT_TIMEZONE,)
CREATE_MODES = ("draft", "schedule")
SPANISH_MONTHS = (
    "",
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


class WebCoverageProvider:
    def __call__(self) -> Mapping[str, dict[str, Any]]:
        lens_extension = current_app.extensions.get("lens", {})
        coverage_store = lens_extension.get("coverage_store")
        if coverage_store is not None:
            return coverage_store.list_coverages()

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


def format_datetime_es(value: str, timezone_name: str = DEFAULT_TIMEZONE) -> str:
    raw_value = str(value or "").strip()
    if not raw_value:
        return ""
    try:
        parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except ValueError:
        return raw_value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    try:
        target_timezone = ZoneInfo(timezone_name or DEFAULT_TIMEZONE)
    except ZoneInfoNotFoundError:
        target_timezone = ZoneInfo(DEFAULT_TIMEZONE)
    local = parsed.astimezone(target_timezone)
    return f"{local.day} de {SPANISH_MONTHS[local.month]} de {local.year}, {local:%H:%M}"


def split_formatted_datetime(value: str) -> dict[str, str]:
    if not value:
        return {"date": "", "time": ""}
    date_part, _, time_part = value.partition(", ")
    return {"date": date_part, "time": time_part}


def truncate_text(value: str, limit: int = 170) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}…"


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


def is_photo_available_for_dispatch(photo: dict[str, Any]) -> bool:
    storage_path = str(photo.get("storage_path", "")).strip()
    if photo.get("available_on_disk", True) is False or not storage_path:
        return False

    lens_extension = current_app.extensions.get("lens", {})
    coverage_store = lens_extension.get("coverage_store")
    if coverage_store is None:
        return photo.get("available_on_disk", True) is not False
    return coverage_store.is_stored_file_available(storage_path)


def get_caption_photo_options(coverage_id: str) -> list[dict[str, str]]:
    if not coverage_id:
        return []
    try:
        coverage = get_dispatch_services()["lens_reader"].get_coverage(coverage_id)
    except Exception:
        return []

    photos = coverage.get("photos", [])
    if not isinstance(photos, list):
        return []
    return [
        {
            "id": str(photo.get("id", "")),
            "name": str(photo.get("name", "") or photo.get("id", "")),
            "caption_excerpt": str(photo.get("caption_narrative", "")).strip()[:140],
            "has_caption": bool(str(photo.get("caption_narrative", "")).strip()),
            "file_available": is_photo_available_for_dispatch(photo),
            "available_on_disk": (
                bool(str(photo.get("caption_narrative", "")).strip())
                and is_photo_available_for_dispatch(photo)
            ),
            "thumbnail_url": url_for(
                "web.coverage_photo_media",
                coverage_id=coverage_id,
                photo_id=str(photo.get("id", "")),
            ) if is_photo_available_for_dispatch(photo) else "",
        }
        for photo in photos
        if photo.get("id")
    ]


def get_live_coverage(coverage_id: str) -> dict[str, Any]:
    try:
        return get_dispatch_services()["lens_reader"].get_coverage(coverage_id)
    except Exception:
        return {}


def build_photo_detail_items(shipment: dict[str, Any]) -> list[dict[str, Any]]:
    coverage_id = str(shipment.get("coverage_id", ""))
    live_coverage = get_live_coverage(coverage_id)
    live_photos = {
        str(photo.get("id")): photo
        for photo in live_coverage.get("photos", [])
        if isinstance(photo, dict)
    }
    snapshot_photos = [
        photo
        for photo in shipment.get("photo_snapshots", [])
        if isinstance(photo, dict)
    ]
    items = []
    for snapshot in snapshot_photos:
        photo_id = str(snapshot.get("id", ""))
        live_photo = live_photos.get(photo_id, {})
        caption = str(
            live_photo.get("caption_narrative")
            or snapshot.get("caption_preview")
            or ""
        )
        caption_status = str(
            live_photo.get("caption_status")
            or snapshot.get("caption_status")
            or ""
        )
        name = str(
            live_photo.get("name")
            or live_photo.get("filename")
            or snapshot.get("name")
            or photo_id
        )
        thumbnail_url = ""
        if live_photo and is_photo_available_for_dispatch(live_photo):
            thumbnail_url = url_for(
                "web.coverage_photo_media",
                coverage_id=coverage_id,
                photo_id=photo_id,
            )
        items.append({
            "id": photo_id,
            "name": name,
            "caption_excerpt": truncate_text(caption),
            "caption_status": caption_status,
            "thumbnail_url": thumbnail_url,
        })
    return items


def count_eligible_coverage_photos(coverage_id: str) -> int:
    return sum(
        1
        for photo in get_caption_photo_options(coverage_id)
        if photo.get("available_on_disk")
    )


def build_content_summary(shipment: dict[str, Any]) -> dict[str, Any]:
    caption_docx = {}
    export_reference = shipment.get("export_reference", {})
    if isinstance(export_reference, dict):
        raw_caption_docx = export_reference.get("caption_docx", {})
        if isinstance(raw_caption_docx, dict):
            caption_docx = raw_caption_docx
    include_docx = bool(shipment.get("include_caption_docx") or caption_docx.get("include"))
    photo_scope = str(caption_docx.get("photo_scope", "selected"))
    selected_count = len(shipment.get("photo_ids", []))
    if photo_scope == "all_eligible" and selected_count == 0:
        docx_photo_count = count_eligible_coverage_photos(str(shipment.get("coverage_id", "")))
        scope_label = "Todos los captions disponibles"
    else:
        docx_photo_count = selected_count
        scope_label = "Fotografías seleccionadas"
    return {
        "docx_included": include_docx,
        "docx_scope": scope_label,
        "docx_photo_count": docx_photo_count,
        "photo_count": selected_count,
    }


def format_recipient(recipient: dict[str, Any]) -> str:
    name = str(recipient.get("name", "")).strip()
    email = str(recipient.get("email", "")).strip()
    if name and email:
        return f"{name} <{email}>"
    return name or email or "Destinatario sin datos"


def summarize_recipients(recipients: list[dict[str, Any]]) -> str:
    if not recipients:
        return "sin destinatarios"
    formatted = [
        format_recipient(recipient)
        for recipient in recipients
        if isinstance(recipient, dict)
    ]
    if not formatted:
        return "sin destinatarios"
    if len(formatted) == 1:
        return formatted[0]
    if len(formatted) == 2:
        return f"{formatted[0]} y {formatted[1]}"
    return f"{formatted[0]}, {formatted[1]} y {len(formatted) - 2} más"


def pluralize(value: int, singular: str, plural: str) -> str:
    return singular if value == 1 else plural


def build_operational_summary(
    shipment: dict[str, Any],
    content_summary: dict[str, Any],
    formatted: dict[str, str],
) -> dict[str, str]:
    status = str(shipment.get("status", ""))
    recipients = [
        recipient
        for recipient in shipment.get("recipients", [])
        if isinstance(recipient, dict)
    ]
    recipient_count = len(recipients)
    photo_count = int(content_summary.get("photo_count", 0) or 0)
    docx_text = (
        " y un documento Word con captions"
        if content_summary.get("docx_included")
        else ""
    )
    scheduled = split_formatted_datetime(formatted.get("scheduled_at", ""))
    sent = split_formatted_datetime(formatted.get("sent_at", ""))
    recipient_summary = summarize_recipients(recipients)
    recipient_label = pluralize(recipient_count, "destinatario", "destinatarios")
    photo_label = pluralize(photo_count, "fotografía", "fotografías")

    text = (
        f"Este despacho está en estado {status or 'sin estado'}."
    )
    if status == "Borrador":
        text = (
            "Este despacho aún no está programado. "
            f"Se entregará a {recipient_count} {recipient_label} e incluye "
            f"{photo_count} {photo_label}{docx_text}."
        )
    elif status == "Programado":
        text = (
            f"Este despacho se enviará el {scheduled['date']} a las {scheduled['time']} "
            f"a {recipient_summary}. Incluye {photo_count} {photo_label}{docx_text}."
        )
    elif status == "Enviando":
        text = f"Este despacho está siendo enviado a {recipient_summary}."
    elif status == "Enviado":
        text = (
            f"Este despacho fue enviado el {sent['date']} a las {sent['time']} "
            f"a {recipient_summary}."
        )
    elif status == "Error":
        text = (
            f"El envío programado para el {scheduled['date']} a las {scheduled['time']} "
            "no pudo completarse."
        )
    elif status == "Cancelado":
        text = (
            f"El envío programado para el {scheduled['date']} a las {scheduled['time']} "
            "fue cancelado."
        )

    return {
        "text": text,
        "secondary": str(shipment.get("last_error", "")).strip() if status == "Error" else "",
    }


def build_detail_context(shipment: dict[str, Any]) -> dict[str, Any]:
    timezone_name = str(shipment.get("timezone") or DEFAULT_TIMEZONE)
    formatted_history = []
    for item in shipment.get("history", []):
        if not isinstance(item, dict):
            continue
        formatted_history.append({
            "status": str(item.get("status", "")),
            "note": str(item.get("note", "")),
            "created_at": format_datetime_es(str(item.get("created_at", "")), timezone_name),
        })
    content_summary = build_content_summary(shipment)
    formatted = {
        "created_at": format_datetime_es(str(shipment.get("created_at", "")), timezone_name),
        "updated_at": format_datetime_es(str(shipment.get("updated_at", "")), timezone_name),
        "scheduled_at": format_datetime_es(str(shipment.get("scheduled_at", "")), timezone_name),
        "sent_at": format_datetime_es(str(shipment.get("sent_at", "")), timezone_name),
        "last_attempt_at": format_datetime_es(str(shipment.get("last_attempt_at", "")), timezone_name),
    }
    return {
        "shipment": shipment,
        "content_summary": content_summary,
        "detail_photos": build_photo_detail_items(shipment),
        "formatted": formatted,
        "operational_summary": build_operational_summary(shipment, content_summary, formatted),
        "history_items": formatted_history,
    }


def parse_recipients(raw_recipients: str) -> list[dict[str, str]]:
    lines = [line.strip() for line in raw_recipients.splitlines() if line.strip()]
    if not lines:
        raise DispatchValidationError("Agrega al menos un destinatario.")

    recipients = []
    for line in lines:
        if "|" not in line:
            raise DispatchValidationError(
                "Cada destinatario debe usar el formato Nombre | correo@dominio.com. "
                "Ejemplo: Mesa Xinhua | desk@xinhua.com"
            )
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
    if requested_coverage_id and selected_coverage and not form_data.get("name"):
        form_data["name"] = selected_coverage["name"]
    if "include_caption_docx" not in form_data:
        form_data["include_caption_docx"] = True
    photo_options = get_caption_photo_options(selected_coverage_id)
    eligible_photo_ids = {
        photo["id"]
        for photo in photo_options
        if photo["available_on_disk"]
    }
    selected_photo_ids = set(form_data.get("photo_ids", []))
    if request.method == "GET" and not selected_photo_ids:
        selected_photo_ids = set(eligible_photo_ids)
    return {
        "channel_options": CHANNEL_OPTIONS,
        "coverage_options": coverage_options,
        "coverage_locked": bool(requested_coverage_id and selected_coverage),
        "timezone_options": TIMEZONE_OPTIONS,
        "errors": context_errors,
        "form_data": form_data,
        "photo_options": photo_options,
        "selected_coverage": selected_coverage,
        "selected_photo_ids": selected_photo_ids,
        "docx_includes_all_captions": bool(
            form_data.get("include_caption_docx")
            and not selected_photo_ids
            and eligible_photo_ids
        ),
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
        "include_caption_docx": "include_caption_docx" in request.form,
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
    if not form_data["photo_ids"] and not form_data["include_caption_docx"]:
        errors.append("Seleccione al menos una fotografía o incluya el documento Word con captions.")
    if form_data["photo_ids"]:
        approved_photo_options = get_caption_photo_options(form_data["coverage_id"])
        unavailable_photo_ids = {
            photo["id"]
            for photo in approved_photo_options
            if not photo["available_on_disk"]
        }
        if any(photo_id in unavailable_photo_ids for photo_id in form_data["photo_ids"]):
            errors.append("Selecciona únicamente fotografías con caption y archivo disponible para envío.")
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
            export_reference={
                "caption_docx": {
                    "include": bool(form_data["include_caption_docx"]),
                    "format": "docx",
                    "photo_scope": "selected" if form_data["photo_ids"] else "all_eligible",
                    "generator": "ExportService",
                }
            },
            status=status,
            scheduled_at=scheduled_at,
            timezone=timezone_name,
            include_caption_docx=bool(form_data["include_caption_docx"]),
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
    return render_template("dispatch/detail.html", **build_detail_context(shipment))
