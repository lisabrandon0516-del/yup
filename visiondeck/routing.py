"""Phase 10. An alert names the workstation that already owns the work.

The route is a desk the player already has. It does not copy that desk, and it
does not carry out the decision.
"""

from __future__ import annotations

# app id, command-center desk (empty when the destination is a real page), label
_ROUTES = {
    "stockout_pressure": ("inventory", "", "Inventory"),
    "supplier_delay": ("orders", "", "Purchasing"),
    "margin_compression": ("economy", "", "Economy"),
    "cash_pressure": ("economy", "", "Economy"),
    "debt_pressure": ("books", "", "Finance"),
    "competitor_price_pressure": ("visiondeck", "competitors", "Competitors"),
    "competitor_expansion": ("visiondeck", "competitors", "Competitors"),
    "customer_switching": ("customers", "", "Customers"),
    "labor_stress": ("stores", "", "Stores"),
    "traffic_decline": ("stores", "", "Stores"),
    "sales_decline": ("home", "", "Command board"),
    "sales_growth": ("home", "", "Command board"),
}


def route_for(alert) -> tuple[str, str, str]:
    """Return (app id, desk, label) for an alert. Unknown kinds use the command board."""
    kind = str(getattr(alert, "kind", "") or "")
    return _ROUTES.get(kind, ("home", "", "Command board"))
