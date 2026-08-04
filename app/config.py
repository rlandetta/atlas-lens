import os


def get_bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


AI_ENABLED = get_bool_env("AI_ENABLED", False)
AI_PROVIDER = os.getenv("AI_PROVIDER", "mock").strip().lower()
DISPATCH_STORE_PATH = os.getenv(
    "DISPATCH_STORE_PATH",
    os.path.join("instance", "dispatch_shipments.json"),
)
LENS_COVERAGE_STORE_PATH = os.getenv(
    "LENS_COVERAGE_STORE_PATH",
    os.path.join("instance", "lens_coverages.json"),
)
LENS_MEDIA_ROOT = os.getenv(
    "LENS_MEDIA_ROOT",
    os.path.join("instance", "lens_media"),
)
