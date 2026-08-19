from __future__ import annotations

# Backward-compatible entry point; the implementation now lives in
# app.dispatch.worker so it can be invoked as `python -m app.dispatch.worker`.
from app.dispatch.worker import (
    DispatchReview,
    build_parser,
    format_shipment_line,
    main,
    parse_scheduled_at,
    print_review,
    review_shipments,
    run_claim,
    run_cleanup,
    run_dry_run,
    run_process_due,
)

__all__ = [
    "DispatchReview",
    "build_parser",
    "format_shipment_line",
    "main",
    "parse_scheduled_at",
    "print_review",
    "review_shipments",
    "run_claim",
    "run_cleanup",
    "run_dry_run",
    "run_process_due",
]

if __name__ == "__main__":
    raise SystemExit(main())
