from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ImageReference:
    photo_id: str
    filename: str
    mime_type: str = "image/jpeg"
    size: int | None = None
    width: int | None = None
    height: int | None = None
    data_url: str | None = None


@dataclass(frozen=True)
class CoverageContext:
    coverage_id: str
    coverage_title: str
    description: str
    city: str
    country: str
    event_date: str
    send_date: str
    agency: str
    photographer: str
    editor: str
    known_people: tuple[str, ...]
    organizations: tuple[str, ...]
    keywords: tuple[str, ...]
    event_type: str
    notes: str
    photo_filename: str
    photo_sequence: int
    language: str
    editorial_template: str


@dataclass(frozen=True)
class AIRequest:
    image: ImageReference
    coverage_context: CoverageContext
    editorial_instructions: str
    language: str = "es"
    max_words: int = 60
    template: str = "xinhua"
    simulate_error: bool = False


@dataclass(frozen=True)
class AIResult:
    narration: str
    provider: str
    model: str
    status: str
    warnings: list[str] = field(default_factory=list)
    raw_metadata: dict[str, Any] = field(default_factory=dict)


class AIError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 500, provider: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.provider = provider
