"""Phase 0 contract. What the company may be read for, and what stays off the save."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from types import SimpleNamespace

from open_late.visiondeck.observations import collect_observations
from open_late.visiondeck.recommendations import ACTIONS as ACTIONS

SCHEMA = (
    "id",
    "day",
    "source_type",
    "source_id",
    "region",
    "store_id",
    "category",
    "metric",
    "observed_value",
    "previous_value",
    "visibility",
    "reliability",
    "freshness",
    "metadata",
)

# Phrases that belong to a rival's private plan. A reading must not carry them.
HIDDEN = (
    "margin is under the plan",
    "cash endurance",
    "no rule fired",
    "four weeks of costs",
    "credit line",
    "opening cooldown",
    "board's cooldown",
)

SAVE = (
    "Observations, alerts, forecasts, and hypotheses are computed. They are not fields on the save.",
    "A player choice is written on the existing decisions list, and only when the player acts.",
    "A visiondeck blob is not part of this phase.",
)


@dataclass(frozen=True)
class Source:
    name: str
    state: str
    reader: str
    metrics: tuple[str, ...]


SOURCES = (
    Source("sales", "last_report", "sales_adapter", ("revenue", "units", "visits", "category_sales")),
    Source("inventory", "doors.stock and stock", "inventory_adapter", ("on_hand", "lost_stockout")),
    Source("pricing", "products", "pricing_adapter", ("price",)),
    Source("customer", "last_report and regulars", "customer_adapter", ("visits", "lost_price", "regulars")),
    Source("supplier", "orders, shipments, supplier_accounts", "supplier_adapter", ("late_order", "late_shipment", "late_payments")),
    Source("finance", "cash, credit_used, credit_limit", "finance_adapter", ("cash", "obligations", "credit_left")),
    Source("workforce", "doors and store_days", "workforce_adapter", ("labor", "labor_overtime", "noshow")),
    Source("rival", "rival_snapshot public feed", "rival_adapter", ("public_move",)),
)


@dataclass(frozen=True)
class Flags:
    """Writes stay off. Reading the company does not need a flag."""

    commit_actions: bool = False
    persist_blob: bool = False


FLAGS = Flags()


def read_company(state):
    """The observations the company is allowed to see. The company is not changed."""
    return collect_observations(state)


def action_callables() -> dict:
    """The registry resolved to the engine functions. Doing nothing has none."""
    found = {}
    for name, path in ACTIONS.items():
        if not path:
            found[name] = None
            continue
        module_name, func = path.rsplit(".", 1)
        found[name] = getattr(importlib.import_module(module_name), func)
    return found


def _report(day: int, lost: int):
    return SimpleNamespace(
        day=day - 1,
        revenue=120,
        units=4,
        visits=3,
        by_category={"grocery": 80},
        gross_profit=40,
        lost_price=0,
        lost_walk=0,
        lost_staff=0,
        labor_hours=0,
        labor_overtime=0,
        noshow_ids=[],
        lost_stockout=lost,
        lost_stockout_by_category={"grocery": lost} if lost else {},
    )


def _company(on_hand: int, lost: int):
    products = {"milk": SimpleNamespace(id="milk", name="Milk", category="grocery", price=4, cost=2)}
    door = SimpleNamespace(
        id="houston",
        city="Houston",
        region="south",
        labor_budget=2400,
        stock={"milk": SimpleNamespace(product_id="milk", on_hand=on_hand)},
    )
    return SimpleNamespace(
        day=4,
        cash=5000,
        credit_limit=8000,
        credit_used=0,
        doors=[door],
        products=products,
        stock={},
        last_report=_report(4, lost),
        history=[],
        shipments=[],
        orders=[],
        supplier_accounts=[],
        store_days=[],
        staff=[],
        regulars=[],
        decisions=[],
    )


def quiet_company():
    return _company(8, 0)


def stockout_company():
    return _company(0, 6)
