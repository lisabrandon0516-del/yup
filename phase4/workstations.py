"""Command workstations for the desks that are still being brought up to the plan."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QInputDialog, QMessageBox

from open_late.text import money
from open_late.ui.components import label
from open_late.ui.components.core import MUTED
from open_late.ui.pages.base import ModulePage
from open_late.ui.phase2.pages import CustomersPage2, MarketingPage2, OperationsPage2, OrderingPage2, RivalsPage2
from open_late.ui.phase4.actions import WorkstationCommand
from open_late.ui.phase4.dialogs import ForecastDialog
from open_late.ui.phase4.forecast import campaign_forecast, order_forecast


class WorkstationMixin:
    command_requested = Signal(object)

    def request(self, command: WorkstationCommand, forecast=None):
        if forecast is not None and ForecastDialog(forecast, self).exec() != ForecastDialog.DialogCode.Accepted:
            return
        self.command_requested.emit(command)

    def notify_result(self, result) -> None:
        box = QMessageBox.information if result.ok else QMessageBox.warning
        box(self, "Workstation", result.message)


class OrderingWorkstation(WorkstationMixin, OrderingPage2):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.add_action("Build purchase order", self.build_order, True)

    def build_order(self) -> None:
        state = self._state
        if state is None:
            return
        from open_late.content import SUPPLIERS

        houses = []
        for supplier_id in sorted({product.supplier_id for product in state.products.values()}):
            house = SUPPLIERS.get(supplier_id)
            if house is not None:
                houses.append(house)
        if not houses:
            return
        names = [house.name for house in houses]
        shown, ok = QInputDialog.getItem(self, "Purchase order", "Supplier", names, 0, False)
        if not ok:
            return
        house = houses[names.index(shown)]
        products = [product for product in state.products.values() if product.supplier_id == house.id]
        products.sort(key=lambda product: product.name)
        item_names = [product.name for product in products]
        item, ok = QInputDialog.getItem(self, "Purchase order", "Item", item_names, 0, False)
        if not ok:
            return
        product = products[item_names.index(item)]
        qty, ok = QInputDialog.getInt(self, "Purchase order", "Quantity", max(1, int(product.case_size or 1)), 1, 100000)
        if not ok:
            return
        items = {product.id: int(qty)}
        self.request(
            WorkstationCommand(
                "place_order",
                {"supplier_id": house.id, "items": items},
                "Place purchase order",
                True,
                ("orders", "inventory", "books"),
            ),
            order_forecast(state, items),
        )


class MarketingWorkstation(WorkstationMixin, MarketingPage2):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.add_action("Launch campaign", self.launch, True)

    def launch(self) -> None:
        state = self._state
        if state is None:
            return
        from open_late.engine import CAMPAIGN_COST

        kinds = list(CAMPAIGN_COST)
        kind, ok = QInputDialog.getItem(self, "Campaign", "Kind", kinds, 0, False)
        if not ok:
            return
        tone, ok = QInputDialog.getItem(self, "Campaign", "Tone", ["discreet", "playful", "bold"], 0, False)
        if not ok:
            return
        categories = sorted({product.category for product in state.products.values()})
        category, ok = QInputDialog.getItem(self, "Campaign", "Category", categories, 0, False)
        if not ok:
            return
        staff_id = None
        if kind == "social":
            people = [person for person in state.staff if person.employed]
            if not people:
                QMessageBox.warning(self, "Campaign", "A social campaign needs someone on payroll.")
                return
            labels = [person.name for person in people]
            who, ok = QInputDialog.getItem(self, "Campaign", "Who posts", labels, 0, False)
            if not ok:
                return
            staff_id = people[labels.index(who)].id
        self.request(
            WorkstationCommand(
                "launch_campaign",
                {"kind": kind, "tone": tone, "category": category, "staff_id": staff_id},
                "Launch campaign",
                True,
                ("marketing", "customers", "books"),
            ),
            campaign_forecast(state, kind, category, CAMPAIGN_COST[kind]),
        )


class OperationsWorkstation(WorkstationMixin, OperationsPage2):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.add_action("Set store hours", self.change_hours, True)

    def change_hours(self) -> None:
        state = self._state
        if state is None:
            return
        doors = list(state.doors or [])
        if not doors:
            opening, ok = QInputDialog.getInt(self, "Store hours", "Open hour", int(state.open_hour), 8, 18)
            if not ok:
                return
            closing, ok = QInputDialog.getInt(self, "Store hours", "Close hour", int(state.close_hour), 9, 23)
            if ok:
                self.request(WorkstationCommand("set_hours", {"open_hour": opening, "close_hour": closing}, "Set hours", False, ("settings",)))
            return
        labels = [door.city for door in doors]
        shown, ok = QInputDialog.getItem(self, "Store hours", "Store", labels, 0, False)
        if not ok:
            return
        door = doors[labels.index(shown)]
        opening, ok = QInputDialog.getInt(self, "Store hours", "Open hour", int(door.open_hour), 8, 18)
        if not ok:
            return
        closing, ok = QInputDialog.getInt(self, "Store hours", "Close hour", int(door.close_hour), 9, 23)
        if not ok:
            return
        self.request(
            WorkstationCommand(
                "set_door_hours",
                {"door_id": door.id, "open_hour": opening, "close_hour": closing},
                "Set hours",
                False,
                ("settings",),
            )
        )


class CustomersWorkstation(WorkstationMixin, CustomersPage2):
    pass


class RivalsWorkstation(WorkstationMixin, RivalsPage2):
    pass


class StaffWorkstation(WorkstationMixin, ModulePage):
    title = "Staff"
    deck = "Roster, assignment, and weekly wage. A change goes through the payroll rules."
    columns = ("Employee", "Assignment", "Wage", "Door", "Status")
    kpis = ("Headcount", "On the floor", "Off", "Payroll")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("staffDesk")
        self.add_action("Change assignment", self.change_assignment, True)
        self.add_action("Delegation", self.open_delegation)

    def open_delegation(self) -> None:
        host = self.window()
        if host is not None and hasattr(host, "_open_app"):
            host._open_app("delegation")

    def refresh(self) -> None:
        if self._state is None:
            return
        people = [person for person in self._state.staff if person.employed]
        doors = {door.id: door.city for door in self._state.doors}
        rows = []
        payroll = 0
        floor = 0
        off = 0
        for person in people:
            payroll += int(person.wage or 0)
            if person.assignment == "off":
                off += 1
            elif person.assignment == "floor":
                floor += 1
            rows.append((
                person.name,
                person.assignment,
                money(person.wage),
                doors.get(person.door_id, "—"),
                "On payroll",
            ))
        self.table.set_rows(rows)
        self.set_kpi(0, str(len(people)), "on payroll")
        self.set_kpi(1, str(floor), "floor")
        self.set_kpi(2, str(off), "off")
        self.set_kpi(3, money(payroll), "weekly wages")
        body = self.insight.body
        while body.count():
            item = body.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        body.addWidget(label("Assignments are floor, fulfillment, modeling, private, event, training, or off.", 12, color=MUTED, wrap=True))

    def change_assignment(self) -> None:
        state = self._state
        if state is None:
            return
        people = [person for person in state.staff if person.employed]
        if not people:
            return
        from open_late.engine import ASSIGNMENTS

        labels = [person.name for person in people]
        shown, ok = QInputDialog.getItem(self, "Assignment", "Employee", labels, 0, False)
        if not ok:
            return
        person = people[labels.index(shown)]
        assignment, ok = QInputDialog.getItem(self, "Assignment", "Work area", list(ASSIGNMENTS), 0, False)
        if not ok:
            return
        self.request(
            WorkstationCommand(
                "set_assignment",
                {"person_id": person.id, "assignment": assignment},
                "Change assignment",
                False,
                ("staff", "settings"),
            )
        )


PHASE4_PAGE_CLASSES = {
    "orders": OrderingWorkstation,
    "customers": CustomersWorkstation,
    "marketing": MarketingWorkstation,
    "market": RivalsWorkstation,
    "settings": OperationsWorkstation,
    "staff": StaffWorkstation,
}
