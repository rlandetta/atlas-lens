from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Blueprint, abort, current_app, redirect, render_template, request, send_file, url_for

from PIL import Image, ImageOps

from app.settings import CHANNEL_TYPES, OutboundChannelDraft, SettingsValidationError
from app.settings.models import SMTP_SECURITY_OPTIONS

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")


SETTINGS_SECTIONS = (
    {
        "title": "Canales de salida",
        "description": "Configura las cuentas desde las que DISPATCH puede entregar material.",
        "endpoint": "settings.channels",
        "enabled": True,
    },
    {
        "title": "Mi perfil",
        "description": "Nombre público, cargo, organización y avatar para entregas.",
        "endpoint": "settings.profile",
        "enabled": True,
    },
    {
        "title": "Branding de entregas",
        "description": "Logo textual y footer para páginas públicas de DISPATCH.",
        "endpoint": "settings.branding",
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


def avatar_root() -> Path:
    return current_app.extensions["settings"]["profile_avatar_root"]


def safe_avatar_path(filename: str) -> Path | None:
    safe_name = "".join(character if character.isalnum() or character in {"-", "_", "."} else "-" for character in str(filename or "").strip())
    safe_name = safe_name.strip("-_.")
    if not safe_name:
        return None
    root = avatar_root().resolve()
    candidate = (root / safe_name).resolve()
    if not candidate.is_relative_to(root) or not candidate.is_file():
        return None
    return candidate


def parse_bool(name: str) -> bool:
    return request.form.get(name) == "1"


def optimize_avatar_upload(raw_bytes: bytes, filename: str) -> tuple[bytes, str]:
    max_bytes = int(current_app.config.get("PROFILE_MAX_AVATAR_BYTES", 5 * 1024 * 1024))
    if len(raw_bytes) > max_bytes:
        raise SettingsValidationError("La foto de perfil supera el tamaño máximo permitido.")
    try:
        with Image.open(Path(filename).name) as _:
            pass
    except Exception:
        pass
    from io import BytesIO

    source = BytesIO(raw_bytes)
    try:
        with Image.open(source) as image:
            image = ImageOps.exif_transpose(image)
            image = ImageOps.fit(image.convert("RGB"), (320, 320), method=Image.Resampling.LANCZOS)
            output = BytesIO()
            image.save(output, format="JPEG", quality=82, optimize=True, progressive=True)
    except Exception as error:
        raise SettingsValidationError("La imagen de perfil no es válida. Use JPG, PNG o WEBP.") from error
    optimized = output.getvalue()
    if not optimized:
        raise SettingsValidationError("No se pudo procesar la foto de perfil.")
    avatar_name = f"avatar-{request.form.get('profile_key', 'default').strip().lower() or 'default'}.jpg"
    safe_name = "".join(character if character.isalnum() or character in {"-", "_", "."} else "-" for character in avatar_name)
    safe_name = safe_name.strip(".-_") or "avatar-default.jpg"
    if not safe_name.endswith(".jpg"):
        safe_name = f"{safe_name}.jpg"
    return optimized, safe_name


def collect_channel_form(channel_id: str = "") -> dict[str, Any]:
    raw_id = channel_id or request.form.get("id", "").strip()
    return {
        "id": raw_id,
        "name": request.form.get("name", "").strip(),
        "display_name": request.form.get("display_name", "").strip(),
        "channel_type": request.form.get("channel_type", "smtp").strip(),
        "sender_email": request.form.get("sender_email", "").strip(),
        "reply_to": request.form.get("reply_to", "").strip(),
        "smtp_host": request.form.get("smtp_host", "").strip(),
        "smtp_port": request.form.get("smtp_port", "").strip(),
        "smtp_security": request.form.get("smtp_security", "").strip(),
        "smtp_username": request.form.get("smtp_username", "").strip(),
        "credential_ref": request.form.get("credential_ref", "").strip(),
        "host": request.form.get("host", "").strip(),
        "port": request.form.get("port", "").strip(),
        "username": request.form.get("username", "").strip(),
        "remote_path": request.form.get("remote_path", "").strip(),
        "host_key_fingerprint": request.form.get("host_key_fingerprint", "").strip(),
        "is_active": parse_bool("is_active"),
        "is_default": parse_bool("is_default"),
    }


def form_to_draft(form_data: dict[str, Any]) -> OutboundChannelDraft:
    return OutboundChannelDraft(
        id=str(form_data.get("id", "")),
        name=str(form_data.get("name", "")),
        display_name=str(form_data.get("display_name", "")),
        channel_type=str(form_data.get("channel_type", "smtp")),
        sender_email=str(form_data.get("sender_email", "")),
        reply_to=str(form_data.get("reply_to", "")),
        smtp_host=str(form_data.get("smtp_host", "")),
        smtp_port=form_data.get("smtp_port", ""),
        smtp_security=str(form_data.get("smtp_security", "")),
        smtp_username=str(form_data.get("smtp_username", "")),
        credential_ref=str(form_data.get("credential_ref", "")),
        host=str(form_data.get("host", "")),
        port=form_data.get("port", ""),
        username=str(form_data.get("username", "")),
        remote_path=str(form_data.get("remote_path", "")),
        host_key_fingerprint=str(form_data.get("host_key_fingerprint", "")),
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
            form_data={"channel_type": "smtp", "smtp_port": 465, "smtp_security": "ssl", "is_active": True},
            smtp_security_options=SMTP_SECURITY_OPTIONS,
            channel_types=CHANNEL_TYPES,
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
            channel_types=CHANNEL_TYPES,
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
            channel_types=CHANNEL_TYPES,
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
            channel_types=CHANNEL_TYPES,
        ), 400
    return redirect(url_for("settings.channels"))


@settings_bp.post("/channels/<channel_id>/delete")
def delete_channel(channel_id: str) -> str:
    try:
        get_settings_service().delete_outbound_channel(channel_id)
    except SettingsValidationError:
        abort(404)
    return redirect(url_for("settings.channels"))


@settings_bp.route("/profile", methods=["GET", "POST"])
def profile() -> str:
    service = get_settings_service()
    requested_key = str(request.args.get("profile_key", request.form.get("profile_key", "default"))).strip() or "default"
    if request.method == "GET":
        return render_template(
            "settings/profile.html",
            errors=[],
            profile_key=requested_key,
            form_data=service.get_public_profile(requested_key),
        )

    profile_payload = {
        "display_name": request.form.get("display_name", "").strip(),
        "role": request.form.get("role", "").strip(),
        "organization": request.form.get("organization", "").strip(),
        "location": request.form.get("location", "").strip(),
        "public_email": request.form.get("public_email", "").strip(),
        "website": request.form.get("website", "").strip(),
        "show_public_email": parse_bool("show_public_email"),
        "show_public_profile": parse_bool("show_public_profile"),
    }
    existing = service.get_public_profile(requested_key)
    profile_payload["avatar_filename"] = existing.get("avatar_filename", "")

    avatar = request.files.get("avatar_file")
    if avatar and avatar.filename:
        raw = avatar.read()
        try:
            optimized, avatar_name = optimize_avatar_upload(raw, avatar.filename)
            root = avatar_root()
            root.mkdir(parents=True, exist_ok=True)
            (root / avatar_name).write_bytes(optimized)
            profile_payload["avatar_filename"] = avatar_name
        except SettingsValidationError as error:
            profile_payload["avatar_filename"] = existing.get("avatar_filename", "")
            return render_template(
                "settings/profile.html",
                errors=[str(error)],
                profile_key=requested_key,
                form_data={**existing, **profile_payload},
            ), 400

    try:
        saved = service.save_public_profile(profile_payload, requested_key)
    except SettingsValidationError as error:
        return render_template(
            "settings/profile.html",
            errors=[str(error)],
            profile_key=requested_key,
            form_data={**existing, **profile_payload},
        ), 400
    return render_template(
        "settings/profile.html",
        errors=[],
        profile_key=requested_key,
        form_data=saved,
        saved=True,
    )


@settings_bp.get("/profile/avatar/<avatar_name>")
def profile_avatar_file(avatar_name: str):
    path = safe_avatar_path(avatar_name)
    if path is None:
        abort(404)
    return send_file(path, mimetype="image/jpeg", conditional=True, max_age=300)


@settings_bp.route("/branding", methods=["GET", "POST"])
def branding() -> str:
    service = get_settings_service()
    if request.method == "GET":
        return render_template("settings/branding.html", errors=[], form_data=service.get_dispatch_branding())

    payload = {
        "enabled": parse_bool("enabled"),
        "organization_name": request.form.get("organization_name", "").strip(),
        "footer_text": request.form.get("footer_text", "").strip(),
        "logo_text": request.form.get("logo_text", "").strip(),
    }
    try:
        saved = service.save_dispatch_branding(payload)
    except SettingsValidationError as error:
        return render_template("settings/branding.html", errors=[str(error)], form_data=payload), 400
    return render_template("settings/branding.html", errors=[], form_data=saved, saved=True)
