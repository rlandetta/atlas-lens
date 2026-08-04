from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from app.dispatch.models import (
    DispatchTransitionError,
    DispatchValidationError,
    utc_now_iso,
    validate_transition,
)
from app.dispatch.store import DispatchShipmentStore


class DispatchScheduler:
    def __init__(self, store: DispatchShipmentStore):
        self.store = store
        self.invalid_shipments: list[dict[str, str]] = []

    def list_due_shipments(self, now: datetime | None = None) -> list[dict[str, Any]]:
        reference = self._aware_now(now)
        due_shipments = []
        invalid_shipments = []
        for shipment in self.store.list_shipments():
            if shipment.get("status") != "Programado":
                continue
            scheduled_at = self._parse_scheduled_at(shipment, invalid_shipments)
            if scheduled_at is None:
                continue
            if scheduled_at <= reference.astimezone(scheduled_at.tzinfo):
                due_shipments.append(deepcopy(shipment))
        self.invalid_shipments = invalid_shipments
        return due_shipments

    def claim_for_execution(self, shipment_id: str, now: datetime | None = None) -> dict[str, Any] | None:
        reference = self._aware_now(now)

        def claim(shipment: dict[str, Any]) -> dict[str, Any] | None:
            if shipment.get("status") != "Programado":
                return None
            scheduled_at = self._parse_scheduled_at(shipment, [])
            if scheduled_at is None:
                return None
            if scheduled_at > reference.astimezone(scheduled_at.tzinfo):
                return None

            timestamp = utc_now_iso()
            next_shipment = deepcopy(shipment)
            validate_transition(str(next_shipment.get("status", "")), "Enviando")
            next_shipment["status"] = "Enviando"
            next_shipment["updated_at"] = timestamp
            next_shipment["last_attempt_at"] = timestamp
            next_shipment["attempt_count"] = int(next_shipment.get("attempt_count") or 0) + 1
            next_shipment["last_error"] = ""
            next_shipment.setdefault("history", []).insert(0, {
                "status": "Enviando",
                "created_at": timestamp,
                "note": "Despacho reclamado para ejecución.",
            })
            return next_shipment

        return self.store.mutate(shipment_id, claim)

    def mark_attempt(self, shipment_id: str, error: str = "") -> dict[str, Any]:
        def record_attempt(shipment: dict[str, Any]) -> dict[str, Any]:
            next_shipment = deepcopy(shipment)
            next_shipment["last_attempt_at"] = utc_now_iso()
            if error.strip():
                next_shipment["last_error"] = error.strip()
            next_shipment["updated_at"] = next_shipment["last_attempt_at"]
            return next_shipment

        shipment = self.store.mutate(shipment_id, record_attempt)
        if shipment is None:
            raise DispatchValidationError("No existe el despacho solicitado.")
        return shipment

    def mark_sent(self, shipment_id: str) -> dict[str, Any]:
        def sent(shipment: dict[str, Any]) -> dict[str, Any]:
            if shipment.get("status") != "Enviando":
                raise DispatchTransitionError("Solo un despacho en Enviando puede marcarse como enviado.")
            timestamp = utc_now_iso()
            next_shipment = deepcopy(shipment)
            validate_transition(str(next_shipment.get("status", "")), "Enviado")
            next_shipment["status"] = "Enviado"
            next_shipment["sent_at"] = timestamp
            next_shipment["updated_at"] = timestamp
            next_shipment["last_error"] = ""
            next_shipment.setdefault("history", []).insert(0, {
                "status": "Enviado",
                "created_at": timestamp,
                "note": "Despacho marcado como enviado.",
            })
            return next_shipment

        shipment = self.store.mutate(shipment_id, sent)
        if shipment is None:
            raise DispatchValidationError("No existe el despacho solicitado.")
        return shipment

    def mark_error(self, shipment_id: str, error: str) -> dict[str, Any]:
        safe_error = error.strip() or "Error de despacho sin detalle adicional."

        def failed(shipment: dict[str, Any]) -> dict[str, Any]:
            if shipment.get("status") not in {"Programado", "Enviando"}:
                raise DispatchTransitionError("Solo un despacho programado o en envío puede marcarse con error.")
            timestamp = utc_now_iso()
            next_shipment = deepcopy(shipment)
            validate_transition(str(next_shipment.get("status", "")), "Error")
            next_shipment["status"] = "Error"
            next_shipment["updated_at"] = timestamp
            next_shipment["last_error"] = safe_error
            next_shipment.setdefault("history", []).insert(0, {
                "status": "Error",
                "created_at": timestamp,
                "note": safe_error,
            })
            return next_shipment

        shipment = self.store.mutate(shipment_id, failed)
        if shipment is None:
            raise DispatchValidationError("No existe el despacho solicitado.")
        return shipment

    def cancel_schedule(self, shipment_id: str) -> dict[str, Any]:
        def cancel(shipment: dict[str, Any]) -> dict[str, Any]:
            if shipment.get("status") != "Programado":
                raise DispatchTransitionError("Solo un despacho programado puede cancelarse.")
            timestamp = utc_now_iso()
            next_shipment = deepcopy(shipment)
            validate_transition(str(next_shipment.get("status", "")), "Cancelado")
            next_shipment["status"] = "Cancelado"
            next_shipment["updated_at"] = timestamp
            next_shipment.setdefault("history", []).insert(0, {
                "status": "Cancelado",
                "created_at": timestamp,
                "note": "Programación cancelada.",
            })
            return next_shipment

        shipment = self.store.mutate(shipment_id, cancel)
        if shipment is None:
            raise DispatchValidationError("No existe el despacho solicitado.")
        return shipment

    @staticmethod
    def _aware_now(now: datetime | None) -> datetime:
        if now is None:
            return datetime.now(timezone.utc)
        if now.tzinfo is None or now.utcoffset() is None:
            raise DispatchValidationError("La fecha de referencia debe incluir zona horaria.")
        return now

    @staticmethod
    def _parse_scheduled_at(
        shipment: dict[str, Any],
        invalid_shipments: list[dict[str, str]],
    ) -> datetime | None:
        scheduled_at = str(shipment.get("scheduled_at", "")).strip()
        if not scheduled_at:
            invalid_shipments.append({
                "id": str(shipment.get("id", "")),
                "error": "scheduled_at vacío.",
            })
            return None
        try:
            parsed = datetime.fromisoformat(scheduled_at)
        except ValueError:
            invalid_shipments.append({
                "id": str(shipment.get("id", "")),
                "error": "scheduled_at inválido.",
            })
            return None
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            invalid_shipments.append({
                "id": str(shipment.get("id", "")),
                "error": "scheduled_at sin zona horaria.",
            })
            return None
        return parsed
