from __future__ import annotations

import json
import logging
from zipfile import ZIP_DEFLATED, ZipFile

from app.export.builders import build_docx, build_html, build_pdf
from app.export.builders.image_sources import (
    ImageSourceError,
    decode_data_url as decode_image_data_url,
    load_required_image_source,
    photo_label,
)
from app.export.models import ExportPhoto, ExportRequest
from app.export.naming import ExportNames

logger = logging.getLogger(__name__)


def decode_data_url(data_url: str) -> bytes:
    image_bytes, _ = decode_image_data_url(data_url)
    return image_bytes


class ZipBuilder:
    def __init__(self, archive: ZipFile):
        self.archive = archive
        self.files_created: list[str] = []

    def write_bytes(self, path: str, content: bytes):
        self.archive.writestr(path, content)
        self.files_created.append(path)

    def write_json(self, path: str, payload: dict):
        self.write_bytes(
            path,
            json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        )

    def write_photo(self, photo: ExportPhoto):
        path = f"Fotografias/{photo.filename}"
        try:
            image_bytes, _ = load_required_image_source(photo)
        except ImageSourceError:
            logger.warning("ZIP export skipped unresolved original photo: %s", photo_label(photo))
            raise
        with self.archive.open(path, "w") as destination:
            destination.write(image_bytes)
        self.files_created.append(path)

    def write_package(
        self,
        *,
        request: ExportRequest,
        names: ExportNames,
        coverage_metadata: dict,
        manifest: dict,
        photos: list[ExportPhoto],
    ) -> tuple[str, ...]:
        if request.include_photos:
            for photo in photos:
                self.write_photo(photo)

        if request.include_captions:
            if "docx" in request.formats:
                self.write_bytes(names.docx_filename, build_docx(photos, coverage_metadata))
            if "html" in request.formats:
                self.write_bytes(names.html_filename, build_html(photos, coverage_metadata))
            if "pdf" in request.formats:
                self.write_bytes(names.pdf_filename, build_pdf(photos, coverage_metadata))

        if request.include_metadata:
            self.write_json(names.metadata_filename, {
                "coverage": coverage_metadata,
                "photos": [photo.metadata for photo in photos],
                "captions": [
                    {"filename": photo.filename, "caption": photo.caption, "status": photo.status}
                    for photo in photos
                ],
            })

        if request.include_manifest:
            self.write_json(names.manifest_filename, manifest)

        return tuple(self.files_created)


def build_zip_archive(
    *,
    request: ExportRequest,
    names: ExportNames,
    coverage_metadata: dict,
    manifest: dict,
    photos: list[ExportPhoto],
) -> tuple[bytes, tuple[str, ...]]:
    import io

    buffer = io.BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        files_created = ZipBuilder(archive).write_package(
            request=request,
            names=names,
            coverage_metadata=coverage_metadata,
            manifest=manifest,
            photos=photos,
        )
    return buffer.getvalue(), files_created
