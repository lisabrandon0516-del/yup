"""Detail panel for one inventory item, store, supplier, employee, household, or rival."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget


class DeepDetailView(QFrame):
    navigate = Signal(object)
    action = Signal(object)
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("phase6DeepDetail")
        self.setFixedWidth(420)
        self.on_show = None
        self.setStyleSheet(
            "QFrame#phase6DeepDetail { background: #FFFFFF; border: 1px solid #E3E8EE; }"
            "QLabel { color: #1C2430; background: transparent; }"
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        header = QFrame()
        row = QHBoxLayout(header)
        row.setContentsMargins(14, 10, 10, 8)
        self.title = QLabel("Details")
        self.title.setStyleSheet("font-size: 18px; font-weight: 700; color: #1C2430;")
        row.addWidget(self.title, 1)
        close = QPushButton("Close")
        close.clicked.connect(self.hide)
        close.clicked.connect(self.closed.emit)
        row.addWidget(close)
        root.addWidget(header)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        root.addWidget(self.scroll, 1)
        self.hide()

    def set_record(self, record: dict) -> None:
        self.title.setText(str(record.get("title", "Details")))
        body = QWidget()
        box = QVBoxLayout(body)
        box.setContentsMargins(14, 4, 14, 14)
        meta = QLabel(f"{record.get('kind', '')} · {record.get('id', '')}")
        meta.setStyleSheet("color: #6B7280;")
        meta.setWordWrap(True)
        box.addWidget(meta)
        for name, value in (record.get("summary") or {}).items():
            line = QLabel(f"{name}: {value}")
            line.setWordWrap(True)
            box.addWidget(line)
        for section, payload in (record.get("sections") or {}).items():
            title = QLabel(section)
            title.setStyleSheet("font-weight: 700; color: #0E5C32; margin-top: 10px;")
            box.addWidget(title)
            text = QLabel(self._format(payload))
            text.setWordWrap(True)
            text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            box.addWidget(text)
        box.addStretch(1)
        self.scroll.setWidget(body)

    def show_record(self, record: dict) -> None:
        self.set_record(record)
        self.show()
        self.raise_()
        if self.on_show is not None:
            self.on_show()

    def _format(self, payload) -> str:
        if isinstance(payload, dict):
            return "\n".join(f"{str(key).replace('_', ' ').title()}: {value}" for key, value in payload.items()) or "No data."
        if isinstance(payload, list):
            return "\n\n".join(self._format(item) if isinstance(item, dict) else str(item) for item in payload) or "No data."
        return str(payload)
