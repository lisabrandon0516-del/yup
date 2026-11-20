"""Delegation desk. Saving a policy or approving a row does not call the engine."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from open_late.text import money

from .managers import managers
from .models import AREAS, LEVELS, DelegationPolicy
from .policy_store import book, store
from .queue import note_restocks, resolve


def _desk_sheet(name: str) -> str:
    return (
        f"QWidget#{name} {{ background: #09152D; color: #E8EEF8; }}"
        "QLabel { color: #E8EEF8; background: transparent; }"
        "QTableWidget { background: #0E1C3A; color: #E8EEF8; gridline-color: #1A2E55;"
        " border: 1px solid #1A2E55; }"
        "QHeaderView::section, QTableCornerButton::section { background: #12254A; color: #E8EEF8; border: none;"
        " border-bottom: 1px solid #1A2E55; padding: 6px; }"
        "QComboBox, QSpinBox, QLineEdit { background: #0B1730; color: #E8EEF8;"
        " border: 1px solid #1A2E55; border-radius: 4px; padding: 4px 8px; }"
        "QPushButton { background: #0E2244; color: #F4F7FB; border: 1px solid #2A4A72;"
        " border-radius: 8px; padding: 6px 14px; font-weight: 600; }"
    )


class DelegationWorkstation(QWidget):
    changed = Signal()
    approval_selected = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("delegationDesk")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(_desk_sheet("delegationDesk"))
        self.state = None
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 16)
        title = QLabel("Executive Delegation")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #E8EEF8; background: transparent;")
        root.addWidget(title)
        note = QLabel("An approval is a decision on the queue. It does not change a price, place an order, or post a schedule. Amounts are dollars.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #8BA0C0; background: transparent;")
        root.addWidget(note)
        self.area = QComboBox()
        self.area.addItems(AREAS)
        self.level = QComboBox()
        self.level.addItems(LEVELS)
        self.objective = QComboBox()
        self.objective.addItems(["balanced", "protect_margin", "availability_first", "growth", "cash_preservation"])
        self.reserve = QSpinBox()
        self.reserve.setPrefix("$")
        self.reserve.setMaximum(2_000_000_000)
        self.spend = QSpinBox()
        self.spend.setPrefix("$")
        self.spend.setMaximum(2_000_000_000)
        row = QHBoxLayout()
        for caption, widget in (
            ("Area", self.area),
            ("Authority", self.level),
            ("Objective", self.objective),
            ("Cash reserve", self.reserve),
            ("Max one decision", self.spend),
        ):
            row.addWidget(QLabel(caption))
            row.addWidget(widget)
        root.addLayout(row)
        save = QPushButton("Save delegation policy")
        save.clicked.connect(self.save_policy)
        root.addWidget(save)
        self.manager_table = QTableWidget(0, 5)
        self.manager_table.setHorizontalHeaderLabels(["Manager", "Area", "Store", "Wage", "Status"])
        self.manager_table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.manager_table)
        self.approval_table = QTableWidget(0, 5)
        self.approval_table.setHorizontalHeaderLabels(["Proposal", "Area", "Decision", "Status", "Reason"])
        self.approval_table.horizontalHeader().setStretchLastSection(True)
        self.approval_table.itemSelectionChanged.connect(self._select)
        root.addWidget(self.approval_table)
        actions = QHBoxLayout()
        approve = QPushButton("Approve")
        approve.clicked.connect(lambda: self._resolve(True))
        reject = QPushButton("Reject")
        reject.clicked.connect(lambda: self._resolve(False))
        actions.addWidget(approve)
        actions.addWidget(reject)
        actions.addStretch(1)
        root.addLayout(actions)
        self.area.currentTextChanged.connect(self._load_policy)

    def load(self, state) -> None:
        self.state = state
        if state is not None:
            note_restocks(state)
        self._load_policy()
        self._fill()

    def _load_policy(self, *_args) -> None:
        if self.state is None:
            return
        policy = book(self.state).policy(self.area.currentText())
        self.level.setCurrentText(policy.level)
        self.objective.setCurrentText(policy.objective)
        self.reserve.setValue(int(policy.min_cash_reserve))
        self.spend.setValue(int(policy.max_single_spend))

    def save_policy(self) -> None:
        if self.state is None:
            return
        current = book(self.state)
        old = current.policy(self.area.currentText())
        current.save_policy(DelegationPolicy(
            area=old.area,
            level=self.level.currentText(),
            objective=self.objective.currentText(),
            min_cash_reserve=self.reserve.value(),
            max_single_spend=self.spend.value(),
            min_margin_pct=old.min_margin_pct,
            max_price_change_pct=old.max_price_change_pct,
            require_review_if_confidence_below=old.require_review_if_confidence_below,
            enabled=True,
        ))
        store(self.state, current)
        self._fill()
        self.changed.emit()

    def _fill(self) -> None:
        people = managers(self.state)
        self.manager_table.setRowCount(len(people))
        for index, person in enumerate(people):
            status = "Available" if person.available else "Unavailable"
            for column, value in enumerate((person.name, person.area, person.assignment, person.wage, status)):
                self.manager_table.setItem(index, column, QTableWidgetItem(str(value)))
        approvals = book(self.state).approvals if self.state is not None else []
        self.approval_table.setRowCount(len(approvals))
        for index, row in enumerate(approvals):
            proposal = row.get("proposal", {})
            decision = row.get("decision", {})
            spend = proposal.get("expected_spend")
            title = proposal.get("title", "")
            if spend:
                title = f"{title} ({money(spend)})"
            values = (title, proposal.get("area"), decision.get("status"), row.get("status"), decision.get("reason"))
            for column, value in enumerate(values):
                self.approval_table.setItem(index, column, QTableWidgetItem(str(value)))

    def _select(self) -> None:
        row = self.approval_table.currentRow()
        approvals = book(self.state).approvals if self.state is not None else []
        if 0 <= row < len(approvals):
            self.approval_selected.emit(approvals[row])

    def _resolve(self, approved: bool) -> None:
        if self.state is None:
            return
        row = self.approval_table.currentRow()
        approvals = book(self.state).approvals
        if row < 0 and approvals:
            row = 0
        if not (0 <= row < len(approvals)):
            return
        resolve(self.state, approvals[row].get("proposal", {}).get("id", ""), approved)
        self._fill()
        self.changed.emit()
