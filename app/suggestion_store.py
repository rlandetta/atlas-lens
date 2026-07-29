import re
import unicodedata

SUGGESTION_FIELDS = ("agency", "photographer", "editor", "city")
SUGGESTION_LIMIT = 50

_suggestions: dict[str, list[dict[str, str]]] = {
    field: []
    for field in SUGGESTION_FIELDS
}


def normalize_value(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_value = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    return re.sub(r"\s+", " ", ascii_value).strip().lower()


def remember_value(field: str, value: str) -> None:
    if field not in _suggestions:
        return

    visible_value = " ".join((value or "").strip().split())
    if not visible_value:
        return

    key = normalize_value(visible_value)
    field_values = [
        item
        for item in _suggestions[field]
        if item["key"] != key
    ]
    field_values.insert(0, {"key": key, "value": visible_value})
    _suggestions[field] = field_values[:SUGGESTION_LIMIT]


def remember_coverage_values(coverage: dict[str, str]) -> None:
    for field in SUGGESTION_FIELDS:
        remember_value(field, coverage.get(field, ""))


def get_suggestions(field: str) -> list[str]:
    return [
        item["value"]
        for item in _suggestions.get(field, [])
    ]


def get_all_suggestions() -> dict[str, list[str]]:
    return {
        field: get_suggestions(field)
        for field in SUGGESTION_FIELDS
    }
