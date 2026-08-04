from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO
from zoneinfo import ZoneInfo

from app.config import DISPATCH_STORE_PATH
from app.dispatch import DispatchShipmentStore, DispatchStoreError
from app.dispatch.scheduler import DispatchScheduler

DISPLAY_TIMEZONE = ZoneInfo("America/Guayaquil")


@dataclass(frozen=True)
class DispatchReview:
    reviewed: int
    due: list[dict]
    future: list[dict]
    invalid: list[dict[str, str]]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.dispatch_worker",
        description="Revisa despachos programados de DISPATCH.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Revisar sin modificar despachos.")
    mode.add_argument("--claim", action="store_true", help="Reclamar despachos vencidos sin enviarlos.")
    parser.add_argument(
        "--store-path",
        default=DISPATCH_STORE_PATH,
        help="Ruta opcional al dispatch_shipments.json.",
    )
    return parser


def parse_scheduled_at(shipment: dict) -> datetime | None:
    scheduled_at = str(shipment.get("scheduled_at", "")).strip()
    if not scheduled_at:
        return None
    try:
        parsed = datetime.fromisoformat(scheduled_at)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def review_shipments(store: DispatchShipmentStore, now: datetime | None = None) -> DispatchReview:
    scheduler = DispatchScheduler(store)
    reference = now or datetime.now(timezone.utc)
    due = scheduler.list_due_shipments(reference)
    due_ids = {shipment["id"] for shipment in due}
    future = []
    reviewed = 0

    for shipment in store.list_shipments():
        if shipment.get("status") != "Programado":
            continue
        reviewed += 1
        scheduled_at = parse_scheduled_at(shipment)
        if scheduled_at is None or shipment.get("id") in due_ids:
            continue
        if scheduled_at > reference.astimezone(scheduled_at.tzinfo):
            future.append(shipment)

    return DispatchReview(
        reviewed=reviewed,
        due=due,
        future=future,
        invalid=list(scheduler.invalid_shipments),
    )


def format_shipment_line(shipment: dict) -> str:
    recipients = shipment.get("recipients") if isinstance(shipment.get("recipients"), list) else []
    photos = shipment.get("photo_ids") if isinstance(shipment.get("photo_ids"), list) else []
    return (
        f"- ID: {shipment.get('id', '')} | "
        f"nombre: {shipment.get('name', '')} | "
        f"scheduled_at: {shipment.get('scheduled_at', '')} | "
        f"zona: {shipment.get('timezone', 'America/Guayaquil')} | "
        f"canal: {shipment.get('channel', '')} | "
        f"destinatarios: {len(recipients)} | "
        f"fotografías: {len(photos)}"
    )


def print_review(review: DispatchReview, out: TextIO) -> None:
    print("DISPATCH dry-run: revisión de despachos programados", file=out)
    print(f"Zona de visualización: {DISPLAY_TIMEZONE.key}", file=out)
    if review.due:
        print("Despachos vencidos:", file=out)
        for shipment in review.due:
            print(format_shipment_line(shipment), file=out)
    else:
        print("No hay despachos vencidos para reclamar.", file=out)

    if review.invalid:
        print("Despachos inválidos:", file=out)
        for item in review.invalid:
            print(f"- ID: {item.get('id', '')} | error: {item.get('error', '')}", file=out)

    print(
        "Resumen: "
        f"revisados={review.reviewed} "
        f"vencidos={len(review.due)} "
        f"futuros={len(review.future)} "
        f"inválidos={len(review.invalid)}",
        file=out,
    )


def run_dry_run(store: DispatchShipmentStore, out: TextIO) -> int:
    review = review_shipments(store)
    print_review(review, out)
    return 0


def run_claim(store: DispatchShipmentStore, out: TextIO) -> int:
    review = review_shipments(store)
    scheduler = DispatchScheduler(store)
    print("DISPATCH claim: reclamación de despachos vencidos", file=out)
    if not review.due:
        print("No hay despachos vencidos para reclamar.", file=out)
    for shipment in review.due:
        claimed = scheduler.claim_for_execution(str(shipment.get("id", "")))
        if claimed is None:
            print(f"- OMITIDO: {shipment.get('id', '')} ya no está disponible para reclamar.", file=out)
            continue
        print(f"- RECLAMADO: {claimed.get('id', '')} | estado: {claimed.get('status', '')}", file=out)
    refreshed = review_shipments(store)
    print(
        "Resumen: "
        f"revisados={review.reviewed} "
        f"vencidos={len(review.due)} "
        f"futuros={len(refreshed.future)} "
        f"inválidos={len(refreshed.invalid)}",
        file=out,
    )
    return 0


def main(argv: list[str] | None = None, out: TextIO = sys.stdout, err: TextIO = sys.stderr) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    store = DispatchShipmentStore(Path(args.store_path))

    try:
        if args.dry_run:
            return run_dry_run(store, out)
        if args.claim:
            return run_claim(store, out)
    except DispatchStoreError as error:
        print(f"ERROR: {error}", file=err)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
