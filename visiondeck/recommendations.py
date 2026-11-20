"""One next action the company can already take. Nothing here places the order."""

from __future__ import annotations

from dataclasses import dataclass

from open_late.text import money
from open_late.visiondeck.forecasts import _on_order, _stock, projection_text
from open_late.visiondeck.models import Recommendation

# Families the simulation can already perform. do_nothing is the baseline.
ACTIONS = {
    "allocate": "open_late.corporate.allocate",
    "place_order": "open_late.engine.place_order",
    "set_price": "open_late.engine.set_price",
    "do_nothing": "",
}


@dataclass(frozen=True)
class StockoutAction:
    text: str
    kind: str
    product_id: str = ""
    quantity: int = 0


def stockout_recommendation(state, source_id: str, category: str, place: str) -> StockoutAction:
    if _on_order(state, source_id, category) > 0:
        return StockoutAction("Wait. Units are already on order.", "wait")
    product_id, pile = ("", 0) if source_id == "shop" else _warehouse_pick(state, category)
    held = 0 if source_id == "shop" else _warehouse_units(state, category)
    if held > 0:
        noun = "unit" if held == 1 else "units"
        return StockoutAction(
            f"Send the {held} warehouse {noun} to {place}.",
            "send",
            product_id,
            pile,
        )
    return StockoutAction(
        f"Place an order for {category}.",
        "order",
        _empty_product(state, source_id, category),
    )


def _warehouse_units(state, category: str) -> int:
    products = getattr(state, "products", {}) or {}
    total = 0
    for line in (getattr(state, "stock", {}) or {}).values():
        product_id = str(getattr(line, "product_id", "") or "")
        product = products.get(product_id)
        if product is None or str(getattr(product, "category", "") or "") != category:
            continue
        total += int(getattr(line, "on_hand", 0) or 0)
    return total


def _warehouse_pick(state, category: str) -> tuple[str, int]:
    products = getattr(state, "products", {}) or {}
    best_id = ""
    best = 0
    for line in (getattr(state, "stock", {}) or {}).values():
        product_id = str(getattr(line, "product_id", "") or "")
        product = products.get(product_id)
        if product is None or str(getattr(product, "category", "") or "") != category:
            continue
        held = int(getattr(line, "on_hand", 0) or 0)
        if held > best:
            best_id, best = product_id, held
    return best_id, best


def recommend(alert, state) -> tuple[Recommendation, ...]:
    """Ranked options for one alert. The company is not changed."""
    options: list[Recommendation] = []
    if alert.kind == "stockout_pressure" and _on_order(state, alert.source_id, alert.category) <= 0:
        truck = _truck(alert, state)
        if truck is not None:
            options.append(truck)
        ordered = _order(alert, state)
        if ordered is not None:
            options.append(ordered)
    elif alert.kind == "margin_compression":
        priced = _reprice(alert, state)
        if priced is not None:
            options.append(priced)
    options.append(_hold(alert, state))
    from open_late.visiondeck.balance import spread

    return spread(options)


def _truck(alert, state) -> Recommendation | None:
    if alert.source_id == "shop":
        return None
    product_id, quantity = _warehouse_pick(state, alert.category)
    if quantity <= 0 or not product_id:
        return None
    door = _door(state, alert.source_id)
    if door is None:
        return None
    try:
        from open_late.corporate import transfer_freight
        from open_late.economy import adjust_freight

        freight = int(adjust_freight(state, door.id, int(transfer_freight(door, quantity))))
    except Exception:
        return None
    cash = getattr(state, "cash", None)
    if cash is not None and int(cash) < freight:
        return None
    place = str(getattr(door, "city", "") or door.id)
    kept = ""
    if getattr(alert, "forecast", None) is not None:
        kept = f" No-action expected remains {alert.forecast.expected_case} turned away."
    return _option(
        alert,
        "allocate",
        f"Send the {quantity} warehouse units to {place}.",
        door.id,
        f"Sends {quantity} units to {place}.{kept}",
        freight,
        "freight",
        int(getattr(door, "transit_days", 1) or 1),
        "low",
        "high",
        "The truck is committed once it leaves.",
        ("Warehouse has the units.", f"{place} is on the lease.", "Cash covers the freight."),
        "Warehouse stock is committed to the truck.",
        product_id,
        quantity,
    )


def _order(alert, state) -> Recommendation | None:
    from open_late.content import SUPPLIERS

    product_id = _empty_product(state, alert.source_id, alert.category)
    product = (getattr(state, "products", {}) or {}).get(product_id)
    if product is None:
        return None
    supplier = SUPPLIERS.get(str(getattr(product, "supplier_id", "") or ""))
    if supplier is None:
        return None
    categories = list(getattr(supplier, "categories", []) or [])
    if categories and alert.category and alert.category not in categories:
        return None
    unit = int(getattr(product, "cost", 0) or 0)
    if unit <= 0:
        return None
    minimum = int(getattr(supplier, "minimum_order", 0) or 0)
    quantity = max(1, (minimum + unit - 1) // unit) if minimum else 1
    merchandise = unit * quantity
    cash = getattr(state, "cash", None)
    if cash is not None and int(cash) < merchandise:
        return None
    return _option(
        alert,
        "place_order",
        f"Place an order for {quantity} units of {alert.category}. Merchandise {money(merchandise)}.",
        str(supplier.id),
        f"Orders {quantity} units. No-action expected remains the current projection.",
        merchandise,
        "merchandise",
        int(getattr(supplier, "lead_time_days", 1) or 1),
        "moderate",
        "moderate",
        "The order stands until it arrives.",
        (
            f"{supplier.name} is on the sheet.",
            f"The order meets the {minimum} minimum.",
            "Cash covers the merchandise.",
        ),
        "Cash leaves when the order is placed.",
        product_id,
        quantity,
    )


def _reprice(alert, state) -> Recommendation | None:
    product = (getattr(state, "products", {}) or {}).get(alert.source_id)
    if product is None:
        return None
    cost = int(getattr(product, "cost", 0) or 0)
    price = int(getattr(product, "price", 0) or 0)
    if cost <= 0 or price >= cost or cost > cost * 5:
        return None
    name = str(getattr(product, "name", "") or product.id)
    return _option(
        alert,
        "set_price",
        f"Set {name} to {money(cost)}.",
        str(product.id),
        f"{name} moves to cost. No-action leaves the price at {money(price)}.",
        0,
        "none",
        0,
        "moderate",
        "high",
        "The price can be set back.",
        ("The new price is at cost or above.", "The new price is within five times cost."),
        "The shelf price changes when the player sets it.",
        str(product.id),
        0,
        cost,
    )


def _hold(alert, state) -> Recommendation:
    waiting = alert.kind == "stockout_pressure" and _on_order(state, alert.source_id, alert.category) > 0
    title = "Wait. Units are already on order." if waiting else "Do nothing."
    forecast = getattr(alert, "forecast", None)
    benefit = projection_text(forecast) if forecast is not None else "No action is the baseline."
    return _option(
        alert,
        "do_nothing",
        title,
        str(alert.source_id or "company"),
        benefit,
        0,
        "none",
        0,
        "moderate",
        "high" if forecast is not None else "low",
        "Already the current state.",
        (),
        "The company is left as it is.",
    )


def _option(
    alert,
    family,
    title,
    target,
    benefit,
    cost,
    operational,
    delay,
    risk,
    confidence,
    reversibility,
    prerequisites,
    side_effects,
    product_id="",
    quantity=0,
    price=0,
) -> Recommendation:
    return Recommendation(
        f"{alert.id}:{family}",
        title,
        alert.id,
        family,
        target,
        benefit,
        int(cost),
        operational,
        int(delay),
        risk,
        confidence,
        reversibility,
        tuple(prerequisites),
        side_effects,
        product_id,
        int(quantity),
        int(price),
    )


def _door(state, door_id: str):
    for door in getattr(state, "doors", []) or []:
        if str(getattr(door, "id", "") or "") == door_id:
            return door
    return None


def _empty_product(state, source_id: str, category: str) -> str:
    products = getattr(state, "products", {}) or {}
    found: list[str] = []
    for line in _stock(state, source_id).values():
        product_id = str(getattr(line, "product_id", "") or "")
        product = products.get(product_id)
        if product is None or str(getattr(product, "category", "") or "") != category:
            continue
        if int(getattr(line, "on_hand", 0) or 0) <= 0:
            found.append(product_id)
    return sorted(found)[0] if found else ""
