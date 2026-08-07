from __future__ import annotations

from typing import Any

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for

from app.settings import OutboundChannelDraft, SettingsValidationError
from app.settings.models import SMTP_SECURITY_OPTIONS

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")


SETTINGS_SECTIONS = (
    {
        "title": "Canales de salida",
        "description": "Configura las cuentas desde las que DISPATCH puede entregar material.",
        "endpoint": "settings.channels",
        "enabled": True,
    },
    {"title": "Usuarios", "description": "Próximamente", "endpoint": "", "enabled": False},
    {"title": "Agencias", "description": "Próximamente", "endpoint": "", "enabled": False},
    {"title": "Plantillas", "description": "Próximamente", "endpoint": "", "enabled": False},
    {"title": "Firmas", "description": "Próximamente", "endpoint": "", "enabled": False},
    {"title": "Configuración general", "description": "Próximamente", "endpoint": "", "enabled": False},
)


def get_settings_service():
    return current_app.extensions["settings"]["settings_service"]


def parse_bool(name: str) -> bool:
    return request.form.get(name) == "1"


def collect_channel_form(channel_id: str = "") -> dict[str, Any]:
    raw_id = channel_id or request.form.get("id", "").strip()
    return {
        "id": raw_id,
        "name": request.form.get("name", "").strip(),
        "display_name": request.form.get("display_name", "").strip(),
        "sender_email": request.form.get("sender_email", "").strip(),
        "reply_to": request.form.get("reply_to", "").strip(),
        "smtp_host": request.form.get("smtp_host", "").strip(),
        "smtp_port": request.form.get("smtp_port", "").strip(),
        "smtp_security": request.form.get("smtp_security", "").strip(),
        "smtp_username": request.form.get("smtp_username", "").strip(),
        "credential_ref": request.form.get("credential_ref", "").strip(),
        "is_active": parse_bool("is_active"),
        "is_default": parse_bool("is_default"),
    }


def form_to_draft(form_data: dict[str, Any]) -> OutboundChannelDraft:
    return OutboundChannelDraft(
        id=str(form_data.get("id", "")),
        name=str(form_data.get("name", "")),
        display_name=str(form_data.get("display_name", "")),
        sender_email=str(form_data.get("sender_email", "")),
        reply_to=str(form_data.get("reply_to", "")),
        smtp_host=str(form_data.get("smtp_host", "")),
        smtp_port=form_data.get("smtp_port", ""),
        smtp_security=str(form_data.get("smtp_security", "")),
        smtp_username=str(form_data.get("smtp_username", "")),
        credential_ref=str(form_data.get("credential_ref", "")),
        is_active=bool(form_data.get("is_active")),
        is_default=bool(form_data.get("is_default")),
    )


@settings_bp.get("/")
def index() -> str:
    return render_template("settings/index.html", sections=SETTINGS_SECTIONS)


@settings_bp.get("/channels")
def channels() -> str:
    return render_template(
        "settings/channels.html",
        channels=get_settings_service().list_outbound_channels(),
    )


@settings_bp.route("/channels/new", methods=["GET", "POST"])
def new_channel() -> str:
    if request.method == "GET":
        return render_template(
            "settings/channel_form.html",
            errors=[],
            form_action=url_for("settings.new_channel"),
            form_mode="create",
            form_data={"smtp_port": 465, "smtp_security": "ssl", "is_active": True},
            smtp_security_options=SMTP_SECURITY_OPTIONS,
        )
    form_data = collect_channel_form()
    try:
        channel = get_settings_service().create_outbound_channel(form_to_draft(form_data))
    except (SettingsValidationError, ValueError) as error:
        return render_template(
            "settings/channel_form.html",
            errors=[str(error)],
            form_action=url_for("settings.new_channel"),
            form_mode="create",
            form_data=form_data,
            smtp_security_options=SMTP_SECURITY_OPTIONS,
        ), 400
    return redirect(url_for("settings.channels"))


@settings_bp.route("/channels/<channel_id>/edit", methods=["GET", "POST"])
def edit_channel(channel_id: str) -> str:
    service = get_settings_service()
    channel = service.get_outbound_channel(channel_id)
    if channel is None:
        abort(404)
    if request.method == "GET":
        return render_template(
            "settings/channel_form.html",
            errors=[],
            form_action=url_for("settings.edit_channel", channel_id=channel_id),
            form_mode="edit",
            form_data=channel,
            smtp_security_options=SMTP_SECURITY_OPTIONS,
        )
    form_data = collect_channel_form(channel_id)
    try:
        service.update_outbound_channel(channel_id, form_data)
    except (SettingsValidationError, ValueError) as error:
        return render_template(
            "settings/channel_form.html",
            errors=[str(error)],
            form_action=url_for("settings.edit_channel", channel_id=channel_id),
            form_mode="edit",
            form_data=form_data,
            smtp_security_options=SMTP_SECURITY_OPTIONS,
        ), 400
    return redirect(url_for("settings.channels"))


@settings_bp.post("/channels/<channel_id>/delete")
def delete_channel(channel_id: str) -> str:
    try:
        get_settings_service().delete_outbound_channel(channel_id)
    except SettingsValidationError:
        abort(404)
    return redirect(url_for("settings.channels"))
