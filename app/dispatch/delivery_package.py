from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import os
import shutil
import zipfile

from app import config
from app.export.models import ExportRequest
from app.export.service import ExportService
from app.export.builders.image_sources import resolve_original_path


class DeliveryPackageError(ValueError):
    pass


@dataclass(frozen=True)
class DeliveryFile:
    id: str
    filename: str
    path: str
    size: int
    type: str
    mimetype: str = "application/octet-stream"
    thumbnail: bool = False


@dataclass(frozen=True)
class DeliveryPackage:
    shipment_id: str
    root: Path
    files_dir: Path
    zip_path: Path
    manifest_path: Path
    files: tuple[DeliveryFile, ...]
    total_bytes: int
    created_at: str


class DeliveryPackageService:
    def __init__(self, *, delivery_root: str | os.PathLike[str], media_root: str | os.PathLike[str], export_service: ExportService | None = None):
        self.delivery_root = Path(delivery_root)
        self.media_root = Path(media_root)
        self.export_service = export_service or ExportService()

    def prepare_package(self, *, shipment: dict[str, Any], coverage: dict[str, Any]) -> DeliveryPackage:
        shipment_id = self.safe_component(str(shipment.get("id", "")))
        if not shipment_id:
            raise DeliveryPackageError("El despacho no tiene identificador válido.")
        package_root = (self.delivery_root / shipment_id).resolve()
        files_dir = package_root / "files"
        files_dir.mkdir(parents=True, exist_ok=True)

        selected_photos = self.select_photos(shipment, coverage)
        copied_files = [self.copy_photo(photo, files_dir) for photo in selected_photos]
        package_files = list(copied_files)

        if shipment.get("include_caption_docx"):
            docx_photos = self.select_docx_photos(shipment, coverage, selected_photos)
            if docx_photos:
                docx_file = self.write_docx(shipment, coverage, docx_photos, files_dir)
                package_files.append(docx_file)

        if not package_files:
            raise DeliveryPackageError("No hay archivos para preparar el paquete.")

        created_at = datetime.now(timezone.utc).isoformat()
        zip_path = package_root / "package.zip"
        self.write_zip(zip_path, package_files, files_dir)
        zip_size = zip_path.stat().st_size
        # The ZIP is just a packaging of the same files, not additional content.
        total_bytes = sum(item.size for item in package_files)
        manifest_path = package_root / "manifest.json"
        manifest = {
            "shipment_id": shipment_id,
            "coverage_id": str(shipment.get("coverage_id", "")),
            "created_at": created_at,
            "files": [item.__dict__ for item in package_files],
            "zip": {"filename": "package.zip", "size": zip_size},
            "total_bytes": total_bytes,
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return DeliveryPackage(
            shipment_id=shipment_id,
            root=package_root,
            files_dir=files_dir,
            zip_path=zip_path,
            manifest_path=manifest_path,
            files=tuple(package_files),
            total_bytes=total_bytes,
            created_at=created_at,
        )

    def load_manifest(self, shipment_id: str) -> dict[str, Any]:
        safe_id = self.safe_component(shipment_id)
        manifest_path = self.delivery_root / safe_id / "manifest.json"
        if not manifest_path.is_file():
            raise DeliveryPackageError("El paquete no existe.")
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    def package_zip_path(self, shipment_id: str) -> Path:
        return self.resolve_package_path(shipment_id, "package.zip")

    def package_file_path(self, shipment_id: str, file_id: str) -> tuple[Path, dict[str, Any]]:
        manifest = self.load_manifest(shipment_id)
        for item in manifest.get("files", []):
            if str(item.get("id", "")) == file_id:
                return self.resolve_package_path(shipment_id, str(item.get("path", ""))), item
        raise DeliveryPackageError("El archivo solicitado no existe.")

    def resolve_package_path(self, shipment_id: str, relative_path: str) -> Path:
        safe_id = self.safe_component(shipment_id)
        package_root = (self.delivery_root / safe_id).resolve()
        candidate = (package_root / relative_path).resolve()
        if not candidate.is_relative_to(package_root) or not candidate.is_file():
            raise DeliveryPackageError("Archivo no disponible.")
        return candidate

    def select_photos(self, shipment: dict[str, Any], coverage: dict[str, Any]) -> list[dict[str, Any]]:
        selected_ids = {str(photo_id) for photo_id in shipment.get("photo_ids", [])}
        photos = coverage.get("photos", []) if isinstance(coverage.get("photos"), list) else []
        return [photo for photo in photos if str(photo.get("id", "")) in selected_ids]

    def select_docx_photos(self, shipment: dict[str, Any], coverage: dict[str, Any], selected_photos: list[dict[str, Any]]) -> list[dict[str, Any]]:
        scope = str(shipment.get("export_reference", {}).get("caption_docx", {}).get("photo_scope", "selected"))
        if scope == "all_eligible":
            photos = coverage.get("photos", []) if isinstance(coverage.get("photos"), list) else []
            return [photo for photo in photos if str(photo.get("caption_narrative", "")).strip()]
        return selected_photos

    def copy_photo(self, photo: dict[str, Any], files_dir: Path) -> DeliveryFile:
        source = self.resolve_lens_photo(photo)
        filename = self.safe_filename(str(photo.get("filename") or photo.get("name") or photo.get("id") or source.name))
        destination = self.unique_destination(files_dir, filename)
        shutil.copy2(source, destination)
        return DeliveryFile(
            id=self.safe_component(str(photo.get("id", destination.stem))) or destination.stem,
            filename=destination.name,
            path=f"files/{destination.name}",
            size=destination.stat().st_size,
            type="photo",
            mimetype=str(photo.get("type", "image/jpeg") or "image/jpeg"),
        )

    def write_docx(self, shipment: dict[str, Any], coverage: dict[str, Any], photos: list[dict[str, Any]], files_dir: Path) -> DeliveryFile:
        coverage_name = str(coverage.get("coverage_name") or shipment.get("coverage_snapshot", {}).get("coverage_name") or shipment.get("coverage_id") or "Cobertura")
        filename = self.safe_filename(f"{coverage_name}_Captions.docx")
        request = ExportRequest(
            coverage_id=str(shipment.get("coverage_id", "")),
            formats=("docx",),
            include_photos=False,
            include_captions=True,
            include_metadata=False,
            include_manifest=False,
            output_name=coverage_name,
            template="xinhua",
            scope="coverage",
            requested_by="DISPATCH",
            destination="dispatch",
        )
        previous_media_root = config.LENS_MEDIA_ROOT
        config.LENS_MEDIA_ROOT = str(self.media_root)
        try:
            result = self.export_service.engine.build_export(
                coverage_id=str(shipment.get("coverage_id", "")),
                coverage=coverage,
                photos=photos,
                request=request,
                warnings=(),
            )
        finally:
            config.LENS_MEDIA_ROOT = previous_media_root
        docx = next((item for item in result.files if item.format == "docx"), None)
        if docx is None:
            raise DeliveryPackageError("No se pudo generar el documento Word.")
        destination = self.unique_destination(files_dir, filename)
        destination.write_bytes(docx.content)
        return DeliveryFile(
            id="captions-docx",
            filename=destination.name,
            path=f"files/{destination.name}",
            size=destination.stat().st_size,
            type="document",
            mimetype=docx.mimetype,
        )

    def write_zip(self, zip_path: Path, files: list[DeliveryFile], files_dir: Path) -> None:
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as archive:
            for item in files:
                source = self.resolve_package_member(files_dir.parent, item.path)
                archive.write(source, arcname=item.path)

    def resolve_lens_photo(self, photo: dict[str, Any]) -> Path:
        source = resolve_original_path(photo, media_root=self.media_root)
        if source is not None:
            return source

        raise DeliveryPackageError("Fotografía no disponible en LENS.")

    @staticmethod
    def resolve_package_member(package_root: Path, relative_path: str) -> Path:
        root = package_root.resolve()
        candidate = (root / relative_path).resolve()
        if not candidate.is_relative_to(root) or not candidate.is_file():
            raise DeliveryPackageError("Archivo de paquete inválido.")
        return candidate

    @staticmethod
    def safe_component(value: str) -> str:
        cleaned = "".join(character if character.isalnum() or character in {"-", "_"} else "-" for character in value.strip())
        return cleaned.strip(".-_")

    @classmethod
    def safe_filename(cls, value: str) -> str:
        name = Path(value).name.strip().replace("\\", "-")
        cleaned = "".join(character if character.isalnum() or character in {"-", "_", ".", " "} else "-" for character in name)
        cleaned = "-".join(cleaned.split())
        return cleaned.strip(".") or "archivo"

    @classmethod
    def unique_destination(cls, directory: Path, filename: str) -> Path:
        safe_name = cls.safe_filename(filename)
        candidate = directory / safe_name
        if not candidate.exists():
            return candidate
        stem = candidate.stem
        suffix = candidate.suffix
        counter = 2
        while True:
            next_candidate = directory / f"{stem}-{counter}{suffix}"
            if not next_candidate.exists():
                return next_candidate
            counter += 1
