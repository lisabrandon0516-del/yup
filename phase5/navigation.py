"""Drill targets. A page id is one the shell already knows how to open."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DrillTarget:
    page_id: str
    entity_id: str = ""
    tab: str = ""
    filters: dict[str, Any] = field(default_factory=dict)
    reason: str = ""


ROUTES = {
    "inventory_item": "inventory",
    "purchase_order": "orders",
    "department": "sales",
    "customer_segment": "customers",
    "rival": "market",
    "account": "books",
    "campaign": "marketing",
    "employee": "staff",
    "store": "stores",
    "message": "journal",
    "economy_factor": "economy",
    "pos": "pos",
}


def target(kind: str, entity_id: str = "", **kwargs) -> DrillTarget:
    return DrillTarget(
        ROUTES.get(kind, kind),
        entity_id,
        kwargs.get("tab", ""),
        dict(kwargs.get("filters") or {}),
        kwargs.get("reason", ""),
    )
