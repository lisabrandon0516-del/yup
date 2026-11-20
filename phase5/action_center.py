"""One list of what needs a person. The same event can name every desk it touches."""

from __future__ import annotations

from dataclasses import dataclass

from .navigation import DrillTarget, target
from .scope import Scope, keep_row

BANDS = ("Critical", "Action Required", "Opportunity", "Information")


@dataclass(frozen=True)
class ActionItem:
    id: str
    title: str
    band: str
    detail: str
    target: DrillTarget
    source: str = "system"
    confidence: str = "confirmed"


def build(state, scope: Scope | None = None) -> list[ActionItem]:
    if state is None:
        return []
    scope = scope or Scope()
    out: list[ActionItem] = []
    for message in list(getattr(state, "inbox", []) or []):
        if bool(getattr(message, "resolved", False)):
            continue
        title_text = str(getattr(message, "title", "Message"))
        kind = str(getattr(message, "kind", "information") or "information")
        body = str(getattr(message, "body", "") or "").strip()
        detail = body.split(".")[0].strip() or kind.replace("_", " ").title()
        if bool(getattr(message, "urgent", False)) or kind == "incident":
            band = "Critical"
        elif kind in ("bills", "quit", "delivery", "order") or any(word in title_text.lower() for word in ("bill", "ship", "truck", "order", "delivery")):
            band = "Action Required"
        elif any(word in title_text.lower() for word in ("offer", "deal", "lease", "opportunity")):
            band = "Opportunity"
        else:
            band = "Information"
        message_id = str(getattr(message, "id", title_text))
        for index, route in enumerate(_routes(message)):
            out.append(ActionItem(
                message_id if index == 0 else f"{message_id}:{route}",
                title_text,
                band,
                detail if index == 0 else f"Also on the {route.replace('_', ' ')} desk.",
                target(route, message_id if route != "inventory" else "", reason=title_text),
                "inbox",
            ))
    try:
        from open_late.ui.inventory_sheet import sheet

        snap = sheet(state)
        for row in snap["rows"]:
            if row["status"] not in ("Out", "Low", "Aging", "Overstock"):
                continue
            if not keep_row(row, scope):
                continue
            band = "Critical" if row["status"] == "Out" else "Action Required"
            confidence = "confirmed" if row["status"] == "Out" else "estimated"
            out.append(ActionItem(
                "inv:" + row["sku"] + ":" + row["location"],
                f"{row['product']} is {row['status'].lower()}",
                band,
                row["location"],
                target("inventory_item", row["sku"], filters={"query": row["sku"]}, reason=row["product"]),
                "inventory",
                confidence,
            ))
    except Exception:
        pass
    order = {name: index for index, name in enumerate(BANDS)}
    return sorted(out, key=lambda item: (order.get(item.band, 99), item.title))[:80]


def counts(items) -> dict[str, int]:
    return {band: sum(item.band == band for item in items) for band in BANDS}


def _routes(message) -> list[str]:
    kind = str(getattr(message, "kind", "") or "").lower()
    title = str(getattr(message, "title", "") or "").lower()
    routes: list[str] = []
    if getattr(message, "urgent", False) or kind == "incident":
        routes.append("staff" if kind == "quit" else "journal")
    elif kind == "quit":
        routes.append("staff")
    elif kind == "bills" or "bill" in title:
        routes.append("books")
    elif any(word in title or word in kind for word in ("offer", "deal", "lease")):
        routes.append("stores" if "lease" in title or kind == "lease" else "orders")
    elif any(word in title or word in kind for word in ("ship", "truck", "order", "delivery")):
        routes.append("orders")
        routes.append("inventory")
    else:
        routes.append("journal")
    if kind == "quit" and "journal" not in routes:
        routes.append("journal")
    if ("lease" in title or kind == "lease") and "stores" not in routes:
        routes.append("stores")
    seen: list[str] = []
    for route in routes:
        if route not in seen:
            seen.append(route)
    return seen
