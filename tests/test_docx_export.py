import base64
import re
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
from app.export.builders.html_builder import build_html
from app.export.builders.image_sources import load_image_source, resolve_original_path
from app.export.builders.pdf_builder import CARD_TEXT_WIDTH, build_pdf, max_chars_for_width
from app.export.builders.zip_builder import build_zip_archive
from app.media import ThumbnailService
from app.export.template_renderer import format_xinhua_location, render_caption


PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)
JPG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xd9"
PDF_JPG_BYTES = (
    b"\xff\xd8"
    b"\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00"
    b"\xff\xd9"
)


CAPTION_COVERAGE = {
    "city": "Quito",
    "country": "Ecuador",
    "agency": "Xinhua",
    "photographer": "Ricardo Landeta",
    "editor": "rl",
    "submit_date": "2026-08-16",
    "event_date": "2026-08-15",
}


def docx_members(content: bytes) -> tuple[list[str], str]:
    with zipfile.ZipFile(BytesIO(content)) as archive:
        return archive.namelist(), archive.read("word/document.xml").decode("utf-8")


def docx_media(content: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(BytesIO(content)) as archive:
        return {
            name: archive.read(name)
            for name in archive.namelist()
            if name.startswith("word/media/")
        }


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


def pdf_image_dimensions(content: bytes) -> list[tuple[int, int]]:
    return [
        (int(width), int(height))
        for width, height in re.findall(rb"/Subtype /Image /Width (\d+) /Height (\d+)", content)
    ]


def pdf_card_count(content: bytes) -> int:
    return len(re.findall(rb"\d+\.\d+ \d+\.\d+ \d+\.\d+ \d+\.\d+ re S", content))


def build_test_jpeg(width: int, height: int, *, quality: int = 95) -> bytes:
    try:
        from PIL import Image
    except ModuleNotFoundError as error:
        if error.name == "PIL":
            raise unittest.SkipTest("Pillow no está disponible para crear JPEGs de prueba.") from error
        raise

    image = Image.new("RGB", (width, height), color=(210, 80, 40))
    output = BytesIO()
    image.save(output, format="JPEG", quality=quality)
    return output.getvalue()


def image_dimensions(image_bytes: bytes) -> tuple[int, int]:
    try:
        from PIL import Image
    except ModuleNotFoundError as error:
        if error.name == "PIL":
            raise unittest.SkipTest("Pillow no está disponible para leer JPEGs de prueba.") from error
        raise

    with Image.open(BytesIO(image_bytes)) as image:
        return image.size


class DocxExportTest(unittest.TestCase):
    def test_format_xinhua_location_handles_capitals_city_locality_and_auto(self):
        cases = (
            ("Quito", "Ecuador", "auto", "en Quito, capital de Ecuador"),
            ("Quito", "Ecuador", "city", "en Quito, capital de Ecuador"),
            ("Quito", "Ecuador", "locality", "en Quito, capital de Ecuador"),
            ("Cuenca", "Ecuador", "city", "en la ciudad de Cuenca, en Ecuador"),
            ("Cuenca", "Ecuador", "auto", "en Cuenca, en Ecuador"),
            ("Mindo", "Ecuador", "locality", "en Mindo, en Ecuador"),
            ("San Antonio de Pichincha", "Ecuador", "auto", "en San Antonio de Pichincha, en Ecuador"),
            ("Bogotá", "Colombia", "auto", "en Bogotá, capital de Colombia"),
            ("Beijing", "China", "auto", "en Beijing, capital de China"),
            ("Mindo", "", "locality", "en Mindo"),
            ("Mindo", "Ecuador", "", "en Mindo, en Ecuador"),
        )

        for city, country, locality_type, expected in cases:
            with self.subTest(city=city, country=country, locality_type=locality_type):
                self.assertEqual(
                    format_xinhua_location(city, country, locality_type),
                    expected,
                )

    def test_xinhua_normal_caption_different_dates_keeps_existing_prefix(self):
        caption = render_caption(
            "xinhua",
            CAPTION_COVERAGE,
            {"caption_narrative": "visitantes recorren el monumento ecuatorial"},
        )

        self.assertIn(
            "Imagen del 15 de agosto de 2026 de visitantes recorren el monumento ecuatorial",
            caption,
        )
        self.assertNotIn("Vista aérea tomada con un dron", caption)

    def test_xinhua_normal_caption_same_dates_keeps_date_at_end(self):
        coverage = {**CAPTION_COVERAGE, "event_date": "2026-08-16"}

        caption = render_caption(
            "xinhua",
            coverage,
            {"caption_narrative": "Visitantes recorren el monumento ecuatorial"},
        )

        self.assertIn(
            "Visitantes recorren el monumento ecuatorial, en Quito, capital de Ecuador, el 16 de agosto de 2026.",
            caption,
        )
        self.assertNotIn("Imagen del", caption)

    def test_xinhua_drone_caption_different_dates_uses_drone_prefix_with_date(self):
        caption = render_caption(
            "xinhua",
            CAPTION_COVERAGE,
            {
                "caption_narrative": "la Ciudad Mitad del Mundo y su monumento ecuatorial",
                "is_drone": True,
            },
        )

        self.assertIn(
            "Vista aérea tomada con un dron el 15 de agosto de 2026 de la Ciudad Mitad del Mundo y su monumento ecuatorial",
            caption,
        )
        self.assertNotIn("el 16 de agosto de 2026. (Xinhua", caption)

    def test_xinhua_drone_caption_same_dates_uses_drone_prefix_and_final_date(self):
        coverage = {**CAPTION_COVERAGE, "event_date": "2026-08-16"}

        caption = render_caption(
            "xinhua",
            coverage,
            {
                "caption_narrative": "la Ciudad Mitad del Mundo y su monumento ecuatorial",
                "is_drone": True,
            },
        )

        self.assertIn(
            "Vista aérea tomada con un dron de la Ciudad Mitad del Mundo y su monumento ecuatorial",
            caption,
        )
        self.assertIn(
            "en Quito, capital de Ecuador, el 16 de agosto de 2026.",
            caption,
        )

    def test_xinhua_caption_location_combinations(self):
        cases = (
            (
                "normal_diff_capital",
                CAPTION_COVERAGE,
                {"caption_narrative": "visitantes recorren el monumento ecuatorial"},
                "Imagen del 15 de agosto de 2026 de visitantes recorren el monumento ecuatorial, en Quito, capital de Ecuador.",
            ),
            (
                "normal_same_capital",
                {**CAPTION_COVERAGE, "event_date": "2026-08-16"},
                {"caption_narrative": "Visitantes recorren el monumento ecuatorial"},
                "Visitantes recorren el monumento ecuatorial, en Quito, capital de Ecuador, el 16 de agosto de 2026.",
            ),
            (
                "drone_diff_capital",
                CAPTION_COVERAGE,
                {"caption_narrative": "la Ciudad Mitad del Mundo", "is_drone": True},
                "Vista aérea tomada con un dron el 15 de agosto de 2026 de la Ciudad Mitad del Mundo, en Quito, capital de Ecuador.",
            ),
            (
                "drone_same_capital",
                {**CAPTION_COVERAGE, "event_date": "2026-08-16"},
                {"caption_narrative": "la Ciudad Mitad del Mundo", "is_drone": True},
                "Vista aérea tomada con un dron de la Ciudad Mitad del Mundo, en Quito, capital de Ecuador, el 16 de agosto de 2026.",
            ),
            (
                "normal_city",
                {**CAPTION_COVERAGE, "city": "Cuenca", "locality_type": "city", "event_date": "2026-08-16"},
                {"caption_narrative": "Personas caminan por el centro histórico"},
                "Personas caminan por el centro histórico, en la ciudad de Cuenca, en Ecuador, el 16 de agosto de 2026.",
            ),
            (
                "drone_city",
                {**CAPTION_COVERAGE, "city": "Cuenca", "locality_type": "city", "event_date": "2026-08-16"},
                {"caption_narrative": "centro histórico", "is_drone": True},
                "Vista aérea tomada con un dron de centro histórico, en la ciudad de Cuenca, en Ecuador, el 16 de agosto de 2026.",
            ),
            (
                "normal_locality",
                {**CAPTION_COVERAGE, "city": "Mindo", "locality_type": "locality", "event_date": "2026-08-16"},
                {"caption_narrative": "Visitantes recorren senderos"},
                "Visitantes recorren senderos, en Mindo, en Ecuador, el 16 de agosto de 2026.",
            ),
            (
                "drone_locality",
                {**CAPTION_COVERAGE, "city": "Mindo", "locality_type": "locality", "event_date": "2026-08-16"},
                {"caption_narrative": "senderos junto al bosque", "is_drone": True},
                "Vista aérea tomada con un dron de senderos junto al bosque, en Mindo, en Ecuador, el 16 de agosto de 2026.",
            ),
        )

        for name, coverage, photo, expected in cases:
            with self.subTest(name=name):
                self.assertIn(expected, render_caption("xinhua", coverage, photo))

    def test_xinhua_missing_is_drone_behaves_as_normal_false(self):
        caption = render_caption(
            "xinhua",
            CAPTION_COVERAGE,
            {"caption_narrative": "visitantes recorren el monumento ecuatorial"},
        )

        self.assertIn("Imagen del 15 de agosto de 2026", caption)
        self.assertNotIn("Vista aérea tomada con un dron", caption)

    def test_xinhua_drone_caption_avoids_duplicate_aerial_phrase(self):
        caption = render_caption(
            "xinhua",
            CAPTION_COVERAGE,
            {
                "caption_narrative": "Vista aérea tomada con un dron de la Ciudad Mitad del Mundo",
                "is_drone": True,
            },
        )

        self.assertEqual(caption.count("Vista aérea tomada con un dron"), 1)
        self.assertIn("de la Ciudad Mitad del Mundo", caption)

    def test_pdf_embeds_media_from_data_url(self):
        encoded = base64.b64encode(build_test_jpeg(800, 533)).decode("ascii")
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
            target.write_bytes(build_test_jpeg(800, 533))

            with patch("app.config.LENS_MEDIA_ROOT", str(media_root)):
                content = build_pdf(
                    [build_photo(id="photo-2", filename="IMG002.jpg", storage_path=storage_path)],
                    {"coverage_name": "Cobertura Quito", "country": "Ecuador"},
                )

        assert_pdf_has_image(self, content)

    def test_pdf_embeds_media_from_flow_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            flow_path = Path(temp_dir) / "IMG003.jpg"
            flow_path.write_bytes(build_test_jpeg(800, 533))

            content = build_pdf(
                [build_photo(id="photo-3", filename="IMG003.jpg", flow_path=str(flow_path))],
                {"coverage_name": "Cobertura Quito", "country": "Ecuador"},
            )

        assert_pdf_has_image(self, content)

    def test_html_embeds_real_portable_previews_from_storage_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            media_root = Path(temp_dir) / "media"
            thumbnail_root = Path(temp_dir) / "thumbnails"
            storage_path = "coverages/cov-1/IMG001.jpg"
            target = media_root / storage_path
            target.parent.mkdir(parents=True)
            target.write_bytes(build_test_jpeg(1200, 800))

            with (
                patch("app.config.LENS_MEDIA_ROOT", str(media_root)),
                patch("app.config.THUMBNAIL_ROOT", str(thumbnail_root)),
            ):
                html = build_html(
                    [build_photo(storage_path=storage_path)],
                    {**CAPTION_COVERAGE, "coverage_name": "Cobertura Quito"},
                ).decode("utf-8")

        self.assertIn('src="data:image/jpeg;base64,', html)
        self.assertEqual(html.count('class="photo-card"'), 1)
        self.assertNotIn("Sin miniatura", html)
        self.assertNotIn(str(media_root), html)
        self.assertNotIn('src="/', html)
        self.assertIn("--page-bg: #0f1720;", html)
        self.assertIn("--card-bg: #17222e;", html)
        self.assertIn("--text: #f4f4f4;", html)
        self.assertIn("display: flex;", html)
        self.assertIn("align-items: center;", html)
        self.assertIn("justify-content: center;", html)
        self.assertIn("object-fit: contain;", html)
        self.assertIn("overflow-wrap: anywhere;", html)
        self.assertIn("@media (max-width: 640px)", html)
        self.assertIn(".photo-card { grid-template-columns: 1fr;", html)
        self.assertIn("COBERTURA QUITO · ECUADOR", html)
        self.assertIn("<dt>Agencia</dt>", html)
        self.assertIn("<dt>Cobertura</dt>", html)
        self.assertIn("<dt>Ciudad</dt>", html)
        self.assertIn("FIN DEL ENVÍO", html)

    def test_pdf_uses_docx_preview_source_and_compact_photo_cards(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            media_root = root / "media"
            thumbnail_root = root / "thumbnails"
            photos = []
            for index in range(1, 4):
                storage_path = f"coverages/cov-1/IMG00{index}.jpg"
                target = media_root / storage_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(build_test_jpeg(2400, 1600))
                photos.append(build_photo(
                    id=f"photo-{index}",
                    filename=f"IMG00{index}.jpg",
                    storage_path=storage_path,
                    caption=f"Caption {index}.",
                ))

            with (
                patch("app.config.LENS_MEDIA_ROOT", str(media_root)),
                patch("app.config.THUMBNAIL_ROOT", str(thumbnail_root)),
            ):
                docx = build_docx(photos, {**CAPTION_COVERAGE, "coverage_name": "Cobertura Quito"})
                pdf = build_pdf(photos, {**CAPTION_COVERAGE, "coverage_name": "Cobertura Quito"})
            original_size = sum((media_root / photo.storage_path).stat().st_size for photo in photos)

        _names, document_xml = docx_members(docx)
        self.assertEqual(document_xml.count("<w:tbl><w:tblPr>") - 1, 3)
        self.assertEqual(pdf_card_count(pdf), 3)
        self.assertEqual(pdf.count(b"/Subtype /Image"), 3)
        for photo in photos:
            self.assertIn(photo.filename.encode("latin-1"), pdf)
        self.assertIn(b"q 155.00 0 0 103.27", pdf)
        self.assertIn(b"COBERTURA QUITO", pdf)
        self.assertIn(b"Agencia:", pdf)
        self.assertIn(b"Cobertura:", pdf)
        self.assertIn(b"Ciudad:", pdf)
        self.assertIn("FIN DEL ENV".encode("latin-1"), pdf)

        dimensions = pdf_image_dimensions(pdf)
        self.assertEqual(len(dimensions), 3)
        self.assertTrue(all(max(size) <= 800 for size in dimensions))
        self.assertEqual(dimensions[0], (800, 533))
        self.assertLess(len(pdf), original_size)

    def test_pdf_fixture_size_does_not_embed_large_originals(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            media_root = root / "media"
            thumbnail_root = root / "thumbnails"
            photos = []
            for index in range(1, 13):
                storage_path = f"coverages/cov-1/BIG{index:02}.jpg"
                target = media_root / storage_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(build_test_jpeg(2400, 1600, quality=98))
                photos.append(build_photo(
                    id=f"photo-{index}",
                    filename=f"BIG{index:02}.jpg",
                    storage_path=storage_path,
                    caption="Caption de control para PDF compacto.",
                ))

            with (
                patch("app.config.LENS_MEDIA_ROOT", str(media_root)),
                patch("app.config.THUMBNAIL_ROOT", str(thumbnail_root)),
            ):
                pdf = build_pdf(photos, {**CAPTION_COVERAGE, "coverage_name": "Fixture PDF"})

        self.assertEqual(pdf.count(b"/Subtype /Image"), 12)
        self.assertEqual(pdf_card_count(pdf), 12)
        self.assertLess(len(pdf), 1_500_000)

    def test_pdf_wraps_long_filename_and_caption_inside_card_width(self):
        long_filename = "CENTRO-HISTORICO-EC-" + ("1269" * 18) + ".jpg"
        long_caption = (
            "Caption con una palabra extremadamente larga "
            + ("supercalifragilistico" * 10)
            + " y texto adicional para validar varias lineas dentro de la tarjeta."
        )
        encoded = base64.b64encode(build_test_jpeg(800, 533)).decode("ascii")

        pdf = build_pdf(
            [build_photo(filename=long_filename, caption=long_caption, data_url=f"data:image/jpeg;base64,{encoded}")],
            {**CAPTION_COVERAGE, "coverage_name": "Cobertura Quito"},
        )
        filename_limit = max_chars_for_width(CARD_TEXT_WIDTH, 12, bold=True)
        caption_limit = max_chars_for_width(CARD_TEXT_WIDTH, 10)

        self.assertEqual(pdf_card_count(pdf), 1)
        self.assertNotIn(long_filename.encode("latin-1"), pdf)
        self.assertIn(long_filename[:filename_limit].encode("latin-1"), pdf)
        self.assertTrue(all(len(line) <= filename_limit for line in re.findall(rb"BT /F2 12 Tf .*?\((.*?)\) Tj ET", pdf)))
        self.assertTrue(all(len(line) <= caption_limit for line in re.findall(rb"BT /F1 10 Tf .*?\((.*?)\) Tj ET", pdf)))

    def test_thumbnail_failure_keeps_filename_and_caption_in_html_and_pdf(self):
        photo = build_photo(
            filename="MISSING.jpg",
            storage_path="coverages/cov-1/missing.jpg",
            data_url="",
            caption="Caption conservado.",
            available_on_disk=False,
        )

        html = build_html([photo], {**CAPTION_COVERAGE, "coverage_name": "Cobertura Quito"}).decode("utf-8")
        pdf = build_pdf([photo], {**CAPTION_COVERAGE, "coverage_name": "Cobertura Quito"})

        self.assertIn("Sin miniatura", html)
        self.assertIn("MISSING.jpg", html)
        self.assertIn("Caption conservado.", html)
        self.assertIn(b"MISSING.jpg", pdf)
        self.assertIn(b"Caption conservado.", pdf)
        self.assertIn(b"Sin miniatura", pdf)

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

    def test_docx_embeds_reduced_jpeg_preview_and_preserves_original(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            media_root = root / "media"
            thumbnail_root = root / "thumbnails"
            storage_path = "coverages/cov-1/IMG001.jpg"
            target = media_root / storage_path
            target.parent.mkdir(parents=True)
            original_bytes = build_test_jpeg(2400, 1600)
            target.write_bytes(original_bytes)

            with (
                patch("app.config.LENS_MEDIA_ROOT", str(media_root)),
                patch("app.config.THUMBNAIL_ROOT", str(thumbnail_root)),
            ):
                content = build_docx(
                    [build_photo(storage_path=storage_path)],
                    {"coverage_name": "Cobertura Quito", "country": "Ecuador"},
                )

            media = docx_media(content)
            self.assertEqual(len(media), 1)
            embedded_name, embedded_bytes = next(iter(media.items()))

            self.assertTrue(embedded_name.endswith(".jpg"))
            self.assertLess(len(embedded_bytes), len(original_bytes))
            self.assertLessEqual(max(image_dimensions(embedded_bytes)), 800)
            self.assertEqual(target.read_bytes(), original_bytes)
            self.assertIn("word/document.xml", docx_members(content)[0])

    def test_docx_reuses_existing_atlas_thumbnail_when_available(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            media_root = root / "media"
            thumbnail_root = root / "thumbnails"
            storage_path = "coverages/cov-1/IMG001.jpg"
            target = media_root / storage_path
            target.parent.mkdir(parents=True)
            target.write_bytes(build_test_jpeg(2400, 1600))
            thumbnail_bytes = build_test_jpeg(320, 213, quality=70)
            service = ThumbnailService(thumbnail_root)
            thumbnail_path = service.thumbnail_path_for(target)
            self.assertIsNotNone(thumbnail_path)
            thumbnail_path.parent.mkdir(parents=True)
            thumbnail_path.write_bytes(thumbnail_bytes)

            with (
                patch("app.config.LENS_MEDIA_ROOT", str(media_root)),
                patch("app.config.THUMBNAIL_ROOT", str(thumbnail_root)),
            ):
                content = build_docx(
                    [build_photo(storage_path=storage_path)],
                    {"coverage_name": "Cobertura Quito", "country": "Ecuador"},
                )

            media = docx_media(content)
            self.assertEqual(next(iter(media.values())), thumbnail_bytes)

    def test_docx_thumbnail_cell_centers_image(self):
        encoded = base64.b64encode(build_test_jpeg(800, 533)).decode("ascii")
        content = build_docx(
            [build_photo(data_url=f"data:image/jpeg;base64,{encoded}")],
            {"coverage_name": "Cobertura Quito", "country": "Ecuador"},
        )

        _names, document_xml = docx_members(content)
        self.assertIn('<w:jc w:val="center"/>', document_xml)
        self.assertIn('<w:vAlign w:val="center"/>', document_xml)

    def test_docx_adds_visual_spacing_after_coverage_header(self):
        encoded = base64.b64encode(build_test_jpeg(800, 533)).decode("ascii")
        content = build_docx(
            [build_photo(data_url=f"data:image/jpeg;base64,{encoded}")],
            {"coverage_name": "Cobertura Quito", "country": "Ecuador"},
        )

        _names, document_xml = docx_members(content)
        self.assertIn('<w:spacing w:after="420"', document_xml)

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
