"""Record drawer opened from a desk row."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QPushButton, QVBoxLayout

from open_late.ui.components import label


class DetailDrawer(QFrame):
    closed = Signal()
    open_target = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("detailDrawer")
        self.setFixedWidth(340)
        self.on_show = None
        box = QVBoxLayout(self)
        box.setContentsMargins(14, 12, 14, 12)
        close = QPushButton("Close")
        close.clicked.connect(self.hide)
        close.clicked.connect(self.closed.emit)
        box.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        self.title = label("Details", 18, True)
        self.meta = label("", 11, wrap=True)
        self.body = label("", 12, wrap=True)
        box.addWidget(self.title)
        box.addWidget(self.meta)
        box.addWidget(self.body)
        box.addStretch(1)
        self.hide()

    def show_record(self, title_text: str, record: dict, meta: str = "") -> None:
        self.title.setText(title_text)
        self.meta.setText(meta)
        self.body.setText("\n".join(f"{key.replace('_', ' ').title()}: {value}" for key, value in record.items()))
        self.show()
        self.raise_()
        if self.on_show is not None:
            self.on_show()
