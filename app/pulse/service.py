from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from app.pulse.budget import XBudgetController
from app.pulse.confidence import ConfidenceEngine
from app.pulse.demo import demo_payload
from app.pulse.models import normalize_payload, normalize_signal, utc_now_iso
from app.pulse.store import PulseStore


class PulseService:
    def __init__(self, store: PulseStore):
        self.store = store
        self.confidence = ConfidenceEngine()
        self.x_budget = XBudgetController()

    def dashboard(self, *, selected_event_id: str | None = None) -> dict[str, Any]:
        payload = self.store.snapshot()
        demo_mode = not payload["events"]
        if demo_mode:
            payload = normalize_payload(demo_payload())
        events = [
            self._decorate_event(event, payload)
            for event in payload["events"].values()
            if not event.get("archived")
        ]
        events.sort(key=lambda item: (self._priority_rank(item["priority"]), item["last_seen"]), reverse=True)
        selected = self._find_selected(events, selected_event_id)
        return {
            "events": events,
            "selected_event": selected,
            "summary": self._summary(events, payload),
            "x_budget": self.x_budget.status(payload.get("x_usage", [])),
            "demo_mode": demo_mode,
        }

    def ingest_signal(self, signal: dict[str, Any]) -> dict[str, Any]:
        payload = self.store.snapshot()
        normalized = normalize_signal(signal)
        normalized["id"] = normalized["id"] or self._build_id("sig", normalized["raw_payload_hash"] or normalized["text"])
        duplicate_id = self._find_duplicate_signal(payload, normalized)
        if duplicate_id:
            normalized["duplicate_of"] = duplicate_id
        event_id = normalized.get("event_id") or self._match_event(payload, normalized)
        normalized["event_id"] = event_id
        payload["signals"][normalized["id"]] = normalized
        if event_id in payload["events"]:
            related = [item for item in payload["signals"].values() if item.get("event_id") == event_id]
            event = payload["events"][event_id]
            event["last_seen"] = utc_now_iso()
            event["signal_count"] = len(related)
            event["source_count"] = len({item.get("source_id") or item.get("source") for item in related})
            event["official_source_count"] = sum(1 for item in related if item.get("source_type") == "oficial")
            event["confidence_score"] = self.confidence.calculate(
                event=event,
                signals=related,
                sources=payload["sources"],
            )
        self.store.save(payload)
        return deepcopy(normalized)

    def set_event_flag(self, event_id: str, flag: str, value: bool = True) -> dict[str, Any] | None:
        if flag not in {"reviewed", "followed", "archived"}:
            return None
        updated = self.store.mutate_event(event_id, lambda event: {**event, flag: value})
        if updated is None and self._seed_demo_event_if_needed(event_id):
            updated = self.store.mutate_event(event_id, lambda event: {**event, flag: value})
        return updated

    def mark_coverage_created(self, event_id: str, coverage_id: str) -> dict[str, Any] | None:
        updated = self.store.mutate_event(event_id, lambda event: {**event, "created_coverage_id": coverage_id, "reviewed": True})
        if updated is None and self._seed_demo_event_if_needed(event_id):
            updated = self.store.mutate_event(event_id, lambda event: {**event, "created_coverage_id": coverage_id, "reviewed": True})
        return updated

    def get_event(self, event_id: str) -> dict[str, Any] | None:
        payload = self.store.snapshot()
        if not payload["events"]:
            payload = normalize_payload(demo_payload())
        event = payload["events"].get(event_id)
        return self._decorate_event(event, payload) if event else None

    def _decorate_event(self, event: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        item = deepcopy(event)
        signals = [signal for signal in payload["signals"].values() if signal.get("event_id") == item["id"]]
        source_ids = {signal.get("source_id") for signal in signals if signal.get("source_id")}
        item["signals"] = signals
        item["sources"] = [payload["sources"][source_id] for source_id in source_ids if source_id in payload["sources"]]
        item["age_label"] = self._age_label(item.get("first_seen"))
        item["last_seen_label"] = self._age_label(item.get("last_seen"))
        return item

    @staticmethod
    def _summary(events: list[dict[str, Any]], payload: dict[str, Any]) -> dict[str, int]:
        return {
            "signals": len(payload["signals"]),
            "events": len(events),
            "important": sum(1 for event in events if event["priority"] == "IMPORTANTE"),
            "urgent": sum(1 for event in events if event["priority"] == "URGENTE"),
        }

    @staticmethod
    def _find_selected(events: list[dict[str, Any]], selected_event_id: str | None) -> dict[str, Any] | None:
        if selected_event_id:
            for event in events:
                if event["id"] == selected_event_id:
                    return event
        return events[0] if events else None

    @staticmethod
    def _priority_rank(priority: str) -> int:
        return {"INFO": 1, "SEGUIMIENTO": 2, "IMPORTANTE": 3, "URGENTE": 4}.get(priority, 0)

    @staticmethod
    def _build_id(prefix: str, value: str) -> str:
        digest = sha256(value.encode("utf-8")).hexdigest()[:12]
        return f"{prefix}-{digest}"

    @staticmethod
    def _find_duplicate_signal(payload: dict[str, Any], signal: dict[str, Any]) -> str:
        for signal_id, existing in payload["signals"].items():
            if existing.get("raw_payload_hash") and existing.get("raw_payload_hash") == signal.get("raw_payload_hash"):
                return signal_id
            if existing.get("url") and existing.get("url") == signal.get("url"):
                return signal_id
        return ""

    def _match_event(self, payload: dict[str, Any], signal: dict[str, Any]) -> str:
        signal_keywords = set(signal.get("keywords", []))
        for event_id, event in payload["events"].items():
            if signal.get("location") and event.get("location") and signal["location"].lower() in event["location"].lower():
                if signal_keywords.intersection(event.get("keywords", [])):
                    return event_id
        event_id = self._build_id("evt", f"{signal.get('location')}|{signal.get('text')[:80]}")
        payload["events"][event_id] = {
            "id": event_id,
            "title": signal.get("text", "Evento detectado")[:90],
            "summary": signal.get("text", ""),
            "category": "general",
            "location": signal.get("location", ""),
            "first_seen": signal.get("detected_at") or utc_now_iso(),
            "last_seen": signal.get("detected_at") or utc_now_iso(),
            "status": "Sin confirmar",
            "priority": "INFO",
            "confidence_score": 0,
            "source_count": 1,
            "official_source_count": 1 if signal.get("source_type") == "oficial" else 0,
            "signal_count": 1,
            "tags": [],
            "keywords": signal.get("keywords", []),
            "evolution": ["Evento creado desde señal normalizada."],
        }
        return event_id

    def _seed_demo_event_if_needed(self, event_id: str) -> bool:
        payload = self.store.snapshot()
        if payload["events"]:
            return False
        demo = normalize_payload(demo_payload())
        if event_id not in demo["events"]:
            return False
        self.store.save(demo)
        return True

    @staticmethod
    def _age_label(value: str | None) -> str:
        if not value:
            return "Sin fecha"
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
        delta = datetime.now(timezone.utc) - parsed
        minutes = max(0, int(delta.total_seconds() // 60))
        if minutes < 60:
            return f"hace {minutes} min"
        hours = minutes // 60
        if hours < 24:
            return f"hace {hours} h"
        return f"hace {hours // 24} d"
