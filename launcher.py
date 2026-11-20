"""The first screen: the company launcher over the dusk storefront."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPen, QPixmap, QPolygon
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from open_late import GAME_NAME
from open_late.text import money
from open_late.ui.theme import ui_font

ASSETS = Path(__file__).resolve().parent.parent / "assets" / "brand" / "launcher"
GREEN = "#157A3A"
GREEN_DEEP = "#0E3B24"
INK = "#142033"
MUTED = "#5C6B7A"
LINE = "#E3E8EE"
CHICAGO = ZoneInfo("America/Chicago")


def _when(stamp: str) -> str:
    try:
        parsed = datetime.fromisoformat(stamp)
    except ValueError:
        return stamp
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    clock = parsed.astimezone(CHICAGO)
    hour = clock.strftime("%I").lstrip("0") or "12"
    return f"{clock.strftime('%b')} {clock.day}, {clock.year} · {hour}:{clock.strftime('%M %p')} CT"


def _play_icon(white: bool) -> QIcon:
    pix = QPixmap(14, 14)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#FFFFFF" if white else GREEN))
    painter.drawPolygon(QPolygon([QPoint(3, 1), QPoint(12, 7), QPoint(3, 13)]))
    painter.end()
    return QIcon(pix)


def _dots_icon() -> QIcon:
    pix = QPixmap(16, 16)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#1C2430"))
    for y in (2, 7, 12):
        painter.drawEllipse(6, y, 3, 3)
    painter.end()
    return QIcon(pix)


def _stores(count: int) -> str:
    return "1 store" if count == 1 else f"{count} stores"


class _Backdrop(QWidget):
    """The store photograph, with a light wash behind the title."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._photo = QPixmap(str(ASSETS / "hero.jpg"))

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        rect = self.rect()
        photo = self._photo
        if not photo.isNull():
            scaled = photo.scaled(
                rect.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = rect.x() + (rect.width() - scaled.width()) // 2
            y = rect.bottom() - scaled.height() + 1
            painter.drawPixmap(x, y, scaled)
        else:
            painter.fillRect(rect, QColor("#1C3A4E"))
        wash = QLinearGradient(0, 0, rect.width() * 0.55, rect.height() * 0.85)
        wash.setColorAt(0.0, QColor(255, 255, 255, 228))
        wash.setColorAt(0.34, QColor(255, 255, 255, 150))
        wash.setColorAt(0.58, QColor(255, 255, 255, 16))
        wash.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillRect(rect, wash)
        scrim = QLinearGradient(0, rect.height() * 0.62, 0, rect.height())
        scrim.setColorAt(0.0, QColor(8, 16, 24, 0))
        scrim.setColorAt(1.0, QColor(8, 16, 24, 150))
        painter.fillRect(rect.adjusted(0, int(rect.height() * 0.55), int(-rect.width() * 0.38), 0), scrim)


class _Glyph(QWidget):
    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.setFixedSize(22, 22)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor(GREEN), 1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        kind = self.kind
        if kind == "stores":
            painter.drawRect(4, 9, 14, 9)
            painter.drawLine(3, 9, 11, 3)
            painter.drawLine(11, 3, 19, 9)
            painter.drawRect(9, 12, 4, 6)
        elif kind == "customers":
            painter.drawRoundedRect(3, 8, 16, 10, 2, 2)
            painter.drawLine(3, 12, 19, 12)
            painter.drawEllipse(8, 4, 6, 5)
        elif kind == "inventory":
            painter.drawRect(4, 7, 14, 11)
            painter.drawLine(4, 11, 18, 11)
            painter.drawLine(11, 7, 11, 18)
        elif kind == "suppliers":
            painter.drawRoundedRect(3, 8, 12, 8, 1, 1)
            painter.drawLine(15, 12, 19, 12)
            painter.drawEllipse(5, 15, 3, 3)
            painter.drawEllipse(12, 15, 3, 3)
        else:
            painter.drawLine(4, 16, 8, 10)
            painter.drawLine(8, 10, 12, 13)
            painter.drawLine(12, 13, 18, 5)


class _Thumb(QLabel):
    def __init__(self, path: Path, badge: bool, parent=None):
        super().__init__(parent)
        self.setFixedSize(128, 72)
        pix = QPixmap(str(path))
        if not pix.isNull():
            scaled = pix.scaled(
                128, 72,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.setPixmap(scaled.copy((scaled.width() - 128) // 2, (scaled.height() - 72) // 2, 128, 72))
        self.setStyleSheet("QLabel { border-radius: 6px; background: #D5DCE3; }")
        if badge:
            tag = QLabel("LAST PLAYED", self)
            tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tag.setFont(ui_font(8))
            tag.setGeometry(18, 4, 92, 16)
            tag.setStyleSheet(
                "QLabel { background: #157A3A; color: white; border: none; border-radius: 3px;"
                " font-size: 8px; font-weight: 700; }"
            )


class _RowMenu(QFrame):
    def __init__(self, host, slot: str, name: str):
        super().__init__(host, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("launchRowMenu")
        self.setStyleSheet(
            "QFrame#launchRowMenu { background: #FFFFFF; border: 1px solid #E3E8EE; border-radius: 8px; }"
            "QPushButton { background: transparent; border: none; color: #1C2430; text-align: left;"
            " padding: 8px 14px; font-weight: 600; }"
            "QPushButton:hover { background: #F4F7F5; }"
            "QPushButton#launchDelete { color: #C2412D; }"
        )
        column = QVBoxLayout(self)
        column.setContentsMargins(4, 4, 4, 4)
        column.setSpacing(0)
        rename = QPushButton("✎   Rename")
        duplicate = QPushButton("⧉   Duplicate")
        delete = QPushButton("🗑   Delete")
        delete.setObjectName("launchDelete")
        for button in (rename, duplicate, delete):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFixedWidth(160)
            column.addWidget(button)
        rename.clicked.connect(lambda: self._go(host._rename_company, slot, name))
        duplicate.clicked.connect(lambda: self._go(host._duplicate_company, slot, name))
        delete.clicked.connect(lambda: self._go(host._delete, slot, name))

    def _go(self, fn, slot: str, name: str) -> None:
        self.close()
        fn(slot, name)


class LaunchScreen(QWidget):
    def __init__(self, host):
        super().__init__()
        self.host = host
        self.setObjectName("launchScreen")
        self._rows: list[tuple] = []
        self._counts: dict[tuple, int] = {}
        self._sort = "Last Played"
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._header())
        root.addWidget(self._body(), stretch=1)
        root.addWidget(self._footer())
        logo = QLabel(self)
        logo.setObjectName("logo")
        logo.setAccessibleName(GAME_NAME)
        mark = QPixmap(str(Path(__file__).resolve().parent.parent / "assets" / "brand" / "game_logo.png"))
        if not mark.isNull():
            logo.setPixmap(mark)
        logo.hide()

    def set_saves(self, rows: list[tuple]) -> None:
        self._rows = list(rows)
        self._fill()

    def _header(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(40)
        bar.setStyleSheet(f"background: {GREEN_DEEP};")
        row = QHBoxLayout(bar)
        row.setContentsMargins(16, 0, 16, 0)
        row.setSpacing(8)
        mark = QLabel("▣")
        mark.setStyleSheet("color: white; font-size: 14px; background: transparent;")
        title = QLabel(GAME_NAME)
        title.setStyleSheet("color: white; font-weight: 700; font-size: 13px; background: transparent;")
        tag = QLabel("REAL DECISIONS. REAL RETAIL. A BIGGER TOMORROW.")
        tag.setStyleSheet("color: rgba(255,255,255,0.82); font-size: 11px; letter-spacing: 0.6px; background: transparent;")
        version = QLabel("v0.1")
        version.setStyleSheet("color: white; font-weight: 700; font-size: 12px; background: transparent;")
        row.addWidget(mark)
        row.addWidget(title)
        row.addStretch(1)
        row.addWidget(tag)
        row.addSpacing(16)
        row.addWidget(version)
        return bar

    def _body(self) -> QWidget:
        backdrop = _Backdrop()
        outer = QHBoxLayout(backdrop)
        outer.setContentsMargins(36, 22, 28, 18)
        outer.setSpacing(24)
        outer.addWidget(self._hero(), stretch=5)
        outer.addWidget(self._companies(), stretch=6)
        return backdrop

    def _hero(self) -> QWidget:
        side = QWidget()
        side.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        column = QVBoxLayout(side)
        column.setContentsMargins(8, 8, 8, 0)
        column.setSpacing(0)
        eyebrow = QLabel("MANAGE     ·     GROW     ·     COMPETE     ·     BUILT")
        eyebrow.setStyleSheet(f"color: {MUTED}; font-size: 11px; letter-spacing: 1.4px; font-weight: 600; background: transparent;")
        column.addWidget(eyebrow)
        column.addSpacing(14)
        title = QLabel(
            f'<span style="color:{INK};">Back Office:</span> <span style="color:{GREEN};">Retail</span>'
        )
        title.setTextFormat(Qt.TextFormat.RichText)
        title.setStyleSheet("font-size: 40px; font-weight: 800; background: transparent;")
        column.addWidget(title)
        column.addSpacing(8)
        deck = QLabel("Run the company behind\nthe storefront.")
        deck.setStyleSheet(f"color: #3E4C5A; font-size: 18px; background: transparent;")
        column.addWidget(deck)
        column.addSpacing(22)
        for kind, label in (
            ("stores", "Open Stores"),
            ("customers", "Serve Customers"),
            ("inventory", "Manage Inventory"),
            ("suppliers", "Work with Suppliers"),
            ("rivals", "Beat the Competition"),
        ):
            line = QHBoxLayout()
            line.setSpacing(10)
            name = QLabel(label)
            name.setStyleSheet(f"color: {INK}; font-size: 15px; font-weight: 600; background: transparent;")
            line.addWidget(_Glyph(kind))
            line.addWidget(name)
            line.addStretch(1)
            column.addLayout(line)
            column.addSpacing(10)
        column.addSpacing(8)
        start = QPushButton("+   Start a New Company    >")
        start.setCursor(Qt.CursorShape.PointingHandCursor)
        start.setFixedHeight(46)
        start.setFixedWidth(300)
        start.setFont(ui_font(14, weight=_bold()))
        start.setStyleSheet(
            f"QPushButton {{ background: {GREEN}; color: white; border: none; border-radius: 8px; font-weight: 700; }}"
            "QPushButton:hover { background: #126833; }"
        )
        start.clicked.connect(self.host._show_setup)
        column.addWidget(start, alignment=Qt.AlignmentFlag.AlignLeft)
        column.addSpacing(8)
        hint = QLabel("Build a new retail chain from the ground up.")
        hint.setStyleSheet("color: #1C2833; font-size: 12px; font-weight: 600; background: transparent;")
        column.addWidget(hint)
        column.addStretch(1)
        quote = QLabel("“Retail isn’t just what happens on the sales floor.\nIt’s every decision behind it.”")
        quote.setStyleSheet("color: white; font-size: 14px; font-weight: 600; background: transparent;")
        sign = QLabel("—  BACK OFFICE: RETAIL")
        sign.setStyleSheet("color: rgba(255,255,255,0.88); font-size: 11px; letter-spacing: 0.8px; font-weight: 700; background: transparent;")
        column.addWidget(quote)
        column.addSpacing(6)
        column.addWidget(sign)
        return side

    def _companies(self) -> QWidget:
        card = QFrame()
        card.setObjectName("launchCompanies")
        card.setStyleSheet(
            f"QFrame#launchCompanies {{ background: #FFFFFF; border: 1px solid #E6EBF0; border-radius: 16px; }}"
        )
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(10, 20, 30, 70))
        card.setGraphicsEffect(shadow)
        column = QVBoxLayout(card)
        column.setContentsMargins(16, 14, 16, 14)
        column.setSpacing(10)
        head = QHBoxLayout()
        head.setSpacing(8)
        building = _Glyph("stores")
        heading = QLabel("Your Companies")
        heading.setStyleSheet(f"color: {INK}; font-size: 16px; font-weight: 800; background: transparent;")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search saves...")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedHeight(32)
        self.search.setStyleSheet(
            "QLineEdit { background: #FFFFFF; border: 1px solid #D5DCE3; border-radius: 8px; padding: 0 10px; color: #1C2430; }"
        )
        self.search.textChanged.connect(self._fill)
        self.sort = QComboBox()
        self.sort.addItems(["Last Played", "Name", "Day", "Cash"])
        self.sort.setFixedHeight(32)
        self.sort.setFixedWidth(130)
        self.sort.setStyleSheet(
            "QComboBox { background: #FFFFFF; border: 1px solid #D5DCE3; border-radius: 8px; padding: 0 8px; color: #1C2430; }"
        )
        self.sort.currentTextChanged.connect(self._on_sort)
        head.addWidget(building)
        head.addWidget(heading)
        head.addStretch(1)
        head.addWidget(self.search, stretch=1)
        head.addWidget(self.sort)
        column.addLayout(head)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.list_host = QWidget()
        self.list_host.setStyleSheet("background: transparent;")
        self.list_box = QVBoxLayout(self.list_host)
        self.list_box.setContentsMargins(0, 0, 0, 0)
        self.list_box.setSpacing(8)
        self.list_box.addStretch(1)
        scroll.setWidget(self.list_host)
        column.addWidget(scroll, stretch=1)
        return card

    def _footer(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(42)
        bar.setStyleSheet(f"background: {GREEN_DEEP};")
        row = QHBoxLayout(bar)
        row.setContentsMargins(8, 0, 16, 0)
        row.setSpacing(4)
        for text, slot in (
            ("Settings", self._settings),
            ("Help", self.host._help),
            ("Release Notes", self._notes),
        ):
            button = QPushButton(text)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(
                "QPushButton { background: transparent; color: white; border: none; font-weight: 600; padding: 6px 10px; }"
                "QPushButton:hover { color: #D7FFE6; }"
            )
            button.clicked.connect(slot)
            row.addWidget(button)
        row.addStretch(1)
        copy = QLabel("© 2026 Back Office: Retail")
        copy.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 12px; background: transparent;")
        version = QLabel("v0.1")
        version.setStyleSheet("color: white; font-size: 12px; font-weight: 700; background: transparent;")
        row.addWidget(copy)
        row.addSpacing(12)
        row.addWidget(version)
        return bar

    def _on_sort(self, text: str) -> None:
        self._sort = text or "Last Played"
        self._fill()

    def _ordered(self) -> list[tuple]:
        query = self.search.text().strip().lower() if hasattr(self, "search") else ""
        rows = [row for row in self._rows if not query or query in str(row[1]).lower()]
        kind = self._sort
        if kind == "Name":
            rows.sort(key=lambda row: str(row[1]).lower())
        elif kind == "Day":
            rows.sort(key=lambda row: int(row[2]), reverse=True)
        elif kind == "Cash":
            rows.sort(key=lambda row: int(row[3]), reverse=True)
        else:
            rows.sort(key=lambda row: str(row[4]), reverse=True)
        return rows

    def _count(self, slot: str, updated: str) -> int:
        key = (slot, updated)
        if key not in self._counts:
            self._counts[key] = self.host.store.store_count(slot)
        return self._counts[key]

    def _fill(self, *_args) -> None:
        while self.list_box.count():
            item = self.list_box.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        rows = self._ordered()
        photos = [ASSETS / "store-brick.jpg", ASSETS / "store-green.jpg"]
        if not rows and not self.search.text().strip():
            pass
        elif not rows:
            empty = QLabel("No companies match that search.")
            empty.setStyleSheet(f"color: {MUTED}; background: transparent; padding: 12px;")
            self.list_box.addWidget(empty)
        newest = max((str(row[4]) for row in self._rows), default="")
        for index, (slot, name, day, cash, updated) in enumerate(rows):
            last = self._sort == "Last Played" and index == 0 and str(updated) == newest and not self.search.text().strip()
            self.list_box.addWidget(self._company_row(
                slot, name, day, cash, updated,
                photos[index % len(photos)],
                last,
            ))
        self.list_box.addWidget(self._create_card())
        self.list_box.addStretch(1)

    def _company_row(self, slot, name, day, cash, updated, photo: Path, last: bool) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background: #FFFFFF; border: 1px solid #E6EBF0; border-radius: 12px; }"
            + ("QFrame { background: #F3FBF6; border: 1px solid #B7E0C4; }" if last else "")
        )
        row = QHBoxLayout(frame)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(12)
        row.addWidget(_Thumb(photo, last))
        text = QVBoxLayout()
        text.setSpacing(2)
        title = QLabel(str(name))
        title.setStyleSheet(f"color: {INK}; font-size: 15px; font-weight: 800; background: transparent; border: none;")
        meta = QLabel(f"Day {day}   ·   {money(cash)} cash")
        meta.setStyleSheet(f"color: #3E4C5A; font-size: 12px; background: transparent; border: none;")
        when = QLabel(f"{_stores(self._count(slot, updated))}   ·   {_when(updated)}")
        when.setStyleSheet(f"color: {MUTED}; font-size: 12px; background: transparent; border: none;")
        text.addWidget(title)
        text.addWidget(meta)
        text.addWidget(when)
        row.addLayout(text, stretch=1)
        resume = QPushButton("  Continue")
        resume.setIcon(_play_icon(white=last))
        resume.setIconSize(QSize(12, 12))
        resume.setCursor(Qt.CursorShape.PointingHandCursor)
        resume.setFixedHeight(36)
        resume.setFixedWidth(124)
        if last:
            resume.setStyleSheet(
                f"QPushButton {{ background: {GREEN}; color: white; border: none; border-radius: 8px; font-weight: 700; }}"
                "QPushButton:hover { background: #126833; }"
            )
        else:
            resume.setStyleSheet(
                f"QPushButton {{ background: white; color: {GREEN}; border: 1px solid #C9D4CE; border-radius: 8px; font-weight: 700; }}"
                "QPushButton:hover { background: #F3FBF6; }"
            )
        resume.clicked.connect(lambda _=False, key=slot: self.host._load(key))
        more = QPushButton()
        more.setIcon(_dots_icon())
        more.setCursor(Qt.CursorShape.PointingHandCursor)
        more.setFixedSize(32, 36)
        more.setStyleSheet(
            "QPushButton { background: white; color: #1C2430; border: 1px solid #E3E8EE; border-radius: 8px; font-weight: 700; }"
            "QPushButton:hover { background: #F4F7F5; }"
        )
        more.clicked.connect(lambda _=False, key=slot, shop=str(name), button=more: self._open_menu(button, key, shop))
        row.addWidget(resume)
        row.addWidget(more)
        return frame

    def _create_card(self) -> QFrame:
        frame = QFrame()
        frame.setCursor(Qt.CursorShape.PointingHandCursor)
        frame.setStyleSheet(
            "QFrame { background: #FFFFFF; border: 1px dashed #C5D0C8; border-radius: 12px; }"
        )
        row = QHBoxLayout(frame)
        row.setContentsMargins(14, 12, 14, 12)
        row.setSpacing(10)
        plus = QLabel("+")
        plus.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        plus.setStyleSheet(f"color: {GREEN}; font-size: 22px; font-weight: 700; background: transparent; border: none;")
        text = QVBoxLayout()
        text.setSpacing(1)
        title = QLabel("Create Another Company")
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        title.setStyleSheet(f"color: {GREEN}; font-size: 14px; font-weight: 800; background: transparent; border: none;")
        body = QLabel("Start a new game with a different strategy, market or difficulty.")
        body.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        body.setStyleSheet(f"color: {MUTED}; font-size: 12px; background: transparent; border: none;")
        text.addWidget(title)
        text.addWidget(body)
        row.addWidget(plus)
        row.addLayout(text)
        frame.mousePressEvent = lambda _event: self.host._show_setup()  # noqa: E731
        return frame

    def _open_menu(self, button: QPushButton, slot: str, name: str) -> None:
        menu = _RowMenu(self.host, slot, name)
        menu.adjustSize()
        point = button.mapToGlobal(button.rect().bottomRight())
        menu.move(point.x() - menu.width(), point.y() + 4)
        menu.show()

    def _settings(self) -> None:
        QMessageBox.information(
            self.host,
            "Settings",
            "Hours, the floor, and the week live inside a company, under Daily Operations.",
        )

    def _notes(self) -> None:
        QMessageBox.information(
            self.host,
            "Release Notes",
            "v0.1 — The company launcher, the office, and the week on the floor.",
        )


def _bold():
    from PySide6.QtGui import QFont
    return QFont.Weight.Bold
