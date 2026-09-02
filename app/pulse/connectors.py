from __future__ import annotations

from hashlib import sha256
from typing import Any


class SignalNormalizer:
    def normalize(self, payload: dict[str, Any], *, source: dict[str, Any]) -> dict[str, Any]:
        text = str(payload.get("text") or payload.get("title") or payload.get("summary") or "").strip()
        url = str(payload.get("url") or payload.get("link") or "").strip()
        published_at = str(payload.get("published_at") or payload.get("published") or "")
        raw_hash = sha256(f"{source.get('id')}|{url}|{text}".encode("utf-8")).hexdigest()
        return {
            "source": source.get("name", ""),
            "source_type": source.get("type", "desconocida"),
            "source_id": source.get("id", ""),
            "author": payload.get("author", ""),
            "text": text,
            "url": url,
            "published_at": published_at,
            "media": payload.get("media", []),
            "location": payload.get("location", ""),
            "keywords": payload.get("keywords", []),
            "metadata": payload,
            "reliability": source.get("historical_reliability", source.get("reputation", 35)),
            "raw_payload_hash": raw_hash,
        }


class RSSConnector:
    platform = "rss"

    def __init__(self, timeout_seconds: int = 8):
        self.timeout_seconds = timeout_seconds

    def configured(self, source: dict[str, Any]) -> bool:
        return bool(source.get("active") and source.get("url"))


class TelegramConnector:
    platform = "telegram"

    def configured(self, source: dict[str, Any]) -> bool:
        return bool(source.get("active") and source.get("metadata", {}).get("credentials_configured"))
