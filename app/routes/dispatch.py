from __future__ import annotations

from typing import Mapping, Any

from flask import Blueprint, abort, current_app, render_template

dispatch_bp = Blueprint("dispatch", __name__, url_prefix="/dispatch")


class WebCoverageProvider:
    def __call__(self) -> Mapping[str, dict[str, Any]]:
        from app.routes.web import coverages

        return coverages


def get_dispatch_services() -> dict[str, Any]:
    return current_app.extensions["dispatch"]


@dispatch_bp.get("/")
def index() -> str:
    shipment_service = get_dispatch_services()["shipment_service"]
    return render_template(
        "dispatch/index.html",
        shipments=shipment_service.list_shipments(),
    )


@dispatch_bp.get("/<shipment_id>")
def detail(shipment_id: str) -> str:
    shipment_service = get_dispatch_services()["shipment_service"]
    shipment = shipment_service.get_shipment(shipment_id)
    if shipment is None:
        abort(404)
    return render_template("dispatch/detail.html", shipment=shipment)
