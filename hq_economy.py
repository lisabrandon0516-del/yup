"""Corporate HQ Economy screen (E1 / E2 / E3, UI only).

Dark navy sibling of the Dashboard. All engine reads go through hq_adapter
with guarded fallbacks so a missing or future E4 surface does not crash the
page.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPalette, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from open_late.text import money, money_compact, money_compact_signed
from open_late.ui.hq_adapter import (
    city_display_name,
    economy_available,
    economy_calendar,
    economy_cities,
    economy_difficulty_of,
    economy_factors,
    economy_movers,
    economy_news,
    economy_snapshot,
    economy_sparklines,
    economy_store_impact,
    factor_band,
    factor_kind,
    factor_neutral,
    impact_filter_kwargs_supported,
    planogram_departments,
    store_ids,
)
from open_late.ui.hq_pages import Sparkline
from open_late.ui.theme import (
    DASH_ACCENT,
    DASH_BG,
    DASH_CARD,
    DASH_FAINT,
    DASH_GLOW,
    DASH_LINE,
    DASH_MUTED,
    DASH_PIN_HIGH,
    DASH_PIN_LOW,
    DASH_PIN_MID,
    DASH_TEXT,
    ui_font,
)

UP_NEON = DASH_PIN_HIGH
DOWN_NEON = DASH_PIN_LOW
BAND_COLORS = {
    "steady": "#67E8F9",
    "watch": DASH_PIN_MID,
    "alert": DASH_PIN_LOW,
}

CATEGORY_LABELS = {
    "national_macro": "National macro",
    "local_regional": "Local & regional",
    "seasonal_calendar": "Seasonal calendar",
    "weather_disasters": "Weather & disasters",
    "labor_market": "Labor market",
    "supply_chain": "Supply chain",
    "commodity_prices": "Commodity prices",
    "competition": "Competition",
    "real_estate_costs": "Real estate & costs",
    "finance": "Finance",
    "regulation_taxes": "Regulation & taxes",
    "consumer_trends": "Consumer trends",
}

LINE_LABELS = {
    "sales": "Sales",
    "cogs": "COGS",
    "labor": "Labor",
    "rent": "Rent",
    "freight": "Freight",
    "shrink": "Shrink",
    "card_fees": "Card fees",
    "pos_fees": "POS fees",
    "contribution": "Store P&L",
}

COST_LINES = {"cogs", "labor", "rent", "freight", "shrink", "card_fees", "pos_fees"}

SCOPE_LABELS = {
    "national": "National",
    "city": "City",
    "store": "Store",
    "department": "Department",
}

TABS = (
    ("factors", "Factors"),
    ("impact", "Why my P&L moved"),
    ("news", "News & calendar"),
)


def _amp(text: str) -> str:
    """Qt treats '&' as a mnemonic in labels and buttons."""
    return str(text).replace("&", "&&")


def _label(text: str, size: int = 13, weight=QFont.Weight.Normal, color: str = DASH_TEXT, name: str = "", wrap: bool = False) -> QLabel:
    lab = QLabel(_amp(text))
    lab.setFont(ui_font(size, weight))
    if name == "pageTitle":
        lab.setStyleSheet(
            "QLabel#pageTitle { background: #0E5C32; color: #FFFFFF; padding: 6px 12px; }"
        )
    else:
        lab.setStyleSheet(f"color: {color}; background: transparent;")
    lab._x_ink = color
    lab.setWordWrap(wrap)
    if wrap:
        lab.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
    if name:
        lab.setObjectName(name)
    return lab



def _ink_key(color: str) -> str:
    return str(color).lstrip("#").lower()


def _ink_colors() -> list[str]:
    return [DASH_TEXT, DASH_MUTED, DASH_FAINT, UP_NEON, DOWN_NEON, *BAND_COLORS.values()]


def _ink_css() -> str:
    """Page-sheet rules for the fixed ink set used by factor rows and movers.

    Same declarations as the old per-label sheet; the economyPage id keeps them
    ahead of any objectName rule on the page, as the per-label sheet was.
    """
    rules = []
    for color in dict.fromkeys(_ink_colors()):
        rules.append(
            f'QWidget#economyPage QLabel[ecoInk="{_ink_key(color)}"] {{ color: {color}; background: transparent; }}'
        )
    return "\n        ".join(rules)


_INK_KEYS = frozenset(_ink_key(c) for c in _ink_colors())


def _ink_label(text: str, size: int = 13, weight=QFont.Weight.Normal, color: str = DASH_TEXT, name: str = "") -> QLabel:
    """_label() for the 120-row factor board: colour via a page rule, not a per-label sheet."""
    if _ink_key(color) not in _INK_KEYS:
        return _label(text, size, weight, color, name)
    lab = QLabel(_amp(text))
    lab.setFont(ui_font(size, weight))
    lab.setProperty("ecoInk", _ink_key(color))
    lab.setWordWrap(False)
    if name:
        lab.setObjectName(name)
    lab._x_ink = color
    return lab


def _set_ink(lab: QLabel, color: str) -> None:
    """Recolor an in-place label; restyle only when the colour actually changed."""
    if getattr(lab, "_x_ink", None) == color:
        return
    lab._x_ink = color
    if lab.property("ecoInk") is not None and _ink_key(color) in _INK_KEYS:
        lab.setProperty("ecoInk", _ink_key(color))
        lab.style().unpolish(lab)
        lab.style().polish(lab)
        lab.update()
    else:
        lab.setStyleSheet(f"color: {color}; background: transparent;")


def _set_text(lab: QLabel, text: str) -> None:
    text = _amp(text)
    if lab.text() != text:
        lab.setText(text)


class _FlowRow(QWidget):
    """Wraps chip-sized children onto the next line instead of clipping."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[QWidget] = []
        self._gap = 6
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

    def add(self, widget: QWidget) -> None:
        widget.setParent(self)
        self._items.append(widget)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._layout_chips(width, apply=False)

    def sizeHint(self):
        return self.minimumSizeHint()

    def minimumSizeHint(self):
        from PySide6.QtCore import QSize
        height = self._layout_chips(max(self.width(), 160), apply=False)
        return QSize(160, height)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_chips(self.width(), apply=True)

    def _layout_chips(self, width: int, apply: bool) -> int:
        x, y, row_h = 0, 0, 0
        width = max(40, int(width))
        for widget in self._items:
            hint = widget.sizeHint()
            w, h = max(hint.width(), widget.minimumWidth()), hint.height() or 18
            if x and x + w > width:
                x = 0
                y += row_h + 4
                row_h = 0
            if apply:
                widget.setGeometry(x, y, w, h)
            x += w + self._gap
            row_h = max(row_h, h)
        return y + max(row_h, 16)

def _category_title(key: str) -> str:
    if key in CATEGORY_LABELS:
        return CATEGORY_LABELS[key]
    return str(key or "").replace("_", " ").title()


def _exact_money(value) -> str:
    try:
        return money(int(round(float(value or 0))))
    except (TypeError, ValueError):
        return money(0)


def _exact_signed_money(value) -> str:
    try:
        amount = int(round(float(value or 0)))
    except (TypeError, ValueError):
        amount = 0
    if amount > 0:
        return f"+{money(amount)}"
    if amount < 0:
        return f"−{money(abs(amount))}"
    return money(0)


def _plain_money(value) -> str:
    return money_compact(value)


def _signed_money(value) -> str:
    return money_compact_signed(value)


def _tip_money(widget, value, *, signed: bool = False) -> None:
    if widget is None:
        return
    widget.setToolTip(_exact_signed_money(value) if signed else _exact_money(value))


def movement_is_calm(neutral, movement) -> bool:
    """True when abs(movement) is under 1% of abs(neutral). No fixed dollar floor."""
    try:
        base = abs(float(neutral or 0))
        move = abs(float(movement or 0))
    except (TypeError, ValueError):
        return False
    if base <= 0:
        return False
    return move < 0.01 * base


def _severity_color(severity) -> str:
    try:
        level = int(severity or 0)
    except (TypeError, ValueError):
        level = 0
    if level >= 4:
        return "#F43F5E"
    if level >= 3:
        return "#F97316"
    if level >= 2:
        return DASH_PIN_MID
    return DASH_MUTED


def _place_text(item: dict, events: list[dict] | None = None) -> str:
    stores = list(item.get("store_ids") or [])
    if stores:
        return ", ".join(city_display_name(sid) for sid in stores[:3])
    department = item.get("department")
    if department:
        return str(department).replace("_", " ").title()
    for event in events or []:
        ids = set(item.get("factor_ids") or [])
        if event.get("factor_id") in ids or (item.get("id") and event.get("id") == item.get("id")):
            if event.get("city_id"):
                return city_display_name(event["city_id"])
            if event.get("department"):
                return str(event["department"]).replace("_", " ").title()
            if event.get("store_ids"):
                return city_display_name(event["store_ids"][0])
    return "National"


def _door_label(state, store_id: str) -> str:
    door = next((item for item in getattr(state, "doors", []) or [] if item.id == store_id), None)
    if door is None:
        return city_display_name(store_id)
    city = getattr(door, "city", "") or city_display_name(store_id)
    state_name = getattr(door, "state_name", "") or ""
    return f"{city}, {state_name}".strip(" ,") if state_name else str(city)


def _contrib_effect(line: str, dollars: int) -> int:
    """Map a P&L-line dollar delta onto contribution."""
    if line in COST_LINES:
        return -int(dollars)
    return int(dollars)


def _neutral_center(low, high) -> float:
    try:
        lo, hi = float(low), float(high)
    except (TypeError, ValueError):
        return 100.0
    if lo <= 100 <= hi:
        return 100.0
    if lo <= 0 <= hi:
        return 0.0
    return (lo + hi) / 2.0


class DeviationBar(QWidget):
    """Horizontal bar of a factor's current value against its neutral index."""

    def __init__(self, value: float, low: float = 70, high: float = 140, color: str | None = None, parent=None, *, neutral=None):
        super().__init__(parent)
        self.set_values(value, low, high, color=color, neutral=neutral)
        self.setFixedHeight(16)
        self.setMinimumWidth(88)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setObjectName("deviationBar")

    def set_values(self, value: float, low: float = 70, high: float = 140, color: str | None = None, *, neutral=None) -> bool:
        """Set the bar's numbers; True when anything visible changed."""
        before = (getattr(self, "value", None), getattr(self, "low", None), getattr(self, "high", None),
                  getattr(self, "neutral", None), getattr(self, "tint", None))
        self.value = float(value)
        self.low = float(low)
        self.high = float(high) if float(high) > float(low) else float(low) + 1
        try:
            self.neutral = float(neutral) if neutral is not None else _neutral_center(self.low, self.high)
        except (TypeError, ValueError):
            self.neutral = _neutral_center(self.low, self.high)
        self.tint = color
        return before != (self.value, self.low, self.high, self.neutral, self.tint)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width, height = max(self.width(), 2), max(self.height(), 2)
        track = QRectF(1, height / 2 - 3, width - 2, 6)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#E4E7EC"))
        painter.drawRoundedRect(track, 3, 3)
        center = self.neutral
        span = self.high - self.low or 1.0
        def x_of(val: float) -> float:
            t = (val - self.low) / span
            return track.left() + track.width() * max(0.0, min(1.0, t))
        mid = x_of(center)
        end = x_of(self.value)
        color = QColor(self.tint or (UP_NEON if self.value >= center else DOWN_NEON))
        left = min(mid, end)
        right = max(mid, end)
        if right - left < 2:
            right = left + 2
        bar = QRectF(left, track.top(), right - left, track.height())
        painter.setBrush(color)
        painter.drawRoundedRect(bar, 3, 3)
        painter.setPen(QPen(QColor("#0E5C32"), 1.4))
        painter.drawLine(int(mid), int(track.top() - 3), int(mid), int(track.bottom() + 3))
        painter.end()


class WaterfallChart(QWidget):
    """Vertical waterfall from neutral P&L through reason steps to actual P&L."""

    def __init__(self, steps: list[dict], parent=None, *, calm: bool = False):
        super().__init__(parent)
        self.steps = steps
        self.calm = bool(calm)
        self.setObjectName("waterfallChart")
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def layout_bars(self, width: int | None = None, height: int | None = None) -> list[dict]:
        """Pixel rects for each bar. Used by paint and by tests; dollars stay on `display`."""
        width = int(self.width() if width is None else width)
        height = int(self.height() if height is None else height)
        left, right, top, bottom = 16, 16, 22, 36
        chart_w = max(40, width - left - right)
        chart_h = max(40, height - top - bottom)
        count = max(1, len(self.steps))
        gap = 14
        bar_w = max(18, (chart_w - gap * max(0, count - 1)) / count)
        rows: list[dict] = []
        if not self.steps:
            return rows
        if self.calm:
            effects = []
            for step in self.steps:
                level = float(step.get("level") or 0)
                prior = float(step.get("prior") or 0) if "prior" in step else 0.0
                effects.append(abs(level - prior) if step.get("kind") != "total" else 0.0)
            max_effect = max(effects) if any(effects) else 1.0
            # Totals are capped at 78% of the plot; reason bars use the lower 48% scaled to the largest reason.
            cap_top = top + chart_h * 0.08
            cap_bot = top + chart_h * 0.86
            detail_bot = top + chart_h * 0.86
            detail_span = chart_h * 0.48
            baseline = detail_bot
            for index, step in enumerate(self.steps):
                level = float(step.get("level") or 0)
                prior = float(step.get("prior") or 0) if "prior" in step else 0.0
                kind = step.get("kind") or "step"
                x = left + index * (bar_w + gap)
                if kind == "total":
                    y, h = cap_top, cap_bot - cap_top
                    capped = True
                else:
                    frac = abs(level - prior) / max_effect if max_effect else 0.0
                    h = max(16.0, detail_span * frac) if abs(level - prior) > 0 else 3.0
                    y = baseline - h
                    capped = False
                rows.append({
                    "index": index,
                    "name": str(step.get("name") or ""),
                    "kind": kind,
                    "x": x,
                    "y": y,
                    "w": bar_w,
                    "h": h,
                    "level": level,
                    "prior": prior,
                    "display": str(step.get("display") or ""),
                    "capped": capped,
                    "up": level >= prior,
                })
            return rows

        values = []
        for step in self.steps:
            values.append(float(step.get("level") or 0))
            if "prior" in step:
                values.append(float(step.get("prior") or 0))
        lo, hi = min(values), max(values)
        if lo > 0:
            lo = 0.0
        if hi < 0:
            hi = 0.0
        pad = max(8.0, (hi - lo) * 0.08) if hi != lo else 8.0
        lo, hi = lo - pad, hi + pad
        span = hi - lo or 1.0
        for index, step in enumerate(self.steps):
            level = float(step.get("level") or 0)
            prior = float(step.get("prior") or 0) if "prior" in step else 0.0
            kind = step.get("kind") or "step"
            x = left + index * (bar_w + gap)
            y_level = top + chart_h * (1 - (level - lo) / span)
            y_prior = top + chart_h * (1 - (prior - lo) / span)
            y_top, y_bot = min(y_level, y_prior), max(y_level, y_prior)
            if y_bot - y_top < 3:
                y_bot = y_top + 3
            rows.append({
                "index": index,
                "name": str(step.get("name") or ""),
                "kind": kind,
                "x": x,
                "y": y_top,
                "w": bar_w,
                "h": y_bot - y_top,
                "level": level,
                "prior": prior,
                "display": str(step.get("display") or ""),
                "capped": False,
                "up": level >= prior,
            })
        return rows

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        width, height = self.width(), self.height()
        painter.fillRect(0, 0, width, height, QColor(DASH_CARD))
        if not self.steps:
            painter.setPen(QColor(DASH_MUTED))
            painter.setFont(ui_font(13))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No attribution yet.")
            painter.end()
            return
        bars = self.layout_bars(width, height)
        if self.calm:
            painter.setPen(QColor(DASH_FAINT))
            painter.setFont(ui_font(9))
            painter.drawText(QRectF(16, 4, width - 32, 14), Qt.AlignmentFlag.AlignLeft, "Capped totals  ·  reason bars at a relative scale")
        for index, bar in enumerate(bars):
            x, y, bar_w, h = bar["x"], bar["y"], bar["w"], bar["h"]
            kind = bar["kind"]
            if kind == "total":
                color = QColor(DASH_GLOW)
            elif bar["up"]:
                color = QColor(UP_NEON)
            else:
                color = QColor(DOWN_NEON)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF(x, y, bar_w, h), 3, 3)
            if bar.get("capped"):
                # Broken-axis ticks on the capped totals so the scale is obviously not 1:1.
                painter.setPen(QPen(QColor("#F4F7FF"), 1.4))
                cap_y = y + 8
                painter.drawLine(int(x + 4), int(cap_y - 3), int(x + 10), int(cap_y + 3))
                painter.drawLine(int(x + 8), int(cap_y - 3), int(x + 14), int(cap_y + 3))
                painter.drawLine(int(x + bar_w - 14), int(cap_y - 3), int(x + bar_w - 8), int(cap_y + 3))
                painter.drawLine(int(x + bar_w - 10), int(cap_y - 3), int(x + bar_w - 4), int(cap_y + 3))
            if index > 0 and not self.calm:
                prev = bars[index - 1]
                painter.setPen(QPen(QColor(DASH_FAINT), 1, Qt.PenStyle.DotLine))
                painter.drawLine(int(prev["x"] + prev["w"]), int(prev["y"] if prev["up"] else prev["y"] + prev["h"]),
                                 int(x), int(y if bar["up"] else y + h))
            amount = bar["display"] or _signed_money(int(bar["level"]))
            painter.setFont(ui_font(9, QFont.Weight.DemiBold))
            if kind == "total" and h >= 28:
                painter.setPen(QColor("#F4F7FF"))
                painter.drawText(QRectF(x, y + h / 2 - 8, bar_w, 16), Qt.AlignmentFlag.AlignCenter, amount)
            else:
                painter.setPen(QColor(DASH_TEXT if kind == "total" else color))
                label_y = int(y) - 15 if y >= 18 else int(y + h) + 1
                tw = painter.fontMetrics().horizontalAdvance(amount) + 4
                tx = x + (bar_w - tw) / 2
                tx = max(2.0, min(width - tw - 2.0, tx))
                painter.drawText(QRectF(tx, label_y, tw, 14), Qt.AlignmentFlag.AlignHCenter, amount)
            painter.setPen(QColor(DASH_MUTED))
            painter.setFont(ui_font(9))
            elided = painter.fontMetrics().elidedText(bar["name"], Qt.TextElideMode.ElideRight, int(bar_w + 12))
            painter.drawText(
                QRectF(x - 6, height - 34, bar_w + 12, 28),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                elided,
            )
        painter.end()



class PnlTrend(QWidget):
    """Optional E4 store vs chain sales and contribution sparklines."""

    def __init__(self, weeks: list, series: dict, parent=None):
        super().__init__(parent)
        self.weeks = list(weeks or [])
        self.series = series or {}
        self.setObjectName("pnlTrend")
        # Keep the trend compact so the waterfall (and its labels) stay on screen at 1100x700.
        self.setMinimumHeight(96)
        self.setFixedHeight(96)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, _event) -> None:
        from PySide6.QtGui import QPainterPath

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        width, height = self.width(), self.height()
        painter.fillRect(0, 0, width, height, QColor(DASH_CARD))
        rows = [
            ("Sales", "sales", "chain:sales", QColor("#22C55E")),
            ("Store P&L", "contribution", "chain:contribution", QColor(DASH_ACCENT)),
        ]
        top, gutter, label_w = 6, 8, 64
        row_h = max(40, (height - top - 8 - gutter) // 2)
        for index, (title, key, chain_key, color) in enumerate(rows):
            y = top + index * (row_h + gutter)
            painter.setPen(QColor(DASH_FAINT))
            painter.setFont(ui_font(9, QFont.Weight.DemiBold))
            painter.drawText(QRectF(8, y, label_w - 6, 14), Qt.AlignmentFlag.AlignLeft, title.upper())
            plot = QRectF(label_w, y + 2, max(40, width - label_w - 10), row_h - 6)
            store = list(self.series.get(key) or [])
            chain = list(self.series.get(chain_key) or [])
            if len(store) == 1:
                store = store + store
            if len(chain) == 1:
                chain = chain + chain
            vals = [v for v in store + chain if v is not None]
            if len(store) < 2 and len(chain) < 2:
                painter.setPen(QColor(DASH_MUTED))
                painter.setFont(ui_font(10))
                painter.drawText(plot, Qt.AlignmentFlag.AlignCenter, "Trend starts after a Sunday close.")
                continue
            lo = min(vals + [0.0])
            hi = max(vals + [0.0])
            if hi == lo:
                lo, hi = lo - 1, hi + 1
            pad = (hi - lo) * 0.12
            lo, hi = lo - pad, hi + pad
            span = hi - lo or 1.0

            def _path(values, pen, fill=None):
                if len(values) < 2:
                    return
                path = QPainterPath()
                for i, value in enumerate(values):
                    x = plot.left() + plot.width() * (i / max(1, len(values) - 1))
                    yy = plot.bottom() - plot.height() * ((value - lo) / span)
                    if i == 0:
                        path.moveTo(x, yy)
                    else:
                        path.lineTo(x, yy)
                if fill is not None:
                    area = QPainterPath(path)
                    area.lineTo(plot.right(), plot.bottom())
                    area.lineTo(plot.left(), plot.bottom())
                    area.closeSubpath()
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(fill)
                    painter.drawPath(area)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(pen)
                painter.drawPath(path)

            if chain:
                muted = QColor(color)
                muted.setAlpha(90)
                _path(chain, QPen(muted, 1.2, Qt.PenStyle.DashLine))
            fill = QColor(color)
            fill.setAlpha(50)
            _path(store or chain, QPen(color, 1.8), fill)
            series = store or chain
            last = series[-1]
            painter.setPen(QColor(DASH_TEXT))
            painter.setFont(ui_font(9, QFont.Weight.DemiBold))
            painter.drawText(
                QRectF(plot.right() - 92, plot.top(), 90, 14),
                Qt.AlignmentFlag.AlignRight,
                _plain_money(int(round(last))),
            )
        painter.end()


class EconomyPage(QWidget):
    """Rail page: factor grid, P&L waterfall, news feed, and calendar."""

    tab_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("economyPage")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(True)
        pal = self.palette()
        pal.setColor(self.backgroundRole(), QColor(DASH_BG))
        pal.setColor(QPalette.ColorRole.Window, QColor(DASH_BG))
        pal.setColor(QPalette.ColorRole.Base, QColor(DASH_BG))
        self.setPalette(pal)
        self.setStyleSheet(self._css())
        self.host = None
        self._tab = "factors"
        self._city_id = None
        self._scope = None
        self._store_id = None
        self._impact_department = None
        self._impact_category = None
        self._impact_events_only = False
        self._expanded: dict[str, bool] = {}
        # Factor board kept between opens; refreshed in place when its shape matches.
        self._factor_cache: dict | None = None
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(20, 10, 20, 12)
        self.box.setSpacing(8)

    def _css(self) -> str:
        return f"""
        QWidget#economyPage {{
            background: {DASH_BG};
            background-color: {DASH_BG};
            color: {DASH_TEXT};
        }}
        QLabel#pageTitle {{ color: #FFFFFF; background: #0E5C32; padding: 6px 12px; }}
        QLabel#pageDeck {{ color: {DASH_MUTED}; background: transparent; }}
        QFrame#ecoCard, QFrame#todayCard, QFrame#factorRow, QFrame#newsCard, QFrame#eventCard, QFrame#weekCard, QFrame#categorySection {{
            background: {DASH_CARD};
            border: 1px solid {DASH_LINE};
            border-radius: 4px;
        }}
        QFrame#factorRow {{ border-radius: 4px; }}
        QPushButton#economyTab {{
            background: #102343;
            color: {DASH_TEXT};
            border: 1px solid {DASH_LINE};
            border-radius: 4px;
            padding: 7px 16px;
        }}
        QPushButton#economyTabOn {{
            background: #0E5C32;
            color: #FFFFFF;
            border: none;
            border-radius: 4px;
            padding: 7px 16px;
        }}
        QPushButton#eventsOnlyBtn, QPushButton#eventsOnlyBtnOn {{
            background: #102343;
            color: {DASH_TEXT};
            border: 1px solid {DASH_LINE};
            border-radius: 4px;
            padding: 5px 12px;
        }}
        QPushButton#eventsOnlyBtnOn {{
            background: #0E5C32;
            color: #FFFFFF;
            border: none;
        }}
        QComboBox#deptFilter, QComboBox#categoryFilter {{
            background: #0B1730;
            color: {DASH_TEXT};
            border: 1px solid {DASH_LINE};
            border-radius: 12px;
            padding: 4px 10px;
            min-height: 26px;
        }}
        QFrame#pnlTrend {{
            background: {DASH_CARD};
            border: 1px solid {DASH_LINE};
            border-radius: 4px;
        }}
        QFrame#moversStrip, QFrame#moverCell {{
            background: {DASH_CARD};
            border: 1px solid {DASH_LINE};
            border-radius: 4px;
        }}
        QLabel#calmNote {{
            color: {DASH_TEXT};
            background: transparent;
        }}
        QFrame#stateChip {{
            background: #E7F6EE;
            border: 1px solid {DASH_LINE};
            border-radius: 11px;
            padding: 0px;
        }}
        QLabel#stateChipLabel {{
            color: {DASH_TEXT};
            background: transparent;
            padding: 4px 10px;
        }}
        QPushButton#categoryHeader {{
            background: transparent;
            color: {DASH_TEXT};
            border: none;
            text-align: left;
            padding: 6px 4px;
        }}
        QComboBox#cityFilter, QComboBox#scopeFilter, QComboBox#storePick, QComboBox#deptFilter, QComboBox#categoryFilter {{
            background: #0B1730;
            color: {DASH_TEXT};
            border: 1px solid {DASH_LINE};
            border-radius: 12px;
            padding: 4px 10px;
            min-height: 26px;
        }}
        QComboBox#cityFilter::drop-down, QComboBox#scopeFilter::drop-down, QComboBox#storePick::drop-down, QComboBox#deptFilter::drop-down, QComboBox#categoryFilter::drop-down {{
            border: none;
            width: 20px;
        }}
        QComboBox QAbstractItemView {{
            background: {DASH_CARD};
            color: {DASH_TEXT};
            selection-background-color: #17376D;
        }}
        QScrollArea#factorScroll, QScrollArea#impactScroll, QScrollArea#newsScroll, QScrollArea#calendarScroll {{
            background: transparent;
            border: none;
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 8px;
            margin: 2px;
        }}
        QScrollBar::handle:vertical {{
            background: #294571;
            border-radius: 4px;
            min-height: 24px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        {_ink_css()}
        """

    def _clear(self) -> None:
        self._factor_cache = None
        while self.box.count():
            item = self.box.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
            elif item.layout() is not None:
                self._clear_layout(item.layout())

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
            elif item.layout() is not None:
                self._clear_layout(item.layout())

    def _state(self):
        host = self.host
        return getattr(host, "state", None) if host is not None else None

    def _set_tab(self, tab: str) -> None:
        if tab == self._tab:
            return
        self._tab = tab
        self.rebuild()
        self.tab_changed.emit(tab)

    def _set_city(self, city_id) -> None:
        self._city_id = city_id or None
        self.rebuild()

    def _set_scope(self, scope) -> None:
        self._scope = scope or None
        self.rebuild()

    def _set_store(self, store_id: str) -> None:
        self._store_id = store_id or None
        self.rebuild()

    def _set_impact_department(self, department) -> None:
        self._impact_department = department or None
        self.rebuild()

    def _set_impact_category(self, category) -> None:
        self._impact_category = category or None
        self.rebuild()

    def _toggle_events_only(self) -> None:
        self._impact_events_only = not self._impact_events_only
        self.rebuild()

    def _toggle_category(self, key: str) -> None:
        self._expanded[key] = not self._expanded.get(key, True)
        self.rebuild()

    def rebuild(self) -> None:
        state = self._state()
        if self._refresh_factors_in_place(state):
            return
        self._clear()
        self.box.addLayout(self._title_row(state))
        self.box.addLayout(self._tab_bar())

        if state is None or not economy_available():
            empty = self._empty_card(
                "The economy desk is not on this build.",
                "The page lights up when the engine exposes E1–E3. Nothing is written back.",
                "economyEmpty",
            )
            self.box.addWidget(empty, stretch=1)
            return

        self.box.addWidget(self._today_card(state))
        if self._tab == "factors":
            self.box.addWidget(self._factors_panel(state), stretch=1)
        elif self._tab == "impact":
            self.box.addWidget(self._impact_panel(state), stretch=1)
        else:
            self.box.addWidget(self._news_calendar_panel(state), stretch=1)

    def _factor_rows_for(self, state) -> list[dict]:
        rows = economy_factors(state, city_id=self._city_id)
        if self._scope:
            rows = [row for row in rows if row.get("scope") == self._scope]
        return rows

    @staticmethod
    def _factor_groups(rows: list[dict]) -> list[tuple[str, list[dict]]]:
        groups: list[tuple[str, list[dict]]] = []
        for row in rows:
            key = str(row.get("category") or "other")
            if not groups or groups[-1][0] != key:
                groups.append((key, [row]))
            else:
                groups[-1][1].append(row)
        return groups

    def _factor_shape(self, groups) -> tuple:
        """Everything that decides the board's widget tree (not its values)."""
        return (
            self._city_id,
            self._scope,
            tuple(
                (
                    key,
                    len(items),
                    self._expanded.get(key, True),
                    tuple((str(item.get("id")), factor_kind(item)) for item in items),
                )
                for key, items in groups
            ),
        )

    def _factor_sparks(self, state, rows: list[dict]) -> dict:
        ids = [int(row["id"]) for row in rows if row.get("id") is not None]
        store_id = None
        if self._city_id:
            # Prefer a door in the selected city so city-scoped sparks use local history.
            for sid in store_ids(state):
                door = next((item for item in getattr(state, "doors", []) or [] if item.id == sid), None)
                city = getattr(door, "city_id", None) or getattr(door, "city", "") or sid
                if str(city).lower().replace(" ", "_") == str(self._city_id).lower():
                    store_id = sid
                    break
        return economy_sparklines(state, ids, weeks=12, store_id=store_id).get("series") or {}

    def _refresh_factors_in_place(self, state) -> bool:
        """Reopen of the Factors tab: update the existing 120 rows, keep the tree."""
        cache = self._factor_cache
        if cache is None or self._tab != "factors" or state is None or not economy_available():
            return False
        if self.box.count() != 4 or self.box.itemAt(3).widget() is not cache["scroll"]:
            return False
        rows = self._factor_rows_for(state)
        if not rows:
            return False
        groups = self._factor_groups(rows)
        if self._factor_shape(groups) != cache["shape"]:
            return False
        sparks = self._factor_sparks(state, rows)
        # Header and tabs are a handful of widgets; rebuild them in front of the board.
        for _ in range(3):
            item = self.box.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
            elif item.layout() is not None:
                self._clear_layout(item.layout())
        self.box.insertLayout(0, self._title_row(state))
        self.box.insertLayout(1, self._tab_bar())
        self.box.insertWidget(2, self._today_card(state))
        layout = cache["layout"]
        old = cache["movers"]
        index = layout.indexOf(old)
        movers = self._movers_strip(state, rows)
        layout.insertWidget(index, movers)
        layout.removeWidget(old)
        old.hide()
        old.setParent(None)
        old.deleteLater()
        cache["movers"] = movers
        flat = [item for _key, items in groups for item in items if self._expanded.get(_key, True)]
        for frame, item in zip(cache["rows"], flat):
            self._fill_factor_row(frame, item, sparks.get(str(item.get("id")), []))
        bar = cache["scroll"].verticalScrollBar()
        if bar is not None:
            bar.setValue(bar.minimum())
        return True

    def _focus_store(self, state) -> tuple[str, str]:
        doors = list(getattr(state, "doors", None) or [])
        if self._store_id:
            door = next((item for item in doors if item.id == self._store_id), None)
            if door is not None:
                return door.id, str(getattr(door, "city", "") or door.id)
        if doors:
            door = doors[0]
            return door.id, str(getattr(door, "city", "") or door.id)
        from open_late.hq import HOME_STORE_ID
        return HOME_STORE_ID, "this store"

    def _today_facts(self, state) -> tuple[str, list[tuple[str, str]]]:
        from open_late.departments import DEPARTMENT_IDS, DEPARTMENT_LABELS
        from open_late.economy import (
            cost_mult,
            demand_mult,
            economy_difficulty,
            freight_mult,
            lead_slip_days,
            visits_mult,
            weather_visits_mult,
        )

        if economy_difficulty(state) == "off":
            return (
                "The economy is off. People, costs, freight, and trucks all sit on a neutral 100.",
                [
                    ("Visits", "A day that would draw 1,000 people still draws 1,000."),
                    ("Mix", "No department is being pushed or pulled."),
                    ("Merchandise", "A $100 case still costs $100."),
                    ("Freight", "A $1,000 truck bill is still $1,000."),
                    ("Trucks", "Deliveries arrive on the lead time you ordered."),
                ],
            )
        store_id, place = self._focus_store(state)
        visits = float(visits_mult(state, store_id) or 1.0)
        weather = float(weather_visits_mult(state, store_id) or 1.0)
        people = max(0, int(round(1000 * visits)))
        mixes = []
        costs = []
        for dept in DEPARTMENT_IDS:
            mixes.append((float(demand_mult(state, store_id, dept) or 1.0), dept))
            costs.append((float(cost_mult(state, store_id, dept) or 1.0), dept))
        mix_mult, mix_dept = max(mixes, key=lambda item: abs(item[0] - 1.0))
        cost_m, cost_dept = max(costs, key=lambda item: abs(item[0] - 1.0))
        freight = float(freight_mult(state, store_id) or 1.0)
        slip = int(lead_slip_days(state) or 0)
        mix_name = DEPARTMENT_LABELS.get(mix_dept, mix_dept)
        cost_name = DEPARTMENT_LABELS.get(cost_dept, cost_dept)
        visit_bit = f"{place} would draw {people:,} people on a day that draws 1,000 at neutral."
        if abs(weather - 1.0) >= 0.01:
            visit_bit += f" Weather alone is {weather:.2f}×."
        mix_bit = (
            f"{mix_name} is {mix_mult:.2f}× a normal mix."
            if abs(mix_mult - 1.0) >= 0.01 else
            "No department is far from a normal mix."
        )
        cost_bit = f"{cost_name} lands at ${max(0, int(round(100 * cost_m)))} on a $100 case."
        freight_dollars = max(0, int(round(1000 * freight)))
        freight_bit = f"A $1,000 truck bill is ${freight_dollars:,}."
        try:
            from open_late.economy import _value

            diesel = float(_value(state, 6, store_id) or 100) / 100.0
        except Exception:
            diesel = 1.0
        if abs(diesel - 1.0) >= 0.02:
            freight_bit += (
                f" Diesel is {diesel:.2f}×, so the truck bill moves first. "
                "The shelf price stays until you change it."
            )
        if slip <= 0:
            truck_bit = "Deliveries are on the lead time you ordered."
        else:
            truck_bit = f"Trucks are slipping {slip} day{'s' if slip != 1 else ''}."
        moves = [
            (abs(visits - 1.0), f"The door at {place} is {visits:.2f}× a neutral day."),
            (abs(freight - 1.0), f"Freight is {freight:.2f}×."),
            (abs(cost_m - 1.0), f"{cost_name} merchandise is {cost_m:.2f}×."),
        ]
        lead = max(moves, key=lambda item: item[0])[1]
        try:
            headline = (economy_news(state, store_id=store_id, limit=1) or [{}])[0].get("headline") or ""
        except Exception:
            headline = ""
        if headline:
            lead = f"{lead} {headline}"
        return lead, [
            ("Visits", visit_bit),
            ("Mix", mix_bit),
            ("Merchandise", cost_bit),
            ("Freight", freight_bit),
            ("Trucks", truck_bit),
        ]

    def _today_card(self, state) -> QFrame:
        frame = QFrame()
        frame.setObjectName("todayCard")
        box = QVBoxLayout(frame)
        box.setContentsMargins(12, 8, 12, 8)
        box.setSpacing(4)
        box.addWidget(_label("TODAY", 11, QFont.Weight.DemiBold, "#0E5C32", "todayKicker"))
        try:
            lead, pipes = self._today_facts(state)
        except Exception:
            lead, pipes = ("The card is quiet.", [("Note", "Open a store and the day will show what moved.")])
        lead_lab = _label(lead, 13, QFont.Weight.DemiBold, DASH_TEXT, "todayLead", wrap=True)
        box.addWidget(lead_lab)
        for name, text in pipes:
            row = QHBoxLayout()
            row.setSpacing(10)
            cap = _label(name, 11, QFont.Weight.DemiBold, DASH_FAINT)
            cap.setMinimumWidth(108)
            row.addWidget(cap)
            detail = _label(text, 12, color=DASH_TEXT, wrap=True)
            row.addWidget(detail, stretch=1)
            box.addLayout(row)
        return frame

    def _title_row(self, state) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(8)
        title = _label("Economy", 16, QFont.Weight.Bold, "#FFFFFF", "pageTitle")
        title.setMinimumHeight(34)
        title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        column.addWidget(title)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        deck = "Indexes sit on a neutral 100. Reasons, news, and the calendar come from the live card."
        if state is not None:
            difficulty = economy_difficulty_of(state).title()
            day = getattr(state, "day", 0)
            live = difficulty.lower() != "off"
            deck = (
                f"{difficulty}  ·  Day {day}.  The card is moving this store."
                if live else
                f"Off  ·  Day {day}.  The card is neutral until the game is on Standard."
            )
        row.addWidget(_label(deck, 13, color=DASH_MUTED, name="pageDeck", wrap=True), stretch=1)
        if self._tab == "factors":
            row.addLayout(self._filters(state))
        column.addLayout(row)
        return column

    def _filters(self, state) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        cities = economy_cities()
        city = QComboBox()
        city.setObjectName("cityFilter")
        city.setFont(ui_font(12))
        city.addItem("All cities", None)
        for ident in cities:
            city.addItem(city_display_name(ident), ident)
        index = city.findData(self._city_id)
        if index >= 0:
            city.setCurrentIndex(index)
        city.currentIndexChanged.connect(lambda _i, box=city: self._set_city(box.currentData()))
        row.addWidget(city)

        scope = QComboBox()
        scope.setObjectName("scopeFilter")
        scope.setFont(ui_font(12))
        scope.addItem("All scopes", None)
        for key, label in SCOPE_LABELS.items():
            scope.addItem(label, key)
        s_index = scope.findData(self._scope)
        if s_index >= 0:
            scope.setCurrentIndex(s_index)
        scope.currentIndexChanged.connect(lambda _i, box=scope: self._set_scope(box.currentData()))
        row.addWidget(scope)
        return row

    def _tab_bar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        for key, label in TABS:
            btn = QPushButton(_amp(label))
            btn.setObjectName("economyTabOn" if key == self._tab else "economyTab")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFont(ui_font(12, QFont.Weight.DemiBold))
            btn.setProperty("tabKey", key)
            btn.clicked.connect(lambda _=False, k=key: self._set_tab(k))
            row.addWidget(btn)
        row.addStretch(1)
        return row

    def _empty_card(self, title: str, body: str, name: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName(name)
        frame.setProperty("class", "ecoCard")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(22, 28, 22, 28)
        layout.setSpacing(8)
        layout.addStretch(1)
        layout.addWidget(_label(title, 18, QFont.Weight.DemiBold, DASH_TEXT, name + "Title", wrap=True))
        layout.addWidget(_label(body, 13, color=DASH_MUTED, name=name + "Body", wrap=True))
        layout.addStretch(1)
        return frame

    def _scroll(self, name: str) -> tuple[QScrollArea, QVBoxLayout]:
        scroll = QScrollArea()
        scroll.setObjectName(name)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName(name + "Inner")
        pal = inner.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor("#FFFFFF"))
        pal.setColor(QPalette.ColorRole.Base, QColor("#FFFFFF"))
        inner.setPalette(pal)
        inner.setAutoFillBackground(True)
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(0, 0, 2, 8)
        layout.setSpacing(8)
        scroll.setWidget(inner)
        return scroll, layout

    def _factors_panel(self, state) -> QWidget:
        scroll, layout = self._scroll("factorScroll")
        rows = self._factor_rows_for(state)
        if not rows:
            layout.addWidget(self._empty_card(
                "No factors on this filter.",
                "Clear the city or scope filter to see the full board.",
                "factorEmpty",
            ))
            layout.addStretch(1)
            return scroll

        groups = self._factor_groups(rows)
        sparks = self._factor_sparks(state, rows)

        movers = self._movers_strip(state, rows)
        layout.addWidget(movers)
        row_frames: list[QFrame] = []

        for key, items in groups:
            expanded = self._expanded.get(key, True)
            section = QFrame()
            section.setObjectName("categorySection")
            section.setProperty("category", key)
            box = QVBoxLayout(section)
            box.setContentsMargins(12, 8, 12, 10)
            box.setSpacing(4)
            header = QPushButton(_amp(
                f"{'▾' if expanded else '▸'}  {_category_title(key).upper()}    ·    {len(items)} factor{'s' if len(items) != 1 else ''}"
            ))
            header.setObjectName("categoryHeader")
            header.setFont(ui_font(11, QFont.Weight.DemiBold))
            header.setCursor(Qt.CursorShape.PointingHandCursor)
            header.setProperty("category", key)
            header.clicked.connect(lambda _=False, k=key: self._toggle_category(k))
            box.addWidget(header)
            if expanded:
                for item in items:
                    frame = self._factor_row(item, sparks.get(str(item.get("id")), []))
                    row_frames.append(frame)
                    box.addWidget(frame)
            layout.addWidget(section)
        layout.addStretch(1)
        if self._tab == "factors":
            self._factor_cache = {
                "shape": self._factor_shape(groups),
                "scroll": scroll,
                "layout": layout,
                "movers": movers,
                "rows": row_frames,
            }
        return scroll

    def _movers_strip(self, state, rows: list[dict]) -> QFrame:
        frame = QFrame()
        frame.setObjectName("moversStrip")
        box = QVBoxLayout(frame)
        box.setContentsMargins(12, 8, 12, 10)
        box.setSpacing(6)
        box.addWidget(_ink_label("BIGGEST MOVERS THIS WEEK", 10, QFont.Weight.DemiBold, DASH_FAINT, "figureCaption"))
        ranked = economy_movers(state, city_id=self._city_id, limit=5)
        if not ranked:
            # Adapter already falls back; this is a last resort if only in-memory rows exist.
            ranked = sorted(
                [row for row in rows if factor_kind(row) == "index"],
                key=lambda row: (
                    -abs(float(row.get("value") or 0) - (factor_neutral(row) if factor_neutral(row) is not None else 100.0)),
                    int(row.get("id") or 0),
                ),
            )[:5]
        grid = QHBoxLayout()
        grid.setSpacing(8)
        grid.setContentsMargins(0, 0, 0, 0)
        if not ranked:
            grid.addWidget(_ink_label("No factors on the board.", 12, color=DASH_MUTED))
        for item in ranked:
            try:
                number = float(item.get("value") or 100)
            except (TypeError, ValueError):
                number = 100.0
            try:
                delta = float(item.get("delta") or 0)
            except (TypeError, ValueError):
                delta = 0.0
            band = factor_band(number, item.get("band"), kind=factor_kind(item), neutral=factor_neutral(item))
            color = BAND_COLORS.get(band, DASH_MUTED)
            cell = QFrame()
            cell.setObjectName("moverCell")
            cell.setProperty("band", band)
            cell.setProperty("factorId", item.get("id"))
            col = QVBoxLayout(cell)
            col.setContentsMargins(8, 6, 8, 6)
            col.setSpacing(2)
            name = _ink_label(str(item.get("name") or "Factor"), 12, QFont.Weight.DemiBold, DASH_TEXT, "moverName")
            name.setWordWrap(True)
            col.addWidget(name)
            row = QHBoxLayout()
            row.setSpacing(6)
            shown = f"{int(round(number))}" if abs(number - round(number)) < 0.05 else f"{number:.1f}"
            row.addWidget(_ink_label(shown, 16, QFont.Weight.Bold, DASH_TEXT, "moverValue"))
            if abs(delta) < 0.05:
                delta_text, delta_color = "—", DASH_FAINT
            else:
                arrow = "↑" if delta > 0 else "↓"
                pretty = f"{abs(delta):.0f}" if abs(delta - round(delta)) < 0.05 else f"{abs(delta):.1f}"
                delta_text, delta_color = f"{arrow} {pretty}", (UP_NEON if delta > 0 else DOWN_NEON)
            row.addWidget(_ink_label(delta_text, 11, QFont.Weight.DemiBold, delta_color, "moverDelta"))
            row.addWidget(_ink_label(band.upper(), 9, QFont.Weight.DemiBold, color, "moverBand"))
            row.addStretch(1)
            col.addLayout(row)
            grid.addWidget(cell, stretch=1)
        box.addLayout(grid)
        return frame

    @staticmethod
    def _factor_row_values(item: dict, series: list) -> dict:
        value = item.get("value")
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = 100.0
        kind = factor_kind(item)
        out = {
            "name": str(item.get("name") or ""),
            "scope": SCOPE_LABELS.get(str(item.get("scope") or ""), str(item.get("scope") or "").title()),
            "kind": kind,
        }
        if kind == "state":
            out["chip"] = str(item.get("label") or "").strip() or str(item.get("name") or "State")
            return out
        rng = item.get("range") or [70, 140]
        out["low"] = rng[0] if len(rng) > 0 else 70
        out["high"] = rng[1] if len(rng) > 1 else 140
        neutral = factor_neutral(item)
        band = factor_band(number, item.get("band"), kind=kind, neutral=neutral)
        out["number"] = number
        out["neutral"] = neutral
        out["band"] = band
        out["band_color"] = BAND_COLORS.get(band, DASH_MUTED)
        shown = f"{int(round(number))}" if abs(number - round(number)) < 0.05 else f"{number:.1f}"
        out["shown"] = shown
        out["tip"] = f"{shown} vs a neutral {int(round(neutral))}" if neutral is not None and abs(neutral - 100) > 0.05 else ""
        try:
            delta = float(item.get("delta") or 0)
        except (TypeError, ValueError):
            delta = 0.0
        if abs(delta) < 0.05:
            out["delta_text"], out["delta_color"] = "—", DASH_FAINT
        else:
            arrow = "↑" if delta > 0 else "↓"
            pretty = f"{abs(delta):.0f}" if abs(delta - round(delta)) < 0.05 else f"{abs(delta):.1f}"
            out["delta_text"] = f"{arrow} {pretty}"
            out["delta_color"] = UP_NEON if delta > 0 else DOWN_NEON
        path = list(series or [])
        if len(path) == 1:
            path = [path[0], path[0]]
        if not path:
            path = [number, number]
        out["path"] = path
        return out

    def _fill_factor_row(self, frame: QFrame, item: dict, series: list) -> None:
        """Push fresh values into a row built by _factor_row (same shape)."""
        refs = getattr(frame, "_x_refs", None)
        if not refs:
            return
        vals = self._factor_row_values(item, series)
        frame.setProperty("factorId", item.get("id"))
        frame.setProperty("factorKind", vals["kind"])
        _set_text(refs["name"], vals["name"])
        _set_text(refs["scope"], vals["scope"])
        if vals["kind"] == "state":
            _set_text(refs["chip"], vals["chip"])
            return
        bar = refs["bar"]
        if bar.set_values(vals["number"], vals["low"], vals["high"], color=vals["band_color"],
                          neutral=vals["neutral"] if vals["neutral"] is not None else 100.0):
            bar.update()
        _set_text(refs["pip"], vals["band"].upper())
        _set_ink(refs["pip"], vals["band_color"])
        _set_text(refs["val"], vals["shown"])
        if refs["val"].toolTip() != vals["tip"]:
            refs["val"].setToolTip(vals["tip"])
        _set_text(refs["delta"], vals["delta_text"])
        _set_ink(refs["delta"], vals["delta_color"])
        spark = refs["spark"]
        color = QColor(vals["band_color"])
        if spark.values != vals["path"] or spark.color != color:
            spark.values = vals["path"]
            spark.color = color
            spark.update()

    def _factor_row(self, item: dict, series: list) -> QFrame:
        frame = QFrame()
        refs: dict = {}
        frame._x_refs = refs
        frame.setObjectName("factorRow")
        frame.setProperty("factorId", item.get("id"))
        frame.setProperty("factorKind", factor_kind(item))
        row = QHBoxLayout(frame)
        row.setContentsMargins(10, 6, 10, 6)
        row.setSpacing(10)
        name_col = QVBoxLayout()
        name_col.setSpacing(0)
        name = _ink_label(str(item.get("name") or ""), 13, QFont.Weight.DemiBold, DASH_TEXT)
        name.setObjectName("factorName")
        name_col.addWidget(name)
        refs["name"] = name
        scope = SCOPE_LABELS.get(str(item.get("scope") or ""), str(item.get("scope") or "").title())
        refs["scope"] = _ink_label(scope, 10, color=DASH_FAINT)
        name_col.addWidget(refs["scope"])
        row.addLayout(name_col, stretch=3)

        value = item.get("value")
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = 100.0
        kind = factor_kind(item)
        if kind == "state":
            chip = QFrame()
            chip.setObjectName("stateChip")
            chip_box = QHBoxLayout(chip)
            chip_box.setContentsMargins(0, 0, 0, 0)
            chip_box.setSpacing(0)
            text = str(item.get("label") or "").strip() or str(item.get("name") or "State")
            lab = _ink_label(text, 12, QFont.Weight.DemiBold, DASH_TEXT, "stateChipLabel")
            lab.setWordWrap(False)
            refs["chip"] = lab
            chip_box.addWidget(lab)
            row.addStretch(1)
            row.addWidget(chip, stretch=0)
            return frame

        rng = item.get("range") or [70, 140]
        low = rng[0] if len(rng) > 0 else 70
        high = rng[1] if len(rng) > 1 else 140
        neutral = factor_neutral(item)
        band = factor_band(number, item.get("band"), kind=kind, neutral=neutral)
        band_color = BAND_COLORS.get(band, DASH_MUTED)
        bar = DeviationBar(number, low, high, color=band_color, neutral=neutral if neutral is not None else 100.0)
        row.addWidget(bar, stretch=2)
        refs["bar"] = bar
        pip = _ink_label(band.upper(), 9, QFont.Weight.DemiBold, band_color, "factorBand")
        pip.setMinimumWidth(44)
        row.addWidget(pip)
        refs["pip"] = pip

        shown = f"{int(round(number))}" if abs(number - round(number)) < 0.05 else f"{number:.1f}"
        val = _ink_label(shown, 16, QFont.Weight.Bold, DASH_TEXT, "factorValue")
        val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        val.setMinimumWidth(40)
        if neutral is not None and abs(neutral - 100) > 0.05:
            val.setToolTip(f"{shown} vs a neutral {int(round(neutral))}")
        row.addWidget(val)
        refs["val"] = val

        try:
            delta = float(item.get("delta") or 0)
        except (TypeError, ValueError):
            delta = 0.0
        if abs(delta) < 0.05:
            delta_text, delta_color = "—", DASH_FAINT
        else:
            arrow = "↑" if delta > 0 else "↓"
            pretty = f"{abs(delta):.0f}" if abs(delta - round(delta)) < 0.05 else f"{abs(delta):.1f}"
            delta_text = f"{arrow} {pretty}"
            delta_color = UP_NEON if delta > 0 else DOWN_NEON
        delta_lab = _ink_label(delta_text, 11, QFont.Weight.DemiBold, delta_color, "factorDelta")
        delta_lab.setMinimumWidth(40)
        row.addWidget(delta_lab)
        refs["delta"] = delta_lab

        path = list(series or [])
        if len(path) == 1:
            path = [path[0], path[0]]
        if not path:
            path = [number, number]
        spark = Sparkline(path, band_color, glow=True)
        spark.setFixedWidth(96)
        spark.setFixedHeight(24)
        row.addWidget(spark)
        refs["spark"] = spark
        return frame

    def _impact_panel(self, state) -> QWidget:
        wrap = QWidget()
        wrap.setObjectName("impactPanel")
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        ids = store_ids(state) if state is not None else []
        if not ids:
            layout.addWidget(self._empty_card(
                "No stores on the board.",
                "Open a door and the attribution will land here.",
                "impactEmpty",
            ), stretch=1)
            return wrap

        if self._store_id not in ids:
            self._store_id = ids[0]

        picker = QHBoxLayout()
        picker.setSpacing(8)
        picker.addWidget(_label("STORE", 10, QFont.Weight.DemiBold, DASH_FAINT, "figureCaption"))
        combo = QComboBox()
        combo.setObjectName("storePick")
        combo.setFont(ui_font(12))
        for sid in ids:
            combo.addItem(_door_label(state, sid), sid)
        index = combo.findData(self._store_id)
        if index >= 0:
            combo.setCurrentIndex(index)
        combo.currentIndexChanged.connect(lambda _i, box=combo: self._set_store(box.currentData()))
        picker.addWidget(combo, stretch=0)
        picker.addWidget(_label("Last 7 days, versus a neutral card.", 12, color=DASH_MUTED), stretch=1)
        layout.addLayout(picker)

        filters_on = impact_filter_kwargs_supported()
        if filters_on:
            layout.addLayout(self._impact_filters())

        impact = economy_store_impact(
            state,
            self._store_id,
            days=7,
            department=self._impact_department if filters_on else None,
            category=self._impact_category if filters_on else None,
            events_only=self._impact_events_only if filters_on else False,
        )
        pnl = impact.get("pnl") or {}
        neutral = impact.get("neutral_pnl") or {}
        delta = impact.get("delta") or {}
        reasons = list(impact.get("reasons") or [])

        actual = int(pnl.get("contribution") or 0)
        base = int(neutral.get("contribution") or 0)
        move = int(delta.get("contribution") if delta.get("contribution") is not None else actual - base)

        scroll, body = self._scroll("impactScroll")

        chips = QHBoxLayout()
        chips.setSpacing(10)
        for caption, amount, color, signed in (
            ("NEUTRAL P&L", base, DASH_TEXT, False),
            ("MOVEMENT", move, UP_NEON if move > 0 else DOWN_NEON if move < 0 else DASH_MUTED, True),
            ("ACTUAL P&L", actual, DASH_TEXT, False),
        ):
            chip = QFrame()
            chip.setObjectName("ecoCard")
            chip.setToolTip(_exact_signed_money(amount) if signed else _exact_money(amount))
            chip_box = QVBoxLayout(chip)
            chip_box.setContentsMargins(12, 6, 12, 6)
            chip_box.setSpacing(1)
            chip_box.addWidget(_label(caption, 10, QFont.Weight.DemiBold, DASH_FAINT))
            shown = _signed_money(amount) if signed else _plain_money(amount)
            figure = _label(shown, 22, QFont.Weight.Bold, color)
            _tip_money(figure, amount, signed=signed)
            chip_box.addWidget(figure)
            chips.addWidget(chip)
        body.addLayout(chips)

        trend = self._pnl_trend(state, self._store_id)
        if trend is not None:
            body.addWidget(trend)

        has_activity = bool(reasons) or base or actual or move
        if not has_activity:
            empty = self._empty_card(
                "No attribution yet.",
                "Reasons appear after the economy has been live for a week, and stay empty when difficulty is off. Close a few days, then come back.",
                "impactEmpty",
            )
            body.addWidget(empty)
            body.addStretch(1)
            layout.addWidget(scroll, stretch=1)
            return wrap

        filtered = bool(filters_on and (self._impact_department or self._impact_category or self._impact_events_only))
        steps = self._waterfall_steps(base, reasons, actual, reconcile=not filtered)
        calm = movement_is_calm(base, move)
        if calm:
            note = _label(
                "Economy is calm this week.",
                13,
                QFont.Weight.DemiBold,
                DASH_TEXT,
                "calmNote",
                wrap=True,
            )
            body.addWidget(note)
            body.addWidget(_label(
                "Reason bars use a relative scale so small moves stay readable. Totals are capped; the dollar labels are the official figures.",
                11,
                color=DASH_MUTED,
                wrap=True,
            ))
        chart = WaterfallChart(steps, calm=calm)
        chart.setMinimumHeight(200)
        chart.setMaximumHeight(240)
        body.addWidget(chart)

        if not reasons and not calm:
            note = _label(
                "No factor lines were attached. Indexes may still sit near 100, or the economy has not been live long enough. Reasons stay empty when difficulty is off.",
                13,
                color=DASH_MUTED,
                name="impactEmpty",
                wrap=True,
            )
            body.addWidget(note)
        elif reasons:
            body.addWidget(_label("WHY IT MOVED", 10, QFont.Weight.DemiBold, DASH_FAINT, "figureCaption"))
            for reason in reasons:
                body.addWidget(self._reason_row(reason))
        body.addStretch(1)
        layout.addWidget(scroll, stretch=1)
        return wrap

    def _impact_filters(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        row.setContentsMargins(0, 0, 0, 0)
        dept = QComboBox()
        dept.setObjectName("deptFilter")
        dept.setFont(ui_font(12))
        dept.addItem("All departments", None)
        for ident, label, _color in planogram_departments():
            dept.addItem(label, ident)
        index = dept.findData(self._impact_department)
        if index >= 0:
            dept.setCurrentIndex(index)
        dept.currentIndexChanged.connect(lambda _i, box=dept: self._set_impact_department(box.currentData()))
        row.addWidget(dept)

        category = QComboBox()
        category.setObjectName("categoryFilter")
        category.setFont(ui_font(12))
        category.addItem("All categories", None)
        for key, label in CATEGORY_LABELS.items():
            category.addItem(label, key)
        c_index = category.findData(self._impact_category)
        if c_index >= 0:
            category.setCurrentIndex(c_index)
        category.currentIndexChanged.connect(lambda _i, box=category: self._set_impact_category(box.currentData()))
        row.addWidget(category)

        events = QPushButton("Events only")
        events.setObjectName("eventsOnlyBtnOn" if self._impact_events_only else "eventsOnlyBtn")
        events.setCursor(Qt.CursorShape.PointingHandCursor)
        events.setFont(ui_font(12, QFont.Weight.DemiBold))
        events.setCheckable(True)
        events.setChecked(self._impact_events_only)
        events.clicked.connect(self._toggle_events_only)
        row.addWidget(events)
        row.addStretch(1)
        return row

    def _pnl_trend(self, state, store_id: str):
        payload = economy_sparklines(
            state,
            [],
            weeks=12,
            store_id=store_id,
            lines=["sales", "contribution"],
        )
        series = payload.get("series") or {}
        if not (series.get("sales") or series.get("contribution") or series.get("chain:sales") or series.get("chain:contribution")):
            return None
        frame = QFrame()
        frame.setObjectName("pnlTrend")
        box = QVBoxLayout(frame)
        box.setContentsMargins(10, 4, 10, 4)
        box.setSpacing(1)
        box.addWidget(_label("SALES AND STORE P&L  ·  STORE VS CHAIN", 10, QFont.Weight.DemiBold, DASH_FAINT, "figureCaption"))
        chart = PnlTrend(payload.get("weeks") or [], series)
        box.addWidget(chart)
        return frame

    def _waterfall_steps(self, base: int, reasons: list[dict], actual: int, reconcile: bool = True) -> list[dict]:
        order = ["sales", "cogs", "labor", "rent", "freight", "shrink", "card_fees", "pos_fees"]
        ranked = sorted(
            reasons,
            key=lambda row: (order.index(row.get("line")) if row.get("line") in order else 99, -abs(int(row.get("dollars") or 0))),
        )
        steps = [{
            "name": "Neutral P&L",
            "kind": "total",
            "level": base,
            "prior": 0,
            "display": _plain_money(base),
        }]
        running = base
        for reason in ranked:
            effect = _contrib_effect(str(reason.get("line") or ""), int(reason.get("dollars") or 0))
            if effect == 0:
                continue
            prior = running
            running += effect
            steps.append({
                "name": str(reason.get("name") or LINE_LABELS.get(reason.get("line"), "Factor")),
                "kind": "step",
                "level": running,
                "prior": prior,
                "display": _signed_money(effect),
            })
        if reconcile and running != actual:
            prior = running
            steps.append({
                "name": "Other",
                "kind": "step",
                "level": actual,
                "prior": prior,
                "display": _signed_money(actual - running),
            })
            running = actual
        final = actual if reconcile else running
        steps.append({
            "name": "Actual P&L" if reconcile else "Filtered P&L",
            "kind": "total",
            "level": final,
            "prior": 0,
            "display": _plain_money(final),
        })
        return steps

    def _reason_row(self, reason: dict) -> QFrame:
        frame = QFrame()
        frame.setObjectName("reasonRow")
        row = QHBoxLayout(frame)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(8)
        line = str(reason.get("line") or "")
        effect = _contrib_effect(line, int(reason.get("dollars") or 0))
        color = UP_NEON if effect > 0 else DOWN_NEON if effect < 0 else DASH_MUTED
        col = QVBoxLayout()
        col.setSpacing(1)
        col.addWidget(_label(str(reason.get("name") or "Factor"), 13, QFont.Weight.DemiBold, DASH_TEXT))
        bits = [LINE_LABELS.get(line, line.title() if line else "")]
        if reason.get("department"):
            bits.append(str(reason["department"]).replace("_", " ").title())
        if reason.get("note"):
            bits.append(str(reason["note"]))
        col.addWidget(_label("  ·  ".join(b for b in bits if b), 11, color=DASH_MUTED, wrap=True))
        row.addLayout(col, stretch=1)
        amount = _label(_signed_money(effect), 14, QFont.Weight.Bold, color)
        _tip_money(amount, effect, signed=True)
        row.addWidget(amount)
        return frame

    def _news_calendar_panel(self, state) -> QWidget:
        wrap = QWidget()
        wrap.setObjectName("newsCalendarPanel")
        split = QHBoxLayout(wrap)
        split.setContentsMargins(0, 0, 0, 0)
        split.setSpacing(10)
        split.addWidget(self._news_panel(state), stretch=3)
        split.addWidget(self._calendar_panel(state), stretch=2)
        return wrap

    def _news_panel(self, state) -> QWidget:
        scroll, layout = self._scroll("newsScroll")
        snap = economy_snapshot(state)
        events = list(snap.get("events_active") or [])
        news = economy_news(state, store_id=None, limit=20)

        layout.addWidget(_label("ACTIVE EVENTS", 10, QFont.Weight.DemiBold, DASH_FAINT, "figureCaption"))
        if not events:
            layout.addWidget(_label("No active events on the card.", 12, color=DASH_MUTED, name="eventsEmpty"))
        else:
            for event in events:
                layout.addWidget(self._event_card(event))

        layout.addSpacing(6)
        layout.addWidget(_label("ON THE WIRE", 10, QFont.Weight.DemiBold, DASH_FAINT, "figureCaption"))
        if not news:
            layout.addWidget(_label("No economy news on the wire yet. Close a day to start the feed.", 12, color=DASH_MUTED, name="newsEmpty"))
        else:
            for item in news:
                layout.addWidget(self._news_card(item, events))
        layout.addStretch(1)
        return scroll

    def _event_card(self, event: dict) -> QFrame:
        frame = QFrame()
        frame.setObjectName("eventCard")
        box = QVBoxLayout(frame)
        box.setContentsMargins(12, 8, 12, 10)
        box.setSpacing(3)
        color = _severity_color(event.get("severity"))
        top = QHBoxLayout()
        pip = _label("●", 11, color=color)
        top.addWidget(pip)
        name = _label(str(event.get("name") or "Event"), 13, QFont.Weight.DemiBold, DASH_TEXT, wrap=True)
        name.setToolTip(str(event.get("name") or "Event"))
        top.addWidget(name, stretch=1)
        days = ""
        start, end = event.get("day_start"), event.get("day_end")
        if start and end:
            days = f"Days {start}–{end}"
        elif start:
            days = f"Day {start}"
        if days:
            top.addWidget(_label(days, 11, color=DASH_FAINT))
        box.addLayout(top)
        place = _place_text(event)
        box.addWidget(_label(place, 11, color=DASH_MUTED))
        return frame

    def _news_card(self, item: dict, events: list[dict]) -> QFrame:
        frame = QFrame()
        frame.setObjectName("newsCard")
        box = QVBoxLayout(frame)
        box.setContentsMargins(12, 8, 12, 10)
        box.setSpacing(3)
        color = _severity_color(item.get("severity"))
        meta = QHBoxLayout()
        outlet = str(item.get("outlet") or "Wire")
        day = item.get("day")
        meta.addWidget(_label(outlet.upper(), 10, QFont.Weight.DemiBold, color))
        if day is not None:
            meta.addWidget(_label(f"Day {day}", 10, color=DASH_FAINT))
        meta.addWidget(_label(_place_text(item, events), 10, color=DASH_MUTED), stretch=1)
        box.addLayout(meta)
        headline = str(item.get("headline") or "")
        head = _label(headline, 14, QFont.Weight.DemiBold, DASH_TEXT, wrap=True)
        body = str(item.get("body") or "").strip()
        head.setToolTip(headline if not body else f"{headline}\n\n{body}")
        box.addWidget(head)
        if body:
            body_lab = _label(body, 12, color=DASH_MUTED, wrap=True)
            body_lab.setToolTip(body)
            box.addWidget(body_lab)
        frame.setToolTip(headline if not body else f"{headline}\n\n{body}")
        return frame

    def _calendar_panel(self, state) -> QWidget:
        scroll, layout = self._scroll("calendarScroll")
        layout.addWidget(_label("NEXT 8 WEEKS", 10, QFont.Weight.DemiBold, DASH_FAINT, "figureCaption"))
        rows = economy_calendar(state, weeks=8)
        if not rows:
            layout.addWidget(_label("The calendar is empty on this build.", 12, color=DASH_MUTED, name="calendarEmpty"))
            layout.addStretch(1)
            return scroll
        for row in rows:
            layout.addWidget(self._week_card(row))
        layout.addStretch(1)
        return scroll

    def _week_card(self, row: dict) -> QFrame:
        frame = QFrame()
        frame.setObjectName("weekCard")
        box = QVBoxLayout(frame)
        box.setContentsMargins(12, 8, 12, 10)
        box.setSpacing(4)
        week_id = row.get("week_id")
        day_from, day_to = row.get("day_from"), row.get("day_to")
        heading = f"WEEK {week_id}"
        if day_from and day_to:
            heading += f"    ·    DAYS {day_from}–{day_to}"
        box.addWidget(_label(heading, 11, QFont.Weight.DemiBold, DASH_TEXT))
        labels = list(row.get("labels") or [])
        if labels:
            chips = _FlowRow()
            for label in labels:
                chip = _label(f"  {label}  ", 10, QFont.Weight.DemiBold, DASH_TEXT)
                chip.setStyleSheet(
                    f"color: {DASH_TEXT}; background: #E7F6EE; border: 1px solid #E3E8EE; border-radius: 4px; padding: 2px 8px;"
                )
                chip.adjustSize()
                chips.add(chip)
            box.addWidget(chips)
        else:
            box.addWidget(_label("Quiet week", 11, color=DASH_FAINT))
        weather = dict(row.get("city_weather") or {})
        if weather:
            parts = [f"{city_display_name(city)} {str(label)}" for city, label in weather.items()]
            box.addWidget(_label("  ·  ".join(parts), 11, color=DASH_MUTED, wrap=True))
        return frame
