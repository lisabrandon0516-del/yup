"""Hall of Records from closed days. Money values are dollars."""

from __future__ import annotations

from open_late.ui.overview_data import _profit

from .models import RecordEntry
from .timeline import _reports


def calculate(state) -> list[RecordEntry]:
    reports = [row for row in _reports(state) if int(getattr(row, "day", 0) or 0) > 0]
    if not reports:
        return []
    sales = max(reports, key=lambda row: int(getattr(row, "revenue", 0) or 0))
    visits = max(reports, key=lambda row: int(getattr(row, "visits", 0) or 0))
    best = max(reports, key=_profit)
    worst = min(reports, key=_profit)
    return [
        RecordEntry("sales_day", "Highest sales day", int(getattr(sales, "revenue", 0) or 0), int(sales.day), "Revenue"),
        RecordEntry("customer_day", "Highest customer count", int(getattr(visits, "visits", 0) or 0), int(visits.day), "Visits"),
        RecordEntry("best_profit", "Best profit day", _profit(best), int(best.day), "Profit"),
        RecordEntry("largest_loss", "Largest loss day", _profit(worst), int(worst.day), "Profit"),
    ]
