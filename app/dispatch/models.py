from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

DISPATCH_STATUSES = (
    "Borrador",
    "Preparando",
    "Listo",
    "Programado",
    "Enviando",
    "Enviado",
    "Entregado",
    "Error",
    "Cancelado",
)

DISPATCH_TRANSITIONS = {
    "Borrador": {"Preparando", "Programado", "Error"},
    "Preparando": {"Listo", "Programado", "Error"},
    "Listo": {"Programado", "Enviado", "Borrador", "Error"},
    "Programado": {"Enviando", "Borrador", "Cancelado", "Error"},
    "Enviando": {"Enviado", "Error"},
    "Enviado": {"Entregado", "Error"},
    "Entregado": set(),
    "Error": {"Borrador", "Preparando", "Programado"},
    "Cancelado": {"Borrador"},
}

DEFAULT_DISPATCH_TIMEZONE = "America/Guayaquil"
DELIVERY_METHODS = ("download_link", "download_link_email", "sftp", "smtp", "api")


class DispatchError(ValueError):
    pass


class DispatchStoreError(DispatchError):
    pass


class DispatchValidationError(DispatchError):
    pass


class DispatchTransitionError(DispatchValidationError):
    pass


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_status(status: str) -> str:
    if status not in DISPATCH_STATUSES:
        raise DispatchValidationError("Estado de despacho no soportado.")
    return status


def validate_transition(current_status: str, next_status: str) -> None:
    validate_status(current_status)
    validate_status(next_status)
    if next_status not in DISPATCH_TRANSITIONS[current_status]:
        raise DispatchTransitionError(
            f"No se permite cambiar de {current_status} a {next_status}."
        )


def normalize_shipment(shipment: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(shipment)
    normalized.setdefault("include_caption_docx", False)
    normalized.setdefault("requested_delivery_mode", "draft")
    normalized.setdefault("scheduled_at", "")
    normalized.setdefault("timezone", DEFAULT_DISPATCH_TIMEZONE)
    normalized.setdefault("channel_id", "")
    normalized.setdefault("channel_name_snapshot", str(normalized.get("channel", "")))
    normalized.setdefault("delivery_method", "download_link_email" if normalized.get("channel_id") else "download_link")
    if normalized["delivery_method"] not in DELIVERY_METHODS:
        normalized["delivery_method"] = "download_link_email"
    normalized.setdefault("delivery_link_id", "")
    normalized.setdefault("delivery_package", {})
    normalized.setdefault("remote_path", "")
    normalized.setdefault("sent_at", "")
    normalized.setdefault("last_attempt_at", "")
    normalized.setdefault("attempt_count", 0)
    normalized.setdefault("last_error", "")
    normalized.setdefault("history", [])
    return normalized


def normalize_recipients(recipients: list[dict[str, Any]]) -> list[dict[str, str]]:
    if not isinstance(recipients, list) or not recipients:
        raise DispatchValidationError("Agrega al menos un destinatario.")

    normalized = []
    for recipient in recipients:
        if not isinstance(recipient, dict):
            raise DispatchValidationError("Destinatario inválido.")
        name = str(recipient.get("name", "")).strip()
        email = str(recipient.get("email", "")).strip()
        if not name and not email:
            raise DispatchValidationError("Destinatario incompleto.")
        normalized.append({"name": name, "email": email})
    return normalized


def normalize_photo_references(photos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    snapshot = []
    for photo in photos:
        snapshot.append({
            "id": str(photo.get("id", "")),
            "name": str(photo.get("name", "")),
            "caption_status": str(photo.get("caption_status", "")),
            "caption_preview": str(photo.get("caption_narrative", "")),
        })
    return snapshot


@dataclass(frozen=True)
class ShipmentDraft:
    name: str
    coverage_id: str
    photo_ids: list[str]
    recipients: list[dict[str, str]]
    delivery_note: str = ""
    channel: str = "manual"
    channel_id: str = ""
    channel_name_snapshot: str = ""
    delivery_method: str = "download_link"
    delivery_link_id: str = ""
    delivery_package: dict[str, Any] | None = None
    remote_path: str = ""
    export_reference: dict[str, Any] | None = None
    include_caption_docx: bool = False
    requested_delivery_mode: str = "draft"
    status: str = "Borrador"
    scheduled_at: str = ""
    timezone: str = DEFAULT_DISPATCH_TIMEZONE


def build_shipment(
    *,
    shipment_id: str,
    draft: ShipmentDraft,
    coverage_snapshot: dict[str, Any],
    photo_snapshots: list[dict[str, Any]],
    created_at: str | None = None,
) -> dict[str, Any]:
    timestamp = created_at or utc_now_iso()
    name = draft.name.strip()
    if not name:
        raise DispatchValidationError("El despacho requiere nombre.")
    if not draft.coverage_id:
        raise DispatchValidationError("El despacho requiere cobertura.")
    if not draft.photo_ids and not draft.include_caption_docx:
        raise DispatchValidationError("Seleccione al menos una fotografía o incluya el documento Word con captions.")
    status = validate_status(draft.status)
    delivery_method = draft.delivery_method.strip() or "download_link"
    if delivery_method not in DELIVERY_METHODS:
        raise DispatchValidationError("Método de entrega no soportado.")

    shipment = {
        "id": shipment_id,
        "name": name,
        "coverage_id": draft.coverage_id,
        "export_reference": deepcopy(draft.export_reference or {}),
        "include_caption_docx": bool(draft.include_caption_docx),
        "requested_delivery_mode": draft.requested_delivery_mode.strip() or "draft",
        "photo_ids": [str(photo_id) for photo_id in draft.photo_ids],
        "photo_snapshots": normalize_photo_references(photo_snapshots),
        "coverage_snapshot": deepcopy(coverage_snapshot),
        "recipients": [] if delivery_method == "download_link" and not draft.recipients else normalize_recipients(draft.recipients),
        "delivery_note": draft.delivery_note.strip(),
        "channel": draft.channel.strip() or "manual",
        "channel_id": draft.channel_id.strip(),
        "channel_name_snapshot": draft.channel_name_snapshot.strip(),
        "delivery_method": delivery_method,
        "delivery_link_id": draft.delivery_link_id.strip(),
        "delivery_package": deepcopy(draft.delivery_package or {}),
        "remote_path": draft.remote_path.strip(),
        "status": status,
        "scheduled_at": draft.scheduled_at.strip(),
        "timezone": draft.timezone.strip() or DEFAULT_DISPATCH_TIMEZONE,
        "sent_at": "",
        "last_attempt_at": "",
        "attempt_count": 0,
        "last_error": "",
        "created_at": timestamp,
        "updated_at": timestamp,
        "history": [
            {
                "status": status,
                "created_at": timestamp,
                "note": "Despacho creado." if status == "Borrador" else f"Despacho creado en estado {status}.",
            }
        ],
    }
    return shipment
