from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ExportNames:
    base_name: str
    zip_filename: str
    metadata_filename: str = "metadata.json"
    manifest_filename: str = "manifest.json"
    docx_filename: str = "captions.docx"
    html_filename: str = "captions.html"
    pdf_filename: str = "captions.pdf"


class ExportNamingService:
    def build_names(self, coverage: dict, output_name: str = "") -> ExportNames:
        base_name = self.normalize_output_name(output_name) if output_name else self.build_base_name(coverage)
        if base_name.lower().endswith(".zip"):
            base_name = base_name[:-4]
        return ExportNames(
            base_name=base_name,
            zip_filename=f"{base_name}.zip",
        )

    def build_base_name(self, coverage: dict) -> str:
        date_token = self.build_date_token(str(coverage.get("submit_date", "")))
        coverage_token = self.normalize_segment(str(coverage.get("coverage_name", "Cobertura")))
        country_token = self.normalize_segment(str(coverage.get("country", "Pais")))
        return f"{date_token}-{coverage_token}-{country_token}"

    def build_date_token(self, value: str) -> str:
        try:
            return datetime.strptime(value, "%Y-%m-%d").strftime("%Y%m%d")
        except ValueError:
            return "00000000"

    def normalize_output_name(self, value: str) -> str:
        value = value.strip()
        if value.lower().endswith(".zip"):
            value = value[:-4]
        return self.normalize_segment(value)

    def normalize_segment(self, value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value.strip())
        ascii_value = "".join(
            character
            for character in normalized
            if not unicodedata.combining(character)
        )
        cleaned = re.sub(r"[^A-Za-z0-9]+", "-", ascii_value)
        cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
        return cleaned or "Exportacion"
