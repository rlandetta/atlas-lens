from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.dispatch.delivery_package import DeliveryPackageError, DeliveryPackageService


class DeliveryPreviewError(ValueError):
    pass


@dataclass(frozen=True)
class DeliveryPreview:
    id: str
    file_id: str
    filename: str
    path: str
    width: int = 0
    height: int = 0
    size: int = 0


class DeliveryPreviewService:
    def __init__(self, *, delivery_root: str | os.PathLike[str], max_long_edge: int = 1280, quality: int = 45):
        self.delivery_root = Path(delivery_root)
        self.max_long_edge = max_long_edge
        self.quality = quality

    def ensure_previews(self, shipment_id: str, manifest: dict[str, Any], *, limit: int = 4) -> list[dict[str, Any]]:
        current = self.load_preview_manifest(shipment_id)
        if current:
            return self.select_backgrounds(current, limit=limit)
        if not self.pillow_available():
            return []

        previews = []
        package_root = self.package_root(shipment_id)
        previews_dir = self.previews_dir(shipment_id)
        previews_dir.mkdir(parents=True, exist_ok=True)
        for item in self.select_photo_items(manifest, limit=limit):
            preview = self.create_preview(package_root, previews_dir, item)
            if preview:
                previews.append(preview.__dict__)
        if previews:
            self.write_preview_manifest(shipment_id, previews)
        return previews

    def load_previews(self, shipment_id: str) -> list[dict[str, Any]]:
        return self.load_preview_manifest(shipment_id)

    def preview_path(self, shipment_id: str, preview_id: str) -> tuple[Path, dict[str, Any]]:
        safe_id = DeliveryPackageService.safe_component(shipment_id)
        safe_preview_id = DeliveryPackageService.safe_component(preview_id)
        if not safe_id or not safe_preview_id or safe_preview_id != str(preview_id):
            raise DeliveryPreviewError("Preview inválido.")
        previews = self.load_preview_manifest(safe_id)
        preview = next((item for item in previews if str(item.get("id", "")) == safe_preview_id), None)
        if not preview:
            raise DeliveryPreviewError("Preview no disponible.")
        package_root = self.package_root(safe_id)
        candidate = (package_root / str(preview.get("path", ""))).resolve()
        previews_root = self.previews_dir(safe_id).resolve()
        if not candidate.is_relative_to(previews_root) or not candidate.is_file():
            raise DeliveryPreviewError("Preview no disponible.")
        return candidate, preview

    def load_preview_manifest(self, shipment_id: str) -> list[dict[str, Any]]:
        path = self.preview_manifest_path(shipment_id)
        if not path.is_file():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        previews = payload.get("previews", []) if isinstance(payload, dict) else []
        return [item for item in previews if isinstance(item, dict)]

    def write_preview_manifest(self, shipment_id: str, previews: list[dict[str, Any]]) -> None:
        path = self.preview_manifest_path(shipment_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"previews": previews}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def create_preview(self, package_root: Path, previews_dir: Path, item: dict[str, Any]) -> DeliveryPreview | None:
        try:
            from PIL import Image, ImageOps
        except ModuleNotFoundError:
            return None

        try:
            source = DeliveryPackageService.resolve_package_member(package_root, str(item.get("path", "")))
        except DeliveryPackageError:
            return None
        preview_id = DeliveryPackageService.safe_component(str(item.get("id", "")))
        if not preview_id:
            return None
        destination = previews_dir / f"{preview_id}.jpg"
        try:
            with Image.open(source) as image:
                image = ImageOps.exif_transpose(image)
                image.thumbnail((self.max_long_edge, self.max_long_edge))
                rgb = image.convert("RGB")
                rgb.save(destination, "JPEG", quality=self.quality, optimize=True, progressive=True)
        except Exception:
            if destination.exists():
                destination.unlink()
            return None
        return DeliveryPreview(
            id=preview_id,
            file_id=str(item.get("id", "")),
            filename=destination.name,
            path=f"previews/{destination.name}",
            width=rgb.width,
            height=rgb.height,
            size=destination.stat().st_size,
        )

    def select_photo_items(self, manifest: dict[str, Any], *, limit: int = 4) -> list[dict[str, Any]]:
        photos = [
            item
            for item in manifest.get("files", [])
            if isinstance(item, dict) and item.get("type") == "photo"
        ]
        if len(photos) <= limit:
            return photos
        indexes = [0, len(photos) // 3, (len(photos) * 2) // 3, len(photos) - 1]
        selected = []
        seen = set()
        for index in indexes:
            if index in seen:
                continue
            seen.add(index)
            selected.append(photos[index])
        return selected[:limit]

    @staticmethod
    def select_backgrounds(previews: list[dict[str, Any]], *, limit: int = 4) -> list[dict[str, Any]]:
        if len(previews) <= limit:
            return previews
        indexes = [0, len(previews) // 3, (len(previews) * 2) // 3, len(previews) - 1]
        selected = []
        seen = set()
        for index in indexes:
            if index in seen:
                continue
            seen.add(index)
            selected.append(previews[index])
        return selected[:limit]

    @staticmethod
    def pillow_available() -> bool:
        try:
            import PIL  # noqa: F401
        except ModuleNotFoundError:
            return False
        return True

    def package_root(self, shipment_id: str) -> Path:
        safe_id = DeliveryPackageService.safe_component(shipment_id)
        if not safe_id:
            raise DeliveryPreviewError("Despacho inválido.")
        root = (self.delivery_root / safe_id).resolve()
        delivery_root = self.delivery_root.resolve()
        if not root.is_relative_to(delivery_root):
            raise DeliveryPreviewError("Despacho inválido.")
        return root

    def previews_dir(self, shipment_id: str) -> Path:
        return self.package_root(shipment_id) / "previews"

    def preview_manifest_path(self, shipment_id: str) -> Path:
        return self.previews_dir(shipment_id) / "previews.json"
