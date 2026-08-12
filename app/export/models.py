from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

EXPORT_VERSION = "2.0"
SUPPORTED_EXPORT_FORMATS = ("zip", "docx", "html", "pdf")
SUPPORTED_CAPTION_FORMATS = ("docx", "html", "pdf")
SUPPORTED_SCOPES = ("coverage",)
SUPPORTED_TEMPLATES = ("xinhua",)
SUPPORTED_EXPORT_DESTINATIONS = ("download", "dispatch")


@dataclass(frozen=True)
class ExportRequest:
    coverage_id: str
    formats: tuple[str, ...] = ("docx",)
    include_photos: bool = True
    include_captions: bool = True
    include_metadata: bool = False
    include_manifest: bool = False
    output_name: str = ""
    template: str = "xinhua"
    scope: str = "coverage"
    requested_by: str = "Sistema"
    destination: str = "download"


ExportOptions = ExportRequest


@dataclass(frozen=True)
class ExportPhoto:
    id: str
    filename: str
    caption: str
    status: str
    photographer: str
    editor: str
    metadata: dict[str, Any]
    data_url: str = ""
    storage_path: str = ""
    flow_path: str = ""
    available_on_disk: bool = False


@dataclass(frozen=True)
class ExportFile:
    format: str
    filename: str
    mimetype: str
    content: bytes
    type: str = "document"
    path: str = ""

    @property
    def size(self) -> int:
        return len(self.content)


@dataclass(frozen=True)
class ExportResult:
    filename: str
    mimetype: str
    content: bytes
    files: tuple[ExportFile, ...] = ()
    formats_generated: tuple[str, ...] = ()
    files_created: tuple[str, ...] = ()
    archive_path: str = ""
    zip_filename: str = ""
    destination: str = "download"
    warnings: tuple[str, ...] = ()
    duration: float = 0
    photo_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def total_size(self) -> int:
        return sum(export_file.size for export_file in self.files)
