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

        next_shipment = deepcopy(shipment)
        for field in ("name", "recipients", "delivery_note", "channel", "export_reference"):
            if field in updates:
                next_shipment[field] = deepcopy(updates[field])
        next_shipment["updated_at"] = utc_now_iso()
        return self.store.update(shipment_id, next_shipment)

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
