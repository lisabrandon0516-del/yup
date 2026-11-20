"""Board desk. Starting a scenario records the scorecard and leaves the company as it is."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QLabel, QProgressBar, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from open_late.text import money

from .board import report
from .catalog import SCENARIOS
from .engine import start

_MONEY = {"cash", "weekly_profit"}


class BoardObjectivesWorkstation(QWidget):
    scenario_started = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("boardDesk")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "QWidget#boardDesk { background: #09152D; color: #E8EEF8; }"
            "QLabel { color: #E8EEF8; background: transparent; }"
            "QTableWidget { background: #0E1C3A; color: #E8EEF8; gridline-color: #1A2E55; border: 1px solid #1A2E55; }"
            "QHeaderView::section { background: #12254A; color: #E8EEF8; border: none; padding: 6px; }"
            "QComboBox, QProgressBar { background: #0B1730; color: #E8EEF8; border: 1px solid #1A2E55; }"
            "QPushButton { background: #0E2244; color: #F4F7FB; border: 1px solid #2A4A72; border-radius: 8px; padding: 6px 14px; }"
        )
        self.state = None
        box = QVBoxLayout(self)
        box.setContentsMargins(16, 12, 16, 16)
        title = QLabel("Board Objectives & Scenarios")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #E8EEF8; background: transparent;")
        box.addWidget(title)
        note = QLabel("A scenario is a scorecard for the board. Starting one does not change cash, prices, inventory, or stores. Money figures are dollars.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #8BA0C0; background: transparent;")
        box.addWidget(note)
        self.selector = QComboBox()
        for ident, row in SCENARIOS.items():
            self.selector.addItem(row.title, ident)
        box.addWidget(self.selector)
        begin = QPushButton("Start selected scenario")
        begin.clicked.connect(self._start)
        box.addWidget(begin)
        self.status = QLabel("No active scenario")
        box.addWidget(self.status)
        self.confidence = QProgressBar()
        self.confidence.setRange(0, 100)
        self.confidence.setObjectName("boardConfidence")
        box.addWidget(self.confidence)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Objective", "Current", "Target", "Deadline", "Weight", "Status"])
        self.table.horizontalHeader().setStretchLastSection(True)
        box.addWidget(self.table)
        self.notes = QLabel("")
        self.notes.setWordWrap(True)
        box.addWidget(self.notes)

    def load(self, state) -> None:
        self.state = state
        self.refresh()

    def _start(self) -> None:
        if self.state is None:
            return
        ident = self.selector.currentData()
        start(self.state, ident)
        self.refresh()
        self.scenario_started.emit(ident)

    def refresh(self) -> None:
        card = report(self.state) if self.state is not None else None
        if card is None:
            self.status.setText("No active scenario")
            self.confidence.setValue(0)
            self.confidence.setFormat("Board confidence")
            self.table.setRowCount(0)
            self.notes.setText("")
            return
        self.status.setText(f"{card.scenario} · {card.status.title()}")
        self.confidence.setValue(card.confidence)
        self.confidence.setFormat(f"Board confidence {card.confidence}%")
        self.table.setRowCount(len(card.objectives))
        for row, objective in enumerate(card.objectives):
            values = (
                objective["title"],
                _figure(objective["metric"], objective["value"]),
                f"{objective['comparison']} {_figure(objective['metric'], objective['target'])}",
                f"Within {objective['deadline']} days",
                objective["weight"],
                "Met" if objective["achieved"] else "Open",
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(str(value)))
        self.notes.setText("\n".join(card.notes[-8:]))


def _figure(metric: str, value) -> str:
    if metric in _MONEY:
        return money(int(value or 0))
    if metric == "open_stores":
        return str(int(value or 0))
    return str(int(value or 0)) if float(value or 0).is_integer() else str(value)
