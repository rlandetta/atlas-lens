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
    kind: str
    width: int = 0
    height: int = 0
    size: int = 0


class DeliveryPreviewService:
    def __init__(
        self,
        *,
        delivery_root: str | os.PathLike[str],
        thumbnail_long_edge: int = 240,
        background_long_edge: int = 1280,
        thumbnail_quality: int = 55,
        background_quality: int = 45,
    ):
        self.delivery_root = Path(delivery_root)
        self.thumbnail_long_edge = thumbnail_long_edge
        self.background_long_edge = background_long_edge
        self.thumbnail_quality = thumbnail_quality
        self.background_quality = background_quality

    def ensure_previews(self, shipment_id: str, manifest: dict[str, Any], *, background_limit: int = 4) -> dict[str, list[dict[str, Any]]]:
        current = self.load_preview_manifest(shipment_id)
        photo_items = self.photo_items(manifest)
        if self.pillow_available():
            current = self.ensure_missing_previews(shipment_id, photo_items, current, background_limit=background_limit)
        background_items = self.select_photo_items(photo_items, limit=background_limit)
        return {
            "thumbnails": self.match_existing_previews(current.get("thumbnails", []), photo_items),
            "backgrounds": self.select_backgrounds(self.match_existing_previews(current.get("backgrounds", []), background_items), limit=background_limit),
            "errors": current.get("errors", []),
        }

    def ensure_missing_previews(
        self,
        shipment_id: str,
        photo_items: list[dict[str, Any]],
        current: dict[str, list[dict[str, Any]]],
        *,
        background_limit: int,
    ) -> dict[str, list[dict[str, Any]]]:
        package_root = self.package_root(shipment_id)
        previews_dir = self.previews_dir(shipment_id)
        previews_dir.mkdir(parents=True, exist_ok=True)
        thumbnails = self.match_existing_previews(current.get("thumbnails", []), photo_items)
        backgrounds = self.match_existing_previews(current.get("backgrounds", []), self.select_photo_items(photo_items, limit=background_limit))
        errors = list(current.get("errors", []))
        thumbnail_ids = {str(item.get("file_id", "")) for item in thumbnails}
        background_ids = {str(item.get("file_id", "")) for item in backgrounds}

        for item in photo_items:
            file_id = str(item.get("id", ""))
            if file_id in thumbnail_ids:
                continue
            preview = self.create_preview(
                package_root,
                previews_dir,
                item,
                kind="thumbnail",
                max_long_edge=self.thumbnail_long_edge,
                quality=self.thumbnail_quality,
            )
            if preview:
                thumbnails.append(preview.__dict__)
                thumbnail_ids.add(file_id)
            else:
                errors.append({"file_id": file_id, "kind": "thumbnail", "message": "No se pudo generar thumbnail."})

        for item in self.select_photo_items(photo_items, limit=background_limit):
            file_id = str(item.get("id", ""))
            if file_id in background_ids:
                continue
            preview = self.create_preview(
                package_root,
                previews_dir,
                item,
                kind="background",
                max_long_edge=self.background_long_edge,
                quality=self.background_quality,
            )
            if preview:
                backgrounds.append(preview.__dict__)
                background_ids.add(file_id)
            else:
                errors.append({"file_id": file_id, "kind": "background", "message": "No se pudo generar background."})

        payload = {"thumbnails": thumbnails, "backgrounds": backgrounds, "errors": errors}
        if thumbnails or backgrounds or errors:
            self.write_preview_manifest(shipment_id, payload)
        return payload

    def load_previews(self, shipment_id: str) -> dict[str, list[dict[str, Any]]]:
        return self.load_preview_manifest(shipment_id)

    def preview_path(self, shipment_id: str, preview_id: str) -> tuple[Path, dict[str, Any]]:
        safe_id = DeliveryPackageService.safe_component(shipment_id)
        safe_preview_id = self.safe_preview_id(preview_id)
        if not safe_id or not safe_preview_id:
            raise DeliveryPreviewError("Preview inválido.")
        previews = self.load_preview_manifest(safe_id)
        all_previews = previews.get("thumbnails", []) + previews.get("backgrounds", [])
        preview = next((item for item in all_previews if str(item.get("id", "")) == safe_preview_id), None)
        if not preview:
            raise DeliveryPreviewError("Preview no disponible.")
        package_root = self.package_root(safe_id)
        candidate = (package_root / str(preview.get("path", ""))).resolve()
        previews_root = self.previews_dir(safe_id).resolve()
        if not candidate.is_relative_to(previews_root) or not candidate.is_file():
            raise DeliveryPreviewError("Preview no disponible.")
        return candidate, preview

    def load_preview_manifest(self, shipment_id: str) -> dict[str, list[dict[str, Any]]]:
        path = self.preview_manifest_path(shipment_id)
        if not path.is_file():
            return {"thumbnails": [], "backgrounds": [], "errors": []}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"thumbnails": [], "backgrounds": [], "errors": []}
        if not isinstance(payload, dict):
            return {"thumbnails": [], "backgrounds": [], "errors": []}
        if "previews" in payload:
            legacy = [self.normalize_legacy_preview(item) for item in payload.get("previews", []) if isinstance(item, dict)]
            legacy = [item for item in legacy if item]
            return {"thumbnails": legacy, "backgrounds": self.select_backgrounds(legacy), "errors": []}
        return {
            "thumbnails": [item for item in payload.get("thumbnails", []) if isinstance(item, dict)],
            "backgrounds": [item for item in payload.get("backgrounds", []) if isinstance(item, dict)],
            "errors": [item for item in payload.get("errors", []) if isinstance(item, dict)],
        }

    def write_preview_manifest(self, shipment_id: str, previews: dict[str, list[dict[str, Any]]]) -> None:
        path = self.preview_manifest_path(shipment_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(previews, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def create_preview(
        self,
        package_root: Path,
        previews_dir: Path,
        item: dict[str, Any],
        *,
        kind: str,
        max_long_edge: int,
        quality: int,
    ) -> DeliveryPreview | None:
        try:
            from PIL import Image, ImageOps
        except ModuleNotFoundError:
            return None

        try:
            source = DeliveryPackageService.resolve_package_member(package_root, str(item.get("path", "")))
        except DeliveryPackageError:
            return None
        file_id = str(item.get("id", ""))
        safe_file_id = DeliveryPackageService.safe_component(file_id)
        if not safe_file_id:
            return None
        preview_id = self.build_preview_id(kind, safe_file_id)
        destination = previews_dir / f"{kind}-{safe_file_id}.jpg"
        if destination.is_file():
            return DeliveryPreview(
                id=preview_id,
                file_id=file_id,
                filename=destination.name,
                path=f"previews/{destination.name}",
                kind=kind,
                size=destination.stat().st_size,
            )
        try:
            with Image.open(source) as image:
                image = ImageOps.exif_transpose(image)
                image.thumbnail((max_long_edge, max_long_edge))
                rgb = image.convert("RGB")
                rgb.save(destination, "JPEG", quality=quality, optimize=True, progressive=True)
                width = rgb.width
                height = rgb.height
        except Exception:
            if destination.exists():
                destination.unlink()
            return None
        return DeliveryPreview(
            id=preview_id,
            file_id=file_id,
            filename=destination.name,
            path=f"previews/{destination.name}",
            kind=kind,
            width=width,
            height=height,
            size=destination.stat().st_size,
        )

    @staticmethod
    def photo_items(manifest: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            item
            for item in manifest.get("files", [])
            if isinstance(item, dict) and item.get("type") == "photo"
        ]

    def select_photo_items(self, manifest_or_photos: dict[str, Any] | list[dict[str, Any]], *, limit: int = 4) -> list[dict[str, Any]]:
        photos = self.photo_items(manifest_or_photos) if isinstance(manifest_or_photos, dict) else list(manifest_or_photos)
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

    def match_existing_previews(self, previews: list[dict[str, Any]], photo_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        wanted = {str(item.get("id", "")) for item in photo_items}
        matched = []
        seen = set()
        for preview in previews:
            file_id = str(preview.get("file_id", ""))
            if file_id not in wanted or file_id in seen:
                continue
            try:
                self.preview_path_from_record(preview)
            except DeliveryPreviewError:
                continue
            matched.append(preview)
            seen.add(file_id)
        return matched

    def preview_path_from_record(self, preview: dict[str, Any]) -> Path:
        path = str(preview.get("path", ""))
        if not path.startswith("previews/"):
            raise DeliveryPreviewError("Preview no disponible.")
        return Path(path)

    @staticmethod
    def build_preview_id(kind: str, safe_file_id: str) -> str:
        return f"{kind}:{safe_file_id}"

    @staticmethod
    def safe_preview_id(value: str) -> str:
        cleaned = "".join(character if character.isalnum() or character in {"-", "_", ":"} else "-" for character in value.strip())
        cleaned = cleaned.strip(".-_")
        return cleaned if cleaned == value and "/" not in cleaned and "\\" not in cleaned else ""

    def normalize_legacy_preview(self, preview: dict[str, Any]) -> dict[str, Any] | None:
        preview_id = str(preview.get("id", "")).strip()
        file_id = str(preview.get("file_id", "")).strip()
        path = str(preview.get("path", "")).strip()
        if not preview_id or not file_id or not path.startswith("previews/"):
            return None
        normalized = dict(preview)
        normalized.setdefault("kind", "legacy")
        return normalized

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
