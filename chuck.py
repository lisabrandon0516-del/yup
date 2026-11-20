"""Check Out Chuck. He repeats the notes a manager already has, and he waits for the click."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QImage, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

PHOTO = Path(__file__).resolve().parent.parent / "assets" / "chuck" / "check_out_chuck.png"
CLEAR = "The desk is clear."
_FACE: QPixmap | None = None


def portrait() -> QPixmap:
    """The original file, with the flat black backdrop left out of the drawing."""
    global _FACE
    if _FACE is None:
        _FACE = _cutout(QPixmap(str(PHOTO)))
    return _FACE


def _cutout(source: QPixmap) -> QPixmap:
    if source.isNull():
        return source
    image = source.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    width = image.width()
    height = image.height()
    if width < 2 or height < 2:
        return source
    seen = bytearray(width * height)
    stack: list[tuple[int, int]] = []

    def push(x: int, y: int) -> None:
        index = y * width + x
        if seen[index]:
            return
        color = image.pixelColor(x, y)
        if color.alpha() > 0 and color.red() + color.green() + color.blue() >= 42:
            return
        seen[index] = 1
        stack.append((x, y))

    for x in range(width):
        push(x, 0)
        push(x, height - 1)
    for y in range(height):
        push(0, y)
        push(width - 1, y)
    while stack:
        x, y = stack.pop()
        image.setPixelColor(x, y, QColor(0, 0, 0, 0))
        if x > 0:
            push(x - 1, y)
        if x + 1 < width:
            push(x + 1, y)
        if y > 0:
            push(x, y - 1)
        if y + 1 < height:
            push(x, y + 1)
    return QPixmap.fromImage(image)


def notes(state) -> list[str]:
    """Urgent inbox, empty shelf, compare line, then the public rival move."""
    return [text for text, _desk in destinations(state)]


def destinations(state) -> list[tuple[str, str]]:
    """Each note, and the desk that already owns it."""
    if state is None:
        return []
    rows: list[tuple[str, str]] = []
    rows.extend((line, "journal") for line in _urgent(state))
    rows.extend((line, "inventory") for line in _shelves(state))
    rows.extend((line, "decide") for line in _compare(state))
    rows.extend((line, "visiondeck") for line in _rival(state))
    return rows


def _urgent(state) -> list[str]:
    found = []
    for message in getattr(state, "inbox", []) or []:
        if getattr(message, "resolved", False) or not getattr(message, "urgent", False):
            continue
        title = str(getattr(message, "title", "") or "").strip()
        if title:
            found.append(title)
    return found


def _shelves(state) -> list[str]:
    try:
        from open_late.visiondeck.persistence import stored_alerts
        from open_late.visiondeck.signals import stockout_alerts

        alerts = stockout_alerts(state, prior=stored_alerts(state))
    except Exception:
        return []
    return [str(alert.evidence).strip() for alert in alerts if str(getattr(alert, "evidence", "") or "").strip()]


def _compare(state) -> list[str]:
    try:
        from open_late.visiondeck.signals import remembered

        alerts = [item for item in remembered(state) if item.kind == "stockout_pressure" and item.recommendations]
    except Exception:
        return []
    if not alerts:
        return []
    return [f"Compare responses for {alerts[0].category}."]


def _rival(state) -> list[str]:
    try:
        from open_late.visiondeck.rivals import public_rival_alert

        alert = public_rival_alert(state)
    except Exception:
        return []
    if alert is None:
        return []
    text = str(getattr(alert, "text", "") or "").strip()
    return [text] if text else []


class ChuckButton(QWidget):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("chuckHost")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        self.button = QPushButton()
        self.button.setObjectName("chuckButton")
        self.button.setToolTip("Check Out Chuck")
        self.button.setAccessibleName("Check Out Chuck")
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.setFixedSize(36, 36)
        self.button.setStyleSheet("QPushButton#chuckButton { background: transparent; border: none; }")
        face = portrait()
        if not face.isNull():
            self.button.setIcon(QIcon(face))
            self.button.setIconSize(QSize(32, 32))
        self.button.clicked.connect(self.clicked.emit)
        self.mark = QLabel(self.button)
        self.mark.setObjectName("chuckMark")
        self.mark.setFixedSize(8, 8)
        self.mark.move(26, 2)
        self.mark.setStyleSheet("QLabel#chuckMark { background: #E23B3B; border-radius: 4px; }")
        self.mark.hide()
        row.addWidget(self.button)

    def set_waiting(self, waiting: bool) -> None:
        self.mark.setVisible(bool(waiting))


class ChuckNote(QLabel):
    """One of Chuck's lines. The click opens the desk that already owns it."""

    pressed = Signal(str)

    def __init__(self, text: str, desk: str, parent=None):
        super().__init__(text, parent)
        self.desk = desk
        self.setObjectName("chuckNote")
        self.setWordWrap(True)
        self.setFixedWidth(280)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event) -> None:
        self.pressed.emit(self.desk)
        super().mousePressEvent(event)


class ChuckOverlay(QWidget):
    """Chuck and his text box, drawn on the open desk. No second window."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("chuckOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)
        if parent is not None:
            parent.installEventFilter(self)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 18, 12)
        row.setSpacing(10)
        self.box = QFrame()
        self.box.setObjectName("chuckBox")
        self.box.setStyleSheet(
            "QFrame#chuckBox { background: #050605; border: 2px solid #39FF14; border-radius: 16px; }"
            "QLabel#chuckName { color: #39FF14; background: transparent; font-size: 15px; font-weight: 800; }"
            "QLabel#chuckBody, QLabel#chuckNote { color: #F4FFF4; background: transparent; font-size: 13px; }"
            "QLabel#chuckNote { border-top: 1px solid #39FF14; padding-top: 6px; }"
            "QPushButton#chuckClose { color: #39FF14; background: #050605; border: 1px solid #39FF14;"
            " border-radius: 9px; padding: 0 6px; font-weight: 700; }"
        )
        column = QVBoxLayout(self.box)
        column.setContentsMargins(14, 12, 14, 12)
        column.setSpacing(6)
        self.name = QLabel("Check Out Chuck")
        self.name.setObjectName("chuckName")
        column.addWidget(self.name)
        self.body = QLabel(CLEAR)
        self.body.setObjectName("chuckBody")
        self.body.setWordWrap(True)
        self.body.setFixedWidth(280)
        column.addWidget(self.body)
        close = QPushButton("×")
        close.setObjectName("chuckClose")
        close.setFixedSize(22, 22)
        close.clicked.connect(self.hide)
        column.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        row.addWidget(self.box, alignment=Qt.AlignmentFlag.AlignBottom)
        self.photo = QLabel()
        self.photo.setObjectName("chuckPhoto")
        self.photo.setStyleSheet("background: transparent;")
        face = portrait()
        if not face.isNull():
            shown = face.scaled(280, 340, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.photo.setPixmap(shown)
            self.photo.setFixedSize(shown.size())
        row.addWidget(self.photo, alignment=Qt.AlignmentFlag.AlignBottom)
        self._notes: list[ChuckNote] = []
        self._opener = None
        self.hide()

    def set_lines(self, lines: list[str]) -> None:
        self.set_notes([(line, "") for line in lines])

    def set_notes(self, rows: list[tuple[str, str]], opener=None) -> None:
        self._opener = opener
        lines = [text for text, _desk in rows if text]
        self.body.setText("\n".join(lines) if lines else CLEAR)
        self.body.setFixedHeight(self.body.heightForWidth(280))
        self.body.setVisible(not any(desk for _text, desk in rows))
        for note in self._notes:
            note.setParent(None)
            note.deleteLater()
        self._notes = []
        column = self.box.layout()
        for text, desk in rows:
            if not text or not desk:
                continue
            note = ChuckNote(text, desk, self.box)
            note.pressed.connect(self._open_note)
            column.insertWidget(max(0, column.count() - 1), note)
            self._notes.append(note)

    def _open_note(self, desk: str) -> None:
        opener = self._opener
        if opener is None or not desk:
            return
        self.hide()
        opener(str(desk))

    def reveal(self) -> None:
        self.adjustSize()
        self.place()
        self.show()
        self.raise_()

    def place(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        self.move(max(0, parent.width() - self.width() - 8), max(0, parent.height() - self.height() - 8))

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.Resize and self.isVisible():
            self.place()
        return False
