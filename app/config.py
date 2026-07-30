import os


def get_bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


AI_ENABLED = get_bool_env("AI_ENABLED", False)
AI_PROVIDER = os.getenv("AI_PROVIDER", "mock").strip().lower()
