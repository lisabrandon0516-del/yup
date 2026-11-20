"""Department floor plan: the fixture map beside the selected shelf."""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from open_late.text import money

from open_late.ui.theme import FRAME, FRAME_BTN, FRAME_BTN_LINE, FRAME_INK

PANEL = "#0E2035"
LINE = "#173A55"
TEXT = "#F4F8FF"
MUTED = "#7897AE"
_WIDTHS = {"gondola": 3, "cooler": 3, "cooler_well": 3, "peg": 3, "endcap": 3, "table": 6, "rack": 4}
_LABELS = {
    "meat_dairy": "Meat & Dairy",
    "health_beauty": "Health & Beauty",
    "home_garden": "Home & Garden",
    "clothing": "Apparel",
}
_DEPT = {
    "produce": "#3FAE63",
    "grocery": "#C59A45",
    "meat_dairy": "#C65B67",
    "frozen": "#3B8FD1",
    "household": "#3FA7A2",
    "health_beauty": "#8F5BC1",
    "pharmacy": "#2FA6A1",
    "electronics": "#367DCE",
    "clothing": "#B76FAF",
    "toys": "#BA5AAE",
    "home_garden": "#8B7E63",
    "sporting": "#4E9B73",
    "seasonal": "#D2574E",
}
_PACKS = ("#E24B4B", "#F0C419", "#3FAE63", "#3B8FD1", "#E07A3D", "#8F5BC1", "#F4F1EA", "#C65B67")
_TIER_ORDER = ("top", "eye", "hand", "well", "bottom")
_TIER_LABEL = {"top": "Top", "eye": "Eye", "hand": "", "well": "", "bottom": "Bottom"}
# Photo floor, in draw order: right wall, left wall, top run, center runs, bottom run.
_PHOTO = (
    (0.915, 0.02, 0.062, 0.95, True, 60),
    (0.018, 0.02, 0.058, 0.58, True, 20),
    (0.22, 0.02, 0.42, 0.09, False, 26),
    (0.13, 0.14, 0.32, 0.085, False, 12),
    (0.50, 0.14, 0.36, 0.085, False, 12),
    (0.13, 0.255, 0.34, 0.085, False, 12),
    (0.52, 0.255, 0.34, 0.085, False, 20),
    (0.13, 0.37, 0.30, 0.085, False, 12),
    (0.50, 0.37, 0.36, 0.085, False, 20),
    (0.15, 0.485, 0.30, 0.085, False, 12),
    (0.52, 0.485, 0.32, 0.085, False, 20),
    (0.16, 0.60, 0.28, 0.08, False, 12),
    (0.50, 0.60, 0.36, 0.08, False, 20),
    (0.28, 0.72, 0.22, 0.075, False, 8),
    (0.13, 0.855, 0.74, 0.10, False, 32),
)


def paint_package_face(painter: QPainter, rect, product) -> None:
    """A package front: the product color, its name, and its size."""
    from open_late.ui.hq_product import _hue, product_size, product_title

    box = rect if isinstance(rect, QRectF) else QRectF(rect)
    if box.width() < 4 or box.height() < 4 or product is None:
        return
    color = _hue(product)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    painter.drawRoundedRect(box, 3, 3)
    painter.setBrush(color.darker(125))
    painter.drawRoundedRect(QRectF(box.left(), box.top(), box.width(), max(3.0, box.height() * 0.16)), 2, 2)
    label = QRectF(box.left() + 4, box.top() + box.height() * 0.22, box.width() - 8, box.height() * 0.70)
    if label.width() < 8 or label.height() < 8:
        painter.setBrush(QColor("#F7F4EE"))
        painter.drawRect(QRectF(box.left() + 1, box.center().y() - 1, box.width() - 2, 3))
        return
    painter.setBrush(QColor("#F7F4EE"))
    painter.drawRoundedRect(label, 3, 3)
    painter.setPen(QColor("#1A140C"))
    font = painter.font()
    font.setBold(True)
    font.setPixelSize(16 if box.height() >= 80 else 13 if box.height() >= 48 else 9)
    painter.setFont(font)
    title = product_title(product)
    size = product_size(product)
    name_box = label.adjusted(4, 3, -4, -16 if size else -4)
    painter.drawText(name_box, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, title)
    if size:
        font.setBold(False)
        font.setPixelSize(max(8, font.pixelSize() - 4))
        painter.setFont(font)
        painter.setPen(QColor("#5C5348"))
        painter.drawText(QRectF(label.left(), label.bottom() - 16, label.width(), 15), Qt.AlignmentFlag.AlignCenter, size)


def _name(raw: str) -> str:
    key = str(raw or "")
    if key in _LABELS:
        return _LABELS[key]
    return key.replace("_", " ").title() or "General"


@dataclass
class Run:
    key: str
    dept: str
    title: str
    role: str
    feet: int
    bays: list = field(default_factory=list)

    @property
    def shelf_bay(self):
        return next((bay for bay in self.bays if not getattr(bay, "is_feature", False)), self.bays[0] if self.bays else None)


class _MapZone(QGraphicsRectItem):
    """One room or aisle. A click reports that zone and nothing else."""

    def __init__(self, owner, ident: str, text: str, size: int, ink: str):
        super().__init__()
        self.owner = owner
        self.ident = ident
        self.label = text
        self.word_size = size
        self.ink = QColor(ink)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setAcceptHoverEvents(True)
        self.setZValue(3)

    def hoverEnterEvent(self, event):
        self.owner._show_name(self)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.owner._hide_name()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        self.owner._pick(self.ident)
        event.accept()

    def paint(self, painter: QPainter, _option, _widget=None) -> None:
        rect = self.rect()
        color = self.brush().color()
        picked = self.ident == self.owner.picked
        edge = QColor("#19E86A") if picked else QColor("#081018")
        if _aisle_code(self.ident):
            _paint_aisle(painter, rect, color, edge, self.label)
            return
        if self.ident.startswith("lane"):
            _paint_register(painter, rect, edge)
            return
        if self.ident in ("self-left", "self-right"):
            _paint_self_checkout(painter, rect, edge, self.label)
            return
        if self.ident == "entrance":
            _paint_entrance(painter, rect, edge)
            return
        painter.setPen(QPen(QColor("#48D840") if self.ident in _DARK_ROOMS and not picked else edge, 2 if picked else 1.4))
        painter.setBrush(color)
        painter.drawRoundedRect(rect, 5, 5)
        words = rect.adjusted(3, 2, -3, -2)
        if rect.height() > 36 and rect.width() > 30:
            icon = QRectF(rect.left(), rect.top() + 3, rect.width(), min(rect.height() * 0.42, 36))
            _paint_mark(painter, self.ident, icon)
            words = QRectF(rect.left() + 3, icon.bottom(), rect.width() - 6, max(12.0, rect.bottom() - icon.bottom() - 2))
        painter.setPen(QColor("#FFFFFF"))
        face = QFont()
        face.setBold(True)
        face.setPixelSize(max(9, min(18, int(min(words.width(), words.height()) * 0.34))))
        painter.setFont(face)
        painter.drawText(words, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self.label)


class _HoverName(QGraphicsRectItem):
    """A readable name that sits beside the block under the pointer."""

    def __init__(self):
        super().__init__()
        self.words = ""
        self.setZValue(20)
        self.setBrush(QBrush(QColor("#071018")))
        self.setPen(QPen(QColor("#48D840"), 1))
        self.hide()

    def place(self, text: str, anchor: QRectF, bounds: QRectF) -> None:
        self.words = text
        face = QFont()
        face.setBold(True)
        face.setPixelSize(14)
        width = QFontMetrics(face).horizontalAdvance(text) + 16
        self.setRect(0, 0, width, 26)
        x = anchor.right() + 6
        y = anchor.center().y() - 13
        if x + width > bounds.right() - 4:
            x = anchor.left() - width - 6
        y = min(max(bounds.top() + 4, y), bounds.bottom() - 30)
        self.setPos(x, y)
        self.show()
        self.update()

    def paint(self, painter: QPainter, _option, _widget=None) -> None:
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        painter.drawRoundedRect(self.rect(), 4, 4)
        painter.setPen(QColor("#FFFFFF"))
        face = QFont()
        face.setBold(True)
        face.setPixelSize(14)
        painter.setFont(face)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.words)


class _CharcoalFloor(QGraphicsRectItem):
    def paint(self, painter: QPainter, _option, _widget=None) -> None:
        _paint_charcoal(painter, self.rect())


class _StoreFrame(QGraphicsRectItem):
    """Cyan glow outside the store, then the bright edge and the dark wall."""

    def __init__(self, store: QRectF):
        super().__init__(store.adjusted(-24, -24, 24, 24))
        self.store = QRectF(store)
        self.setPen(QPen(Qt.PenStyle.NoPen))
        self.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self.setZValue(2)

    def paint(self, painter: QPainter, _option, _widget=None) -> None:
        store = self.store
        painter.save()
        outside = QPainterPath()
        outside.addRect(self.rect().adjusted(-4, -4, 4, 4))
        hole = QPainterPath()
        hole.addRoundedRect(store, 14, 14)
        title = QPainterPath()
        title.addRect(QRectF(store.right() - 224, 4, 228, 32))
        painter.setClipPath(outside.subtracted(hole).subtracted(title))
        painter.setPen(Qt.PenStyle.NoPen)
        for pad, hex_color, alpha in (
            (22.0, "#2A8A24", 90),
            (16.0, "#3AD040", 140),
            (11.0, "#48D840", 185),
            (7.0, "#6EF060", 220),
            (4.0, "#C8FFC0", 245),
        ):
            color = QColor(hex_color)
            color.setAlpha(alpha)
            painter.setBrush(color)
            painter.drawRoundedRect(store.adjusted(-pad, -pad, pad, pad), 14 + pad, 14 + pad)
        painter.restore()
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#D8D8D8"), 5))
        painter.drawRoundedRect(store, 14, 14)
        painter.setPen(QPen(QColor("#070707"), 8))
        painter.drawRoundedRect(store.adjusted(6.5, 6.5, -6.5, -6.5), 8, 8)


def _store_rect(width: float, height: float) -> QRectF:
    margin = 16.0
    header = 36.0
    avail = QRectF(margin, header, max(80.0, width - margin * 2), max(80.0, height - header - margin))
    aspect = 1.72
    if avail.width() / avail.height() > aspect:
        wide = avail.height() * aspect
        return QRectF(avail.center().x() - wide / 2, avail.top(), wide, avail.height())
    tall = avail.width() / aspect
    return QRectF(avail.left(), avail.center().y() - tall / 2, avail.width(), tall)


_DARK_ROOMS = {"receiving", "vision", "service", "restrooms"}


def _aisle_code(ident: str) -> bool:
    text = str(ident or "")
    return len(text) >= 2 and text[0].isalpha() and text[1:].isdigit()


def _shade(color: QColor, factor: float) -> QColor:
    return QColor(
        max(0, min(255, int(color.red() * factor))),
        max(0, min(255, int(color.green() * factor))),
        max(0, min(255, int(color.blue() * factor))),
    )


def _paint_aisle(painter: QPainter, rect: QRectF, color: QColor, edge: QColor, label: str) -> None:
    code, _, name = label.partition("\n")
    cap_h = max(14.0, min(22.0, rect.height() * 0.22))
    cap = QRectF(rect.left(), rect.top(), rect.width(), cap_h)
    body = QRectF(rect.left(), rect.top() + cap_h, rect.width(), max(4.0, rect.height() - cap_h))
    painter.setPen(QPen(edge, 1))
    painter.setBrush(color)
    painter.drawRect(cap)
    painter.setBrush(QColor(int(color.red() * 0.22 + 48), int(color.green() * 0.22 + 48), int(color.blue() * 0.22 + 54)))
    painter.drawRect(body)
    painter.setPen(QColor("#FFFFFF"))
    _draw_fitted(painter, cap.adjusted(1, 0, -1, 0), code, 12)
    painter.save()
    painter.translate(body.center())
    painter.rotate(-90)
    spun = QRectF(-body.height() / 2 + 1, -body.width() / 2, body.height() - 2, body.width())
    _draw_fitted(painter, spun, name, 13, one_line=True)
    painter.restore()


def _draw_fitted(painter: QPainter, rect: QRectF, text: str, largest: int, one_line: bool = False) -> None:
    """Center the words, shrinking a condensed face until the longest word fits the block."""
    words = [part for part in str(text).replace("\n", " ").split() if part]
    block = " ".join(words) if one_line else ("\n".join(words) if words else str(text))
    longest = block if one_line else (max(words, key=len) if words else str(text))
    face = QFont()
    face.setBold(True)
    face.setStretch(70)
    size = largest
    face.setPixelSize(size)
    painter.setFont(face)
    while size > 6 and painter.fontMetrics().horizontalAdvance(longest) > rect.width() - 1:
        size -= 1
        face.setPixelSize(size)
        painter.setFont(face)
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, block)


def _paint_register(painter: QPainter, rect: QRectF, edge: QColor) -> None:
    stand = QRectF(rect.left(), rect.top(), rect.width(), rect.height() * 0.62)
    painter.setPen(QPen(edge, 1))
    painter.setBrush(QColor("#1A3E72"))
    painter.drawRoundedRect(stand, 2, 2)
    screen = QRectF(stand.left() + 2, stand.top() + 2, stand.width() - 4, stand.height() * 0.48)
    painter.setBrush(QColor("#48D840"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRect(screen)
    painter.setBrush(QColor("#0C1828"))
    painter.drawRoundedRect(QRectF(stand.left() + 2, stand.bottom() - 5, stand.width() - 4, 4), 1, 1)
    post = QRectF(rect.center().x() - 1.5, stand.bottom() + 2, 3, rect.bottom() - stand.bottom() - 2)
    painter.setBrush(QColor("#C8D0DA"))
    painter.drawRect(post)
    painter.setPen(QPen(QColor("#C8D0DA"), 2))
    painter.drawLine(QPointF(rect.left(), rect.bottom() - 2), QPointF(rect.right(), rect.bottom() - 2))


def _paint_kiosk(painter: QPainter, rect: QRectF) -> None:
    painter.setPen(QPen(QColor("#081018"), 1))
    painter.setBrush(QColor("#1A4E9A"))
    painter.drawRoundedRect(rect, 3, 3)
    screen = QRectF(rect.left() + 3, rect.top() + 3, rect.width() - 6, rect.height() * 0.58)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#48D840"))
    painter.drawRoundedRect(screen, 2, 2)
    painter.setBrush(QColor("#0C1828"))
    painter.drawRect(QRectF(rect.left() + 4, rect.bottom() - 6, rect.width() - 8, 3))


def _paint_self_checkout(painter: QPainter, rect: QRectF, edge: QColor, label: str) -> None:
    bar_h = max(16.0, rect.height() * 0.30)
    bar = QRectF(rect.left(), rect.top(), rect.width(), bar_h)
    painter.setPen(QPen(edge, 1))
    painter.setBrush(QColor("#2F6FE0"))
    painter.drawRoundedRect(bar, 4, 4)
    painter.setPen(QColor("#FFFFFF"))
    face = QFont()
    face.setBold(True)
    face.setPixelSize(max(9, min(14, int(bar.height() * 0.55))))
    painter.setFont(face)
    painter.drawText(bar, Qt.AlignmentFlag.AlignCenter, label)
    bay = QRectF(rect.left() + 2, bar.bottom() + 4, rect.width() - 4, max(8.0, rect.height() - bar_h - 6))
    gap = max(4.0, bay.width() * 0.08)
    width = (bay.width() - gap) / 2
    _paint_kiosk(painter, QRectF(bay.left(), bay.top(), width, bay.height()))
    _paint_kiosk(painter, QRectF(bay.left() + width + gap, bay.top(), width, bay.height()))


def _paint_entrance(painter: QPainter, rect: QRectF, edge: QColor) -> None:
    doors = QRectF(rect.left() + rect.width() * 0.18, rect.top(), rect.width() * 0.64, rect.height() * 0.58)
    painter.setPen(QPen(QColor("#48D840"), 2))
    painter.setBrush(QColor("#0C2410"))
    painter.drawRoundedRect(doors, 2, 2)
    painter.drawLine(QPointF(doors.center().x(), doors.top() + 2), QPointF(doors.center().x(), doors.bottom() - 2))
    label = QRectF(rect.left(), doors.bottom() + 4, rect.width(), max(14.0, rect.bottom() - doors.bottom() - 4))
    painter.setPen(QPen(edge, 1))
    painter.setBrush(QColor("#1E6FE0"))
    painter.drawRoundedRect(label, 4, 4)
    painter.setPen(QColor("#FFFFFF"))
    face = QFont()
    face.setBold(True)
    face.setPixelSize(max(9, min(14, int(label.height() * 0.6))))
    painter.setFont(face)
    painter.drawText(label, Qt.AlignmentFlag.AlignCenter, "Enter / Exit")


def _paint_mark(painter: QPainter, ident: str, area: QRectF) -> None:
    side = min(area.width() * 0.55, area.height() * 0.9)
    if side < 8:
        return
    box = QRectF(area.center().x() - side / 2, area.center().y() - side / 2, side, side)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QPen(QColor("#FFFFFF"), max(1.4, side * 0.08), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    if ident == "pharmacy":
        painter.drawLine(QPointF(box.center().x(), box.top()), QPointF(box.center().x(), box.bottom()))
        painter.drawLine(QPointF(box.left(), box.center().y()), QPointF(box.right(), box.center().y()))
    elif ident == "bakery":
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(box.adjusted(0, side * 0.28, 0, 0))
    elif ident == "deli":
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawRoundedRect(box.adjusted(side * 0.08, side * 0.35, -side * 0.08, -side * 0.2), 3, 3)
        painter.drawEllipse(QRectF(box.left() + side * 0.15, box.top() + side * 0.12, side * 0.7, side * 0.28))
    elif ident == "produce":
        painter.drawEllipse(box.adjusted(side * 0.05, side * 0.2, -side * 0.35, -side * 0.15))
        painter.drawEllipse(box.adjusted(side * 0.35, side * 0.05, -side * 0.05, -side * 0.35))
    elif ident == "meat":
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(box.adjusted(side * 0.12, side * 0.28, -side * 0.2, -side * 0.28))
    elif ident == "health":
        painter.drawRoundedRect(box.adjusted(side * 0.12, side * 0.15, -side * 0.55, 0), 2, 2)
        painter.drawRoundedRect(box.adjusted(side * 0.55, side * 0.15, -side * 0.12, 0), 2, 2)
    elif ident == "home":
        painter.drawLine(QPointF(box.left(), box.center().y()), QPointF(box.center().x(), box.top()))
        painter.drawLine(QPointF(box.center().x(), box.top()), QPointF(box.right(), box.center().y()))
        painter.drawRect(box.adjusted(side * 0.18, side * 0.48, -side * 0.18, 0))
    elif ident == "cosmetics":
        painter.drawRoundedRect(QRectF(box.center().x() - side * 0.12, box.top() + side * 0.35, side * 0.24, side * 0.5), 1, 1)
        painter.drawLine(QPointF(box.center().x(), box.top()), QPointF(box.center().x(), box.top() + side * 0.35))
    elif ident == "personal":
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(QRectF(box.left(), box.top() + side * 0.15, side * 0.55, side * 0.5))
        painter.drawEllipse(QRectF(box.left() + side * 0.4, box.top() + side * 0.15, side * 0.55, side * 0.5))
    elif ident == "pet":
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(box.adjusted(side * 0.28, side * 0.35, -side * 0.28, -side * 0.15))
        for dx, dy in ((0.05, 0.05), (0.7, 0.05), (0.0, 0.35), (0.75, 0.35)):
            painter.drawEllipse(QRectF(box.left() + side * dx, box.top() + side * dy, side * 0.22, side * 0.22))
    elif ident == "vision":
        painter.drawEllipse(box.adjusted(0, side * 0.3, -side * 0.48, -side * 0.3))
        painter.drawEllipse(box.adjusted(side * 0.48, side * 0.3, 0, -side * 0.3))
    elif ident == "receiving":
        painter.drawRect(box.adjusted(0, side * 0.35, -side * 0.25, -side * 0.15))
        painter.drawRect(box.adjusted(side * 0.55, side * 0.2, 0, -side * 0.35))
    elif ident == "restrooms":
        painter.drawEllipse(QRectF(box.left() + side * 0.12, box.top(), side * 0.22, side * 0.22))
        painter.drawEllipse(QRectF(box.right() - side * 0.34, box.top(), side * 0.22, side * 0.22))
        painter.drawLine(QPointF(box.left() + side * 0.23, box.top() + side * 0.24), QPointF(box.left() + side * 0.23, box.bottom()))
        painter.drawLine(QPointF(box.right() - side * 0.23, box.top() + side * 0.24), QPointF(box.right() - side * 0.23, box.bottom()))
    elif ident == "service":
        painter.drawEllipse(box.adjusted(side * 0.15, side * 0.05, -side * 0.15, -side * 0.05))
        face = QFont()
        face.setBold(True)
        face.setPixelSize(max(8, int(side * 0.55)))
        painter.setFont(face)
        painter.drawText(box, Qt.AlignmentFlag.AlignCenter, "i")
    painter.restore()


def _paint_charcoal(painter: QPainter, rect: QRectF) -> None:
    """Near-black floor with a fine cool grid, matching the store picture."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    painter.fillRect(rect, QColor("#050505"))
    painter.setPen(QPen(QColor("#163816"), 1))
    step = 5.0
    x = rect.left()
    while x <= rect.right():
        painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
        x += step
    y = rect.top()
    while y <= rect.bottom():
        painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
        y += step
    painter.restore()


class DeptFloorCanvas(QGraphicsView):
    runPicked = Signal(str)
    LEGEND = (
        ("Gondola", "#35566F"),
        ("Endcap", "#F4C84A"),
        ("Wall Run", "#3FAE63"),
        ("Cooler/Freezer", "#3B8FD1"),
        ("Promotional Display", "#D2574E"),
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("deptFloorCanvas")
        self.runs: list[Run] = []
        self.products = {}
        self.selected = ""
        self.zoom = 100
        self.hits: list[tuple[QRectF, str]] = []
        self.city = ""
        self.state = ""
        self.number = ""
        self.picked = ""
        self._zones: list[_MapZone] = []
        self._name_chip: _HoverName | None = None
        self._map = QGraphicsScene(self)
        self.setScene(self._map)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setBackgroundBrush(QColor("#050505"))
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.setMinimumHeight(220)

    def set_store(self, city: str, state: str, number: str) -> None:
        self.city = str(city or "")
        self.state = str(state or "")
        self.number = str(number or "")
        self._rebuild()

    def set_plan(self, runs, selected: str, products=None) -> None:
        self.runs = list(runs or [])
        self.selected = str(selected or "")
        if products is not None:
            self.products = dict(products)
        self.viewport().update()

    def set_zoom(self, value: int) -> None:
        self.zoom = max(70, min(160, int(value)))
        self._apply_zoom()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rebuild()

    def showEvent(self, event):
        super().showEvent(event)
        self._rebuild()

    def _pick(self, ident: str) -> None:
        self.picked = ident
        self.selected = ident
        for zone in self._zones:
            zone.update()
        self.runPicked.emit(ident)

    def _show_name(self, zone: _MapZone) -> None:
        if self._name_chip is None:
            return
        self._name_chip.place(zone.label.replace("\n", " "), zone.sceneBoundingRect(), self._map.sceneRect())

    def _hide_name(self) -> None:
        if self._name_chip is not None:
            self._name_chip.hide()

    def _apply_zoom(self) -> None:
        self.resetTransform()
        if self.zoom != 100:
            self.scale(self.zoom / 100.0, self.zoom / 100.0)

    def _rebuild(self) -> None:
        width = self.viewport().width()
        height = self.viewport().height()
        if width < 40 or height < 40:
            return
        self._map.clear()
        self._zones = []
        self._map.setSceneRect(0, 0, width, height)
        store = _store_rect(width, height)
        floor = store.adjusted(7, 7, -7, -7)
        ground = _CharcoalFloor(floor)
        ground.setPen(QPen(Qt.PenStyle.NoPen))
        ground.setZValue(1)
        self._map.addItem(ground)
        self._map.addItem(_StoreFrame(store))
        place = ", ".join(part for part in (self.city.upper(), self.state.upper()) if part) or "YOUR STORE"
        number = f"STORE #{self.number}" if self.number else "STORE"
        self._title(number, 14, store.right() - 220, 6, 220)
        self._title(place, 12, store.right() - 220, 20, 220)
        self.hits = []
        for ident, _dept, x, y, w, h, fill, text, size, ink in map_zones():
            rect = QRectF(floor.left() + floor.width() * x, floor.top() + floor.height() * y, floor.width() * w, floor.height() * h)
            zone = _MapZone(self, ident, text, size, ink)
            zone.setToolTip(text.replace("\n", " "))
            zone.setRect(rect)
            zone.setBrush(QBrush(QColor(fill)))
            self._map.addItem(zone)
            self._zones.append(zone)
            self.hits.append((QRectF(rect), ident))
        self._name_chip = _HoverName()
        self._map.addItem(self._name_chip)
        self._apply_zoom()

    def _title(self, text: str, size: int, left: float, top: float, width: float) -> None:
        font = QFont()
        font.setBold(True)
        font.setPixelSize(size)
        item = QGraphicsSimpleTextItem(text)
        item.setFont(font)
        item.setBrush(QBrush(QColor("#D8D8D8")))
        item.setZValue(5)
        item.setPos(left + max(0.0, width - item.boundingRect().width()), top)
        self._map.addItem(item)

    def _charcoal_tiles(self, painter: QPainter, rect: QRectF) -> None:
        _paint_charcoal(painter, rect)

    def _tiles(self, painter, rect: QRectF) -> None:
        painter.fillRect(rect, QColor("#D9D1C2"))
        painter.setPen(QPen(QColor("#C3B9A8"), 1))
        x = rect.left()
        while x < rect.right():
            painter.drawLine(int(x), int(rect.top()), int(x), int(rect.bottom()))
            x += 26
        y = rect.top()
        while y < rect.bottom():
            painter.drawLine(int(rect.left()), int(y), int(rect.right()), int(y))
            y += 26

    def _place(self, painter, area: QRectF) -> None:
        slots = self._slots(area, list(self.runs))
        for run, rect, slot in slots:
            self._fixture(painter, rect, run, vertical=slot in ("left", "right"))
        self._service(painter, area, slots)
        for corner in (area.topLeft(), area.topRight(), area.bottomLeft(), area.bottomRight()):
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#2C6A40"))
            painter.drawEllipse(QRectF(corner.x() + 6, corner.y() + 6, 14, 14))
            painter.setBrush(QColor("#3F8F56"))
            painter.drawEllipse(QRectF(corner.x() + 9, corner.y() + 8, 7, 7))

    def _slots(self, area: QRectF, runs: list[Run]) -> list[tuple[Run, QRectF, str]]:
        slots: list[tuple[Run, QRectF, str]] = []
        for index, run in enumerate(runs):
            if index >= len(_PHOTO):
                break
            x, y, w, h, vertical, _feet = _PHOTO[index]
            rect = QRectF(area.left() + area.width() * x, area.top() + area.height() * y, area.width() * w, area.height() * h)
            if rect.right() > area.right() - 4:
                rect.setRight(area.right() - 4)
            if rect.bottom() > area.bottom() - 4:
                rect.setBottom(area.bottom() - 4)
            kind = "right" if index == 0 else "left" if index == 1 else "bottom" if index == len(_PHOTO) - 1 else "center"
            slots.append((run, rect, kind))
        return slots

    def _service(self, painter, area: QRectF, slots) -> None:
        left = next((rect for _run, rect, slot in slots if slot == "left"), None)
        if left is None:
            return
        pocket = QRectF(area.left() + area.width() * 0.02, left.bottom() + 8, area.width() * 0.18, max(64.0, area.bottom() - left.bottom() - 16))
        painter.setPen(QColor("#3A342C"))
        font = painter.font()
        font.setPixelSize(13)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(pocket.left() + 16, pocket.top(), pocket.width() - 16, 18), Qt.AlignmentFlag.AlignLeft, "Main Store")
        painter.setBrush(QColor("#3A342C"))
        painter.setPen(Qt.PenStyle.NoPen)
        origin = pocket.topLeft()
        painter.drawPolygon([origin + QPointF(4, 16), origin + QPointF(4, 2), origin + QPointF(13, 9)])
        painter.setBrush(QColor("#2A3138"))
        painter.drawRoundedRect(QRectF(pocket.left(), pocket.top() + 24, 28, 22), 3, 3)
        painter.setBrush(QColor("#8C8478"))
        painter.drawRoundedRect(QRectF(pocket.left() + 4, pocket.top() + 40, 18, 4), 1, 1)
        painter.setBrush(QColor("#232A31"))
        painter.drawRoundedRect(QRectF(pocket.left(), pocket.top() + 50, 36, pocket.height() - 56), 2, 2)
        painter.setBrush(QColor("#C8C2B6"))
        painter.drawRect(QRectF(pocket.left() + 4, pocket.center().y() + 8, 28, 4))
        painter.setBrush(QColor("#9A958C"))
        block = QRectF(pocket.left() + 42, pocket.top() + 28, pocket.width() - 48, pocket.height() - 36)
        painter.drawRoundedRect(block, 3, 3)
        painter.setPen(QColor("#F7F4EE"))
        font.setPixelSize(11)
        painter.setFont(font)
        painter.drawText(block.adjusted(4, 2, -4, -2), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, "Back of House\nStock Pallet")

    def _fixture(self, painter, rect: QRectF, run: Run, vertical: bool) -> None:
        from open_late.ui.hq_product import _hue

        selected = run.key == self.selected
        painter.setBrush(QColor("#1A2128"))
        painter.setPen(QPen(QColor("#0B0E12"), 2))
        painter.drawRoundedRect(rect, 4, 4)
        self.hits.append((rect, run.key))
        packages = _run_products(run.bays, self.products)
        painter.setBrush(QColor("#E2B431"))
        painter.setPen(Qt.PenStyle.NoPen)
        if vertical:
            painter.drawRoundedRect(QRectF(rect.left(), rect.top() - 3, rect.width(), max(6.0, rect.height() * 0.03)), 2, 2)
            plate = QRectF(rect.left() + rect.width() * 0.22, rect.top() + 8, rect.width() * 0.56, rect.height() - 16)
            self._packs(painter, QRectF(rect.left() + 2, rect.top() + 8, max(4.0, plate.left() - rect.left() - 3), rect.height() - 14), packages, True, _hue)
            self._packs(painter, QRectF(plate.right() + 1, rect.top() + 8, max(4.0, rect.right() - plate.right() - 3), rect.height() - 14), list(reversed(packages)) or packages, True, _hue)
        else:
            painter.drawRoundedRect(QRectF(rect.left() - 3, rect.top(), max(6.0, rect.width() * 0.03), rect.height()), 2, 2)
            plate_h = max(12.0, min(22.0, rect.height() * 0.42))
            plate = QRectF(rect.left() + 10, rect.center().y() - plate_h / 2, rect.width() - 16, plate_h)
            band = max(4.0, (rect.height() - plate_h) / 2 - 3)
            self._packs(painter, QRectF(rect.left() + 10, rect.top() + 3, rect.width() - 14, band), packages, False, _hue)
            self._packs(painter, QRectF(rect.left() + 10, rect.bottom() - 3 - band, rect.width() - 14, band), list(reversed(packages)) or packages, False, _hue)
        painter.setBrush(QColor("#101418"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(plate, 2, 2)
        font = painter.font()
        font.setBold(True)
        font.setPixelSize(max(9, min(14, int((plate.width() if vertical else plate.height()) * 0.7))))
        painter.setFont(font)
        painter.setPen(QColor("#FFFFFF"))
        if vertical:
            painter.save()
            painter.translate(plate.center())
            painter.rotate(-90)
            spun = QRectF(-plate.height() / 2, -plate.width() / 2, plate.height(), plate.width())
            painter.drawText(spun, Qt.AlignmentFlag.AlignCenter, painter.fontMetrics().elidedText(run.title, Qt.TextElideMode.ElideRight, int(spun.width() - 8)))
            painter.restore()
        else:
            painter.drawText(plate, Qt.AlignmentFlag.AlignCenter, painter.fontMetrics().elidedText(run.title, Qt.TextElideMode.ElideRight, int(plate.width() - 10)))
        if selected:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#19E86A"), 3))
            painter.drawRoundedRect(rect.adjusted(-3, -3, 3, 3), 5, 5)

    def _packs(self, painter, rect: QRectF, products, vertical: bool, hue) -> None:
        if rect.width() < 8 or rect.height() < 8:
            return
        pack_w, pack_h = (14.0, 10.0) if vertical else (16.0, 12.0)
        pitch = (pack_h if vertical else pack_w) + 3.0
        count = max(1, int((rect.height() if vertical else rect.width()) / pitch))
        span = count * pitch - 3.0
        origin = (rect.top() if vertical else rect.left()) + max(0.0, ((rect.height() if vertical else rect.width()) - span) / 2)
        for index in range(count):
            product = products[index % len(products)] if products else None
            color = hue(product) if product is not None else QColor(_PACKS[index % len(_PACKS)])
            if vertical:
                cell = QRectF(rect.left() + max(0, (rect.width() - pack_w) / 2), origin + index * pitch, min(pack_w, rect.width()), pack_h)
            else:
                cell = QRectF(origin + index * pitch, rect.top() + max(0, (rect.height() - pack_h) / 2), pack_w, min(pack_h, rect.height()))
            painter.setPen(QPen(QColor("#111418"), 1))
            painter.setBrush(color)
            painter.drawRoundedRect(cell, 1.5, 1.5)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#F7F4EE"))
            painter.drawRect(QRectF(cell.left() + 1, cell.center().y() - 1, max(2.0, cell.width() - 2), max(2.0, cell.height() * 0.28)))

    def _legend(self, painter, rect: QRectF) -> None:
        font = painter.font()
        font.setPixelSize(8)
        font.setBold(False)
        painter.setFont(font)
        x = rect.left()
        for text, color in self.LEGEND:
            painter.setBrush(QColor(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(x, rect.center().y() - 4, 8, 8), 2, 2)
            painter.setPen(QColor(MUTED))
            width = painter.fontMetrics().horizontalAdvance(text) + 8
            painter.drawText(QRectF(x + 11, rect.top(), width, rect.height()), Qt.AlignmentFlag.AlignVCenter, text)
            x += 14 + width


class _Shelf(QWidget):
    skuPicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("deptShelf")
        self.bay = None
        self.run = None
        self.products = {}
        self.stock = {}
        self.rows = {}
        self.mode = "planogram"
        self.selected = ""
        self.hits: list[tuple[QRect, str, int]] = []
        self.open_btn = QPushButton("View in inventory", self)
        self.open_btn.setObjectName("deptOpenInventory")
        self.open_btn.clicked.connect(self._open)
        self.move_btn = QPushButton("Move item", self)
        self.move_btn.setObjectName("deptMoveItem")
        self.setMinimumWidth(280)

    def resizeEvent(self, event):
        self.move_btn.setGeometry(max(8, self.width() - 292), self.height() - 32, 130, 26)
        self.open_btn.setGeometry(max(146, self.width() - 154), self.height() - 32, 142, 26)
        super().resizeEvent(event)

    def set_mode(self, mode: str) -> None:
        self.mode = mode if mode in ("planogram", "list", "facings") else "planogram"
        self.update()

    def set_run(self, run, products, stock) -> None:
        self.run = run
        self.bay = None if run is None else run.shelf_bay
        self.products = dict(products or {})
        self.stock = dict(stock or {})
        self.rows = _tier_cards(None if run is None else run.bays, self.products)
        self.selected = next((cards[0][0] for cards in self.rows.values() if cards), "")
        self.open_btn.setEnabled(bool(self.selected))
        self.move_btn.setEnabled(self.bay is not None)
        self.update()

    def _open(self) -> None:
        if self.selected:
            self.skuPicked.emit(self.selected)

    def _first(self, bay) -> str:
        try:
            from open_late.shelf_model import sku_index_v1

            index = list(sku_index_v1())
        except Exception:
            return ""
        for _tier, items in getattr(bay, "tiers", ()) or ():
            for sku, _facings in items or ():
                try:
                    pos = int(sku)
                except (TypeError, ValueError):
                    continue
                if 0 <= pos < len(index) and index[pos] in self.products:
                    return index[pos]
        return ""

    def mousePressEvent(self, event):
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        for rect, pid, _facings in self.hits:
            if rect.contains(pos):
                self.selected = pid
                self.open_btn.setEnabled(True)
                self.update()
                return
        super().mousePressEvent(event)

    def paintEvent(self, _event):
        from open_late.shelf_model import sku_index_v1
        from open_late.ui.hq_product import paint_product_art, product_size, product_title

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#071425"))
        painter.setPen(QPen(QColor(LINE), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -2, -2), 8, 8)
        self.hits = []
        bay = self.bay
        if bay is None:
            painter.setPen(QColor(MUTED))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Select a fixture")
            painter.end()
            return
        tiers = self.rows or {}
        ordered = [name for name in _TIER_ORDER if name in tiers]
        ordered += [name for name in tiers if name not in ordered]
        top = 8
        bottom = self.height() - 150
        count = max(1, len(ordered))
        band = max(36, (bottom - top) / count)
        chosen = None
        chosen_facings = 0
        for row, name in enumerate(ordered):
            y = int(top + row * band)
            number = len(ordered) - row
            extra = _TIER_LABEL.get(name, "")
            painter.setPen(QColor("#19E86A") if name == "eye" else QColor(MUTED))
            font = painter.font()
            font.setPixelSize(13)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(QRect(8, y, 46, int(band)), Qt.AlignmentFlag.AlignVCenter, f"{number} {extra}".strip())
            items = list(tiers.get(name) or ())[:6]
            if not items:
                continue
            card_w = min(118, max(72, (self.width() - 64) / len(items) - 8))
            card_h = min(int(band) - 12, 132)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#243140"))
            painter.drawRoundedRect(QRect(52, y + int(card_h) - 2, self.width() - 60, 6), 1, 1)
            for col, (pid, product, facings) in enumerate(items):
                rect = QRect(56 + int(col * (card_w + 8)), y + 2, int(card_w), int(card_h))
                self.hits.append((rect, pid, int(facings)))
                title = product_title(product)
                selected = pid == self.selected
                painter.setPen(QPen(QColor("#19E86A") if selected else QColor("#12181F"), 3 if selected else 1))
                painter.setBrush(QColor("#F4F0E6"))
                painter.drawRoundedRect(rect, 4, 4)
                if self.mode == "facings":
                    painter.setPen(QColor("#14301F"))
                    font.setPixelSize(22)
                    font.setBold(True)
                    painter.setFont(font)
                    painter.drawText(rect.adjusted(4, 4, -4, -22), Qt.AlignmentFlag.AlignCenter, str(facings))
                elif self.mode == "list":
                    painter.setPen(QColor("#14301F"))
                    font.setPixelSize(12)
                    font.setBold(True)
                    painter.setFont(font)
                    painter.drawText(rect.adjusted(6, 6, -6, -22), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, title)
                else:
                    paint_package_face(painter, rect.adjusted(2, 2, -2, -2), product)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.setPen(QPen(QColor("#19E86A") if selected else QColor("#12181F"), 3 if selected else 1))
                    painter.drawRoundedRect(rect, 4, 4)
                if pid == self.selected:
                    chosen = product
                    chosen_facings = int(facings)
        card = QRect(8, self.height() - 142, self.width() - 16, 100)
        painter.setBrush(QColor(PANEL))
        painter.setPen(QPen(QColor(LINE), 1))
        painter.drawRoundedRect(card, 6, 6)
        painter.setPen(QColor(TEXT))
        font = painter.font()
        font.setPixelSize(12)
        font.setBold(True)
        painter.setFont(font)
        if chosen is None:
            painter.drawText(card.adjusted(10, 8, -10, -8), Qt.AlignmentFlag.AlignLeft, "Click a package")
        else:
            line = self.stock.get(self.selected)
            on_hand = int(getattr(line, "on_hand", 0) or 0) if line is not None else 0
            on_order = int(getattr(line, "on_order", 0) or 0) if line is not None else 0
            thumb = QRect(card.left() + 8, card.top() + 8, 64, card.height() - 16)
            painter.setBrush(QColor("#F7F3EA"))
            painter.setPen(QPen(QColor(LINE), 1))
            painter.drawRoundedRect(thumb, 4, 4)
            paint_package_face(painter, thumb.adjusted(3, 3, -3, -3), chosen)
            painter.setPen(QColor(TEXT))
            painter.drawText(card.adjusted(80, 6, -10, -70), Qt.AlignmentFlag.AlignLeft, product_title(chosen))
            font.setPixelSize(10)
            font.setBold(False)
            painter.setFont(font)
            painter.setPen(QColor(MUTED))
            facts = "\n".join(
                (
                    f"Facings  {chosen_facings}     On hand  {on_hand}",
                    f"On order  {on_order}     Size  {product_size(chosen) or '—'}",
                    f"Supplier  {getattr(chosen, 'supplier_id', '') or '—'}",
                    f"Department  {_name(getattr(chosen, 'department', '') or getattr(bay, 'dept', ''))}",
                    f"Cost  {money(int(getattr(chosen, 'cost', 0) or 0))}     Retail  {money(int(getattr(chosen, 'price', 0) or 0))}",
                )
            )
            painter.drawText(card.adjusted(80, 26, -10, -6), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, facts)
        painter.end()


class DeptFloorView(QWidget):
    """Fixture map for one department, with that fixture's shelf beside it."""

    skuPicked = Signal(str)
    movePicked = Signal(str)
    navPicked = Signal(str)
    deptPicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("deptFloorView")
        self.setStyleSheet(
            f"""
            QWidget#deptFloorView {{ background:{FRAME}; color:{TEXT}; }}
            QFrame#deptToolbar {{ background:{FRAME}; border:1px solid {FRAME_BTN_LINE}; border-radius:8px; }}
            QLabel {{ color:{TEXT}; background:transparent; }}
            QComboBox {{ background:#0B1A2D; color:{TEXT}; border:1px solid {LINE}; border-radius:4px; padding:4px 8px; }}
            QPushButton {{ background:{FRAME_BTN}; color:{FRAME_INK}; border:1px solid {FRAME_BTN_LINE}; border-radius:8px; padding:6px 14px; font-weight:600; }}
            QPushButton:hover {{ border-color:#19E86A; }}
            QFrame#deptNav {{ background:#0B1A2D; border:1px solid {LINE}; border-radius:7px; }}
            QFrame#deptNav QPushButton {{ text-align:left; padding:8px 10px; }}
            QPushButton#templateChipOn {{ background:#19E86A; color:#03150A; border:1px solid #72FFA8; font-weight:800; }}
            QPushButton#templateChip {{ background:#0B1A2D; color:#7897AE; }}
            """
        )
        self.layout_data = None
        self.products = {}
        self.stock = {}
        self.runs: list[Run] = []
        self.zone_run: dict[str, Run] = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)
        bar = QFrame()
        bar.setObjectName("deptToolbar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(8, 6, 8, 6)
        self.heading = QLabel("Floor Plan")
        self.heading.setObjectName("deptHeading")
        font = self.heading.font()
        font.setBold(True)
        font.setPixelSize(14)
        self.heading.setFont(font)
        self.stats = QLabel("")
        self.stats.setObjectName("deptStats")
        row.addWidget(self.heading)
        row.addWidget(self.stats)
        row.addStretch(1)
        row.addWidget(QLabel("Department"))
        self.department = QComboBox()
        self.department.setObjectName("deptFloorDepartment")
        row.addWidget(self.department)
        row.addWidget(QLabel("Zoom"))
        self.zoom = QSlider(Qt.Orientation.Horizontal)
        self.zoom.setRange(70, 160)
        self.zoom.setValue(100)
        self.zoom.setFixedWidth(100)
        row.addWidget(self.zoom)
        self.reset = QPushButton("Reset View")
        row.addWidget(self.reset)
        bar.hide()
        root.addWidget(bar)
        body = QHBoxLayout()
        body.setSpacing(8)
        nav = QFrame()
        nav.setObjectName("deptNav")
        nav.setFixedWidth(176)
        nav_box = QVBoxLayout(nav)
        nav_box.setContentsMargins(8, 8, 8, 8)
        nav_box.setSpacing(4)
        nav_title = QLabel("Planograms")
        nav_font = nav_title.font()
        nav_font.setBold(True)
        nav_title.setFont(nav_font)
        nav_box.addWidget(nav_title)
        for key, text in (
            ("floor", "Floor Plan"),
            ("editor", "Shelf Editor"),
            ("layout", "Item Placement"),
            ("endcaps", "Endcaps & Displays"),
            ("workbench", "Planogram View"),
        ):
            button = QPushButton(text)
            button.setObjectName("templateChipOn" if key == "floor" else "templateChip")
            button.clicked.connect(lambda _=False, key=key: self.navPicked.emit(key))
            nav_box.addWidget(button)
        nav_box.addStretch(1)
        nav.hide()
        body.addWidget(nav)
        self.canvas = DeptFloorCanvas()
        side = QVBoxLayout()
        self.shelf_title = QLabel("Shelf Planogram")
        self.shelf_title.setObjectName("deptShelfTitle")
        title_font = self.shelf_title.font()
        title_font.setBold(True)
        title_font.setPixelSize(13)
        self.shelf_title.setFont(title_font)
        pick = QHBoxLayout()
        pick.addWidget(QLabel("Fixture"))
        self.fixture = QComboBox()
        self.fixture.setObjectName("deptFloorFixture")
        pick.addWidget(self.fixture, 1)
        self.mode_plan = QPushButton("Planogram View")
        self.mode_list = QPushButton("Product List")
        self.mode_grid = QPushButton("Facings Grid")
        for button, mode in ((self.mode_plan, "planogram"), (self.mode_list, "list"), (self.mode_grid, "facings")):
            button.clicked.connect(lambda _=False, mode=mode: self._set_mode(mode))
            pick.addWidget(button)
        self.shelf = _Shelf()
        self._set_mode("planogram")
        self.side_host = QWidget()
        self.side_host.setLayout(side)
        self.side_host.hide()
        side.addWidget(self.shelf_title)
        side.addLayout(pick)
        side.addWidget(self.shelf, 1)
        body.addWidget(self.canvas, 1)
        body.addWidget(self.side_host)
        root.addLayout(body, 1)
        self.department.currentIndexChanged.connect(self._department_changed)
        self.fixture.currentIndexChanged.connect(self._fixture_changed)
        self.zoom.valueChanged.connect(self.canvas.set_zoom)
        self.reset.clicked.connect(lambda: self.zoom.setValue(100))
        self.canvas.runPicked.connect(self._on_zone)
        self.shelf.skuPicked.connect(self.skuPicked)
        self.shelf.move_btn.clicked.connect(self._move)

    def load(self, layout, products, door=None) -> None:
        self.layout_data = layout
        self.products = dict(products or {})
        self.stock = dict(getattr(door, "stock", {}) or {}) if door is not None else {}
        city = str(getattr(door, "city", "") or "Store")
        state = str(getattr(door, "state_name", "") or getattr(door, "state", "") or "")
        number = str(getattr(door, "number", "") or getattr(door, "id", "") or "")
        self.canvas.set_store(city if door is not None else "", state if door is not None else "", number if door is not None else "")
        bays = list(getattr(layout, "bays", ()) or ())
        depts = []
        for bay in bays:
            dept = str(getattr(bay, "dept", "") or "")
            if dept and dept != "*" and dept not in depts:
                depts.append(dept)
        self.department.blockSignals(True)
        current = str(self.department.currentData() or "")
        self.department.clear()
        for dept in depts:
            self.department.addItem(_name(dept), dept)
        if current:
            index = self.department.findData(current)
            if index >= 0:
                self.department.setCurrentIndex(index)
        elif depts:
            fullest = max(depts, key=lambda dept: sum(1 for bay in bays if str(getattr(bay, "dept", "")) == dept))
            index = self.department.findData(fullest)
            if index >= 0:
                self.department.setCurrentIndex(index)
        self.department.blockSignals(False)
        self.heading.setText(f"{_name(str(self.department.currentData() or ''))}  –  Floor Plan" if depts else f"{city}  –  Floor Plan")
        self._wire_zones()
        self._show_department()

    def _set_mode(self, mode: str) -> None:
        self.shelf.set_mode(mode)
        for button, name in ((self.mode_plan, "planogram"), (self.mode_list, "list"), (self.mode_grid, "facings")):
            button.setObjectName("templateChipOn" if name == mode else "templateChip")
            button.style().unpolish(button)
            button.style().polish(button)

    def _department_changed(self) -> None:
        self.heading.setText(f"{_name(str(self.department.currentData() or ''))}  –  Floor Plan")
        self._show_department()

    def _show_department(self) -> None:
        dept = str(self.department.currentData() or "")
        raw = _runs(self.layout_data, dept, self.products)
        skus = _sku_count(raw, self.products)
        self.runs = _photo_runs(raw, self.products)
        feet = sum(run.feet for run in self.runs)
        self.stats.setText(f"{feet} ft    ·    {len(self.runs)} fixtures    ·    {skus} SKUs")
        self.fixture.blockSignals(True)
        self.fixture.clear()
        for run in self.runs:
            self.fixture.addItem(run.title, run.key)
        self.fixture.blockSignals(False)
        if self.runs:
            self._select_run(self.runs[0].key)
        else:
            self.canvas.set_plan([], "", self.products)
            self.shelf.set_run(None, self.products, self.stock)
            self.shelf_title.setText("Shelf Planogram")

    def _fixture_changed(self) -> None:
        key = str(self.fixture.currentData() or "")
        if key:
            self._select_run(key)

    def _wire_zones(self) -> None:
        pools: dict[str, list] = {}
        checkout = []
        for bay in list(getattr(self.layout_data, "bays", ()) or ()):
            if getattr(bay, "kind", "") == "checkout":
                checkout.append(bay)
                continue
            dept = str(getattr(bay, "dept", "") or "")
            if dept and dept != "*":
                pools.setdefault(dept, []).append(bay)
        used: dict[str, int] = {}
        wired: dict[str, Run] = {}
        for ident, dept, *_rest in map_zones():
            pool = checkout if dept == "checkout" else pools.get(dept, [])
            if not pool:
                continue
            bay = pool[used.get(dept, 0) % len(pool)]
            used[dept] = used.get(dept, 0) + 1
            wired[ident] = Run(ident, dept or "checkout", ident, "gondola", 3, [bay])
        self.zone_run = wired

    def _on_zone(self, ident: str) -> None:
        self.canvas.picked = ident
        self.canvas.update()
        zone = next((item for item in map_zones() if item[0] == ident), None)
        label = "Floor Plan" if zone is None else str(zone[7]).replace("\n", " ")
        run = self.zone_run.get(ident)
        if run is None:
            self.side_host.hide()
            self.heading.setText(f"{label}  –  Floor Plan")
            self.stats.setText("This area has no shelf in the store.")
            return
        self.side_host.show()
        self.heading.setText(f"{label}  –  Floor Plan")
        bay = run.shelf_bay
        self.stats.setText(f"Bay {getattr(bay, 'key', '')}")
        self.shelf_title.setText(f"Shelf Planogram  –  {label}")
        self.shelf.set_run(run, self.products, self.stock)
        if run.dept and run.dept != "checkout":
            self.deptPicked.emit(run.dept)

    def _select_run(self, key: str) -> None:
        run = next((item for item in self.runs if item.key == key), None)
        if run is None:
            return
        index = self.fixture.findData(run.key)
        if index >= 0 and self.fixture.currentIndex() != index:
            self.fixture.blockSignals(True)
            self.fixture.setCurrentIndex(index)
            self.fixture.blockSignals(False)
        self.canvas.set_plan(self.runs, run.key, self.products)
        self.shelf_title.setText(f"Shelf Planogram  –  {run.title}")
        self.shelf.set_run(run, self.products, self.stock)

    def _move(self) -> None:
        bay = self.shelf.bay
        if bay is None:
            return
        key = str(getattr(bay, "key", "") or "")
        aisle = str(getattr(bay, "aisle", "") or "")
        if key.endswith((".F", ".B")) or key.startswith("CK"):
            self.movePicked.emit(key)
        else:
            self.movePicked.emit(aisle or key)


def _lead_name(bays, products) -> str:
    try:
        from open_late.shelf_model import sku_index_v1
        from open_late.ui.hq_product import product_title

        index = list(sku_index_v1())
    except Exception:
        return ""
    for bay in bays:
        tiers = list(getattr(bay, "tiers", ()) or ())
        tiers.sort(key=lambda item: 0 if item and item[0] == "eye" else 1)
        for _tier, items in tiers:
            for sku, _facings in items or ():
                try:
                    pos = int(sku)
                except (TypeError, ValueError):
                    continue
                product = products.get(index[pos]) if 0 <= pos < len(index) else None
                if product is None:
                    continue
                title = product_title(product)
                return title if len(title) <= 22 else title[:21].rstrip() + "…"
    return ""


def map_zones() -> list[tuple]:
    """Store-map blocks: ident, game department, box, color, and the words on the block."""
    zones = [
        ("bakery", "grocery", 0.145, 0.045, 0.11, 0.075, "#E8872A", "BAKERY", 12, "#FFFFFF"),
        ("deli", "meat_dairy", 0.26, 0.045, 0.11, 0.075, "#E8872A", "DELI", 12, "#FFFFFF"),
        ("produce", "produce", 0.375, 0.045, 0.17, 0.075, "#1FA34A", "PRODUCE", 13, "#FFFFFF"),
        ("meat", "meat_dairy", 0.55, 0.045, 0.22, 0.075, "#1E6FE0", "MEAT & SEAFOOD", 12, "#FFFFFF"),
        ("receiving", "", 0.84, 0.02, 0.145, 0.13, "#141C28", "RECEIVING\n(Associates Only)", 9, "#FFFFFF"),
        ("pharmacy", "pharmacy", 0.02, 0.16, 0.11, 0.15, "#7A33E0", "PHARMACY", 11, "#FFFFFF"),
        ("health", "health_beauty", 0.02, 0.32, 0.11, 0.14, "#2E9FE0", "HEALTH\n& BEAUTY", 10, "#FFFFFF"),
        ("cosmetics", "health_beauty", 0.02, 0.47, 0.11, 0.12, "#E23B8C", "COSMETICS", 10, "#FFFFFF"),
        ("personal", "health_beauty", 0.02, 0.60, 0.11, 0.12, "#14B8A6", "PERSONAL\nCARE", 10, "#FFFFFF"),
        ("vision", "", 0.02, 0.84, 0.12, 0.11, "#141C28", "VISION CENTER", 9, "#FFFFFF"),
        ("home", "home_garden", 0.855, 0.18, 0.125, 0.16, "#2F7FE0", "HOME\nSOLUTIONS", 11, "#FFFFFF"),
        ("pet", "", 0.855, 0.40, 0.125, 0.18, "#E8872A", "PET CARE\n(Dogs & Cats)", 10, "#FFFFFF"),
        ("self-left", "checkout", 0.16, 0.655, 0.17, 0.145, "#2F6FE0", "Self Checkout", 10, "#FFFFFF"),
        ("checkouts", "checkout", 0.36, 0.655, 0.26, 0.038, "#2F6FE0", "Checkouts", 11, "#FFFFFF"),
        ("self-right", "checkout", 0.65, 0.655, 0.17, 0.145, "#2F6FE0", "Self Checkout", 10, "#FFFFFF"),
        ("entrance", "", 0.36, 0.84, 0.26, 0.14, "#1E6FE0", "Enter / Exit", 11, "#FFFFFF"),
        ("service", "", 0.64, 0.86, 0.16, 0.07, "#141C28", "CUSTOMER SERVICE", 9, "#FFFFFF"),
        ("restrooms", "", 0.82, 0.78, 0.16, 0.18, "#141C28", "RESTROOMS", 10, "#FFFFFF"),
    ]
    _lay_aisles(zones, 0.132, 0.168, (
        ("A", ("Grocery", "Grocery", "Grocery", "Grocery", "Beverages", "Snacks"), "grocery", "#E0B000"),
        ("B", ("Canned Goods", "Boxed Meals", "Pasta & Rice", "Condiments", "International"), "grocery", "#C6C43A"),
        ("C", ("Frozen Foods", "Frozen Meals", "Ice Cream", "Dairy"), "frozen", "#7BC143"),
        ("D", ("Paper Goods", "Cleaning"), "household", "#C9A15A"),
    ))
    _lay_aisles(zones, 0.314, 0.155, (
        ("E", ("Baby", "Toddler", "Diapers", "Baby Food"), "health_beauty", "#E07AA8"),
        ("F", ("Toys", "Games", "Seasonal", "Party"), "toys", "#D4538A"),
        ("G", ("Home Decor", "Storage", "Kitchen", "Appliances"), "home_garden", "#6A7AD4"),
        ("H", ("Auto Care", "Hardware", "Paint", "Electrical"), "home_garden", "#3AAA6A"),
        ("I", ("Pet Food", "Supplies", "Health", "Accessories"), "", "#E8942A"),
    ))
    _lay_aisles(zones, 0.484, 0.155, (
        ("J", ("Men's Apparel", "Men's Shoes", "Men's Active"), "clothing", "#E07AA8"),
        ("K", ("Women's Apparel", "Women's Shoes", "Women's Active", "Intimates"), "clothing", "#8E74C8"),
        ("L", ("Kids' Apparel", "Kids' Shoes", "Character"), "clothing", "#A98AD0"),
        ("M", ("Electronics", "Photo", "Phones", "Entertainment"), "electronics", "#2E9A55"),
        ("N", ("Sports", "Garden", "Seasonal"), "sporting", ("#3AAA6A", "#3AAA6A", "#E07AA8")),
    ))
    lane_w = 0.25 / 8
    for index in range(8):
        zones.append((f"lane{index + 1}", "checkout", 0.365 + index * lane_w, 0.70, lane_w - 0.002, 0.09, "#2F6FDB", "", 7, "#FFFFFF"))
    return zones


def _lay_aisles(zones: list, y: float, height: float, bands: tuple) -> None:
    """Pack one row of gondolas across the open floor between the side rooms."""
    left, right = 0.148, 0.842
    aisle_gap, group_gap = 0.004, 0.012
    total = sum(len(labels) for _letter, labels, _dept, _fill in bands)
    gaps = aisle_gap * (total - len(bands)) + group_gap * (len(bands) - 1)
    slot = (right - left - gaps) / total
    x = left
    for letter, labels, dept, fill in bands:
        colors = fill if isinstance(fill, tuple) else (fill,) * len(labels)
        for index, label in enumerate(labels):
            zones.append((f"{letter}{index + 1}", dept, x, y, slot, height, colors[index], f"{letter}{index + 1}\n{label}", 9, "#FFFFFF"))
            x += slot + aisle_gap
        x += group_gap - aisle_gap


def _short_label(name: str) -> str:
    """Photo-style gondola word: the product's last real word, such as Flour."""
    words = [word.strip(".,") for word in str(name).replace("-", " ").split() if word.lower() not in {"a", "an", "the", "and", "of", "with", "style"}]
    word = words[-1] if words else str(name)
    if not word:
        return "Item"
    return word[:1].upper() + word[1:]


def _photo_runs(runs: list[Run], products) -> list[Run]:
    """Place the department's real products on the photo's fixture arrangement."""
    if not runs:
        return []
    from open_late.ui.hq_product import product_title

    names: list[str] = []
    for run in runs:
        for product in _run_products(run.bays, products):
            title = product_title(product)
            if title and title not in names:
                names.append(title)
    if not names:
        names = [_name(runs[0].dept)]
    photo: list[Run] = []
    for index, spec in enumerate(_PHOTO):
        source = runs[index % len(runs)]
        name = _short_label(names[index % len(names)])
        photo.append(Run(f"{source.key}#{index}", source.dept, f"{spec[5]}' {name}", "wall" if spec[4] else "gondola", spec[5], list(source.bays)))
    return photo


def _runs(layout, dept: str, products=None) -> list[Run]:
    products = products or {}
    groups: dict[str, list] = {}
    order: list[str] = []
    for bay in list(getattr(layout, "bays", ()) or ()):
        if str(getattr(bay, "dept", "") or "") != dept:
            continue
        if getattr(bay, "kind", "") in ("checkout", "action_alley"):
            continue
        key = str(getattr(bay, "aisle", "") or getattr(bay, "key", ""))
        if key not in groups:
            order.append(key)
        groups.setdefault(key, []).append(bay)
    runs = []
    for key in order:
        bays = groups[key]
        role = "gondola"
        if any(getattr(bay, "kind", "") in ("perimeter", "pharmacy") for bay in bays):
            role = "wall"
        elif any(getattr(bay, "kind", "") == "seasonal" for bay in bays):
            role = "promo"
        inline = [bay for bay in bays if not str(getattr(bay, "key", "")).endswith((".F", ".B"))] or bays
        caps = [bay for bay in bays if str(getattr(bay, "key", "")).endswith((".F", ".B"))]
        for index in range(0, len(inline), 2):
            piece = list(inline[index:index + 2])
            if index == 0:
                piece = caps + piece
            feet = sum(_WIDTHS.get(str(getattr(bay, "fixture", "")), 3) for bay in piece)
            name = _lead_name(piece, products) or _name(dept)
            runs.append(Run(f"{key}:{index}", dept, f"{feet}' {name}", role if index == 0 else "gondola", feet, piece))
    return runs


def _run_products(bays, products) -> list:
    try:
        from open_late.shelf_model import sku_index_v1

        index = list(sku_index_v1())
    except Exception:
        return []
    found = []
    seen = set()
    ordered = []
    for bay in bays:
        tiers = list(getattr(bay, "tiers", ()) or ())
        tiers.sort(key=lambda item: 0 if item and item[0] == "eye" else 1)
        ordered.extend(tiers)
    for _tier, items in ordered:
        for sku, _facings in items or ():
            try:
                pos = int(sku)
            except (TypeError, ValueError):
                continue
            pid = index[pos] if 0 <= pos < len(index) else ""
            product = products.get(pid)
            if product is None or pid in seen:
                continue
            seen.add(pid)
            found.append(product)
    return found


def _tier_cards(bays, products) -> dict:
    try:
        from open_late.shelf_model import sku_index_v1

        index = list(sku_index_v1())
    except Exception:
        return {}
    rows: dict[str, list] = {}
    for bay in list(bays or []):
        for tier, items in getattr(bay, "tiers", ()) or ():
            bucket = rows.setdefault(str(tier), [])
            for sku, facings in items or ():
                try:
                    pos = int(sku)
                    count = max(1, int(facings))
                except (TypeError, ValueError):
                    continue
                pid = index[pos] if 0 <= pos < len(index) else ""
                product = products.get(pid)
                if product is None:
                    continue
                for _copy in range(min(count, 4)):
                    if len(bucket) >= 7:
                        break
                    bucket.append((pid, product, count))
    return rows


def _sku_count(runs, products) -> int:
    try:
        from open_late.shelf_model import sku_index_v1

        index = list(sku_index_v1())
    except Exception:
        return 0
    seen = set()
    for run in runs:
        for bay in run.bays:
            for _tier, items in getattr(bay, "tiers", ()) or ():
                for sku, _facings in items or ():
                    try:
                        pos = int(sku)
                    except (TypeError, ValueError):
                        continue
                    if 0 <= pos < len(index) and index[pos] in products:
                        seen.add(index[pos])
    return len(seen)
