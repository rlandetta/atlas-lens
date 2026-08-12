from __future__ import annotations

import io
from dataclasses import dataclass
from html import escape
from zipfile import ZIP_DEFLATED, ZipFile

from app.export.builders.image_sources import load_image_source
from app.export.models import ExportPhoto

EMU_PER_INCH = 914400
TEXT_COLOR = "333333"
MAX_IMAGE_WIDTH_EMU = int(1.70 * EMU_PER_INCH)
MAX_IMAGE_HEIGHT_EMU = int(1.13 * EMU_PER_INCH)


@dataclass(frozen=True)
class EmbeddedImage:
    relationship_id: str
    filename: str
    content_type: str
    width_emu: int
    height_emu: int
    alt_text: str
    data: bytes


def xml_text(value: str) -> str:
    return escape(str(value or ""), quote=True)


def normalize_title(value: str) -> str:
    return "-".join(str(value or "").upper().split())


def build_report_title(coverage_metadata: dict) -> str:
    coverage_name = normalize_title(coverage_metadata.get("coverage_name") or coverage_metadata.get("name", ""))
    country = str(coverage_metadata.get("country", "")).upper()
    return f"{coverage_name} · {country}".strip(" ·")


def detect_image_size(image_bytes: bytes, content_type: str) -> tuple[int, int]:
    if content_type == "image/png" and image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        width = int.from_bytes(image_bytes[16:20], "big")
        height = int.from_bytes(image_bytes[20:24], "big")
        return width, height

    if content_type in {"image/jpeg", "image/jpg"} and image_bytes.startswith(b"\xff\xd8"):
        index = 2
        while index < len(image_bytes) - 9:
            if image_bytes[index] != 0xFF:
                index += 1
                continue
            marker = image_bytes[index + 1]
            index += 2
            if marker in {0xD8, 0xD9}:
                continue
            segment_length = int.from_bytes(image_bytes[index:index + 2], "big")
            if 0xC0 <= marker <= 0xC3:
                height = int.from_bytes(image_bytes[index + 3:index + 5], "big")
                width = int.from_bytes(image_bytes[index + 5:index + 7], "big")
                return width, height
            index += segment_length

    return 1200, 800


def scaled_dimensions(width: int, height: int) -> tuple[int, int]:
    width_emu = max(width, 1) * 9525
    height_emu = max(height, 1) * 9525
    scale = min(
        MAX_IMAGE_WIDTH_EMU / width_emu,
        MAX_IMAGE_HEIGHT_EMU / height_emu,
        1,
    )
    return int(width_emu * scale), int(height_emu * scale)


def image_extension(content_type: str, fallback_name: str) -> str:
    lowered = fallback_name.lower()
    if lowered.endswith((".jpg", ".jpeg")):
        return "jpg"
    if lowered.endswith(".png"):
        return "png"
    if lowered.endswith(".webp"):
        return "webp"
    if content_type == "image/png":
        return "png"
    if content_type == "image/webp":
        return "webp"
    return "jpg"


def build_embedded_images(photos: list[ExportPhoto]) -> list[EmbeddedImage]:
    images = []
    for index, photo in enumerate(photos, start=1):
        image_bytes, content_type = load_image_source(photo)
        if not image_bytes:
            continue
        width, height = detect_image_size(image_bytes, content_type)
        width_emu, height_emu = scaled_dimensions(width, height)
        extension = image_extension(content_type, photo.filename)
        images.append(EmbeddedImage(
            relationship_id=f"rIdImg{index}",
            filename=f"image{index}.{extension}",
            content_type={
                "png": "image/png",
                "webp": "image/webp",
            }.get(extension, "image/jpeg"),
            width_emu=width_emu,
            height_emu=height_emu,
            alt_text=photo.filename,
            data=image_bytes,
        ))
    return images


def paragraph(text: str = "", *, bold: bool = False, size: int = 22, align: str | None = None, color: str | None = None, spacing_after: int = 120, keep_next: bool = False, line: str | None = None) -> str:
    ppr = []
    if align:
        ppr.append(f'<w:jc w:val="{align}"/>')
    if keep_next:
        ppr.append('<w:keepNext/>')
        ppr.append('<w:keepLines/>')
    if line:
        ppr.append('<w:pBdr><w:bottom w:val="single" w:sz="4" w:space="1" w:color="B8C0CA"/></w:pBdr>')
    ppr.append(f'<w:spacing w:after="{spacing_after}" w:line="276" w:lineRule="auto"/>')
    rpr = [f'<w:sz w:val="{size}"/>', f'<w:szCs w:val="{size}"/>', '<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>']
    rpr.append(f'<w:color w:val="{color or TEXT_COLOR}"/>')
    if bold:
        rpr.append('<w:b/>')
    text_node = '<w:t/>' if not text else f'<w:t xml:space="preserve">{xml_text(text)}</w:t>'
    return f'<w:p><w:pPr>{"".join(ppr)}</w:pPr><w:r><w:rPr>{"".join(rpr)}</w:rPr>{text_node}</w:r></w:p>'


def cover_table(coverage_metadata: dict) -> str:
    rows = (
        ("Agencia:", coverage_metadata.get("agency", "")),
        ("Cobertura:", coverage_metadata.get("coverage_name") or coverage_metadata.get("name", "")),
        ("Ciudad:", coverage_metadata.get("city", "")),
        ("Fotógrafo:", coverage_metadata.get("photographer", "")),
        ("Editor:", coverage_metadata.get("editor", "")),
        ("Fecha de cobertura:", coverage_metadata.get("event_date", coverage_metadata.get("submit_date", ""))),
    )
    row_xml = []
    for label, value in rows:
        row_xml.append(
            '<w:tr>'
            '<w:tc><w:tcPr><w:tcW w:w="2200" w:type="dxa"/></w:tcPr>'
            f'{paragraph(label, bold=True, size=22, spacing_after=0)}'
            '</w:tc>'
            '<w:tc><w:tcPr><w:tcW w:w="6600" w:type="dxa"/></w:tcPr>'
            f'{paragraph(str(value), size=22, spacing_after=0)}'
            '</w:tc>'
            '</w:tr>'
        )
    return (
        '<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/>'
        '<w:tblBorders><w:top w:val="nil"/><w:left w:val="nil"/><w:bottom w:val="nil"/><w:right w:val="nil"/><w:insideH w:val="nil"/><w:insideV w:val="nil"/></w:tblBorders>'
        '</w:tblPr>'
        f'{"".join(row_xml)}</w:tbl>'
    )


def image_drawing(image: EmbeddedImage, doc_pr_id: int) -> str:
    return f'''
<w:drawing>
  <wp:inline distT="0" distB="0" distL="0" distR="0" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">
    <wp:extent cx="{image.width_emu}" cy="{image.height_emu}"/>
    <wp:docPr id="{doc_pr_id}" name="{xml_text(image.alt_text)}"/>
    <a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
      <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
        <pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
          <pic:nvPicPr><pic:cNvPr id="0" name="{xml_text(image.alt_text)}"/><pic:cNvPicPr/></pic:nvPicPr>
          <pic:blipFill><a:blip r:embed="{image.relationship_id}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>
          <pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{image.width_emu}" cy="{image.height_emu}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>
        </pic:pic>
      </a:graphicData>
    </a:graphic>
  </wp:inline>
</w:drawing>'''


def image_paragraph(image: EmbeddedImage, doc_pr_id: int) -> str:
    return (
        '<w:p><w:pPr><w:jc w:val="left"/><w:keepNext/><w:keepLines/>'
        '<w:spacing w:after="0"/></w:pPr><w:r>'
        f'{image_drawing(image, doc_pr_id)}</w:r></w:p>'
    )


def empty_thumbnail_paragraph() -> str:
    return paragraph("Sin miniatura", size=18, color="606975", spacing_after=0)


def cell(content: str, width: int, *, shade: str | None = None) -> str:
    shading = f'<w:shd w:fill="{shade}"/>' if shade else ""
    return (
        '<w:tc><w:tcPr>'
        f'<w:tcW w:w="{width}" w:type="dxa"/>'
        '<w:tcMar><w:top w:w="120" w:type="dxa"/><w:left w:w="120" w:type="dxa"/>'
        '<w:bottom w:w="120" w:type="dxa"/><w:right w:w="120" w:type="dxa"/></w:tcMar>'
        f'{shading}</w:tcPr>{content}</w:tc>'
    )


def photo_block(index: int, photo: ExportPhoto, image: EmbeddedImage | None) -> str:
    thumbnail = image_paragraph(image, index) if image else empty_thumbnail_paragraph()
    photo_copy = "".join((
        paragraph(f"{index}. {photo.filename}", bold=True, size=22, spacing_after=70, keep_next=True),
        paragraph(photo.caption or "[Sin caption]", size=20, spacing_after=0),
    ))
    table = (
        '<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/>'
        '<w:tblBorders><w:top w:val="single" w:sz="4" w:space="0" w:color="D7DDE5"/>'
        '<w:left w:val="single" w:sz="4" w:space="0" w:color="D7DDE5"/>'
        '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="D7DDE5"/>'
        '<w:right w:val="single" w:sz="4" w:space="0" w:color="D7DDE5"/>'
        '<w:insideH w:val="nil"/><w:insideV w:val="nil"/></w:tblBorders>'
        '<w:tblCellMar><w:top w:w="80" w:type="dxa"/><w:left w:w="80" w:type="dxa"/>'
        '<w:bottom w:w="80" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tblCellMar>'
        '</w:tblPr><w:tr>'
        f'{cell(thumbnail, 2350, shade="F4F6F8")}'
        f'{cell(photo_copy, 7000)}'
        '</w:tr></w:tbl>'
    )
    return '<w:sdt><w:sdtContent>' + table + paragraph("", spacing_after=150) + '</w:sdtContent></w:sdt>'


def document_relationships(images: list[EmbeddedImage]) -> str:
    rels = []
    for image in images:
        rels.append(f'<Relationship Id="{image.relationship_id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/{image.filename}"/>')
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + "".join(rels) + '</Relationships>'


def content_types(images: list[EmbeddedImage]) -> str:
    defaults = {
        "rels": "application/vnd.openxmlformats-package.relationships+xml",
        "xml": "application/xml",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }
    default_xml = "".join(f'<Default Extension="{extension}" ContentType="{content_type}"/>' for extension, content_type in defaults.items())
    overrides = (
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    )
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">' + default_xml + overrides + '</Types>'


def package_relationships() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        '</Relationships>'
    )


def section_properties() -> str:
    return '''<w:sectPr>
  <w:pgSz w:w="12240" w:h="15840"/>
  <w:pgMar w:top="900" w:right="990" w:bottom="900" w:left="990" w:header="720" w:footer="720" w:gutter="0"/>
</w:sectPr>'''


def build_document_xml(photos: list[ExportPhoto], coverage_metadata: dict, images: list[EmbeddedImage]) -> str:
    title = build_report_title(coverage_metadata)
    images_by_photo = {image.alt_text: image for image in images}
    body = [
        paragraph(title, bold=True, size=34, align="left", spacing_after=160),
        cover_table(coverage_metadata),
        paragraph("", spacing_after=90),
    ]
    for index, photo in enumerate(photos, start=1):
        body.append(photo_block(index, photo, images_by_photo.get(photo.filename)))
    body.extend((
        paragraph("", spacing_after=320),
        paragraph("«········ FIN DEL ENVÍO ········»", bold=True, size=26, align="center", spacing_after=0),
        section_properties(),
    ))
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        f'<w:body>{"".join(body)}</w:body></w:document>'
    )


def build_docx(photos: list[ExportPhoto], coverage_metadata: dict) -> bytes:
    images = build_embedded_images(photos)
    buffer = io.BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as docx:
        docx.writestr("[Content_Types].xml", content_types(images))
        docx.writestr("_rels/.rels", package_relationships())
        docx.writestr("word/document.xml", build_document_xml(photos, coverage_metadata, images))
        docx.writestr("word/_rels/document.xml.rels", document_relationships(images))
        for image in images:
            docx.writestr(f"word/media/{image.filename}", image.data)
    return buffer.getvalue()
