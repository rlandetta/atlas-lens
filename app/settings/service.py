from __future__ import annotations

from copy import deepcopy
from typing import Any
import os

from app.settings.models import (
    OutboundChannelDraft,
    SettingsSecretError,
    SettingsValidationError,
    build_channel,
    normalize_channel,
    utc_now_iso,
    validate_new_channel_id,
)
from app.settings.store import SettingsStore


class SettingsService:
    def __init__(self, store: SettingsStore):
        self.store = store

    def list_outbound_channels(self) -> list[dict[str, Any]]:
        return sorted(self.store.list_channels(), key=lambda channel: channel["name"].casefold())

    def list_active_outbound_channels(self) -> list[dict[str, Any]]:
        return [channel for channel in self.list_outbound_channels() if channel.get("is_active")]

    def get_outbound_channel(self, channel_id: str) -> dict[str, Any] | None:
        return self.store.get_channel(channel_id)

    def get_default_outbound_channel(self) -> dict[str, Any] | None:
        for channel in self.list_active_outbound_channels():
            if channel.get("is_default"):
                return channel
        return None

    def create_outbound_channel(self, draft: OutboundChannelDraft) -> dict[str, Any]:
        if draft.channel_type == "api":
            raise SettingsValidationError("API todavía no está disponible como canal de entrega.")
        channels = self.store.list_channels()
        channel_id = validate_new_channel_id(draft.id)
        if any(channel.get("id") == channel_id for channel in channels):
            raise SettingsValidationError("Ya existe un canal con ese identificador.")
        channel = build_channel(OutboundChannelDraft(**{**draft.__dict__, "id": channel_id}))
        channels.append(channel)
        self.store.save_channels(self._normalize_default(channels, channel["id"] if channel.get("is_default") else ""))
        return self.store.get_channel(channel["id"]) or channel

    def update_outbound_channel(self, channel_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        channels = self.store.list_channels()
        for index, channel in enumerate(channels):
            if channel.get("id") == channel_id:
                next_channel = deepcopy(channel)
                next_channel.update(deepcopy(updates))
                next_channel["id"] = channel_id
                next_channel["created_at"] = channel.get("created_at")
                next_channel["updated_at"] = utc_now_iso()
                normalized = normalize_channel(next_channel)
                channels[index] = normalized
                self.store.save_channels(self._normalize_default(channels, channel_id if normalized.get("is_default") else ""))
                return self.store.get_channel(channel_id) or normalized
        raise SettingsValidationError("No existe el canal solicitado.")

    def delete_outbound_channel(self, channel_id: str) -> dict[str, Any]:
        channels = self.store.list_channels()
        remaining = []
        deleted = None
        for channel in channels:
            if channel.get("id") == channel_id:
                deleted = channel
            else:
                remaining.append(channel)
        if deleted is None:
            raise SettingsValidationError("No existe el canal solicitado.")
        self.store.save_channels(remaining)
        return deleted

    def resolve_channel_secret(self, channel: dict[str, Any]) -> str:
        credential_ref = str(channel.get("credential_ref", "")).strip()
        if not credential_ref:
            raise SettingsSecretError("Credencial SMTP no configurada.")
        secret = os.environ.get(credential_ref)
        if not secret:
            raise SettingsSecretError("Credencial SMTP no configurada.")
        return secret

    @staticmethod
    def _normalize_default(channels: list[dict[str, Any]], default_channel_id: str) -> list[dict[str, Any]]:
        normalized = []
        for channel in channels:
            item = normalize_channel(channel)
            if default_channel_id:
                item["is_default"] = item.get("id") == default_channel_id
            normalized.append(item)
        return normalized
