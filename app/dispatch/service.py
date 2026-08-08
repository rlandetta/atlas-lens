from __future__ import annotations

import random
from copy import deepcopy
from datetime import datetime, timezone

from app.dispatch.models import (
    DispatchValidationError,
    ShipmentDraft,
    build_shipment,
    utc_now_iso,
    validate_transition,
)
from app.dispatch.store import DispatchShipmentStore
from app.export.models import ExportResult
from app.lens_read_service import LensReadError, LensReadService


class DispatchHandoffService:
    def prepare(self, coverage: dict, result: ExportResult) -> dict:
        payload = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "prepared",
            "destination": "dispatch",
            "formats": list(result.formats_generated),
            "files": [
                {
                    "filename": export_file.filename,
                    "format": export_file.format,
                    "type": export_file.type,
                    "mimetype": export_file.mimetype,
                    "size": export_file.size,
                    "path": export_file.path,
                }
                for export_file in result.files
            ],
            "zip": result.zip_filename,
            "photo_count": result.photo_count,
            "total_size": result.total_size,
            "warnings": list(result.warnings),
        }
        queue = coverage.setdefault("dispatch_queue", [])
        queue.insert(0, payload)
        del queue[25:]
        return payload


class ShipmentService:
    def __init__(self, *, store: DispatchShipmentStore, lens_reader: LensReadService):
        self.store = store
        self.lens_reader = lens_reader

    def create_shipment(
        self,
        *,
        name: str,
        coverage_id: str,
        photo_ids: list[str],
        recipients: list[dict[str, str]],
        delivery_note: str = "",
        channel: str = "manual",
        channel_id: str = "",
        channel_name_snapshot: str = "",
        delivery_method: str = "download_link",
        delivery_link_id: str = "",
        delivery_package: dict | None = None,
        remote_path: str = "",
        export_reference: dict | None = None,
        status: str = "Borrador",
        scheduled_at: str = "",
        timezone: str = "America/Guayaquil",
        include_caption_docx: bool = False,
        requested_delivery_mode: str = "draft",
    ) -> dict:
        normalized_photo_ids = [str(photo_id) for photo_id in photo_ids if str(photo_id)]
        if not normalized_photo_ids and not include_caption_docx:
            raise DispatchValidationError("Seleccione al menos una fotografía o incluya el documento Word con captions.")

        try:
            coverage = self.lens_reader.get_coverage(coverage_id)
            photos = self.lens_reader.get_approved_photos_by_ids(coverage_id, normalized_photo_ids)
        except LensReadError as error:
            raise DispatchValidationError(str(error)) from error

        if len(photos) != len(normalized_photo_ids):
            raise DispatchValidationError("No todas las fotografías seleccionadas tienen caption y archivo disponible.")

        draft = ShipmentDraft(
            name=name,
            coverage_id=coverage_id,
            photo_ids=normalized_photo_ids,
            recipients=recipients,
            delivery_note=delivery_note,
            channel=channel,
            channel_id=channel_id,
            channel_name_snapshot=channel_name_snapshot,
            delivery_method=delivery_method,
            delivery_link_id=delivery_link_id,
            delivery_package=deepcopy(delivery_package or {}),
            remote_path=remote_path,
            export_reference=deepcopy(export_reference or {}),
            include_caption_docx=include_caption_docx,
            requested_delivery_mode=requested_delivery_mode,
            status=status,
            scheduled_at=scheduled_at,
            timezone=timezone,
        )
        shipment = build_shipment(
            shipment_id=self.build_shipment_id(),
            draft=draft,
            coverage_snapshot=self.build_coverage_snapshot(coverage_id, coverage),
            photo_snapshots=photos,
        )
        return self.store.create(shipment)

    def get_shipment(self, shipment_id: str) -> dict | None:
        return self.store.get(shipment_id)

    def list_shipments(self) -> list[dict]:
        return self.store.list_shipments()

    def update_shipment(self, shipment_id: str, updates: dict) -> dict:
        shipment = self.store.get(shipment_id)
        if shipment is None:
            raise DispatchValidationError("No existe el despacho solicitado.")
        if shipment.get("status") not in {"Borrador", "Programado", "Error"}:
            raise DispatchValidationError("Este despacho no puede editarse en su estado actual.")

        next_shipment = deepcopy(shipment)
        editable_fields = (
            "name",
            "photo_ids",
            "photo_snapshots",
            "recipients",
            "delivery_note",
            "channel",
            "channel_id",
            "channel_name_snapshot",
            "delivery_method",
            "delivery_link_id",
            "delivery_package",
            "remote_path",
            "export_reference",
            "include_caption_docx",
            "requested_delivery_mode",
            "status",
            "scheduled_at",
            "timezone",
        )
        for field in editable_fields:
            if field in updates:
                next_shipment[field] = deepcopy(updates[field])
        timestamp = utc_now_iso()
        next_shipment["updated_at"] = timestamp
        history = next_shipment.setdefault("history", [])
        note = "Programación actualizada." if updates.get("schedule_changed") else "Despacho editado."
        history.insert(0, {"status": next_shipment.get("status", ""), "created_at": timestamp, "note": note})
        return self.store.update(shipment_id, next_shipment)

    def record_delivery_ready(
        self,
        shipment_id: str,
        *,
        delivery_package: dict,
        delivery_link_id: str = "",
        remote_path: str = "",
        note: str = "Entrega preparada.",
        status: str = "Listo",
        error: str = "",
    ) -> dict:
        shipment = self.store.get(shipment_id)
        if shipment is None:
            raise DispatchValidationError("No existe el despacho solicitado.")
        timestamp = utc_now_iso()
        next_shipment = deepcopy(shipment)
        next_shipment["status"] = status
        next_shipment["delivery_package"] = deepcopy(delivery_package)
        if delivery_link_id:
            next_shipment["delivery_link_id"] = delivery_link_id
        if remote_path:
            next_shipment["remote_path"] = remote_path
        next_shipment["updated_at"] = timestamp
        if status in {"Enviado", "Entregado"}:
            next_shipment["sent_at"] = timestamp
        next_shipment["last_error"] = error
        next_shipment.setdefault("history", []).insert(0, {
            "status": status,
            "created_at": timestamp,
            "note": note,
        })
        return self.store.update(shipment_id, next_shipment)

    def duplicate_shipment(self, shipment_id: str) -> dict:
        shipment = self.store.get(shipment_id)
        if shipment is None:
            raise DispatchValidationError("No existe el despacho solicitado.")
        if shipment.get("status") not in {"Borrador", "Programado", "Enviado", "Error", "Cancelado"}:
            raise DispatchValidationError("Este despacho no puede duplicarse en su estado actual.")

        timestamp = utc_now_iso()
        duplicated = deepcopy(shipment)
        duplicated["id"] = self.build_shipment_id()
        duplicated["name"] = f"Copia de {shipment.get('name', '').strip() or shipment_id}"
        duplicated["status"] = "Borrador"
        duplicated["scheduled_at"] = ""
        duplicated["sent_at"] = ""
        duplicated["delivery_link_id"] = ""
        duplicated["delivery_package"] = {}
        duplicated["remote_path"] = ""
        duplicated["last_attempt_at"] = ""
        duplicated["attempt_count"] = 0
        duplicated["last_error"] = ""
        duplicated["requested_delivery_mode"] = "draft"
        duplicated["created_at"] = timestamp
        duplicated["updated_at"] = timestamp
        duplicated["history"] = [{
            "status": "Borrador",
            "created_at": timestamp,
            "note": f"Despacho duplicado desde {shipment_id}.",
        }]
        return self.store.create(duplicated)

    def delete_shipment_record(self, shipment_id: str) -> dict:
        shipment = self.store.get(shipment_id)
        if shipment is None:
            raise DispatchValidationError("No existe el despacho solicitado.")
        if shipment.get("status") not in {"Borrador", "Cancelado"}:
            raise DispatchValidationError("Solo se pueden eliminar despachos en borrador o cancelados.")
        return self.store.delete(shipment_id)

    def delete_cancelled_shipments(self) -> int:
        deleted_count = 0
        for shipment in self.store.list_shipments():
            if shipment.get("status") == "Cancelado":
                self.store.delete(str(shipment.get("id", "")))
                deleted_count += 1
        return deleted_count

    def delete_draft(self, shipment_id: str) -> dict:
        return self.delete_shipment_record(shipment_id)

    def transition_status(self, shipment_id: str, next_status: str, note: str = "") -> dict:
        shipment = self.store.get(shipment_id)
        if shipment is None:
            raise DispatchValidationError("No existe el despacho solicitado.")

        validate_transition(str(shipment.get("status", "")), next_status)
        timestamp = utc_now_iso()
        next_shipment = deepcopy(shipment)
        next_shipment["status"] = next_status
        next_shipment["updated_at"] = timestamp
        history = next_shipment.setdefault("history", [])
        history.insert(0, {
            "status": next_status,
            "created_at": timestamp,
            "note": note.strip() or f"Estado cambiado a {next_status}.",
        })
        return self.store.update(shipment_id, next_shipment)

    def build_shipment_id(self) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        suffix = f"{random.randint(1000, 9999)}"
        return f"ship-{timestamp}-{suffix}"

    @staticmethod
    def build_coverage_snapshot(coverage_id: str, coverage: dict) -> dict:
        return {
            "id": coverage_id,
            "coverage_name": str(coverage.get("coverage_name", "")),
            "submit_date": str(coverage.get("submit_date", "")),
            "event_date": str(coverage.get("event_date", "")),
            "city": str(coverage.get("city", "")),
            "country": str(coverage.get("country", "")),
            "agency": str(coverage.get("agency", "")),
            "photographer": str(coverage.get("photographer", "")),
            "editor": str(coverage.get("editor", "")),
        }
