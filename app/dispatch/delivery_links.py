from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import fcntl
import hashlib
import json
import os
import secrets
import tempfile

from app.dispatch.geolocation import empty_location, resolve_geolocation


class DeliveryLinkError(ValueError):
    pass


DOWNLOAD_TYPES = ("PACKAGE", "PHOTO", "DOCUMENT")
MAX_DOWNLOAD_EVENTS_STORED = 200

EXPIRATION_DAYS = {
    "1": 1,
    "3": 3,
    "7": 7,
    "14": 14,
    "30": 30,
    "none": None,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_utc(value: str) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalize_link(link: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(link)
    normalized["id"] = str(normalized.get("id", "")).strip()
    normalized["shipment_id"] = str(normalized.get("shipment_id", "")).strip()
    normalized["token"] = str(normalized.get("token", "")).strip()
    normalized.setdefault("created_at", utc_now_iso())
    normalized.setdefault("expires_at", "")
    normalized.setdefault("revoked_at", "")
    normalized["download_count"] = int(normalized.get("download_count") or 0)
    normalized.setdefault("last_download_at", "")
    normalized["download_events"] = [
        event for event in normalized.get("download_events") or [] if isinstance(event, dict)
    ]
    normalized.setdefault("password_hash", "")
    normalized["is_active"] = bool(normalized.get("is_active", True))
    if not normalized["id"] or not normalized["shipment_id"] or not normalized["token"]:
        raise DeliveryLinkError("Link de descarga inválido.")
    return normalized


class DeliveryLinkStore:
    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path)
        self.lock_path = self.path.with_name(f"{self.path.name}.lock")

    @contextmanager
    def _locked(self, *, shared: bool):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_SH if shared else fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def load(self) -> dict[str, list[dict[str, Any]]]:
        with self._locked(shared=True):
            return self._load_unlocked()

    def _load_unlocked(self) -> dict[str, list[dict[str, Any]]]:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return {"links": []}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise DeliveryLinkError(f"El archivo de links contiene JSON inválido: {self.path}") from error
        if not isinstance(payload, dict) or not isinstance(payload.get("links"), list):
            raise DeliveryLinkError(f"El archivo de links tiene estructura inválida: {self.path}")
        return {"links": [normalize_link(item) for item in payload["links"] if isinstance(item, dict)]}

    def _save_unlocked(self, payload: dict[str, list[dict[str, Any]]]) -> None:
        if not isinstance(payload, dict) or not isinstance(payload.get("links"), list):
            raise DeliveryLinkError("No se puede guardar una estructura de links inválida.")
        normalized = {"links": [normalize_link(item) for item in payload["links"]]}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent, prefix=f".{self.path.name}.", suffix=".tmp", delete=False) as temp_file:
                temp_path = Path(temp_file.name)
                json.dump(normalized, temp_file, ensure_ascii=False, indent=2)
                temp_file.write("\n")
                temp_file.flush()
                os.fsync(temp_file.fileno())
            os.replace(temp_path, self.path)
        except Exception:
            if temp_path and temp_path.exists():
                temp_path.unlink()
            raise

    def list_links(self) -> list[dict[str, Any]]:
        with self._locked(shared=True):
            return deepcopy(self._load_unlocked()["links"])

    def create(self, link: dict[str, Any]) -> dict[str, Any]:
        normalized = normalize_link(link)
        with self._locked(shared=False):
            payload = self._load_unlocked()
            if any(item["id"] == normalized["id"] or item["token"] == normalized["token"] for item in payload["links"]):
                raise DeliveryLinkError("Ya existe un link con ese identificador.")
            payload["links"].insert(0, normalized)
            self._save_unlocked(payload)
        return deepcopy(normalized)

    def update(self, link_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        with self._locked(shared=False):
            payload = self._load_unlocked()
            for index, link in enumerate(payload["links"]):
                if link["id"] == link_id:
                    next_link = deepcopy(link)
                    next_link.update(deepcopy(updates))
                    payload["links"][index] = normalize_link(next_link)
                    self._save_unlocked(payload)
                    return deepcopy(payload["links"][index])
        raise DeliveryLinkError("No existe el link solicitado.")

    def get_by_token(self, token: str) -> dict[str, Any] | None:
        for link in self.list_links():
            if secrets.compare_digest(str(link.get("token", "")), str(token or "")):
                return link
        return None

    def get_active_for_shipment(self, shipment_id: str) -> dict[str, Any] | None:
        for link in self.list_links():
            if link.get("shipment_id") == shipment_id and self.is_usable(link):
                return link
        return None

    def list_for_shipment(self, shipment_id: str) -> list[dict[str, Any]]:
        return [link for link in self.list_links() if link.get("shipment_id") == shipment_id]

    def record_download(
        self,
        link_id: str,
        *,
        download_type: str = "PACKAGE",
        filename: str = "",
        country: str = "",
        city: str = "",
        country_code: str = "",
        region: str = "",
        latitude: float | None = None,
        longitude: float | None = None,
        ip_hash: str = "",
        browser: str = "",
        os_name: str = "",
        device_category: str = "",
        user_agent: str = "",
    ) -> dict[str, Any]:
        timestamp = utc_now_iso()
        current = next((link for link in self.list_links() if link.get("id") == link_id), None)
        if current is None:
            raise DeliveryLinkError("No existe el link solicitado.")
        safe_type = download_type if download_type in DOWNLOAD_TYPES else "PACKAGE"
        events = [event for event in current.get("download_events") or [] if isinstance(event, dict)]
        events.insert(0, {
            "downloaded_at": timestamp,
            "download_type": safe_type,
            "filename": str(filename or ""),
            "country": str(country or ""),
            "city": str(city or ""),
            "country_code": str(country_code or ""),
            "region": str(region or ""),
            "latitude": latitude,
            "longitude": longitude,
            "ip_hash": str(ip_hash or ""),
            "browser": str(browser or ""),
            "os": str(os_name or ""),
            "device_category": str(device_category or ""),
            "user_agent": str(user_agent or ""),
        })
        return self.update(link_id, {
            "download_count": int(current.get("download_count") or 0) + 1,
            "last_download_at": timestamp,
            "download_events": events[:MAX_DOWNLOAD_EVENTS_STORED],
        })

    @staticmethod
    def is_usable(link: dict[str, Any], now: datetime | None = None) -> bool:
        if not link.get("is_active") or link.get("revoked_at"):
            return False
        expires_at = parse_utc(str(link.get("expires_at", "")))
        if expires_at is None:
            return True
        reference = now or datetime.now(timezone.utc)
        return expires_at > reference.astimezone(timezone.utc)


class DeliveryLinkService:
    def __init__(
        self,
        store: DeliveryLinkStore,
        public_base_url: str = "",
        *,
        public_delivery_base_url: str = "",
        geolocation_service=None,
    ):
        self.store = store
        self.public_base_url = public_base_url.rstrip("/")
        self.public_delivery_base_url = public_delivery_base_url.rstrip("/")
        self.geolocation_service = geolocation_service

    def create_link(self, shipment_id: str, expires_in: str = "7") -> dict[str, Any]:
        duration = EXPIRATION_DAYS.get(str(expires_in), 7)
        created_at = datetime.now(timezone.utc)
        token = secrets.token_urlsafe(32)
        link = self.store.create({
            "id": f"link-{secrets.token_urlsafe(12)}",
            "shipment_id": shipment_id,
            "token": token,
            "created_at": created_at.isoformat(),
            "expires_at": "" if duration is None else (created_at + timedelta(days=duration)).isoformat(),
            "revoked_at": "",
            "download_count": 0,
            "last_download_at": "",
            "password_hash": "",
            "is_active": True,
        })
        return self.with_url(link)

    def get_active_for_shipment(self, shipment_id: str) -> dict[str, Any] | None:
        link = self.store.get_active_for_shipment(shipment_id)
        return self.with_url(link) if link else None

    def get_by_token(self, token: str) -> dict[str, Any] | None:
        link = self.store.get_by_token(token)
        if not link or not self.store.is_usable(link):
            return None
        return self.with_url(link)

    def revoke_for_shipment(self, shipment_id: str) -> dict[str, Any] | None:
        link = self.store.get_active_for_shipment(shipment_id)
        if not link:
            return None
        return self.with_url(self.store.update(link["id"], {"revoked_at": utc_now_iso(), "is_active": False}))

    def regenerate_for_shipment(self, shipment_id: str, expires_in: str = "7") -> dict[str, Any]:
        self.revoke_for_shipment(shipment_id)
        return self.create_link(shipment_id, expires_in=expires_in)

    def record_download(
        self,
        link_id: str,
        *,
        download_type: str = "PACKAGE",
        filename: str = "",
        ip: str = "",
        browser: str = "",
        os_name: str = "",
        device_category: str = "",
        user_agent: str = "",
    ) -> dict[str, Any]:
        location = self.resolve_geolocation(ip)
        return self.with_url(self.store.record_download(
            link_id,
            download_type=download_type,
            filename=filename,
            country=str(location.get("country", "")),
            city=str(location.get("city", "")),
            country_code=str(location.get("country_code", "")),
            region=str(location.get("region", "")),
            latitude=location.get("latitude"),
            longitude=location.get("longitude"),
            ip_hash=hash_ip(ip),
            browser=browser,
            os_name=os_name,
            device_category=device_category,
            user_agent=user_agent,
        ))

    def resolve_geolocation(self, ip: str) -> dict[str, Any]:
        if self.geolocation_service is not None:
            try:
                return self.geolocation_service.resolve(ip)
            except Exception:
                return empty_location()
        return resolve_geolocation(ip)

    def with_url(self, link: dict[str, Any]) -> dict[str, Any]:
        enriched = deepcopy(link)
        path = f"/d/{enriched.get('token', '')}"
        enriched["url"] = f"{self.public_base_url}{path}" if self.public_base_url else path
        enriched["public_url"] = f"{self.public_delivery_base_url}{path}" if self.public_delivery_base_url else enriched["url"]
        return enriched


def hash_ip(ip: str) -> str:
    safe_ip = str(ip or "").strip()
    if not safe_ip:
        return ""
    return hashlib.sha256(safe_ip.encode("utf-8")).hexdigest()
