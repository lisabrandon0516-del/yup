"""Turn the shelf the company can see into timestamped observations."""

from __future__ import annotations

from open_late.visiondeck.models import Observation


def inventory_observations(state) -> list[Observation]:
    if state is None:
        return []
    day = int(getattr(state, "day", 0) or 0)
    products = getattr(state, "products", {}) or {}
    rows: list[Observation] = []
    for source_type, source_id, stock, place, region in _shelves(state):
        totals: dict[str, int] = {}
        for line in stock.values():
            product = products.get(getattr(line, "product_id", ""))
            if product is None:
                continue
            category = str(getattr(product, "category", "") or "other")
            totals[category] = totals.get(category, 0) + int(getattr(line, "on_hand", 0) or 0)
        for category, units in sorted(totals.items()):
            rows.append(Observation(
                f"on_hand:{source_id}:{category}:{day}",
                day,
                source_type,
                source_id,
                category,
                "on_hand",
                units,
                None,
                region,
                source_id if source_type == "store" else "",
                "company",
                90,
                0,
                (("place", place),),
            ))
    report = getattr(state, "last_report", None)
    lost = getattr(report, "lost_stockout_by_category", None) or {}
    earlier = _previous_lost(state)
    report_day = int(getattr(report, "day", 0) or 0) or day
    for category, count in sorted(lost.items()):
        name = str(category)
        rows.append(Observation(
            f"lost_stockout:{name}:{report_day}",
            report_day,
            "company",
            "",
            name,
            "lost_stockout",
            int(count or 0),
            earlier.get(name),
            "",
            "",
            "company",
            85,
        ))
    return rows


def collect_observations(state) -> list[Observation]:
    """Every adapter, in a stable order. Reading does not change the company."""
    if state is None:
        return []
    from open_late.visiondeck.adapters import all_observations

    rows = all_observations(state)
    rows.sort(key=lambda row: (row.metric, row.source_id, row.category, row.id))
    return rows


def _shelves(state) -> list[tuple[str, str, dict, str, str]]:
    doors = list(getattr(state, "doors", []) or [])
    if doors:
        return [
            (
                "store",
                str(getattr(door, "id", "") or "store"),
                dict(getattr(door, "stock", {}) or {}),
                str(getattr(door, "city", "") or getattr(door, "id", "") or "store"),
                str(getattr(door, "region", "") or ""),
            )
            for door in doors
        ]
    return [("shop", "shop", dict(getattr(state, "stock", {}) or {}), "shop", "")]


def _previous_lost(state) -> dict[str, int]:
    history = list(getattr(state, "history", []) or [])
    if not history:
        return {}
    report = history[-1]
    lost = getattr(report, "lost_stockout_by_category", None)
    if lost is None and isinstance(report, dict):
        lost = report.get("lost_stockout_by_category") or {}
    return {str(key): int(value or 0) for key, value in (lost or {}).items()}
