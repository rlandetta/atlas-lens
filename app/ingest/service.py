from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.ingest.store import IngestStore


@dataclass(frozen=True)
class IngestPhotoDraft:
    filename: str
    path: str
    source: str = ""
    received_at: str | None = None
    captured_at: str | None = None


class IngestService:
    def __init__(self, store: IngestStore, *, session_timeout_minutes: int = 60):
        self.store = store
        self.session_timeout = timedelta(minutes=session_timeout_minutes)

    def register_received_photo(self, draft: IngestPhotoDraft | dict[str, Any]) -> dict[str, Any]:
        photo_draft = self.normalize_draft(draft)
        received_at = self.parse_datetime(photo_draft.received_at) if photo_draft.received_at else datetime.now(timezone.utc)

        def mutation(payload: dict[str, list[dict[str, Any]]]):
            self.close_inactive_sessions(payload, now=received_at)
            session = self.get_active_session_from_payload(payload, now=received_at)
            if session is None:
                session = self.create_session(payload, received_at)
            photo = {
                "id": f"photo-{uuid4().hex}",
                "filename": photo_draft.filename,
                "path": photo_draft.path,
                "source": photo_draft.source,
                "camera": photo_draft.source,
                "received_at": received_at.isoformat(),
                "captured_at": photo_draft.captured_at or "",
                "session_id": session["id"],
            }
            payload["photos"].append(photo)
            self.refresh_session(session, payload["photos"])
            return photo

        return self.store.mutate(mutation)

    def get_active_session(self, *, now: datetime | str | None = None) -> dict[str, Any] | None:
        timestamp = self.parse_datetime(now) if now else datetime.now(timezone.utc)

        def mutation(payload: dict[str, list[dict[str, Any]]]):
            self.close_inactive_sessions_in_payload(payload, now=timestamp)
            return self.get_active_session_from_payload(payload, now=timestamp)

        return self.store.mutate(mutation)

    def close_inactive_sessions(self, payload: dict[str, list[dict[str, Any]]] | None = None, *, now: datetime | str | None = None):
        timestamp = self.parse_datetime(now) if now else datetime.now(timezone.utc)
        if payload is not None:
            return self.close_inactive_sessions_in_payload(payload, now=timestamp)

        def mutation(current: dict[str, list[dict[str, Any]]]):
            return self.close_inactive_sessions_in_payload(current, now=timestamp)

        return self.store.mutate(mutation)

    def create_new_session(self, *, started_at: datetime | str | None = None) -> dict[str, Any]:
        timestamp = self.parse_datetime(started_at) if started_at else datetime.now(timezone.utc)

        def mutation(payload: dict[str, list[dict[str, Any]]]):
            self.close_inactive_sessions_in_payload(payload, now=timestamp, force=True)
            return self.create_session(payload, timestamp)

        return self.store.mutate(mutation)

    def create_session(self, payload: dict[str, list[dict[str, Any]]], started_at: datetime) -> dict[str, Any]:
        session = {
            "id": f"session-{uuid4().hex}",
            "started_at": started_at.isoformat(),
            "last_received_at": started_at.isoformat(),
            "status": "active",
            "photo_count": 0,
            "sources": [],
        }
        payload["sessions"].append(session)
        return session

    def get_active_session_from_payload(self, payload: dict[str, list[dict[str, Any]]], *, now: datetime) -> dict[str, Any] | None:
        active_sessions = [session for session in payload["sessions"] if session.get("status") == "active"]
        if not active_sessions:
            return None
        active_sessions.sort(key=lambda item: str(item.get("last_received_at", "")), reverse=True)
        session = active_sessions[0]
        last_received_at = self.parse_datetime(str(session.get("last_received_at") or session.get("started_at")))
        if now - last_received_at >= self.session_timeout:
            session["status"] = "closed"
            return None
        return session

    def close_inactive_sessions_in_payload(self, payload: dict[str, list[dict[str, Any]]], *, now: datetime, force: bool = False) -> list[dict[str, Any]]:
        closed = []
        for session in payload["sessions"]:
            if session.get("status") != "active":
                continue
            last_received_at = self.parse_datetime(str(session.get("last_received_at") or session.get("started_at")))
            if force or now - last_received_at >= self.session_timeout:
                session["status"] = "closed"
                closed.append(session)
        return closed

    def refresh_session(self, session: dict[str, Any], photos: list[dict[str, Any]]) -> None:
        session_photos = [photo for photo in photos if photo.get("session_id") == session.get("id")]
        session["photo_count"] = len(session_photos)
        if session_photos:
            session["last_received_at"] = max(str(photo.get("received_at", "")) for photo in session_photos)
        sources = sorted({str(photo.get("source") or photo.get("camera") or "").strip() for photo in session_photos if str(photo.get("source") or photo.get("camera") or "").strip()})
        session["sources"] = sources

    @staticmethod
    def normalize_draft(draft: IngestPhotoDraft | dict[str, Any]) -> IngestPhotoDraft:
        if isinstance(draft, IngestPhotoDraft):
            return draft
        filename = str(draft.get("filename") or Path(str(draft.get("path", ""))).name)
        return IngestPhotoDraft(
            filename=filename,
            path=str(draft.get("path", "")),
            source=str(draft.get("source") or draft.get("camera") or ""),
            received_at=str(draft.get("received_at")) if draft.get("received_at") else None,
            captured_at=str(draft.get("captured_at")) if draft.get("captured_at") else None,
        )

    @staticmethod
    def parse_datetime(value: datetime | str) -> datetime:
        if isinstance(value, datetime):
            parsed = value
        else:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
