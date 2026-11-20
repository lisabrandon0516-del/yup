"""Ranges for the alerts. Each one is a projection, not an outcome."""

from __future__ import annotations

from dataclasses import replace

from open_late.text import money
from open_late.visiondeck.confidence import rate
from open_late.visiondeck.models import Forecast


def stockout_projection(state, source_id: str, category: str, turned: int) -> str:
    coming = _on_order(state, source_id, category)
    if coming > 0:
        return f"{coming} units are already on order, so a repeat of yesterday is not the base case."
    low, high = _band(turned)
    return f"Projection if nothing changes: low {low}, expected {turned}, high {high} turned away."


def stockout_score(state, category: str) -> str:
    """How yesterday's turned-away count sat against the range from the day before."""
    report = getattr(state, "last_report", None)
    if report is None:
        return ""
    report_day = int(getattr(report, "day", 0) or 0)
    prior = None
    for item in reversed(list(getattr(state, "history", []) or [])):
        day = item.get("day", 0) if isinstance(item, dict) else getattr(item, "day", 0)
        if int(day or 0) < report_day:
            prior = item
            break
    if prior is None:
        return ""
    expected = _lost(prior, category)
    if expected <= 0:
        return ""
    actual = _lost(report, category)
    low, high = _band(expected)
    if low <= actual <= high:
        return f"Yesterday's projection held: {actual} turned away, inside {low} to {high}."
    return f"Yesterday's projection missed: {actual} turned away, outside {low} to {high}."


def _band(turned: int) -> tuple[int, int]:
    count = int(turned)
    return max(1, count // 2), count + count // 2


def _lost(report, category: str) -> int:
    lost = report.get("lost_stockout_by_category") if isinstance(report, dict) else getattr(report, "lost_stockout_by_category", None)
    return int((lost or {}).get(category, 0) or 0)


def _on_order(state, source_id: str, category: str) -> int:
    products = getattr(state, "products", {}) or {}
    total = 0
    for line in _stock(state, source_id).values():
        product_id = str(getattr(line, "product_id", "") or "")
        product = products.get(product_id)
        if product is None or str(getattr(product, "category", "") or "") != category:
            continue
        total += int(getattr(line, "on_order", 0) or 0)
    if source_id == "shop":
        return total
    for shipment in getattr(state, "shipments", None) or []:
        if str(getattr(shipment, "door_id", "") or "") != source_id:
            continue
        for product_id, qty in (getattr(shipment, "lines", None) or {}).items():
            product = products.get(product_id)
            if product is None or str(getattr(product, "category", "") or "") != category:
                continue
            total += int(qty or 0)
    return total


def project(alert, state, rows, day: int) -> Forecast | None:
    """The open range. No baseline means no forecast."""
    measured = _measure(alert, state, rows)
    if measured is None:
        return None
    baseline, expected, metric, style, label, assumptions = measured
    low, high = _range(expected)
    confidence = rate(90, measured=True)[1]
    return Forecast(
        f"forecast:{alert.id}:{day}",
        alert.id,
        alert.scope,
        metric,
        1,
        int(baseline),
        low,
        int(expected),
        high,
        confidence,
        assumptions,
        int(day),
        int(day) + 1,
        str(alert.category or ""),
        str(alert.source_id or ""),
        label,
        style,
        None,
        "",
    )


def settle(prior, rows, day: int) -> Forecast | None:
    """Score the prior range once its day has arrived."""
    forecast = getattr(prior, "forecast", None) if prior is not None else None
    if forecast is None or forecast.verdict or int(day) < int(forecast.expires_at):
        return None
    actual = _actual(forecast, rows)
    if actual is None:
        return None
    verdict = "held" if forecast.low_case <= actual <= forecast.high_case else "missed"
    return replace(forecast, actual=actual, verdict=verdict)


def projection_text(forecast: Forecast) -> str:
    low = _fmt(forecast, forecast.low_case)
    expected = _fmt(forecast, forecast.expected_case)
    high = _fmt(forecast, forecast.high_case)
    tail = f" {forecast.label}" if forecast.label else ""
    return f"Projection if {forecast.assumptions}: low {low}, expected {expected}, high {high}{tail}."


def score_text(forecast: Forecast) -> str:
    if forecast is None or not forecast.verdict or forecast.actual is None:
        return ""
    actual = _fmt(forecast, forecast.actual)
    low = _fmt(forecast, forecast.low_case)
    high = _fmt(forecast, forecast.high_case)
    tail = f" {forecast.label}" if forecast.label else ""
    if forecast.verdict == "held":
        return f"Yesterday's projection held: {actual}{tail}, inside {low} to {high}."
    return f"Yesterday's projection missed: {actual}{tail}, outside {low} to {high}."


def _measure(alert, state, rows):
    kind = alert.kind
    if kind == "stockout_pressure":
        coming = _on_order(state, alert.source_id, alert.category)
        assumption = (
            "units are already on order, so a repeat of yesterday is not the base case"
            if coming > 0
            else "nothing changes"
        )
        turned = int(alert.current_value)
        return turned, turned, "turned_away", "count", "turned away", assumption
    if kind in {"sales_decline", "category_opportunity"}:
        row = _row(rows, "category_sales", alert.category)
        if row is None or row.previous_value is None:
            return None
        return int(row.previous_value), int(row.observed_value), "category_sales", "money", "", "nothing changes"
    if kind == "traffic_decline":
        row = _row(rows, "visits", "")
        if row is None or row.previous_value is None:
            return None
        return int(row.previous_value), int(row.observed_value), "visits", "count", "visits", "nothing changes"
    if kind == "cash_pressure":
        gap = int(alert.current_value)
        return gap, gap, "cash_gap", "money", "", "nothing changes"
    if kind == "debt_pressure":
        gap = int(alert.current_value)
        return gap, gap, "debt_gap", "money", "", "nothing changes"
    if kind == "labor_stress":
        gap = int(alert.current_value)
        if alert.source_id == "company":
            return gap, gap, "labor_count", "count", "", "nothing changes"
        return gap, gap, "labor_over", "money", "", "nothing changes"
    if kind == "supplier_delay":
        late = int(alert.current_value)
        return late, late, "days_late", "count", "days late", "nothing changes"
    if kind == "customer_switching":
        walked = int(alert.current_value)
        return walked, walked, "walked", "count", "walked on price", "nothing changes"
    if kind == "margin_compression":
        gap = int(alert.current_value)
        return gap, gap, "price_gap", "money", "", "nothing changes"
    return None


def _actual(forecast: Forecast, rows) -> int | None:
    if forecast.metric == "turned_away":
        found = [row.observed_value for row in rows if row.metric == "lost_stockout" and row.category == forecast.category]
        return int(found[-1]) if found else 0
    if forecast.metric == "category_sales":
        row = _row(rows, "category_sales", forecast.category)
        return None if row is None else int(row.observed_value)
    if forecast.metric == "visits":
        row = _row(rows, "visits", "")
        return None if row is None else int(row.observed_value)
    if forecast.metric == "cash_gap":
        cash = _row(rows, "cash", "")
        bill = _row(rows, "obligations", "")
        if cash is None or bill is None:
            return None
        return max(0, int(bill.observed_value) - int(cash.observed_value))
    if forecast.metric == "debt_gap":
        credit = _row(rows, "credit_left", "")
        bill = _row(rows, "obligations", "")
        if credit is None or bill is None:
            return None
        return max(0, int(bill.observed_value) - int(credit.observed_value))
    if forecast.metric == "labor_over":
        row = next((item for item in rows if item.metric == "labor" and item.source_id == forecast.source_id), None)
        if row is None:
            return None
        budget = int(_meta(row, "budget") or 0)
        return max(0, int(row.observed_value) - budget)
    if forecast.metric == "days_late":
        row = next((item for item in rows if item.source_id == forecast.source_id and item.metric in {"late_order", "late_shipment", "late_payments"}), None)
        return None if row is None else int(row.observed_value)
    if forecast.metric == "walked":
        row = _row(rows, "lost_price", "")
        return None if row is None else int(row.observed_value)
    if forecast.metric == "price_gap":
        row = next((item for item in rows if item.metric == "price" and item.source_id == forecast.source_id), None)
        if row is None:
            return None
        cost = int(_meta(row, "cost") or 0)
        return max(0, cost - int(row.observed_value))
    if forecast.metric == "labor_count":
        return None
    return None


def _range(expected: int) -> tuple[int, int]:
    if expected <= 0:
        return 0, 0
    return _band(expected)


def _fmt(forecast: Forecast, amount: int) -> str:
    if forecast.style == "money":
        return money(amount)
    return str(int(amount))


def _row(rows, metric: str, category: str):
    found = [row for row in rows if row.metric == metric and (not category or row.category == category)]
    return found[-1] if found else None


def _meta(row, key: str) -> str:
    for name, value in row.metadata:
        if name == key:
            return value
    return ""


def _stock(state, source_id: str) -> dict:
    for door in getattr(state, "doors", None) or []:
        if str(getattr(door, "id", "") or "") == source_id:
            return dict(getattr(door, "stock", {}) or {})
    if source_id == "shop":
        return dict(getattr(state, "stock", {}) or {})
    return {}
