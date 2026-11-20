"""Action Center and morning briefing. A click carries the drill target."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QPushButton, QVBoxLayout

from open_late.ui.components import label
from open_late.ui.components.core import MUTED

from .action_center import BANDS


class ActionCenterWidget(QFrame):
    chosen = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("phase5ActionCenter")
        self.box = QVBoxLayout(self)
        self.box.addWidget(label("Action Center", 16, True))
        self.counts = label("", 11, color=MUTED, wrap=True)
        self.counts.setObjectName("phase5Counts")
        self.box.addWidget(self.counts)

    def set_payload(self, payload):
        while self.box.count() > 2:
            item = self.box.takeAt(2)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        items = list(payload.get("items", []))
        tally = payload.get("counts") or {}
        self.counts.setText("  ·  ".join(f"{band}: {tally.get(band, 0)}" for band in BANDS))
        for action in items[:8]:
            button = QPushButton(f"{action.band}: {action.title}")
            button.setToolTip(action.detail)
            button.clicked.connect(lambda _=False, drill=action.target: self.chosen.emit(drill))
            self.box.addWidget(button)
        if len(items) > 8:
            self.box.addWidget(label(f"{len(items) - 8} more on the list.", 11, color=MUTED))
        self.box.addStretch(1)


class BriefingWidget(QFrame):
    chosen = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("phase5Briefing")
        self.box = QVBoxLayout(self)
        self.box.addWidget(label("Morning Executive Briefing", 16, True))

    def set_items(self, items):
        while self.box.count() > 1:
            item = self.box.takeAt(1)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for row in items:
            button = QPushButton(row.title)
            button.setToolTip(row.detail)
            button.clicked.connect(lambda _=False, drill=row.target: self.chosen.emit(drill))
            self.box.addWidget(button)
        self.box.addStretch(1)
