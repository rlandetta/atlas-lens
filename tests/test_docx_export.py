import base64
import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from app.export.engine import ExportEngine
from app.export.models import ExportPhoto, ExportRequest
from app.export.builders.docx_builder import build_docx
from app.export.template_renderer import render_caption


PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def docx_members(content: bytes) -> tuple[list[str], str]:
    with zipfile.ZipFile(BytesIO(content)) as archive:
        return archive.namelist(), archive.read("word/document.xml").decode("utf-8")


class DocxExportTest(unittest.TestCase):
    def test_docx_embeds_media_from_storage_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            media_root = Path(temp_dir)
            storage_path = "coverages/cov-1/photo-1_IMG001.png"
            target = media_root / storage_path
            target.parent.mkdir(parents=True)
            target.write_bytes(PNG_BYTES)

            with patch("app.config.LENS_MEDIA_ROOT", str(media_root)):
                content = build_docx(
                    [
                        ExportPhoto(
                            id="photo-1",
                            filename="IMG001.png",
                            caption="Caption de prueba.",
                            status="Aprobado",
                            photographer="",
                            editor="",
                            metadata={"type": "image/png"},
                            storage_path=storage_path,
                            available_on_disk=True,
                        )
                    ],
                    {"coverage_name": "Cobertura Quito", "country": "Ecuador"},
                )

        names, document_xml = docx_members(content)
        self.assertTrue(any(name.startswith("word/media/") for name in names))
        self.assertIn("<w:drawing>", document_xml)
        self.assertIn("Caption de prueba.", document_xml)

    def test_docx_embeds_media_when_submit_date_differs_from_event_date(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            media_root = Path(temp_dir)
            storage_path = "coverages/cov-1/photo-1_IMG001.png"
            target = media_root / storage_path
            target.parent.mkdir(parents=True)
            target.write_bytes(PNG_BYTES)
            coverage = {
                "coverage_name": "Cobertura Bogotá",
                "city": "Bogotá",
                "country": "Colombia",
                "agency": "Xinhua",
                "photographer": "Stringer",
                "editor": "rl",
                "submit_date": "2026-08-07",
                "event_date": "2026-08-05",
            }
            photo = {
                "id": "photo-1",
                "name": "IMG001.png",
                "filename": "IMG001.png",
                "storage_path": storage_path,
                "caption_narrative": "Persona participa en evento",
                "caption_status": "Aprobado",
                "available_on_disk": True,
                "type": "image/png",
            }

            with patch("app.config.LENS_MEDIA_ROOT", str(media_root)):
                result = ExportEngine().build_export(
                    coverage_id="cov-1",
                    coverage=coverage,
                    photos=[photo],
                    request=ExportRequest(coverage_id="cov-1", formats=("docx",)),
                )

        names, document_xml = docx_members(result.content)
        self.assertTrue(any(name.startswith("word/media/") for name in names))
        self.assertIn("<w:drawing>", document_xml)
        self.assertIn("Imagen del 5 de agosto de 2026", document_xml)

    def test_xinhua_caption_does_not_end_location_with_comma_period(self):
        caption = render_caption(
            "xinhua",
            {
                "city": "Bogotá",
                "country": "Colombia",
                "agency": "Xinhua",
                "photographer": "Stringer",
                "editor": "rl",
                "submit_date": "2026-08-07",
                "event_date": "2026-08-05",
            },
            {"caption_narrative": "Persona participa en evento"},
        )

        self.assertNotIn(",.", caption)
        self.assertIn("Colombia. (Xinhua/Stringer) (rl)", caption)


if __name__ == "__main__":
    unittest.main()
