"""Read the company. These figures are not written back."""

from __future__ import annotations


def read(state, metric: str) -> float:
    if state is None:
        return 0.0
    if metric == "cash":
        return float(getattr(state, "cash", 0) or 0)
    if metric == "open_stores":
        day = int(getattr(state, "day", 0) or 0)
        return float(sum(
            getattr(door, "status", "") == "open" and int(getattr(door, "opens_on", 0) or 0) <= day
            for door in getattr(state, "doors", []) or []
        ))
    if metric in ("weekly_profit", "weekly_visits", "stockouts"):
        try:
            from open_late.ui.overview_data import snapshot

            snap = snapshot(state, "week")
            return float({
                "weekly_profit": snap.get("profit", 0),
                "weekly_visits": snap.get("visits", 0),
                "stockouts": snap.get("low_stock", 0),
            }[metric] or 0)
        except Exception:
            return 0.0
    return float(getattr(state, metric, 0) or 0)


def achieved(value: float, comparison: str, target: float) -> bool:
    if comparison == ">=":
        return value >= target
    if comparison == "<=":
        return value <= target
    return value == target
