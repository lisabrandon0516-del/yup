"""Which row opens which record. The cell text is a name; the inspector needs an id."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EntityRef:
    kind: str
    entity_id: str


_KINDS = {
    "inventory": "inventory_item",
    "orders": "supplier",
    "customers": "customer_segment",
    "market": "rival",
    "staff": "employee",
    "settings": "store",
    "stores": "store",
}


def infer(page_id: str, headers: list[str], values: list[str], state=None) -> EntityRef | None:
    kind = _KINDS.get(page_id)
    if kind is None or not values or state is None:
        return None
    if kind == "supplier":
        return _supplier(values, state)
    if kind == "employee":
        return _by_name(values[0], getattr(state, "staff", []), "employee")
    if kind == "store":
        return _store(values[0], state)
    if kind == "rival":
        return _rival(values[0], state)
    if kind == "customer_segment":
        return _customer(values[0], state)
    if kind == "inventory_item":
        return _product(values, state)
    return None


def _supplier(values: list[str], state) -> EntityRef | None:
    from open_late.content import SUPPLIERS

    name = values[1] if len(values) > 1 else values[0]
    if not name or name.lower().startswith("truck"):
        return None
    for supplier_id, house in SUPPLIERS.items():
        if house.name == name or supplier_id == name:
            return EntityRef("supplier", supplier_id)
    return None


def _by_name(label: str, people, kind: str) -> EntityRef | None:
    for person in people or []:
        if getattr(person, "name", "") == label or getattr(person, "id", "") == label:
            return EntityRef(kind, person.id)
    return None


def _store(label: str, state) -> EntityRef | None:
    for door in getattr(state, "doors", []) or []:
        if door.city == label or door.id == label or label.startswith(door.city):
            return EntityRef("store", door.id)
    return None


def _rival(label: str, state) -> EntityRef | None:
    try:
        from open_late.rival_ai import rival_snapshot

        for chain in (rival_snapshot(state) or {}).get("chains") or []:
            if chain.get("name") == label or chain.get("id") == label:
                return EntityRef("rival", str(chain["id"]))
    except Exception:
        pass
    rival = getattr(state, "rival", None)
    if rival is not None and (rival.name == label or label == "rival"):
        return EntityRef("rival", rival.name)
    return None


def _customer(label: str, state) -> EntityRef | None:
    if not label or label == "—":
        return None
    block = getattr(state, "shopperlife", None)
    for home in list(getattr(block, "households", []) or []) if block is not None else []:
        if home.id == label or getattr(home, "name", "") == label:
            return EntityRef("customer_segment", home.id)
    for person in getattr(state, "regulars", []) or []:
        if person.name == label or person.id == label:
            return EntityRef("customer_segment", person.id)
    return EntityRef("customer_segment", label)


def _product(values: list[str], state) -> EntityRef | None:
    products = getattr(state, "products", {}) or {}
    for cell in values:
        if cell in products:
            return EntityRef("inventory_item", cell)
    for cell in values:
        for product in products.values():
            if product.name == cell:
                return EntityRef("inventory_item", product.id)
    return None
