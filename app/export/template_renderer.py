from __future__ import annotations

from datetime import datetime
import re
import unicodedata

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

XINHUA_CAPITALS = {
    "Argentina": "Buenos Aires",
    "Alemania": "Berlín",
    "Bolivia": "Sucre",
    "Brasil": "Brasilia",
    "Canadá": "Ottawa",
    "Chile": "Santiago",
    "China": "Beijing",
    "Colombia": "Bogotá",
    "Costa Rica": "San José",
    "Cuba": "La Habana",
    "Ecuador": "Quito",
    "España": "Madrid",
    "Estados Unidos": "Washington",
    "Francia": "París",
    "Italia": "Roma",
    "México": "Ciudad de México",
    "Panamá": "Ciudad de Panamá",
    "Paraguay": "Asunción",
    "Perú": "Lima",
    "Reino Unido": "Londres",
    "República Dominicana": "Santo Domingo",
    "Uruguay": "Montevideo",
    "Venezuela": "Caracas",
}

# Alias kept for callers/tests that imported the previous table name.
CAPITALS = XINHUA_CAPITALS
LOCALITY_TYPES = {"auto", "city", "locality", "capital"}
ADMIN_AREA_TYPES = {
    "province": "en la provincia de {admin_area}",
    "state": "en el estado de {admin_area}",
    "department": "en el departamento de {admin_area}",
    "region": "en la región de {admin_area}",
    "district": "en el distrito de {admin_area}",
}

CAPITALS_BY_COUNTRY_KEY: dict[str, str] = {}


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


def normalize_comparison_text(value: str) -> str:
    normalized = unicodedata.normalize("NFD", normalize_text(value).casefold())
    return "".join(
        character
        for character in normalized
        if unicodedata.category(character) != "Mn"
    )


CAPITALS_BY_COUNTRY_KEY.update({
    normalize_comparison_text(country): capital
    for country, capital in XINHUA_CAPITALS.items()
})


def bool_value(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def normalize_drone_narrative(value: str) -> str:
    narrative = normalize_text(value)
    if not narrative:
        return narrative

    patterns = (
        r"^una\s+vista\s+a[eé]rea\s+tomada\s+con\s+un\s+dron\s+(?:de\s+)?",
        r"^una\s+vista\s+a[eé]rea\s+tomada\s+con\s+dron\s+(?:de\s+)?",
        r"^vista\s+a[eé]rea\s+tomada\s+con\s+un\s+dron\s+(?:de\s+)?",
        r"^vista\s+a[eé]rea\s+tomada\s+con\s+dron\s+(?:de\s+)?",
        r"^una\s+vista\s+a[eé]rea\s+(?:de\s+)?",
        r"^vista\s+a[eé]rea\s+(?:de\s+)?",
    )
    for pattern in patterns:
        cleaned = re.sub(pattern, "", narrative, count=1, flags=re.IGNORECASE).strip()
        if cleaned != narrative and cleaned:
            return cleaned
    return narrative


def normalize_locality_type(value: str) -> str:
    normalized = normalize_text(value).casefold()
    return normalized if normalized in LOCALITY_TYPES else "auto"


def normalize_admin_area_type(value: str) -> str:
    normalized = normalize_text(value).casefold()
    return normalized if normalized in set(ADMIN_AREA_TYPES) | {"other"} else ""


def same_city(left: str, right: str) -> bool:
    return normalize_comparison_text(left) == normalize_comparison_text(right)


def format_admin_area(admin_area: str, admin_area_type: str) -> str:
    admin_area = normalize_text(admin_area)
    if not admin_area:
        return ""
    template = ADMIN_AREA_TYPES.get(normalize_admin_area_type(admin_area_type))
    if not template:
        return f"en {admin_area}"
    return template.format(admin_area=admin_area)


def append_unique_location_part(parts: list[str], value: str) -> None:
    clean_value = normalize_text(value)
    if not clean_value:
        return
    comparable = normalize_comparison_text(clean_value)
    if any(comparable == normalize_comparison_text(existing) for existing in parts):
        return
    parts.append(clean_value)


def format_xinhua_location(
    city: str,
    country: str,
    locality_type: str = "auto",
    admin_area: str = "",
    admin_area_type: str = "",
) -> str:
    city = normalize_text(city)
    country = normalize_text(country)
    locality_type = normalize_locality_type(locality_type)

    if not city:
        return ""
    if not country:
        return f"en {city}"

    capital = CAPITALS_BY_COUNTRY_KEY.get(normalize_comparison_text(country))
    if capital and same_city(city, capital):
        return f"en {city}, capital de {country}"
    if locality_type == "city":
        return f"en la ciudad de {city}, en {country}"
    parts = [f"en {city}"]
    admin_phrase = ""
    if (
        locality_type == "locality"
        and admin_area
        and not same_city(admin_area, city)
        and not same_city(admin_area, country)
    ):
        admin_phrase = format_admin_area(admin_area, admin_area_type)
    append_unique_location_part(parts, admin_phrase)
    append_unique_location_part(parts, f"en {country}")
    return ", ".join(parts)


def build_location_phrase(city: str, country: str) -> str:
    location = format_xinhua_location(city, country, "city")
    return f"{location}," if location else ""


def append_location_clause(text: str, location: str) -> str:
    text = normalize_text(text).rstrip()
    location = normalize_text(location)
    if not location:
        return text

    text = text.rstrip()
    if text.endswith(","):
        return f"{text} {location}"
    if text.endswith("."):
        text = text[:-1].rstrip()
    return f"{text}, {location}" if text else location


def append_date_clause(text: str, date_text: str) -> str:
    text = normalize_text(text).rstrip(" ,")
    return f"{text}, el {date_text}" if text else f"el {date_text}"


def render_xinhua_caption(coverage: dict, photo: dict) -> str:
    narrative = normalize_text(photo.get("caption_narrative", ""))
    if not narrative:
        return ""
    is_drone = bool_value(photo.get("is_drone", False))
    if is_drone:
        narrative = normalize_drone_narrative(narrative)

    send_date = coverage.get("submit_date", "")
    event_date = coverage.get("event_date", "") or send_date
    city = normalize_text(coverage.get("city", ""))
    country = normalize_text(coverage.get("country", ""))
    locality_type = normalize_locality_type(coverage.get("locality_type", "auto"))
    admin_area = normalize_text(coverage.get("admin_area", ""))
    admin_area_type = normalize_admin_area_type(coverage.get("admin_area_type", ""))
    agency = normalize_text(coverage.get("agency", "Xinhua")) or "Xinhua"
    photographer = normalize_text(coverage.get("photographer", ""))
    editor = normalize_text(coverage.get("editor_initials", "")) or normalize_text(coverage.get("editor", ""))

    header = f"({format_dateline_code(send_date)}) -- {city.upper()}, {format_header_date(send_date)} ({agency}) --"
    location = format_xinhua_location(city, country, locality_type, admin_area, admin_area_type)
    credit = f"({agency}/{photographer})" if photographer else f"({agency})"
    editor_credit = f" ({editor})" if editor else ""

    if is_drone and event_date and event_date != send_date:
        body = f"Vista aérea tomada con un dron el {format_long_date(event_date)} de {narrative}"
    elif is_drone:
        body = f"Vista aérea tomada con un dron de {narrative}"
    elif event_date and event_date != send_date:
        body = f"Imagen del {format_long_date(event_date)} de {narrative}"
    else:
        body = narrative

    body = append_location_clause(body, location)
    if not (event_date and event_date != send_date):
        body = append_date_clause(body, format_long_date(send_date))

    body = body.rstrip(" ,")
    return f"{header} {body}. {credit}{editor_credit}"


TEMPLATE_RENDERERS = {
    "xinhua": render_xinhua_caption,
}


def render_caption(template: str, coverage: dict, photo: dict) -> str:
    renderer = TEMPLATE_RENDERERS.get(template)
    if renderer is None:
        raise ValueError(f"Unsupported template: {template}")
    return renderer(coverage, photo)
