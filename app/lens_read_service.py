from __future__ import annotations

from copy import deepcopy
from typing import Callable, Mapping, Any


CoverageSource = Mapping[str, dict[str, Any]] | Callable[[], Mapping[str, dict[str, Any]]]


class LensReadError(ValueError):
    pass


class LensReadService:
    def __init__(self, coverage_source: CoverageSource):
        self.coverage_source = coverage_source

    def _coverages(self) -> Mapping[str, dict[str, Any]]:
        source = self.coverage_source() if callable(self.coverage_source) else self.coverage_source
        if not isinstance(source, Mapping):
            raise LensReadError("La fuente de coberturas no es válida.")
        return source

    def get_coverage(self, coverage_id: str) -> dict[str, Any]:
        coverage = self._coverages().get(coverage_id)
        if coverage is None:
            raise LensReadError("La cobertura no existe.")
        return deepcopy(coverage)

    def get_photo(self, coverage_id: str, photo_id: str) -> dict[str, Any]:
        coverage = self.get_coverage(coverage_id)
        for photo in coverage.get("photos", []):
            if photo.get("id") == photo_id:
                return deepcopy(photo)
        raise LensReadError("La fotografía no existe.")

    def get_approved_photos(self, coverage_id: str) -> list[dict[str, Any]]:
        coverage = self.get_coverage(coverage_id)
        photos = coverage.get("photos", [])
        if not isinstance(photos, list):
            return []
        return [
            deepcopy(photo)
            for photo in photos
            if self.is_photo_approved(photo)
        ]

    def get_approved_photos_by_ids(self, coverage_id: str, photo_ids: list[str]) -> list[dict[str, Any]]:
        approved_photos = {
            str(photo.get("id")): photo
            for photo in self.get_approved_photos(coverage_id)
        }
        selected = []
        for photo_id in photo_ids:
            photo = approved_photos.get(str(photo_id))
            if photo is None:
                original = self.get_photo(coverage_id, str(photo_id))
                if original.get("caption_status") != "Aprobado":
                    raise LensReadError("La fotografía no tiene caption aprobado.")
                raise LensReadError("La fotografía aprobada no está disponible.")
            selected.append(deepcopy(photo))
        return selected

    @staticmethod
    def is_photo_approved(photo: dict[str, Any]) -> bool:
        return (
            photo.get("caption_status") == "Aprobado"
            and bool(str(photo.get("caption_narrative", "")).strip())
            and photo.get("available_on_disk", True) is not False
        )
