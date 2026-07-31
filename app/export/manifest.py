from __future__ import annotations

from datetime import datetime

from app.export.models import EXPORT_VERSION, ExportPhoto


def build_manifest(
    *,
    coverage_id: str,
    coverage: dict,
    created_at: datetime,
    template: str,
    photos: list[ExportPhoto],
) -> dict:
    return {
        "coverage_id": coverage_id,
        "coverage_name": coverage.get("coverage_name", ""),
        "created_at": created_at.isoformat(),
        "template": template,
        "agency": coverage.get("agency", ""),
        "total_photos": len(photos),
        "export_version": EXPORT_VERSION,
        "photos": [
            {
                "filename": photo.filename,
                "caption": photo.caption,
                "status": photo.status,
                "photographer": photo.photographer,
                "editor": photo.editor,
            }
            for photo in photos
        ],
    }
