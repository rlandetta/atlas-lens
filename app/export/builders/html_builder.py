from __future__ import annotations

import base64
from html import escape

from app.export.builders.image_sources import load_preview_image_source
from app.export.models import ExportPhoto

TEXT_COLOR = "#333333"


def coverage_name(coverage_metadata: dict) -> str:
    return str(coverage_metadata.get("coverage_name") or coverage_metadata.get("name") or "Reporte editorial")


def build_report_title(coverage_metadata: dict) -> str:
    title = coverage_name(coverage_metadata).upper()
    country = str(coverage_metadata.get("country", "")).upper()
    return f"{title} · {country}".strip(" ·")


def embedded_preview(photo: ExportPhoto) -> str:
    preview = load_preview_image_source(photo)
    if preview is None:
        return '<div class="photo-placeholder">Sin miniatura</div>'
    encoded = base64.b64encode(preview.data).decode("ascii")
    return (
        f'<img src="data:{escape(preview.content_type, quote=True)};base64,{encoded}" '
        f'width="{preview.width}" height="{preview.height}" '
        f'alt="{escape(photo.filename, quote=True)}">'
    )


def build_html(photos: list[ExportPhoto], coverage_metadata: dict) -> bytes:
    title = coverage_name(coverage_metadata)
    photo_blocks = "\n".join(
        """
        <article class="photo-card">
            <div class="photo-media">
                {image}
            </div>
            <div class="photo-copy">
                <p class="filename">{index}. {filename}</p>
                <p class="caption">{caption}</p>
            </div>
        </article>
        """.format(
            image=embedded_preview(photo),
            index=index,
            filename=escape(photo.filename),
            caption=escape(photo.caption or "[Sin caption]"),
        )
        for index, photo in enumerate(photos, start=1)
    )
    html = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
	<style>
	:root {{
	    --page-bg: #0f1720;
	    --card-bg: #17222e;
	    --card-bg-soft: #1b2733;
	    --text: #f4f4f4;
	    --muted: #aeb9c6;
	    --line: #2b3a48;
	    --accent: #6fb7b8;
	    --shadow: 0 18px 42px rgba(0, 0, 0, 0.28);
	    --radius: 16px;
	}}
	* {{ box-sizing: border-box; }}
	img {{ max-width: 100%; }}
	html {{ background: var(--page-bg); }}
	body {{
	    margin: 0;
    font-family: Arial, Helvetica, sans-serif;
    color: var(--text);
    background: var(--page-bg);
    line-height: 1.42;
}}
.report-page {{
    width: min(1120px, calc(100% - 32px));
    margin: 0 auto;
    padding: 32px 0 44px;
}}
.report-header {{
    text-align: left;
    background: linear-gradient(180deg, var(--card-bg-soft), var(--card-bg));
    border: 1px solid var(--line);
    border-radius: var(--radius);
    box-shadow: var(--shadow);
    padding: 22px 26px;
    margin-bottom: 24px;
}}
.report-header h1 {{
    margin: 0 0 12px;
    color: var(--text);
    font-size: 1.72rem;
    line-height: 1.08;
    letter-spacing: 0;
}}
.report-meta {{
    display: grid;
    grid-template-columns: max-content minmax(0, 1fr);
    gap: 5px 18px;
    margin: 0;
    color: var(--text);
}}
.report-meta dt {{
    font-weight: 700;
    color: var(--muted);
}}
.report-meta dd {{
    margin: 0;
    color: var(--text);
    overflow-wrap: anywhere;
}}
.photo-list {{ display: grid; gap: 18px; }}
.photo-card {{
    display: grid;
    grid-template-columns: minmax(190px, 30%) minmax(0, 1fr);
    gap: 22px;
    align-items: stretch;
    background: var(--card-bg);
    border: 1px solid var(--line);
    border-radius: var(--radius);
    box-shadow: var(--shadow);
    padding: 18px;
    overflow: hidden;
}}
.photo-card {{ break-inside: avoid; }}
.photo-media {{
    display: flex;
    align-items: center;
    justify-content: center;
    justify-self: stretch;
    width: 100%;
    min-height: 170px;
    border-radius: 12px;
    background: #111b25;
    border: 1px solid rgba(174, 185, 198, 0.14);
    overflow: hidden;
}}
.photo-media img {{
    display: block;
    max-width: 100%;
    width: auto;
    height: auto;
    max-height: 190px;
    object-fit: contain;
    border-radius: 8px;
}}
.photo-placeholder {{
    width: 100%;
    min-height: 150px;
    border-radius: 8px;
    border: 1px dashed var(--line);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--muted);
    background: #111b25;
}}
.photo-copy {{ min-width: 0; align-self: center; }}
.filename {{
    margin: 0 0 10px;
    color: var(--text);
    font-weight: 700;
    font-size: 0.98rem;
    line-height: 1.32;
    overflow-wrap: anywhere;
}}
.caption {{
    margin: 0;
    color: var(--text);
    font-size: 0.96rem;
    line-height: 1.48;
    overflow-wrap: anywhere;
}}
.end-marker {{
    margin: 34px 0 0;
    text-align: center;
    color: var(--muted);
    font-weight: 700;
    font-size: 1.02rem;
}}
@media (max-width: 640px) {{
    .report-page {{ width: min(100% - 20px, 1120px); padding: 18px 0 28px; }}
    .report-header {{ padding: 20px; margin-bottom: 18px; }}
    .photo-list {{ gap: 16px; }}
    .photo-card {{ grid-template-columns: 1fr; gap: 16px; padding: 18px; }}
    .photo-media {{ min-height: 140px; }}
    .photo-media img {{ max-height: none; }}
}}
</style>
</head>
<body>
<main class="report-page">
<header class="report-header">
<h1>{escape(build_report_title(coverage_metadata))}</h1>
<dl class="report-meta">
<dt>Agencia</dt><dd>{escape(str(coverage_metadata.get('agency', '')))}</dd>
<dt>Cobertura</dt><dd>{escape(str(coverage_metadata.get('coverage_name') or coverage_metadata.get('name') or ''))}</dd>
<dt>Ciudad</dt><dd>{escape(str(coverage_metadata.get('city', '')))}</dd>
<dt>Fotógrafo</dt><dd>{escape(str(coverage_metadata.get('photographer', '')))}</dd>
<dt>Editor</dt><dd>{escape(str(coverage_metadata.get('editor', '')))}</dd>
<dt>Fecha cobertura</dt><dd>{escape(str(coverage_metadata.get('event_date') or coverage_metadata.get('submit_date') or ''))}</dd>
</dl>
</header>
<section class="photo-list">
{photo_blocks}
</section>
<p class="end-marker">«········ FIN DEL ENVÍO ········»</p>
</main>
</body>
</html>
"""
    return html.encode("utf-8")
