"""Read-only records. Dollars stay dollars. Rival cash stays off this desk."""

from __future__ import annotations

from typing import Any

from open_late.text import money


def inventory_item(state, sku: str) -> dict[str, Any]:
    product = (getattr(state, "products", {}) or {}).get(sku)
    rows = []
    try:
        from open_late.ui.inventory_sheet import sheet

        rows = [row for row in sheet(state, query=sku)["rows"] if row["sku"] == sku]
    except Exception:
        rows = []
    from open_late.content import SUPPLIERS

    house = SUPPLIERS.get(getattr(product, "supplier_id", "")) if product is not None else None
    return {
        "kind": "Inventory item",
        "id": sku,
        "title": getattr(product, "name", sku),
        "summary": {
            "SKU": sku,
            "Department": getattr(product, "department", "—") or "—",
            "Supplier": house.name if house is not None else getattr(product, "supplier_id", "—"),
            "Price": money(getattr(product, "price", 0) or 0),
            "Cost": money(getattr(product, "cost", 0) or 0),
        },
        "sections": {
            "Stock by location": [
                {
                    "Location": row["location"],
                    "On hand": row["on_hand"],
                    "Available": row["available"],
                    "Status": row["status"],
                }
                for row in rows
            ],
        },
    }


def store(state, store_id: str) -> dict[str, Any]:
    door = next((item for item in getattr(state, "doors", []) or [] if item.id == store_id), None)
    address = ""
    pos_name = "—"
    pnl: dict[str, Any] = {}
    departments = []
    try:
        from open_late.ui.hq_adapter import department_week_compare, display_address, store_pnl, store_pos

        address = display_address(door)
        pos_name = (store_pos(state, store_id) or {}).get("name", "—")
        raw = store_pnl(state, store_id, days=7) or {}
        pnl = {
            "Sales": money(raw.get("sales", 0)),
            "Cost of goods": money(raw.get("cogs", 0)),
            "Labor": money(raw.get("labor", 0)),
            "Rent": money(raw.get("rent", 0)),
            "Contribution": money(raw.get("contribution", 0)),
        }
        for ident, row in (department_week_compare(state, store_id) or {}).items():
            departments.append({
                "Department": str(ident).replace("_", " ").title(),
                "This week": money(row.get("sales", 0)),
                "Prior week": money(row.get("prior", 0)) if row.get("has_prior") else "—",
            })
    except Exception:
        pass
    return {
        "kind": "Store",
        "id": store_id,
        "title": getattr(door, "city", store_id),
        "summary": {
            "Location": address or "—",
            "Status": getattr(door, "status", "—"),
            "Hours": f"{getattr(door, 'open_hour', '—')}:00–{getattr(door, 'close_hour', '—')}:00",
            "POS": pos_name,
        },
        "sections": {"Last 7 days": pnl, "Departments": departments},
    }


def supplier(state, supplier_id: str) -> dict[str, Any]:
    from open_late.content import SUPPLIERS

    house = SUPPLIERS.get(supplier_id)
    account = next((item for item in getattr(state, "supplier_accounts", []) or [] if item.supplier_id == supplier_id), None)
    products = [item for item in (getattr(state, "products", {}) or {}).values() if item.supplier_id == supplier_id]
    orders = [item for item in getattr(state, "orders", []) or [] if item.supplier_id == supplier_id]
    return {
        "kind": "Supplier",
        "id": supplier_id,
        "title": house.name if house is not None else supplier_id.replace("_", " ").title(),
        "summary": {
            "Products": len(products),
            "Open orders": len(orders),
            "Terms": getattr(account, "terms", "cash") if account is not None else "cash",
            "Minimum": money(getattr(house, "minimum_order", 0) or 0) if house is not None else "—",
            "Lead time": f"{getattr(house, 'lead_time_days', '—')} days" if house is not None else "—",
        },
        "sections": {
            "Products": [{"Item": item.name, "Cost": money(item.cost)} for item in products[:12]],
            "Purchase orders": [
                {"Order": item.id, "Arrives": f"Day {item.arrives_on}", "Cost": money(int(item.cost or 0) + int(item.freight or 0))}
                for item in orders
            ],
        },
    }


def employee(state, person_id: str) -> dict[str, Any]:
    person = next((item for item in getattr(state, "staff", []) or [] if item.id == person_id), None)
    if person is None:
        return {"kind": "Employee", "id": person_id, "title": person_id, "summary": {}, "sections": {}}
    doors = {door.id: door.city for door in getattr(state, "doors", []) or []}
    return {
        "kind": "Employee",
        "id": person.id,
        "title": person.name,
        "summary": {
            "Assignment": person.assignment,
            "Wage": money(person.wage),
            "Door": doors.get(person.door_id, "—"),
            "Status": "On payroll" if person.employed else "Off the sheet",
            "Mood": person.mood,
            "Loyalty": person.loyalty,
            "YTD gross": money(person.ytd_gross),
            "YTD net": money(person.ytd_net),
        },
        "sections": {},
    }


def customer_segment(state, segment_id: str) -> dict[str, Any]:
    block = getattr(state, "shopperlife", None)
    homes = list(getattr(block, "households", []) or []) if block is not None else []
    home = next((item for item in homes if item.id == segment_id), None)
    if home is not None:
        from open_late.shopperlife.inspector import explain_household

        detail = explain_household(block, home.id)
        player = home.retailer_relationships.get("player")
        stage = player.stage if player is not None else (detail.get("stages") or {}).get("player", "unaware")
        return {
            "kind": "Household",
            "id": home.id,
            "title": home.id,
            "summary": {
                "Place": str(getattr(home, "region_id", "") or "—"),
                "Needs": ", ".join(detail.get("needs") or []) or "—",
                "Trips": int(player.trips) if player is not None else 0,
                "Stage": str(stage).replace("_", " "),
                "Why": ", ".join(detail.get("causes") or []) or (detail.get("mission_type") or "No cause recorded"),
            },
            "sections": {},
        }
    person = next((item for item in getattr(state, "regulars", []) or [] if item.id == segment_id or item.name == segment_id), None)
    if person is None:
        return {"kind": "Household", "id": segment_id, "title": segment_id, "summary": {"Note": "ShopperLife is off."}, "sections": {}}
    return {
        "kind": "Regular",
        "id": person.id,
        "title": person.name,
        "summary": {
            "Trips": person.visits,
            "Stage": "Active" if person.active else "Quiet",
            "Why": person.blurb or "A regular on the book. ShopperLife households are not turned on.",
        },
        "sections": {},
    }


def rival(state, rival_id: str) -> dict[str, Any]:
    """Public tape only. Cash, debt, and internal plans are not on this card."""
    try:
        from open_late.rival_ai import rival_snapshot

        public = rival_snapshot(state) if state is not None else {}
    except Exception:
        public = {}
    chain = next((item for item in public.get("chains") or [] if item.get("id") == rival_id or item.get("name") == rival_id), None)
    if chain is not None:
        low = int(chain.get("sales_low") or 0)
        high = int(chain.get("sales_high") or 0)
        band = f"{money(low)}–{money(high)}" if high else "—"
        return {
            "kind": "Rival",
            "id": str(chain.get("id") or rival_id),
            "title": chain.get("name") or rival_id,
            "summary": {
                "Doctrine": chain.get("doctrine") or "—",
                "Price index": chain.get("price_index", "—"),
                "Open stores": chain.get("open_stores", 0),
                "Posted sales band": band,
                "Visible activity": chain.get("last_move") or "No public move on the tape.",
            },
            "sections": {},
        }
    other = getattr(state, "rival", None)
    if other is not None and (other.name == rival_id or rival_id == "rival"):
        return {
            "kind": "Rival",
            "id": other.name,
            "title": other.name,
            "summary": {
                "Focus": other.focus,
                "Price index": other.price_index,
                "Visible activity": other.note or "Nothing confirmed.",
                "Distance": f"{other.blocks_away} blocks",
            },
            "sections": {},
        }
    return {"kind": "Rival", "id": rival_id, "title": rival_id, "summary": {"Visible activity": "Nothing confirmed."}, "sections": {}}


INSPECTORS = {
    "inventory_item": inventory_item,
    "store": store,
    "supplier": supplier,
    "employee": employee,
    "customer_segment": customer_segment,
    "rival": rival,
}


def inspect(state, kind: str, entity_id: str) -> dict[str, Any]:
    if state is None:
        return {"kind": kind, "id": entity_id, "title": entity_id, "summary": {}, "sections": {}}
    func = INSPECTORS.get(kind)
    if func is None:
        return {"kind": kind, "id": entity_id, "title": entity_id, "summary": {}, "sections": {}}
    return func(state, entity_id)
