"""Desks wired to the live company. They do not replace Overview, Stores, Planograms, Inventory, or Merchandising."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel

from open_late.ui.components import label
from open_late.ui.components.core import MUTED
from open_late.ui.pages.modules import CustomersPage, MarketingPage, OperationsPage, OrderingPage, RivalsPage
from .snapshots import customer_snapshot, marketing_snapshot, money, operations_snapshot, ordering_snapshot, rival_snapshot


def _fill_notes(page, lines: list[str]) -> None:
    body = page.insight.body
    while body.count():
        item = body.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
    if not lines:
        body.addWidget(label("Nothing new on this desk.", 12, color=MUTED, wrap=True))
        return
    for text in lines:
        line = label(text, 12, wrap=True)
        line.setObjectName("deskNote")
        body.addWidget(line)


class OrderingPage2(OrderingPage):
    title = "Ordering"
    deck = "Purchase orders from draft through closed, recommended orders, and supplier trouble written as business facts."

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("orderingDesk")

    def refresh(self):
        if self._state is None:
            return
        snap = ordering_snapshot(self._state)
        self.table.set_rows([
            (row["id"], row["vendor"], f"Day {row['placed']}", f"Day {row['arrival']}", money(row["cost"]), row["status"])
            for row in snap["rows"]
        ])
        self.set_kpi(0, str(snap["open"]), "on the book")
        self.set_kpi(1, money(snap["cost"]), "goods, freight, and truck cost")
        self.set_kpi(2, str(snap["due"]), "arriving today", "warning" if snap["due"] else "neutral")
        self.set_kpi(3, str(snap["late"]), "past arrival", "bad" if snap["late"] else "good")
        _fill_notes(self, snap["notes"])


class CustomersPage2(CustomersPage):
    title = "Customers"
    deck = "ShopperLife. Households, why a figure moved, and the needs, trips, baskets, and memory behind it."
    columns = ("Household", "Place", "Needs", "Trips", "Stage", "Why")
    kpis = ("Households", "Primary", "At risk", "Lapsed")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("customersDesk")

    def refresh(self):
        if self._state is None:
            return
        snap = customer_snapshot(self._state)
        self.table.set_rows([
            (row["household"], row["place"], row["needs"], row["trips"], row["stage"], row["why"])
            for row in snap["rows"]
        ])
        self.set_kpi(0, str(snap["households"]) if snap["source"] == "shopperlife" else str(len(snap["rows"])), snap["source"])
        self.set_kpi(1, str(snap["primary"]) if snap["source"] == "shopperlife" else "—", f"wallet {snap['wallet']}")
        self.set_kpi(2, str(snap["at_risk"]), f"trips {snap['trips']}", "bad" if snap["at_risk"] else "good")
        self.set_kpi(3, str(snap["lapsed"]), f"basket {snap['basket']}", "warning" if snap["lapsed"] else "neutral")
        _fill_notes(self, snap["notes"])


class MarketingPage2(MarketingPage):
    title = "Marketing"
    deck = "Spend, reach, response, lift, and who the campaign is for. Results land in shopper perception."

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("marketingDesk")

    def refresh(self):
        if self._state is None:
            return
        snap = marketing_snapshot(self._state)
        self.table.set_rows([
            (row["name"], row["channel"], row["audience"], money(row["spend"]), row["status"], row["lift"])
            for row in snap["rows"]
        ])
        self.set_kpi(0, str(snap["active"]), "running now", "good" if snap["active"] else "neutral")
        self.set_kpi(1, money(snap["spend"]), "advertising this quarter")
        self.set_kpi(2, snap["lift"], "traffic multiple on the campaign")
        self.set_kpi(3, "—", "perception updates with the campaign")
        _fill_notes(self, snap["notes"])


class RivalsPage2(RivalsPage):
    title = "Rivals"
    deck = "Market intelligence. Doctrine, threat, price position, and only what you can see."
    columns = ("Company", "Doctrine", "Threat", "Price position", "Visible activity", "Confidence")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("rivalsDesk")

    def refresh(self):
        if self._state is None:
            return
        snap = rival_snapshot(self._state)
        self.table.set_rows([
            (row["name"], row["doctrine"], row["threat"], row["price"], row["activity"], row["confidence"])
            for row in snap["rows"]
        ])
        confirmed = sum(row["confidence"] == "Confirmed" for row in snap["rows"])
        self.set_kpi(0, str(snap["active"]), "on the tape")
        self.set_kpi(1, str(sum(row["threat"] == "High" for row in snap["rows"])), "high threat")
        self.set_kpi(2, str(confirmed), "confirmed moves")
        self.set_kpi(3, "Public", "no hidden rival logic", "info")
        _fill_notes(self, snap["notes"])


class OperationsPage2(OperationsPage):
    title = "Daily Operations"
    deck = "Readiness before the doors open. After Open the Floor, the last tape and what is still moving."
    columns = ("Store", "Open", "Close", "Staffing", "Deliveries", "Readiness")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("operationsDesk")

    def refresh(self):
        if self._state is None:
            return
        snap = operations_snapshot(self._state)
        self.table.set_rows([
            (row["store"], f"{row['open']}:00", f"{row['close']}:00", row["staffing"], row["deliveries"], row["status"])
            for row in snap["rows"]
        ])
        self.set_kpi(0, str(snap["open"]), "ready to sell", "good" if snap["open"] else "warning")
        self.set_kpi(1, "Live" if snap["live"] else "Planning", "floor" if snap["live"] else "before open")
        self.set_kpi(2, str(snap["exceptions"]), "not ready", "warning" if snap["exceptions"] else "good")
        self.set_kpi(3, str(sum(row["deliveries"] for row in snap["rows"])), "trucks due today")
        _fill_notes(self, snap["notes"])


PHASE2_PAGE_CLASSES = {
    "orders": OrderingPage2,
    "customers": CustomersPage2,
    "marketing": MarketingPage2,
    "market": RivalsPage2,
    "settings": OperationsPage2,
}

# Kept so a label import in older overlays still resolves.
_ = QLabel
