from __future__ import annotations

from datetime import datetime, timezone

from app.export.models import ExportResult


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
