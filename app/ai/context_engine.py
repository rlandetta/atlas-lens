from dataclasses import asdict
import re

from app.ai.models import CoverageContext


def split_context_lines(value) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        source = "\n".join(str(item) for item in value)
    else:
        source = str(value or "")

    return tuple(
        line.strip()
        for line in re.split(r"[\n,;]+", source)
        if line.strip()
    )


def get_coverage_context_data(coverage: dict) -> dict:
    context = coverage.get("ai_context")
    if not isinstance(context, dict):
        context = {}
        coverage["ai_context"] = context

    return context


def normalize_context_payload(payload: dict) -> dict:
    return {
        "known_people": "\n".join(split_context_lines(payload.get("known_people", ""))),
        "organizations": "\n".join(split_context_lines(payload.get("organizations", ""))),
        "keywords": "\n".join(split_context_lines(payload.get("keywords", ""))),
        "notes": str(payload.get("notes", "") or "").strip(),
    }


class ContextEngine:
    def build(self, coverage_id: str, coverage: dict, photo: dict, photo_sequence: int = 0) -> CoverageContext:
        ai_context = get_coverage_context_data(coverage)
        return CoverageContext(
            coverage_id=str(coverage_id or ""),
            coverage_title=str(coverage.get("coverage_name", "") or ""),
            description=str(ai_context.get("description", "") or coverage.get("coverage_name", "") or ""),
            city=str(coverage.get("city", "") or ""),
            country=str(coverage.get("country", "") or ""),
            event_date=str(coverage.get("event_date", "") or ""),
            send_date=str(coverage.get("submit_date", "") or ""),
            agency=str(coverage.get("agency", "") or ""),
            photographer=str(coverage.get("photographer", "") or ""),
            editor=str(coverage.get("editor_name", coverage.get("editor", "")) or ""),
            known_people=split_context_lines(ai_context.get("known_people", "")),
            organizations=split_context_lines(ai_context.get("organizations", "")),
            keywords=split_context_lines(ai_context.get("keywords", "")),
            event_type=str(ai_context.get("event_type", "") or ""),
            notes=str(ai_context.get("notes", "") or ""),
            photo_filename=str(photo.get("name", "") or ""),
            photo_sequence=int(photo_sequence or 0),
            language="es",
            editorial_template="xinhua",
        )

    def to_json_payload(self, context: CoverageContext) -> dict:
        payload = asdict(context)
        payload["known_people"] = list(context.known_people)
        payload["organizations"] = list(context.organizations)
        payload["keywords"] = list(context.keywords)
        return {
            "coverage": {
                "coverage_id": payload["coverage_id"],
                "coverage_title": payload["coverage_title"],
                "description": payload["description"],
                "city": payload["city"],
                "country": payload["country"],
                "event_date": payload["event_date"],
                "send_date": payload["send_date"],
                "agency": payload["agency"],
                "photographer": payload["photographer"],
                "editor": payload["editor"],
                "event_type": payload["event_type"],
                "language": payload["language"],
                "editorial_template": payload["editorial_template"],
            },
            "photo": {
                "filename": payload["photo_filename"],
                "sequence": payload["photo_sequence"],
            },
            "known_people": payload["known_people"],
            "organizations": payload["organizations"],
            "keywords": payload["keywords"],
            "notes": payload["notes"],
            "future_sources": {
                "exif": {},
                "gps": {},
                "face_recognition": [],
                "ocr": "",
                "detected_objects": [],
                "classification": "",
                "related_news": [],
            },
        }
