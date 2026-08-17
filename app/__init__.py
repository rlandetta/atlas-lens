from __future__ import annotations


ATLAS_NAVIGATION = (
    {
        "label": "DASHBOARD",
        "endpoint": "web.home",
        "blueprint": "dashboard",
        "enabled": True,
    },
    {
        "label": "FLOW",
        "endpoint": "web.flow_home",
        "blueprint": "web",
        "enabled": True,
    },
    {
        "label": "LENS",
        "endpoint": "web.lens_home",
        "blueprint": "web",
        "enabled": True,
    },
    {
        "label": "DISPATCH",
        "endpoint": "dispatch.index",
        "blueprint": "dispatch",
        "enabled": True,
    },
    {
        "label": "SETTINGS",
        "endpoint": "settings.index",
        "blueprint": "settings",
        "enabled": True,
    },
)


CANONICAL_ROUTE_ALIASES = (
    ("/flow/", "web.flow_home", ("GET",)),
    ("/lens/", "web.lens_home", ("GET",)),
    ("/lens/coverages/new", "web.new_coverage", ("GET", "POST")),
    ("/lens/coverages/<coverage_id>", "web.coverage_detail", ("GET",)),
    ("/lens/coverages/<coverage_id>/edit", "web.edit_coverage", ("POST",)),
    ("/lens/coverages/<coverage_id>/ai-context", "web.save_coverage_ai_context", ("POST",)),
    ("/lens/coverages/<coverage_id>/delete", "web.delete_coverage", ("POST",)),
    ("/lens/coverages/<coverage_id>/exports", "web.create_coverage_export", ("POST",)),
    ("/lens/coverages/<coverage_id>/photos", "web.add_coverage_photo", ("POST",)),
    (
        "/lens/coverages/<coverage_id>/photos/<photo_id>/thumbnail",
        "web.coverage_photo_thumbnail",
        ("GET",),
    ),
    (
        "/lens/coverages/<coverage_id>/photos/<photo_id>/media",
        "web.coverage_photo_media",
        ("GET",),
    ),
    (
        "/lens/coverages/<coverage_id>/photos/<photo_id>/caption",
        "web.save_coverage_photo_caption",
        ("POST",),
    ),
    (
        "/lens/coverages/<coverage_id>/captions/copy-caption-empty",
        "web.copy_caption_to_empty_photos",
        ("POST",),
    ),
    (
        "/lens/coverages/<coverage_id>/photos/<photo_id>/generate-narration",
        "web.generate_photo_narration",
        ("POST",),
    ),
    (
        "/lens/coverages/<coverage_id>/photos/<photo_id>/ai-context",
        "web.get_photo_ai_context",
        ("GET",),
    ),
    (
        "/lens/coverages/<coverage_id>/photos/<photo_id>/delete",
        "web.delete_coverage_photo",
        ("POST",),
    ),
)


class UrlPrefixMiddleware:
    def __init__(self, app, prefix: str):
        self.app = app
        self.prefix = prefix.rstrip("/")

    def __call__(self, environ, start_response):
        path_info = environ.get("PATH_INFO", "")
        if path_info == self.prefix:
            environ["SCRIPT_NAME"] = self.prefix
            environ["PATH_INFO"] = "/"
        elif path_info.startswith(f"{self.prefix}/"):
            environ["SCRIPT_NAME"] = self.prefix
            environ["PATH_INFO"] = path_info[len(self.prefix):] or "/"
        else:
            script_name = environ.get("SCRIPT_NAME", "").rstrip("/")
            if script_name == self.prefix:
                environ["SCRIPT_NAME"] = self.prefix
        return self.app(environ, start_response)


def register_canonical_route_aliases(app) -> None:
    for rule, endpoint, methods in CANONICAL_ROUTE_ALIASES:
        app.add_url_rule(
            rule,
            endpoint=endpoint,
            view_func=app.view_functions[endpoint],
            methods=list(methods),
        )


def create_app():
    from pathlib import Path

    from flask import Flask

    from app.config import (
        ATLAS_URL_PREFIX,
        DELIVERY_LINKS_STORE_PATH,
        DELIVERY_ROOT,
        DISPATCH_STORE_PATH,
        FLOW_EVENTS_ROOT,
        INGEST_SESSION_TIMEOUT_MINUTES,
        INGEST_STORE_PATH,
        LENS_COVERAGE_STORE_PATH,
        PUBLIC_BASE_URL,
        SETTINGS_STORE_PATH,
        LENS_MAX_PHOTO_BYTES,
        LENS_MEDIA_ROOT,
        THUMBNAIL_ROOT,
    )
    from app.dispatch import DeliveryLinkService, DeliveryLinkStore, DeliveryPackageService, DeliveryPreviewService, DispatchShipmentStore, ShipmentService, SMTPLinkTransport
    from app.ingest import IngestService, IngestStore
    from app.lens import LensCoverageStore
    from app.media import ThumbnailService
    from app.settings import SettingsService, SettingsStore
    from app.lens_read_service import LensReadService
    from app.routes.dispatch import dispatch_bp
    from app.routes.dispatch import WebCoverageProvider
    from app.routes.downloads import downloads_bp
    from app.routes.settings import settings_bp
    from app.routes.web import configure_coverage_store, web_bp

    app = Flask(__name__)
    if ATLAS_URL_PREFIX:
        app.config["APPLICATION_ROOT"] = ATLAS_URL_PREFIX
        app.wsgi_app = UrlPrefixMiddleware(app.wsgi_app, ATLAS_URL_PREFIX)
    app.config["LENS_MAX_PHOTO_BYTES"] = LENS_MAX_PHOTO_BYTES
    app.config["FLOW_EVENTS_ROOT"] = FLOW_EVENTS_ROOT
    ingest_store = IngestStore(INGEST_STORE_PATH)
    ingest_service = IngestService(ingest_store, session_timeout_minutes=INGEST_SESSION_TIMEOUT_MINUTES)
    lens_coverage_store = LensCoverageStore(LENS_COVERAGE_STORE_PATH, LENS_MEDIA_ROOT)
    thumbnail_root = Path(THUMBNAIL_ROOT)
    if not thumbnail_root.is_absolute() and thumbnail_root.parts[:1] == ("instance",):
        thumbnail_root = Path(app.instance_path, *thumbnail_root.parts[1:])
    thumbnail_service = ThumbnailService(thumbnail_root, base_path=Path(app.root_path).parent)
    configure_coverage_store(lens_coverage_store)
    coverage_provider = WebCoverageProvider()
    lens_reader = LensReadService(coverage_provider)
    dispatch_store = DispatchShipmentStore(DISPATCH_STORE_PATH)
    delivery_link_store = DeliveryLinkStore(DELIVERY_LINKS_STORE_PATH)
    delivery_link_service = DeliveryLinkService(delivery_link_store, PUBLIC_BASE_URL)
    delivery_package_service = DeliveryPackageService(delivery_root=DELIVERY_ROOT, media_root=LENS_MEDIA_ROOT)
    delivery_preview_service = DeliveryPreviewService(delivery_root=DELIVERY_ROOT)
    settings_store = SettingsStore(SETTINGS_STORE_PATH)
    settings_service = SettingsService(settings_store)
    smtp_transport = SMTPLinkTransport(settings_service=settings_service)
    app.extensions["ingest"] = {
        "store": ingest_store,
        "ingest_service": ingest_service,
    }
    app.extensions["lens"] = {
        "coverage_store": lens_coverage_store,
    }
    app.extensions["media"] = {
        "thumbnail_service": thumbnail_service,
    }
    app.extensions["settings"] = {
        "store": settings_store,
        "settings_service": settings_service,
    }
    app.extensions["dispatch"] = {
        "coverage_provider": coverage_provider,
        "store": dispatch_store,
        "lens_reader": lens_reader,
        "settings_service": settings_service,
        "delivery_link_store": delivery_link_store,
        "delivery_link_service": delivery_link_service,
        "delivery_package_service": delivery_package_service,
        "delivery_preview_service": delivery_preview_service,
        "smtp_transport": smtp_transport,
        "shipment_service": ShipmentService(
            store=dispatch_store,
            lens_reader=lens_reader,
        ),
    }

    @app.context_processor
    def inject_atlas_shell():
        return {"atlas_navigation": ATLAS_NAVIGATION}

    app.register_blueprint(web_bp)
    app.register_blueprint(dispatch_bp)
    app.register_blueprint(downloads_bp)
    app.register_blueprint(settings_bp)
    if not ATLAS_URL_PREFIX:
        register_canonical_route_aliases(app)
    return app
