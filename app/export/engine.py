from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from time import perf_counter

from app.export.builders import build_docx, build_html, build_pdf
from app.export.builders.zip_builder import build_zip_archive
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
        coverage_metadata = build_coverage_metadata(coverage_id, coverage)
        manifest = build_manifest(
            coverage_id=coverage_id,
            coverage=coverage,
            created_at=created_at,
            template=request.template,
            photos=export_photos,
        )

        files: list[ExportFile] = []
        for export_format in selected_formats:
            if export_format not in DOCUMENT_BUILDERS:
                continue
            extension, mimetype, builder = DOCUMENT_BUILDERS[export_format]
            filename = f"{names.base_name}.{extension}"
            content = builder(export_photos, coverage_metadata)
            files.append(ExportFile(
                format=export_format,
                filename=filename,
                mimetype=mimetype,
                content=content,
                type="document",
                path=filename,
            ))

        if "zip" in selected_formats:
            zip_caption_formats = tuple(
                export_format
                for export_format in selected_formats
                if export_format in DOCUMENT_BUILDERS
            )
            if request.include_captions and not zip_caption_formats:
                zip_caption_formats = ("docx",)
            zip_request = replace(request, formats=zip_caption_formats)
            zip_content, zip_files_created = build_zip_archive(
                request=zip_request,
                names=names,
                coverage_metadata=coverage_metadata,
                manifest=manifest,
                photos=export_photos,
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

        files_tuple = tuple(files)
        first_file = files_tuple[0]
        return ExportResult(
            filename=first_file.filename,
            mimetype=first_file.mimetype,
            content=first_file.content,
            files=files_tuple,
            formats_generated=tuple(export_file.format for export_file in files_tuple),
            files_created=tuple(export_file.filename for export_file in files_tuple) + tuple(zip_files_created),
            archive_path=archive_path,
            zip_filename=zip_filename,
            destination=request.destination,
            warnings=warnings,
            duration=perf_counter() - started_at,
            photo_count=len(export_photos),
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
            },
            data_url=str(photo.get("data_url", "")),
            storage_path=str(photo.get("storage_path", "")),
            flow_path=str(photo.get("flow_path", "")),
            available_on_disk=photo.get("available_on_disk", True) is not False,
        )
