from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class XBudgetController:
    def __init__(self, monthly_budget: float = 10.0, internal_hard_limit: float = 9.0):
        self.monthly_budget = monthly_budget
        self.internal_hard_limit = internal_hard_limit

    def status(self, usage_rows: list[dict[str, Any]]) -> dict[str, Any]:
        month_key = datetime.now(timezone.utc).strftime("%Y-%m")
        month_total = sum(
            float(row.get("estimated_cost", 0) or 0)
            for row in usage_rows
            if str(row.get("created_at", "")).startswith(month_key)
        )
        percent = 0 if self.monthly_budget <= 0 else min(100, round((month_total / self.monthly_budget) * 100))
        if month_total >= self.internal_hard_limit:
            state = "BLOQUEADO"
        elif percent >= 90:
            state = "SOLO URGENTES"
        elif percent >= 75:
            state = "RESTRINGIDO"
        elif percent >= 50:
            state = "AHORRO"
        else:
            state = "NORMAL"
        return {
            "monthly_budget": self.monthly_budget,
            "internal_hard_limit": self.internal_hard_limit,
            "month_total": round(month_total, 4),
            "percent": percent,
            "state": state,
            "blocked": state == "BLOQUEADO",
        }

    def can_spend(self, usage_rows: list[dict[str, Any]], estimated_cost: float) -> bool:
        return self.status(usage_rows)["month_total"] + estimated_cost <= self.internal_hard_limit
