"""Dashboard, store portfolio, and POS pages for the HQ shell."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPalette, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractScrollArea,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from open_late.corporate import capital_markets, door_by_id, manager_by_id, openable_markets, open_market
from open_late.finance import weekly_obligations
from open_late.text import (
    CATEGORY_LABELS,
    CATEGORY_SHORT,
    WEEKDAYS,
    is_sunday,
    money,
    money_compact,
    money_compact_signed,
    money_axis_ticks,
    weekday_name,
)

try:
    from open_late.corporate import allocate, replenish, set_planogram, set_door_hours, sign_deal
except ImportError:  # pragma: no cover
    allocate = None
    replenish = None
    set_planogram = None
    set_door_hours = None
    sign_deal = None

try:
    from open_late.engine import order_qty_max
except ImportError:  # pragma: no cover
    def order_qty_max() -> int:
        return 40
from open_late.ui.hq_adapter import (
    chain_board,
    chain_info,
    chain_logo_path,
    contribution_share,
    department_sales,
    display_address,
    street_address,
    hq_available,
    install_fee,
    planogram_departments,
    pos_options,
    recorded_sales,
    resolved_chain_id,
    scoped_store_ids,
    set_store_pos,
    store_pnl,
    store_pos,
    warehouse_units,
)
from open_late.ui.hq_art import CITIES, StoreMap, StorefrontArt
from open_late.ui.theme import (
    DASH_ACCENT, DASH_BG, DASH_CARD, DASH_FAINT, DASH_GLOW, DASH_LINE, DASH_MUTED, FRAME,
    DASH_PIN_HIGH, DASH_PIN_LOW, DASH_PIN_MID, DASH_TEXT, DOWN, HQ_CANVAS, HQ_CARD, HQ_FAINT, HQ_LINE, HQ_MUTED,
    HQ_TITLE, OPEN_GREEN, RR_BLUE, RR_YELLOW, TEXT, UP, ui_font,
)
from open_late.ui.opening_cost import shown_opening_cost  # rival AI: live opening cost


def _label(text: str, size: int = 13, weight=QFont.Weight.Normal, color: str = TEXT, name: str = "", wrap: bool = False) -> QLabel:
    lab = QLabel(text)
    lab.setFont(ui_font(size, weight))
    lab.setStyleSheet(f"color: {color}; background: transparent;")
    lab.setWordWrap(wrap)
    if name:
        lab.setObjectName(name)
    return lab


def labor_budget_ceiling(current: int = 0) -> int:
    """Upper end of a labor-budget spinner. E7e default is $180,000; keep a fallback if it has not landed."""
    default = 180_000
    try:
        from open_late.finance import LABOR_BUDGET_DEFAULT
        if LABOR_BUDGET_DEFAULT is not None:
            default = int(LABOR_BUDGET_DEFAULT)
    except (ImportError, TypeError, ValueError):
        default = 180_000
    try:
        current_val = int(current or 0)
    except (TypeError, ValueError):
        current_val = 0
    return max(default, current_val, 180_000)


def _card() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(6)
    return frame, layout


def _page_header(title: str, deck: str, search: QWidget | None = None) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    col = QVBoxLayout()
    col.setSpacing(2)
    col.addWidget(_label(title, 26, QFont.Weight.Bold, HQ_TITLE, "pageTitle"))
    if deck:
        col.addWidget(_label(deck, 13, color=HQ_MUTED, name="pageDeck", wrap=True))
    row.addLayout(col, stretch=1)
    if search is not None:
        row.addWidget(search, alignment=Qt.AlignmentFlag.AlignTop)
    return row



def _short_money(value: float) -> str:
    return money_compact(value)


def _tip_money(widget, amount, *, signed: bool = False) -> None:
    if widget is None:
        return
    try:
        number = int(round(float(amount or 0)))
    except (TypeError, ValueError):
        number = 0
    if signed:
        tip = f"+{money(number)}" if number > 0 else (f"−{money(abs(number))}" if number < 0 else money(0))
    else:
        tip = money(number)
    widget.setToolTip(tip)


def _margin_pct(sales, contribution) -> float | None:
    try:
        sales = float(sales or 0)
        contribution = float(contribution or 0)
    except (TypeError, ValueError):
        return None
    if sales <= 0:
        return None
    return contribution / sales * 100.0


def _board_total(state, days: int) -> dict:
    board = chain_board(state, days=days) or []
    return next((row for row in board if row.get("store_id") == "chain"), {}) or {}


def _prior_split(current: dict, combined: dict) -> dict:
    out = {}
    for key in ("sales", "contribution"):
        out[key] = int(combined.get(key) or 0) - int(current.get(key) or 0)
    return out


def _week_length() -> int:
    return max(1, len(WEEKDAYS))


def _week_id_for(day: int) -> int:
    """Engine week id (0-based). Guarded so the chart still works without E1."""
    try:
        from open_late.economy import week_id
        return int(week_id(day))
    except Exception:
        return (max(1, int(day)) - 1) // _week_length()


def _normalize_trend_points(points) -> list[dict]:
    out = []
    for item in points or []:
        if isinstance(item, dict):
            value = float(item.get("value") or 0)
            label = str(item.get("label") or "")
            tip = str(item.get("tip") or "")
            row = dict(item)
            row["label"] = label
            row["value"] = value
            if not tip:
                tip = f"{label}  ·  {money(int(round(value)))}"
            row["tip"] = tip
            row["partial"] = bool(item.get("partial"))
            out.append(row)
            continue
        label = str(item[0])
        value = float(item[1])
        out.append({
            "label": label,
            "value": value,
            "partial": False,
            "days": None,
            "tip": f"{label}  ·  {money(int(round(value)))}",
        })
    return out


def _week_points(history, state=None) -> list[dict]:
    """Bucket closed-day revenue by engine week. Never treat a partial week as complete.

    The current week is drawn as a dashed 'Week so far (N days)' point, where N is
    the number of closed days already in that engine week. A week is complete only
    once its Sunday is in the history (the engine week ends on Sunday).
    """
    length = _week_length()
    buckets: dict[int, dict] = {}
    for item in history or []:
        try:
            day = int(item.day or 0)
        except (TypeError, ValueError):
            continue
        if day <= 0:
            continue
        wid = _week_id_for(day)
        rec = buckets.setdefault(wid, {"value": 0.0, "days": set(), "last_day": day})
        rec["value"] += float(getattr(item, "revenue", 0) or 0)
        rec["days"].add(day)
        rec["last_day"] = max(rec["last_day"], day)

    current_day = 0
    if state is not None:
        try:
            current_day = int(getattr(state, "day", 0) or 0)
        except (TypeError, ValueError):
            current_day = 0
    if not current_day and history:
        try:
            current_day = int(history[-1].day or 0)
        except (TypeError, ValueError):
            current_day = 0
    current_wid = _week_id_for(current_day) if current_day else None

    weekly = []
    for wid, rec in sorted(buckets.items()):
        closed = sorted(rec["days"])
        n = len(closed)
        complete = any(is_sunday(day) for day in closed) or n >= length
        # Only the open engine week can be partial; older buckets stay complete.
        partial = (not complete) and (current_wid is None or wid == current_wid)
        if partial:
            label = f"Week so far ({n} days)"
            tip = f"{money(int(round(rec['value'])))}  ·  {n} days elapsed"
        else:
            label = f"Week {wid + 1}"
            tip = f"{label}  ·  {money(int(round(rec['value'])))}"
        weekly.append({
            "label": label,
            "value": rec["value"],
            "partial": partial,
            "days": n,
            "week": wid + 1,
            "tip": tip,
        })

    # Daily points until at least one engine week has closed — a single partial
    # week should not be drawn as if it were a full Week 1.
    if not any(not row["partial"] for row in weekly):
        daily = []
        for item in list(history or [])[-8:]:
            try:
                day = int(item.day or 0)
            except (TypeError, ValueError):
                continue
            if day <= 0:
                continue
            value = float(getattr(item, "revenue", 0) or 0)
            label = weekday_name(day)[:3]
            daily.append({
                "label": label,
                "value": value,
                "partial": False,
                "days": 1,
                "tip": f"{weekday_name(day)}  ·  {money(int(round(value)))}",
            })
        return daily
    return weekly[-8:]


def _economy_news_feed(state) -> tuple[list[dict], list[dict]]:
    """Guarded E2 news + active events. Failures become an empty feed."""
    try:
        from open_late.economy import economy_news, economy_snapshot
    except Exception:
        return [], []
    news, events = [], []
    try:
        news = list(economy_news(state, store_id=None, limit=10) or [])
    except Exception:
        news = []
    try:
        snap = economy_snapshot(state) or {}
        events = list(snap.get("events_active") or [])
    except Exception:
        events = []
    return news, events


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


def _news_place(item: dict, events: list[dict] | None = None) -> str:
    stores = list(item.get("store_ids") or [])
    if stores:
        return stores[0].replace("_", " ").title()
    department = item.get("department")
    if department:
        return str(department).replace("_", " ").title()
    events = events or []
    # Fall back to a matching active event's city or department.
    ids = set(item.get("factor_ids") or [])
    for event in events:
        if event.get("factor_id") in ids or (item.get("id") and event.get("id") == item.get("id")):
            if event.get("city_id"):
                return str(event["city_id"]).replace("_", " ").title()
            if event.get("department"):
                return str(event["department"]).replace("_", " ").title()
            if event.get("store_ids"):
                return str(event["store_ids"][0]).replace("_", " ").title()
    return "National"


class _TickerEdgeFade(QWidget):
    """Soft left/right mask so a mid-cut headline fades into the dark card instead of clipping hard."""

    def __init__(self, color: str, parent=None, *, fade: int = 32):
        super().__init__(parent)
        self._color = QColor(color)
        self._fade = int(fade)
        self.setObjectName("tickerFade")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width, height = self.width(), max(1, self.height())
        if width <= 2 or height <= 0:
            painter.end()
            return
        fade = min(self._fade, max(8, width // 5))
        right_w = min(width, fade + 10)  # slightly wider on the right, where the hard cut was worst
        edge = QColor(self._color)
        edge.setAlpha(255)
        clear = QColor(self._color)
        clear.setAlpha(0)
        left = QLinearGradient(0, 0, fade, 0)
        left.setColorAt(0.0, edge)
        left.setColorAt(1.0, clear)
        painter.fillRect(0, 0, fade, height, left)
        right = QLinearGradient(width - right_w, 0, width, 0)
        right.setColorAt(0.0, clear)
        right.setColorAt(1.0, edge)
        painter.fillRect(width - right_w, 0, right_w, height, right)
        painter.end()


class NewsTicker(QWidget):
    """Slow horizontal marquee for long E2 headlines. Timer runs only while visible and overflowing."""

    def __init__(self, items: list[dict], parent=None):
        super().__init__(parent)
        self.setObjectName("newsTicker")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(22)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")
        self._offset = 0.0
        self._loop = 0
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._step)
        self._inner = QWidget(self)
        self._inner.setStyleSheet("background: transparent;")
        row = QHBoxLayout(self._inner)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(28)
        self._labels: list[QLabel] = []
        # Draw the sequence twice so a looping marquee has no seam.
        sequence = list(items or [])
        if sequence:
            sequence = sequence + sequence
        for item in sequence:
            text = str(item.get("text") or "")
            lab = QLabel(text)
            lab.setObjectName("newsItem")
            lab.setFont(ui_font(11))
            color = item.get("color") or DASH_MUTED
            lab.setStyleSheet(f"color: {color}; background: transparent;")
            lab.setToolTip(str(item.get("tip") or text))
            lab.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            row.addWidget(lab)
            self._labels.append(lab)
        self._inner.adjustSize()
        self.setToolTip(self.full_text())
        self._fade = _TickerEdgeFade(DASH_CARD, self)
        self._fade.raise_()

    def sizeHint(self) -> QSize:
        return QSize(200, 22)

    def minimumSizeHint(self) -> QSize:
        return QSize(40, 22)

    def full_text(self) -> str:
        # Unique items only (the inner row is duplicated for a seamless loop).
        unique = self._labels[: len(self._labels) // 2] if len(self._labels) >= 2 else self._labels
        return "  ·  ".join(lab.text() for lab in unique)

    def is_scrolling(self) -> bool:
        return self._timer.isActive()

    def _loop_width(self) -> int:
        # Two copies of the items; the loop distance is one copy plus the joining gap.
        spacing = 0
        layout = self._inner.layout()
        if layout is not None:
            spacing = layout.spacing()
        if len(self._labels) < 2:
            return max(1, self._inner.sizeHint().width())
        return max(1, (self._inner.sizeHint().width() + spacing) // 2)

    def _place_fade(self) -> None:
        fade = getattr(self, "_fade", None)
        if fade is None:
            return
        fade.setGeometry(self.rect())
        fade.raise_()
        fade.show()

    def _edge_inset(self) -> int:
        """Keep the first glyph out of the left mask when the row overflows."""
        fade = getattr(self, "_fade", None)
        if fade is None or self._loop_width() <= self.width() + 2:
            return 0
        return int(getattr(fade, "_fade", 32) or 32)

    def _place_inner(self) -> None:
        self._inner.move(self._edge_inset() - int(self._offset), 0)

    def _relayout(self) -> None:
        hint = self._inner.sizeHint()
        self._inner.resize(max(hint.width(), self.width()), self.height())
        if not self.isVisible() or self._loop_width() <= self.width() + 2:
            self._timer.stop()
            self._offset = 0.0
            self._place_inner()
            self._place_fade()
            return
        self._place_inner()
        if not self._timer.isActive():
            self._timer.start()
        self._place_fade()

    def _step(self) -> None:
        if not self.isVisible():
            self._timer.stop()
            return
        loop = self._loop_width()
        if loop <= self.width() + 2:
            self._timer.stop()
            self._offset = 0.0
            self._inner.move(0, 0)
            return
        self._offset += 0.9
        if self._offset >= loop:
            self._offset -= loop
        self._place_inner()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._relayout()

    def hideEvent(self, event) -> None:
        self._timer.stop()
        super().hideEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._relayout()

    def closeEvent(self, event) -> None:
        self._timer.stop()
        super().closeEvent(event)


class KpiIcon(QWidget):
    """QPainter KPI glyph: wallet, bars, or pie, in a glowing rounded tile."""

    def __init__(self, kind: str, color: str, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.color = QColor(color)
        self.setObjectName("kpiIcon")
        self.setFixedSize(36, 36)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        glow = QColor(self.color)
        glow.setAlpha(50)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawRoundedRect(1, 1, 34, 34, 8, 8)
        painter.setBrush(QColor(14, 28, 58, 220))
        painter.setPen(QPen(self.color, 1.2))
        painter.drawRoundedRect(3, 3, 30, 30, 7, 7)
        painter.setPen(QPen(self.color, 1.7))
        painter.setBrush(self.color)
        kind = self.kind
        if kind == "wallet":
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(9, 13, 18, 13, 3, 3)
            painter.drawLine(9, 16, 27, 16)
            painter.setBrush(self.color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(20, 17, 5, 5)
            painter.setPen(QPen(self.color, 1.6))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(12, 8, 12, 10, 0, 180 * 16)
        elif kind == "bars":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(9, 20, 5, 8, 1, 1)
            painter.drawRoundedRect(16, 14, 5, 14, 1, 1)
            painter.drawRoundedRect(23, 10, 5, 18, 1, 1)
        else:  # pie
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self.color)
            painter.drawEllipse(9, 9, 18, 18)
            painter.setBrush(QColor("#0B1730"))
            painter.drawPie(9, 9, 18, 18, 40 * 16, 95 * 16)
            # thin ring so the slice reads as a pie, not a blob
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(self.color, 1.5))
            painter.drawEllipse(9, 9, 18, 18)
        painter.end()


class LineChart(QWidget):

    def __init__(self, title: str, points: list, parent=None, dark: bool = False):
        super().__init__(parent)
        self.title = title
        self.points = points
        self.dark = dark
        self._hits: list[tuple[QRect, str]] = []
        self._axis_ticks: list[tuple[float, str]] = []
        self._axis_ceiling = 0
        self.setMinimumHeight(170)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setObjectName("lineChart")
        self.setMouseTracking(True)

    def _rows(self) -> list[dict]:
        return _normalize_trend_points(self.points)

    def mouseMoveEvent(self, event) -> None:
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        tip = ""
        for rect, text in self._hits:
            if rect.contains(pos):
                tip = text
                break
        if tip != self.toolTip():
            self.setToolTip(tip)
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        if self.toolTip():
            self.setToolTip("")
        super().leaveEvent(event)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setClipRect(self.rect())
        ink = QColor(DASH_TEXT if self.dark else HQ_TITLE)
        muted = QColor(DASH_MUTED if self.dark else HQ_MUTED)
        faint = QColor(DASH_FAINT if self.dark else HQ_FAINT)
        grid = QColor("#1A2E55" if self.dark else "#E4E7EC")
        line = QColor("#C084FC" if self.dark else RR_BLUE)
        rows = self._rows()
        if self.title:
            painter.setPen(ink)
            painter.setFont(ui_font(13, QFont.Weight.DemiBold))
            painter.drawText(8, 16, self.title)
            top = 28
        else:
            top = 16
        width, height = self.width(), self.height()
        # Extra baseline room so "Week so far (N days)" sits under the line, not on the last dot.
        axis_h = 36 if any(row.get("partial") for row in rows) else 22
        self._hits = []
        self._axis_ticks = []
        self._axis_ceiling = 0
        if not rows:
            left, right, bottom = 10, width - 10, height - axis_h
            painter.setPen(QPen(grid, 1))
            for step in range(4):
                y = top + (bottom - top) * step / 3
                painter.drawLine(left, int(y), right, int(y))
            painter.setPen(muted)
            painter.setFont(ui_font(12))
            painter.drawText(QRect(left, top, right - left, bottom - top), Qt.AlignmentFlag.AlignCenter, "The line starts when a day closes.")
            painter.end()
            return
        vals = [row["value"] for row in rows]
        peak = max(vals)
        floor = min(vals)
        if floor >= 0:
            ceiling, ticks = money_axis_ticks(peak)
            lo, hi = 0.0, float(ceiling)
        else:
            ceiling, pos_ticks = money_axis_ticks(max(abs(floor), abs(peak)))
            lo, hi = -float(ceiling), float(ceiling)
            ticks = [(-value, money_compact(-value) if value else "$0") for value, _label in reversed(pos_ticks[1:])]
            ticks.extend(pos_ticks)
        self._axis_ceiling = hi
        self._axis_ticks = ticks
        painter.setFont(ui_font(9))
        tick_w = max((painter.fontMetrics().horizontalAdvance(label) for _value, label in ticks), default=24)
        left = max(44, tick_w + 10)
        right, bottom = width - 10, height - axis_h
        span = (hi - lo) or 1.0
        for value, label in ticks:
            y = bottom - (bottom - top) * ((value - lo) / span)
            painter.setPen(QPen(grid, 1))
            painter.drawLine(left, int(y), right, int(y))
            painter.setPen(muted)
            painter.setFont(ui_font(9))
            painter.drawText(
                QRect(2, int(y) - 8, left - 6, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                label,
            )
        coords = []
        for index, row in enumerate(rows):
            x = left + (right - left) * (index / max(1, len(rows) - 1))
            y = bottom - (bottom - top) * ((row["value"] - lo) / span)
            coords.append((x, y, row))
        last_solid = len(coords) - 1
        if coords[-1][2].get("partial") and len(coords) >= 2:
            last_solid = len(coords) - 2
        solid = coords[: last_solid + 1]
        fill = QPainterPath()
        path = QPainterPath()
        fill.moveTo(solid[0][0], bottom)
        fill.lineTo(solid[0][0], solid[0][1])
        path.moveTo(solid[0][0], solid[0][1])
        for x, y, _row in solid[1:]:
            path.lineTo(x, y)
            fill.lineTo(x, y)
        fill.lineTo(solid[-1][0], bottom)
        fill.closeSubpath()
        if self.dark:
            gradient = QLinearGradient(0, top, 0, bottom)
            top_c = QColor("#C084FC")
            top_c.setAlpha(150)
            mid_c = QColor("#7C5CFF")
            mid_c.setAlpha(70)
            bot_c = QColor("#7C5CFF")
            bot_c.setAlpha(8)
            gradient.setColorAt(0.0, top_c)
            gradient.setColorAt(0.55, mid_c)
            gradient.setColorAt(1.0, bot_c)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(gradient)
            painter.drawPath(fill)
        else:
            wash = QColor(RR_BLUE)
            wash.setAlpha(40)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(wash)
            painter.drawPath(fill)
        glow = QColor(line)
        glow.setAlpha(90)
        painter.setPen(QPen(glow, 6))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        painter.setPen(QPen(line, 2.4))
        painter.drawPath(path)
        if last_solid < len(coords) - 1:
            x0, y0, _ = coords[last_solid]
            x1, y1, _ = coords[-1]
            dash = QPainterPath()
            dash.moveTo(x0, y0)
            dash.lineTo(x1, y1)
            ghost = QColor(line)
            ghost.setAlpha(110)
            pen = QPen(ghost, 2.2, Qt.PenStyle.DashLine)
            pen.setDashPattern([5, 4])
            painter.setPen(pen)
            painter.drawPath(dash)
        painter.setFont(ui_font(9, QFont.Weight.DemiBold))
        slots: list[tuple[int, int, int, int, str]] = []
        for x, y, row in coords:
            partial = bool(row.get("partial"))
            painter.setPen(QPen(QColor("#FFFFFF"), 1.2))
            painter.setBrush(Qt.BrushStyle.NoBrush if partial else line)
            if partial:
                painter.setBrush(QColor(DASH_CARD))
            painter.drawEllipse(int(x) - 4, int(y) - 4, 8, 8)
            text = _short_money(row["value"])
            tw = painter.fontMetrics().horizontalAdvance(text)
            tx = int(x - tw / 2)
            tx = max(left, min(right - tw, tx))
            ty = int(y) - 8
            # Keep the compact amount inside the plot so million-scale points do not clip the title.
            ty = max(top + 10, min(bottom - 2, ty))
            slots.append((tx, ty, tw, 12, text))
            self._hits.append((QRect(int(x) - 16, int(y) - 22, 36, 36), str(row.get("tip") or "")))

        def _overlaps(a, b, pad: int = 3) -> bool:
            ax, ay, aw, ah = a[0], a[1] - a[3], a[2], a[3]
            bx, by, bw, bh = b[0], b[1] - b[3], b[2], b[3]
            return not (ax + aw + pad < bx or bx + bw + pad < ax or ay + ah + pad < by or by + bh + pad < ay)

        def _pack(items: list) -> list:
            # Prefer the last and first values; drop any label that would collide.
            if not items:
                return []
            order = [len(items) - 1]
            if len(items) > 1:
                order.append(0)
            order.extend(range(len(items) - 2, 0, -1))
            kept: list = []
            seen: set[int] = set()
            for index in order:
                if index in seen:
                    continue
                seen.add(index)
                item = items[index]
                if any(_overlaps(item, other) for other in kept):
                    continue
                kept.append(item)
            return kept

        painter.setPen(ink)
        painter.setFont(ui_font(9, QFont.Weight.DemiBold))
        for tx, ty, _tw, _th, text in _pack(slots):
            painter.drawText(tx, ty, text)
        painter.setPen(faint)
        painter.setFont(ui_font(9))
        # Week / day labels along the axis; skip a middle label if they would collide.
        n = len(coords)
        show = set(range(n))
        if n > 6:
            show = set(range(0, n, 2)) | {0, n - 1}
        axis_slots: list[tuple] = []
        for index, (x, _y, row) in enumerate(coords):
            if index not in show:
                continue
            label = str(row.get("label") or "")
            # Partial week: two-line axis label so "Week so far (N days)" stays readable.
            if row.get("partial") and label.startswith("Week so far") and "(" in label:
                main, rest = "Week so far", label[label.find("("):]
                box_w = 116
                tx = int(x - box_w / 2)
                tx = max(2, min(width - box_w - 2, tx))
                axis_slots.append((tx, height - 15, box_w, 26, (main, rest), True))
            else:
                tw = painter.fontMetrics().horizontalAdvance(label)
                tx = int(x - tw / 2)
                tx = max(2, min(width - tw - 2, tx))
                axis_slots.append((tx, height - 6, tw, 12, (label,), False))
        for tx, ty, tw, th, parts, two_line in _pack(axis_slots):
            if two_line:
                painter.drawText(QRect(tx, height - 28, tw, 13), Qt.AlignmentFlag.AlignHCenter, parts[0])
                painter.drawText(QRect(tx, height - 15, tw, 13), Qt.AlignmentFlag.AlignHCenter, parts[1])
            else:
                painter.drawText(tx, ty, parts[0])
        painter.end()


class BarChart(QWidget):
    def __init__(self, title: str, rows: list[tuple[str, float, bool]], parent=None):
        super().__init__(parent)
        self.title = title
        self.rows = rows
        self.setMinimumHeight(max(140, 24 + 22 * max(1, len(rows))))
        self.setObjectName("barChart")

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor(TEXT))
        painter.setFont(ui_font(13, QFont.Weight.DemiBold))
        painter.drawText(8, 16, self.title)
        width = self.width()
        top = 26
        if not self.rows:
            painter.setPen(QColor(HQ_MUTED))
            painter.setFont(ui_font(12))
            painter.drawText(QRect(8, top, width - 16, 40), Qt.AlignmentFlag.AlignLeft, "No doors on the lease yet.")
            painter.end()
            return
        peak = max((abs(value) for _name, value, _muted in self.rows), default=1.0) or 1.0
        row_h = max(18, (self.height() - top - 8) / max(1, len(self.rows)))
        for index, (name, value, muted) in enumerate(self.rows):
            y = top + index * row_h
            painter.setPen(QColor(HQ_MUTED if muted else TEXT))
            painter.setFont(ui_font(11))
            painter.drawText(QRect(8, int(y), 90, int(row_h)), Qt.AlignmentFlag.AlignVCenter, name)
            bar_left = 102
            bar_w = max(2, int((width - bar_left - 92) * (abs(value) / peak)))
            if muted:
                color = QColor("#9AA3B2")
            elif value < 0:
                color = QColor(DOWN)
            elif index == 0:
                color = QColor(RR_YELLOW)
            else:
                color = QColor(RR_BLUE)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(bar_left, int(y + 4), bar_w, int(row_h - 8), 3, 3)
            painter.setPen(QColor(TEXT))
            painter.drawText(QRect(bar_left + bar_w + 8, int(y), 84, int(row_h)), Qt.AlignmentFlag.AlignVCenter, money_compact(int(value)))
        painter.end()


class MixLegend(QWidget):
    def __init__(self, title: str, slices: list[tuple[str, float, str]], parent=None):
        super().__init__(parent)
        self.title = title
        self.slices = slices
        self.setMinimumHeight(140)
        self.setObjectName("mixLegend")

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor(TEXT))
        painter.setFont(ui_font(13, QFont.Weight.DemiBold))
        painter.drawText(8, 16, self.title)
        total = sum(value for _n, value, _c in self.slices) or 1.0
        y = 28
        if not self.slices:
            painter.setPen(QColor(HQ_MUTED))
            painter.setFont(ui_font(12))
            painter.drawText(8, 48, "The mix starts when a day closes.")
            painter.end()
            return
        track = QRect(12, y, self.width() - 24, 14)
        painter.setPen(Qt.PenStyle.NoPen)
        x = track.x()
        for _name, value, color in self.slices:
            w = max(2, int(track.width() * (value / total)))
            painter.setBrush(QColor(color))
            painter.drawRect(x, track.y(), w, track.height())
            x += w
        y = track.bottom() + 10
        painter.setFont(ui_font(11))
        for name, value, color in self.slices:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(12, y + 3, 10, 10, 2, 2)
            painter.setPen(QColor(TEXT))
            pct = 100 * value / total
            painter.drawText(QRect(28, y, self.width() - 36, 16), Qt.AlignmentFlag.AlignVCenter, f"{name}  {pct:.0f}%")
            y += 18
        painter.end()



class Sparkline(QWidget):
    def __init__(self, values: list[float], color: str = "#3D7EFF", glow: bool = False, parent=None):
        super().__init__(parent)
        self.values = values
        self.color = QColor(color)
        self.glow = glow
        self.setFixedHeight(28)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setObjectName("sparkline")

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        vals = self.values or [0.0]
        width, height = max(self.width(), 2), max(self.height(), 2)
        lo, hi = min(vals), max(vals)
        span = (hi - lo) or 1.0
        path = QPainterPath()
        for index, value in enumerate(vals):
            x = 2 + (width - 4) * (index / max(1, len(vals) - 1))
            y = height - 4 - (height - 8) * ((value - lo) / span)
            if index == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        if self.glow:
            glow = QPen(self.color)
            gc = QColor(self.color)
            gc.setAlpha(80)
            painter.setPen(QPen(gc, 5))
            painter.drawPath(path)
        painter.setPen(QPen(self.color, 1.8))
        painter.drawPath(path)
        painter.end()


def _delta_text(current, previous) -> tuple[str, str]:
    if previous is None:
        return "First readings", "quiet"
    try:
        previous = float(previous)
        current = float(current)
    except (TypeError, ValueError):
        return "First readings", "quiet"
    if previous == 0:
        return "First readings", "quiet"
    change = (current - previous) / abs(previous)
    arrow = "↑" if change >= 0 else "↓"
    return f"{arrow}  {abs(change) * 100:.1f}% vs prior", "up" if change >= 0 else "down"



def _economy_mod():
    try:
        from open_late import economy as module
        return module
    except Exception:
        return None


def _economy_spark_series(state, factor_ids: list[int]) -> dict[str, list[float]]:
    module = _economy_mod()
    func = getattr(module, "economy_sparklines", None) if module is not None else None
    if func is None:
        return {}
    try:
        payload = func(state, factor_ids, weeks=12)
    except Exception:
        return {}
    series = payload.get("series") or {}
    out = {}
    for key, values in series.items():
        if values and len(values) >= 2:
            out[str(key)] = [float(v) for v in values]
    return out


def _economy_gauges(state) -> list[dict]:
    module = _economy_mod()
    func = getattr(module, "economy_snapshot", None) if module is not None else None
    difficulty = getattr(module, "economy_difficulty", None) if module is not None else None
    if func is None:
        return []
    try:
        if difficulty is not None and difficulty(state) == "off":
            return []
        snap = func(state) or {}
    except Exception:
        return []
    return list(snap.get("gauges") or [])


class DashboardPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dashboardPage")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(True)
        pal = self.palette()
        pal.setColor(self.backgroundRole(), QColor("#EEF1F4"))
        pal.setColor(QPalette.ColorRole.Window, QColor("#EEF1F4"))
        pal.setColor(QPalette.ColorRole.Base, QColor("#EEF1F4"))
        self.setPalette(pal)
        self.setStyleSheet(f"QWidget#dashboardPage {{ background: {FRAME}; color: #F4F7FB; }}")
        self.host = None
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(0, 0, 0, 0)
        self.box.setSpacing(6)

    def _clear(self) -> None:
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

    def rebuild(self) -> None:
        self._clear()
        host = self.host
        state = host.state if host is not None else None
        if state is None:
            return
        self.show_desk()

    def show_desk(self) -> None:
        """Company Overview: the figures, the doors, and the morning notes."""
        host = self.host
        state = host.state if host is not None else None
        if state is None:
            return
        self._clear()
        from open_late.ui.overview import CompanyOverview

        self.setStyleSheet(f"QWidget#dashboardPage {{ background: {FRAME}; color: #F4F7FB; }}")
        board = CompanyOverview()
        self.box.addWidget(board, stretch=1)
        board.load(state)
        if host is not None:
            board.open_page.connect(host._open_app)
            board.open_store.connect(self._open_store)

    def _open_store(self, store_id: str) -> None:
        """A store row on the overview opens that door."""
        host = self.host
        if host is None or getattr(host, "shell", None) is None:
            return
        host.shell.stores.selected = store_id
        host._open_app("stores")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_map_height()

    def _apply_map_height(self) -> None:
        """Give the regional map a large visible slice without pushing other cards off the fold."""
        store_map = getattr(self, "map", None)
        if store_map is None:
            return
        viewport = max(1, self.height())
        shell = getattr(getattr(self, "host", None), "shell", None)
        if shell is not None:
            viewport = min(viewport, max(1, shell.work_area().height()))
        # Title, KPI (128), ticker strip, paddings and gaps above the mid row.
        above = 244 if viewport >= 680 else 236
        map_chrome = 56  # card title + padding around the map widget
        low = 154 if viewport >= 680 else 136
        bottom = 8
        slack = 20  # title/ticker/card chrome tends to run a little over the estimate
        budget = viewport - above - map_chrome - low - bottom - slack
        floor = 240 if viewport >= 680 else 190
        if budget >= floor:
            target = budget
        else:
            target = max(180, budget)
        target = int(min(max(target, 160), 400))
        vis = store_map.visibleRegion().boundingRect()
        if vis.isValid() and vis.height() >= 80 and store_map.height() > vis.height() + 2:
            target = min(target, vis.height())
        if store_map.minimumHeight() != target:
            store_map.setMinimumHeight(target)

    def _dash_css(self) -> str:
        return f"""
            QWidget#dashboardPage {{
                background: {DASH_BG};
                background-color: {DASH_BG};
                color: {DASH_TEXT};
            }}
            QLabel#pageTitle {{ color: {DASH_TEXT}; background: transparent; }}
            QLabel#pageDeck, QLabel#pnlNote {{ color: {DASH_MUTED}; background: transparent; }}
            QLabel#figureCaption {{
                color: {DASH_FAINT};
                letter-spacing: 1px;
                background: transparent;
            }}
            QLabel#kpiValue {{
                color: {DASH_TEXT};
                background: transparent;
            }}
            QFrame#card, QFrame#kpiTake, QFrame#kpiContribution, QFrame#kpiDrawer,
            QFrame#kpiSunday, QFrame#marketingCard, QFrame#planoPreview,
            QFrame#revenueCard, QFrame#perfCard, QFrame#mapCard, QFrame#todoQueue,
            QFrame#economyStrip, QFrame#economyNews {{
                background: {DASH_CARD};
                border: 1px solid {DASH_LINE};
                border-radius: 12px;
            }}
            QWidget#storeMap {{
                background: {DASH_BG};
                border: none;
            }}
            QPushButton#quiet {{
                color: {DASH_MUTED};
                background: transparent;
                border: none;
            }}
            QPushButton#primary, QPushButton#launchCampaign {{
                background: {DASH_ACCENT};
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 8px 14px;
                font-weight: 700;
            }}
        """


    def _economy_strip(self, gauges: list[dict]) -> QFrame:
        frame, layout = _card()
        frame.setObjectName("economyStrip")
        row = QHBoxLayout()
        row.setSpacing(16)
        row.addWidget(_label("ECONOMY", 11, QFont.Weight.DemiBold, DASH_FAINT))
        for gauge in gauges[:5]:
            value = int(gauge.get("value") or 100)
            delta = int(gauge.get("delta") or 0)
            name = str(gauge.get("name") or "")
            color = UP if delta > 0 else DOWN if delta < 0 else DASH_MUTED
            sign = "↑" if delta > 0 else "↓" if delta < 0 else "·"
            col = QVBoxLayout()
            col.setSpacing(0)
            col.addWidget(_label(name, 10, color=DASH_FAINT))
            col.addWidget(_label(f"{value}  {sign} {abs(delta)}", 13, QFont.Weight.DemiBold, color))
            row.addLayout(col)
        row.addStretch(1)
        layout.addLayout(row)
        return frame

    def _todo_card(self, host, state) -> QFrame:
        frame, layout = _card()
        frame.setObjectName("todoQueue")
        layout.addWidget(_label("TO DO", 11, QFont.Weight.DemiBold, DASH_FAINT))
        layout.addWidget(_label("The desk is clear.", 13, color=DASH_MUTED))
        return frame

    def _map_card(self, state, ids, chain) -> QFrame:
        frame, layout = _card()
        frame.setObjectName("mapCard")
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        head = QHBoxLayout()
        head.setSpacing(8)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.addWidget(_label("Regional store map", 13, QFont.Weight.DemiBold, DASH_TEXT))
        titles.addWidget(_label("United States  ·  last 8 wks performance", 11, color=DASH_MUTED))
        head.addLayout(titles, stretch=1)
        legend = QHBoxLayout()
        legend.setSpacing(10)
        legend.addWidget(_label("STORE PERFORMANCE", 10, QFont.Weight.DemiBold, DASH_FAINT))
        for color, name in ((DASH_PIN_HIGH, "High performer"), (DASH_PIN_MID, "On target"), (DASH_PIN_LOW, "Below target")):
            swatch = QLabel("●  " + name)
            swatch.setStyleSheet(f"color: {color}; background: transparent;")
            swatch.setFont(ui_font(11))
            legend.addWidget(swatch)
        head.addLayout(legend)
        layout.addLayout(head)
        self.map = StoreMap(theme="dark")
        self.map.setObjectName("storeMap")
        self.map.setMinimumHeight(240)
        self.map.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        selected = set(ids)
        pins = []
        contributions = []
        for store_id, (label, lon, lat, ox, oy) in CITIES.items():
            door = door_by_id(state, store_id)
            if door is None:
                pins.append({
                    "id": store_id, "label": label, "lon": lon, "lat": lat,
                    "owned": False, "offset": (ox, oy), "tip": f"{label} · not leased",
                })
                continue
            sales = recorded_sales(state, door)
            contrib, share = contribution_share(state, door)
            contributions.append((store_id, contrib))
            pins.append({
                "id": door.id, "label": door.city, "lon": lon, "lat": lat,
                "owned": True, "open": door.status == "open",
                "selected": door.id in selected and len(selected) == 1,
                "offset": (ox, oy),
                "sales_label": money_compact(sales),
                "contrib_label": f"Contrib. {share * 100:.1f}%",
                "contrib": contrib,
                "tip": f"{door.city} · {money(sales)} · Store P&L {money(contrib)}",
            })
        owned_vals = [row[1] for row in contributions]
        if owned_vals:
            hi = max(owned_vals)
            lo = min(owned_vals)
            for pin in pins:
                if not pin.get("owned"):
                    continue
                value = pin.get("contrib") or 0
                if len(owned_vals) == 1:
                    pin["rank"] = "mid"
                elif hi != lo and value >= lo + 0.75 * (hi - lo):
                    pin["rank"] = "high"
                elif hi != lo and value <= lo + 0.25 * (hi - lo):
                    pin["rank"] = "low"
                else:
                    pin["rank"] = "mid"
                pin["size"] = {"high": 11, "mid": 8, "low": 6}.get(pin["rank"], 8)
        self.map.set_pins(pins)
        layout.addWidget(self.map, stretch=1)
        return frame

    def _marketing_card(self, state) -> QFrame:
        frame, layout = _card()
        frame.setObjectName("marketingCard")
        layout.addWidget(_label("Marketing campaign spotlight", 15, QFont.Weight.DemiBold, DASH_TEXT))
        campaign = state.campaign
        if campaign is None:
            art = QFrame()
            art.setObjectName("campaignArt")
            art.setMinimumHeight(110)
            art.setStyleSheet(
                "QFrame#campaignArt { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
                " stop:0 #3A1D6E, stop:1 #12365C); border-radius: 10px; }"
            )
            art_box = QVBoxLayout(art)
            art_box.addStretch(1)
            art_box.addWidget(_label("No campaign is on the air.", 16, QFont.Weight.Bold, DASH_TEXT, wrap=True))
            art_box.addWidget(_label("Launch a local ad, a social post, or an email and this card will follow it.", 12, color=DASH_MUTED, wrap=True))
            art_box.addStretch(1)
            layout.addWidget(art, stretch=1)
            btn = QPushButton("Launch a campaign")
            btn.setObjectName("launchCampaign")
            if self.host is not None:
                btn.clicked.connect(lambda: self.host._open_app("marketing"))
            layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignLeft)
            return frame
        title = f"{campaign.kind.replace('_', ' ').title()}  ·  {campaign.tone}"
        layout.addWidget(_label(title, 20, QFont.Weight.Bold, DASH_TEXT, wrap=True))
        layout.addWidget(_label(
            f"{campaign.category.replace('_', ' ').title()}  ·  {campaign.days_left} days left",
            13, color=DASH_MUTED, wrap=True,
        ))
        layout.addWidget(_label(f"Traffic lift  {campaign.traffic_mult:.2f}×", 13, color=DASH_TEXT))
        layout.addStretch(1)
        btn = QPushButton("View campaign details")
        btn.setObjectName("primary")
        if self.host is not None:
            btn.clicked.connect(lambda: self.host._open_app("marketing"))
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignLeft)
        return frame

    def _status_chip(self, text: str, color: str) -> QLabel:
        lab = QLabel(text)
        lab.setObjectName("statusChip")
        lab.setFont(ui_font(10, QFont.Weight.DemiBold))
        lab.setStyleSheet(
            f"color: {color}; background: {color}22; border: 1px solid {color}66;"
            " border-radius: 8px; padding: 1px 8px;"
        )
        lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return lab

    def _perf_card(self, state, ids) -> QFrame:
        frame, layout = _card()
        frame.setObjectName("perfCard")
        layout.setContentsMargins(12, 10, 12, 8)
        layout.setSpacing(4)
        head = QHBoxLayout()
        head.addWidget(_label("Store performance overview", 13, QFont.Weight.DemiBold, DASH_TEXT))
        head.addStretch(1)
        link = QPushButton("View all stores")
        link.setObjectName("quiet")
        if self.host is not None:
            link.clicked.connect(lambda: self.host._open_app("stores"))
        head.addWidget(link)
        layout.addLayout(head)
        header = QHBoxLayout()
        header.setSpacing(6)
        for cap, stretch in (
            ("STORE", 3),
            ("REGION", 2),
            ("SALES", 2),
            ("SHARE OF CHAIN", 3),
            ("MARGIN", 1),
            ("POS", 2),
            ("STATUS", 2),
        ):
            cap_lab = _label(cap, 9, QFont.Weight.DemiBold, DASH_FAINT, "figureCaption")
            cap_lab.setWordWrap(True)
            header.addWidget(cap_lab, stretch=stretch)
        layout.addLayout(header)
        doors = [door for door in state.doors if door.id in ids] or list(state.doors)
        if not doors:
            layout.addWidget(_label(state.shop_name, 13, color=DASH_TEXT))
        # Rank doors the same way the map does, by last-8-weeks contribution.
        ranks = {}
        contribs = []
        for door in doors:
            contrib, _share = contribution_share(state, door)
            contribs.append((door.id, contrib))
        values = [row[1] for row in contribs]
        if values:
            hi, lo = max(values), min(values)
            for store_id, value in contribs:
                if len(values) == 1:
                    ranks[store_id] = "mid"
                elif hi != lo and value >= lo + 0.75 * (hi - lo):
                    ranks[store_id] = "high"
                elif hi != lo and value <= lo + 0.25 * (hi - lo):
                    ranks[store_id] = "low"
                else:
                    ranks[store_id] = "mid"
        for door in doors:
            row = QHBoxLayout()
            row.setSpacing(6)
            sales = recorded_sales(state, door)
            contrib, share = contribution_share(state, door)
            pos = store_pos(state, door.id)
            rank = ranks.get(door.id, "mid")
            rank_label = {"high": "High performer", "mid": "On target", "low": "Below target"}[rank]
            rank_color = {"high": DASH_PIN_HIGH, "mid": DASH_PIN_MID, "low": DASH_PIN_LOW}[rank]
            cur = store_pnl(state, door.id, days=7) if hq_available() else {}
            both = store_pnl(state, door.id, days=14) if hq_available() else {}
            prior = _prior_split(cur, both) if cur and both else {}
            if not int(prior.get("sales") or 0) and hq_available():
                cur = store_pnl(state, door.id, days=1)
                prior = _prior_split(cur, store_pnl(state, door.id, days=2))
            sales_delta, sales_role = _delta_text(int(cur.get("sales") or sales), prior.get("sales") if prior else None)
            pnl_delta, pnl_role = _delta_text(int(cur.get("contribution") or contrib), prior.get("contribution") if prior else None)
            # Store name with a colored performance dot.
            name_row = QHBoxLayout()
            name_row.setSpacing(6)
            name_row.setContentsMargins(0, 0, 0, 0)
            pip = QLabel("●")
            pip.setObjectName("statusDot")
            pip.setStyleSheet(f"color: {rank_color}; background: transparent;")
            pip.setFont(ui_font(11))
            name_row.addWidget(pip)
            name_row.addWidget(_label(door.city, 12, QFont.Weight.DemiBold, DASH_TEXT), stretch=1)
            name_wrap = QWidget()
            name_wrap.setStyleSheet("background: transparent;")
            name_wrap.setLayout(name_row)
            row.addWidget(name_wrap, stretch=3)
            row.addWidget(_label(door.region, 11, color=DASH_MUTED), stretch=2)
            # Sales + up/down delta
            sales_col = QVBoxLayout()
            sales_col.setSpacing(0)
            sales_lab = _label(money_compact(sales), 12, QFont.Weight.DemiBold, DASH_TEXT)
            sales_lab.setToolTip(money(sales))
            sales_col.addWidget(sales_lab)
            sc = UP if sales_role == "up" else DOWN if sales_role == "down" else DASH_MUTED
            sales_col.addWidget(_label(sales_delta.replace(" vs prior", ""), 10, color=sc, name="deltaLabel"))
            sales_wrap = QWidget()
            sales_wrap.setStyleSheet("background: transparent;")
            sales_wrap.setLayout(sales_col)
            row.addWidget(sales_wrap, stretch=2)
            # Share of chain (store P&L dollars + share %) and the store's own net margin.
            pnl_col = QVBoxLayout()
            pnl_col.setSpacing(0)
            share_text = f"{money_compact(contrib)}  ({share * 100:.1f}%)" if hq_available() or contrib else "—"
            share_lab = _label(share_text, 12, QFont.Weight.DemiBold, DASH_TEXT, "shareLabel")
            share_lab.setWordWrap(True)
            if hq_available() or contrib:
                share_lab.setToolTip(f"{money(contrib)}  ·  {share * 100:.1f}% of chain")
            pnl_col.addWidget(share_lab)
            pc = UP if pnl_role == "up" else DOWN if pnl_role == "down" else DASH_MUTED
            pnl_col.addWidget(_label(pnl_delta.replace(" vs prior", ""), 10, color=pc, name="deltaLabel"))
            pnl_wrap = QWidget()
            pnl_wrap.setStyleSheet("background: transparent;")
            pnl_wrap.setLayout(pnl_col)
            row.addWidget(pnl_wrap, stretch=3)
            margin = _margin_pct(sales, contrib)
            if margin is None:
                margin_text = "—"
                margin_tip = "Net margin  ·  no sales"
            else:
                margin_text = f"{margin:.1f}%"
                margin_tip = f"Net margin  {margin:.1f}%  ·  Store P&L {money(contrib)}  /  sales {money(sales)}"
            margin_lab = _label(margin_text, 12, QFont.Weight.DemiBold, DASH_TEXT, "marginLabel")
            margin_lab.setToolTip(margin_tip)
            row.addWidget(margin_lab, stretch=1)
            pos_lab = _label(str(pos.get("name") or "Counter Ledger"), 11, color=DASH_MUTED)
            pos_lab.setWordWrap(True)
            row.addWidget(pos_lab, stretch=2)
            row.addWidget(self._status_chip(rank_label, rank_color), stretch=2)
            layout.addLayout(row)
        layout.addStretch(1)
        return frame

    def _economy_news_strip(self, state) -> QFrame:
        frame, layout = _card()
        frame.setObjectName("economyNews")
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(2)
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        news, events = _economy_news_feed(state)
        row = QHBoxLayout()
        row.setSpacing(14)
        row.addWidget(_label("ECONOMY NEWS", 10, QFont.Weight.DemiBold, DASH_FAINT, "figureCaption"))
        if not news and not events:
            empty = _label("No economy news on the wire.", 12, color=DASH_MUTED, name="newsEmpty")
            row.addWidget(empty, stretch=1)
            layout.addLayout(row)
            return frame
        items = list(news[:4])
        # Surface an active event if the news list is short.
        for event in events[:2]:
            if len(items) >= 4:
                break
            items.append({
                "outlet": "Desk brief",
                "headline": event.get("name") or "Active event",
                "store_ids": event.get("store_ids") or [],
                "department": event.get("department"),
                "city_id": event.get("city_id"),
                "severity": event.get("severity") or 0,
                "factor_ids": [event.get("factor_id")] if event.get("factor_id") else [],
            })
        bits = []
        for item in items:
            color = _severity_color(item.get("severity"))
            outlet = str(item.get("outlet") or "Wire")
            headline = str(item.get("headline") or "")
            place = _news_place(item, events)
            if item.get("city_id") and place == "National":
                place = str(item["city_id"]).replace("_", " ").title()
            text = f"{outlet}  ·  {headline}  ·  {place}"
            body = str(item.get("body") or "").strip()
            tip = text if not body else f"{text}\n\n{body}"
            bits.append({"text": text, "tip": tip, "color": color})
        ticker = NewsTicker(bits)
        row.addWidget(ticker, stretch=1)
        layout.addLayout(row)
        return frame

    def _planogram_preview(self, host, state) -> QFrame:
        frame, layout = _card()
        frame.setObjectName("planoPreview")
        head = QHBoxLayout()
        head.addWidget(_label("Planogram preview", 13, QFont.Weight.DemiBold, DASH_TEXT))
        head.addStretch(1)
        link = QPushButton("Open planogram editor")
        link.setObjectName("quiet")
        if host is not None:
            link.clicked.connect(lambda: host._open_app("planograms"))
        head.addWidget(link)
        layout.addLayout(head)
        from open_late.ui.hq_planogram import PlanogramPreview
        preview = PlanogramPreview()
        preview.setMinimumHeight(110)
        layout.addWidget(preview, stretch=1)
        return frame


class LeasePickerDialog(QDialog):
    """Pick a city and confirm before a lease is signed."""

    def __init__(self, markets, parent=None, preselect: str = "", state=None):
        super().__init__(parent)
        self.setObjectName("leasePicker")
        self.setWindowTitle("Sign a lease")
        self.setModal(True)
        self.setStyleSheet(
            f"""
            QDialog#leasePicker {{
                background: {HQ_CANVAS};
                color: {HQ_TITLE};
            }}
            QListWidget#leaseCityList {{
                background: {HQ_CARD};
                color: {HQ_TITLE};
                border: 1px solid {HQ_LINE};
                border-radius: 8px;
                padding: 4px;
            }}
            QListWidget#leaseCityList::item:selected {{
                background: {RR_BLUE};
                color: #FFFFFF;
            }}
            QPushButton#leaseConfirm {{
                background: {RR_BLUE};
                color: #FFFFFF;
                border: none;
                border-bottom: 2px solid {RR_YELLOW};
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 700;
            }}
            QPushButton#leaseCancel {{
                background: {HQ_CARD};
                color: {HQ_TITLE};
                border: 1px solid {HQ_LINE};
                border-radius: 8px;
                padding: 8px 16px;
            }}
            """
        )
        self._markets = {market.id: market for market in markets}
        self._state = state  # for the live opening cost (rival AI on)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(10)
        root.addWidget(_label("Choose a city", 16, QFont.Weight.DemiBold, HQ_TITLE))
        root.addWidget(_label("Nothing is signed until you confirm.", 12, color=HQ_MUTED, wrap=True))
        self.list = QListWidget()
        self.list.setObjectName("leaseCityList")
        for market in markets:
            item = QListWidgetItem(f"{market.city}, {market.state_name}")
            item.setData(Qt.ItemDataRole.UserRole, market.id)
            self.list.addItem(item)
            if market.id == preselect or (not preselect and self.list.count() == 1):
                self.list.setCurrentItem(item)
        self.list.currentItemChanged.connect(lambda *_: self._refresh_detail())
        root.addWidget(self.list)
        self.detail = _label("", 12, color=HQ_MUTED, wrap=True, name="leaseDetail")
        root.addWidget(self.detail)
        form = QGridLayout()
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(6)
        self.sqft = QSpinBox()
        self.sqft.setObjectName("leaseSqft")
        self.sqft.setRange(20_000, 300_000)
        self.sqft.setSingleStep(5_000)
        self.sqft.setValue(115_000)
        self.sqft.setSuffix(" sq ft")
        self.build_days = QSpinBox()
        self.build_days.setObjectName("leaseBuildDays")
        self.build_days.setRange(0, 120)
        self.build_days.setSuffix(" days")
        self.center = QSpinBox()
        self.center.setObjectName("leaseCenter")
        self.center.setRange(2, 30)
        self.center.setValue(6)
        self.gm = QSpinBox()
        self.gm.setObjectName("leaseGm")
        self.gm.setRange(2, 30)
        self.gm.setValue(7)
        self.layout_pick = QComboBox()
        self.layout_pick.setObjectName("leaseLayout")
        for template_id, label in (
            ("balanced", "Balanced"),
            ("fresh_first", "Fresh first"),
            ("value_grocery", "Value grocery"),
            ("gm_push", "GM push"),
            ("seasonal_push", "Seasonal push"),
        ):
            self.layout_pick.addItem(label, template_id)
        form.addWidget(_label("Square feet", 12, color=HQ_MUTED), 0, 0)
        form.addWidget(self.sqft, 0, 1)
        form.addWidget(_label("Build-out", 12, color=HQ_MUTED), 0, 2)
        form.addWidget(self.build_days, 0, 3)
        form.addWidget(_label("Center aisles", 12, color=HQ_MUTED), 1, 0)
        form.addWidget(self.center, 1, 1)
        form.addWidget(_label("GM aisles", 12, color=HQ_MUTED), 1, 2)
        form.addWidget(self.gm, 1, 3)
        form.addWidget(_label("Layout", 12, color=HQ_MUTED), 2, 0)
        form.addWidget(self.layout_pick, 2, 1, 1, 3)
        root.addLayout(form)
        self._shown_market = ""
        for box in (self.sqft, self.build_days, self.center, self.gm):
            box.valueChanged.connect(lambda *_: self._refresh_detail())
        self.layout_pick.currentIndexChanged.connect(lambda *_: self._refresh_detail())
        self.loan = QCheckBox("Finance 70% with a building loan")
        self.loan.setObjectName("leaseLoan")
        self.loan.setEnabled(False)
        self.loan.toggled.connect(lambda *_: self._refresh_detail())
        root.addWidget(self.loan)
        self.loan_note = _label("", 12, color=HQ_MUTED, wrap=True, name="leaseLoanNote")
        root.addWidget(self.loan_note)
        buttons = QDialogButtonBox()
        self.confirm = buttons.addButton("Sign this lease", QDialogButtonBox.ButtonRole.AcceptRole)
        self.confirm.setObjectName("leaseConfirm")
        cancel = buttons.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        cancel.setObjectName("leaseCancel")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self._refresh_detail()
        self.setMinimumSize(560, 560)
        self.resize(640, 640)

    def _loan_offer(self, market_id: str) -> dict:
        state = self._state
        if state is None or not market_id:
            return {"approved": False, "reason": ""}
        try:
            from open_late.rival_ai import player_store_loan_offer
        except ImportError:
            return {"approved": False, "reason": "No building loan in this build."}
        offer = player_store_loan_offer(state, market_id)
        from open_late.us_capitals import by_id as capital_by_id

        if capital_by_id(market_id) and not offer.get("approved"):
            offer = dict(offer)
            offer["reason"] = "This capital is paid from the drawer. The building loan covers the original city leases."
        return offer

    def _refresh_detail(self) -> None:
        market = self._markets.get(self.selected_market_id())
        if market is None:
            self.detail.setText("Select a city to read the opening cost and rent.")
            self.confirm.setEnabled(False)
            self.loan.setEnabled(False)
            self.loan_note.setText("")
            return
        self.confirm.setEnabled(True)
        if market.id != self._shown_market:
            self._shown_market = market.id
            self.build_days.blockSignals(True)
            self.build_days.setValue(int(market.build_days))
            self.build_days.blockSignals(False)
        scale = max(0.35, min(3.0, self.sqft.value() / 115_000))
        opening = int(round(shown_opening_cost(self._state, market) * scale))
        rent = int(round(market.rent_weekly * scale))
        from open_late.us_capitals import by_id as capital_by_id
        from open_late.us_capitals import demographic_line

        census = capital_by_id(market.id)
        census_line = ""
        if census is not None:
            census_line = f" {census.population:,} people. {demographic_line(census)}."
        if market.foot_traffic:
            census_line += (
                f" Usual draw {int(market.foot_traffic):,} before the week's card."
            )
        card_tip = ""
        if self._state is not None:
            from open_late.market_card import market_lines

            face, card_tip = market_lines(self._state, market.id)
            census_line += f" {face}"
        self.detail.setText(
            f"Opening {money_compact(opening)}. Rent {money(rent)} / week. "
            f"Build-out {self.build_days.value()} days. "
            f"{self.sqft.value():,} sq ft, {self.center.value()} center aisles, {self.gm.value()} GM aisles. "
            f"Truck {market.transit_days} days. "
            f"Leave at least {money(market.min_cash_after)} in the drawer.{census_line}"
        )
        self.detail.setToolTip(
            f"Opening {money(opening)}. Rent {money(rent)} / week. "
            f"{self.sqft.value():,} sq ft.{census_line} {card_tip}".strip()
        )
        offer = self._loan_offer(market.id)
        approved = bool(offer.get("approved"))
        self.loan.blockSignals(True)
        self.loan.setEnabled(approved)
        if not approved and self.loan.isChecked():
            self.loan.setChecked(False)
        self.loan.blockSignals(False)
        if approved and self.loan.isChecked():
            down = int(round(int(offer.get("equity") or 0) * scale))
            principal = int(round(int(offer.get("principal") or 0) * scale))
            weekly = int(round(int(offer.get("weekly_payment") or 0) * scale))
            years = int(offer.get("term_weeks") or 0) // 52
            self.loan_note.setText(
                f"Down payment {money_compact(down)}. {money_compact(principal)} on a {years}-year loan, "
                f"about {money(weekly)} a week."
            )
            self.loan_note.setToolTip(
                f"Down payment {money(down)}. Principal {money(principal)}. Weekly {money(weekly)}."
            )
        elif approved:
            self.loan_note.setText("Cash pays the opening cost today. The loan is 70% of that cost.")
            self.loan_note.setToolTip("")
        else:
            reason = str(offer.get("reason") or "No building loan for this city.")
            self.loan_note.setText(reason)
            self.loan_note.setToolTip(reason)

    def selected_market_id(self) -> str:
        item = self.list.currentItem()
        if item is None:
            return ""
        return str(item.data(Qt.ItemDataRole.UserRole) or "")

    def build_choice(self) -> dict:
        return {
            "sq_ft": int(self.sqft.value()),
            "build_days": int(self.build_days.value()),
            "center": int(self.center.value()),
            "gm": int(self.gm.value()),
            "template": str(self.layout_pick.currentData() or "balanced"),
        }


class StoresPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("storesPage")
        self.setStyleSheet(
            "QWidget#storesPage, QWidget#storesMain, QWidget#storeGrid { background: #09152D; color: #E8EEF8; }"
            "QLabel#pageTitle { color: #E8EEF8; background: transparent; }"
            "QFrame#storeCard, QFrame#storeCardOn, QFrame#storeDrawer {"
            " background: #0E1C3A; border: 1px solid #1A2E55; border-radius: 4px; color: #E8EEF8; }"
            "QFrame#storeCardOn { border: 1px solid #16803C; }"
        )
        self.host = None
        self.selected = ""
        self.sort_key = "pnl"
        self.query = ""
        self._profile = False
        self._store_tab = "Overview"
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        left = QWidget()
        left.setObjectName("storesMain")
        self.left_box = QVBoxLayout(left)
        self.left_box.setContentsMargins(24, 18, 16, 18)
        self.left_box.setSpacing(12)
        self.left_box.addLayout(_page_header(
            "Store Portfolio",
            "Click a state to lease its capital. Owned doors stay on the cards.",
        ))
        self.map = StoreMap()
        self.map.setObjectName("storeMap")
        self.map.set_show_places(True)
        self.map.setMinimumHeight(150)
        self.map.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.map.store_clicked.connect(self.select_store)
        self.map.sign_requested.connect(self._sign_prompt)
        self.left_box.addWidget(self.map, stretch=1)
        tools = QHBoxLayout()
        tools.addWidget(_label("Doors", 16, QFont.Weight.DemiBold))
        self.summary = _label("", 12, color=HQ_MUTED, name="portfolioSummary")
        tools.addWidget(self.summary, stretch=1)
        tools.addWidget(_label("Sort", 12, color=HQ_MUTED))
        self.sort = QComboBox()
        self.sort.setObjectName("storeSort")
        self.sort.addItem("Store P&L", "pnl")
        self.sort.addItem("Sales", "sales")
        self.sort.addItem("City", "city")
        self.sort.addItem("Status", "status")
        self.sort.currentIndexChanged.connect(self._on_sort)
        tools.addWidget(self.sort)
        self.sign_button = QPushButton("Sign a lease")
        self.sign_button.setObjectName("signLease")
        self.sign_button.clicked.connect(self._sign_prompt)
        tools.addWidget(self.sign_button)
        self.left_box.addLayout(tools)
        self.grid_host = QWidget()
        self.grid_host.setObjectName("storeGrid")
        self.grid = QVBoxLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(8)
        scroll = QScrollArea()
        scroll.setObjectName("storeList")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidget(self.grid_host)
        scroll.setMinimumHeight(72)
        scroll.setMaximumHeight(96)
        self.left_box.addWidget(scroll)
        self.capital_query = ""
        self.capital_find = QLineEdit()
        self.capital_find.setObjectName("capitalFind")
        self.capital_find.setPlaceholderText("State or capital")
        self.capital_find.textChanged.connect(self._on_capital_query)
        self.left_box.addWidget(self.capital_find)
        self.capital_table = QTableWidget(0, 5)
        self.capital_table.setObjectName("capitalSheet")
        self.capital_table.setHorizontalHeaderLabels(["State", "Capital", "People", "Demographics", "Rent / week"])
        self.capital_table.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored)
        self.capital_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        self.capital_table.setMinimumHeight(120)
        self.capital_table.setMaximumHeight(190)
        self.capital_table.setWordWrap(False)
        self.capital_table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.capital_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.capital_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.capital_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.capital_table.verticalHeader().setVisible(False)
        self.capital_table.verticalHeader().setDefaultSectionSize(22)
        self.capital_table.horizontalHeader().setStretchLastSection(False)
        self.capital_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.capital_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.capital_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.capital_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.capital_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.capital_table.cellDoubleClicked.connect(self._capital_activated)
        self.left_box.addWidget(self.capital_table, stretch=1)
        root.addWidget(left, stretch=3)
        self.drawer = QFrame()
        self.drawer.setObjectName("storeDrawer")
        self.drawer.setFixedWidth(320)
        drawer_shell = QVBoxLayout(self.drawer)
        drawer_shell.setContentsMargins(0, 0, 0, 0)
        drawer_shell.setSpacing(0)
        drawer_scroll = QScrollArea()
        drawer_scroll.setObjectName("storeDrawerScroll")
        drawer_scroll.setWidgetResizable(True)
        drawer_scroll.setFrameShape(QFrame.Shape.NoFrame)
        drawer_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("storeDrawerInner")
        self.drawer_box = QVBoxLayout(inner)
        self.drawer_box.setContentsMargins(16, 4, 16, 6)
        self.drawer_box.setSpacing(2)
        drawer_scroll.setWidget(inner)
        drawer_shell.addWidget(drawer_scroll)
        root.addWidget(self.drawer)

    def select_store(self, store_id: str) -> None:
        self.selected = store_id
        self._profile = False
        self.rebuild()

    def set_query(self, text: str) -> None:
        self.query = (text or "").strip().lower()
        self.rebuild()

    def _on_sort(self, _index: int) -> None:
        self.sort_key = self.sort.currentData() or "pnl"
        self.rebuild()

    def rebuild(self) -> None:
        host = self.host
        state = host.state if host is not None else None
        if state is None:
            return
        kind, scope_id = host.shell.scope
        ids = scoped_store_ids(state, kind, scope_id)
        if self.selected and self.selected not in ids and kind != "all":
            self.selected = ids[0] if ids else ""
        if not self.selected and ids:
            self.selected = ids[0]
        self.map.set_show_places(state.mode == "corporate")
        available = openable_markets(state) if state.mode == "corporate" else []
        self.sign_button.setVisible(state.mode == "corporate" and bool(available or capital_markets()))
        self._fill_map(state, ids, available)
        self._fill_grid(state, ids, available)
        self._fill_capitals(state)
        owned = [door for door in state.doors if door.id in ids]
        sales = sum(recorded_sales(state, door) for door in owned)
        open_caps = sum(1 for market in capital_markets() if door_by_id(state, market.id) is None)
        if state.mode == "corporate":
            short = f"{len(owned)} open · {len(available)} leases · {open_caps} capitals"
            self.summary.setText(short)
            self.summary.setToolTip(
                f"{len(owned)} open. {money(sales)} over the last 8 weeks. "
                f"{len(available)} city leases. {open_caps} state capitals still available."
            )
        else:
            self.summary.setText(f"{money_compact(sales)} last 8 wks")
        self._fill_drawer(state)
        self._park_cover()

    def _park_cover(self) -> None:
        """Keep the splash widget for older checks, and leave the portfolio on screen."""
        from open_late.ui.osprey_docs import OspreySplash

        if getattr(self, "cover", None) is None:
            self.cover = OspreySplash(self)
        self.cover.hide()

    def _show_cover(self) -> None:
        self._park_cover()

    def reveal(self) -> None:
        cover = getattr(self, "cover", None)
        if cover is not None:
            cover.hide()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # The map takes the leftover. The door list and the capital sheet stay on the page.
        room = self.height() - 480
        cap = max(150, min(280, room))
        if self.map.maximumHeight() != cap:
            self.map.setMaximumHeight(cap)
        cover = getattr(self, "cover", None)
        if cover is not None and cover.isVisible():
            cover.setGeometry(self.rect())
            cover.raise_()

    def _fill_map(self, state, ids, available) -> None:
        selected = set(ids)
        pins = []
        for store_id, (label, lon, lat, ox, oy) in CITIES.items():
            door = door_by_id(state, store_id)
            if door is None:
                market = next((item for item in available if item.id == store_id), None)
                pins.append({
                    "id": store_id, "label": label, "lon": lon, "lat": lat,
                    "owned": False, "offset": (ox, oy),
                    "health": "planned",
                    "sales_label": "",
                    "tip": f"{label} · not leased" if market else label,
                })
                continue
            sales = recorded_sales(state, door)
            contrib, share = contribution_share(state, door)
            from open_late.ui.store_intel import brief as store_brief

            card = store_brief(state, door)
            pins.append({
                "id": door.id,
                "label": door.city,
                "lon": lon,
                "lat": lat,
                "owned": True,
                "open": door.status == "open",
                "health": card["health"],
                "selected": door.id == self.selected,
                "dim": door.id not in selected,
                "offset": (ox, oy),
                "sales_label": money_compact(sales),
                "contrib_label": f"Contrib. {share * 100:.1f}%",
                "tip": f"{door.city} · sales {money(sales)} · Store P&L {money(contrib)}",
            })
        from open_late.us_capitals import by_id as capital_by_id

        known = set(CITIES)
        for door in state.doors:
            if door.id in known or door.id not in selected:
                continue
            place = capital_by_id(door.id)
            if place is None:
                continue
            sales = recorded_sales(state, door)
            contrib, share = contribution_share(state, door)
            from open_late.ui.store_intel import brief as store_brief

            card = store_brief(state, door)
            pins.append({
                "id": door.id,
                "label": door.city,
                "lon": place.lon,
                "lat": place.lat,
                "owned": True,
                "open": door.status == "open",
                "health": card["health"],
                "selected": door.id == self.selected,
                "dim": False,
                "sales_label": money_compact(sales),
                "contrib_label": f"Contrib. {share * 100:.1f}%",
                "tip": f"{door.city} · sales {money(sales)} · Store P&L {money(contrib)}",
            })
        self.map.set_pins(pins)

    def _on_capital_query(self, text: str) -> None:
        self.capital_query = (text or "").strip().lower()
        host = self.host
        state = host.state if host is not None else None
        if state is not None and state.mode == "corporate":
            self._fill_capitals(state)

    def _fill_capitals(self, state) -> None:
        from open_late.ui.osprey_docs import excel_table
        from open_late.us_capitals import CAPITALS, demographic_line

        table = self.capital_table
        if state.mode != "corporate":
            table.setRowCount(0)
            table.setVisible(False)
            self.capital_find.setVisible(False)
            return
        table.setVisible(True)
        self.capital_find.setVisible(True)
        excel_table(table)
        table.setWordWrap(False)
        table.verticalHeader().setVisible(False)
        query = self.capital_query
        rows = [
            item for item in CAPITALS
            if not query or query in item.state.lower() or query in item.city.lower() or query in item.abbr.lower()
        ]
        table.setRowCount(len(rows))
        owned = {door.id: door for door in state.doors}
        for row, item in enumerate(rows):
            market = next((market for market in capital_markets() if market.id == item.ident), None)
            door = owned.get(item.ident)
            if door is None:
                status = "Available"
            elif door.status == "open":
                status = "Open"
            else:
                status = f"Opens day {door.opens_on}"
            demo = demographic_line(item)
            rent = money_compact(market.rent_weekly) if market is not None else ""
            values = [item.state, f"{item.city} · {status}", f"{item.population:,}", demo, rent]
            for column, text in enumerate(values):
                cell = QTableWidgetItem(text)
                if column == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, item.ident)
                if column in (2, 4):
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                cell.setToolTip(
                    f"{item.city}, {item.abbr} · {item.population:,} people. {demo}. "
                    "Hispanic/Latino overlaps the race shares. "
                    + (money(market.rent_weekly) + " rent / week." if market is not None else "")
                )
                table.setItem(row, column, cell)

    def _capital_activated(self, row: int, _column: int) -> None:
        cell = self.capital_table.item(row, 0)
        ident = str(cell.data(Qt.ItemDataRole.UserRole) or "") if cell is not None else ""
        if not ident or self.host is None or self.host.state is None:
            return
        if door_by_id(self.host.state, ident) is not None:
            self.select_store(ident)
            return
        self._sign_prompt(ident)

    def _matches(self, door) -> bool:
        if not self.query:
            return True
        blob = f"{door.city} {door.state_name} {door.region} {door.id}".lower()
        return self.query in blob

    def _fill_grid(self, state, ids, available=None) -> None:
        del available
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        doors = [door for door in state.doors if door.id in ids and self._matches(door)]
        if not doors and state.mode != "corporate":
            self.grid.addWidget(self._shop_card(state))
            self.grid.addStretch(1)
            return
        key = self.sort_key
        def sort_value(door):
            if key == "sales":
                return (0, -recorded_sales(state, door), door.city)
            if key == "status":
                return (0 if door.status == "open" else 1, door.city)
            if key == "city":
                return (0, door.city)
            contrib, _share = contribution_share(state, door)
            return (0, -contrib, door.city)
        doors = sorted(doors, key=sort_value)
        hero = len(doors) <= 1
        for door in doors:
            self.grid.addWidget(self._door_card(state, door, hero=hero))
        self.grid.addStretch(1)

    def _row_metric(self, caption: str, value: str, tip: str = "", width: int = 108) -> QWidget:
        box = QVBoxLayout()
        box.setSpacing(0)
        cap = _label(caption, 10, QFont.Weight.DemiBold, HQ_FAINT)
        shown = _label(value, 13, QFont.Weight.DemiBold)
        for lab in (cap, shown):
            lab.setWordWrap(False)
            if tip:
                lab.setToolTip(tip)
        box.addWidget(cap)
        box.addWidget(shown)
        wrap = QWidget()
        wrap.setLayout(box)
        wrap.setMinimumWidth(width)
        return wrap

    def _shop_card(self, state) -> QFrame:
        frame = QFrame()
        frame.setObjectName("storeCardOn" if self.selected else "storeCard")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(6, 4, 10, 4)
        layout.setSpacing(10)
        art = StorefrontArt(resolved_chain_id(state), frame, compact=True)
        layout.addWidget(art)
        pad = QVBoxLayout()
        pad.setSpacing(2)
        pad.addWidget(_label(state.shop_name, 15, QFont.Weight.DemiBold))
        pad.addWidget(_label(chain_info(state)["name"], 12, color=HQ_MUTED, name="cardChainName"))
        layout.addLayout(pad, stretch=1)
        return frame

    def _door_card(self, state, door, hero: bool = False) -> QFrame:
        frame = QFrame()
        on = door.id == self.selected
        frame.setObjectName("storeCardOn" if on else "storeCard")
        frame.setCursor(Qt.CursorShape.PointingHandCursor)
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(6, 4, 10, 4)
        layout.setSpacing(10)
        art = StorefrontArt(resolved_chain_id(state), frame, compact=True)
        art.set_chain(resolved_chain_id(state), door.status == "open", hero=False)
        layout.addWidget(art)
        pad = QVBoxLayout()
        pad.setSpacing(1)
        pad.addWidget(_label(door.city, 15, QFont.Weight.DemiBold))
        pad.addWidget(_label(display_address(door), 11, color=HQ_MUTED))
        chain = chain_info(state)
        manager = manager_by_id(state, door.manager_id)
        who = manager.name if manager else "No manager"
        if door.status == "open":
            phase = "Open"
        else:
            phase = f"Opens day {door.opens_on}"
        from open_late.ui.store_intel import HEALTH_COLORS, brief as store_brief

        tone = store_brief(state, door)["health"]
        phase_lab = _label(f"●  {phase}", 11, QFont.Weight.DemiBold, HEALTH_COLORS[tone], name="storeHealth")
        meta = _label(f"{chain.get('name') or ''}  ·  {who}", 11, color=HQ_MUTED, name="cardChainName")
        meta.setWordWrap(False)
        meta.setToolTip(f"{chain.get('name') or ''}  ·  {phase}  ·  {who}")
        pad.addWidget(phase_lab)
        pad.addWidget(meta)
        layout.addLayout(pad, stretch=1)
        sales = recorded_sales(state, door)
        contrib, _share = contribution_share(state, door)
        layout.addWidget(self._row_metric("Last 8 wks", money_compact(sales), money(sales)))
        layout.addWidget(self._row_metric("Store P&L", money_compact(contrib), money(contrib)))
        layout.addWidget(self._row_metric(
            "Last week",
            money_compact(door.last_contribution),
            money(door.last_contribution),
        ))
        frame.mousePressEvent = lambda _event, ident=door.id: self.select_store(ident)  # noqa: E731
        for child in frame.findChildren(QWidget):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        return frame

    def _market_card(self, state, market) -> QFrame:
        frame = QFrame()
        frame.setObjectName("storeCard")
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(6, 4, 10, 4)
        layout.setSpacing(10)
        art = StorefrontArt(resolved_chain_id(state), frame, compact=True)
        art.set_chain(resolved_chain_id(state), open_badge=False, hero=False)
        layout.addWidget(art)
        pad = QVBoxLayout()
        pad.setSpacing(1)
        pad.addWidget(_label(market.city, 15, QFont.Weight.DemiBold))
        abbr = {"Indiana": "IN", "Illinois": "IL", "Texas": "TX", "Nevada": "NV", "Washington": "WA"}.get(
            market.state_name, market.state_name,
        )
        pad.addWidget(_label(f"{market.city}, {abbr}", 11, color=HQ_MUTED))
        pad.addWidget(_label("Available to lease", 12, color=HQ_MUTED))
        layout.addLayout(pad, stretch=1)
        rent = _label(f"Rent {money_compact(market.rent_weekly)} / week", 13, QFont.Weight.DemiBold)
        rent.setToolTip(money(market.rent_weekly) + " / week")
        rent.setWordWrap(False)
        layout.addWidget(rent)
        btn = QPushButton("Sign a lease")
        btn.setObjectName("signLease")
        btn.setMinimumHeight(32)
        btn.clicked.connect(lambda _=False, ident=market.id: self._sign_prompt(ident))
        layout.addWidget(btn)
        return frame

    def _fill_drawer(self, state) -> None:
        box = self.drawer_box
        while box.count():
            item = box.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
            elif item.layout() is not None:
                layout = item.layout()
                while layout.count():
                    child = layout.takeAt(0)
                    w = child.widget()
                    if w is not None:
                        w.hide()
                        w.setParent(None)
                        w.deleteLater()
        door = door_by_id(state, self.selected) if self.selected else None
        box.addWidget(_label("Store Details", 11, QFont.Weight.DemiBold, HQ_FAINT, name="drawerKicker"))
        if door is None:
            box.addWidget(_label("Select a store", 18, QFont.Weight.Bold, name="drawerEmpty"))
            box.addWidget(_label("A pin on the map or a store card opens its details here.", 13, color=HQ_MUTED, wrap=True))
            box.addStretch(1)
            return
        manager = manager_by_id(state, door.manager_id)
        box.addWidget(_label(door.city, 22, QFont.Weight.Bold, name="drawerTitle"))
        box.addWidget(_label(street_address(door), 12, color=HQ_MUTED, name="drawerAddress", wrap=True))
        # Manager
        box.addWidget(_label("Store Manager", 11, QFont.Weight.DemiBold, HQ_FAINT))
        name = manager.name if manager else "No manager"
        box.addWidget(_label(name, 14, QFont.Weight.DemiBold, name="drawerManager"))
        box.addWidget(_label("Hours of Operation", 11, QFont.Weight.DemiBold, HQ_FAINT))
        hours = f"Mon – Sat:  {door.open_hour:02d}:00 – {door.close_hour:02d}:00"
        box.addWidget(_label(hours, 13, name="drawerHours", wrap=True))
        box.addWidget(_label("Labor Budget (Weekly)", 11, QFont.Weight.DemiBold, HQ_FAINT))
        self._add_floor_tools(box, state, door)
        sales = recorded_sales(state, door)
        contrib, share = contribution_share(state, door)
        box.addWidget(_label("Contribution (last 8 wks)", 11, QFont.Weight.DemiBold, HQ_FAINT))
        if hq_available():
            pnl_line = _label(f"{money_compact(contrib)} Store P&L  ·  {money_compact(sales)} sales", 12, color=HQ_MUTED, wrap=True, name="drawerPnlLines")
            pnl_line.setToolTip(f"{money(contrib)} Store P&L  ·  {money(sales)} sales")
            box.addWidget(pnl_line)
        else:
            box.addWidget(_label("Store P&L waits on the engine API. It is not the last-week contribution.", 12, color=HQ_MUTED, name="placeholder", wrap=True))
        week_lab = _label(f"Last week contribution  {money_compact(door.last_contribution)}", 12, color=HQ_MUTED, name="drawerWeek")
        week_lab.setToolTip(money(door.last_contribution))
        box.addWidget(week_lab)
        self._add_store_brief(box, state, door)
        pos = store_pos(state, door.id)
        pos_line = pos.get("name") or "Counter Ledger"
        if pos.get("pending_name"):
            pos_line += f"  ·  pending Sunday: {pos['pending_name']}"
        pos_lab = _label(f"POS  {pos_line}", 13, name="drawerPos", wrap=True)
        pos_tip = (
            "A switch charges the install fee today (Open Drawer $200, Counter Ledger $350, Chain Link $800) "
            "and the new till takes over at the next Sunday close."
        )
        pos_lab.setToolTip(pos_tip)
        box.addWidget(pos_lab)
        if pos_options():
            picker = QComboBox()
            picker.setObjectName("posPicker")
            picker.setToolTip(pos_tip)
            current = pos.get("id") or pos.get("pos_id")
            for option in pos_options():
                fee = install_fee(option["id"])
                label = option["name"]
                if fee:
                    label = f"{label}  ·  install {money(fee)}"
                picker.addItem(label, option["id"])
                if option["id"] == current:
                    picker.setCurrentIndex(picker.count() - 1)
            apply = QPushButton("Switch till")
            apply.setObjectName("primary" if hq_available() else "quiet")
            apply.setMinimumHeight(32)
            apply.setEnabled(hq_available())
            apply.clicked.connect(lambda _=False, combo=picker, ident=door.id: self._queue_pos(ident, combo.currentData()))
            box.addWidget(picker)
            box.addWidget(apply)
        if self._profile:
            self._add_profile_tools(box, state, door)
            box.addWidget(_label(f"Wall match  {door.compliance}", 12, color=HQ_MUTED, wrap=True))
            box.addWidget(_label(f"Transit  {door.transit_days} day  ·  tax {door.sales_tax_bps / 100:.1f}%", 12, color=HQ_MUTED, wrap=True))
            chain = chain_info(state)
            box.addWidget(_label(f"Chain  {chain['name']}", 12, color=HQ_MUTED))
        profile = QPushButton("View full profile  →" if not self._profile else "Back to details")
        profile.setObjectName("viewProfile")
        profile.setMinimumHeight(36)
        profile.clicked.connect(self._toggle_profile)
        box.addWidget(profile)
        inner = box.parentWidget()
        if inner is not None:
            inner.adjustSize()
            inner.updateGeometry()

    def _add_store_brief(self, box, state, door) -> None:
        from open_late.ui.store_intel import TABS, brief as store_brief

        card = store_brief(state, door)
        picker = QComboBox()
        picker.setObjectName("storeView")
        picker.setMaximumHeight(24)
        for name in TABS:
            picker.addItem(name)
        index = picker.findText(self._store_tab)
        picker.setCurrentIndex(max(0, index))
        shown = _label(card["tabs"].get(self._store_tab) or card["tabs"]["Overview"], 11, color="#1C2430", wrap=True, name="storeIntel")
        shown.setWordWrap(True)
        shown.setMaximumHeight(58)

        def _switch(name: str, label=shown, tabs=card["tabs"]) -> None:
            self._store_tab = name
            label.setText(tabs.get(name) or "")

        picker.currentTextChanged.connect(_switch)
        box.addWidget(picker)
        box.addWidget(shown)

    def _add_floor_tools(self, box, state, door) -> None:
        """Labor, weeks of supply, truck, replenish; shares and house deals in the profile."""
        budget = QHBoxLayout()
        labor = QSpinBox()
        labor.setObjectName("laborBudget")
        labor.setPrefix("$")
        labor.setRange(400, labor_budget_ceiling(door.labor_budget))
        labor.setSingleStep(50)
        labor.setValue(int(door.labor_budget or 0))
        labor.setToolTip("Weekly labor budget. The manager writes the roster inside this number.")
        if hasattr(labor, "setGroupSeparatorShown"):
            labor.setGroupSeparatorShown(True)
        weeks = QSpinBox()
        weeks.setObjectName("weeksSupply")
        weeks.setRange(1, 8)
        weeks.setValue(int(door.weeks_of_supply or 3))
        weeks.setToolTip("Weeks of last week's sales that Replenish tries to put on the shelf.")
        self._labor = {door.id: labor}
        self._weeks = {door.id: weeks}
        budget.addWidget(_label("Labor", 11, color=HQ_MUTED))
        budget.addWidget(labor, stretch=1)
        budget.addWidget(_label("Weeks", 11, color=HQ_MUTED))
        budget.addWidget(weeks)
        box.addLayout(budget)
        save = QPushButton("Set budget")
        save.setObjectName("setBudget")
        save.setMinimumHeight(36)
        save.clicked.connect(lambda _=False, door_id=door.id: self._set_budget(door_id))
        box.addWidget(save)

        from open_late.dc import pool_summary

        face, tip = pool_summary(state)
        pools = _label(face, 11, color=HQ_MUTED, wrap=True)
        pools.setObjectName("poolLine")
        pools.setToolTip(tip)
        box.addWidget(pools)
        truck_title = _label("Warehouse truck", 11, QFont.Weight.DemiBold, HQ_FAINT)
        truck_title.setToolTip(
            "Send truck moves the quantity you pick from Evansville. "
            "Replenish fills this store up to its weeks of supply."
        )
        box.addWidget(truck_title)
        product = QComboBox()
        product.setObjectName("truckProduct")
        product.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        product.addItem("Pick from the warehouse", "")
        for product_id, line in state.stock.items():
            if int(getattr(line, "on_hand", 0) or 0) <= 0:
                continue
            item = state.products.get(product_id)
            name = getattr(item, "name", product_id) if item is not None else product_id
            product.addItem(f"{name}  ·  {line.on_hand}", product_id)
        qty = QSpinBox()
        qty.setObjectName("truckQty")
        ceiling = 40
        try:
            ceiling = int(order_qty_max())
        except Exception:
            ceiling = 40
        qty.setRange(1, max(1, ceiling))
        qty.setValue(min(2, max(1, ceiling)))
        arm = getattr(self, "_truck_arm", None) or {}
        if str(arm.get("door") or "") == door.id:
            index = product.findData(str(arm.get("product") or ""))
            if index >= 0:
                product.setCurrentIndex(index)
            wanted = int(arm.get("qty") or 0)
            if wanted > 0:
                qty.setValue(min(qty.maximum(), max(qty.minimum(), wanted)))
            self._truck_arm = {}
        self._truck_product = {door.id: product}
        self._truck_qty = {door.id: qty}
        box.addWidget(product)
        qty_row = QHBoxLayout()
        qty_row.addWidget(_label("Qty", 11, color=HQ_MUTED))
        qty_row.addWidget(qty, stretch=1)
        box.addLayout(qty_row)
        truck = QHBoxLayout()
        truck.setSpacing(8)
        go = QPushButton("Send truck")
        go.setObjectName("sendTruck")
        go.setMinimumHeight(36)
        go.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        go.setToolTip("Ship the chosen item and quantity from the Evansville warehouse.")
        go.clicked.connect(lambda _=False, door_id=door.id: self._send_truck(door_id))
        fill = QPushButton("Replenish")
        fill.setObjectName("replenishDoor")
        fill.setMinimumHeight(36)
        fill.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        fill.setToolTip("Fill the shelf up to this store's weeks of supply.")
        fill.clicked.connect(lambda _=False, door_id=door.id: self._replenish(door_id))
        truck.addWidget(go, stretch=1)
        truck.addWidget(fill, stretch=1)
        box.addLayout(truck)


    def _add_profile_tools(self, box, state, door) -> None:
        box.addWidget(_label("Department shares (must total 100)", 11, QFont.Weight.DemiBold, HQ_FAINT, wrap=True))
        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(4)
        spins = {}
        keys = list(CATEGORY_LABELS)
        for index, key in enumerate(keys):
            cell = QVBoxLayout()
            cell.setSpacing(0)
            cell.addWidget(_label(CATEGORY_SHORT.get(key, key), 10, color=HQ_MUTED, wrap=True))
            spin = QSpinBox()
            spin.setObjectName(f"share_{key}")
            spin.setRange(0, 100)
            spin.setValue(int((door.planogram or {}).get(key, 0)))
            spins[key] = spin
            cell.addWidget(spin)
            grid.addLayout(cell, index // 3, index % 3)
        self._plano = {door.id: spins}
        box.addLayout(grid)
        send = QPushButton("Send this wall")
        send.setObjectName("sendWall")
        send.setMinimumHeight(36)
        send.clicked.connect(lambda _=False, door_id=door.id: self._send_wall(door_id))
        box.addWidget(send)

        box.addWidget(_label("Vendor houses", 11, QFont.Weight.DemiBold, HQ_FAINT))
        try:
            from open_late.content import SUPPLIERS
        except ImportError:
            SUPPLIERS = {}
        for supplier in SUPPLIERS.values():
            if supplier.id == "labelco" and not getattr(getattr(state, "flags", None), "private_label", False):
                continue
            account = next((item for item in getattr(state, "supplier_accounts", []) if item.supplier_id == supplier.id), None)
            deal = next((item for item in getattr(state, "deals", []) if item.supplier_id == supplier.id), None)
            volume = account.volume if account else 0
            standing = (
                f"{deal.tier}, {deal.cost_off_percent}% off"
                if deal else "list price"
            )
            row = QHBoxLayout()
            lab = _label(f"{supplier.name}  ·  {standing}", 11, color=HQ_MUTED, wrap=True)
            row.addWidget(lab, stretch=1)
            button = QPushButton("Sign the deal")
            button.setObjectName(f"signDeal_{supplier.id}")
            button.clicked.connect(lambda _=False, sid=supplier.id: self._sign_house(sid))
            row.addWidget(button)
            box.addLayout(row)

    def _set_budget(self, door_id: str) -> None:
        host = self.host
        if host is None or host.state is None:
            return
        door = door_by_id(host.state, door_id)
        labor = (getattr(self, "_labor", {}) or {}).get(door_id)
        weeks = (getattr(self, "_weeks", {}) or {}).get(door_id)
        if door is None or labor is None or weeks is None:
            return
        door.labor_budget = labor.value()
        door.weeks_of_supply = weeks.value()
        door.roster_set = False
        host._say(
            f"{door.city} labor budget is {money(door.labor_budget)} a week. "
            f"Replenishment covers {door.weeks_of_supply} weeks of the last week's sales. "
            "The manager rewrites the roster on the next close."
        )
        if hasattr(host, "_save"):
            host._save()
        host.refresh()

    def _replenish(self, door_id: str) -> None:
        host = self.host
        if host is None or host.state is None or replenish is None:
            return
        host._say(replenish(host.state, door_id))
        if hasattr(host, "_save"):
            host._save()
        host.refresh()

    def _send_truck(self, door_id: str) -> None:
        host = self.host
        if host is None or host.state is None or allocate is None:
            return
        product = (getattr(self, "_truck_product", {}) or {}).get(door_id)
        qty = (getattr(self, "_truck_qty", {}) or {}).get(door_id)
        if product is None or qty is None or not product.currentData():
            host._say("Pick something the warehouse actually has.")
            return
        text = allocate(host.state, door_id, {str(product.currentData()): qty.value()})
        host._say(text)
        follow = getattr(host, "_stockout_follow", None) or {}
        if str(text).startswith("Sent ") and follow.get("action") == "send" and follow.get("door") == door_id:
            from open_late.visiondeck.memory import remember_send

            remember_send(
                host.state,
                door_id,
                str(follow.get("place") or door_id),
                str(follow.get("category") or ""),
                str(product.currentData() or ""),
                int(qty.value()),
            )
            host._stockout_follow = None
        if hasattr(host, "_save"):
            host._save()
        host.refresh()

    def _send_wall(self, door_id: str) -> None:
        host = self.host
        if host is None or host.state is None or set_planogram is None:
            return
        spins = (getattr(self, "_plano", {}) or {}).get(door_id, {})
        shares = {key: spin.value() for key, spin in spins.items()}
        text = set_planogram(host.state, door_id, shares)
        door = door_by_id(host.state, door_id)
        city = door.city if door else "the store"
        host._say(text or f"The wall for {city} adds up. The manager has to catch up to it.")
        if hasattr(host, "_save"):
            host._save()
        host.refresh()

    def _sign_house(self, supplier_id: str) -> None:
        host = self.host
        if host is None or host.state is None or sign_deal is None:
            return
        host._say(sign_deal(host.state, supplier_id))
        if hasattr(host, "_save"):
            host._save()
        host.refresh()

    def _toggle_profile(self) -> None:
        self._profile = not self._profile
        if self.host is not None and self.host.state is not None:
            self._fill_drawer(self.host.state)

    def _queue_pos(self, store_id: str, pos_id: str) -> None:
        host = self.host
        if host is None or host.state is None or not pos_id:
            return
        host._say(set_store_pos(host.state, store_id, pos_id))
        host.refresh()

    def _sign_city(self, market_id: str, loan: bool = False, build: dict | None = None) -> None:
        host = self.host
        if host is None or host.state is None:
            return
        host._say(open_market(host.state, market_id, loan=loan, build=build))
        host.refresh()

    def _sign_prompt(self, preselect: str = "") -> None:
        host = self.host
        state = host.state if host is not None else None
        if state is None or state.mode != "corporate":
            return
        owned = {door.id for door in state.doors}
        available = list(openable_markets(state))
        available.extend(market for market in capital_markets() if market.id not in owned)
        if not available:
            return
        dialog = LeasePickerDialog(available, self, preselect=str(preselect or ""), state=state)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        market_id = dialog.selected_market_id()
        if not market_id:
            return
        self._sign_city(market_id, loan=bool(dialog.loan.isChecked()), build=dialog.build_choice())

class PosPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("posPage")
        self.setStyleSheet(
            "QWidget#posPage { background: #09152D; color: #E8EEF8; }"
            "QFrame#card { background: #0E1C3A; border: 1px solid #1A2E55; border-radius: 4px; color: #E8EEF8; }"
        )
        self.host = None
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(16, 12, 16, 16)
        self.box.setSpacing(10)

    def rebuild(self) -> None:
        while self.box.count():
            item = self.box.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        host = self.host
        state = host.state if host is not None else None
        head = QLabel("  POS")
        head.setObjectName("posHead")
        head.setFixedHeight(34)
        head.setStyleSheet(
            "QLabel#posHead { background: #12254A; color: #F4F7FB; font-weight: 700; }"
        )
        self.box.addWidget(head)
        self.box.addWidget(_label(
            "A switch charges the install fee today (Open Drawer $200, Counter Ledger $350, Chain Link $800) "
            "and the new till takes over at the next Sunday close.",
            13, color=HQ_MUTED, name="posSwitchHint", wrap=True,
        ))
        if not hq_available():
            self.box.addWidget(_label(
                "Placeholder. The engine POS API is not in this build yet. "
                "The store drawer already shows the POS name and any pending Sunday switch.",
                13, color=HQ_MUTED, name="placeholder", wrap=True,
            ))
        options = pos_options()
        tills = QHBoxLayout()
        tills.setSpacing(8)
        for option in options:
            frame, layout = _card()
            title = option.get("name") or option.get("id")
            layout.addWidget(_label(str(title).upper(), 11, QFont.Weight.DemiBold, HQ_MUTED))
            fee = install_fee(option.get("id") or "")
            layout.addWidget(_label(money(fee), 22, QFont.Weight.Bold))
            layout.addWidget(_label("install fee, charged today", 11, color=HQ_MUTED))
            layout.addWidget(_label(option.get("blurb") or "", 12, color=HQ_MUTED, wrap=True))
            weekly = option.get("weekly_license")
            if weekly:
                layout.addWidget(_label(f"Weekly license {money(int(weekly))}", 12, color=HQ_MUTED))
            rate = option.get("card_fee_rate")
            if rate:
                layout.addWidget(_label(f"Card fee {float(rate) * 100:.1f}%", 12, color=HQ_MUTED))
            if option.get("placeholder"):
                layout.addWidget(_label("Placeholder catalog", 11, color=HQ_MUTED, name="placeholder"))
            tills.addWidget(frame)
        if options:
            self.box.addLayout(tills)
        if state is not None:
            from open_late.ui.hq_adapter import store_ids
            assigned, assigned_box = _card()
            assigned_box.addWidget(_label("STORE TILLS", 11, QFont.Weight.DemiBold, HQ_MUTED))
            for store_id in store_ids(state):
                pos = store_pos(state, store_id)
                door = door_by_id(state, store_id)
                name = f"{door.city}, {door.state_name}" if door else state.shop_name
                line = f"{name}: {pos.get('name') or 'Counter Ledger'}"
                if pos.get("pending_name"):
                    line += f" · pending Sunday: {pos['pending_name']}"
                assigned_box.addWidget(_label(line, 13, wrap=True))
            self.box.addWidget(assigned)
            if pos_options():
                switch, switch_box = _card()
                switch_box.addWidget(
                    _label("SWITCH SYSTEM", 11, QFont.Weight.DemiBold, HQ_MUTED, name="posSwitchTitle")
                )
                row = QHBoxLayout()
                store_picker = QComboBox()
                store_picker.setObjectName("posSwitchStore")
                for store_id in store_ids(state):
                    pos = store_pos(state, store_id)
                    door = door_by_id(state, store_id)
                    name = f"{door.city}, {door.state_name}" if door else state.shop_name
                    current = pos.get("name") or "Counter Ledger"
                    store_picker.addItem(f"{name}  ·  {current}", store_id)
                sys_picker = QComboBox()
                sys_picker.setObjectName("posSwitchSystem")
                for option in pos_options():
                    fee = install_fee(option["id"])
                    label = option["name"]
                    if fee:
                        label = f"{label}  ·  install {money(fee)}"
                    sys_picker.addItem(label, option["id"])
                apply = QPushButton("Switch System")
                apply.setObjectName("posSwitchBtn")
                apply.setEnabled(bool(hq_available()))
                apply.clicked.connect(self._switch_system)
                row.addWidget(store_picker, stretch=1)
                row.addWidget(sys_picker, stretch=1)
                row.addWidget(apply)
                switch_box.addLayout(row)
                self.box.addWidget(switch)
                self._pos_store = store_picker
                self._pos_system = sys_picker
        self.box.addStretch(1)

    def _switch_system(self) -> None:
        host = self.host
        store_picker = getattr(self, "_pos_store", None)
        sys_picker = getattr(self, "_pos_system", None)
        if host is None or host.state is None or store_picker is None or sys_picker is None:
            return
        store_id = store_picker.currentData()
        pos_id = sys_picker.currentData()
        if not store_id or not pos_id:
            return
        host._say(set_store_pos(host.state, store_id, pos_id))
        host.refresh()
