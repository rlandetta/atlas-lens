from __future__ import annotations

import hashlib
import ipaddress
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Blueprint, abort, current_app, make_response, render_template, request, send_file, url_for

from app.config import DISPATCH_TRUSTED_PROXY_CIDRS
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


def get_public_link_state(token: str) -> tuple[dict[str, Any] | None, str]:
    store = get_services()["delivery_link_store"]
    raw_link = store.get_by_token(token)
    if raw_link is None:
        return None, "invalid"
    if not store.is_usable(raw_link):
        return None, "expired"
    return get_services()["delivery_link_service"].with_url(raw_link), "ok"


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


def format_bytes(value: int) -> str:
    size = float(value or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{int(value)} B"


def format_public_date(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "-"
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return raw
    return parsed.astimezone(timezone.utc).strftime("%d %b %Y")


def sanitize_profile_key(value: str) -> str:
    raw = str(value or "").strip().lower()
    safe = "".join(character if character.isalnum() or character in {"-", "_"} else "-" for character in raw)
    return safe.strip("-_") or "default"


def coverage_location(snapshot: dict[str, Any]) -> str:
    city = str(snapshot.get("city", "")).strip()
    country = str(snapshot.get("country", "")).strip()
    if city and country:
        return f"{city}, {country}"
    return city or country


def build_delivery_public_id(token: str) -> str:
    digest = hashlib.sha256(str(token or "").encode("utf-8")).hexdigest().upper()
    return f"AYAMPI-{digest[:8]}"


def is_trusted_proxy(remote_addr: str) -> bool:
    try:
        remote_ip = ipaddress.ip_address(str(remote_addr or "").strip())
    except ValueError:
        return False
    for raw_network in DISPATCH_TRUSTED_PROXY_CIDRS:
        try:
            if remote_ip in ipaddress.ip_network(str(raw_network), strict=False):
                return True
        except ValueError:
            continue
    return False


def first_valid_forwarded_ip(value: str) -> str:
    for candidate in str(value or "").split(","):
        candidate = candidate.strip()
        try:
            ipaddress.ip_address(candidate)
        except ValueError:
            continue
        return candidate
    return ""


def resolve_client_ip() -> str:
    remote_addr = str(request.remote_addr or "").strip()
    if not is_trusted_proxy(remote_addr):
        return remote_addr
    forwarded_for = first_valid_forwarded_ip(request.headers.get("X-Forwarded-For", ""))
    if forwarded_for:
        return forwarded_for
    real_ip = first_valid_forwarded_ip(request.headers.get("X-Real-IP", ""))
    return real_ip or remote_addr


def classify_user_agent(user_agent: str) -> dict[str, str]:
    value = str(user_agent or "")
    lower = value.lower()
    if "edg/" in lower:
        browser = "Edge"
    elif "chrome/" in lower and "chromium" not in lower:
        browser = "Chrome"
    elif "safari/" in lower and "chrome/" not in lower:
        browser = "Safari"
    elif "firefox/" in lower:
        browser = "Firefox"
    else:
        browser = ""

    if "windows" in lower:
        os_name = "Windows"
    elif "mac os x" in lower or "macintosh" in lower:
        os_name = "macOS"
    elif "android" in lower:
        os_name = "Android"
    elif "iphone" in lower or "ipad" in lower:
        os_name = "iOS"
    elif "linux" in lower:
        os_name = "Linux"
    else:
        os_name = ""

    if "ipad" in lower or "tablet" in lower:
        device_category = "Tablet"
    elif "mobile" in lower or "iphone" in lower or "android" in lower:
        device_category = "Mobile"
    elif value:
        device_category = "Desktop"
    else:
        device_category = ""

    return {"browser": browser, "os_name": os_name, "device_category": device_category}


def infer_document_label(filename: str) -> tuple[str, str]:
    extension = Path(str(filename or "")).suffix.lower().lstrip(".")
    if extension == "pdf":
        return "PDF", "Documento PDF"
    if extension == "docx":
        return "DOCX", "Documento Word"
    if extension == "txt":
        return "TXT", "Texto"
    if extension == "zip":
        return "ZIP", "Archivo comprimido"
    return (extension.upper() if extension else "DOC"), "Documento"


def choose_hero_image(
    photo_files: list[dict[str, Any]],
    backgrounds: list[dict[str, Any]],
) -> tuple[str, str]:
    if not photo_files:
        return "", ""
    if len(photo_files) == 1:
        selected = photo_files[0]
    else:
        selected = random.choice(photo_files)
    selected_id = str(selected.get("id", ""))
    background_by_file = {
        str(item.get("file_id", "")): str(item.get("url", ""))
        for item in backgrounds
        if isinstance(item, dict)
    }
    hero_url = background_by_file.get(selected_id) or str(selected.get("thumbnail_url", ""))
    return hero_url, str(selected.get("filename", ""))


def resolve_public_profile(shipment: dict[str, Any]) -> dict[str, Any]:
    settings_service = current_app.extensions["settings"]["settings_service"]
    snapshot = shipment.get("coverage_snapshot", {}) if isinstance(shipment.get("coverage_snapshot", {}), dict) else {}
    profile_key = sanitize_profile_key(str(snapshot.get("editor", "") or snapshot.get("photographer", "") or "default"))
    profile = settings_service.get_public_profile(profile_key)
    default_profile = settings_service.get_public_profile("default")

    display_name = str(profile.get("display_name", "")).strip() or str(default_profile.get("display_name", "")).strip() or str(snapshot.get("photographer", "")).strip()
    role = str(profile.get("role", "")).strip() or str(default_profile.get("role", "")).strip()
    organization = str(profile.get("organization", "")).strip() or str(default_profile.get("organization", "")).strip() or str(snapshot.get("agency", "")).strip()
    location = str(profile.get("location", "")).strip() or str(default_profile.get("location", "")).strip() or coverage_location(snapshot)
    profile_public_email = str(profile.get("public_email", "")).strip()
    default_public_email = str(default_profile.get("public_email", "")).strip()
    if profile_public_email:
        public_email = profile_public_email
        show_public_email = bool(profile.get("show_public_email", False))
    else:
        public_email = default_public_email
        show_public_email = bool(default_profile.get("show_public_email", False))
    show_public_profile = bool(profile.get("show_public_profile", default_profile.get("show_public_profile", True)))

    avatar_filename = str(profile.get("avatar_filename", "")).strip() or str(default_profile.get("avatar_filename", "")).strip()
    return {
        "profile_key": profile_key,
        "show_public_profile": show_public_profile,
        "display_name": display_name,
        "role": role,
        "organization": organization,
        "location": location,
        "public_email": public_email if show_public_email else "",
        "avatar_filename": avatar_filename,
    }


def public_files(manifest: dict[str, Any], thumbnails: list[dict[str, Any]] | None = None, token: str = "") -> list[dict[str, Any]]:
    thumbnail_by_file = {
        str(preview.get("file_id", "")): preview
        for preview in thumbnails or []
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
            "size_label": format_bytes(int(item.get("size") or 0)),
            "thumbnail_url": "",
            "extension": Path(str(item.get("filename", ""))).suffix.lower().lstrip("."),
        }
        thumbnail = thumbnail_by_file.get(public_item["id"])
        if token and thumbnail:
            public_item["thumbnail_url"] = url_for(
                "downloads.preview",
                token=token,
                preview_id=str(thumbnail.get("id", "")),
            )
        items.append(public_item)
    return items


def public_backgrounds(backgrounds: list[dict[str, Any]], token: str, *, limit: int = 4) -> list[dict[str, str]]:
    public_items = []
    for preview in backgrounds[:limit]:
        preview_id = str(preview.get("id", "")).strip()
        if not preview_id:
            continue
        file_id = str(preview.get("file_id", "")).strip()
        public_items.append({
            "id": preview_id,
            "file_id": file_id,
            "url": url_for("downloads.preview", token=token, preview_id=preview_id),
        })
    return public_items


def resolve_avatar_path(filename: str) -> Path | None:
    safe_name = "".join(character if character.isalnum() or character in {"-", "_", "."} else "-" for character in str(filename or "").strip())
    safe_name = safe_name.strip("-_.")
    if not safe_name:
        return None
    root = current_app.extensions["settings"]["profile_avatar_root"].resolve()
    candidate = (root / safe_name).resolve()
    if not candidate.is_relative_to(root) or not candidate.is_file():
        return None
    return candidate


@downloads_bp.get("/d/<token>")
def landing(token: str) -> str:
    link, status = get_public_link_state(token)
    if status != "ok" or link is None:
        response = make_response(render_template("downloads/link_unavailable.html", reason=status), 404)
        response.headers["Cache-Control"] = "no-store"
        return response
    shipment = get_shipment_or_404(str(link.get("shipment_id", "")))
    try:
        manifest = get_services()["delivery_package_service"].load_manifest(str(shipment.get("id", "")))
    except DeliveryPackageError:
        response = make_response(render_template("downloads/link_unavailable.html", reason="invalid"), 404)
        response.headers["Cache-Control"] = "no-store"
        return response
    preview_service = get_services().get("delivery_preview_service")
    photo_count_for_previews = len([item for item in manifest.get("files", []) if isinstance(item, dict) and str(item.get("type", "")) == "photo"])
    preview_payload = preview_service.ensure_previews(
        str(shipment.get("id", "")),
        manifest,
        background_limit=max(4, photo_count_for_previews),
    ) if preview_service else {"thumbnails": [], "backgrounds": []}
    files = public_files(manifest, preview_payload.get("thumbnails", []), token=token)
    photo_files = [item for item in files if item["type"] == "photo"]
    document_files = [item for item in files if item["type"] == "document"]
    photo_count = len(photo_files)
    docx_included = bool(document_files)
    all_backgrounds = public_backgrounds(preview_payload.get("backgrounds", []), token, limit=max(4, photo_count or 4))
    hero_image_url, hero_image_name = choose_hero_image(photo_files, all_backgrounds)
    decorative_backgrounds = [
        background
        for background in all_backgrounds[:4]
        if str(background.get("url", "")) != hero_image_url
    ]
    if "/preview/background:photo-" in hero_image_url:
        decorative_backgrounds = decorative_backgrounds[:3]
    profile = resolve_public_profile(shipment)
    branding = current_app.extensions["settings"]["settings_service"].get_dispatch_branding()
    profile_avatar_url = ""
    if profile.get("avatar_filename"):
        profile_avatar_url = url_for("downloads.profile_avatar", token=token, avatar_name=profile["avatar_filename"])
    location_label = coverage_location(shipment.get("coverage_snapshot", {}))
    if not location_label:
        location_label = "Ubicacion no especificada"

    prepared_documents = []
    for item in document_files:
        badge, kind = infer_document_label(str(item.get("filename", "")))
        prepared_documents.append({**item, "doc_badge": badge, "doc_kind": kind})

    response = make_response(render_template(
        "downloads/landing.html",
        token=token,
        link=link,
        shipment=shipment,
        files=files,
        photo_files=photo_files,
        document_files=prepared_documents,
        backgrounds=decorative_backgrounds,
        photo_count=photo_count,
        document_count=len(document_files),
        docx_included=docx_included,
        total_bytes_label=format_bytes(int(manifest.get("total_bytes") or 0)),
        expires_at_display=format_expiration(str(link.get("expires_at", ""))),
        created_at_display=format_public_date(str(shipment.get("created_at", ""))),
        expires_at_short=format_public_date(str(link.get("expires_at", ""))),
        location_label=location_label,
        hero_image_url=hero_image_url,
        hero_image_name=hero_image_name,
        profile=profile,
        profile_avatar_url=profile_avatar_url,
        public_delivery_id=build_delivery_public_id(token),
        branding=branding,
    ))
    response.headers["Cache-Control"] = "no-store"
    return response


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


@downloads_bp.get("/d/<token>/avatar/<avatar_name>")
def profile_avatar(token: str, avatar_name: str):
    _link = get_link_or_404(token)
    path = resolve_avatar_path(avatar_name)
    if path is None:
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
    get_services()["delivery_link_service"].record_download(
        str(link.get("id", "")),
        download_type="PACKAGE",
        ip=resolve_client_ip(),
        user_agent=str(request.user_agent),
        **classify_user_agent(str(request.user_agent)),
    )
    return send_file(path, as_attachment=True, download_name=f"{Path(str(shipment.get('name', 'dispatch'))).stem or 'dispatch'}.zip")


@downloads_bp.get("/d/<token>/file/<file_id>")
def download_file(token: str, file_id: str):
    link = get_link_or_404(token)
    shipment = get_shipment_or_404(str(link.get("shipment_id", "")))
    try:
        path, item = get_services()["delivery_package_service"].package_file_path(str(shipment.get("id", "")), file_id)
    except DeliveryPackageError:
        abort(404)
    download_type = "DOCUMENT" if str(item.get("type", "")) == "document" else "PHOTO"
    get_services()["delivery_link_service"].record_download(
        str(link.get("id", "")),
        download_type=download_type,
        filename=str(item.get("filename") or path.name),
        ip=resolve_client_ip(),
        user_agent=str(request.user_agent),
        **classify_user_agent(str(request.user_agent)),
    )
    return send_file(path, as_attachment=True, download_name=str(item.get("filename") or path.name))
