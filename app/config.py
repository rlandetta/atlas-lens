import os


DEFAULT_DEV_RUNTIME_ROOT = "/home/atlas/ayampi-dev/runtime/lens"
RUNTIME_ROOT = os.getenv("AYAMPI_RUNTIME_ROOT", DEFAULT_DEV_RUNTIME_ROOT)


def get_bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def get_list_env(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if value is None:
        return default
    items = [item.strip() for item in value.replace("\n", ",").split(",")]
    return [item for item in items if item]


def get_url_prefix_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        return ""
    normalized = "/" + value.strip("/")
    return "" if normalized == "/" else normalized


AI_ENABLED = get_bool_env("AI_ENABLED", False)
AI_PROVIDER = os.getenv("AI_PROVIDER", "mock").strip().lower()
ATLAS_URL_PREFIX = get_url_prefix_env("ATLAS_URL_PREFIX")
DISPATCH_STORE_PATH = os.getenv(
    "DISPATCH_STORE_PATH",
    os.path.join(RUNTIME_ROOT, "dispatch_shipments.json"),
)

INGEST_STORE_PATH = os.getenv(
    "INGEST_STORE_PATH",
    os.path.join(RUNTIME_ROOT, "ingest.json"),
)
INGEST_SESSION_TIMEOUT_MINUTES = get_int_env("INGEST_SESSION_TIMEOUT_MINUTES", 60)

FLOW_WATCH_DIRECTORIES = get_list_env("FLOW_WATCH_DIRECTORIES", [
    os.path.join(RUNTIME_ROOT, "flow-events"),
])
FLOW_WATCH_INTERVAL_SECONDS = get_int_env("FLOW_WATCH_INTERVAL_SECONDS", 2)
FLOW_EVENTS_ROOT = os.getenv(
    "FLOW_EVENTS_ROOT",
    os.path.join(RUNTIME_ROOT, "flow-events"),
)
FLOW_TRASH_ROOT = os.getenv(
    "FLOW_TRASH_ROOT",
    os.path.join(RUNTIME_ROOT, "flow-trash"),
)
DELIVERY_ROOT = os.getenv(
    "DELIVERY_ROOT",
    os.path.join(RUNTIME_ROOT, "deliveries"),
)
DELIVERY_LINKS_STORE_PATH = os.getenv(
    "DELIVERY_LINKS_STORE_PATH",
    os.path.join(RUNTIME_ROOT, "delivery_links.json"),
)
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:5101").strip().rstrip("/")
PUBLIC_DELIVERY_BASE_URL = os.getenv("PUBLIC_DELIVERY_BASE_URL", PUBLIC_BASE_URL).strip().rstrip("/")
DISPATCH_IP_GEOLOCATION_PROVIDER = os.getenv("DISPATCH_IP_GEOLOCATION_PROVIDER", "ipwhois").strip().lower()
DISPATCH_IP_GEOLOCATION_CACHE_PATH = os.getenv(
    "DISPATCH_IP_GEOLOCATION_CACHE_PATH",
    os.path.join(RUNTIME_ROOT, "dispatch_ip_geolocation_cache.json"),
)
DISPATCH_IP_GEOLOCATION_CACHE_TTL_DAYS = get_int_env("DISPATCH_IP_GEOLOCATION_CACHE_TTL_DAYS", 30)
DISPATCH_TRUSTED_PROXY_CIDRS = get_list_env("DISPATCH_TRUSTED_PROXY_CIDRS", ["127.0.0.1/32", "::1/128"])
DELIVERY_REVOKED_RETENTION_DAYS = get_int_env("DELIVERY_REVOKED_RETENTION_DAYS", 7)
SETTINGS_STORE_PATH = os.getenv(
    "SETTINGS_STORE_PATH",
    os.path.join(RUNTIME_ROOT, "settings.json"),
)
LENS_COVERAGE_STORE_PATH = os.getenv(
    "LENS_COVERAGE_STORE_PATH",
    os.path.join(RUNTIME_ROOT, "lens_coverages.json"),
)
LENS_MEDIA_ROOT = os.getenv(
    "LENS_MEDIA_ROOT",
    os.path.join(RUNTIME_ROOT, "lens_media"),
)
THUMBNAIL_ROOT = os.getenv(
    "THUMBNAIL_ROOT",
    os.path.join(RUNTIME_ROOT, "thumbnails"),
)
LENS_MAX_PHOTO_BYTES = get_int_env("LENS_MAX_PHOTO_BYTES", 25 * 1024 * 1024)
PROFILE_AVATAR_ROOT = os.getenv(
    "PROFILE_AVATAR_ROOT",
    os.path.join(RUNTIME_ROOT, "profile_avatars"),
)
PROFILE_MAX_AVATAR_BYTES = get_int_env("PROFILE_MAX_AVATAR_BYTES", 5 * 1024 * 1024)
PULSE_STORE_PATH = os.getenv(
    "PULSE_STORE_PATH",
    os.path.join(RUNTIME_ROOT, "pulse.json"),
)
