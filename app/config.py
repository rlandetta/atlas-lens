import os


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


AI_ENABLED = get_bool_env("AI_ENABLED", False)
AI_PROVIDER = os.getenv("AI_PROVIDER", "mock").strip().lower()
DISPATCH_STORE_PATH = os.getenv(
    "DISPATCH_STORE_PATH",
    os.path.join("instance", "dispatch_shipments.json"),
)

INGEST_STORE_PATH = os.getenv(
    "INGEST_STORE_PATH",
    os.path.join("instance", "ingest.json"),
)
INGEST_SESSION_TIMEOUT_MINUTES = get_int_env("INGEST_SESSION_TIMEOUT_MINUTES", 60)

FLOW_WATCH_DIRECTORIES = get_list_env("FLOW_WATCH_DIRECTORIES", [
    "/data/FLOW/sftpgo/storage/incoming/canon-r6",
    "/data/FLOW/sftpgo/storage/incoming/canon-1dx",
])
FLOW_WATCH_INTERVAL_SECONDS = get_int_env("FLOW_WATCH_INTERVAL_SECONDS", 2)
DELIVERY_ROOT = os.getenv(
    "DELIVERY_ROOT",
    os.path.join("instance", "deliveries"),
)
DELIVERY_LINKS_STORE_PATH = os.getenv(
    "DELIVERY_LINKS_STORE_PATH",
    os.path.join("instance", "delivery_links.json"),
)
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
DELIVERY_REVOKED_RETENTION_DAYS = get_int_env("DELIVERY_REVOKED_RETENTION_DAYS", 7)
SETTINGS_STORE_PATH = os.getenv(
    "SETTINGS_STORE_PATH",
    os.path.join("instance", "settings.json"),
)
LENS_COVERAGE_STORE_PATH = os.getenv(
    "LENS_COVERAGE_STORE_PATH",
    os.path.join("instance", "lens_coverages.json"),
)
LENS_MEDIA_ROOT = os.getenv(
    "LENS_MEDIA_ROOT",
    os.path.join("instance", "lens_media"),
)
LENS_MAX_PHOTO_BYTES = get_int_env("LENS_MAX_PHOTO_BYTES", 25 * 1024 * 1024)
