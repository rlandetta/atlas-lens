from __future__ import annotations

from datetime import datetime, timezone

from app.export.engine import ExportEngine
from app.export.models import (
    SUPPORTED_EXPORT_DESTINATIONS,
    SUPPORTED_EXPORT_FORMATS,
    SUPPORTED_SCOPES,
    SUPPORTED_TEMPLATES,
    ExportRequest,
    ExportResult,
)


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
        self.record_history(coverage, request, result)
        return result

    def validate_request(self, request: ExportRequest):
        if request.scope not in SUPPORTED_SCOPES:
            raise ExportValidationError("Tipo de exportación no soportado.")
        if request.template not in SUPPORTED_TEMPLATES:
            raise ExportValidationError("Plantilla de exportación no soportada.")
        if request.destination not in SUPPORTED_EXPORT_DESTINATIONS:
            raise ExportValidationError("Destino de exportación no soportado.")
        if not request.formats:
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
        history.insert(0, {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "user": request.requested_by,
            "type": request.destination,
            "format": "+".join(result.formats_generated).upper(),
            "formats": list(result.formats_generated),
            "photo_count": result.photo_count,
            "filename": result.filename,
            "files_created": list(result.files_created),
            "file_count": len(result.files),
            "total_size": result.total_size,
            "zip": result.zip_filename,
            "duration": result.duration,
        })
        del history[25:]
