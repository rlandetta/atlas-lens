from __future__ import annotations


ATLAS_NAVIGATION = (
    {
        "label": "Dashboard",
        "endpoint": None,
        "blueprint": "dashboard",
        "enabled": False,
    },
    {
        "label": "LENS",
        "endpoint": "web.home",
        "blueprint": "web",
        "enabled": True,
    },
    {
        "label": "DISPATCH",
        "endpoint": "dispatch.index",
        "blueprint": "dispatch",
        "enabled": True,
    },
)


def create_app():
    from flask import Flask

    from app.config import DISPATCH_STORE_PATH
    from app.dispatch import DispatchShipmentStore, ShipmentService
    from app.lens_read_service import LensReadService
    from app.routes.dispatch import dispatch_bp
    from app.routes.dispatch import WebCoverageProvider
    from app.routes.web import web_bp

    app = Flask(__name__)
    lens_reader = LensReadService(WebCoverageProvider())
    dispatch_store = DispatchShipmentStore(DISPATCH_STORE_PATH)
    app.extensions["dispatch"] = {
        "store": dispatch_store,
        "lens_reader": lens_reader,
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
    return app
