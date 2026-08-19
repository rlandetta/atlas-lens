from __future__ import annotations

import io
import zlib
from dataclasses import dataclass

from app.export.builders.image_sources import load_preview_image_source
from app.export.models import ExportPhoto

PAGE_WIDTH = 612
PAGE_HEIGHT = 792
MARGIN_X = 72
TOP_Y = 720
BOTTOM_Y = 36
TEXT_RGB = (0.2, 0.2, 0.2)
MAX_IMAGE_WIDTH = 205
MAX_IMAGE_HEIGHT = 137
CARD_GAP = 18
CARD_PADDING = 12
CARD_IMAGE_WIDTH = 155
CARD_IMAGE_HEIGHT = 105
CARD_TEXT_X = MARGIN_X + CARD_PADDING + CARD_IMAGE_WIDTH + 18
CARD_RIGHT = PAGE_WIDTH - MARGIN_X
CARD_WIDTH = CARD_RIGHT - MARGIN_X
CARD_TEXT_WIDTH = CARD_RIGHT - CARD_TEXT_X - CARD_PADDING
FILENAME_LEADING = 14
CAPTION_LEADING = 13


@dataclass(frozen=True)
class PdfImage:
    name: str
    width: int
    height: int
    color_space: str
    bits: int
    filters: str
    data: bytes


def pdf_escape(value: str) -> bytes:
    text = str(value or "").encode("latin-1", "replace").decode("latin-1")
    return (
        text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    ).encode("latin-1")


def coverage_name(coverage_metadata: dict) -> str:
    return str(coverage_metadata.get("coverage_name") or coverage_metadata.get("name") or "Reporte editorial")


def build_report_title(coverage_metadata: dict) -> str:
    title = coverage_name(coverage_metadata).upper()
    country = str(coverage_metadata.get("country", "")).upper()
    return f"{title} · {country}".strip(" ·")


def jpeg_size(data: bytes) -> tuple[int, int] | None:
    if not data.startswith(b"\xff\xd8"):
        return None
    index = 2
    while index < len(data) - 9:
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        index += 2
        if marker in {0xD8, 0xD9}:
            continue
        segment_length = int.from_bytes(data[index:index + 2], "big")
        if 0xC0 <= marker <= 0xC3:
            height = int.from_bytes(data[index + 3:index + 5], "big")
            width = int.from_bytes(data[index + 5:index + 7], "big")
            return width, height
        index += segment_length
    return None


def png_chunks(data: bytes):
    index = 8
    while index + 8 <= len(data):
        length = int.from_bytes(data[index:index + 4], "big")
        kind = data[index + 4:index + 8]
        payload = data[index + 8:index + 8 + length]
        yield kind, payload
        index += 12 + length


def paeth(left: int, above: int, upper_left: int) -> int:
    estimate = left + above - upper_left
    distances = (abs(estimate - left), abs(estimate - above), abs(estimate - upper_left))
    if distances[0] <= distances[1] and distances[0] <= distances[2]:
        return left
    if distances[1] <= distances[2]:
        return above
    return upper_left


def defilter_png(raw: bytes, width: int, height: int, channels: int, bit_depth: int) -> bytes | None:
    if bit_depth != 8:
        return None
    stride = width * channels
    output = bytearray()
    previous = bytearray(stride)
    index = 0
    for _ in range(height):
        if index >= len(raw):
            return None
        filter_type = raw[index]
        index += 1
        row = bytearray(raw[index:index + stride])
        index += stride
        if len(row) != stride:
            return None
        for column in range(stride):
            left = row[column - channels] if column >= channels else 0
            above = previous[column]
            upper_left = previous[column - channels] if column >= channels else 0
            if filter_type == 1:
                row[column] = (row[column] + left) & 0xFF
            elif filter_type == 2:
                row[column] = (row[column] + above) & 0xFF
            elif filter_type == 3:
                row[column] = (row[column] + ((left + above) // 2)) & 0xFF
            elif filter_type == 4:
                row[column] = (row[column] + paeth(left, above, upper_left)) & 0xFF
            elif filter_type != 0:
                return None
        output.extend(row)
        previous = row
    return bytes(output)


def png_image(data: bytes, name: str) -> PdfImage | None:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    width = height = bit_depth = color_type = None
    compressed_parts = []
    for kind, payload in png_chunks(data):
        if kind == b"IHDR":
            width = int.from_bytes(payload[0:4], "big")
            height = int.from_bytes(payload[4:8], "big")
            bit_depth = payload[8]
            color_type = payload[9]
            compression = payload[10]
            filter_method = payload[11]
            interlace = payload[12]
            if compression or filter_method or interlace:
                return None
        elif kind == b"IDAT":
            compressed_parts.append(payload)
    if width is None or height is None or bit_depth != 8 or color_type not in {2, 6}:
        return None
    channels = 3 if color_type == 2 else 4
    try:
        raw = zlib.decompress(b"".join(compressed_parts))
    except zlib.error:
        return None
    pixels = defilter_png(raw, width, height, channels, bit_depth)
    if pixels is None:
        return None
    if channels == 4:
        pixels = bytes(component for index, component in enumerate(pixels) if index % 4 != 3)
    return PdfImage(name=name, width=width, height=height, color_space="DeviceRGB", bits=8, filters="/FlateDecode", data=zlib.compress(pixels))


def build_pdf_image(photo: ExportPhoto, name: str) -> PdfImage | None:
    preview = load_preview_image_source(photo)
    if preview is None:
        return None
    if preview.content_type in {"image/jpeg", "image/jpg"}:
        return PdfImage(name=name, width=preview.width, height=preview.height, color_space="DeviceRGB", bits=8, filters="/DCTDecode", data=preview.data)
    if preview.content_type == "image/png":
        return png_image(preview.data, name)
    return None


def max_chars_for_width(max_width: float, size: int, *, bold: bool = False) -> int:
    average_width = size * (0.56 if bold else 0.52)
    return max(int(max_width / average_width), 8)


def split_long_word(word: str, max_chars: int) -> list[str]:
    return [word[index:index + max_chars] for index in range(0, len(word), max_chars)] or [""]


def wrap_text(value: str, max_width: float, size: int = 11, *, bold: bool = False) -> list[str]:
    max_chars = max_chars_for_width(max_width, size, bold=bold)
    words: list[str] = []
    for word in str(value or "").split():
        words.extend(split_long_word(word, max_chars) if len(word) > max_chars else [word])
    lines = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > max_chars and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [""]


def scaled_size(width: int, height: int) -> tuple[float, float]:
    scale = min(MAX_IMAGE_WIDTH / max(width, 1), MAX_IMAGE_HEIGHT / max(height, 1), 1)
    return width * scale, height * scale


def scaled_card_image_size(width: int, height: int) -> tuple[float, float]:
    scale = min(CARD_IMAGE_WIDTH / max(width, 1), CARD_IMAGE_HEIGHT / max(height, 1), 1)
    return width * scale, height * scale


def text_op(x: float, y: float, text: str, size: int = 11, bold: bool = False) -> bytes:
    font = "/F1" if not bold else "/F2"
    return b"BT " + font.encode("ascii") + f" {size} Tf {TEXT_RGB[0]} {TEXT_RGB[1]} {TEXT_RGB[2]} rg {x:.2f} {y:.2f} Td ".encode("ascii") + b"(" + pdf_escape(text) + b") Tj ET\n"


def line_op(y: float) -> bytes:
    return f"0.82 0.85 0.88 RG 0.6 w {MARGIN_X} {y:.2f} m {PAGE_WIDTH - MARGIN_X} {y:.2f} l S\n".encode("ascii")


def rect_op(x: float, y: float, width: float, height: float, *, fill: bool = False) -> bytes:
    if fill:
        return f"0.96 0.97 0.98 rg {x:.2f} {y:.2f} {width:.2f} {height:.2f} re f\n".encode("ascii")
    return f"0.82 0.85 0.88 RG 0.6 w {x:.2f} {y:.2f} {width:.2f} {height:.2f} re S\n".encode("ascii")


def image_op(image: PdfImage, x: float, y: float, width: float, height: float) -> bytes:
    return f"q {width:.2f} 0 0 {height:.2f} {x:.2f} {y:.2f} cm /{image.name} Do Q\n".encode("ascii")


def build_pdf(photos: list[ExportPhoto], coverage_metadata: dict) -> bytes:
    images_by_filename: dict[str, PdfImage] = {}
    for index, photo in enumerate(photos, start=1):
        image = build_pdf_image(photo, f"Im{index}")
        if image:
            images_by_filename[photo.filename] = image

    pages: list[bytearray] = [bytearray()]
    y = TOP_Y

    def ensure(space: float):
        nonlocal y
        if y - space < BOTTOM_Y:
            pages.append(bytearray())
            y = TOP_Y

    def add_text(text: str, size: int = 11, bold: bool = False, x: float = MARGIN_X, leading: float | None = None):
        nonlocal y
        ensure(size + 8)
        pages[-1].extend(text_op(x, y, text, size, bold))
        y -= leading if leading is not None else size + 5

    add_text(build_report_title(coverage_metadata), size=18, bold=True, leading=30)
    label_x = MARGIN_X
    value_x = MARGIN_X + 128
    rows = (
        ("Agencia:", coverage_metadata.get("agency", "")),
        ("Cobertura:", coverage_metadata.get("coverage_name") or coverage_metadata.get("name", "")),
        ("Ciudad:", coverage_metadata.get("city", "")),
        ("Fotógrafo:", coverage_metadata.get("photographer", "")),
        ("Editor:", coverage_metadata.get("editor", "")),
        ("Fecha de cobertura:", coverage_metadata.get("event_date") or coverage_metadata.get("submit_date", "")),
    )
    for label, value in rows:
        ensure(16)
        pages[-1].extend(text_op(label_x, y, str(label), 11, True))
        pages[-1].extend(text_op(value_x, y, str(value), 11, False))
        y -= 15
    y -= 26

    for index, photo in enumerate(photos, start=1):
        image = images_by_filename.get(photo.filename)
        filename_lines = wrap_text(f"{index}. {photo.filename}", CARD_TEXT_WIDTH, 12, bold=True)
        caption_lines = wrap_text(photo.caption or "[Sin caption]", CARD_TEXT_WIDTH, 10)
        text_height = len(filename_lines) * FILENAME_LEADING + 8 + len(caption_lines) * CAPTION_LEADING
        block_height = max(CARD_IMAGE_HEIGHT, text_height) + (CARD_PADDING * 2)
        ensure(block_height)
        card_top = y
        card_bottom = y - block_height
        pages[-1].extend(rect_op(MARGIN_X, card_bottom, CARD_WIDTH, block_height))
        pages[-1].extend(rect_op(MARGIN_X + CARD_PADDING, card_bottom + CARD_PADDING, CARD_IMAGE_WIDTH, CARD_IMAGE_HEIGHT, fill=True))
        if image:
            image_width, image_height = scaled_card_image_size(image.width, image.height)
            image_x = MARGIN_X + CARD_PADDING + ((CARD_IMAGE_WIDTH - image_width) / 2)
            image_y = card_bottom + CARD_PADDING + ((CARD_IMAGE_HEIGHT - image_height) / 2)
            pages[-1].extend(image_op(image, image_x, image_y, image_width, image_height))
        else:
            pages[-1].extend(text_op(MARGIN_X + CARD_PADDING + 30, card_bottom + CARD_PADDING + 48, "Sin miniatura", 10, False))
        text_y = card_top - CARD_PADDING - 11
        for line in filename_lines:
            pages[-1].extend(text_op(CARD_TEXT_X, text_y, line, 12, True))
            text_y -= FILENAME_LEADING
        text_y -= 8
        for line in caption_lines:
            pages[-1].extend(text_op(CARD_TEXT_X, text_y, line, 10, False))
            text_y -= CAPTION_LEADING
        y = card_bottom - CARD_GAP

    ensure(80)
    add_text("«········ FIN DEL ENVÍO ········»", size=14, bold=True, x=180, leading=0)

    return assemble_pdf(pages, list(images_by_filename.values()))


def pdf_stream(data: bytes) -> bytes:
    return b"<< /Length " + str(len(data)).encode("ascii") + b" >>\nstream\n" + data + b"endstream"


def assemble_pdf(page_streams: list[bytearray], images: list[PdfImage]) -> bytes:
    page_count = len(page_streams)
    catalog_obj = 1
    pages_obj = 2
    first_page_obj = 3
    font_regular_obj = first_page_obj + page_count
    font_bold_obj = font_regular_obj + 1
    first_image_obj = font_bold_obj + 1
    first_content_obj = first_image_obj + len(images)

    objects: dict[int, bytes] = {}
    page_refs = " ".join(f"{first_page_obj + i} 0 R" for i in range(page_count))
    objects[catalog_obj] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[pages_obj] = f"<< /Type /Pages /Kids [{page_refs}] /Count {page_count} >>".encode("ascii")
    objects[font_regular_obj] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Arial /Encoding /WinAnsiEncoding >>"
    objects[font_bold_obj] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Arial-BoldMT /Encoding /WinAnsiEncoding >>"

    image_refs = []
    for offset, image in enumerate(images):
        object_number = first_image_obj + offset
        image_refs.append(f"/{image.name} {object_number} 0 R")
        objects[object_number] = (
            f"<< /Type /XObject /Subtype /Image /Width {image.width} /Height {image.height} "
            f"/ColorSpace /{image.color_space} /BitsPerComponent {image.bits} /Filter {image.filters} /Length {len(image.data)} >>\nstream\n"
        ).encode("ascii") + image.data + b"\nendstream"

    xobjects = f"/XObject << {' '.join(image_refs)} >>" if image_refs else ""
    resources = f"<< /Font << /F1 {font_regular_obj} 0 R /F2 {font_bold_obj} 0 R >> {xobjects} >>"
    for index, stream in enumerate(page_streams):
        page_obj = first_page_obj + index
        content_obj = first_content_obj + index
        objects[page_obj] = (
            f"<< /Type /Page /Parent {pages_obj} 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            f"/Resources {resources} /Contents {content_obj} 0 R >>"
        ).encode("ascii")
        objects[content_obj] = pdf_stream(bytes(stream))

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number in range(1, max(objects) + 1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode("ascii"))
        pdf.extend(objects[number])
        pdf.extend(b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(f"trailer\n<< /Size {len(offsets)} /Root {catalog_obj} 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii"))
    return bytes(pdf)
