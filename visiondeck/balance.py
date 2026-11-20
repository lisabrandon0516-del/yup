"""Phase 12. Standard keeps today's bars. Calm is quieter. Stern is louder.

A single turned-away customer is noise. A forecast that has missed twice
opens its next range. A flood of one kind keeps the loudest few, and two
options of the same family collapse to one.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from open_late.visiondeck.config import LOST_PRICE_MIN, MATERIAL_PERCENT, STOCKOUT_CRITICAL

_PREFIX = {
    "stockout_pressure": "stockout:",
    "cash_pressure": "cash_pressure:",
    "margin_compression": "margin:",
    "sales_decline": "sales_decline:",
    "traffic_decline": "traffic_decline:",
}


@dataclass(frozen=True)
class Bars:
    material: int
    lost_price: int
    stockout_critical: int
    stockout_high: int
    stockout_floor: int
    per_kind: int


_STANDARD = Bars(MATERIAL_PERCENT, LOST_PRICE_MIN, STOCKOUT_CRITICAL, 3, 2, 6)
_CALM = Bars(15, 8, 8, 5, 3, 4)
_STERN = Bars(5, 3, 4, 2, 1, 8)


def bars_for(state) -> Bars:
    """Economy off uses the standard bars. The card being off is not silence."""
    eco = getattr(state, "economy", None)
    key = str(getattr(eco, "difficulty", "") or "").strip().lower()
    if key == "calm":
        return _CALM
    if key == "stern":
        return _STERN
    return _STANDARD


def widen_forecast(forecast, state, kind: str):
    """Two misses, and more misses than holds, open the next range. The expected case stays."""
    if forecast is None:
        return None
    misses, holds = _record(state, kind)
    if misses < 2 or misses <= holds:
        return forecast
    expected = int(forecast.expected_case)
    low_span = max(1, expected - int(forecast.low_case))
    high_span = max(1, int(forecast.high_case) - expected)
    return replace(
        forecast,
        low_case=max(0, expected - low_span * 2),
        high_case=expected + high_span * 2,
    )


def limit_alerts(alerts: list, cap: int) -> list:
    """Keep every resolved row. Keep the loudest open rows of each kind."""
    kept = []
    seen: dict[str, int] = {}
    for alert in alerts:
        if getattr(alert, "status", "") == "resolved":
            kept.append(alert)
            continue
        kind = str(getattr(alert, "kind", "") or "")
        seen[kind] = seen.get(kind, 0) + 1
        if seen[kind] <= cap:
            kept.append(alert)
    return kept


def spread(options) -> tuple:
    """One option per family. Doing nothing stays last."""
    kept = []
    seen = set()
    hold = None
    for item in options:
        family = str(getattr(item, "action_family", "") or "")
        if family == "do_nothing":
            hold = item
            continue
        if family in seen:
            continue
        seen.add(family)
        kept.append(item)
    if hold is not None:
        kept.append(hold)
    return tuple(kept)


def _record(state, kind: str) -> tuple[int, int]:
    prefix = _PREFIX.get(kind, "")
    if not prefix:
        return 0, 0
    misses = 0
    holds = 0
    for note in list(getattr(state, "decisions", []) or []):
        if str(getattr(note, "kind", "") or "") != "decision_lab":
            continue
        if not str(getattr(note, "ref", "") or "").startswith(prefix):
            continue
        result = str(getattr(note, "result", "") or "").lower()
        if "missed" in result:
            misses += 1
        elif "held" in result:
            holds += 1
    return misses, holds
