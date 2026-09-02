from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


EVENT_PRIORITIES = {"INFO", "SEGUIMIENTO", "IMPORTANTE", "URGENTE"}
VERIFICATION_STATES = {
    "Sin confirmar",
    "En observación",
    "En corroboración",
    "Probable",
    "Alta confianza",
    "Confirmado",
    "Descartado",
}
SOURCE_TYPES = {
    "oficial",
    "medio",
    "periodista",
    "ciudadano",
    "organización",
    "automatizada",
    "desconocida",
}
SOURCE_PLATFORMS = {
    "rss",
    "web",
    "medio",
    "oficial",
    "telegram",
    "x",
    "youtube",
    "otra",
}


class PulseStoreError(ValueError):
    pass


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def optional_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def optional_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if value is None:
        return default
    return bool(value)


def normalize_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def normalize_mapping(value: Any) -> dict[str, Any]:
    return deepcopy(value) if isinstance(value, dict) else {}


def bounded_score(value: Any) -> int:
    return max(0, min(100, optional_int(value, 0)))


def normalize_source(source: dict[str, Any]) -> dict[str, Any]:
    source_type = str(source.get("type") or "desconocida").strip().lower()
    platform = str(source.get("platform") or "otra").strip().lower()
    return {
        "id": str(source.get("id") or "").strip(),
        "name": str(source.get("name") or "Fuente sin nombre").strip(),
        "platform": platform if platform in SOURCE_PLATFORMS else "otra",
        "type": source_type if source_type in SOURCE_TYPES else "desconocida",
        "url": str(source.get("url") or "").strip(),
        "reputation": bounded_score(source.get("reputation", 40)),
        "historical_reliability": bounded_score(source.get("historical_reliability", 40)),
        "correct_events": optional_int(source.get("correct_events"), 0),
        "false_positives": optional_int(source.get("false_positives"), 0),
        "priority": str(source.get("priority") or "normal").strip().lower(),
        "active": optional_bool(source.get("active"), True),
        "last_checked_at": str(source.get("last_checked_at") or ""),
        "last_error": str(source.get("last_error") or ""),
    }


def normalize_signal(signal: dict[str, Any]) -> dict[str, Any]:
    now = utc_now_iso()
    return {
        "id": str(signal.get("id") or "").strip(),
        "event_id": str(signal.get("event_id") or "").strip(),
        "source": str(signal.get("source") or "").strip(),
        "source_type": str(signal.get("source_type") or "desconocida").strip().lower(),
        "source_id": str(signal.get("source_id") or "").strip(),
        "author": str(signal.get("author") or "").strip(),
        "text": str(signal.get("text") or "").strip(),
        "url": str(signal.get("url") or "").strip(),
        "published_at": str(signal.get("published_at") or ""),
        "detected_at": str(signal.get("detected_at") or now),
        "media": normalize_list(signal.get("media")),
        "location": str(signal.get("location") or "").strip(),
        "keywords": normalize_list(signal.get("keywords")),
        "metadata": normalize_mapping(signal.get("metadata")),
        "reliability": bounded_score(signal.get("reliability", 35)),
        "raw_payload_hash": str(signal.get("raw_payload_hash") or "").strip(),
        "duplicate_of": str(signal.get("duplicate_of") or "").strip(),
    }


def normalize_event(event: dict[str, Any]) -> dict[str, Any]:
    now = utc_now_iso()
    priority = str(event.get("priority") or "INFO").strip().upper()
    status = str(event.get("status") or "Sin confirmar").strip()
    return {
        "id": str(event.get("id") or "").strip(),
        "title": str(event.get("title") or "Evento sin título").strip(),
        "summary": str(event.get("summary") or "").strip(),
        "description": str(event.get("description") or event.get("summary") or "").strip(),
        "category": str(event.get("category") or "general").strip().lower(),
        "location": str(event.get("location") or "").strip(),
        "latitude": optional_float(event.get("latitude")),
        "longitude": optional_float(event.get("longitude")),
        "first_seen": str(event.get("first_seen") or now),
        "last_seen": str(event.get("last_seen") or event.get("first_seen") or now),
        "status": status if status in VERIFICATION_STATES else "Sin confirmar",
        "priority": priority if priority in EVENT_PRIORITIES else "INFO",
        "confidence_score": bounded_score(event.get("confidence_score", 0)),
        "source_count": optional_int(event.get("source_count"), 0),
        "official_source_count": optional_int(event.get("official_source_count"), 0),
        "signal_count": optional_int(event.get("signal_count"), 0),
        "tags": normalize_list(event.get("tags")),
        "keywords": normalize_list(event.get("keywords")),
        "evolution": normalize_list(event.get("evolution")),
        "reviewed": optional_bool(event.get("reviewed")),
        "followed": optional_bool(event.get("followed")),
        "archived": optional_bool(event.get("archived")),
        "image_url": str(event.get("image_url") or "").strip(),
        "pulse_conclusion": str(event.get("pulse_conclusion") or "").strip(),
        "information": str(event.get("information") or "").strip(),
        "created_coverage_id": str(event.get("created_coverage_id") or "").strip(),
    }


def empty_pulse_payload() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "events": {},
        "signals": {},
        "sources": {},
        "monitors": {},
        "rules": {},
        "alerts": {},
        "event_sources": [],
        "event_timeline": [],
        "x_usage": [],
    }


def normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise PulseStoreError("El archivo de PULSE tiene una estructura inválida.")
    normalized = empty_pulse_payload()
    normalized["schema_version"] = optional_int(payload.get("schema_version"), 1)
    normalized["events"] = {
        str(event_id): normalize_event(event)
        for event_id, event in normalize_mapping(payload.get("events")).items()
        if isinstance(event, dict)
    }
    normalized["signals"] = {
        str(signal_id): normalize_signal(signal)
        for signal_id, signal in normalize_mapping(payload.get("signals")).items()
        if isinstance(signal, dict)
    }
    normalized["sources"] = {
        str(source_id): normalize_source(source)
        for source_id, source in normalize_mapping(payload.get("sources")).items()
        if isinstance(source, dict)
    }
    for key in ("monitors", "rules", "alerts"):
        normalized[key] = normalize_mapping(payload.get(key))
    for key in ("event_sources", "event_timeline", "x_usage"):
        value = payload.get(key, [])
        normalized[key] = deepcopy(value) if isinstance(value, list) else []
    return normalized
