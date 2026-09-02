from __future__ import annotations

from datetime import datetime, timezone
import logging

from app.export.engine import ExportEngine
from app.export.models import (
    SUPPORTED_EXPORT_DESTINATIONS,
    SUPPORTED_EXPORT_FORMATS,
    SUPPORTED_SCOPES,
    SUPPORTED_TEMPLATES,
    ExportRequest,
    ExportResult,
)

LOGGER = logging.getLogger(__name__)


class ExportValidationError(ValueError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ExportWarningRequired(Exception):
    def __init__(self, warnings: tuple[str, ...]):
        super().__init__("Export requires warning confirmation.")
        self.warnings = warnings


class ExportService:
    def __init__(self, engine: ExportEngine | None = None):
        self.engine = engine or ExportEngine()

    def create_export(
        self,
        *,
        coverage_id: str,
        coverage: dict,
        request: ExportRequest,
        confirm_warnings: bool = False,
    ) -> ExportResult:
        self.validate_request(request)
        photos = self.select_photos(coverage, request)
        if not photos:
            raise ExportValidationError("No se puede exportar una cobertura vacía.")

        warnings = self.build_warnings(photos, request)
        if warnings and not confirm_warnings:
            raise ExportWarningRequired(warnings)

        result = self.engine.build_export(
            coverage_id=coverage_id,
            coverage=coverage,
            photos=photos,
            request=request,
            warnings=warnings,
        )
        if result.status == "PARTIAL" and request.destination == "dispatch" and not request.partial_confirmed:
            raise ExportWarningRequired((
                f"Esta exportación está incompleta. Se exportaron {result.exported_photo_count} de {result.requested_photo_count} fotografías.",
            ))
        self.record_history(coverage, request, result)
        if result.omitted_photos:
            for item in result.omitted_photos:
                LOGGER.info(
                    "LENS export omitted photo",
                    extra={
                        "coverage_id": coverage_id,
                        "photo_id": str(item.get("id", "")),
                        "photo_filename": str(item.get("filename", "")),
                        "action": "export",
                        "reason": str(item.get("reason", "")),
                        "stage": str(item.get("stage", "")),
                    },
                )
        return result

    def validate_request(self, request: ExportRequest):
        if request.scope not in SUPPORTED_SCOPES:
            raise ExportValidationError("Tipo de exportación no soportado.")
        if request.template not in SUPPORTED_TEMPLATES:
            raise ExportValidationError("Plantilla de exportación no soportada.")
        if request.destination not in SUPPORTED_EXPORT_DESTINATIONS:
            raise ExportValidationError("Destino de exportación no soportado.")
        if not request.formats and not request.include_photos:
            raise ExportValidationError("Selecciona al menos un formato.")
        unsupported_formats = set(request.formats) - set(SUPPORTED_EXPORT_FORMATS)
        if unsupported_formats:
            raise ExportValidationError("Formato de exportación no soportado.")
        if "zip" in request.formats and not (
            request.include_photos
            or request.include_captions
            or request.include_metadata
            or request.include_manifest
        ):
            raise ExportValidationError("Selecciona al menos un contenido para el ZIP.")

    def select_photos(self, coverage: dict, request: ExportRequest) -> list[dict]:
        photos = coverage.get("photos", [])
        return photos if isinstance(photos, list) else []

    def build_warnings(self, photos: list[dict], request: ExportRequest) -> tuple[str, ...]:
        wants_captions = bool(set(request.formats) - {"zip"}) or (
            "zip" in request.formats and request.include_captions
        )
        if not wants_captions:
            return ()
        missing = [
            str(photo.get("name", photo.get("id", "Fotografía")))
            for photo in photos
            if not str(photo.get("caption_narrative", "")).strip()
        ]
        if missing:
            return (f"{len(missing)} fotografía(s) sin caption: {', '.join(missing)}",)
        return ()

    def record_history(self, coverage: dict, request: ExportRequest, result: ExportResult):
        history = coverage.setdefault("export_history", [])
        export_id = f"exp-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        selected_photos = self.select_photos(coverage, request)
        omitted_ids = {str(item.get("id", "")) for item in result.omitted_photos if str(item.get("id", ""))}
        omitted_filenames = {str(item.get("filename", "")) for item in result.omitted_photos if str(item.get("filename", ""))}
        exported_photos = [
            photo
            for photo in selected_photos
            if str(photo.get("id", "")) not in omitted_ids
            and str(photo.get("filename") or photo.get("name") or "") not in omitted_filenames
        ]
        history.insert(0, {
            "export_id": export_id,
            "coverage_id": request.coverage_id,
            "coverage_name": str(coverage.get("coverage_name", "")),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "user": request.requested_by,
            "destination": request.destination,
            "type": request.destination,
            "format": "+".join(result.formats_generated).upper(),
            "formats": list(result.formats_generated),
            "filename": result.filename,
            "artifacts": [
                {
                    "filename": export_file.filename,
                    "format": export_file.format,
                    "type": export_file.type,
                    "size": export_file.size,
                    "path": export_file.path,
                }
                for export_file in result.files
            ],
            "requested_photo_count": result.requested_photo_count,
            "persisted_photo_count": result.persisted_photo_count,
            "exported_photo_count": result.exported_photo_count,
            "requested_photos": [
                {
                    "id": str(photo.get("id", "")),
                    "filename": str(photo.get("filename") or photo.get("name") or ""),
                }
                for photo in request.requested_photos
            ] or [
                {
                    "id": str(photo.get("id", "")),
                    "filename": str(photo.get("filename") or photo.get("name") or ""),
                }
                for photo in selected_photos
            ],
            "exported_photos": [
                {
                    "id": str(photo.get("id", "")),
                    "filename": str(photo.get("filename") or photo.get("name") or ""),
                }
                for photo in exported_photos
            ],
            "omitted_photos": list(result.omitted_photos),
            "captions_included": result.captions_included,
            "status": result.status,
            "warnings": list(result.warnings),
            "dispatch_reference": "",
            "photo_count": result.photo_count,
            "files_created": list(result.files_created),
            "file_count": len(result.files),
            "total_size": result.total_size,
            "zip": result.zip_filename,
            "duration": result.duration,
        })
        del history[25:]
