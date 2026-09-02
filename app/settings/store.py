from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any
import fcntl
import json
import os
import tempfile

from app.settings.models import SettingsStoreError, empty_settings_payload, normalize_channel
from app.settings.models import normalize_dispatch_branding, normalize_public_profile, sanitize_profile_key


class SettingsStore:
    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path)
        self.lock_path = self.path.with_name(f"{self.path.name}.lock")

    @contextmanager
    def _locked(self, *, shared: bool):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a", encoding="utf-8") as lock_file:
            operation = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
            fcntl.flock(lock_file.fileno(), operation)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def load(self) -> dict[str, Any]:
        with self._locked(shared=True):
            return self._load_unlocked()

    def _load_unlocked(self) -> dict[str, Any]:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return empty_settings_payload()
        try:
            with self.path.open("r", encoding="utf-8") as source:
                payload = json.load(source)
        except json.JSONDecodeError as error:
            raise SettingsStoreError(f"El archivo de settings contiene JSON inválido: {self.path}") from error
        if not isinstance(payload, dict):
            raise SettingsStoreError(f"El archivo de settings tiene una estructura inválida: {self.path}")
        channels = payload.get("outbound_channels", [])
        if not isinstance(channels, list):
            raise SettingsStoreError(f"La lista de canales de salida es inválida: {self.path}")
        normalized = empty_settings_payload()
        normalized["schema_version"] = int(payload.get("schema_version", normalized["schema_version"]) or normalized["schema_version"])
        normalized["outbound_channels"] = [normalize_channel(channel) for channel in channels if isinstance(channel, dict)]
        raw_profiles = payload.get("public_profiles", {})
        profiles: dict[str, dict[str, Any]] = {}
        if isinstance(raw_profiles, dict):
            for key, profile in raw_profiles.items():
                if not isinstance(profile, dict):
                    continue
                profiles[sanitize_profile_key(str(key))] = normalize_public_profile(profile)
        normalized["public_profiles"] = profiles
        raw_branding = payload.get("dispatch_branding", normalized["dispatch_branding"])
        normalized["dispatch_branding"] = normalize_dispatch_branding(raw_branding if isinstance(raw_branding, dict) else {})
        return normalized

    def save(self, payload: dict[str, Any]) -> None:
        with self._locked(shared=False):
            self._save_unlocked(payload)

    def _save_unlocked(self, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict) or not isinstance(payload.get("outbound_channels"), list):
            raise SettingsStoreError("No se puede guardar una estructura de settings inválida.")
        normalized = empty_settings_payload()
        normalized["schema_version"] = int(payload.get("schema_version", normalized["schema_version"]) or normalized["schema_version"])
        normalized["outbound_channels"] = [normalize_channel(channel) for channel in payload["outbound_channels"]]
        raw_profiles = payload.get("public_profiles", {})
        profiles: dict[str, dict[str, Any]] = {}
        if isinstance(raw_profiles, dict):
            for key, profile in raw_profiles.items():
                if not isinstance(profile, dict):
                    continue
                profiles[sanitize_profile_key(str(key))] = normalize_public_profile(profile)
        normalized["public_profiles"] = profiles
        raw_branding = payload.get("dispatch_branding", normalized["dispatch_branding"])
        normalized["dispatch_branding"] = normalize_dispatch_branding(raw_branding if isinstance(raw_branding, dict) else {})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temp_file:
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

    def list_channels(self) -> list[dict[str, Any]]:
        with self._locked(shared=True):
            return deepcopy(self._load_unlocked()["outbound_channels"])

    def get_channel(self, channel_id: str) -> dict[str, Any] | None:
        with self._locked(shared=True):
            for channel in self._load_unlocked()["outbound_channels"]:
                if channel.get("id") == channel_id:
                    return deepcopy(channel)
        return None

    def save_channels(self, channels: list[dict[str, Any]]) -> list[dict[str, Any]]:
        payload = empty_settings_payload()
        payload["outbound_channels"] = channels
        self.save(payload)
        return self.list_channels()
