from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

DISPATCH_STATUSES = (
    "Borrador",
    "Preparando",
    "Listo",
    "Enviado",
    "Entregado",
    "Error",
)

DISPATCH_TRANSITIONS = {
    "Borrador": {"Preparando", "Error"},
    "Preparando": {"Listo", "Error"},
    "Listo": {"Enviado", "Borrador", "Error"},
    "Enviado": {"Entregado", "Error"},
    "Entregado": set(),
    "Error": {"Borrador", "Preparando"},
}


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
    export_reference: dict[str, Any] | None = None


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
    if not draft.photo_ids:
        raise DispatchValidationError("Selecciona al menos una fotografía.")

    shipment = {
        "id": shipment_id,
        "name": name,
        "coverage_id": draft.coverage_id,
        "export_reference": deepcopy(draft.export_reference or {}),
        "photo_ids": [str(photo_id) for photo_id in draft.photo_ids],
        "photo_snapshots": normalize_photo_references(photo_snapshots),
        "coverage_snapshot": deepcopy(coverage_snapshot),
        "recipients": normalize_recipients(draft.recipients),
        "delivery_note": draft.delivery_note.strip(),
        "channel": draft.channel.strip() or "manual",
        "status": "Borrador",
        "created_at": timestamp,
        "updated_at": timestamp,
        "history": [
            {
                "status": "Borrador",
                "created_at": timestamp,
                "note": "Despacho creado.",
            }
        ],
    }
    return shipment

