"""One inventory row per pile, and the totals above the sheet."""

from __future__ import annotations

from open_late.content import SUPPLIERS

STATUS_COLOR = {
    "problem": "#C24141",
    "watch": "#C2410C",
}

HEADERS = (
    "SKU",
    "Product",
    "Location",
    "On hand",
    "On order",
    "Allocated",
    "Available",
    "WOS",
    "Reorder point",
    "Status",
)


def _history_weekly(state, product_id: str) -> int:
    total = 0
    for report in list(getattr(state, "history", None) or [])[-7:]:
        total += int((getattr(report, "units_by_product", None) or {}).get(product_id, 0) or 0)
    return total


def _in_window(day: int, sold_on: int) -> bool:
    return day - 7 < sold_on <= day


def _door_weekly(door, product_id: str, day: int) -> int:
    total = 0
    for row in getattr(door, "sales_days", None) or []:
        sold_on = int(getattr(row, "day", 0) or 0)
        if _in_window(day, sold_on):
            total += int((getattr(row, "units", None) or {}).get(product_id, 0) or 0)
    return total


def _demand(state, product_id: str) -> int:
    """Units sold in the last seven days. A chain uses each door's tape."""
    day = int(getattr(state, "day", 1) or 1)
    doors = list(getattr(state, "doors", None) or [])
    if not doors:
        return _history_weekly(state, product_id)
    return sum(_door_weekly(door, product_id, day) for door in doors)


def _reservations(state) -> tuple[dict[str, int], dict[str, dict[str, int]]]:
    """Units still on a truck: reserved at the warehouse, inbound at the door."""
    by_product: dict[str, int] = {}
    by_door: dict[str, dict[str, int]] = {}
    for shipment in getattr(state, "shipments", None) or []:
        door_id = str(getattr(shipment, "door_id", "") or "")
        bucket = by_door.setdefault(door_id, {})
        for product_id, qty in (getattr(shipment, "lines", None) or {}).items():
            amount = int(qty or 0)
            if amount <= 0:
                continue
            by_product[product_id] = by_product.get(product_id, 0) + amount
            bucket[product_id] = bucket.get(product_id, 0) + amount
    return by_product, by_door


def _shrink(state) -> int:
    reports = list(getattr(state, "history", None) or [])
    total = sum(int(getattr(report, "shrink_cost", 0) or 0) for report in reports)
    last = getattr(state, "last_report", None)
    if last is not None and int(getattr(last, "day", 0) or 0):
        if not any(int(getattr(report, "day", 0) or 0) == int(last.day) for report in reports):
            total += int(getattr(last, "shrink_cost", 0) or 0)
    return total


def _warehouse_label(state) -> str:
    for site in getattr(state, "sites", None) or []:
        if getattr(site, "is_warehouse", False):
            return str(site.label or "Warehouse")
    return "Warehouse"


def _status(on_hand: int, on_order: int, age: int, reorder: int, wos: float | None, weekly: int) -> tuple[str, str]:
    if on_hand <= 0 and on_order <= 0:
        return "Out", "problem"
    if on_hand <= 0:
        return "On order", "watch"
    if age >= 21:
        return "Aging", "watch"
    if on_hand <= reorder:
        return "Low", "watch"
    # A handful of sales is not a pace. Show the weeks, and mark overstock only
    # when the pile really covers twelve weeks of a rate the tape can support.
    if weekly >= 4 and wos is not None and wos >= 12:
        return "Overstock", "watch"
    return "In stock", ""


def _row(product, *, place: str, location: str, region: str, store: str, on_hand: int, on_order: int, allocated: int, age: int, weekly: int) -> dict:
    house = SUPPLIERS.get(product.supplier_id)
    allocated = max(0, min(int(allocated), int(on_hand)))
    reorder = 2 if weekly <= 0 else max(2, weekly)
    wos = None if weekly <= 0 else round(on_hand / weekly, 1)
    status, tone = _status(on_hand, on_order, age, reorder, wos, weekly)
    return {
        "sku": product.id,
        "product": product.name,
        "location": location,
        "place": place,
        "store": store,
        "region": region,
        "department": str(product.department or product.category or ""),
        "vendor": house.name if house is not None else product.supplier_id,
        "vendor_id": product.supplier_id,
        "on_hand": on_hand,
        "on_order": on_order,
        "allocated": allocated,
        "available": on_hand - allocated,
        "wos": wos,
        "reorder": reorder,
        "status": status,
        "tone": tone,
        "cost": int(product.cost),
        "age": age,
    }


def sheet(
    state,
    *,
    department: str = "",
    vendor: str = "",
    region: str = "",
    store: str = "",
    place: str = "",
    query: str = "",
) -> dict:
    """Rows for the piles the company can count, plus the totals for those rows."""
    rows = []
    warehouse = _warehouse_label(state)
    day = int(getattr(state, "day", 1) or 1)
    reserved, inbound = _reservations(state)
    needle = (query or "").strip().lower()
    for product in state.products.values():
        if needle and needle not in product.name.lower() and needle not in str(product.id).lower():
            continue
        demand = _demand(state, product.id)
        line = state.stock.get(product.id)
        hand = int(getattr(line, "on_hand", 0) or 0) if line is not None else 0
        ordered = int(getattr(line, "on_order", 0) or 0) if line is not None else 0
        age = int(getattr(line, "age_days", 0) or 0) if line is not None else 0
        on_truck = int(reserved.get(product.id, 0) or 0)
        rows.append(_row(
            product,
            place="warehouse",
            location=warehouse,
            region="",
            store="warehouse",
            on_hand=hand + on_truck,
            on_order=ordered,
            allocated=on_truck,
            age=age,
            weekly=demand,
        ))
        for door in getattr(state, "doors", None) or []:
            held = door.stock.get(product.id)
            if held is None:
                continue
            coming = int((inbound.get(door.id) or {}).get(product.id, 0) or 0)
            rows.append(_row(
                product,
                place="store",
                location=door.city,
                region=str(getattr(door, "region", "") or ""),
                store=door.id,
                on_hand=int(getattr(held, "on_hand", 0) or 0),
                on_order=int(getattr(held, "on_order", 0) or 0) + coming,
                allocated=0,
                age=int(getattr(held, "age_days", 0) or 0),
                weekly=_door_weekly(door, product.id, day),
            ))
    if department:
        rows = [row for row in rows if row["department"] == department]
    if vendor:
        rows = [row for row in rows if row["vendor_id"] == vendor]
    if region:
        rows = [row for row in rows if row["region"] == region]
    if store:
        rows = [row for row in rows if row["store"] == store]
    if place == "warehouse":
        rows = [row for row in rows if row["place"] == "warehouse"]
    elif place == "stores":
        rows = [row for row in rows if row["place"] == "store"]
    rows.sort(key=lambda row: (row["product"], 0 if row["place"] == "warehouse" else 1, row["location"]))
    units = sum(row["on_hand"] for row in rows)
    value = sum(row["on_hand"] * row["cost"] for row in rows)
    sold = 0
    seen = set()
    for row in rows:
        if row["sku"] in seen:
            continue
        seen.add(row["sku"])
        sold += _demand(state, row["sku"])
    wos = None if sold <= 0 else round(units / sold, 1)
    return {
        "rows": rows,
        "units": units,
        "value": value,
        "wos": wos,
        "stockouts": sum(1 for row in rows if row["status"] == "Out"),
        "overstock": sum(1 for row in rows if row["status"] == "Overstock"),
        "shrink": _shrink(state),
    }
