from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Blueprint, abort, current_app, render_template, send_file

from app.dispatch.delivery_package import DeliveryPackageError


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


def public_files(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for item in manifest.get("files", []):
        if not isinstance(item, dict):
            continue
        items.append({
            "id": str(item.get("id", "")),
            "filename": str(item.get("filename", "")),
            "type": str(item.get("type", "")),
            "size": int(item.get("size") or 0),
        })
    return items


@downloads_bp.get("/d/<token>")
def landing(token: str) -> str:
    link = get_link_or_404(token)
    shipment = get_shipment_or_404(str(link.get("shipment_id", "")))
    try:
        manifest = get_services()["delivery_package_service"].load_manifest(str(shipment.get("id", "")))
    except DeliveryPackageError:
        abort(404)
    files = public_files(manifest)
    photo_count = sum(1 for item in files if item["type"] == "photo")
    docx_included = any(item["type"] == "document" for item in files)
    return render_template(
        "downloads/landing.html",
        token=token,
        link=link,
        shipment=shipment,
        files=files,
        photo_count=photo_count,
        docx_included=docx_included,
        expires_at_display=format_expiration(str(link.get("expires_at", ""))),
    )


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
