import base64
import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from app.export.engine import ExportEngine
from app.export.models import ExportPhoto, ExportRequest
from app.export.naming import ExportNames
from app.export.builders.docx_builder import build_docx
from app.export.builders.image_sources import load_image_source, resolve_original_path
from app.export.builders.pdf_builder import build_pdf
from app.export.builders.zip_builder import build_zip_archive
from app.export.template_renderer import render_caption


PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)
JPG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xd9"
PDF_JPG_BYTES = (
    b"\xff\xd8"
    b"\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00"
    b"\xff\xd9"
)


def docx_members(content: bytes) -> tuple[list[str], str]:
    with zipfile.ZipFile(BytesIO(content)) as archive:
        return archive.namelist(), archive.read("word/document.xml").decode("utf-8")


def build_photo(**overrides) -> ExportPhoto:
    values = {
        "id": "photo-1",
        "filename": "IMG001.jpg",
        "caption": "Caption de prueba.",
        "status": "Aprobado",
        "photographer": "",
        "editor": "",
        "metadata": {"type": "image/jpeg"},
        "available_on_disk": True,
    }
    values.update(overrides)
    return ExportPhoto(**values)


def build_photos_zip(photos: list[ExportPhoto]) -> bytes:
    content, _ = build_zip_archive(
        request=ExportRequest(
            coverage_id="cov-1",
            formats=(),
            include_photos=True,
            include_captions=False,
            include_metadata=False,
            include_manifest=False,
        ),
        names=ExportNames(base_name="test-export", zip_filename="test-export.zip"),
        coverage_metadata={"coverage_name": "Cobertura Quito", "country": "Ecuador"},
        manifest={},
        photos=photos,
    )
    return content


def build_flow_events_path(root: Path, filename: str = "_21A1622.JPG") -> Path:
    return root / "storage" / "events" / "2026" / "08" / "12" / "sabado" / "ricardo" / "canon-r6" / "JPG" / filename


def build_flow_archive_path(root: Path, filename: str = "_21A1622.JPG") -> Path:
    return root / "storage" / "archive" / "2026" / "08" / "12" / "canon-r6" / filename


def assert_pdf_has_image(test_case: unittest.TestCase, content: bytes):
    test_case.assertTrue(content.startswith(b"%PDF-1.4"))
    test_case.assertIn(b"/Subtype /Image", content)


class DocxExportTest(unittest.TestCase):
    def test_pdf_embeds_media_from_data_url(self):
        encoded = base64.b64encode(PDF_JPG_BYTES).decode("ascii")
        content = build_pdf(
            [build_photo(data_url=f"data:image/jpeg;base64,{encoded}")],
            {"coverage_name": "Cobertura Quito", "country": "Ecuador"},
        )

        assert_pdf_has_image(self, content)

    def test_pdf_embeds_media_from_storage_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            media_root = Path(temp_dir)
            storage_path = "coverages/cov-1/IMG002.jpg"
            target = media_root / storage_path
            target.parent.mkdir(parents=True)
            target.write_bytes(PDF_JPG_BYTES)

            with patch("app.config.LENS_MEDIA_ROOT", str(media_root)):
                content = build_pdf(
                    [build_photo(id="photo-2", filename="IMG002.jpg", storage_path=storage_path)],
                    {"coverage_name": "Cobertura Quito", "country": "Ecuador"},
                )

        assert_pdf_has_image(self, content)

    def test_pdf_embeds_media_from_flow_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            flow_path = Path(temp_dir) / "IMG003.jpg"
            flow_path.write_bytes(PDF_JPG_BYTES)

            content = build_pdf(
                [build_photo(id="photo-3", filename="IMG003.jpg", flow_path=str(flow_path))],
                {"coverage_name": "Cobertura Quito", "country": "Ecuador"},
            )

        assert_pdf_has_image(self, content)

    def test_zip_writes_non_empty_photo_from_data_url(self):
        encoded = base64.b64encode(JPG_BYTES).decode("ascii")
        content = build_photos_zip([
            build_photo(data_url=f"data:image/jpeg;base64,{encoded}")
        ])

        with zipfile.ZipFile(BytesIO(content)) as archive:
            self.assertGreater(len(archive.read("Fotografias/IMG001.jpg")), 0)

    def test_zip_writes_non_empty_photo_from_storage_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            media_root = Path(temp_dir)
            storage_path = "coverages/cov-1/IMG002.jpg"
            target = media_root / storage_path
            target.parent.mkdir(parents=True)
            target.write_bytes(JPG_BYTES)

            with patch("app.config.LENS_MEDIA_ROOT", str(media_root)):
                content = build_photos_zip([
                    build_photo(id="photo-2", filename="IMG002.jpg", storage_path=storage_path)
                ])

        with zipfile.ZipFile(BytesIO(content)) as archive:
            self.assertGreater(len(archive.read("Fotografias/IMG002.jpg")), 0)

    def test_zip_writes_non_empty_photo_from_flow_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            flow_path = Path(temp_dir) / "IMG003.jpg"
            flow_path.write_bytes(JPG_BYTES)

            content = build_photos_zip([
                build_photo(id="photo-3", filename="IMG003.jpg", flow_path=str(flow_path))
            ])

        with zipfile.ZipFile(BytesIO(content)) as archive:
            self.assertGreater(len(archive.read("Fotografias/IMG003.jpg")), 0)

    def test_flow_events_path_existing_resolves_original(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            events_path = build_flow_events_path(Path(temp_dir))
            archive_path = build_flow_archive_path(Path(temp_dir))
            events_path.parent.mkdir(parents=True)
            archive_path.parent.mkdir(parents=True)
            events_path.write_bytes(b"events-original")
            archive_path.write_bytes(b"archive-original")

            source = resolve_original_path(build_photo(filename="_21A1622.JPG", flow_path=str(events_path)))

        self.assertEqual(source, events_path.resolve())

    def test_flow_events_path_missing_resolves_archive_original_deterministically(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            events_path = build_flow_events_path(Path(temp_dir))
            archive_path = build_flow_archive_path(Path(temp_dir))
            archive_path.parent.mkdir(parents=True)
            archive_path.write_bytes(JPG_BYTES + b"archive")

            content = build_photos_zip([
                build_photo(id="photo-flow", filename="_21A1622.JPG", flow_path=str(events_path))
            ])

        with zipfile.ZipFile(BytesIO(content)) as archive:
            self.assertEqual(archive.read("Fotografias/_21A1622.JPG"), JPG_BYTES + b"archive")

    def test_flow_events_path_missing_and_archive_missing_is_unresolved(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            events_path = build_flow_events_path(Path(temp_dir))

            source = resolve_original_path(build_photo(filename="_21A1622.JPG", flow_path=str(events_path)))

        self.assertIsNone(source)

    def test_flow_events_zero_byte_file_is_unresolved_without_archive_fallback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            events_path = build_flow_events_path(Path(temp_dir))
            archive_path = build_flow_archive_path(Path(temp_dir))
            events_path.parent.mkdir(parents=True)
            archive_path.parent.mkdir(parents=True)
            events_path.write_bytes(b"")
            archive_path.write_bytes(JPG_BYTES)

            source = resolve_original_path(build_photo(filename="_21A1622.JPG", flow_path=str(events_path)))

        self.assertIsNone(source)

    def test_flow_archive_zero_byte_file_is_unresolved(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            events_path = build_flow_events_path(Path(temp_dir))
            archive_path = build_flow_archive_path(Path(temp_dir))
            archive_path.parent.mkdir(parents=True)
            archive_path.write_bytes(b"")

            source = resolve_original_path(build_photo(filename="_21A1622.JPG", flow_path=str(events_path)))

        self.assertIsNone(source)

    def test_legacy_data_url_and_storage_path_still_resolve(self):
        encoded = base64.b64encode(JPG_BYTES).decode("ascii")
        with tempfile.TemporaryDirectory() as temp_dir:
            media_root = Path(temp_dir)
            storage_path = "coverages/cov-1/IMG002.jpg"
            target = media_root / storage_path
            target.parent.mkdir(parents=True)
            target.write_bytes(JPG_BYTES + b"storage")

            image_bytes, content_type = load_image_source(
                build_photo(data_url=f"data:image/jpeg;base64,{encoded}")
            )
            with patch("app.config.LENS_MEDIA_ROOT", str(media_root)):
                storage_source = resolve_original_path(build_photo(id="photo-storage", storage_path=storage_path))

        self.assertEqual(image_bytes, JPG_BYTES)
        self.assertEqual(content_type, "image/jpeg")
        self.assertEqual(storage_source, target.resolve())

    def test_zip_includes_exactly_six_jpgs_with_original_filenames_and_non_empty_bytes(self):
        photos = []
        for index in range(1, 7):
            filename = f"IMG00{index}.jpg"
            encoded = base64.b64encode(JPG_BYTES + bytes([index])).decode("ascii")
            photos.append(build_photo(
                id=f"photo-{index}",
                filename=filename,
                data_url=f"data:image/jpeg;base64,{encoded}",
            ))

        content = build_photos_zip(photos)

        with zipfile.ZipFile(BytesIO(content)) as archive:
            jpg_names = [
                name for name in archive.namelist()
                if name.startswith("Fotografias/") and name.lower().endswith(".jpg")
            ]
            self.assertEqual(jpg_names, [f"Fotografias/{photo.filename}" for photo in photos])
            self.assertEqual(len(jpg_names), 6)
            for name in jpg_names:
                self.assertGreater(len(archive.read(name)), 0)

    def test_zip_raises_explicit_error_for_unresolved_photo(self):
        with self.assertRaisesRegex(ValueError, "missing.jpg.*photo-missing"):
            build_photos_zip([
                build_photo(id="photo-missing", filename="missing.jpg")
            ])

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
