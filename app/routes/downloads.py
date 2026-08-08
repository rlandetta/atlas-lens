from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Blueprint, abort, current_app, render_template, send_file, url_for

from app.dispatch.delivery_package import DeliveryPackageError
from app.dispatch.delivery_previews import DeliveryPreviewError


downloads_bp = Blueprint("downloads", __name__)


def get_services() -> dict[str, Any]:
    return current_app.extensions["dispatch"]


def get_link_or_404(token: str) -> dict[str, Any]:
    link = get_services()["delivery_link_service"].get_by_token(token)
    if not link:
        abort(404)
    return link


def get_shipment_or_404(shipment_id: str) -> dict[str, Any]:
    shipment = get_services()["shipment_service"].get_shipment(shipment_id)
    if not shipment:
        abort(404)
    return shipment


def format_expiration(value: str) -> str:
    if not value:
        return "Sin expiración"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return parsed.astimezone(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")


def public_files(manifest: dict[str, Any], previews: list[dict[str, Any]] | None = None, token: str = "") -> list[dict[str, Any]]:
    preview_by_file = {
        str(preview.get("file_id", "")): preview
        for preview in previews or []
        if isinstance(preview, dict)
    }
    items = []
    for item in manifest.get("files", []):
        if not isinstance(item, dict):
            continue
        public_item = {
            "id": str(item.get("id", "")),
            "filename": str(item.get("filename", "")),
            "type": str(item.get("type", "")),
            "size": int(item.get("size") or 0),
            "preview_url": "",
        }
        preview = preview_by_file.get(public_item["id"])
        if token and preview:
            public_item["preview_url"] = url_for(
                "downloads.preview",
                token=token,
                preview_id=str(preview.get("id", "")),
            )
        items.append(public_item)
    return items


def public_backgrounds(previews: list[dict[str, Any]], token: str, *, limit: int = 4) -> list[dict[str, str]]:
    backgrounds = []
    for preview in previews[:limit]:
        preview_id = str(preview.get("id", "")).strip()
        if not preview_id:
            continue
        backgrounds.append({
            "id": preview_id,
            "url": url_for("downloads.preview", token=token, preview_id=preview_id),
        })
    return backgrounds


@downloads_bp.get("/d/<token>")
def landing(token: str) -> str:
    link = get_link_or_404(token)
    shipment = get_shipment_or_404(str(link.get("shipment_id", "")))
    try:
        manifest = get_services()["delivery_package_service"].load_manifest(str(shipment.get("id", "")))
    except DeliveryPackageError:
        abort(404)
    preview_service = get_services().get("delivery_preview_service")
    previews = preview_service.ensure_previews(str(shipment.get("id", "")), manifest, limit=4) if preview_service else []
    files = public_files(manifest, previews, token=token)
    photo_count = sum(1 for item in files if item["type"] == "photo")
    docx_included = any(item["type"] == "document" for item in files)
    return render_template(
        "downloads/landing.html",
        token=token,
        link=link,
        shipment=shipment,
        files=files,
        backgrounds=public_backgrounds(previews, token, limit=4),
        photo_count=photo_count,
        docx_included=docx_included,
        expires_at_display=format_expiration(str(link.get("expires_at", ""))),
    )


@downloads_bp.get("/d/<token>/preview/<preview_id>")
def preview(token: str, preview_id: str):
    link = get_link_or_404(token)
    shipment = get_shipment_or_404(str(link.get("shipment_id", "")))
    preview_service = get_services().get("delivery_preview_service")
    if preview_service is None:
        abort(404)
    try:
        path, _ = preview_service.preview_path(str(shipment.get("id", "")), preview_id)
    except DeliveryPreviewError:
        abort(404)
    response = send_file(path, mimetype="image/jpeg", conditional=True, max_age=86400)
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response


@downloads_bp.get("/d/<token>/download")
def download_zip(token: str):
    link = get_link_or_404(token)
    shipment = get_shipment_or_404(str(link.get("shipment_id", "")))
    try:
        path = get_services()["delivery_package_service"].package_zip_path(str(shipment.get("id", "")))
    except DeliveryPackageError:
        abort(404)
    get_services()["delivery_link_service"].record_download(str(link.get("id", "")))
    return send_file(path, as_attachment=True, download_name=f"{Path(str(shipment.get('name', 'dispatch'))).stem or 'dispatch'}.zip")


@downloads_bp.get("/d/<token>/file/<file_id>")
def download_file(token: str, file_id: str):
    link = get_link_or_404(token)
    shipment = get_shipment_or_404(str(link.get("shipment_id", "")))
    try:
        path, item = get_services()["delivery_package_service"].package_file_path(str(shipment.get("id", "")), file_id)
    except DeliveryPackageError:
        abort(404)
    get_services()["delivery_link_service"].record_download(str(link.get("id", "")))
    return send_file(path, as_attachment=True, download_name=str(item.get("filename") or path.name))
