from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import fcntl
import ipaddress
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

# Pluggable resolver so a local GeoIP data source can be wired in later without
# touching call sites. Defaults to a safe no-op: download tracking must never
# be blocked by the absence of a geolocation source.
LocationResolver = Callable[[str], tuple[str, str]]
GEOLOCATION_FIELDS = (
    "country_code",
    "country",
    "region",
    "city",
    "latitude",
    "longitude",
)


def empty_location() -> dict[str, Any]:
    return {
        "country_code": "",
        "country": "",
        "region": "",
        "city": "",
        "latitude": None,
        "longitude": None,
    }


def normalize_location(payload: dict[str, Any] | None) -> dict[str, Any]:
    location = empty_location()
    if not isinstance(payload, dict):
        return location
    for field in GEOLOCATION_FIELDS:
        if field in {"latitude", "longitude"}:
            try:
                location[field] = float(payload[field]) if payload.get(field) not in {"", None} else None
            except (TypeError, ValueError):
                location[field] = None
        else:
            location[field] = str(payload.get(field) or "").strip()
    return location


def is_public_ip(ip: str) -> bool:
    try:
        parsed = ipaddress.ip_address(str(ip or "").strip())
    except ValueError:
        return False
    return parsed.is_global


class JsonGeolocationCache:
    def __init__(self, path: str | os.PathLike[str], ttl_days: int = 30):
        self.path = Path(path)
        self.lock_path = self.path.with_name(f"{self.path.name}.lock")
        self.ttl = timedelta(days=max(int(ttl_days or 30), 1))

    @contextmanager
    def _locked(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def load(self) -> dict[str, Any]:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return {"entries": {}}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"entries": {}}
        entries = payload.get("entries") if isinstance(payload, dict) else None
        return {"entries": entries if isinstance(entries, dict) else {}}

    def save(self, payload: dict[str, Any]) -> None:
        temp_path = None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=self.path.parent,
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            json.dump(payload, temp_file, ensure_ascii=False, indent=2)
            temp_file.write("\n")
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, self.path)

    def get(self, ip: str) -> dict[str, Any] | None:
        with self._locked():
            entry = self.load()["entries"].get(ip)
            if not isinstance(entry, dict):
                return None
            try:
                resolved_at = datetime.fromisoformat(str(entry.get("resolved_at", "")).replace("Z", "+00:00"))
            except ValueError:
                return None
            if resolved_at.tzinfo is None or resolved_at.utcoffset() is None:
                resolved_at = resolved_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - resolved_at.astimezone(timezone.utc) > self.ttl:
                return None
            return normalize_location(entry.get("location", {}))

    def set(self, ip: str, location: dict[str, Any]) -> None:
        with self._locked():
            payload = self.load()
            payload["entries"][ip] = {
                "resolved_at": datetime.now(timezone.utc).isoformat(),
                "location": normalize_location(location),
            }
            self.save(payload)


class IpWhoIsGeolocationService:
    provider_name = "ipwhois"

    def __init__(self, cache: JsonGeolocationCache | None = None, timeout_seconds: float = 1.5):
        self.cache = cache
        self.timeout_seconds = timeout_seconds

    def resolve(self, ip: str) -> dict[str, Any]:
        safe_ip = str(ip or "").strip()
        if not is_public_ip(safe_ip):
            return empty_location()
        if self.cache is not None:
            cached = self.cache.get(safe_ip)
            if cached is not None:
                return cached
        location = self._fetch(safe_ip)
        if self.cache is not None:
            self.cache.set(safe_ip, location)
        return location

    def _fetch(self, ip: str) -> dict[str, Any]:
        request = Request(
            f"https://ipwho.is/{quote(ip, safe='')}",
            headers={"User-Agent": "ATLAS-DISPATCH/1.0"},
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
            return empty_location()
        if not isinstance(payload, dict) or payload.get("success") is False:
            return empty_location()
        return normalize_location({
            "country_code": payload.get("country_code", ""),
            "country": payload.get("country", ""),
            "region": payload.get("region", ""),
            "city": payload.get("city", ""),
            "latitude": payload.get("latitude"),
            "longitude": payload.get("longitude"),
        })


class StaticGeolocationService:
    provider_name = "static"

    def __init__(self, resolver: LocationResolver):
        self.resolver = resolver

    def resolve(self, ip: str) -> dict[str, Any]:
        country, city = self.resolver(ip)
        return normalize_location({"country": country, "city": city})


class NoOpGeolocationService:
    provider_name = "none"

    def resolve(self, ip: str) -> dict[str, Any]:
        return empty_location()


def _no_op_resolver(ip: str) -> tuple[str, str]:
    return "", ""


_resolver: LocationResolver = _no_op_resolver
_service: Any = NoOpGeolocationService()


def set_resolver(resolver: LocationResolver) -> None:
    global _resolver
    _resolver = resolver
    set_service(StaticGeolocationService(resolver))


def set_service(service: Any) -> None:
    global _service
    _service = service or NoOpGeolocationService()


def build_geolocation_service(
    *,
    provider: str = "ipwhois",
    cache_path: str | os.PathLike[str] = "",
    ttl_days: int = 30,
) -> Any:
    if str(provider or "").strip().lower() in {"", "none", "disabled"}:
        return NoOpGeolocationService()
    cache = JsonGeolocationCache(cache_path, ttl_days=ttl_days) if cache_path else None
    return IpWhoIsGeolocationService(cache=cache)


def resolve_geolocation(ip: str) -> dict[str, Any]:
    if not ip:
        return empty_location()
    try:
        return normalize_location(_service.resolve(ip))
    except Exception:
        return empty_location()


def resolve_location(ip: str) -> tuple[str, str]:
    """Best-effort (country, city) lookup for an IP address.

    Returns ("", "") when no location can be resolved so callers can fall
    back to a clear "Ubicación no disponible" label.
    """
    if not ip:
        return "", ""
    try:
        location = resolve_geolocation(ip)
        return str(location.get("country", "")), str(location.get("city", ""))
    except Exception:
        return "", ""
