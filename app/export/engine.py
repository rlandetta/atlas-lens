from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from time import perf_counter

from app.export.builders import build_docx, build_html, build_pdf
from app.export.builders.zip_builder import build_zip_archive
from app.export.builders.image_sources import resolve_original_path
from app.export.manifest import build_manifest
from app.export.models import ExportFile, ExportPhoto, ExportRequest, ExportResult
from app.export.naming import ExportNamingService
from app.export.template_renderer import render_caption

ZIP_MIMETYPE = "application/zip"
DOCX_MIMETYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
HTML_MIMETYPE = "text/html; charset=utf-8"
PDF_MIMETYPE = "application/pdf"
DOCUMENT_BUILDERS = {
    "docx": ("docx", DOCX_MIMETYPE, build_docx),
    "html": ("html", HTML_MIMETYPE, build_html),
    "pdf": ("pdf", PDF_MIMETYPE, build_pdf),
}


def export_filename(names, export_format: str) -> str:
    return {
        "docx": names.docx_filename,
        "html": names.html_filename,
        "pdf": names.pdf_filename,
    }.get(export_format, f"{names.base_name}.{export_format}")


def normalize_omitted_photo(item: dict, *, stage: str = "export", reason: str = "") -> dict:
    return {
        "id": str(item.get("id", "")),
        "filename": str(item.get("filename") or item.get("name") or "Fotografía"),
        "stage": str(item.get("stage") or stage),
        "reason": str(item.get("reason") or reason or "No se pudo procesar."),
    }


def normalize_requested_photo(item: dict) -> dict:
    return {
        "id": str(item.get("id", "")),
        "filename": str(item.get("filename") or item.get("name") or "Fotografía"),
    }


def build_coverage_metadata(coverage_id: str, coverage: dict) -> dict:
    return {
        "coverage_id": coverage_id,
        "coverage_name": coverage.get("coverage_name", ""),
        "submit_date": coverage.get("submit_date", ""),
        "event_date": coverage.get("event_date", ""),
        "city": coverage.get("city", ""),
        "country": coverage.get("country", ""),
        "agency": coverage.get("agency", ""),
        "photographer": coverage.get("photographer", ""),
        "editor": coverage.get("editor", ""),
    }


class ExportEngine:
    def __init__(self, naming_service: ExportNamingService | None = None):
        self.naming_service = naming_service or ExportNamingService()

    def build_export(
        self,
        *,
        coverage_id: str,
        coverage: dict,
        photos: list[dict],
        request: ExportRequest,
        warnings: tuple[str, ...] = (),
    ) -> ExportResult:
        started_at = perf_counter()
        created_at = datetime.now(timezone.utc)
        names = self.naming_service.build_names(coverage, request.output_name)
        selected_formats = tuple(dict.fromkeys(request.formats))
        export_photos = [
            self.build_export_photo(coverage, photo, request.template)
            for photo in photos
        ]
        omitted_photos = [normalize_omitted_photo(item) for item in request.omitted_photos]
        requested_photos = [normalize_requested_photo(item) for item in request.requested_photos]
        persisted_ids = {str(photo.get("id", "")) for photo in photos if str(photo.get("id", ""))}
        persisted_filenames = {str(photo.get("filename") or photo.get("name") or "") for photo in photos}
        for item in requested_photos:
            if (
                (item["id"] and item["id"] in persisted_ids)
                or (item["filename"] and item["filename"] in persisted_filenames)
            ):
                continue
            omitted_photos.append(normalize_omitted_photo(
                item,
                stage="persistence",
                reason="No está asociada a la cobertura persistida.",
            ))
        processable_photos = []
        omit_missing_captions = bool(request.requested_photos)
        for photo, export_photo in zip(photos, export_photos):
            if omit_missing_captions and request.include_captions and not str(export_photo.caption).strip():
                omitted_photos.append(normalize_omitted_photo(
                    {
                        "id": export_photo.id,
                        "filename": export_photo.filename,
                        "stage": "caption",
                        "reason": "Caption ausente.",
                    }
                ))
                continue
            if resolve_original_path(export_photo) is None and not export_photo.data_url:
                omitted_photos.append(normalize_omitted_photo(
                    {
                        "id": export_photo.id,
                        "filename": export_photo.filename,
                        "stage": "export",
                        "reason": "Archivo no disponible para exportación.",
                    }
                ))
                continue
            processable_photos.append(export_photo)
        requested_photo_count = (
            request.requested_photo_count
            if request.requested_photo_count is not None
            else len(export_photos) + len(request.omitted_photos)
        )
        if int(requested_photo_count or 0) > 0 and not processable_photos:
            omitted_tuple = tuple(omitted_photos)
            return ExportResult(
                filename="",
                mimetype="",
                content=b"",
                files=(),
                formats_generated=(),
                files_created=(),
                destination=request.destination,
                warnings=warnings,
                duration=perf_counter() - started_at,
                photo_count=len(export_photos),
                requested_photo_count=(
                    int(requested_photo_count)
                    if requested_photo_count is not None
                    else len(export_photos) + len(omitted_tuple)
                ),
                persisted_photo_count=len(export_photos),
                exported_photo_count=0,
                captions_included=0,
                omitted_photos=omitted_tuple,
                status="FAILED",
                created_at=created_at,
            )
        coverage_metadata = build_coverage_metadata(coverage_id, coverage)
        manifest = build_manifest(
            coverage_id=coverage_id,
            coverage=coverage,
            created_at=created_at,
            template=request.template,
            photos=processable_photos,
        )

        files: list[ExportFile] = []
        document_formats = tuple(export_format for export_format in selected_formats if export_format in DOCUMENT_BUILDERS)
        package_required = bool(request.include_photos or len(document_formats) > 1)
        direct_document_formats = () if package_required else document_formats

        for export_format in direct_document_formats:
            if export_format not in DOCUMENT_BUILDERS:
                continue
            extension, mimetype, builder = DOCUMENT_BUILDERS[export_format]
            filename = export_filename(names, extension)
            content = builder(processable_photos, coverage_metadata)
            files.append(ExportFile(
                format=export_format,
                filename=filename,
                mimetype=mimetype,
                content=content,
                type="document",
                path=filename,
            ))

        if package_required:
            zip_request = replace(request, formats=document_formats)
            zip_content, zip_files_created = build_zip_archive(
                request=zip_request,
                names=names,
                coverage_metadata=coverage_metadata,
                manifest=manifest,
                photos=processable_photos,
            )
            files.append(ExportFile(
                format="zip",
                filename=names.zip_filename,
                mimetype=ZIP_MIMETYPE,
                content=zip_content,
                type="archive",
                path=names.zip_filename,
            ))
            zip_filename = names.zip_filename
            archive_path = names.zip_filename
        else:
            zip_files_created = ()
            zip_filename = ""
            archive_path = ""

        if not files:
            omitted_tuple = tuple(omitted_photos)
            return ExportResult(
                filename="",
                mimetype="",
                content=b"",
                files=(),
                formats_generated=(),
                files_created=(),
                archive_path="",
                zip_filename="",
                destination=request.destination,
                warnings=warnings,
                duration=perf_counter() - started_at,
                photo_count=len(export_photos),
                requested_photo_count=(
                    int(requested_photo_count)
                    if requested_photo_count is not None
                    else len(export_photos) + len(omitted_tuple)
                ),
                persisted_photo_count=len(export_photos),
                exported_photo_count=0,
                captions_included=0,
                omitted_photos=omitted_tuple,
                status="FAILED",
                created_at=created_at,
            )

        files_tuple = tuple(files)
        first_file = files_tuple[0]
        omitted_tuple = tuple(omitted_photos)
        exported_photo_count = len(processable_photos)
        expected_count = (
            int(requested_photo_count)
            if requested_photo_count is not None
            else len(export_photos) + len(omitted_tuple)
        )
        captions_included = sum(1 for photo in processable_photos if str(photo.caption).strip())
        status = "PARTIAL" if omitted_tuple or exported_photo_count < expected_count else "COMPLETE"
        return ExportResult(
            filename=first_file.filename,
            mimetype=first_file.mimetype,
            content=first_file.content,
            files=files_tuple,
            formats_generated=tuple(dict.fromkeys(tuple(document_formats) + tuple(export_file.format for export_file in files_tuple))),
            files_created=tuple(export_file.filename for export_file in files_tuple) + tuple(zip_files_created),
            archive_path=archive_path,
            zip_filename=zip_filename,
            destination=request.destination,
            warnings=warnings,
            duration=perf_counter() - started_at,
            photo_count=len(export_photos),
            requested_photo_count=expected_count,
            persisted_photo_count=len(export_photos),
            exported_photo_count=exported_photo_count,
            captions_included=captions_included,
            omitted_photos=omitted_tuple,
            status=status,
            created_at=created_at,
        )

    def build_export_photo(self, coverage: dict, photo: dict, template: str) -> ExportPhoto:
        caption = render_caption(template, coverage, photo)
        return ExportPhoto(
            id=str(photo.get("id", "")),
            filename=str(photo.get("name", "photo")),
            caption=caption,
            status=str(photo.get("caption_status", "Sin editar")),
            photographer=str(coverage.get("photographer", "")),
            editor=str(coverage.get("editor", "")),
            metadata={
                "id": photo.get("id", ""),
                "filename": photo.get("name", ""),
                "size": photo.get("size", 0),
                "type": photo.get("type", ""),
                "width": photo.get("width"),
                "height": photo.get("height"),
                "caption_status": photo.get("caption_status", "Sin editar"),
                "is_drone": bool(photo.get("is_drone", False)),
            },
            data_url=str(photo.get("data_url", "")),
            storage_path=str(photo.get("storage_path", "")),
            flow_path=str(photo.get("flow_path", "")),
            available_on_disk=photo.get("available_on_disk", True) is not False,
        )
