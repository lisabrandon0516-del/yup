"""QPainter product tiles used on the planogram shelf, SKU rail, and dashboard preview."""

from __future__ import annotations

import hashlib
from typing import Any

from PySide6.QtCore import QPoint, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

from open_late.ui.theme import ui_font

# Facing-status dots (planogram legend).
STATUS_COLOR = {"optimal": "#3B82F6", "risk": "#C9A227", "over": "#C42B1C"}


def product_title(product: Any) -> str:
    name = str(getattr(product, "name", "") or getattr(product, "id", ""))
    if "," in name:
        head, tail = name.rsplit(",", 1)
        if _is_size(tail.strip()):
            return head.strip()
    return name


def product_size(product: Any) -> str:
    name = str(getattr(product, "name", "") or "")
    if "," in name:
        tail = name.rsplit(",", 1)[1].strip()
        if _is_size(tail):
            return tail
    return ""


def _is_size(text: str) -> bool:
    lower = text.lower()
    return any(
        token in lower
        for token in ("lb", "oz", "qt", "ct", "pk", "pack", "ft", "in", "gal", "dozen", "pint", "pc", "roll", "pair", "bunch")
    )


def _hue(product: Any) -> QColor:
    ident = str(getattr(product, "id", "") or getattr(product, "name", "x"))
    digest = hashlib.sha256(ident.encode()).digest()
    return QColor.fromHsv(digest[0] % 360, 90 + digest[1] % 80, 180 + digest[2] % 60)


def paint_product_art(painter: QPainter, rect: QRect, product: Any) -> None:
    """Draw a small illustrated package inside rect."""
    ident = str(getattr(product, "id", "") or "")
    name = str(getattr(product, "name", "") or "").lower()
    dept = str(getattr(product, "department", "") or "")
    prefix = ident.split("-", 1)[0]
    cx, cy = rect.center().x(), rect.center().y()
    w, h = rect.width(), rect.height()

    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)

    def box(color, x, y, bw, bh, radius=4, stroke=None):
        painter.setBrush(QColor(color))
        if stroke:
            painter.setPen(QPen(QColor(stroke), 1))
        else:
            painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(int(x), int(y), int(bw), int(bh), radius, radius)
        painter.setPen(Qt.PenStyle.NoPen)

    def bottle(color, cap="#EEE", x=None, wide=0.28):
        bw = max(8, int(w * wide))
        bh = max(16, int(h * 0.72))
        x0 = cx - bw // 2 if x is None else x
        y0 = cy - bh // 2
        box(color, x0, y0 + 8, bw, bh - 8, 6, "#00000022")
        box(cap, x0 + bw * 0.25, y0, bw * 0.5, 10, 2, "#00000022")

    def can(color):
        bw, bh = int(w * 0.42), int(h * 0.62)
        box(color, cx - bw // 2, cy - bh // 2, bw, bh, 8, "#00000022")
        painter.setBrush(QColor("#FFFFFFAA"))
        painter.drawEllipse(cx - bw // 2 + 3, cy - bh // 2 - 3, bw - 6, 8)

    def bag(color):
        path = QPainterPath()
        bw, bh = int(w * 0.55), int(h * 0.62)
        x0, y0 = cx - bw // 2, cy - bh // 2 + 4
        path.moveTo(x0 + 4, y0)
        path.lineTo(x0 + bw - 4, y0)
        path.lineTo(x0 + bw, y0 + bh)
        path.lineTo(x0, y0 + bh)
        path.closeSubpath()
        painter.setBrush(QColor(color))
        painter.setPen(QPen(QColor("#00000022"), 1))
        painter.drawPath(path)

    def carton(color, stripe="#FFFFFF"):
        bw, bh = int(w * 0.50), int(h * 0.62)
        box(color, cx - bw // 2, cy - bh // 2, bw, bh, 3, "#00000022")
        painter.setBrush(QColor(stripe))
        painter.drawRect(cx - bw // 2, cy - 4, bw, 8)

    def tray(color):
        bw, bh = int(w * 0.62), int(h * 0.28)
        box("#F4F1EA", cx - bw // 2, cy - 2, bw, bh, 3, "#00000022")
        painter.setBrush(QColor(color))
        painter.drawRoundedRect(cx - bw // 2 + 4, cy, bw - 8, bh - 8, 4, 4)

    def apparel(color, kind="tee"):
        painter.setPen(QPen(QColor(color), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(QColor(color))
        if kind in ("tee", "hoodie", "shirt"):
            path = QPainterPath()
            path.moveTo(cx - 16, cy - 10)
            path.lineTo(cx - 8, cy - 14)
            path.lineTo(cx + 8, cy - 14)
            path.lineTo(cx + 16, cy - 10)
            path.lineTo(cx + 12, cy - 4)
            path.lineTo(cx + 10, cy + 16)
            path.lineTo(cx - 10, cy + 16)
            path.lineTo(cx - 12, cy - 4)
            path.closeSubpath()
            painter.setPen(QPen(QColor("#00000022"), 1))
            painter.drawPath(path)
            if kind == "hoodie":
                painter.setBrush(QColor(color).darker(110))
                painter.drawEllipse(cx - 7, cy - 20, 14, 10)
        elif kind in ("jeans", "pants", "shorts", "sleep"):
            length = 22 if kind != "shorts" else 12
            box(color, cx - 12, cy - 10, 10, length, 2)
            box(color, cx + 2, cy - 10, 10, length, 2)
            box(color, cx - 12, cy - 14, 24, 8, 2)
        elif kind == "cap":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(color))
            painter.drawEllipse(cx - 12, cy - 8, 24, 14)
            painter.drawRoundedRect(cx + 4, cy - 2, 16, 5, 2, 2)
        elif kind == "socks":
            box(color, cx - 8, cy - 12, 7, 22, 3)
            box(color, cx + 2, cy - 12, 7, 22, 3)
        elif kind == "jacket":
            path = QPainterPath()
            path.addRoundedRect(QRectF(cx - 14, cy - 14, 28, 28), 4, 4)
            painter.setPen(QPen(QColor("#00000022"), 1))
            painter.drawPath(path)
            painter.setPen(QPen(QColor("#FFFFFFAA"), 1))
            painter.drawLine(cx, cy - 10, cx, cy + 10)

    # --- department / id specialists ---
    if prefix == "prod" or dept == "produce":
        color = "#E6C229" if "banana" in name else "#D94A3A" if "apple" in name or "tomato" in name else "#F28C28" if "orange" in name or "carrot" in name else "#7BB661" if "lettuce" in name or "salad" in name or "berry" in name else "#C9A227"
        if "banana" in name:
            painter.setBrush(QColor("#F6D026"))
            painter.setPen(QPen(QColor("#C9A227"), 2))
            painter.drawArc(cx - 16, cy - 16, 28, 28, 30 * 16, 160 * 16)
            painter.drawArc(cx - 10, cy - 18, 28, 28, 20 * 16, 150 * 16)
        elif "berry" in name:
            for i, (dx, dy) in enumerate(((-8, -4), (4, -6), (-2, 6), (8, 4), (-10, 6))):
                painter.setBrush(QColor("#7B2D8E" if i % 2 == 0 else "#C0392B"))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(cx + dx, cy + dy, 10, 10)
        else:
            painter.setBrush(QColor(color))
            painter.setPen(QPen(QColor("#00000022"), 1))
            painter.drawEllipse(cx - 14, cy - 12, 28, 26)
            painter.setPen(QPen(QColor("#3D6B2A"), 2))
            painter.drawLine(cx, cy - 14, cx + 3, cy - 20)
        return

    if prefix in ("meat", "dairy") or dept == "meat_dairy":
        if "milk" in name:
            carton("#F4F6FA", "#0070F0")
        elif "egg" in name:
            box("#F3E6C8", cx - 16, cy - 10, 32, 20, 6, "#00000022")
            painter.setBrush(QColor("#FFF8E7"))
            painter.drawEllipse(cx - 12, cy - 6, 10, 12)
            painter.drawEllipse(cx + 2, cy - 6, 10, 12)
        elif "yogurt" in name:
            can("#F7C6D0")
        elif "butter" in name or "cheddar" in name:
            box("#F5D76E", cx - 16, cy - 8, 32, 18, 3, "#00000022")
        else:
            tray("#C45C4A")
        return

    if prefix == "fzn" or dept == "frozen":
        if "ice" in name:
            carton("#F7FBFF", "#8EC5E8")
            painter.setBrush(QColor("#F4F9FC"))
            painter.drawEllipse(cx - 8, cy - 8, 10, 10)
            painter.drawEllipse(cx, cy - 2, 8, 8)
        elif "pizza" in name:
            painter.setBrush(QColor("#E8C07A"))
            painter.drawEllipse(cx - 16, cy - 14, 32, 28)
            painter.setBrush(QColor("#C0392B"))
            painter.drawEllipse(cx - 6, cy - 6, 8, 8)
        else:
            carton("#7EC8FF", "#FFFFFF")
        return

    if prefix == "groc" or dept == "grocery":
        if "coffee" in name:
            can("#5B3A29")
        elif "flour" in name or "rice" in name or "pasta" in name:
            bag("#F3E2B8")
        elif "cereal" in name:
            carton("#E86A17", "#FFD56A")
        elif "tomato" in name:
            can("#C0392B")
        elif "bread" in name or "muffin" in name or "bun" in name or "roll" in name:
            box("#E8C07A", cx - 16, cy - 8, 32, 18, 8, "#00000022")
        elif "spread" in name:
            bottle("#C9843A", "#F4E1B0", wide=0.36)
        else:
            carton("#D9A566")
        return

    if prefix == "house" or dept == "household":
        if "soap" in name or "cleaner" in name or "laundry" in name or "dish" in name:
            bottle("#4AA3DF" if "dish" in name else "#5B8DEF")
        elif "bulb" in name:
            painter.setBrush(QColor("#F8E9A1"))
            painter.drawEllipse(cx - 10, cy - 12, 20, 18)
            box("#D0D4DC", cx - 6, cy + 4, 12, 8, 2)
        elif "battery" in name:
            box("#2D2D2D", cx - 14, cy - 8, 12, 20, 2)
            box("#C0392B", cx - 14, cy - 12, 12, 6, 2)
            box("#2D2D2D", cx + 2, cy - 8, 12, 20, 2)
            box("#C0392B", cx + 2, cy - 12, 12, 6, 2)
        else:
            carton("#E8EEF5", "#9AA8BC")
        return

    if prefix == "beauty" or dept == "health_beauty":
        if "soap" in name:
            box("#E8D5F0", cx - 14, cy - 8, 28, 16, 6)
        elif "razor" in name:
            box("#D0D4DC", cx - 4, cy - 16, 8, 28, 3)
            painter.setBrush(QColor("#8A93A0"))
            painter.drawRect(cx - 10, cy + 10, 20, 4)
        else:
            bottle("#7EC8C3" if "shampoo" in name else "#F4A7B9" if "lotion" in name or "cream" in name or "balm" in name else "#7EB6FF")
        return

    if prefix == "pharm" or dept == "pharmacy":
        if "syrup" in name or "spray" in name or "reducer" in name:
            bottle("#4CAF7A", "#F4F6FA")
        elif "bandage" in name or "kit" in name:
            carton("#C0392B", "#FFFFFF")
        elif "thermo" in name:
            box("#EEF2F6", cx - 4, cy - 16, 8, 28, 4, "#00000022")
            painter.setBrush(QColor("#C0392B"))
            painter.drawEllipse(cx - 6, cy + 8, 12, 12)
        else:
            box("#F4F6FA", cx - 14, cy - 10, 28, 18, 4, "#3B82F6")
        return

    if prefix == "elec" or dept == "electronics":
        if "earbuds" in name or "mouse" in name:
            painter.setBrush(QColor("#2D2D2D"))
            painter.drawEllipse(cx - 12, cy - 6, 12, 14)
            painter.drawEllipse(cx + 2, cy - 6, 12, 14)
        elif "speaker" in name:
            box("#2D2D2D", cx - 14, cy - 12, 28, 24, 6)
            painter.setBrush(QColor("#6B7380"))
            painter.drawEllipse(cx - 8, cy - 6, 16, 16)
        elif "tablet" in name or "display" in name or "tv" in name:
            box("#1A1A1A", cx - 18, cy - 12, 36, 24, 3)
            box("#3A7BD5", cx - 15, cy - 9, 30, 18, 2)
        elif "cable" in name or "hdmi" in name or "strip" in name:
            painter.setPen(QPen(QColor("#2D2D2D"), 3))
            painter.drawArc(cx - 16, cy - 10, 32, 20, 0, 180 * 16)
        else:
            box("#3A3A3A", cx - 14, cy - 10, 28, 20, 4)
        return

    if prefix == "cloth" or dept == "clothing":
        color = "#1F4E8C" if "jean" in name or "denim" in name else "#2C3E5A" if "hoodie" in name or "jacket" in name else "#3D7EFF" if "tee" in name or "shirt" in name else "#5B8F3A" if "short" in name or "athletic" in name else "#6B4F3A" if "work" in name else "#E8EEF5" if "sock" in name or "sleep" in name else "#1A1A1A"
        kind = "hoodie" if "hoodie" in name else "jacket" if "jacket" in name else "jeans" if "jean" in name or "pant" in name or "sleep" in name else "shorts" if "short" in name else "cap" if "cap" in name else "socks" if "sock" in name else "tee"
        apparel(color, kind)
        return

    if prefix == "toy" or dept == "toys":
        if "plush" in name or "fox" in name:
            painter.setBrush(QColor("#E07A3D"))
            painter.drawEllipse(cx - 12, cy - 8, 24, 22)
            painter.drawEllipse(cx - 14, cy - 16, 10, 10)
            painter.drawEllipse(cx + 4, cy - 16, 10, 10)
        elif "truck" in name:
            box("#C0392B", cx - 16, cy - 4, 28, 12, 3)
            box("#C0392B", cx - 4, cy - 12, 14, 10, 3)
            painter.setBrush(QColor("#2D2D2D"))
            painter.drawEllipse(cx - 12, cy + 4, 10, 10)
            painter.drawEllipse(cx + 4, cy + 4, 10, 10)
        elif "block" in name or "tile" in name:
            box("#E07A3D", cx - 14, cy - 4, 14, 14, 2)
            box("#3D7EFF", cx - 2, cy - 10, 14, 14, 2)
            box("#F5C542", cx + 4, cy + 2, 12, 12, 2)
        else:
            carton("#F5C542", "#3D7EFF")
        return

    if prefix == "garden" or dept == "home_garden":
        if "hose" in name or "cord" in name:
            painter.setPen(QPen(QColor("#3D6B2A"), 4))
            painter.drawArc(cx - 14, cy - 10, 28, 22, 20 * 16, 280 * 16)
        elif "pot" in name or "planter" in name:
            box("#C9843A", cx - 12, cy - 2, 24, 16, 3)
            painter.setBrush(QColor("#5B8F3A"))
            painter.drawEllipse(cx - 8, cy - 12, 16, 14)
        elif "soil" in name or "seed" in name or "feed" in name:
            bag("#6B4F3A")
        else:
            carton("#C9B896", "#5B8F3A")
        return

    if prefix == "sport" or dept == "sporting":
        if "ball" in name or "soccer" in name:
            painter.setBrush(QColor("#F4F6FA"))
            painter.setPen(QPen(QColor("#1A1A1A"), 1))
            painter.drawEllipse(cx - 14, cy - 14, 28, 28)
        elif "mat" in name or "yoga" in name:
            box("#7B2D8E", cx - 18, cy - 6, 36, 12, 4)
        elif "bottle" in name:
            bottle("#3D7EFF", "#F4F6FA", wide=0.24)
        elif "helmet" in name:
            painter.setBrush(QColor("#C0392B"))
            painter.drawChord(cx - 14, cy - 12, 28, 24, 0, 180 * 16)
        else:
            carton("#1F4E8C", "#F5C542")
        return

    if prefix == "season" or dept == "seasonal":
        if "light" in name or "lantern" in name:
            painter.setPen(QPen(QColor("#F5C542"), 2))
            painter.drawLine(cx - 12, cy - 8, cx + 12, cy + 8)
            painter.setBrush(QColor("#F8E9A1"))
            painter.setPen(Qt.PenStyle.NoPen)
            for dx in (-10, 0, 10):
                painter.drawEllipse(cx + dx - 3, cy - 4, 6, 6)
        elif "wreath" in name:
            painter.setPen(QPen(QColor("#2E7D32"), 5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(cx - 14, cy - 14, 28, 28)
        elif "cape" in name:
            apparel("#7B2D8E", "tee")
        else:
            carton("#7B2D8E", "#F5C542")
        return

    # fallback
    carton(_hue(product).name(), "#FFFFFF")


def paint_product_tile(
    painter: QPainter,
    rect: QRect,
    product: Any,
    *,
    status: str | None = None,
    compact: bool = False,
) -> None:
    """Rounded product card: illustration, name, and size."""
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#173A55"), 1))
    painter.setBrush(QColor("#0E2035"))
    painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 8, 8)
    caption_h = 28 if compact else 34
    art = QRect(rect.x() + 6, rect.y() + 6, rect.width() - 12, max(16, rect.height() - caption_h - 8))
    if art.height() > 12:
        paint_product_art(painter, art, product)
    title = product_title(product)
    size = product_size(product)
    painter.setPen(QColor("#F4F8FF"))
    painter.setFont(ui_font(9 if compact else 10, QFont.Weight.DemiBold))
    text_rect = QRect(rect.x() + 6, rect.bottom() - caption_h + 2, rect.width() - 12, 14 if not size else 16)
    elided = painter.fontMetrics().elidedText(title, Qt.TextElideMode.ElideRight, text_rect.width())
    painter.drawText(text_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, elided)
    if size and not compact:
        painter.setPen(QColor("#9FB0C8"))
        painter.setFont(ui_font(9))
        painter.drawText(
            QRect(rect.x() + 6, rect.bottom() - 16, rect.width() - 12, 14),
            Qt.AlignmentFlag.AlignHCenter,
            size,
        )
    if status and status in STATUS_COLOR:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(STATUS_COLOR[status]))
        painter.drawEllipse(rect.right() - 12, rect.y() + 6, 7, 7)


class ProductTile(QWidget):
    def __init__(self, product=None, compact: bool = False, parent=None):
        super().__init__(parent)
        self.product = product
        self.compact = compact
        self.status = None
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(72, 88 if not compact else 72)

    def set_product(self, product, status: str | None = None) -> None:
        self.product = product
        self.status = status
        self.update()

    def paintEvent(self, _event) -> None:
        if self.product is None:
            return
        painter = QPainter(self)
        paint_product_tile(painter, self.rect().adjusted(1, 1, -1, -1), self.product, status=self.status, compact=self.compact)
        painter.end()
