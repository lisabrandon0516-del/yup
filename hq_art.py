"""Painted storefronts, department tiles, and the clean US map used by HQ pages."""

from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, Signal
from collections import deque

from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygon,
)
from PySide6.QtWidgets import QWidget, QSizePolicy

from open_late.ui.hq_adapter import CHAIN_COLORS, chain_logo_path, default_chain_id
from open_late.ui.theme import DASH_BG, DASH_CARD, DASH_LINE, DASH_MUTED, DASH_PIN_HIGH, DASH_PIN_LOW, DASH_PIN_MID, DASH_TEXT, TEXT, ui_font
from open_late.ui.us_states import (
    CONTERMINOUS,
    INSET_STATES,
    STATE_RINGS,
    project_region,
    region_aspect,
    region_extent,
    region_for_lonlat,
    state_for_city,
    wrap_alaska_lon,
)

# Simplified contiguous US outline (lon, lat).
_US = [
    (-124.7, 48.4), (-124.2, 43.0), (-124.4, 40.4), (-123.8, 38.9), (-122.4, 37.2),
    (-122.0, 36.3), (-120.9, 35.4), (-120.6, 34.5), (-117.1, 32.5), (-114.7, 32.7),
    (-110.8, 31.3), (-108.2, 31.3), (-106.5, 31.8), (-103.0, 29.1), (-101.5, 29.3),
    (-99.1, 26.4), (-97.4, 25.9), (-97.1, 27.7), (-93.9, 29.7), (-89.1, 29.1),
    (-89.0, 30.3), (-87.5, 30.3), (-85.0, 29.7), (-84.0, 30.3), (-83.0, 29.1),
    (-81.7, 25.2), (-80.1, 25.2), (-80.2, 27.3), (-81.3, 31.0), (-80.6, 32.1),
    (-75.6, 35.2), (-75.5, 38.0), (-74.0, 40.5), (-69.8, 41.3), (-70.0, 43.8),
    (-66.9, 44.8), (-67.1, 47.2), (-69.0, 47.4), (-71.6, 45.3), (-75.0, 44.9),
    (-76.8, 43.6), (-79.0, 43.6), (-82.5, 41.7), (-83.4, 42.4), (-84.8, 46.8),
    (-87.8, 47.6), (-90.6, 47.3), (-95.2, 49.0), (-107.0, 49.0), (-116.0, 49.0),
    (-123.3, 49.0), (-124.7, 48.4),
]

# A few interior lines to suggest regions without a state shapefile.
_DIVIDERS = [
    [(-108.2, 31.3), (-108.2, 49.0)],
    [(-104.0, 36.99), (-94.6, 36.99), (-89.1, 36.99)],
    [(-94.6, 29.3), (-94.6, 49.0)],
    [(-87.5, 30.3), (-87.5, 41.8), (-82.5, 41.7)],
    [(-117.1, 32.5), (-117.1, 42.0), (-124.2, 42.0)],
]

CITIES = {
    "seattle": ("Seattle", -122.33, 47.61, 8, -36),
    "las_vegas": ("Las Vegas", -115.14, 36.17, 10, 22),
    "houston": ("Houston", -95.37, 29.76, -10, 28),
    "evansville": ("Evansville", -87.55, 37.97, 18, 10),
    "naperville": ("Naperville", -88.15, 41.75, 16, -34),
}

LAND = QColor("#D5DAE3")
LAND_LINE = QColor("#8E96A3")
MAP_BG = QColor("#EEF1F4")
PIN = QColor("#16803C")
CALLOUT_BG = QColor(255, 255, 255, 245)
CALLOUT_INK = QColor("#122033")
CALLOUT_MUTED = QColor("#5B6573")
# Clear air between the lower 48 and the AK/HI band under it.
INSET_GUTTER = 12

# Perf caches shared by every StoreMap (pages rebuild their map on open).
# Projected Albers x/y never depend on the widget rect, so each state's rings
# are projected once per process; the per-rect pixel paths, land masks,
# leaders, and callout slots are keyed on the pins and the exact rect.
_PROJECTED_RINGS: dict[tuple[str, str], list[list[tuple[float, float]]]] = {}
_PATH_CACHE: dict[tuple, QPainterPath] = {}
_LAND_MASK_CACHE: dict[tuple, QImage] = {}
_LEADER_CACHE: dict[tuple, list[QPoint]] = {}
_CALLOUT_CACHE: dict[tuple, tuple[tuple[int, int, int, int], list[QPoint]]] = {}
_CACHE_LIMIT = 256
_ZERO_FLAG = bytes([1] + [0] * 255)
_ONE_FLAG = bytes([0, 1] + [0] * 254)


def _cache_put(cache: dict, key, value, limit: int = _CACHE_LIMIT) -> None:
    if len(cache) >= limit:
        cache.clear()
    cache[key] = value


def _projected_rings(abbr: str, region: str) -> list[list[tuple[float, float]]]:
    key = (abbr, region)
    rings = _PROJECTED_RINGS.get(key)
    if rings is None:
        rings = [
            [project_region(lon, lat, region) for lon, lat in ring]
            for ring in (STATE_RINGS.get(abbr) or [])
        ]
        _PROJECTED_RINGS[key] = rings
    return rings


def _pins_signature(pins: list[dict]) -> str:
    """Stable key for the caller-supplied pin data (layout scratch keys skipped)."""
    return repr([
        sorted((str(k), repr(v)) for k, v in pin.items() if not str(k).startswith("_"))
        for pin in pins
    ])


def _letterbox_rect(target: QRect, aspect: float, *, margin: int = 0, top_gutter: int = 0) -> QRect:
    """Largest centered rect of the given aspect that fits inside target."""
    if target.width() < 2 or target.height() < 2 or aspect <= 0:
        return QRect(target)
    inner = target.adjusted(margin, margin + top_gutter, -margin, -margin)
    if inner.width() < 2 or inner.height() < 2:
        inner = QRect(target)
    box_aspect = inner.width() / max(1, inner.height())
    if aspect > box_aspect:
        width = inner.width()
        height = max(2, int(round(width / aspect)))
    else:
        height = inner.height()
        width = max(2, int(round(height * aspect)))
    x = inner.x() + (inner.width() - width) // 2
    y = inner.y() + (inner.height() - height) // 2
    return QRect(x, y, width, height)


def _xy_to_point(x: float, y: float, used: QRect, extent: tuple[float, float, float, float]) -> QPoint:
    minx, miny, maxx, maxy = extent
    span_x = maxx - minx
    span_y = maxy - miny
    if span_x <= 0 or span_y <= 0 or used.width() < 1 or used.height() < 1:
        return used.center()
    px = used.x() + (x - minx) / span_x * used.width()
    py = used.y() + (maxy - y) / span_y * used.height()
    return QPoint(int(round(px)), int(round(py)))


def _project_region_to_rect(lon: float, lat: float, rect: QRect, region: str = "CONUS", *, margin: int = 0, top_gutter: int = 0) -> QPoint:
    used = _letterbox_rect(rect, region_aspect(region), margin=margin, top_gutter=top_gutter)
    x, y = project_region(lon, lat, region)
    return _xy_to_point(x, y, used, region_extent(region))


def _project(lon: float, lat: float, rect: QRect) -> QPoint:
    """Project a CONUS lon/lat into rect, letterboxed to the Albers land aspect."""
    return _project_region_to_rect(lon, lat, rect, "CONUS")


def _bounds_of(abbr: str, pad_lon: float = 0.45, pad_lat: float = 0.28) -> tuple[float, float, float, float]:
    rings = STATE_RINGS.get(abbr) or []
    xs = [pt[0] for ring in rings for pt in ring]
    ys = [pt[1] for ring in rings for pt in ring]
    if not xs:
        return (-180.0, 0.0, -60.0, 70.0)
    return (min(xs) - pad_lon, min(ys) - pad_lat, max(xs) + pad_lon, max(ys) + pad_lat)


def _project_fitted(lon: float, lat: float, rect: QRect, west: float, south: float, east: float, north: float, pad: float = 0.10) -> QPoint:
    """Letterbox a lon/lat into rect, leaving a small inner margin for the frame."""
    inner = QRectF(rect)
    inset_x = max(6.0, inner.width() * pad)
    inset_y = max(8.0, inner.height() * pad)
    inner.adjust(inset_x, inset_y + 4, -inset_x, -inset_y)
    span_x = east - west
    span_y = north - south
    if span_x <= 0 or span_y <= 0 or inner.width() <= 1 or inner.height() <= 1:
        return rect.center()
    aspect = span_x / span_y
    box_aspect = inner.width() / inner.height()
    if aspect > box_aspect:
        use_w = inner.width()
        use_h = use_w / aspect
    else:
        use_h = inner.height()
        use_w = use_h * aspect
    x0 = inner.x() + (inner.width() - use_w) / 2
    y0 = inner.y() + (inner.height() - use_h) / 2
    x = x0 + (float(lon) - west) / span_x * use_w
    y = y0 + (north - float(lat)) / span_y * use_h
    return QPoint(int(round(x)), int(round(y)))


def _ink_for(color: QColor) -> QColor:
    luma = 0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()
    return QColor("#10203A") if luma > 150 else QColor("#F7FBFF")


def store_badge_rect(center: QPoint, size: int = 20) -> QRect:
    return QRect(int(center.x()) - size // 2, int(center.y()) - size // 2, size, size)


def draw_store_badge(
    painter: QPainter,
    center: QPoint,
    color: QColor,
    *,
    size: int = 20,
    selected: bool = False,
    hover: bool = False,
    count: int = 1,
    unowned: bool = False,
) -> QRect:
    """Draw a rounded storefront badge. Status color fills the badge; the shop is a QPainter glyph."""
    rect = store_badge_rect(center, size)
    radius = max(3.5, size * 0.22)
    # Soft drop so the badge stays readable on land washes.
    shadow = QColor(0, 0, 0, 90)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(shadow)
    painter.drawRoundedRect(QRectF(rect).translated(0, 1.2), radius, radius)
    if selected or hover:
        ring = QColor("#FFFFFF") if selected else QColor(color)
        ring.setAlpha(230 if selected else 170)
        painter.setPen(QPen(ring, 2.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(rect).adjusted(-2.2, -2.2, 2.2, 2.2), radius + 1, radius + 1)
    painter.setPen(QPen(QColor("#F4F7FF"), 1.15 if not unowned else 1.0))
    painter.setBrush(color)
    painter.drawRoundedRect(QRectF(rect), radius, radius)

    ink = _ink_for(color)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(ink)
    # Peaked awning / roof
    roof = QPainterPath()
    top = rect.y() + size * 0.16
    eaves = rect.y() + size * 0.42
    roof.moveTo(rect.center().x(), top)
    roof.lineTo(rect.right() - size * 0.16, eaves)
    roof.lineTo(rect.left() + size * 0.16, eaves)
    roof.closeSubpath()
    painter.drawPath(roof)
    # Shop body
    body = QRectF(rect.x() + size * 0.22, eaves - 0.5, size * 0.56, rect.bottom() - (eaves - 0.5) - size * 0.14)
    painter.drawRoundedRect(body, 1.2, 1.2)
    # Cut door and windows out of the body by overpainting the badge fill, then window panes.
    painter.setBrush(color)
    door_w, door_h = size * 0.16, size * 0.28
    door = QRectF(rect.center().x() - door_w / 2, body.bottom() - door_h, door_w, door_h)
    painter.drawRect(door)
    win_s = max(2.0, size * 0.12)
    gap = size * 0.08
    left_win = QRectF(body.x() + gap, body.y() + gap * 0.8, win_s, win_s)
    right_win = QRectF(body.right() - gap - win_s, body.y() + gap * 0.8, win_s, win_s)
    painter.drawRect(left_win)
    painter.drawRect(right_win)
    # Window panes slightly lighter so they read at 16px.
    pane = QColor(ink)
    pane.setAlpha(180)
    painter.setBrush(pane)
    painter.drawRect(left_win.adjusted(0.4, 0.4, -0.4, -0.4))
    painter.drawRect(right_win.adjusted(0.4, 0.4, -0.4, -0.4))

    if count and count > 1:
        badge = max(10, int(size * 0.55))
        cx = rect.right() - 1
        cy = rect.top() + 1
        bubble = QRect(cx - badge // 2, cy - badge // 2, badge, badge)
        painter.setPen(QPen(QColor("#F4F7FF"), 1))
        painter.setBrush(QColor("#10203A"))
        painter.drawEllipse(bubble)
        painter.setPen(QColor("#F4F7FF"))
        painter.setFont(ui_font(max(7, badge - 4), QFont.Weight.DemiBold))
        label = "9+" if count > 9 else str(count)
        painter.drawText(bubble, Qt.AlignmentFlag.AlignCenter, label)
    return rect


def chain_pixmap(chain_id: str | None, width: int, height: int) -> QPixmap:
    path = chain_logo_path(chain_id or default_chain_id())
    pix = QPixmap(str(path)) if path.exists() else QPixmap()
    if pix.isNull():
        return pix
    return pix.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)


def brand_pixmap(width: int, height: int) -> QPixmap:
    path = Path(__file__).resolve().parent.parent / "assets" / "brand" / "game_icon.png"
    pix = QPixmap(str(path)) if path.exists() else QPixmap()
    if pix.isNull():
        return pix
    return pix.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)



class StorefrontArt(QWidget):
    """A painted supercenter facade with the chosen chain's logo on the sign."""

    def __init__(self, chain_id: str | None = None, parent=None, hero: bool = False, compact: bool = False):
        super().__init__(parent)
        self.chain_id = chain_id or default_chain_id()
        self.open_badge = True
        self.hero = hero
        self.compact = compact
        self.setSizePolicy(QSizePolicy.Policy.Fixed if compact else QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._apply_art_size()

    def _apply_art_size(self) -> None:
        if self.compact:
            self.setFixedSize(100, 48)
        else:
            self.setMinimumWidth(0)
            self.setMaximumWidth(16777215)
            self.setFixedHeight(200 if self.hero else 132)

    def set_chain(self, chain_id: str | None, open_badge: bool = True, hero: bool = False) -> None:
        self.chain_id = chain_id or default_chain_id()
        self.open_badge = open_badge
        self.hero = hero
        self._apply_art_size()
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        colors = CHAIN_COLORS.get(self.chain_id, CHAIN_COLORS["megamart"])
        fascia = QColor(colors["fascia"])
        accent = QColor(colors["accent"])
        wall = QColor(colors.get("wall") or "#EFE8D8")
        trim = QColor(colors.get("trim") or "#0B3A67")

        # Sky
        sky = QLinearGradient(0, 0, 0, int(h * 0.58))
        sky.setColorAt(0.0, QColor("#9EC6EA"))
        sky.setColorAt(0.55, QColor("#C5DDF0"))
        sky.setColorAt(1.0, QColor("#E7EEF4"))
        painter.fillRect(0, 0, w, h, sky)
        # Soft cloud
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 80))
        painter.drawEllipse(int(w * 0.12), int(h * 0.04), int(w * 0.22), int(h * 0.10))
        painter.drawEllipse(int(w * 0.22), int(h * 0.06), int(w * 0.16), int(h * 0.08))

        # Distant tree
        painter.setBrush(QColor("#5B8F3A"))
        painter.drawEllipse(int(w * 0.04), int(h * 0.42), int(w * 0.10), int(h * 0.16))
        painter.setBrush(QColor("#6B4F3A"))
        painter.drawRect(int(w * 0.08), int(h * 0.54), 4, int(h * 0.10))

        # Lot
        lot_y = int(h * 0.78)
        painter.setBrush(QColor("#B7BCC4"))
        painter.drawRect(0, lot_y, w, h - lot_y)
        painter.setPen(QPen(QColor("#D5DAE0"), 1, Qt.PenStyle.DashLine))
        for i in range(5):
            x = int(w * (0.12 + i * 0.16))
            painter.drawLine(x, lot_y + 4, x, h - 3)
        # Cart corral
        painter.setPen(QPen(QColor("#C42B1C"), 2))
        painter.setBrush(QColor(255, 255, 255, 60))
        painter.drawRect(int(w * 0.78), lot_y - 6, int(w * 0.14), int(h * 0.12))

        # Building mass
        bx, by = int(w * 0.06), int(h * 0.22)
        bw, bh = int(w * 0.88), int(h * 0.58)
        # Side wing
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(wall.darker(108))
        painter.drawRect(bx + bw - int(bw * 0.18), by + int(h * 0.10), int(bw * 0.18), bh - int(h * 0.10))
        # Main wall
        painter.setBrush(wall)
        painter.setPen(QPen(QColor("#D5CDB8"), 1))
        painter.drawRect(bx, by + int(h * 0.14), int(bw * 0.84), bh - int(h * 0.14))

        # Entry canopy
        canopy_y = by + int(h * 0.30)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#D9D3C4"))
        painter.drawRect(bx + int(bw * 0.28), canopy_y, int(bw * 0.30), 8)
        painter.setBrush(QColor("#C9C3B4"))
        painter.drawRect(bx + int(bw * 0.27), canopy_y + 8, int(bw * 0.32), 3)

        # Fascia / sign
        fascia_h = max(28, int(h * 0.20))
        painter.setBrush(fascia)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(bx, by, bw, fascia_h)
        painter.setBrush(accent)
        painter.drawRect(bx, by + fascia_h - 3, bw, 3)

        # Logo on a white sign board
        logo = chain_pixmap(self.chain_id, max(60, int(bw * 0.46)), max(18, fascia_h - 10))
        if not logo.isNull():
            chip_w, chip_h = logo.width() + 16, logo.height() + 8
            lx = bx + (bw - chip_w) // 2
            ly = by + max(4, (fascia_h - 3 - chip_h) // 2)
            painter.setBrush(QColor("#FFFFFF"))
            painter.setPen(QPen(QColor(0, 0, 0, 28), 1))
            painter.drawRoundedRect(lx, ly, chip_w, chip_h, 5, 5)
            painter.drawPixmap(lx + 8, ly + 4, logo)

        # Glass bays
        glass_top = by + fascia_h + 8
        glass_h = lot_y - glass_top - 4
        bay = max(18, int((bw * 0.84 - 20) / 5))
        for i in range(5):
            gx = bx + 8 + i * (bay + 4)
            if i in (2,):
                # Automatic doors — darker glass, vertical divider
                painter.setBrush(QColor("#6A9BC4"))
                painter.setPen(QPen(trim, 1))
                painter.drawRect(gx, glass_top, bay, glass_h)
                painter.setPen(QPen(QColor("#EEF6FC"), 1))
                painter.drawLine(gx + bay // 2, glass_top + 2, gx + bay // 2, glass_top + glass_h - 2)
            else:
                grad = QLinearGradient(gx, glass_top, gx + bay, glass_top + glass_h)
                grad.setColorAt(0.0, QColor("#B9D4EA"))
                grad.setColorAt(0.55, QColor("#8FB6D4"))
                grad.setColorAt(1.0, QColor("#7AA3C6"))
                painter.setBrush(grad)
                painter.setPen(QPen(QColor("#C9D8E4"), 1))
                painter.drawRect(gx, glass_top, bay, glass_h)
                # Window highlights
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(255, 255, 255, 60))
                painter.drawRect(gx + 3, glass_top + 3, max(4, bay // 3), max(6, glass_h // 3))

        # Curb
        painter.setBrush(QColor("#C5C1B6"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(bx, lot_y - 3, int(bw * 0.84), 4)

        if self.open_badge:
            badge = QRect(w - 54, 8, 46, 18)
            painter.setBrush(QColor("#1F9A56"))
            painter.drawRoundedRect(badge, 9, 9)
            painter.setPen(QColor("#FFFFFF"))
            painter.setFont(ui_font(10, QFont.Weight.DemiBold))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, "Open")
        painter.end()


def paint_department_icon(painter: QPainter, rect: QRect, department: str, color: str) -> None:
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    bg = QColor(color)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(bg)
    painter.drawRoundedRect(rect, 8, 8)
    painter.setPen(QPen(QColor("#FFFFFF"), 2))
    cx, cy = rect.center().x(), rect.center().y()
    r = min(rect.width(), rect.height()) // 2 - 6
    dept = department.lower()
    aliases = {'dairy': 'meat_dairy', 'apparel': 'clothing', 'home': 'home_garden',
               'health': 'health_beauty', 'bakery': 'grocery'}
    dept = aliases.get(dept, dept)
    if dept == "produce":
        painter.drawEllipse(QPoint(cx, cy), r - 2, r - 4)
        painter.drawLine(cx, cy - r + 2, cx + 4, cy - r - 2)
    elif dept == "dairy":
        painter.drawRoundedRect(cx - r + 2, cy - r + 4, 2 * r - 4, 2 * r - 6, 3, 3)
    elif dept == "bakery":
        painter.drawArc(cx - r, cy - r // 2, 2 * r, r + 4, 0, 180 * 16)
        painter.drawLine(cx - r, cy, cx + r, cy)
    elif dept == "frozen":
        painter.drawLine(cx, cy - r, cx, cy + r)
        painter.drawLine(cx - r, cy, cx + r, cy)
        painter.drawLine(cx - r + 3, cy - r + 3, cx + r - 3, cy + r - 3)
    elif dept == "electronics":
        painter.drawRoundedRect(cx - r, cy - r + 4, 2 * r, 2 * r - 8, 3, 3)
        painter.drawLine(cx - 4, cy + r - 4, cx + 4, cy + r - 4)
    elif dept == "apparel":
        path = QPainterPath()
        path.moveTo(cx, cy - r + 2)
        path.lineTo(cx + r - 2, cy - 2)
        path.lineTo(cx + r - 6, cy + r - 2)
        path.lineTo(cx - r + 6, cy + r - 2)
        path.lineTo(cx - r + 2, cy - 2)
        path.closeSubpath()
        painter.drawPath(path)
    elif dept == "home":
        path = QPainterPath()
        path.moveTo(cx, cy - r)
        path.lineTo(cx + r, cy)
        path.lineTo(cx + r - 4, cy)
        path.lineTo(cx + r - 4, cy + r)
        path.lineTo(cx - r + 4, cy + r)
        path.lineTo(cx - r + 4, cy)
        path.lineTo(cx - r, cy)
        path.closeSubpath()
        painter.drawPath(path)
    elif dept == "toys":
        painter.drawEllipse(QPoint(cx - 4, cy - 2), r // 2, r // 2)
        painter.drawEllipse(QPoint(cx + 5, cy + 3), r // 2 - 1, r // 2 - 1)
    elif dept in ("health", "health_beauty", "pharmacy"):
        painter.setBrush(QColor("#FFFFFF"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(cx - 3, cy - r + 2, 6, 2 * r - 4)
        painter.drawRect(cx - r + 2, cy - 3, 2 * r - 4, 6)
    elif dept == "meat_dairy":
        painter.drawRoundedRect(cx - r + 2, cy - r + 4, 2 * r - 4, 2 * r - 6, 3, 3)
        painter.drawLine(cx - r + 6, cy, cx + r - 6, cy)
    elif dept in ("household",):
        painter.drawRect(cx - r + 4, cy - r + 6, 2 * r - 8, 2 * r - 10)
    elif dept in ("home", "home_garden"):
        path = QPainterPath()
        path.moveTo(cx, cy - r)
        path.lineTo(cx + r, cy)
        path.lineTo(cx + r - 4, cy)
        path.lineTo(cx + r - 4, cy + r)
        path.lineTo(cx - r + 4, cy + r)
        path.lineTo(cx - r + 4, cy)
        path.lineTo(cx - r, cy)
        path.closeSubpath()
        painter.drawPath(path)
    elif dept == "sporting":
        painter.drawEllipse(QPoint(cx, cy), r - 2, r - 2)
        painter.drawLine(cx - r + 4, cy + r - 4, cx + r - 4, cy - r + 4)
    elif dept == "seasonal":
        painter.drawEllipse(QPoint(cx, cy - 2), r - 3, r - 3)
        painter.drawLine(cx, cy + 2, cx, cy + r - 1)
    elif dept == "clothing":
        path = QPainterPath()
        path.moveTo(cx, cy - r + 2)
        path.lineTo(cx + r - 2, cy - 2)
        path.lineTo(cx + r - 6, cy + r - 2)
        path.lineTo(cx - r + 6, cy + r - 2)
        path.lineTo(cx - r + 2, cy - 2)
        path.closeSubpath()
        painter.drawPath(path)
    else:  # grocery
        painter.drawRoundedRect(cx - r + 1, cy - r + 6, 2 * r - 2, 2 * r - 8, 3, 3)
        painter.drawLine(cx - r + 4, cy - 2, cx + r - 4, cy - 2)
    painter.restore()


class DepartmentTile(QWidget):
    def __init__(self, department: str, label: str, color: str, caption: str = "", parent=None):
        super().__init__(parent)
        self.department = department
        self.label = label
        self.color = color
        self.caption = caption
        self.setMinimumSize(72, 88)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        icon = QRect(12, 6, self.width() - 24, min(56, self.height() - 28))
        if icon.width() > 0 and icon.height() > 0:
            paint_department_icon(painter, icon, self.department, self.color)
        painter.setPen(QColor(TEXT))
        painter.setFont(ui_font(10, QFont.Weight.DemiBold))
        text = self.caption or self.label
        painter.drawText(QRect(4, self.height() - 22, self.width() - 8, 20), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, text)
        painter.end()




def place_callout(
    point: QPoint,
    box_w: int,
    box_h: int,
    bounds: QRect,
    preferred: tuple[int, int] = (12, -28),
    occupied: list | None = None,
) -> QRect:
    """Flip or clamp a callout so it stays inside bounds and misses earlier callouts."""
    inner = QRect(bounds).adjusted(4, 4, -4, -4)
    if inner.width() < 8 or inner.height() < 8:
        inner = QRect(bounds)
    box_w = min(box_w, max(24, inner.width()))
    box_h = min(box_h, max(16, inner.height()))
    ox, oy = preferred
    blockers = [QRect(*item) if not isinstance(item, QRect) else item for item in (occupied or [])]

    def overlaps(box: QRect) -> bool:
        return any(box.intersects(other.adjusted(2, 2, -2, -2)) for other in blockers)

    candidates = [
        (ox, oy),
        (-box_w - 8, oy),
        (ox, 8),
        (-box_w - 8, 8),
        (ox, -box_h - 6),
        (-box_w - 8, -box_h - 6),
        (8, -box_h - 6),
        (-box_w // 2, -box_h - 6),
        (-box_w // 2, 8),
        (12, -box_h - 6),
        (-box_w - 12, 10),
    ]
    # Also try sliding along the bounds in a small grid so two inset pins can both show.
    for dx in (0, 8, -8, 16, -16, 24, -24, 40, -40, 56, -56):
        for dy in (0, -box_h - 6, 8, -20, 20, -box_h - 16):
            candidates.append((dx, dy))
    seen = set()
    for xoff, yoff in candidates:
        box = QRect(point.x() + xoff, point.y() + yoff, box_w, box_h)
        key = (box.x(), box.y(), box.width(), box.height())
        if key in seen:
            continue
        seen.add(key)
        if inner.contains(box) and not overlaps(box):
            return box
    # Clamp inside bounds, preferring a side that misses other callouts.
    bx = max(inner.left(), min(inner.right() - box_w, point.x() + ox))
    by = max(inner.top(), min(inner.bottom() - box_h, point.y() + oy))
    clamped = QRect(bx, by, box_w, box_h)
    if not overlaps(clamped):
        return clamped
    for x in range(inner.left(), max(inner.left(), inner.right() - box_w) + 1, 4):
        for y in range(inner.top(), max(inner.top(), inner.bottom() - box_h) + 1, 4):
            box = QRect(x, y, box_w, box_h)
            if inner.contains(box) and not overlaps(box):
                return box
    return clamped


class StoreMap(QWidget):
    """US map with simplified state borders, storefront badges, and AK/HI insets."""

    store_clicked = Signal(str)
    sign_requested = Signal(str)

    def __init__(self, parent=None, theme: str = "light"):
        super().__init__(parent)
        self.setObjectName("storeMap")
        self.setMinimumHeight(240)
        self.pins: list[dict] = []
        self._hover = ""
        self.theme = theme
        self._land_mask_cache: dict = _LAND_MASK_CACHE
        self._leader_cache: dict = _LEADER_CACHE
        self._mask_bytes: dict = {}
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.show_places = False
        self._place_abbr = ""
        self._place_hits: list[tuple[QRect, str]] = []
        self._painted_states: list[tuple[str, QPainterPath]] = []
        self._label_points: dict[tuple, QPoint] = {}

    def set_show_places(self, show: bool) -> None:
        self.show_places = bool(show)
        self.update()

    def set_theme(self, theme: str) -> None:
        # Masks and leaders are geometry only; the shared caches stay valid.
        self.theme = theme
        self.update()

    def set_pins(self, pins: list[dict]) -> None:
        # Caches are keyed on the pin data and rect, so nothing is wiped here;
        # identical pins on a rebuilt page reuse the mask, leader, and callout.
        self.pins = pins
        self.update()

    def _cache_tag(self) -> tuple:
        host = self._host_rect()
        return (_pins_signature(self.pins), host.x(), host.y(), host.width(), host.height())

    def _host_rect(self) -> QRect:
        """The visible map, not the overflowing minimum-height cell on a tight dashboard."""
        vis = self.visibleRegion().boundingRect()
        if vis.isValid() and vis.width() >= 80 and vis.height() >= 80:
            return vis
        return self.rect()

    def _canvas_rect(self) -> QRect:
        host = self._host_rect()
        return QRect(host.x() + 8, host.y() + 6, max(40, host.width() - 16), max(40, host.height() - 14))

    def inset_frames(self) -> dict[str, QRect]:
        """Alaska (left) and Hawaii (right) sit bottom-left, in a band under the lower 48."""
        host = self._host_rect()
        w, h = host.width(), host.height()
        pad = 8
        gap = 10
        ak_aspect = region_aspect("AK")
        hi_aspect = region_aspect("HI")
        # Leave most of the card for CONUS; keep a reserved strip on the right for the callout.
        band = max(52, min(int(h * 0.26), 96))
        ak_h = band
        ak_w = max(72, int(round(ak_h * ak_aspect)))
        max_ak_w = max(88, int(w * 0.34))
        if ak_w > max_ak_w:
            ak_w = max_ak_w
            ak_h = max(44, int(round(ak_w / max(ak_aspect, 0.1))))
        hi_h = max(44, int(round(ak_h * 0.72)))
        hi_w = max(80, int(round(hi_h * hi_aspect)))
        # Re-derive HI height so the frame keeps the source aspect after the width floor.
        hi_h = max(44, int(round(hi_w / max(hi_aspect, 0.1))))
        callout_reserve = 168
        needed = pad + ak_w + gap + hi_w + gap + callout_reserve
        if needed > w - pad:
            scale = (w - 2 * pad - gap - gap - callout_reserve) / max(1, ak_w + hi_w)
            scale = min(1.0, max(0.55, scale))
            ak_w = max(96, int(ak_w * scale))
            hi_w = max(80, int(hi_w * scale))
            ak_h = max(48, int(round(ak_w / max(ak_aspect, 0.1))))
            hi_h = max(44, int(round(hi_w / max(hi_aspect, 0.1))))
        # If the card is very short, shrink the band rather than climbing onto CONUS.
        max_band = max(40, h - 80 - INSET_GUTTER - pad)
        if ak_h > max_band:
            ak_h = max_band
            ak_w = max(96, int(round(ak_h * ak_aspect)))
            hi_w = max(80, min(hi_w, int(round(max(36, ak_h * 0.72) * hi_aspect))))
            hi_h = max(44, int(round(hi_w / max(hi_aspect, 0.1))))
            if hi_h > ak_h:
                hi_h = ak_h
                hi_w = max(80, int(round(hi_h * hi_aspect)))
        ak = QRect(host.x() + pad, host.bottom() - pad - ak_h, ak_w, ak_h)
        hi = QRect(ak.right() + 1 + gap, host.bottom() - pad - hi_h, hi_w, hi_h)
        hi.moveBottom(ak.bottom())
        return {"AK": ak, "HI": hi}

    def conus_rect(self) -> QRect:
        """The lower 48 live in the band above the insets, with a clear gutter."""
        canvas = self._canvas_rect()
        frames = self.inset_frames()
        dock = frames["AK"].united(frames["HI"])
        bottom = dock.top() - INSET_GUTTER
        height = max(40, bottom - canvas.y())
        return QRect(canvas.x(), canvas.y(), canvas.width(), height)

    def _map_rect(self) -> QRect:
        # Kept for older callers; the lower 48 now use conus_rect().
        return self.conus_rect()

    def conus_draw_rect(self) -> QRect:
        """The letterboxed rectangle the lower 48 actually occupy."""
        return _letterbox_rect(self.conus_rect(), region_aspect("CONUS"))

    def conus_bounds_rect(self) -> QRect:
        """Pixel bounding rect of the contiguous state shapes."""
        bounds = QRect()
        rect = self.conus_rect()
        for abbr in CONTERMINOUS:
            path = self._path_for(abbr, rect, inset=False)
            if path.isEmpty():
                continue
            box = path.boundingRect().toAlignedRect()
            bounds = box if bounds.isNull() else bounds.united(box)
        return bounds if bounds.isValid() else self.conus_draw_rect()

    def state_paths(self) -> list[QPainterPath]:
        """All drawn state polygons, including the AK/HI inset land."""
        paths = []
        conus = self.conus_rect()
        for abbr in CONTERMINOUS:
            path = self._path_for(abbr, conus, inset=False)
            if not path.isEmpty():
                paths.append(path)
        frames = self.inset_frames()
        for abbr, frame in frames.items():
            path = self._path_for(abbr, frame, inset=True)
            if not path.isEmpty():
                paths.append(path)
        return paths

    def callout_hits_states(self, box: QRect) -> bool:
        area = QRectF(box)
        return any(path.intersects(area) for path in self.state_paths())

    def source_map_aspect(self, region: str = "CONUS") -> float:
        return region_aspect(region)

    def drawn_map_aspect(self, region: str = "CONUS") -> float:
        if region in ("AK", "HI"):
            used = _letterbox_rect(self.inset_frames()[region], region_aspect(region), margin=4, top_gutter=14)
        else:
            used = self.conus_draw_rect()
        return used.width() / max(1, used.height())

    def badge_size(self) -> int:
        rect = self.conus_rect()
        return max(16, min(22, min(rect.width(), rect.height()) // 16))

    def pin_region(self, pin: dict) -> str:
        return region_for_lonlat(pin.get("lon"), pin.get("lat"))

    def project_pin(self, pin: dict) -> QPoint:
        """Project a pin into the CONUS map or the AK/HI inset that owns it."""
        lon = float(pin.get("lon") or 0)
        lat = float(pin.get("lat") or 0)
        region = region_for_lonlat(lon, lat)
        if region in ("AK", "HI"):
            return _project_region_to_rect(
                lon, lat, self.inset_frames()[region], region, margin=4, top_gutter=14,
            )
        return _project(lon, lat, self.conus_rect())

    def _pin_point(self, pin: dict) -> QPoint:
        # Prefer the laid-out (possibly offset) point when one is already on the pin.
        point = pin.get("_point")
        if isinstance(point, QPoint):
            return QPoint(point)
        return self.project_pin(pin)

    def _clamp_pin_point(self, point: QPoint, pin: dict, frames: dict[str, QRect], size: int) -> QPoint:
        region = pin.get("_region") or self.pin_region(pin)
        box = frames.get(region) if region in ("AK", "HI") else self.conus_rect()
        if box is None or box.width() < size or box.height() < size:
            box = self._host_rect()
        half = max(1, size // 2)
        x = max(box.left() + half, min(box.right() - half, point.x()))
        y = max(box.top() + half, min(box.bottom() - half, point.y()))
        return QPoint(x, y)

    def _move_stack(self, laid: list[dict], old: QPoint, new: QPoint, size: int) -> None:
        """Keep stacked doors (same badge, same point) together when one is nudged."""
        for item in laid:
            if item.get("_point") == old:
                item["_point"] = QPoint(new)
                item["_badge"] = store_badge_rect(new, size)

    def _separate_badges(self, laid: list[dict], size: int) -> list[dict]:
        """Push overlapping store badges apart so their rects do not share a pixel."""
        frames = self.inset_frames()
        for _ in range(48):
            moved = False
            seen = set()
            reps = []
            for pin in laid:
                point = pin.get("_point")
                if point is None:
                    continue
                key = (point.x(), point.y())
                if key in seen:
                    continue
                seen.add(key)
                reps.append(pin)
            for index, pin in enumerate(reps):
                ra = pin.get("_badge")
                if ra is None:
                    continue
                for other in reps[index + 1:]:
                    rb = other.get("_badge")
                    if rb is None or not ra.intersects(rb):
                        continue
                    ac = QPoint(pin["_point"])
                    bc = QPoint(other["_point"])
                    dx = float(bc.x() - ac.x())
                    dy = float(bc.y() - ac.y())
                    dist = math.hypot(dx, dy)
                    need = float(size + 2)
                    if dist < 0.5:
                        dx, dy, dist = 1.0, -1.0, math.hypot(1.0, -1.0)
                    step = (need - dist) / dist
                    ox = int(math.ceil(abs(dx * step) / 2)) or 1
                    oy = int(math.ceil(abs(dy * step) / 2)) or 1
                    ox = ox if dx >= 0 else -ox
                    oy = oy if dy >= 0 else -oy
                    new_a = self._clamp_pin_point(QPoint(ac.x() - ox, ac.y() - oy), pin, frames, size)
                    new_b = self._clamp_pin_point(QPoint(bc.x() + ox, bc.y() + oy), other, frames, size)
                    self._move_stack(laid, ac, new_a, size)
                    self._move_stack(laid, bc, new_b, size)
                    ra = pin["_badge"]
                    moved = True
            if not moved:
                break
        return laid

    def layout_pins(self) -> list[dict]:
        """Project pins, then offset close neighbors or stack exact overlaps with a count."""
        if not self.pins:
            return []
        size = self.badge_size()
        frames = self.inset_frames()
        self._callout_boxes: list[QRect] = []
        raw = []
        for pin in self.pins:
            pin["_region"] = self.pin_region(pin)
            pin["_raw"] = self.project_pin(pin)
            raw.append(pin)

        used = set()
        groups: list[list[dict]] = []
        # Group anything whose badges would already collide at the raw projection.
        thresh = max(size, 16)
        for index, pin in enumerate(raw):
            if index in used:
                continue
            group = [pin]
            used.add(index)
            px, py = pin["_raw"].x(), pin["_raw"].y()
            for other_index, other in enumerate(raw):
                if other_index in used:
                    continue
                dx = other["_raw"].x() - px
                dy = other["_raw"].y() - py
                if dx * dx + dy * dy <= thresh * thresh:
                    group.append(other)
                    used.add(other_index)
            groups.append(group)

        laid: list[dict] = []
        for group in groups:
            n = len(group)
            same_spot = all(item["_raw"] == group[0]["_raw"] for item in group)
            if n == 1:
                point = self._clamp_pin_point(QPoint(group[0]["_raw"]), group[0], frames, size)
                group[0]["_point"] = point
                group[0]["_count"] = 1
                group[0]["_badge"] = store_badge_rect(point, size)
                laid.append(group[0])
                continue
            # Stack exact same-door overlaps first, then fan the distinct locations
            # so Houston A/B stay one badge even if Dallas is nearby.
            spots: dict[tuple, list[dict]] = {}
            for item in group:
                key = (
                    round(float(item.get("lon") or 0), 3),
                    round(float(item.get("lat") or 0), 3),
                )
                spots.setdefault(key, []).append(item)
            locations = list(spots.values())
            if len(locations) == 1:
                cx = int(round(sum(item["_raw"].x() for item in group) / n))
                cy = int(round(sum(item["_raw"].y() for item in group) / n))
                point = self._clamp_pin_point(QPoint(cx, cy), group[0], frames, size)
                for item in group:
                    item["_point"] = QPoint(point)
                    item["_count"] = n
                    item["_badge"] = store_badge_rect(point, size)
                    laid.append(item)
                continue
            # Fan along each stack's raw bearing from the centroid so north stays north.
            reps = []
            for cluster in locations:
                rx = sum(item["_raw"].x() for item in cluster) / len(cluster)
                ry = sum(item["_raw"].y() for item in cluster) / len(cluster)
                reps.append((rx, ry, cluster))
            cx = sum(item[0] for item in reps) / len(reps)
            cy = sum(item[1] for item in reps) / len(reps)
            radius = max(size + 2, 16)
            for k, (rx, ry, cluster) in enumerate(reps):
                dx, dy = rx - cx, ry - cy
                if math.hypot(dx, dy) < 0.5:
                    angle = math.radians(-90 + 360.0 * k / len(reps))
                else:
                    angle = math.atan2(dy, dx)
                point = QPoint(int(round(cx + radius * math.cos(angle))), int(round(cy + radius * math.sin(angle))))
                point = self._clamp_pin_point(point, cluster[0], frames, size)
                count = len(cluster)
                for item in cluster:
                    item["_point"] = QPoint(point)
                    item["_count"] = count
                    item["_badge"] = store_badge_rect(point, size)
                    laid.append(item)
        return self._separate_badges(laid, size)

    def primary_callout_pin(self, laid: list[dict] | None = None) -> dict | None:
        """One callout: the selected store, else Evansville, else the first owned door."""
        laid = laid if laid is not None else self.layout_pins()
        chosen = [pin for pin in laid if pin.get("selected") and pin.get("owned")]
        if chosen:
            return chosen[0]
        for pin in laid:
            if str(pin.get("id") or "") == "evansville" and pin.get("owned"):
                return pin
        for pin in laid:
            if pin.get("owned") and (pin.get("sales_label") or pin.get("selected")):
                return pin
        return None

    def _callout_slot(self, box_w: int, box_h: int, pin: dict) -> QRect:
        """Park the callout in a free card corner, never over a state shape."""
        host = self._host_rect()
        frames = self.inset_frames()
        dock = frames["AK"].united(frames["HI"])
        pad = 8
        candidates: list[QRect] = []
        # Preferred: bottom-right of the inset band, to the right of Hawaii.
        x = min(host.right() - pad - box_w, max(dock.right() + 10, host.right() - pad - box_w))
        y = dock.bottom() - box_h
        candidates.append(QRect(x, y, box_w, box_h))
        # Bottom-right of the whole card.
        candidates.append(QRect(host.right() - pad - box_w, host.bottom() - pad - box_h, box_w, box_h))
        # Top-right, then top-left, then bottom-left (above the insets).
        candidates.append(QRect(host.right() - pad - box_w, host.top() + pad, box_w, box_h))
        candidates.append(QRect(host.left() + pad, host.top() + pad, box_w, box_h))
        candidates.append(QRect(host.right() - pad - box_w, dock.top() - INSET_GUTTER - box_h, box_w, box_h))
        # A few slides if the preferred corner is tight.
        for dx, dy in ((-20, 0), (-40, 0), (0, -12), (0, 12), (-20, -12)):
            base = candidates[0]
            candidates.append(QRect(base.x() + dx, base.y() + dy, box_w, box_h))

        def blocked(box: QRect) -> bool:
            if not host.adjusted(2, 2, -2, -2).contains(box) and not host.contains(box):
                if not host.intersects(box):
                    return True
            if not host.contains(box):
                return True
            if any(box.intersects(frame.adjusted(2, 2, -2, -2)) for frame in frames.values()):
                return True
            if self.callout_hits_states(box):
                return True
            return False

        for box in candidates:
            if not blocked(box):
                return box
        # Last resort: clamp the preferred slot into the host and accept it only
        # if it still misses state land; otherwise shrink toward the corner.
        box = QRect(candidates[0])
        box.moveRight(min(box.right(), host.right() - pad))
        box.moveBottom(min(box.bottom(), host.bottom() - pad))
        box.moveLeft(max(box.left(), host.left() + pad))
        box.moveTop(max(box.top(), host.top() + pad))
        if not blocked(box):
            return box
        return box

    def layout_callout(self, laid: list[dict] | None = None) -> QRect | None:
        laid = laid if laid is not None else self.layout_pins()
        pin = self.primary_callout_pin(laid)
        if pin is None:
            return None
        city = str(pin.get("label") or pin.get("city") or "")
        lines = [city]
        if pin.get("sales_label"):
            lines.append(str(pin.get("sales_label")))
        if pin.get("contrib_label"):
            lines.append(str(pin.get("contrib_label")))
        from PySide6.QtGui import QFontMetrics
        key = (self._cache_tag(), str(pin.get("id") or ""))
        cached = _CALLOUT_CACHE.get(key)
        if cached is not None:
            rect, pts = cached
            box = QRect(*rect)
            pin["_callout"] = rect
            pin["_leader"] = [QPoint(p) for p in pts]
            return box
        metrics = QFontMetrics(ui_font(11, QFont.Weight.DemiBold))
        width = max(metrics.horizontalAdvance(line) for line in lines)
        box_w, box_h = width + 16, 16 * len(lines) + 10
        box = self._callout_slot(box_w, box_h, pin)
        pin["_callout"] = (box.x(), box.y(), box.width(), box.height())
        pin["_leader"] = self.leader_points(pin, box)
        _cache_put(_CALLOUT_CACHE, key, (pin["_callout"], [QPoint(p) for p in pin["_leader"]]))
        return box

    def _pin_at(self, pos: QPoint) -> dict | None:
        # Walk the laid-out badges (offsets included) so hover stays truthful.
        for pin in reversed(self.layout_pins()):
            badge = pin.get("_badge")
            if badge and QRect(badge).adjusted(-2, -2, 2, 2).contains(pos):
                return pin
            call = pin.get("_callout")
            if call and QRect(*call).contains(pos):
                return pin
        return None

    def _colors(self) -> dict:
        if self.theme == "dark":
            return {
                "bg": QColor(DASH_BG),
                "land": QColor("#163056"),
                "border": QColor("#7AA7D9"),
                "outer": QColor("#A8C8EC"),
                "glow_high": QColor(DASH_PIN_HIGH),
                "glow_mid": QColor(DASH_PIN_MID),
                "glow_low": QColor(DASH_PIN_LOW),
                "call_bg": QColor(14, 28, 58, 230),
                "call_ink": QColor(DASH_TEXT),
                "call_muted": QColor(DASH_MUTED),
                "unowned": QColor("#5B6F90"),
                "inset_bg": QColor("#0C1B38"),
                "inset_line": QColor("#7AA7D9"),
            }
        return {
            "bg": QColor("#F3F6FB"),
            "land": QColor("#E6E8EC"),
            "border": QColor("#C5CAD3"),
            "outer": QColor("#B0B6C0"),
            "glow_high": QColor("#0B3A67"),
            "glow_mid": QColor("#0B5FBD"),
            "glow_low": QColor("#5B6573"),
            "call_bg": QColor(255, 255, 255, 250),
            "call_ink": QColor("#122033"),
            "call_muted": QColor("#5B6573"),
            "unowned": QColor("#9AA3B2"),
            "inset_bg": QColor("#E8EEF6"),
            "inset_line": QColor("#8A93A3"),
        }

    def _path_for(self, abbr: str, rect: QRect, *, inset: bool = False) -> QPainterPath:
        """State outline in widget pixels; cached per (state, rect, inset).

        Same math as _project/_project_region_to_rect, with the letterbox and
        the Albers projection hoisted out of the per-vertex loop.
        """
        key = (abbr, rect.x(), rect.y(), rect.width(), rect.height(), bool(inset))
        cached = _PATH_CACHE.get(key)
        if cached is not None:
            return cached
        region = abbr if inset else "CONUS"
        if inset:
            used = _letterbox_rect(rect, region_aspect(region), margin=4, top_gutter=14)
        else:
            used = _letterbox_rect(rect, region_aspect(region))
        minx, miny, maxx, maxy = region_extent(region)
        span_x = maxx - minx
        span_y = maxy - miny
        degenerate = span_x <= 0 or span_y <= 0 or used.width() < 1 or used.height() < 1
        ux, uy, uw, uh = used.x(), used.y(), used.width(), used.height()
        centre = used.center()
        path = QPainterPath()
        for ring in _projected_rings(abbr, region):
            if not ring:
                continue
            first = True
            for x, y in ring:
                if degenerate:
                    ix, iy = centre.x(), centre.y()
                else:
                    ix = int(round(ux + (x - minx) / span_x * uw))
                    iy = int(round(uy + (maxy - y) / span_y * uh))
                if first:
                    path.moveTo(float(ix), float(iy))
                    first = False
                else:
                    path.lineTo(float(ix), float(iy))
            path.closeSubpath()
        _cache_put(_PATH_CACHE, key, path)
        return path

    def _glow_for(self, pal: dict) -> dict[str, QColor]:
        glow_for: dict[str, QColor] = {}
        for pin in self.pins:
            ident = str(pin.get("id") or "")
            abbr = state_for_city(ident) or (self.pin_region(pin) if pin.get("owned") else "")
            if abbr not in STATE_RINGS or not pin.get("owned"):
                continue
            rank = pin.get("rank") or "mid"
            glow_for[abbr] = pal[{"high": "glow_high", "low": "glow_low"}.get(rank, "glow_mid")]
        return glow_for

    def _draw_states(self, painter: QPainter, pal: dict, rect: QRect, abbrs: set[str], *, inset: bool = False) -> None:
        glow_for = self._glow_for(pal)
        for abbr in abbrs:
            path = self._path_for(abbr, rect, inset=inset)
            if path.isEmpty():
                continue
            fill = QColor(glow_for[abbr]) if abbr in glow_for and self.theme == "dark" else pal["land"]
            if self.show_places and abbr == self._place_abbr and not (abbr in glow_for and self.theme == "dark"):
                fill = QColor("#C9DDD0") if self.theme != "dark" else QColor("#1E4D38")
            if abbr in glow_for and self.theme == "dark":
                fill.setAlpha(70)
                painter.setBrush(pal["land"])
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawPath(path)
                painter.setBrush(fill)
            else:
                painter.setBrush(fill)
            painter.setPen(QPen(pal["border"], 1.15 if inset else 1.35))
            painter.drawPath(path)

    def _draw_inset(self, painter: QPainter, pal: dict, abbr: str, frame: QRect) -> None:
        painter.save()
        painter.setPen(QPen(pal["inset_line"], 1.2))
        painter.setBrush(pal["inset_bg"])
        painter.drawRoundedRect(QRectF(frame), 7, 7)
        painter.setClipRect(frame.adjusted(1, 1, -1, -1))
        self._draw_states(painter, pal, frame, {abbr}, inset=True)
        painter.setClipping(False)
        painter.setPen(pal["call_muted"])
        painter.setFont(ui_font(9, QFont.Weight.DemiBold))
        label = "Alaska" if abbr == "AK" else "Hawaii"
        painter.drawText(QRect(frame.x() + 6, frame.y() + 3, frame.width() - 10, 14), label)
        painter.restore()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        pal = self._colors()
        host = self._host_rect()
        painter.setClipRect(host)
        painter.fillRect(host, pal["bg"])
        self._draw_states(painter, pal, self.conus_rect(), set(CONTERMINOUS), inset=False)
        frames = self.inset_frames()
        self._draw_inset(painter, pal, "AK", frames["AK"])
        self._draw_inset(painter, pal, "HI", frames["HI"])
        if self.show_places:
            self._draw_places(painter, pal)

        size = self.badge_size()
        laid = self.layout_pins()
        self._callout_boxes: list[QRect] = []
        drawn_stacks: set[tuple[int, int]] = set()
        # Badges first so callouts can sit on top and steer around them.
        for pin in laid:
            point = pin["_point"]
            owned = bool(pin.get("owned"))
            count = int(pin.get("_count") or 1)
            stack_key = (point.x(), point.y())
            if count > 1 and stack_key in drawn_stacks:
                continue
            if count > 1:
                drawn_stacks.add(stack_key)
            hover = str(pin.get("id") or "") == self._hover
            if not owned:
                color = _health_color(pin.get("health")) or pal["unowned"]
                draw_store_badge(
                    painter, point, color, size=max(16, size - 2),
                    selected=False, hover=hover, count=count, unowned=True,
                )
                continue
            rank = pin.get("rank") or "mid"
            color = _health_color(pin.get("health")) or pal[{"high": "glow_high", "low": "glow_low"}.get(rank, "glow_mid")]
            draw_store_badge(
                painter, point, color, size=size,
                selected=bool(pin.get("selected")), hover=hover, count=count,
            )
        occupied = [QRect(pin["_badge"]) for pin in laid if pin.get("_badge")]
        self._callout_boxes = occupied
        box = self.layout_callout(laid)
        pin = self.primary_callout_pin(laid)
        if pin is not None and box is not None:
            self._draw_callout(painter, pin, pin["_point"], pal, box)
        painter.end()


    def _interior_point(self, abbr: str, path: QPainterPath) -> QPoint:
        box = path.boundingRect()
        key = (abbr, int(box.x()), int(box.y()), int(box.width()), int(box.height()))
        cached = self._label_points.get(key)
        if cached is not None:
            return QPoint(cached)
        cx, cy = box.center().x(), box.center().y()
        if path.contains(QPointF(cx, cy)):
            point = QPoint(int(round(cx)), int(round(cy)))
        else:
            best = None
            best_d = 1e18
            step = max(3, int(min(box.width(), box.height()) / 7) or 3)
            y = box.top() + step / 2
            while y <= box.bottom():
                x = box.left() + step / 2
                while x <= box.right():
                    if path.contains(QPointF(x, y)):
                        distance = (x - cx) ** 2 + (y - cy) ** 2
                        if distance < best_d:
                            best_d = distance
                            best = (x, y)
                    x += step
                y += step
            point = QPoint(int(round(best[0])), int(round(best[1]))) if best else QPoint(int(round(cx)), int(round(cy)))
        if len(self._label_points) > 400:
            self._label_points.clear()
        self._label_points[key] = point
        return point

    def _draw_places(self, painter: QPainter, pal: dict) -> None:
        """State letters at an interior point, and each capital on its own coordinates."""
        from open_late.us_capitals import BY_ABBR

        self._place_hits = []
        self._painted_states = []
        ink = QColor("#145C32") if self.theme != "dark" else QColor("#E8F5EC")
        dot = QColor("#0E5C32") if self.theme != "dark" else QColor("#8FDBA8")
        font_px = max(8, min(12, self.conus_rect().height() // 26))
        painter.setFont(ui_font(font_px, QFont.Weight.DemiBold))
        frames = self.inset_frames()
        jobs = [(abbr, self.conus_rect(), False) for abbr in CONTERMINOUS if abbr != "DC"]
        jobs.append(("AK", frames["AK"], True))
        jobs.append(("HI", frames["HI"], True))
        for abbr, rect, inset in jobs:
            path = self._path_for(abbr, rect, inset=inset)
            if path.isEmpty():
                continue
            self._painted_states.append((abbr, path))
            item = BY_ABBR.get(abbr)
            if item is None:
                continue
            label_at = self._interior_point(abbr, path)
            box = path.boundingRect()
            if box.width() >= 26 and box.height() >= 14:
                painter.setPen(ink)
                painter.drawText(
                    QRect(label_at.x() - 18, label_at.y() - 8, 36, 14),
                    int(Qt.AlignmentFlag.AlignCenter),
                    abbr,
                )
            point = self.project_pin({"lon": item.lon, "lat": item.lat})
            if not path.contains(QPointF(point)):
                point = self._nearest_inside(path, point)
            painter.setPen(QPen(QColor("#FFFFFF"), 1))
            painter.setBrush(dot)
            painter.drawEllipse(point, 3, 3)
            self._place_hits.append((QRect(point.x() - 8, point.y() - 8, 16, 16), item.ident))
            if box.width() >= 86:
                painter.setPen(ink)
                painter.setFont(ui_font(max(7, font_px - 1)))
                painter.drawText(
                    QRect(point.x() - 48, point.y() + 4, 96, 12),
                    int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
                    item.city,
                )
                painter.setFont(ui_font(font_px, QFont.Weight.DemiBold))

    def _nearest_inside(self, path: QPainterPath, point: QPoint) -> QPoint:
        """A capital on a coast thinner than one pixel lands on the nearest land pixel."""
        best = None
        best_d = 10**9
        for radius in (4, 12, 24):
            for dy in range(-radius, radius + 1, 1):
                for dx in range(-radius, radius + 1, 1):
                    if dx * dx + dy * dy > radius * radius:
                        continue
                    if path.contains(QPointF(point.x() + dx, point.y() + dy)):
                        distance = dx * dx + dy * dy
                        if distance < best_d:
                            best_d = distance
                            best = QPoint(point.x() + dx, point.y() + dy)
            if best is not None:
                return best
        return point

    def _place_at(self, pos: QPoint) -> str:
        if not self.show_places:
            return ""
        from open_late.us_capitals import by_abbr

        for rect, ident in self._place_hits:
            if rect.contains(pos):
                return ident
        point = QPointF(pos)
        for abbr, path in self._painted_states:
            if path.contains(point):
                item = by_abbr(abbr)
                return item.ident if item is not None else ""
        return ""

    def pin_state_abbr(self, pin: dict) -> str:
        ident = str(pin.get("id") or "")
        return state_for_city(ident) or (self.pin_region(pin) if pin.get("owned") else "") or ""

    def _leader_ends(self, pin: dict, box: QRect) -> tuple[QPoint, QPoint]:
        point = pin.get("_point") or self.project_pin(pin)
        badge = pin.get("_badge") or store_badge_rect(point, self.badge_size())
        # Leave the badge toward the callout, and land on the nearest callout edge.
        tx = min(max(point.x(), box.left()), box.right())
        ty = min(max(point.y(), box.top()), box.bottom())
        dest = QPoint(tx, ty)
        bx = min(max(dest.x(), badge.left()), badge.right())
        by = min(max(dest.y(), badge.top()), badge.bottom())
        start = QPoint(bx, by)
        return start, dest

    def _land_mask(self, pin_abbr: str, pin: dict | None = None) -> tuple[QImage, QRect, int]:
        """Grayscale map: 0 water/gutter, 1 foreign land, 2 the pin's own state."""
        host = self._host_rect()
        cell = 1
        key = (self._cache_tag(), pin_abbr or "", str((pin or {}).get("id") or ""))
        cached = self._land_mask_cache.get(key)
        if cached is not None:
            return cached, host, cell
        img = QImage(max(1, host.width()), max(1, host.height()), QImage.Format_Grayscale8)
        img.fill(0)
        painter = QPainter(img)
        painter.translate(-host.x(), -host.y())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setBrush(QColor(1, 1, 1))
        conus = self.conus_rect()
        for abbr in CONTERMINOUS:
            path = self._path_for(abbr, conus, inset=False)
            if not path.isEmpty():
                painter.drawPath(path)
        frames = self.inset_frames()
        for abbr, frame in frames.items():
            path = self._path_for(abbr, frame, inset=True)
            if not path.isEmpty():
                painter.drawPath(path)
        if pin_abbr:
            painter.setBrush(QColor(2, 2, 2))
            if pin_abbr in CONTERMINOUS:
                path = self._path_for(pin_abbr, conus, inset=False)
                if not path.isEmpty():
                    painter.drawPath(path)
            elif pin_abbr in frames:
                path = self._path_for(pin_abbr, frames[pin_abbr], inset=True)
                if not path.isEmpty():
                    painter.drawPath(path)
            # A 1px fringe so thin raster necks (Lake Michigan, a river border) stay connected.
            painter.setPen(QPen(QColor(2, 2, 2), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            if pin_abbr in CONTERMINOUS:
                path = self._path_for(pin_abbr, conus, inset=False)
                if not path.isEmpty():
                    painter.drawPath(path)
            elif pin_abbr in frames:
                path = self._path_for(pin_abbr, frames[pin_abbr], inset=True)
                if not path.isEmpty():
                    painter.drawPath(path)
        if pin is not None:
            geo = pin.get("_point") or self.project_pin(pin)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(2, 2, 2))
            painter.drawEllipse(geo if isinstance(geo, QPoint) else QPoint(geo), 2, 2)
        painter.end()
        self._dilate_water(img, radius=2)
        # Masks are a full-size image each; keep only a few (resizes add new keys).
        _cache_put(self._land_mask_cache, key, img, limit=8)
        return img, host, cell

    def _dilate_water(self, img: QImage, radius: int = 2) -> None:
        """Grow water/gutter by a few pixels so thin lake and coastal rifts stay connected."""
        if radius <= 0 or img.width() < 2 or img.height() < 2:
            return
        w, h = img.width(), img.height()
        bpl = img.bytesPerLine()
        size = bpl * h
        src = bytes(img.constBits())[:size]
        r2 = radius * radius
        # One flag byte per pixel, packed into Python ints so each disc offset is
        # a single shift/or instead of a per-pixel loop. Same rule as before:
        # water (0) clears foreign land (1) within the disc, never own state (2).
        def row_mask(lo: int, hi: int) -> int:
            lo, hi = max(0, lo), min(w - 1, hi)
            if hi < lo:
                return 0
            row = b"\x00" * lo + b"\x01" * (hi - lo + 1) + b"\x00" * (bpl - hi - 1)
            return int.from_bytes(row * h, "little")
        water = int.from_bytes(src.translate(_ZERO_FLAG), "little") & row_mask(0, w - 1)
        foreign = int.from_bytes(src.translate(_ONE_FLAG), "little")
        full = (1 << (size * 8)) - 1
        col_masks: dict[int, int] = {}
        reach = 0
        for oy in range(-radius, radius + 1):
            for ox in range(-radius, radius + 1):
                if ox * ox + oy * oy > r2:
                    continue
                shift = (oy * bpl + ox) * 8
                moved = water << shift if shift >= 0 else water >> -shift
                if ox not in col_masks:
                    col_masks[ox] = row_mask(ox, w - 1 + ox)
                reach |= moved & col_masks[ox]
        hit = reach & full & foreign
        dst = (int.from_bytes(src, "little") & ~(hit * 0xFF)).to_bytes(size, "little")
        out = QImage(dst, w, h, bpl, QImage.Format_Grayscale8)
        painter = QPainter(img)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.drawImage(0, 0, out)
        painter.end()

    def _mask_data(self, img: QImage) -> tuple[bytes, int]:
        key = img.cacheKey()
        data = self._mask_bytes.get(key)
        if data is None:
            bpl = img.bytesPerLine()
            data = (bytes(img.constBits())[: bpl * img.height()], bpl)
            self._mask_bytes = {key: data}
        return data

    def _walkable_at(self, img: QImage, host: QRect, x: int, y: int, badge: QRect | None = None) -> bool:
        if badge is not None and badge.adjusted(-1, -1, 1, 1).contains(x, y):
            return True
        if not host.contains(x, y):
            return False
        lx, ly = x - host.x(), y - host.y()
        if lx >= img.width() or ly >= img.height():
            px = img.pixel(lx, ly) & 0xFF
            return px != 1
        data, bpl = self._mask_data(img)
        return data[ly * bpl + lx] != 1

    def _segment_walkable(self, img: QImage, host: QRect, a: QPoint, b: QPoint, badge: QRect | None = None) -> bool:
        dx = b.x() - a.x()
        dy = b.y() - a.y()
        steps = max(abs(dx), abs(dy), 1)
        for i in range(steps + 1):
            x = a.x() + int(round(dx * i / steps))
            y = a.y() + int(round(dy * i / steps))
            if not self._walkable_at(img, host, x, y, badge):
                return False
        return True

    def leader_points(self, pin: dict, box: QRect) -> list[QPoint]:
        """Polyline from the pin badge to the callout that stays off foreign land."""
        start, dest = self._leader_ends(pin, box)
        abbr = self.pin_state_abbr(pin)
        badge = pin.get("_badge") or store_badge_rect(pin.get("_point") or start, self.badge_size())
        cache_key = (
            start.x(), start.y(), dest.x(), dest.y(),
            box.x(), box.y(), box.width(), box.height(),
            abbr,
            self._host_rect().width(), self._host_rect().height(),
            self._cache_tag(), str(pin.get("id") or ""),
        )
        cached = self._leader_cache.get(cache_key)
        if cached is not None:
            return [QPoint(p) for p in cached]
        img, host, _cell = self._land_mask(abbr, pin)
        if self._segment_walkable(img, host, start, dest, badge):
            pts = [QPoint(start), QPoint(dest)]
            _cache_put(self._leader_cache, cache_key, pts)
            return [QPoint(p) for p in pts]
        origin = pin.get("_point") or pin.get("_raw") or self.project_pin(pin)
        raw = self._route_leader(img, host, start, dest, badge, origin=QPoint(origin))
        if len(raw) < 2:
            raw = self._gutter_elbow(host, start, dest, img, badge)
            if self.leader_hits_foreign_states(raw, pin):
                raw = []
        if len(raw) < 2:
            pts = [QPoint(start), QPoint(dest)]
            _cache_put(self._leader_cache, cache_key, pts)
            return [QPoint(p) for p in pts]
        pts = self._simplify_leader(img, host, raw, badge)
        _cache_put(self._leader_cache, cache_key, pts)
        return [QPoint(p) for p in pts]

    def _route_leader(self, img: QImage, host: QRect, start: QPoint, dest: QPoint, badge: QRect, origin: QPoint | None = None) -> list[QPoint]:
        origin = origin or start
        for step in (2, 1):
            pts = self._route_leader_step(img, host, origin, dest, badge, step)
            if pts:
                out = [QPoint(start)]
                if origin != start:
                    out.append(QPoint(origin))
                out.extend(pts[1:] if pts[0] == origin or (origin != start and pts[0] == start) else pts)
                if out[-1] != dest:
                    out.append(QPoint(dest))
                # Drop consecutive duplicates.
                clean: list[QPoint] = []
                for pt in out:
                    if not clean or pt != clean[-1]:
                        clean.append(pt)
                return clean
        return []

    def _route_leader_step(self, img: QImage, host: QRect, start: QPoint, dest: QPoint, badge: QRect, step: int) -> list[QPoint]:
        def cell(pt: QPoint) -> tuple[int, int]:
            return (int(round((pt.x() - host.x()) / step)), int(round((pt.y() - host.y()) / step)))
        def point(c: tuple[int, int]) -> QPoint:
            return QPoint(host.x() + c[0] * step, host.y() + c[1] * step)
        sc, dc = cell(start), cell(dest)
        cols = max(1, (host.width() + step - 1) // step + 1)
        rows = max(1, (host.height() + step - 1) // step + 1)
        if not (0 <= sc[0] < cols and 0 <= sc[1] < rows and 0 <= dc[0] < cols and 0 <= dc[1] < rows):
            return []
        walk = [[False] * rows for _ in range(cols)]
        data, bpl = self._mask_data(img)
        hx, hy = host.x(), host.y()
        hr, hb = host.right(), host.bottom()
        iw, ih = img.width(), img.height()
        near = badge.adjusted(-1, -1, 1, 1) if badge is not None else None
        bl, bt, br, bb = (near.left(), near.top(), near.right(), near.bottom()) if near is not None else (1, 1, 0, 0)
        for cx in range(cols):
            x = hx + cx * step
            column = walk[cx]
            x_in = hx <= x <= hr
            for cy in range(rows):
                y = hy + cy * step
                if bl <= x <= br and bt <= y <= bb:
                    column[cy] = True
                elif not (x_in and hy <= y <= hb):
                    column[cy] = False
                elif x - hx < iw and y - hy < ih:
                    column[cy] = data[(y - hy) * bpl + (x - hx)] != 1
                else:
                    column[cy] = self._walkable_at(img, host, x, y, badge)
        walk[sc[0]][sc[1]] = True
        walk[dc[0]][dc[1]] = True
        prev: dict[tuple[int, int], tuple[int, int] | None] = {sc: None}
        queue = deque([sc])
        found = False
        neigh = ((1, 0), (-1, 0), (0, 1), (0, -1))
        while queue:
            cur = queue.popleft()
            if cur == dc:
                found = True
                break
            for dx, dy in neigh:
                nxt = (cur[0] + dx, cur[1] + dy)
                if nxt in prev:
                    continue
                if not (0 <= nxt[0] < cols and 0 <= nxt[1] < rows):
                    continue
                if not walk[nxt[0]][nxt[1]]:
                    continue
                prev[nxt] = cur
                queue.append(nxt)
        if not found:
            return []
        cells = [dc]
        while cells[-1] != sc:
            cells.append(prev[cells[-1]])
        cells.reverse()
        return [QPoint(start)] + [point(c) for c in cells] + [QPoint(dest)]

    def _gutter_elbow(self, host: QRect, start: QPoint, dest: QPoint, img: QImage, badge: QRect) -> list[QPoint]:
        """Drop into the band under CONUS, then run horizontally to the callout."""
        bounds = self.conus_bounds_rect() if hasattr(self, "conus_bounds_rect") else self.conus_draw_rect()
        gutter_y = min(max(bounds.bottom() + max(2, INSET_GUTTER // 2), host.top() + 2), host.bottom() - 2)
        # Prefer a y in the gutter that is walkable near the pin's x, then toward dest.x.
        candidates_y = [gutter_y, bounds.bottom() + 2, dest.y(), host.bottom() - 4]
        mid_y = gutter_y
        for y in candidates_y:
            probe = QPoint(start.x(), y)
            if self._walkable_at(img, host, probe.x(), y, badge):
                mid_y = y
                break
        mid_a = QPoint(start.x(), mid_y)
        mid_b = QPoint(dest.x(), mid_y)
        return [QPoint(start), mid_a, mid_b, QPoint(dest)]

    def _simplify_leader(self, img: QImage, host: QRect, points: list[QPoint], badge: QRect) -> list[QPoint]:
        if len(points) <= 2:
            return [QPoint(p) for p in points]
        # String-pull: keep a point only when the skip would cross foreign land.
        kept = [QPoint(points[0])]
        i = 0
        while i < len(points) - 1:
            best = i + 1
            j = i + 2
            while j < len(points) and self._segment_walkable(img, host, points[i], points[j], badge):
                best = j
                j += 1
            kept.append(QPoint(points[best]))
            i = best
        # Drop near-duplicates.
        clean: list[QPoint] = []
        for pt in kept:
            if not clean or abs(pt.x() - clean[-1].x()) + abs(pt.y() - clean[-1].y()) >= 2:
                clean.append(pt)
        if len(clean) < 2:
            return [QPoint(points[0]), QPoint(points[-1])]
        return clean

    def leader_hits_foreign_states(self, points: list[QPoint], pin: dict) -> bool:
        """True if a polyline sample lands in a state other than the pin's own."""
        if len(points) < 2:
            return False
        abbr = self.pin_state_abbr(pin)
        img, host, _ = self._land_mask(abbr, pin)
        badge = pin.get("_badge")
        for a, b in zip(points, points[1:]):
            if not self._segment_walkable(img, host, a, b, badge):
                return True
        return False

    def _draw_callout(self, painter: QPainter, pin: dict, point: QPoint, pal: dict, box: QRect) -> None:
        city = str(pin.get("label") or pin.get("city") or "")
        sales = str(pin.get("sales_label") or "")
        contrib = str(pin.get("contrib_label") or "")
        lines = [city]
        if sales:
            lines.append(sales)
        if contrib:
            lines.append(contrib)
        pin["_callout"] = (box.x(), box.y(), box.width(), box.height())
        # Elbow or routed leader that stays off foreign state land.
        points = pin.get("_leader") or self.leader_points(pin, box)
        pin["_leader"] = points
        if len(points) >= 2:
            painter.setPen(QPen(pal["border"], 1.25))
            for start, end in zip(points, points[1:]):
                painter.drawLine(start, end)
        painter.setPen(QPen(pal["border"], 1))
        painter.setBrush(pal["call_bg"])
        painter.drawRoundedRect(box, 6, 6)
        painter.setPen(pal["call_ink"])
        painter.setFont(ui_font(11, QFont.Weight.DemiBold))
        painter.drawText(QRect(box.x() + 8, box.y() + 4, box.width() - 12, 14), city)
        painter.setFont(ui_font(10))
        painter.setPen(pal["call_muted"])
        y = box.y() + 18
        for line in lines[1:]:
            painter.drawText(QRect(box.x() + 8, y, box.width() - 12, 14), line)
            y += 14

    def mousePressEvent(self, event) -> None:
        pos = event.position().toPoint()
        pin = self._pin_at(pos)
        if pin is None:
            ident = self._place_at(pos)
            if not ident:
                return
            owned = any(item.get("id") == ident and item.get("owned") for item in self.pins)
            if owned:
                self.store_clicked.emit(ident)
            else:
                self.sign_requested.emit(ident)
            return
        if pin.get("owned"):
            self.store_clicked.emit(str(pin["id"]))
        else:
            self.sign_requested.emit(str(pin["id"]))

    def mouseMoveEvent(self, event) -> None:
        from open_late.us_capitals import by_abbr, by_id, place_tip

        pos = event.position().toPoint()
        pin = self._pin_at(pos)
        ident = pin["id"] if pin else ""
        place = "" if pin else self._place_at(pos)
        abbr = ""
        if place:
            found = by_id(place)
            abbr = found.abbr if found is not None else ""
        elif pin is not None:
            abbr = self.pin_state_abbr(pin)
        changed = ident != self._hover or abbr != self._place_abbr
        self._hover = ident
        self._place_abbr = abbr
        if pin:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setToolTip(str(pin.get("tip") or ""))
        elif place:
            found = by_id(place) or by_abbr(abbr)
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setToolTip(place_tip(found) if found is not None else "")
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.setToolTip("")
        if changed:
            self.update()

    def leaveEvent(self, event) -> None:
        if self._hover or self._place_abbr:
            self._hover = ""
            self._place_abbr = ""
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.setToolTip("")
            self.update()
        super().leaveEvent(event)


def _health_color(tone: str | None):
    if not tone:
        return None
    from open_late.ui.store_intel import HEALTH_COLORS

    hex_color = HEALTH_COLORS.get(str(tone))
    return QColor(hex_color) if hex_color else None
