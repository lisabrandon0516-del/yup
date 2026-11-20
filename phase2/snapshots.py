"""Read-only figures for the Phase 2 desks. Money is already in dollars."""

from __future__ import annotations


def money(value: int | float) -> str:
    return f"${int(value or 0):,}"


def _supplier_name(supplier_id: str) -> str:
    from open_late.content import SUPPLIERS

    house = SUPPLIERS.get(supplier_id)
    return house.name if house is not None else (supplier_id or "—")


def _door_city(state, door_id: str) -> str:
    for door in getattr(state, "doors", []) or []:
        if door.id == door_id:
            return door.city
    return door_id or "the warehouse"


def _price_position(index: int) -> str:
    if index < 98:
        return "Below the shelf"
    if index > 102:
        return "Above the shelf"
    return "Even with the shelf"


def _threat(open_stores: int, activity: str) -> str:
    text = (activity or "").lower()
    if "price war" in text or "bankrupt" in text:
        return "High"
    if open_stores >= 3 or "opened" in text:
        return "Watch"
    return "Low"


def ordering_snapshot(state) -> dict:
    today = int(getattr(state, "day", 0) or 0)
    rows = []
    for order in list(getattr(state, "orders", []) or []):
        arrives = int(getattr(order, "arrives_on", 0) or 0)
        if arrives < today:
            status = "Late"
        elif arrives == today:
            status = "Pending"
        else:
            status = "Submitted"
        goods = int(getattr(order, "cost", 0) or 0)
        freight = int(getattr(order, "freight", 0) or 0)
        rows.append({
            "id": str(getattr(order, "id", "PO")),
            "vendor": _supplier_name(str(getattr(order, "supplier_id", "") or "")),
            "placed": int(getattr(order, "placed_on", 0) or 0),
            "arrival": arrives,
            "cost": goods + freight,
            "status": status,
        })
    for shipment in list(getattr(state, "shipments", []) or []):
        arrives = int(getattr(shipment, "arrives_on", 0) or 0)
        departs = int(getattr(shipment, "departs_on", 0) or 0)
        if arrives < today:
            status = "Late"
        elif arrives == today:
            status = "Due today"
        elif departs <= today:
            status = "In transit"
        else:
            status = "Scheduled"
        city = _door_city(state, str(getattr(shipment, "door_id", "") or ""))
        rows.append({
            "id": str(getattr(shipment, "id", "truck")),
            "vendor": f"Truck to {city}",
            "placed": departs,
            "arrival": arrives,
            "cost": int(getattr(shipment, "freight", 0) or 0),
            "status": status,
        })
    notes = _ordering_notes(state, today)
    return {
        "rows": rows,
        "open": len(rows),
        "due": sum(row["status"] in ("Pending", "Due today") for row in rows),
        "late": sum(row["status"] == "Late" for row in rows),
        "cost": sum(row["cost"] for row in rows),
        "notes": notes,
    }


def _ordering_notes(state, today: int) -> list[str]:
    notes = [
        "A draft stays on the order ticket until you place it. Placed orders are submitted, then pending, then closed when the dock checks them in.",
    ]
    try:
        from open_late.ui.inventory_sheet import sheet

        piles = sheet(state, place="warehouse")["rows"]
    except Exception:
        piles = []
    recommended = [row for row in piles if row.get("status") in ("Out", "Low")]
    if recommended:
        shown = recommended[:6]
        notes.append("Recommended from the warehouse and the last sales:")
        for row in shown:
            notes.append(f"{row['product']}: {row['status']}, {row['on_hand']} on hand, {row['on_order']} on order.")
        extra = len(recommended) - len(shown)
        if extra:
            notes.append(f"{extra} more lines are low or out.")
    else:
        notes.append("No warehouse line is low or out, so there is no recommended order.")
    for shipment in list(getattr(state, "shipments", []) or []):
        arrives = int(getattr(shipment, "arrives_on", 0) or 0)
        if arrives < today:
            city = _door_city(state, str(getattr(shipment, "door_id", "") or ""))
            notes.append(f"Late truck {shipment.id} to {city}. It was due on day {arrives}.")
    for account in list(getattr(state, "supplier_accounts", []) or []):
        name = _supplier_name(str(getattr(account, "supplier_id", "") or ""))
        terms = str(getattr(account, "terms", "cash") or "cash")
        if terms != "cash":
            notes.append(f"{name} changed the bill to {terms}. Freight is included. It is not due with the truck.")
        late = int(getattr(account, "late_payments", 0) or 0)
        if late:
            notes.append(f"{name} has {late} late payment{'s' if late != 1 else ''} on the account.")
    return notes


def customer_snapshot(state) -> dict:
    block = getattr(state, "shopperlife", None)
    homes = list(getattr(block, "households", []) or []) if block is not None else []
    if homes:
        return _shopperlife_snapshot(state, block, homes)
    rows = []
    for person in list(getattr(state, "regulars", []) or []):
        if not getattr(person, "introduced", False) and not getattr(person, "active", False):
            continue
        rows.append({
            "household": getattr(person, "name", "Regular"),
            "place": "This company",
            "needs": "—",
            "trips": int(getattr(person, "visits", 0) or 0),
            "stage": "Active" if getattr(person, "active", False) else "Quiet",
            "why": getattr(person, "blurb", "") or "A regular on the book. ShopperLife households are not turned on.",
        })
    return {
        "rows": rows,
        "households": 0,
        "at_risk": 0,
        "lapsed": 0,
        "primary": 0,
        "wallet": "—",
        "trips": "—",
        "basket": "—",
        "notes": ["ShopperLife is off, so this desk shows regulars. Household needs, trips, and memory appear when ShopperLife is on."],
        "source": "regulars",
    }


def _shopperlife_snapshot(state, block, homes) -> dict:
    from open_late.shopperlife.inspector import explain_household, intelligence_summary

    summary = intelligence_summary(block)
    rows = []
    for home in homes:
        detail = explain_household(block, home.id)
        player = home.retailer_relationships.get("player")
        stage = player.stage if player is not None else (detail.get("stages") or {}).get("player", "unaware")
        needs = ", ".join(detail.get("needs") or []) or "—"
        why = ", ".join(detail.get("causes") or []) or (detail.get("mission_type") or "No cause recorded")
        trips = int(player.trips) if player is not None else 0
        rows.append({
            "household": home.id,
            "place": str(getattr(home, "region_id", "") or "—"),
            "needs": needs,
            "trips": trips,
            "stage": str(stage).replace("_", " "),
            "why": why,
        })
    def pct(value: float) -> str:
        return f"{round(float(value) * 100)}%"

    notes = [
        f"{summary['households']} households on the book. {summary['primary']} call this company primary.",
        f"Share of wallet {pct(summary['wallet'])}. Share of trips {pct(summary['trips'])}. Basket completion {pct(summary['basket_completion'])}.",
        "Why is the cause on the household: a need, a trip, a basket, or a memory. It is not a hidden score.",
    ]
    gains = summary.get("gains") or {}
    losses = summary.get("losses") or {}
    for ident, count in sorted(losses.items()):
        if count:
            notes.append(f"{count} left {ident}.")
    for ident, count in sorted(gains.items()):
        if count:
            notes.append(f"{count} joined {ident}.")
    return {
        "rows": rows,
        "households": int(summary["households"]),
        "at_risk": int(summary["at_risk"]),
        "lapsed": int(summary["lapsed"]),
        "primary": int(summary["primary"]),
        "wallet": pct(summary["wallet"]),
        "trips": pct(summary["trips"]),
        "basket": pct(summary["basket_completion"]),
        "notes": notes,
        "source": "shopperlife",
    }


def rival_snapshot(state) -> dict:
    """What the company could already see. No cash, no debt, no private plan."""
    rows = []
    notes = ["Confidence is Confirmed, Estimated, Rumored, or Unknown. A blank is Unknown, not a guess."]
    try:
        from open_late.rival_ai import rival_snapshot as public_snapshot

        public = public_snapshot(state) if state is not None else {}
    except Exception:
        public = {}
    for chain in public.get("chains") or []:
        activity = str(chain.get("last_move") or "")
        doctrine = str(chain.get("doctrine") or "")
        if activity:
            confidence = "Confirmed"
        elif doctrine:
            confidence = "Estimated"
        else:
            confidence = "Unknown"
        rows.append({
            "name": chain.get("name") or "Rival",
            "doctrine": doctrine or "—",
            "threat": _threat(int(chain.get("open_stores") or 0), activity),
            "price": _price_position(int(chain.get("price_index") or 100)),
            "activity": activity or "No public move on the tape.",
            "confidence": confidence,
        })
    if not rows:
        rival = getattr(state, "rival", None)
        if rival is not None:
            note = str(getattr(rival, "note", "") or "")
            rows.append({
                "name": getattr(rival, "name", "Rival"),
                "doctrine": str(getattr(rival, "focus", "") or "—"),
                "threat": "Low",
                "price": _price_position(int(getattr(rival, "price_index", 100) or 100)),
                "activity": note or "Nothing confirmed.",
                "confidence": "Estimated" if note else "Unknown",
            })
            notes.append("Living Market is off. This card is the rival on the lease, not an internal plan.")
    else:
        notes.append("Doctrine and price position are estimates from what is posted. A move on the tape is confirmed.")
    return {"rows": rows, "active": len(rows), "notes": notes}


def operations_snapshot(state) -> dict:
    today = int(getattr(state, "day", 0) or 0)
    phase = str(getattr(state, "phase", "morning") or "morning")
    staff = list(getattr(state, "staff", []) or [])
    shipments = list(getattr(state, "shipments", []) or [])
    rows = []
    for door in list(getattr(state, "doors", []) or []):
        open_now = getattr(door, "status", "") == "open" and int(getattr(door, "opens_on", 0) or 0) <= today
        crew = [person for person in staff if getattr(person, "employed", False) and getattr(person, "door_id", "") == door.id]
        due = sum(1 for item in shipments if getattr(item, "door_id", None) == door.id and int(getattr(item, "arrives_on", 0) or 0) == today)
        if not open_now:
            status = "Build-out"
        elif not crew:
            status = "Needs a crew"
        else:
            status = "Ready"
        rows.append({
            "store": getattr(door, "city", getattr(door, "id", "Store")),
            "open": int(getattr(door, "open_hour", 0) or 0),
            "close": int(getattr(door, "close_hour", 0) or 0),
            "staffing": len(crew),
            "deliveries": due,
            "status": status,
        })
    report = getattr(state, "last_report", None)
    live = phase == "desk"
    notes = []
    if live:
        visits = int(getattr(report, "visits", 0) or 0) if report is not None else 0
        sales = int(getattr(report, "revenue", 0) or 0) if report is not None else 0
        stockouts = len(getattr(report, "stockout_ids", []) or []) if report is not None else 0
        incident = bool(getattr(report, "incident", False)) if report is not None else False
        trucks = sum(1 for item in shipments if int(getattr(item, "departs_on", 0) or 0) <= today <= int(getattr(item, "arrives_on", 0) or 0))
        labor = sum(row["staffing"] for row in rows)
        notes.append("The floor is open. Today's tape posts when the day closes. The last closed tape is below.")
        notes.append(f"Customers on the last tape: {visits:,}.")
        notes.append(f"Sales on the last tape: {money(sales)}.")
        notes.append(f"Registers follow the tills on POS. Crew on the doors: {labor}.")
        notes.append(f"Stockouts on the last tape: {stockouts}. Trucks on the road: {trucks}.")
        notes.append("Incident on the last tape." if incident else "No incident on the last tape.")
    else:
        notes.append("The doors are not open yet. Readiness is the crew, the trucks due today, and whether the store can sell.")
        notes.append("Open the Floor to move from this plan to the live board.")
    return {
        "rows": rows,
        "open": sum(row["status"] == "Ready" for row in rows),
        "exceptions": sum(row["status"] != "Ready" for row in rows),
        "live": live,
        "notes": notes,
    }


def marketing_snapshot(state) -> dict:
    campaign = getattr(state, "campaign", None)
    rows = []
    spend = int(getattr(state, "quarter_ads", 0) or 0) or int(getattr(state, "spent_advertising", 0) or 0)
    if campaign is not None and int(getattr(campaign, "days_left", 0) or 0) > 0:
        lift = float(getattr(campaign, "traffic_mult", 1.0) or 1.0)
        audience = str(getattr(campaign, "category", "") or "all shoppers").replace("_", " ")
        rows.append({
            "name": str(getattr(campaign, "kind", "Campaign")).replace("_", " "),
            "channel": str(getattr(campaign, "kind", "—")).replace("_", " "),
            "audience": audience,
            "spend": spend,
            "status": f"{int(campaign.days_left)} days left",
            "lift": f"{lift:.2f}× traffic",
        })
        notes = [
            f"This campaign is aimed at {audience}. The result is the traffic multiple written onto shopper perception, not a separate sales bonus.",
            "Target a behavior from the customer desk: value, premium, at risk, lapsed, or a rival's customers. This running campaign stores the category it was bought for.",
        ]
    else:
        notes = [
            "No campaign is running. Spend, reach, and lift stay on this desk once an ad is on the book.",
            "A campaign should name who it is for: value, premium, at risk, lapsed, or a rival's customers.",
        ]
    return {
        "rows": rows,
        "active": len(rows),
        "spend": spend,
        "lift": rows[0]["lift"] if rows else "—",
        "notes": notes,
    }
