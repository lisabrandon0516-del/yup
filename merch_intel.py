"""One row and one brief for the merchandising command center."""

from __future__ import annotations

from open_late.content import SUPPLIERS
from open_late.text import money

STATUS_COLOR = {
    "problem": "#C24141",
    "watch": "#C2410C",
}


def status_of(on_hand: int, on_order: int, age_days: int) -> tuple[str, str]:
    """Neutral while the item is fine. Color only when the shelf needs a person."""
    if int(on_hand) <= 0 and int(on_order) <= 0:
        return "Out", "problem"
    if int(on_hand) <= 0:
        return "On order", "watch"
    if int(age_days) >= 21:
        return "Aging", "watch"
    if int(on_hand) <= 2:
        return "Low", "watch"
    return "In stock", ""


def _shelf(state, product) -> tuple[int, int, int, int, str]:
    """Units on hand, units on order, age, doors carrying it, and where it sits."""
    warehouse = state.stock.get(product.id)
    warehouse_hand = int(getattr(warehouse, "on_hand", 0) or 0) if warehouse is not None else 0
    on_order = int(getattr(warehouse, "on_order", 0) or 0) if warehouse is not None else 0
    age = int(getattr(warehouse, "age_days", 0) or 0) if warehouse is not None else 0
    doors = 0
    door_hand = 0
    for door in state.doors:
        line = door.stock.get(product.id)
        held = int(getattr(line, "on_hand", 0) or 0) if line is not None else 0
        if held > 0:
            doors += 1
            door_hand += held
    door_word = "door" if doors == 1 else "doors"
    if doors and warehouse_hand > 0:
        where = f"Warehouse · {doors} {door_word}"
    elif doors:
        where = f"{doors} {door_word}"
    elif warehouse_hand > 0:
        where = "Warehouse"
    else:
        where = "None"
    return warehouse_hand + door_hand, on_order, age, doors, where


def line_for(state, product) -> dict:
    """The grid cells for one item."""
    on_hand, on_order, age, _doors, where = _shelf(state, product)
    status, tone = status_of(on_hand, on_order, age)
    cost = int(product.cost)
    price = int(product.price)
    margin = int(round((price - cost) * 100 / price)) if price else 0
    house = SUPPLIERS.get(product.supplier_id)
    return {
        "id": product.id,
        "tone": tone,
        "cells": [
            product.name,
            product.brand or "—",
            house.name if house is not None else product.supplier_id,
            money(cost),
            money(price),
            f"{margin}%",
            f"{on_hand:,}",
            where,
            status,
        ],
    }


def brief(state, product) -> str:
    """Supplier, rival position, preference, substitutes, and the shelf."""
    house = SUPPLIERS.get(product.supplier_id)
    supplier = house.name if house is not None else product.supplier_id
    lead = f"{house.lead_time_days} days" if house is not None else "—"
    index = int(getattr(getattr(state, "rival", None), "price_index", 0) or 0)
    if index:
        rival = f"No item price from a rival. Their shelf index is {index} against a normal 100."
    else:
        rival = "No rival price is on this item."
    others = [
        other.name
        for other in state.products.values()
        if other.id != product.id and other.category == product.category
    ]
    others.sort()
    substitutes = ", ".join(others[:3]) if others else "No other item in this category."
    on_hand, on_order, age, _doors, where = _shelf(state, product)
    life = int(product.shelf_life_days or 0)
    life_line = f"{life} days" if life else "No shelf life"
    return (
        f"Supplier  {supplier}\n"
        f"Lead time  {lead}\n"
        f"Rival price  {rival}\n"
        f"Preference  Quality {product.quality} of 5. Trend {product.trend}.\n"
        f"Substitutes  {substitutes}\n"
        f"Inventory  {on_hand:,} on hand at {where}, {on_order:,} on order, age {age} days. {life_line}."
    )


def tree_groups(products) -> list[tuple[str, str, list[tuple[str, str, int]]]]:
    """Department key, label, and the categories under it with a count."""
    from open_late.departments import DEPARTMENT_LABELS

    buckets: dict[str, dict[str, int]] = {}
    for product in products:
        dept = str(product.department or product.category or "other")
        cat = str(product.category or dept)
        buckets.setdefault(dept, {})
        buckets[dept][cat] = buckets[dept].get(cat, 0) + 1
    rows = []
    for dept in sorted(buckets):
        label = DEPARTMENT_LABELS.get(dept, dept.replace("_", " ").title())
        children = []
        for cat, count in sorted(buckets[dept].items()):
            if cat == dept:
                continue
            children.append((cat, cat.replace("_", " ").title(), count))
        rows.append((dept, label, children))
    return rows
