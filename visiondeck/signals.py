"""One stockout signal per empty shelf that already turned people away."""

from __future__ import annotations

from open_late.visiondeck.diagnosis import stockout_cause
from open_late.visiondeck.engine import detect
from open_late.visiondeck.forecasts import stockout_projection, stockout_score
from open_late.visiondeck.models import Signal
from open_late.visiondeck.observations import inventory_observations
from open_late.visiondeck.recommendations import stockout_recommendation

__all__ = ["detect", "remembered", "stockout_alerts"]


def remembered(state):
    """Today's alerts, continued from the signals stored on the save."""
    from open_late.visiondeck.persistence import stored_alerts

    return detect(state, prior=stored_alerts(state))


def stockout_alerts(state, prior=None) -> list[Signal]:
    if state is None:
        return []
    seen = inventory_observations(state)
    lost = {row.category: row.observed_value for row in seen if row.metric == "lost_stockout"}
    day = int(getattr(state, "day", 0) or 0)
    known = {item.id: item for item in (prior or []) if getattr(item, "kind", "") == "stockout_pressure"}
    places = {
        str(getattr(door, "id", "")): str(getattr(door, "city", "") or getattr(door, "id", ""))
        for door in (getattr(state, "doors", []) or [])
    }
    alerts: list[Signal] = []
    for row in seen:
        if row.metric != "on_hand" or row.observed_value != 0:
            continue
        turned = int(lost.get(row.category, 0) or 0)
        if turned <= 0:
            continue
        ident = f"stockout:{row.source_id}:{row.category}"
        earlier = known.get(ident)
        place = places.get(row.source_id) or row.source_id
        cause, confidence = stockout_cause(state, row.category)
        outlook = stockout_projection(state, row.source_id, row.category, turned)
        action = stockout_recommendation(state, row.source_id, row.category, place)
        score = stockout_score(state, row.category)
        shelf = f"{place} {row.category} is empty, 0 on hand. {turned} turned away for an empty {row.category} shelf."
        tail = " ".join(part for part in (cause, outlook, action.text, score) if part)
        alerts.append(Signal(
            ident,
            "stockout_pressure",
            day,
            earlier.first_seen if earlier is not None else day,
            day,
            "active" if earlier is not None else "new",
            row.category,
            row.source_id,
            0,
            turned,
            confidence,
            f"{shelf} {tail}",
            action.kind,
            action.product_id,
            action.quantity,
        ))
    alerts.sort(key=lambda item: (item.source_id, item.category))
    return alerts
