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


def create_app():
    from flask import Flask

    from app.config import (
        DELIVERY_LINKS_STORE_PATH,
        DELIVERY_ROOT,
        DISPATCH_STORE_PATH,
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
    app.config["LENS_MAX_PHOTO_BYTES"] = LENS_MAX_PHOTO_BYTES
    ingest_store = IngestStore(INGEST_STORE_PATH)
    ingest_service = IngestService(ingest_store, session_timeout_minutes=INGEST_SESSION_TIMEOUT_MINUTES)
    lens_coverage_store = LensCoverageStore(LENS_COVERAGE_STORE_PATH, LENS_MEDIA_ROOT)
    thumbnail_service = ThumbnailService(THUMBNAIL_ROOT)
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
    return app
