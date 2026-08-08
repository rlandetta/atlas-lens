from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

SETTINGS_SCHEMA_VERSION = 1
SMTP_SECURITY_OPTIONS = ("ssl", "starttls")
CHANNEL_TYPES = ("download_link", "sftp", "smtp", "api")


class SettingsError(ValueError):
    pass


class SettingsStoreError(SettingsError):
    pass


class SettingsValidationError(SettingsError):
    pass


class SettingsSecretError(SettingsError):
    pass


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class OutboundChannelDraft:
    id: str
    name: str
    display_name: str
    channel_type: str
    sender_email: str
    reply_to: str
    smtp_host: str
    smtp_port: int
    smtp_security: str
    smtp_username: str
    credential_ref: str
    host: str = ""
    port: int | str = ""
    username: str = ""
    remote_path: str = ""
    host_key_fingerprint: str = ""
    is_active: bool = True
    is_default: bool = False


def validate_email(value: str, field_name: str) -> str:
    email = str(value or "").strip()
    if not email or "@" not in email or email.startswith("@") or email.endswith("@") or "." not in email.rsplit("@", 1)[-1]:
        raise SettingsValidationError(f"{field_name} debe ser un correo válido.")
    return email


def validate_channel_id(value: str) -> str:
    channel_id = str(value or "").strip()
    if not channel_id:
        raise SettingsValidationError("El identificador del canal es obligatorio.")
    if not all(character.isalnum() or character in {"-", "_"} for character in channel_id):
        raise SettingsValidationError("El identificador solo puede contener letras, números, guiones y guiones bajos.")
    return channel_id


def validate_port(value: Any, *, label: str = "El puerto SMTP") -> int:
    try:
        port = int(value)
    except (TypeError, ValueError) as error:
        raise SettingsValidationError(f"{label} debe ser numérico.") from error
    if port < 1 or port > 65535:
        raise SettingsValidationError(f"{label} debe estar entre 1 y 65535.")
    return port


def normalize_channel(channel: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(channel)
    normalized["id"] = validate_channel_id(normalized.get("id", ""))
    normalized["name"] = str(normalized.get("name", "")).strip()
    if not normalized["name"]:
        raise SettingsValidationError("El nombre del canal es obligatorio.")
    normalized["display_name"] = str(normalized.get("display_name", "")).strip() or normalized["name"]
    normalized["channel_type"] = str(normalized.get("channel_type", "") or "smtp").strip().lower()
    if normalized["channel_type"] not in CHANNEL_TYPES:
        raise SettingsValidationError("Tipo de canal no soportado.")
    normalized["sender_email"] = str(normalized.get("sender_email", "")).strip()
    if normalized["channel_type"] == "smtp":
        normalized["sender_email"] = validate_email(normalized["sender_email"], "El correo remitente")
    reply_to = str(normalized.get("reply_to", "")).strip()
    normalized["reply_to"] = validate_email(reply_to, "Reply-To") if reply_to else ""
    normalized["smtp_host"] = str(normalized.get("smtp_host", "")).strip()
    if normalized["channel_type"] == "smtp" and not normalized["smtp_host"]:
        raise SettingsValidationError("El servidor SMTP es obligatorio.")
    normalized["smtp_port"] = validate_port(normalized.get("smtp_port", 465) or 465)
    normalized["smtp_security"] = str(normalized.get("smtp_security", "")).strip().lower()
    if normalized["channel_type"] == "smtp" and normalized["smtp_security"] not in SMTP_SECURITY_OPTIONS:
        raise SettingsValidationError("La seguridad SMTP debe ser ssl o starttls.")
    if normalized["smtp_security"] not in SMTP_SECURITY_OPTIONS:
        normalized["smtp_security"] = "ssl"
    normalized["smtp_username"] = str(normalized.get("smtp_username", "")).strip()
    if normalized["channel_type"] == "smtp" and not normalized["smtp_username"]:
        raise SettingsValidationError("El usuario SMTP es obligatorio.")
    normalized["host"] = str(normalized.get("host") or normalized["smtp_host"] or "").strip()
    normalized["port"] = validate_port(normalized.get("port") or (22 if normalized["channel_type"] == "sftp" else normalized["smtp_port"]), label="El puerto")
    normalized["username"] = str(normalized.get("username") or normalized["smtp_username"] or "").strip()
    normalized["remote_path"] = str(normalized.get("remote_path", "")).strip()
    normalized["host_key_fingerprint"] = str(normalized.get("host_key_fingerprint", "")).strip()
    if normalized["channel_type"] == "sftp":
        if not normalized["host"]:
            raise SettingsValidationError("El servidor SFTP es obligatorio.")
        if not normalized["username"]:
            raise SettingsValidationError("El usuario SFTP es obligatorio.")
        if not normalized["remote_path"].startswith("/"):
            raise SettingsValidationError("La ruta remota SFTP debe iniciar con /.")
    normalized["credential_ref"] = str(normalized.get("credential_ref", "")).strip()
    if normalized["channel_type"] in {"smtp", "sftp"} and not normalized["credential_ref"]:
        raise SettingsValidationError("La referencia de credencial es obligatoria.")
    forbidden_keys = {"smtp_password", "app_password", "password", "token", "secret"}
    for key in forbidden_keys:
        normalized.pop(key, None)
    normalized["is_active"] = bool(normalized.get("is_active", True))
    normalized["is_default"] = bool(normalized.get("is_default", False))
    normalized.setdefault("created_at", utc_now_iso())
    normalized.setdefault("updated_at", normalized["created_at"])
    return normalized


def build_channel(draft: OutboundChannelDraft, *, created_at: str | None = None) -> dict[str, Any]:
    timestamp = created_at or utc_now_iso()
    return normalize_channel({
        "id": draft.id,
        "name": draft.name,
        "display_name": draft.display_name,
        "channel_type": draft.channel_type,
        "sender_email": draft.sender_email,
        "reply_to": draft.reply_to,
        "smtp_host": draft.smtp_host,
        "smtp_port": draft.smtp_port,
        "smtp_security": draft.smtp_security,
        "smtp_username": draft.smtp_username,
        "credential_ref": draft.credential_ref,
        "host": draft.host,
        "port": draft.port,
        "username": draft.username,
        "remote_path": draft.remote_path,
        "host_key_fingerprint": draft.host_key_fingerprint,
        "is_active": draft.is_active,
        "is_default": draft.is_default,
        "created_at": timestamp,
        "updated_at": timestamp,
    })


def empty_settings_payload() -> dict[str, Any]:
    return {
        "schema_version": SETTINGS_SCHEMA_VERSION,
        "outbound_channels": [],
    }
