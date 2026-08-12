from __future__ import annotations

from datetime import datetime

SPANISH_MONTHS = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)

CAPITALS = {
    "Argentina": "Buenos Aires",
    "Bolivia": "La Paz",
    "Brasil": "Brasilia",
    "Chile": "Santiago",
    "Colombia": "Bogotá",
    "Costa Rica": "San José",
    "Cuba": "La Habana",
    "Ecuador": "Quito",
    "El Salvador": "San Salvador",
    "Guatemala": "Ciudad de Guatemala",
    "Haití": "Puerto Príncipe",
    "Honduras": "Tegucigalpa",
    "Nicaragua": "Managua",
    "Panamá": "Ciudad de Panamá",
    "Paraguay": "Asunción",
    "Perú": "Lima",
    "República Dominicana": "Santo Domingo",
    "Uruguay": "Montevideo",
    "Venezuela": "Caracas",
}


def parse_iso_date(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None


def format_long_date(value: str) -> str:
    parsed = parse_iso_date(value)
    if parsed is None:
        return value or "fecha no definida"
    return f"{parsed.day} de {SPANISH_MONTHS[parsed.month - 1]} de {parsed.year}"


def format_header_date(value: str) -> str:
    parsed = parse_iso_date(value)
    if parsed is None:
        return value or "fecha no definida"
    return f"{parsed.day} {SPANISH_MONTHS[parsed.month - 1]}, {parsed.year}"


def format_dateline_code(value: str) -> str:
    parsed = parse_iso_date(value)
    if parsed is None:
        return "000000"
    return parsed.strftime("%y%m%d")


def normalize_text(value: str) -> str:
    return " ".join(str(value or "").split())


def same_city(left: str, right: str) -> bool:
    return normalize_text(left).casefold() == normalize_text(right).casefold()


def build_location_phrase(city: str, country: str) -> str:
    city = normalize_text(city)
    country = normalize_text(country)
    capital = CAPITALS.get(country)
    if capital and same_city(city, capital):
        return f"en la ciudad de {city}, capital de {country},"
    return f"en la ciudad de {city}, en {country}," if city and country else ""


def render_xinhua_caption(coverage: dict, photo: dict) -> str:
    narrative = normalize_text(photo.get("caption_narrative", ""))
    if not narrative:
        return ""

    send_date = coverage.get("submit_date", "")
    event_date = coverage.get("event_date", "") or send_date
    city = normalize_text(coverage.get("city", ""))
    country = normalize_text(coverage.get("country", ""))
    agency = normalize_text(coverage.get("agency", "Xinhua")) or "Xinhua"
    photographer = normalize_text(coverage.get("photographer", ""))
    editor = normalize_text(coverage.get("editor_initials", "")) or normalize_text(coverage.get("editor", ""))

    header = f"({format_dateline_code(send_date)}) -- {city.upper()}, {format_header_date(send_date)} ({agency}) --"
    location = build_location_phrase(city, country)
    credit = f"({agency}/{photographer})" if photographer else f"({agency})"
    editor_credit = f" ({editor})" if editor else ""

    if event_date and event_date != send_date:
        body = f"Imagen del {format_long_date(event_date)} de {narrative} {location}".strip()
    else:
        body = f"{narrative} {location} el {format_long_date(send_date)}".strip()

    body = body.rstrip()
    if body.endswith(","):
        body = body[:-1]
    return f"{header} {body}. {credit}{editor_credit}"


TEMPLATE_RENDERERS = {
    "xinhua": render_xinhua_caption,
}


def render_caption(template: str, coverage: dict, photo: dict) -> str:
    renderer = TEMPLATE_RENDERERS.get(template)
    if renderer is None:
        raise ValueError(f"Unsupported template: {template}")
    return renderer(coverage, photo)
