"""Home desk: inbox and the book. Products live on Inventory; the store plan lives on Planograms."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from open_late.books import balance_lines
from open_late.departments import DEPARTMENT_LABELS
from open_late.text import money, money_compact, weekday_name

PURPLE = "#3F1D72"
YELLOW = "#FFC40A"
GREEN = "#0E5C32"
BLUE = "#0E5C32"
INK = "#122033"
LINE = "#E3E7EE"
CREAM = "#F7F4EC"


def _label(text: str, size: int = 13, bold: bool = False, color: str = INK) -> QLabel:
    lab = QLabel(text)
    lab.setStyleSheet(f"color: {color}; background: transparent;")
    font = lab.font()
    font.setPixelSize(size)
    font.setBold(bold)
    lab.setFont(font)
    return lab


class FloorPlan(QWidget):
    """Orthographic grocery plan: rooms, gondolas, coolers, produce."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("floorPane")
        self.setMinimumHeight(96)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAutoFillBackground(True)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor(CREAM))
        margin = 10
        hall = (margin, margin, w - margin * 2, h - margin * 2)
        painter.setPen(QPen(QColor("#4A4A4A"), 3))
        painter.setBrush(QColor("#FBF9F4"))
        painter.drawRect(*hall)
        self._rooms(painter, hall)
        painter.end()

    def _rooms(self, painter: QPainter, hall: tuple[int, int, int, int]) -> None:
        x, y, w, h = hall
        font = QFont()
        font.setPixelSize(9 if h < 160 else 10)
        painter.setFont(font)
        top_h = max(22, int(h * 0.20))
        bot_h = max(20, int(h * 0.16))
        rooms = [
            (x, y, int(w * 0.12), top_h, "#E7E0D4", "Mech."),
            (x + int(w * 0.12), y, int(w * 0.10), top_h, "#F3E6C8", "Men"),
            (x + int(w * 0.22), y, int(w * 0.10), top_h, "#F3E6C8", "Women"),
            (x + int(w * 0.32), y, int(w * 0.14), top_h, "#F6E7D2", "Office"),
            (x + int(w * 0.46), y, int(w * 0.22), top_h, "#D5E8F2", "Freezer"),
            (x + int(w * 0.68), y, int(w * 0.16), top_h, "#EFE8DC", "Stock"),
            (x + int(w * 0.84), y, int(w * 0.16), top_h, "#EFE8DC", "Receiving"),
        ]
        for rx, ry, rw, rh, color, name in rooms:
            self._room(painter, rx, ry, rw, rh, color, name)
        cool_y = y + top_h + 8
        self._room(painter, x + 8, cool_y, int(w * 0.10), int(h * 0.16), "#D5E8F2", "Cooler")
        self._room(painter, x + int(w * 0.46), y + top_h + 6, int(w * 0.28), int(h * 0.12), "#E7F2F8", "Frozen")
        self._room(painter, x + int(w * 0.76), y + top_h + 6, int(w * 0.16), int(h * 0.12), "#E7F2F8", "Dairy")
        mid_top = y + top_h + max(4, int(h * 0.14))
        mid_h = max(16, h - top_h - bot_h - max(8, int(h * 0.16)))
        gondola_w = max(10, int(w * 0.035))
        gap = max(14, int(w * 0.045))
        left = x + int(w * 0.22)
        for index in range(6):
            gx = left + index * (gondola_w + gap)
            painter.setPen(QPen(QColor("#C5B89A"), 1))
            painter.setBrush(QColor("#E7D7C3"))
            painter.drawRect(gx, mid_top, gondola_w, max(20, mid_h))
        painter.setPen(QColor("#6E6454"))
        painter.drawText(left, mid_top + mid_h // 2, "Grocery")
        prod_x = x + int(w * 0.78)
        painter.setPen(QPen(QColor("#8AA882"), 1))
        painter.setBrush(QColor("#E4F0D8"))
        painter.drawRect(prod_x, mid_top, int(w * 0.18), max(20, mid_h))
        painter.setPen(QColor("#3E5A32"))
        painter.drawText(prod_x + 8, mid_top + 16, "Produce")
        by = y + h - bot_h
        self._room(painter, x + int(w * 0.28), by, int(w * 0.22), bot_h - 4, "#F6EFE4", "Cashiers")
        self._room(painter, x + int(w * 0.52), by, int(w * 0.22), bot_h - 4, "#EFE8DC", "Entry")

    def _room(self, painter: QPainter, x: int, y: int, w: int, h: int, color: str, name: str) -> None:
        painter.setPen(QPen(QColor("#8A8172"), 1))
        painter.setBrush(QColor(color))
        painter.drawRect(x, y, max(8, w), max(8, h))
        if h >= 16 and w >= 28:
            painter.setPen(QColor("#5C564C"))
            painter.drawText(x + 3, y + min(12, h - 2), name)


def _stock_rows(state):
    if state is None:
        return []
    rows = []
    for product_id, line in state.stock.items():
        product = state.products.get(product_id)
        if product is None:
            continue
        rows.append((product, line))
    rows.sort(key=lambda pair: (-pair[1].on_hand, pair[0].name))
    return rows[:16]


def _fit_table(table: QTableWidget, stretch_column: int) -> None:
    table.setWordWrap(False)
    table.setTextElideMode(Qt.TextElideMode.ElideRight)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(22)
    header = table.horizontalHeader()
    header.setMinimumSectionSize(36)
    header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    for col in range(table.columnCount()):
        mode = QHeaderView.ResizeMode.Stretch if col == stretch_column else QHeaderView.ResizeMode.ResizeToContents
        header.setSectionResizeMode(col, mode)


class ProductSheet(QFrame):
    """The MY PRODUCTS grid. Lives on the Inventory tab."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("productPane")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"QFrame#productPane {{ background: #FFFFFF; border: 1px solid {LINE}; }}")
        self.setMinimumHeight(180)
        self.setMaximumHeight(280)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        head = QHBoxLayout()
        head.addWidget(_label("MY PRODUCTS", 14, True))
        head.addStretch(1)
        export = QPushButton("Export Filtered Data")
        export.setObjectName("exportProducts")
        export.setCursor(Qt.CursorShape.PointingHandCursor)
        export.setStyleSheet(
            f"QPushButton#exportProducts {{ background: {YELLOW}; color: #1A1A1A; border: none; "
            f"border-radius: 2px; padding: 6px 10px; font-weight: 700; }}"
        )
        export.clicked.connect(self._export_products)
        head.addWidget(export)
        layout.addLayout(head)
        self.product_table = QTableWidget(0, 5)
        self.product_table.setHorizontalHeaderLabels(["status", "product sku", "item name", "stock", "price"])
        from open_late.ui.osprey_docs import excel_table
        excel_table(self.product_table)
        _fit_table(self.product_table, stretch_column=2)
        layout.addWidget(self.product_table, stretch=1)

    def load(self, state) -> None:
        rows = _stock_rows(state)
        self.product_table.setRowCount(len(rows))
        for index, (product, line) in enumerate(rows):
            values = [
                "Active" if line.on_hand else "Out",
                product.id,
                product.name,
                str(line.on_hand),
                money(product.price),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == 2:
                    item.setForeground(QColor(BLUE))
                self.product_table.setItem(index, col, item)
        _fit_table(self.product_table, stretch_column=2)

    def _export_products(self) -> None:
        lines = ["\t".join(["status", "product sku", "item name", "stock", "price"])]
        table = self.product_table
        for row in range(table.rowCount()):
            cells = []
            for col in range(table.columnCount()):
                item = table.item(row, col)
                cells.append(item.text() if item is not None else "")
            lines.append("\t".join(cells))
        QApplication.clipboard().setText("\n".join(lines))


class CommandBoard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("commandBoard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"QWidget#commandBoard {{ background: #FFFFFF; color: {INK}; }}")
        self._host = None
        self._messages: list = []
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 8)
        root.setSpacing(6)
        self.summary = QFrame()
        self.summary.setObjectName("deskSummary")
        self.summary.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.summary.setStyleSheet(
            f"QFrame#deskSummary {{ background: #FFFFFF; border: 1px solid {LINE}; }}"
        )
        self.summary_row = QHBoxLayout(self.summary)
        self.summary_row.setContentsMargins(10, 4, 10, 4)
        self.summary_row.setSpacing(18)
        root.addWidget(self.summary)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.mail = self._mail_pane()
        self.book = self._book_pane()
        row.addWidget(self.mail, stretch=1)
        row.addWidget(self.book, stretch=1)
        root.addLayout(row, stretch=1)

    def load(self, state, host) -> None:
        self._host = host
        self._fill_summary(state)
        self._fill_mail(state)
        self._fill_book(state)

    def _fill_summary(self, state) -> None:
        while self.summary_row.count():
            item = self.summary_row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if state is None:
            return
        notes = sum(1 for message in state.inbox if not message.resolved)
        on_hand = sum(int(line.on_hand or 0) for line in state.stock.values())
        items = sum(1 for line in state.stock.values() if line.on_hand)
        figures = (
            ("Cash", money_compact(state.cash), money(state.cash)),
            ("Open notes", str(notes), ""),
            ("Items in stock", str(items), ""),
            ("Units on hand", f"{on_hand:,}", ""),
        )
        for caption, value, tip in figures:
            block = QVBoxLayout()
            block.setSpacing(0)
            block.addWidget(_label(caption.upper(), 10, True, "#5B6573"))
            shown = _label(value, 16, True)
            if tip:
                shown.setToolTip(tip)
            block.addWidget(shown)
            wrap = QWidget()
            wrap.setLayout(block)
            self.summary_row.addWidget(wrap)
        self.summary_row.addStretch(1)

    def _pane(self, name: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName(name)
        frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        frame.setStyleSheet(
            f"QFrame#{name} {{ background: #FFFFFF; border: 1px solid {LINE}; }}"
        )
        frame.setMinimumHeight(0)
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        return frame

    def _mail_pane(self) -> QFrame:
        frame = self._pane("mailPane")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        bar = QWidget()
        bar.setMinimumHeight(32)
        bar.setStyleSheet(f"background: {BLUE};")
        bar_row = QHBoxLayout(bar)
        bar_row.setContentsMargins(8, 0, 8, 0)
        title = QLabel("Inbox")
        title.setStyleSheet("color: white; font-weight: 700; background: transparent;")
        bar_row.addWidget(title)
        bar_row.addStretch(1)
        write = QPushButton("Write")
        write.setObjectName("writeMail")
        write.setCursor(Qt.CursorShape.PointingHandCursor)
        write.setStyleSheet(
            "QPushButton#writeMail { background: #FFFFFF; color: #0E5C32; border: none; "
            "border-radius: 2px; padding: 2px 10px; font-weight: 700; }"
        )
        write.clicked.connect(self._write_mail)
        bar_row.addWidget(write)
        layout.addWidget(bar)
        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self.mail_list = QListWidget()
        self.mail_list.setObjectName("mailList")
        self.mail_list.currentRowChanged.connect(self._show_message)
        body.addWidget(self.mail_list, stretch=1)
        reading = QWidget()
        reading.setObjectName("mailReading")
        column = QVBoxLayout(reading)
        column.setContentsMargins(12, 10, 12, 10)
        self.mail_from = _label("", 12, True)
        self.mail_subject = _label("", 14, True)
        self.mail_subject.setWordWrap(True)
        self.mail_body = _label("", 12)
        self.mail_body.setWordWrap(True)
        self.mail_body.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.mail_actions = QHBoxLayout()
        column.addWidget(self.mail_from)
        column.addWidget(self.mail_subject)
        column.addWidget(self.mail_body, stretch=1)
        column.addLayout(self.mail_actions)
        body.addWidget(reading, stretch=1)
        layout.addLayout(body, stretch=1)
        return frame

    def _book_pane(self) -> QFrame:
        frame = self._pane("bookPane")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        bar = QLabel("  Book")
        bar.setMinimumHeight(28)
        bar.setStyleSheet(f"background: {GREEN}; color: white; font-weight: 700;")
        layout.addWidget(bar)
        ribbon = QHBoxLayout()
        ribbon.setContentsMargins(8, 4, 8, 4)
        for name, slot in (("Home", self._show_prices), ("Data", self._show_books)):
            btn = QPushButton(name)
            btn.setObjectName("book" + name)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { background: #FFFFFF; color: #122033; border: 1px solid #E3E7EE; "
                "border-radius: 2px; padding: 4px 10px; font-weight: 600; }"
                "QPushButton:hover { background: #F4F6FA; }"
            )
            btn.clicked.connect(slot)
            ribbon.addWidget(btn)
        ribbon.addStretch(1)
        layout.addLayout(ribbon)
        self.book_table = QTableWidget(0, 6)
        self.book_table.setHorizontalHeaderLabels(["Category", "Code", "Description", "On hand", "Cost", "Price"])
        from open_late.ui.osprey_docs import excel_table
        excel_table(self.book_table)
        _fit_table(self.book_table, stretch_column=2)
        layout.addWidget(self.book_table, stretch=1)
        return frame

    def _fill_book(self, state) -> None:
        self._price_rows = _stock_rows(state)
        self._book_rows = balance_lines(state)
        self._show_prices()

    def _show_prices(self) -> None:
        self.book_table.setColumnCount(6)
        self.book_table.setHorizontalHeaderLabels(["Category", "Code", "Description", "On hand", "Cost", "Price"])
        rows = getattr(self, "_price_rows", [])
        self.book_table.setRowCount(len(rows))
        for index, (product, line) in enumerate(rows):
            dept = DEPARTMENT_LABELS.get(product.department or product.category, product.category)
            values = [dept, product.id, product.name, str(line.on_hand), money(product.cost), money(product.price)]
            for col, value in enumerate(values):
                self.book_table.setItem(index, col, QTableWidgetItem(value))
        _fit_table(self.book_table, stretch_column=2)

    def _show_books(self) -> None:
        self.book_table.setColumnCount(2)
        self.book_table.setHorizontalHeaderLabels(["Account", "Amount"])
        rows = getattr(self, "_book_rows", [])
        self.book_table.setRowCount(len(rows))
        for index, (name, amount) in enumerate(rows):
            self.book_table.setItem(index, 0, QTableWidgetItem(name))
            self.book_table.setItem(index, 1, QTableWidgetItem(money(amount)))
        _fit_table(self.book_table, stretch_column=0)

    def _fill_mail(self, state) -> None:
        self.mail_list.clear()
        self._messages = []
        if state is None:
            return
        pending = [message for message in state.inbox if not message.resolved]
        pending.sort(key=lambda message: (not message.urgent, -message.day))
        for message in pending:
            self._messages.append(message)
            when = f"{weekday_name(message.day)} · Day {message.day}"
            item = QListWidgetItem(f"{message.title}\n{when}")
            self.mail_list.addItem(item)
        for entry in reversed(state.journal[-8:]):
            self._messages.append(entry)
            self.mail_list.addItem(QListWidgetItem(entry.split("\n", 1)[0][:80]))
        if self.mail_list.count():
            self.mail_list.setCurrentRow(0)
        else:
            self.mail_subject.setText("The desk is clear.")
            self.mail_body.setText("Notes show up here when the floor writes in.")
            self.mail_from.setText("")

    def _show_message(self, row: int) -> None:
        while self.mail_actions.count():
            item = self.mail_actions.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if row < 0 or row >= len(self._messages):
            return
        message = self._messages[row]
        if isinstance(message, str):
            self.mail_from.setText("Journal")
            self.mail_subject.setText(message.split("\n", 1)[0][:80])
            self.mail_body.setText(message)
            return
        self.mail_from.setText("Floor")
        self.mail_subject.setText(message.title)
        self.mail_body.setText(message.body)
        for choice in message.choices:
            btn = QPushButton(choice.label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if choice is message.choices[0]:
                btn.setStyleSheet(
                    f"QPushButton {{ background: {YELLOW}; color: #1A1A1A; border: none; "
                    "border-radius: 4px; padding: 6px 12px; font-weight: 700; }}"
                )
            btn.clicked.connect(lambda _=False, mid=message.id, cid=choice.id: self._choose(mid, cid))
            self.mail_actions.addWidget(btn)
        self.mail_actions.addStretch(1)

    def _choose(self, message_id: str, choice_id: str) -> None:
        host = self._host
        if host is not None and hasattr(host, "_choose"):
            host._choose(message_id, choice_id)

    def _write_mail(self) -> None:
        host = self._host
        if host is not None and hasattr(host, "_open_app"):
            host._open_app("journal")
