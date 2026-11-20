"""Morning briefing. Dollars stay dollars."""

from __future__ import annotations

from dataclasses import dataclass

from open_late.text import money

from .action_center import build
from .navigation import target
from .scope import Scope


@dataclass(frozen=True)
class BriefingItem:
    title: str
    detail: str
    priority: int
    target: object
    confidence: str = "confirmed"


def morning(state, scope: Scope | None = None, limit: int = 8) -> list[BriefingItem]:
    if state is None:
        return []
    scope = scope or Scope()
    rows = []
    for item in build(state, scope):
        priority = {"Critical": 100, "Action Required": 70, "Opportunity": 45, "Information": 20}.get(item.band, 10)
        rows.append(BriefingItem(item.title, item.detail, priority, item.target, item.confidence))
    headlines = []
    try:
        from open_late.ui.overview_data import snapshot

        snap = snapshot(state, "week")
        profit = int(snap.get("profit", 0) or 0)
        if profit < 0:
            headlines.append(BriefingItem(
                "Weekly profit is negative",
                f"Current result {money(profit)}",
                90,
                target("account", "profit"),
                "confirmed",
            ))
        low = int(snap.get("low_stock", 0) or 0)
        if low:
            headlines.append(BriefingItem(
                "Low-stock exposure",
                f"{low} inventory piles need review",
                75,
                target("inventory"),
                "confirmed",
            ))
    except Exception:
        pass
    headlines.extend(_stockout_lines(state, scope))
    headlines.extend(_decision_lines(state, scope))
    headlines.extend(_memory_lines(state))
    headlines.extend(_rival_lines(state))
    ranked = sorted(rows, key=lambda row: (-row.priority, row.title))
    room = max(0, limit - len(headlines))
    return (ranked[:room] + headlines)[:limit]


def _rival_lines(state) -> list[BriefingItem]:
    from open_late.visiondeck.rivals import public_rival_alert

    alert = public_rival_alert(state)
    if alert is None:
        return []
    if alert.action == "review_prices":
        drill = target(
            "sales",
            alert.door_id,
            filters={"action": "review_prices", "door": alert.door_id},
            reason=alert.text,
        )
    elif alert.action == "do_nothing":
        drill = target(
            "",
            filters={"action": "do_nothing", "door": alert.door_id, "place": _door_city(state, alert.door_id)},
            reason=alert.text,
        )
    else:
        drill = target("rival", alert.chain_id, reason=alert.text)
    return [BriefingItem(alert.text, alert.text, 80, drill, "confirmed")]


def _stockout_lines(state, scope: Scope) -> list[BriefingItem]:
    from open_late.visiondeck import stockout_alerts
    from open_late.visiondeck.persistence import stored_alerts

    alerts = stockout_alerts(state, prior=stored_alerts(state))
    if scope.kind == "store" and scope.ident:
        alerts = [item for item in alerts if item.source_id == scope.ident]
    return [
        BriefingItem(alert.evidence, alert.evidence, 95, _stockout_target(state, alert), alert.confidence)
        for alert in alerts
    ]


def _decision_lines(state, scope: Scope) -> list[BriefingItem]:
    from open_late.visiondeck.signals import remembered

    alerts = [item for item in remembered(state) if item.kind == "stockout_pressure" and item.recommendations]
    if scope.kind == "store" and scope.ident:
        alerts = [item for item in alerts if item.source_id == scope.ident]
    if not alerts:
        return []
    alert = alerts[0]
    detail = "The options, the cost, and doing nothing."
    if alert.memory:
        detail = f"{detail} {alert.memory}"
    return [BriefingItem(
        f"Compare responses for {alert.category}.",
        detail,
        94,
        target("home", alert.id, filters={"action": "decide", "alert": alert.id}),
        "confirmed",
    )]


def _memory_lines(state) -> list[BriefingItem]:
    from open_late.visiondeck.memory import stockout_outcomes

    from open_late.visiondeck.memory import rival_outcomes

    lines = stockout_outcomes(state) + rival_outcomes(state)
    return [
        BriefingItem(text, text, 96, target("stores"), "confirmed")
        for text in lines
    ]


def _door_city(state, door_id: str) -> str:
    for door in getattr(state, "doors", []) or []:
        if str(getattr(door, "id", "") or "") == door_id:
            return str(getattr(door, "city", "") or door_id)
    return door_id


def _place_for(state, alert) -> str:
    for door in getattr(state, "doors", []) or []:
        if str(getattr(door, "id", "") or "") == alert.source_id and getattr(door, "city", ""):
            return str(door.city)
    return alert.source_id


def _stockout_target(state, alert):
    place = _place_for(state, alert)
    shared = {"category": alert.category, "place": place, "door": alert.source_id}
    if alert.action == "send":
        return target(
            "stores",
            alert.source_id,
            filters={**shared, "action": "send", "product": alert.product_id, "qty": alert.quantity},
            reason=alert.evidence,
        )
    if alert.action == "order":
        return target(
            "orders",
            alert.product_id,
            filters={**shared, "action": "order", "query": alert.product_id},
            reason=alert.evidence,
        )
    return target("", filters={**shared, "action": "wait", "lost": alert.lost}, reason=alert.evidence)
