from __future__ import annotations

from html import escape

from app.export.models import ExportPhoto

TEXT_COLOR = "#333333"


def coverage_name(coverage_metadata: dict) -> str:
    return str(coverage_metadata.get("coverage_name") or coverage_metadata.get("name") or "Reporte editorial")


def build_html(photos: list[ExportPhoto], coverage_metadata: dict) -> bytes:
    title = coverage_name(coverage_metadata)
    photo_blocks = "\n".join(
        """
        <article class="photo-card">
            <div class="photo-media">
                {image}
            </div>
            <div class="photo-copy">
                <p class="filename">{filename}</p>
                <p class="caption">{caption}</p>
            </div>
        </article>
        """.format(
            image=(
                f'<img src="{escape(photo.data_url, quote=True)}" alt="{escape(photo.filename, quote=True)}">'
                if photo.data_url else '<div class="photo-placeholder">Sin miniatura</div>'
            ),
            filename=escape(photo.filename),
            caption=escape(photo.caption or "[Sin caption]"),
        )
        for photo in photos
    )
    html = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>
:root {{
    --page-bg: #f3f4f6;
    --card-bg: #ffffff;
    --text: {TEXT_COLOR};
    --muted: #606975;
    --line: #d9dee5;
    --shadow: 0 14px 34px rgba(25, 31, 40, 0.08);
    --radius: 18px;
}}
* {{ box-sizing: border-box; }}
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
    background: var(--card-bg);
    border: 1px solid rgba(217, 222, 229, 0.9);
    border-radius: var(--radius);
    box-shadow: var(--shadow);
    padding: 24px 28px;
    margin-bottom: 28px;
}}
.report-header h1 {{
    margin: 0 0 14px;
    color: var(--text);
    font-size: clamp(1.55rem, 2.4vw, 2.1rem);
    line-height: 1.08;
    letter-spacing: 0.01em;
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
    color: var(--text);
}}
.report-meta dd {{
    margin: 0;
    color: var(--muted);
}}
.photo-list {{ display: grid; gap: 22px; }}
.photo-card {{
    display: grid;
    grid-template-columns: minmax(180px, 285px) minmax(0, 1fr);
    gap: 24px;
    align-items: start;
    background: var(--card-bg);
    border: 1px solid rgba(217, 222, 229, 0.9);
    border-radius: var(--radius);
    box-shadow: var(--shadow);
    padding: 22px;
}}
.photo-media {{ justify-self: start; width: 100%; }}
.photo-media img {{
    display: block;
    max-width: 100%;
    width: auto;
    height: auto;
    max-height: 190px;
    object-fit: contain;
    border-radius: 10px;
}}
.photo-placeholder {{
    min-height: 150px;
    border-radius: 10px;
    border: 1px dashed var(--line);
    display: grid;
    place-items: center;
    color: var(--muted);
    background: #f8fafc;
}}
.filename {{
    margin: 0 0 12px;
    color: var(--text);
    font-weight: 700;
    font-size: 1rem;
}}
.caption {{
    margin: 0;
    color: var(--text);
    font-size: 1rem;
    line-height: 1.5;
}}
.end-marker {{
    margin: 34px 0 0;
    text-align: center;
    color: var(--text);
    font-weight: 700;
    font-size: 1.15rem;
}}
@media (max-width: 640px) {{
    .report-page {{ width: min(100% - 20px, 1120px); padding: 18px 0 28px; }}
    .report-header {{ padding: 20px; margin-bottom: 18px; }}
    .photo-list {{ gap: 16px; }}
    .photo-card {{ grid-template-columns: 1fr; gap: 16px; padding: 18px; }}
    .photo-media img {{ max-height: none; }}
}}
</style>
</head>
<body>
<main class="report-page">
<header class="report-header">
<h1>{escape(title)}</h1>
<dl class="report-meta">
<dt>Agencia</dt><dd>{escape(str(coverage_metadata.get('agency', '')))}</dd>
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
