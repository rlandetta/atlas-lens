from __future__ import annotations

from typing import Callable

# Pluggable resolver so a local GeoIP data source can be wired in later without
# touching call sites. Defaults to a safe no-op: download tracking must never
# be blocked by the absence of a geolocation source.
LocationResolver = Callable[[str], tuple[str, str]]


def _no_op_resolver(ip: str) -> tuple[str, str]:
    return "", ""


_resolver: LocationResolver = _no_op_resolver


def set_resolver(resolver: LocationResolver) -> None:
    global _resolver
    _resolver = resolver


def resolve_location(ip: str) -> tuple[str, str]:
    """Best-effort (country, city) lookup for an IP address.

    Returns ("", "") when no location can be resolved so callers can fall
    back to a clear "Ubicación no disponible" label.
    """
    if not ip:
        return "", ""
    try:
        return _resolver(ip)
    except Exception:
        return "", ""
