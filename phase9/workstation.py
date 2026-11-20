"""Archive desk. It reads the company and does not change it."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QLabel, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from open_late.text import money

from .annual import create
from .eras import identify
from .records import calculate
from .timeline import build, year_for_day

_MONEY_METRICS = {"revenue", "expenses", "net_profit", "ending_cash", "average_basket"}
_MONEY_RECORDS = {"Revenue", "Profit"}


class CorporateHistoryWorkstation(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("historyDesk")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "QWidget#historyDesk { background: #09152D; color: #E8EEF8; }"
            "QLabel { color: #E8EEF8; background: transparent; }"
            "QTableWidget { background: #0E1C3A; color: #E8EEF8; gridline-color: #1A2E55; border: 1px solid #1A2E55; }"
            "QHeaderView::section { background: #12254A; color: #E8EEF8; border: none; padding: 6px; }"
            "QComboBox { background: #0B1730; color: #E8EEF8; border: 1px solid #1A2E55; padding: 4px 8px; }"
            "QTabWidget::pane { background: #0E1C3A; border: 1px solid #1A2E55; }"
            "QTabBar::tab { background: #12254A; color: #E8EEF8; padding: 6px 12px; }"
            "QTabBar::tab:selected { background: #17376D; }"
        )
        self.state = None
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 16)
        title = QLabel("Corporate History & Annual Reports")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #E8EEF8; background: transparent;")
        root.addWidget(title)
        note = QLabel("The archive reads closed days, store openings, and the mail already on the desk. It does not change the company. Money is in dollars.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #8BA0C0; background: transparent;")
        root.addWidget(note)
        self.year = QComboBox()
        self.year.currentIndexChanged.connect(self.refresh)
        root.addWidget(self.year)
        tabs = QTabWidget()
        root.addWidget(tabs)
        self.timeline = QTableWidget(0, 5)
        self.timeline.setHorizontalHeaderLabels(["Day", "Year", "Type", "Event", "Detail"])
        self.timeline.horizontalHeader().setStretchLastSection(True)
        tabs.addTab(self.timeline, "Timeline")
        self.report = QTableWidget(0, 3)
        self.report.setHorizontalHeaderLabels(["Section", "Metric", "Value"])
        self.report.horizontalHeader().setStretchLastSection(True)
        tabs.addTab(self.report, "Annual Report")
        self.records = QTableWidget(0, 4)
        self.records.setHorizontalHeaderLabels(["Record", "Value", "Day", "Detail"])
        self.records.horizontalHeader().setStretchLastSection(True)
        tabs.addTab(self.records, "Hall of Records")
        self.eras = QTableWidget(0, 4)
        self.eras.setHorizontalHeaderLabels(["Era", "Start", "End", "Reason"])
        self.eras.horizontalHeader().setStretchLastSection(True)
        tabs.addTab(self.eras, "Corporate Eras")
        self.lessons = QLabel("")
        self.lessons.setWordWrap(True)
        root.addWidget(self.lessons)

    def load(self, state) -> None:
        self.state = state
        current = year_for_day(int(getattr(state, "day", 1) or 1)) if state is not None else 1
        self.year.blockSignals(True)
        self.year.clear()
        for number in range(1, current + 1):
            self.year.addItem(f"Year {number}", number)
        self.year.setCurrentIndex(max(0, current - 1))
        self.year.blockSignals(False)
        self.refresh()

    def refresh(self, *_args) -> None:
        if self.state is None:
            return
        year = int(self.year.currentData() or 1)
        events = build(self.state)
        self.timeline.setRowCount(len(events))
        for index, event in enumerate(events):
            for column, value in enumerate((event.day, event.year, event.kind, event.title, event.detail)):
                self.timeline.setItem(index, column, QTableWidgetItem(str(value)))
        annual = create(self.state, year)
        rows = [("Financial", key, _shown(key, value)) for key, value in annual.financials.items()]
        rows.extend(("Operations", key, _shown(key, value)) for key, value in annual.operations.items())
        self.report.setRowCount(len(rows))
        for index, row in enumerate(rows):
            for column, value in enumerate(row):
                self.report.setItem(index, column, QTableWidgetItem(str(value)))
        records = calculate(self.state)
        self.records.setRowCount(len(records))
        for index, item in enumerate(records):
            value = money(int(item.value)) if item.detail in _MONEY_RECORDS else str(int(item.value))
            for column, cell in enumerate((item.title, value, item.day, item.detail)):
                self.records.setItem(index, column, QTableWidgetItem(str(cell)))
        eras = identify(self.state)
        self.eras.setRowCount(len(eras))
        for index, item in enumerate(eras):
            for column, value in enumerate((item.title, item.start_day, item.end_day or "Current", item.reason)):
                self.eras.setItem(index, column, QTableWidgetItem(str(value)))
        self.lessons.setText("\n".join(annual.lessons))


def _shown(key: str, value) -> str:
    if key in _MONEY_METRICS:
        return money(int(value or 0))
    return str(value)
