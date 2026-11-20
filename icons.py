"""Generic painted app icons. No vendor logos."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient

ASSETS = Path(__file__).resolve().parent.parent / "assets"

# id, label, glyph, desk index
APPS = [
    ("overview", "Overview", "floor", 0),
    ("sales", "Sales", "chart", 1),
    ("inventory", "Inventory", "box", 2),
    ("orders", "Orders", "clip", 3),
    ("staff", "Staff", "people", 4),
    ("customers", "Customers", "heart", 5),
    ("marketing", "Marketing", "horn", 6),
    ("books", "Books", "ledger", 7),
    ("expansion", "Expansion", "store", 8),
    ("market", "Market", "tag", 9),
    ("journal", "Journal", "book", 10),
    ("settings", "Settings", "sliders", 11),
]

TILE = {
    "overview": ("#3AA6A0", "#2A7F7A"),
    "sales": ("#3D8BDB", "#1F5FA8"),
    "inventory": ("#C9843A", "#8F5A22"),
    "orders": ("#5B7FCF", "#3A58A0"),
    "staff": ("#6A9A4E", "#4A7034"),
    "customers": ("#C45B6A", "#8E3844"),
    "marketing": ("#B86A3A", "#8A4A22"),
    "books": ("#5B6E8A", "#3A4A62"),
    "expansion": ("#7A5CAF", "#56408A"),
    "market": ("#6B4EA0", "#3F2E70"),
    "economy": ("#3D7EFF", "#2547A0"),
    "journal": ("#3F8F8A", "#2A6460"),
    "settings": ("#6E6E74", "#4A4A50"),
}


def app_label(app_id: str, *, corporate: bool = False) -> str:
    if app_id == "expansion":
        return "Stores" if corporate else "Expansion"
    for item, label, _glyph, _index in APPS:
        if item == app_id:
            return label
    return app_id.title()


def app_id_for_index(index: int) -> str:
    for item, _label, _glyph, desk_index in APPS:
        if desk_index == index:
            return item
    return "overview"


def index_for_app(app_id: str) -> int:
    for item, _label, _glyph, desk_index in APPS:
        if item == app_id:
            return desk_index
    return 0


def icon_pixmap(app_id: str, size: int) -> QPixmap:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    margin = max(1, int(size * 0.06))
    rect = QRectF(margin, margin, size - margin * 2, size - margin * 2)
    top, bottom = TILE.get(app_id, ("#5A6A7A", "#3A4A5A"))
    grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
    grad.setColorAt(0.0, QColor(top))
    grad.setColorAt(1.0, QColor(bottom))
    radius = rect.width() * 0.28
    painter.setPen(QPen(QColor(255, 255, 255, 90), 1))
    painter.setBrush(grad)
    painter.drawRoundedRect(rect, radius, radius)
    hi = QRadialGradient(rect.center().x(), rect.top() + rect.height() * 0.15, rect.width() * 0.6)
    hi.setColorAt(0.0, QColor(255, 255, 255, 50))
    hi.setColorAt(1.0, QColor(255, 255, 255, 0))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(hi)
    painter.drawEllipse(rect.adjusted(2, 2, -2, -2))
    glyph = "box"
    for item, _label, g, _index in APPS:
        if item == app_id:
            glyph = g
            break
    _draw_glyph(painter, rect, glyph, QColor("#FFFFFF"), max(1.6, size / 22))
    painter.end()
    return pix


def start_mark(size: int) -> QPixmap:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    rect = QRectF(1, 1, size - 2, size - 2)
    painter.setBrush(QColor("#0B6CBD"))
    painter.setPen(QPen(QColor(255, 255, 255, 80), 1))
    painter.drawRoundedRect(rect, rect.width() * 0.28, rect.width() * 0.28)
    mark = ASSETS / "brand" / "mark.png"
    if mark.exists():
        raw = QPixmap(str(mark))
        inner = int(size * 0.72)
        scaled = raw.scaled(inner, inner, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        painter.drawPixmap(int((size - scaled.width()) / 2), int((size - scaled.height()) / 2), scaled)
    painter.end()
    return pix


def _draw_glyph(painter: QPainter, rect: QRectF, kind: str, color: QColor, width: float) -> None:
    painter.save()
    painter.setPen(QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    cx, cy = rect.center().x(), rect.center().y()
    s = rect.width()
    r = QRectF(cx - s * 0.22, cy - s * 0.22, s * 0.44, s * 0.44)
    if kind == "floor":
        painter.drawRoundedRect(QRectF(cx - s * 0.22, cy - s * 0.22, s * 0.44, s * 0.12), 2, 2)
        painter.drawLine(QPointF(cx - s * 0.22, cy - s * 0.10), QPointF(cx - s * 0.22, cy + s * 0.20))
        painter.drawLine(QPointF(cx + s * 0.22, cy - s * 0.10), QPointF(cx + s * 0.22, cy + s * 0.20))
        painter.drawLine(QPointF(cx - s * 0.22, cy + s * 0.20), QPointF(cx + s * 0.22, cy + s * 0.20))
        painter.drawRect(QRectF(cx - s * 0.08, cy - s * 0.04, s * 0.16, s * 0.16))
    elif kind == "chart":
        painter.drawLine(QPointF(r.left(), r.bottom()), QPointF(r.left() + r.width() * 0.3, r.center().y()))
        painter.drawLine(QPointF(r.left() + r.width() * 0.3, r.center().y()), QPointF(r.left() + r.width() * 0.6, r.bottom() - r.height() * 0.15))
        painter.drawLine(QPointF(r.left() + r.width() * 0.6, r.bottom() - r.height() * 0.15), QPointF(r.right(), r.top()))
    elif kind == "box":
        painter.drawRoundedRect(r, 3, 3)
        painter.drawLine(QPointF(r.left(), r.top() + r.height() * 0.38), QPointF(r.right(), r.top() + r.height() * 0.38))
        painter.drawLine(QPointF(r.center().x(), r.top()), QPointF(r.center().x(), r.top() + r.height() * 0.38))
    elif kind == "clip":
        painter.drawRoundedRect(QRectF(cx - s * 0.14, cy - s * 0.20, s * 0.28, s * 0.40), 3, 3)
        painter.drawLine(QPointF(cx - s * 0.08, cy - s * 0.08), QPointF(cx + s * 0.08, cy - s * 0.08))
        painter.drawLine(QPointF(cx - s * 0.08, cy + 2), QPointF(cx + s * 0.08, cy + 2))
    elif kind == "people":
        painter.drawEllipse(QRectF(cx - s * 0.23, cy - s * 0.18, s * 0.14, s * 0.14))
        painter.drawEllipse(QRectF(cx + s * 0.09, cy - s * 0.18, s * 0.14, s * 0.14))
        painter.drawArc(QRectF(cx - s * 0.28, cy - s * 0.02, s * 0.24, s * 0.28), 0, 180 * 16)
        painter.drawArc(QRectF(cx + s * 0.04, cy - s * 0.02, s * 0.24, s * 0.28), 0, 180 * 16)
    elif kind == "heart":
        path = QPainterPath()
        path.moveTo(cx, cy + s * 0.16)
        path.cubicTo(cx - s * 0.22, cy + s * 0.02, cx - s * 0.20, cy - s * 0.16, cx, cy - s * 0.06)
        path.cubicTo(cx + s * 0.20, cy - s * 0.16, cx + s * 0.22, cy + s * 0.02, cx, cy + s * 0.16)
        painter.drawPath(path)
    elif kind == "horn":
        path = QPainterPath()
        path.moveTo(cx - s * 0.16, cy - s * 0.06)
        path.lineTo(cx + s * 0.04, cy - s * 0.16)
        path.lineTo(cx + s * 0.04, cy + s * 0.16)
        path.lineTo(cx - s * 0.16, cy + s * 0.06)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawArc(QRectF(cx + s * 0.04, cy - s * 0.12, s * 0.16, s * 0.24), -80 * 16, 160 * 16)
    elif kind == "ledger":
        painter.drawRoundedRect(r, 3, 3)
        for i in range(3):
            y = r.top() + r.height() * (0.28 + i * 0.22)
            painter.drawLine(QPointF(r.left() + 4, y), QPointF(r.right() - 4, y))
    elif kind == "store":
        painter.drawLine(QPointF(cx - s * 0.18, cy + s * 0.04), QPointF(cx, cy - s * 0.16))
        painter.drawLine(QPointF(cx, cy - s * 0.16), QPointF(cx + s * 0.18, cy + s * 0.04))
        painter.drawRect(QRectF(cx - s * 0.16, cy + s * 0.04, s * 0.32, s * 0.16))
    elif kind == "tag":
        path = QPainterPath()
        path.moveTo(cx - s * 0.16, cy - s * 0.06)
        path.lineTo(cx + s * 0.04, cy - s * 0.18)
        path.lineTo(cx + s * 0.18, cy - s * 0.04)
        path.lineTo(cx - s * 0.02, cy + s * 0.18)
        path.closeSubpath()
        painter.drawPath(path)
        painter.setBrush(color)
        painter.drawEllipse(QRectF(cx + s * 0.02, cy - s * 0.12, s * 0.07, s * 0.07))
    elif kind == "book":
        painter.drawRoundedRect(QRectF(cx - s * 0.16, cy - s * 0.18, s * 0.32, s * 0.36), 3, 3)
        painter.drawLine(QPointF(cx, cy - s * 0.18), QPointF(cx, cy + s * 0.18))
    else:
        painter.drawLine(QPointF(cx - s * 0.18, cy - s * 0.10), QPointF(cx + s * 0.18, cy - s * 0.10))
        painter.drawLine(QPointF(cx - s * 0.18, cy + s * 0.10), QPointF(cx + s * 0.18, cy + s * 0.10))
        painter.setBrush(color)
        painter.drawEllipse(QRectF(cx - s * 0.04, cy - s * 0.16, s * 0.12, s * 0.12))
        painter.drawEllipse(QRectF(cx + s * 0.02, cy + s * 0.04, s * 0.12, s * 0.12))
    painter.restore()

def quiet_icon(kind: str, size: int = 16) -> QPixmap:
    """Monochrome glyph for rail footer actions: help, save, door."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    color = QColor("#E8EEF5")
    pen = QPen(color, max(1.2, size / 10))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    m = size * 0.18
    r = QRectF(m, m, size - 2 * m, size - 2 * m)
    if kind == "save":
        painter.drawRoundedRect(r, 1.5, 1.5)
        top = QRectF(r.left() + r.width() * 0.2, r.top(), r.width() * 0.6, r.height() * 0.32)
        painter.drawRect(top)
        painter.drawLine(QPointF(r.left() + r.width() * 0.25, r.bottom() - r.height() * 0.2),
                         QPointF(r.right() - r.width() * 0.25, r.bottom() - r.height() * 0.2))
    elif kind == "door":
        painter.drawRoundedRect(r.adjusted(r.width() * 0.1, 0, 0, 0), 1.2, 1.2)
        knob_x = r.left() + r.width() * 0.35
        knob_y = r.center().y()
        painter.setBrush(color)
        painter.drawEllipse(QPointF(knob_x, knob_y), size * 0.06, size * 0.06)
    else:  # help
        painter.drawEllipse(r)
        painter.setFont(painter.font())
        from PySide6.QtGui import QFont
        font = QFont(painter.font())
        font.setPixelSize(max(8, int(size * 0.62)))
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(r, Qt.AlignmentFlag.AlignCenter, "?")
    painter.end()
    return pix
