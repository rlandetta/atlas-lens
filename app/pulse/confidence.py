from __future__ import annotations

from collections import Counter
from typing import Any


class ConfidenceEngine:
    """Rule-based event confidence calculator for cheap first-pass verification."""

    def calculate(
        self,
        *,
        event: dict[str, Any],
        signals: list[dict[str, Any]],
        sources: dict[str, dict[str, Any]],
    ) -> int:
        independent_sources = {
            signal.get("source_id") or signal.get("source") or signal.get("author")
            for signal in signals
            if not signal.get("duplicate_of")
        }
        platforms = {
            sources.get(signal.get("source_id"), {}).get("platform", signal.get("source_type"))
            for signal in signals
            if not signal.get("duplicate_of")
        }
        official_count = sum(
            1
            for signal in signals
            if sources.get(signal.get("source_id"), {}).get("type") == "oficial"
            or signal.get("source_type") == "oficial"
        )
        duplicate_count = sum(1 for signal in signals if signal.get("duplicate_of"))
        rumor_count = self._keyword_hits(signals, {"rumor", "sin confirmar", "dicen", "posible"})
        contradiction_count = self._keyword_hits(signals, {"desmiente", "falso", "descarta", "no ocurrió"})
        media_count = sum(1 for signal in signals if signal.get("media"))

        score = 12
        score += min(len(independent_sources), 6) * 8
        score += min(len(platforms), 4) * 5
        score += min(official_count, 3) * 12
        score += min(media_count, 3) * 4
        if event.get("location") and self._has_location_overlap(event, signals):
            score += 8
        if len(signals) >= 2:
            score += 6
        score -= min(duplicate_count, 6) * 3
        score -= min(rumor_count, 4) * 5
        score -= min(contradiction_count, 4) * 10

        return max(0, min(100, score))

    @staticmethod
    def _keyword_hits(signals: list[dict[str, Any]], needles: set[str]) -> int:
        counter = Counter()
        for signal in signals:
            text = " ".join([signal.get("text", ""), " ".join(signal.get("keywords", []))]).lower()
            for needle in needles:
                if needle in text:
                    counter[needle] += 1
        return sum(counter.values())

    @staticmethod
    def _has_location_overlap(event: dict[str, Any], signals: list[dict[str, Any]]) -> bool:
        location = str(event.get("location") or "").lower()
        if not location:
            return False
        return any(location in str(signal.get("location") or "").lower() for signal in signals)
