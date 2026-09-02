from __future__ import annotations

from datetime import datetime, timezone
import logging

from flask import Blueprint, abort, current_app, redirect, render_template, url_for

from app.routes import web


LOGGER = logging.getLogger(__name__)
pulse_bp = Blueprint("pulse", __name__, url_prefix="/pulse")


def pulse_service():
    return current_app.extensions["pulse"]["service"]


@pulse_bp.get("/")
def index():
    selected_event_id = None
    dashboard = pulse_service().dashboard(selected_event_id=selected_event_id)
    return render_template("pulse/index.html", **dashboard)


@pulse_bp.get("/events/<event_id>")
def event_detail(event_id: str):
    dashboard = pulse_service().dashboard(selected_event_id=event_id)
    if dashboard["selected_event"] is None:
        abort(404)
    return render_template("pulse/index.html", **dashboard)


@pulse_bp.post("/events/<event_id>/follow")
def follow_event(event_id: str):
    updated = pulse_service().set_event_flag(event_id, "followed", True)
    if updated is None:
        abort(404)
    LOGGER.info("PULSE event followed: %s", event_id)
    return redirect(url_for("pulse.event_detail", event_id=event_id))


@pulse_bp.post("/events/<event_id>/review")
def review_event(event_id: str):
    updated = pulse_service().set_event_flag(event_id, "reviewed", True)
    if updated is None:
        abort(404)
    LOGGER.info("PULSE event reviewed: %s", event_id)
    return redirect(url_for("pulse.event_detail", event_id=event_id))


@pulse_bp.post("/events/<event_id>/archive")
def archive_event(event_id: str):
    updated = pulse_service().set_event_flag(event_id, "archived", True)
    if updated is None:
        abort(404)
    LOGGER.info("PULSE event archived: %s", event_id)
    return redirect(url_for("pulse.index"))


@pulse_bp.post("/events/<event_id>/coverage")
def create_nexus_coverage(event_id: str):
    event = pulse_service().get_event(event_id)
    if event is None:
        abort(404)

    today = datetime.now(timezone.utc).date().isoformat()
    city, country = _split_location(event.get("location", ""))
    coverage_id = web.build_coverage_id(event["title"])
    coverage = {
        "coverage_name": event["title"],
        "submit_date": today,
        "event_date": today,
        "city": city,
        "country": country,
        "locality_type": "auto",
        "agency": "ATLAS NEXUS",
        "photographer": "PULSE",
        "editor": "pulse",
        "photos": [],
        "pulse_event_id": event_id,
    }
    web.attach_editor_metadata(coverage)
    web.attach_default_ai_context(coverage)
    web.coverages[coverage_id] = coverage
    web.persist_coverage(coverage_id)
    pulse_service().mark_coverage_created(event_id, coverage_id)
    LOGGER.info("PULSE event %s created NEXUS coverage bridge %s", event_id, coverage_id)
    return redirect(url_for("web.coverage_detail", coverage_id=coverage_id))


def _split_location(location: str) -> tuple[str, str]:
    parts = [part.strip() for part in str(location or "").split(",") if part.strip()]
    if len(parts) >= 2:
        return parts[0], parts[-1]
    if parts:
        return parts[0], "Ecuador"
    return "Quito", "Ecuador"
