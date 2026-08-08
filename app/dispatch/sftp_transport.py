from __future__ import annotations

from pathlib import Path
from typing import Any


class SFTPTransportError(ValueError):
    pass


try:
    import paramiko  # type: ignore
except Exception:  # pragma: no cover - availability varies by deployment
    paramiko = None


class SFTPTransport:
    def __init__(self, *, settings_service=None):
        self.settings_service = settings_service

    @property
    def is_available(self) -> bool:
        return paramiko is not None

    def upload_package(self, *, channel: dict[str, Any], package_root: Path, files: list[dict[str, Any]]) -> dict[str, Any]:
        if paramiko is None:
            raise SFTPTransportError("Paramiko no está instalado; la transferencia SFTP real queda pendiente.")
        if self.settings_service is None:
            raise SFTPTransportError("SettingsService no disponible para resolver credenciales SFTP.")
        credential = self.settings_service.resolve_channel_secret(channel)
        host = str(channel.get("host") or channel.get("smtp_host") or "").strip()
        username = str(channel.get("username") or channel.get("smtp_username") or "").strip()
        remote_path = str(channel.get("remote_path") or "/").rstrip("/")
        port = int(channel.get("port") or channel.get("smtp_port") or 22)
        if not host or not username or not remote_path:
            raise SFTPTransportError("Canal SFTP incompleto.")
        transport = paramiko.Transport((host, port))
        try:
            transport.connect(username=username, password=credential)
            sftp = paramiko.SFTPClient.from_transport(transport)
            shipment_remote = f"{remote_path}/{package_root.name}"
            self._mkdir_p(sftp, shipment_remote)
            uploaded = []
            for item in files:
                local = package_root / str(item.get("path", ""))
                if not local.is_file() or not local.resolve().is_relative_to(package_root.resolve()):
                    continue
                remote = f"{shipment_remote}/{local.name}"
                sftp.put(str(local), remote)
                uploaded.append(remote)
            sftp.close()
            return {"remote_path": shipment_remote, "files": uploaded}
        finally:
            transport.close()

    @staticmethod
    def _mkdir_p(sftp, path: str) -> None:
        current = ""
        for part in [item for item in path.split("/") if item]:
            current = f"{current}/{part}"
            try:
                sftp.mkdir(current)
            except Exception:
                pass
