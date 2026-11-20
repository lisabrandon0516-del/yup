"""Planogram editor: fixture list, glass shelf canvas, templates, and SKU rail."""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from open_late.text import money, money_compact
from open_late.text import CATEGORY_LABELS
from open_late.ui.hq_adapter import (
    department_of,
    department_sales,
    department_week_compare,
    planogram_departments,
    products_by_department,
    scoped_store_ids,
)

try:
    from open_late.corporate import door_by_id, set_planogram
except ImportError:  # pragma: no cover
    door_by_id = None

    def set_planogram(state, door_id, shares):
        return ""
from open_late.ui.hq_art import paint_department_icon
from open_late.ui.hq_product import STATUS_COLOR, ProductTile, paint_product_art, paint_product_tile, product_title
from open_late.ui.theme import (
    DOWN, FRAME, FRAME_BTN, FRAME_BTN_LINE, FRAME_INK, FRAME_LINE,
    HQ_FAINT, HQ_MUTED, HQ_TITLE, OPEN_GREEN, RR_BLUE, TEXT, UP, ui_font,
)

FIXTURES = [
    ("glass_4", "Glass Shelf 4-Tier", "48\"W × 16\"D × 72\"H"),
    ("gondola_4", "Wall Gondola 4-Tier", "48\"W × 19\"D × 72\"H"),
    ("peg", "Peg Wall", "48\"W × 12\"D × 72\"H"),
    ("table_72", "Table Display 72\"W", "72\"W × 36\"D × 30\"H"),
    ("endcap", "End Cap", "36\"W × 20\"D × 60\"H"),
    ("spinner", "Accessory Spinner", "28\" diameter × 60\"H"),
]

TEMPLATES = [
    ("balanced", "Balanced Mix"),
    ("grocery", "Grocery"),
    ("fresh", "Fresh"),
    ("general", "General"),
    ("seasonal", "Seasonal"),
    ("blank", "Blank"),
]

# Unfiltered "All" shows a few families from every department so grocery
# cannot swallow the rail. A department filter or search pages the rest.
SKU_RAIL_MIXED = 4
SKU_RAIL_PAGE = 20


def _sku_blob(product, dept_id: str, dept_label: str) -> str:
    parts = (
        getattr(product, "name", ""),
        getattr(product, "id", ""),
        getattr(product, "brand", ""),
        getattr(product, "department", ""),
        getattr(product, "category", ""),
        dept_id,
        dept_label,
    )
    return " ".join(str(part) for part in parts if part).lower()


# Default 4-tier × 4 facing layout, department ids.

def compiled_shelf_rows(state) -> list[list] | None:
    """The first inline bay of an open store, one cell per facing."""
    if state is None or not getattr(state, "doors", None):
        return None
    try:
        from open_late.shelf_model import sku_index_v1
        from open_late.shelves import compile_for, shelves_on
    except Exception:
        return None
    if not shelves_on(state):
        return None
    door = next((item for item in state.doors if getattr(item, "status", "") == "open"), state.doors[0])
    try:
        layout = compile_for(state, door)
    except Exception:
        return None
    index = sku_index_v1()
    bay = next((item for item in layout.bays if not item.is_feature and item.tiers), None)
    if bay is None:
        return None
    rows: list[list] = []
    products = getattr(state, "products", {}) or {}
    for _tier, items in bay.tiers:
        row = []
        for sku, facings in items:
            if not (0 <= int(sku) < len(index)):
                continue
            product = products.get(index[int(sku)])
            if product is None:
                continue
            row.extend([product] * max(1, int(facings)))
        if row:
            rows.append(row)
    return rows or None


def _layout_products(template_id: str, state=None) -> list[list]:
    """4x4 product facings for a template, drawn from the department catalog."""
    grouped = products_by_department(state)
    def take(dept: str, count: int, offset: int = 0):
        items = list(grouped.get(dept) or [])
        if not items:
            return [None] * count
        out = []
        for i in range(count):
            out.append(items[(offset + i) % len(items)])
        return out
    blank = [[None] * 4 for _ in range(4)]
    if template_id == "blank":
        return blank
    if template_id == "grocery":
        return [
            take("grocery", 4),
            take("produce", 4),
            take("meat_dairy", 4),
            take("frozen", 4),
        ]
    if template_id == "fresh":
        return [
            take("produce", 4),
            take("meat_dairy", 4),
            take("frozen", 2) + take("grocery", 2),
            take("grocery", 2, 2) + take("produce", 2, 4),
        ]
    if template_id == "general":
        return [
            take("electronics", 4),
            take("clothing", 4),
            take("household", 2) + take("toys", 2),
            take("home_garden", 2) + take("sporting", 2),
        ]
    if template_id == "seasonal":
        return [
            take("seasonal", 4),
            take("toys", 2) + take("clothing", 2),
            take("home_garden", 2) + take("grocery", 2),
            take("seasonal", 2, 4) + take("sporting", 2),
        ]
    # balanced mix
    return [
        take("grocery", 2) + take("produce", 2),
        take("meat_dairy", 2) + take("frozen", 2),
        take("household", 1) + take("health_beauty", 1) + take("pharmacy", 1) + take("electronics", 1),
        take("clothing", 1) + take("toys", 1) + take("home_garden", 1) + take("seasonal", 1),
    ]


def template_shares(template_id: str, state=None) -> dict[str, int]:
    """Facing counts from a template, scaled to integers that sum to 100."""
    keys = list(CATEGORY_LABELS)
    rows = _layout_products(template_id, state)
    counts = {key: 0 for key in keys}
    total = 0
    for row in rows:
        for product in row:
            if product is None:
                continue
            dept = str(getattr(product, "department", "") or getattr(product, "category", "") or "")
            if dept not in counts:
                counts[dept] = 0
            counts[dept] += 1
            total += 1
    if total <= 0:
        return {key: 0 for key in keys}
    raw = {key: counts.get(key, 0) * 100.0 / total for key in keys}
    shares = {key: int(raw[key]) for key in keys}
    leftover = 100 - sum(shares.values())
    order = sorted(keys, key=lambda key: (raw[key] - shares[key], counts.get(key, 0)), reverse=True)
    index = 0
    while leftover > 0 and order:
        shares[order[index % len(order)]] += 1
        leftover -= 1
        index += 1
    return shares


# The editor's template names and the shelf engine's template names.
SHELF_TEMPLATE = {
    "balanced": "balanced",
    "grocery": "value_grocery",
    "fresh": "fresh_first",
    "general": "gm_push",
    "seasonal": "seasonal_push",
}


def facing_choice(template_id: str, state, door=None):
    """The shelf choice a push sends: the matching template, plus the products on the glass as eye-level pins."""
    from open_late.shelf_model import MAX_PINS_PER_DEPT, MAX_PINS_PER_STORE, LiteChoice, sku_pos

    shelf_id = SHELF_TEMPLATE.get(template_id)
    if shelf_id is None or state is None:
        return None
    allow_pharmacy = door is None or bool(getattr(door, "allows_intense", True))
    pos = sku_pos()
    counts: dict[str, int] = {}
    pins: list[int] = []
    for row in _layout_products(template_id, state):
        for product in row:
            if product is None:
                continue
            dept = str(getattr(product, "department", "") or getattr(product, "category", "") or "")
            if dept == "pharmacy" and not allow_pharmacy:
                continue
            idx = pos.get(str(getattr(product, "id", "") or ""))
            if idx is None or idx in pins or counts.get(dept, 0) >= MAX_PINS_PER_DEPT:
                continue
            pins.append(idx)
            counts[dept] = counts.get(dept, 0) + 1
            if len(pins) >= MAX_PINS_PER_STORE:
                return LiteChoice(template_id=shelf_id, priorities=tuple(pins))
    return LiteChoice(template_id=shelf_id, priorities=tuple(pins))


def shares_for_door(shares: dict[str, int], door) -> dict[str, int]:
    """Drop pharmacy facings on a lease that does not allow the counter, keep 100."""
    cleaned = {key: int(shares.get(key, 0) or 0) for key in CATEGORY_LABELS}
    if door is not None and not bool(getattr(door, "allows_intense", True)) and cleaned.get("pharmacy", 0):
        extra = cleaned["pharmacy"]
        cleaned["pharmacy"] = 0
        target = max((key for key in cleaned if key != "pharmacy"), key=lambda key: cleaned[key], default="grocery")
        cleaned[target] = cleaned.get(target, 0) + extra
    return cleaned


def _label(text: str, size: int = 13, weight=QFont.Weight.Normal, color: str = TEXT, name: str = "", wrap: bool = False) -> QLabel:
    lab = QLabel(text)
    lab.setFont(ui_font(size, weight))
    lab.setStyleSheet(f"color: {color}; background: transparent;")
    lab.setWordWrap(wrap)
    if name:
        lab.setObjectName(name)
    return lab


def _dept_meta() -> dict[str, tuple[str, str]]:
    return {ident: (label, color) for ident, label, color in planogram_departments()}


def _dept_of(product) -> str:
    if product is None:
        return ""
    return str(getattr(product, "department", "") or getattr(product, "category", "") or "")


def department_row_blocks(row: list) -> list[tuple[str, int, int]]:
    """Contiguous same-department facings on one shelf: (dept_id, start_col, span)."""
    blocks: list[tuple[str, int, int]] = []
    index = 0
    while index < len(row):
        product = row[index]
        if product is None:
            index += 1
            continue
        dept = _dept_of(product)
        span = 1
        while index + span < len(row) and row[index + span] is not None and _dept_of(row[index + span]) == dept:
            span += 1
        if dept:
            blocks.append((dept, index, span))
        index += span
    return blocks


def _pct_label(value) -> str:
    if value is None:
        return "—"
    try:
        pct = float(value) * 100
    except (TypeError, ValueError):
        return "—"
    body = f"{pct:.1f}".rstrip("0").rstrip(".")
    return f"{body}%"


def block_sales_copy(stat: dict | None, *, width: int, include_name: str = "") -> tuple[str, str, str]:
    """Return (primary, secondary, tip). Primary always carries the dollars when known.

    Narrow blocks drop or abbreviate the share and the name, but keep the compact amount.
    """
    if not stat:
        return ("", "", "")
    sales = int(stat.get("sales") or 0)
    prior = int(stat.get("prior") or 0)
    share = stat.get("share")
    delta = stat.get("delta_pct")
    has_prior = bool(stat.get("has_prior"))
    store_total = int(stat.get("store_total") or 0)
    dollars = money_compact(sales)
    share_txt = _pct_label(share)
    if has_prior and delta is not None:
        arrow = "↑" if delta >= 0 else "↓"
        move_txt = f"{arrow}  {_pct_label(abs(delta))}"
    else:
        move_txt = "—"
    primary = dollars
    if width >= 148 and include_name:
        secondary = f"{include_name}  ·  {share_txt}  {move_txt}"
    elif width >= 118:
        secondary = f"{share_txt}  {move_txt}"
    elif width >= 78:
        secondary = move_txt
    else:
        secondary = ""
    prior_txt = money(prior) if has_prior else "—"
    share_exact = f"{share * 100:.1f}% of store" if share is not None else "no store sales yet"
    move_exact = (
        f"{'↑' if delta >= 0 else '↓'}  {abs(delta) * 100:.1f}% vs prior week"
        if has_prior and delta is not None
        else "no prior week"
    )
    name = include_name or "Department"
    tip = (
        f"{name}  ·  last week {money(sales)}  ·  {share_exact} "
        f"({money(sales)} / {money(store_total)})  ·  prior week {prior_txt}  ·  {move_exact}"
    )
    return primary, secondary, tip



# Chip typography: secondary is one step up from v3i's 8px; dollars stay a step larger.
CHIP_DOLLAR_PX = 10
CHIP_SECONDARY_PX = 9
CHIP_HEADER = 28


class ShelfCanvas(QWidget):
    """A painted 4-tier glass shelf with one product tile per facing."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("shelfCanvas")
        self.layout_products: list[list] = [[None] * 4 for _ in range(4)]
        self.heat: dict[str, float] = {}
        self.facing: dict[str, str] = {}
        self.stats: dict[str, dict] = {}
        self.blocks: list[dict] = []
        self.tile_rects: list[QRect] = []
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)

    def set_layout(
        self,
        rows: list[list],
        heat: dict[str, float] | None = None,
        facing: dict[str, str] | None = None,
        stats: dict[str, dict] | None = None,
    ) -> None:
        self.layout_products = [list(row) for row in rows]
        self.heat = dict(heat or {})
        self.facing = dict(facing or {})
        self.stats = dict(stats or {})
        self.update()

    def mouseMoveEvent(self, event) -> None:
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        tip = ""
        for block in self.blocks:
            rect = block.get("rect")
            if isinstance(rect, QRect) and rect.contains(pos):
                tip = str(block.get("tip") or "")
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
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor("#071018"))
        cabinet = QRect(6, 4, max(40, w - 12), max(40, h - 10))
        painter.setBrush(QColor("#252A2E"))
        painter.setPen(QPen(QColor("#173A55"), 1))
        painter.drawRoundedRect(cabinet, 10, 10)
        inner = cabinet.adjusted(10, 14, -10, -12)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#3A3D42"))
        painter.drawRect(inner)
        # top valance
        painter.setBrush(QColor("#26282B"))
        painter.drawRect(inner.x(), inner.y(), inner.width(), 8)
        rows = self.layout_products or [[None] * 4]
        tiers = max(1, len(rows))
        cols = max(1, max(len(row) for row in rows))
        usable = inner.adjusted(8, 12, -8, -8)
        tier_h = usable.height() / tiers
        show_sales = bool(self.stats) and tier_h >= 72
        header_h = CHIP_HEADER if show_sales else 0
        meta = _dept_meta()
        self.blocks = []
        self.tile_rects = []
        for t, row in enumerate(rows):
            y = usable.y() + int(t * tier_h)
            shelf_y = y + int(tier_h) - 11
            # rear shadow just above the glass
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, 40))
            painter.drawRect(usable.x(), shelf_y - 4, usable.width(), 4)
            glass = QLinearGradient(0, shelf_y, 0, shelf_y + 10)
            glass.setColorAt(0.0, QColor(255, 255, 255, 230))
            glass.setColorAt(0.4, QColor(210, 222, 232, 230))
            glass.setColorAt(1.0, QColor(150, 160, 170, 200))
            painter.setBrush(glass)
            painter.setPen(QPen(QColor(255, 255, 255, 90), 1))
            painter.drawRect(usable.x(), shelf_y, usable.width(), 10)
            painter.setPen(QPen(QColor(255, 255, 255, 180), 1.2))
            painter.drawLine(usable.x(), shelf_y, usable.x() + usable.width(), shelf_y)
            cell_w = usable.width() / cols
            for c, product in enumerate(row):
                if product is None:
                    continue
                tw = max(36, int(cell_w * 0.78))
                th = max(40, int(tier_h - 26 - header_h))
                cx = int(usable.x() + c * cell_w + (cell_w - tw) / 2)
                cy = shelf_y - th
                tile = QRect(cx, cy, tw, th)
                # soft reflection on the glass
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(255, 255, 255, 28))
                painter.drawRoundedRect(cx + 4, shelf_y + 2, tw - 8, 6, 2, 2)
                dept = getattr(product, "department", "") or getattr(product, "id", "")
                status = self.facing.get(str(getattr(product, "id", ""))) or self.facing.get(str(dept))
                paint_product_tile(painter, tile, product, status=status)
                self.tile_rects.append(QRect(tile))
            if not show_sales:
                continue
            for dept, start, span in department_row_blocks(row):
                x0 = int(usable.x() + start * cell_w)
                bw = int(span * cell_w)
                # A slim shelf-talker just above the tiles, spanning the aisle block.
                chip = QRect(x0 + 4, y + 2, max(28, bw - 8), header_h)
                self._paint_sales_chip(painter, chip, dept, meta)
        painter.end()

    def _paint_sales_chip(self, painter: QPainter, chip: QRect, dept: str, meta: dict) -> None:
        stat = self.stats.get(dept) or {}
        name, color = meta.get(dept, (dept.replace("_", " ").title(), "#6B7380"))
        primary, secondary, tip = block_sales_copy(stat, width=chip.width(), include_name=name)
        if not primary:
            return
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(20, 22, 24, 210))
        painter.drawRoundedRect(chip, 4, 4)
        # Department color pip, echoing the mockup's small status dots.
        painter.setBrush(QColor(color))
        painter.drawEllipse(chip.x() + 5, chip.y() + (chip.height() - 6) // 2, 6, 6)
        text_x = chip.x() + 15
        text_w = max(8, chip.width() - 20)
        two_line = bool(secondary) and chip.height() >= CHIP_HEADER and chip.width() >= 78
        painter.setPen(QColor("#F4F6FA"))
        painter.setFont(ui_font(CHIP_DOLLAR_PX, QFont.Weight.DemiBold))
        if two_line:
            # Leave a little air between the dominant dollars and the secondary line.
            dollar_h = 13
            painter.drawText(
                QRect(text_x, chip.y() + 1, text_w, dollar_h),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                painter.fontMetrics().elidedText(primary, Qt.TextElideMode.ElideRight, text_w),
            )
            self._paint_secondary_line(
                painter,
                QRect(text_x, chip.y() + 1 + dollar_h, text_w, chip.height() - (1 + dollar_h) - 1),
                secondary,
            )
        else:
            painter.drawText(
                QRect(text_x, chip.y(), text_w, chip.height()),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                painter.fontMetrics().elidedText(primary, Qt.TextElideMode.ElideRight, text_w),
            )
        self.blocks.append({
            "dept": dept,
            "name": name,
            "sales": int(stat.get("sales") or 0),
            "primary": primary,
            "secondary": secondary,
            "tip": tip,
            "rect": QRect(chip),
        })

    def _paint_secondary_line(self, painter: QPainter, rect: QRect, secondary: str) -> None:
        painter.setFont(ui_font(CHIP_SECONDARY_PX))
        arrow_at = max(secondary.find("↑"), secondary.find("↓"))
        if arrow_at < 0:
            painter.setPen(QColor("#C8CDD5"))
            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                painter.fontMetrics().elidedText(secondary, Qt.TextElideMode.ElideRight, rect.width()),
            )
            return
        prefix = secondary[:arrow_at].rstrip()
        move = secondary[arrow_at:]
        x = rect.x()
        if prefix:
            painter.setPen(QColor("#C8CDD5"))
            prefix_text = prefix + "  "
            pw = min(painter.fontMetrics().horizontalAdvance(prefix_text), max(0, rect.width() - 20))
            painter.drawText(
                QRect(x, rect.y(), pw, rect.height()),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                painter.fontMetrics().elidedText(prefix_text, Qt.TextElideMode.ElideRight, pw),
            )
            x += pw
        painter.setPen(QColor(UP if "↑" in move else DOWN))
        remain = max(8, rect.right() - x + 1)
        painter.drawText(
            QRect(x, rect.y(), remain, rect.height()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            painter.fontMetrics().elidedText(move, Qt.TextElideMode.ElideRight, remain),
        )


class PlanogramPreview(ShelfCanvas):
    """Small dashboard shelf: fewer, full-size tiles, letterboxed in the card.

    The editor's ShelfCanvas squeezes 4 tiers x 4 facings into whatever height it
    gets; in the ~110 px dashboard card that crushed tiles on top of each other and
    elided every label. The preview instead fits as many whole tiers and facings as
    keep a readable tile, sizes the cabinet to that content, and centers it.
    """

    TILE_W = 84
    TILE_H = 80
    MIN_TILE_W = 64
    MIN_TILE_H = 60
    GAP = 8
    FRAME = 8
    VALANCE = 6
    GLASS = 8
    MAX_TIERS = 4
    MAX_COLS = 6

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(170)
        self.preview_titles: list[str] = []
        self.cabinet_rect = QRect()
        self.set_layout(_layout_products("balanced"))

    def preview_grid(self, w: int, h: int) -> tuple[int, int, int, int]:
        """(tiers, cols, tile_w, tile_h) that fit a w x h widget."""
        avail_h = h - 4 - 2 * self.FRAME - self.VALANCE
        tiers, tile_h = 1, self.MIN_TILE_H
        for t in range(self.MAX_TIERS, 0, -1):
            each = (avail_h - t * (self.GLASS + self.GAP)) // t
            if each >= self.MIN_TILE_H or t == 1:
                tiers, tile_h = t, max(24, min(self.TILE_H, each))
                break
        avail_w = w - 4 - 2 * self.FRAME
        cols, tile_w = 1, self.MIN_TILE_W
        for c in range(self.MAX_COLS, 0, -1):
            each = (avail_w - (c + 1) * self.GAP) // c
            if each >= self.MIN_TILE_W or c == 1:
                cols, tile_w = c, max(24, min(self.TILE_W, each))
                break
        # Keep tiles roughly product-card shaped, never a squashed strip.
        tile_w = min(tile_w, int(tile_h * 1.25))
        tile_h = min(tile_h, int(tile_w * 1.35))
        return tiers, cols, tile_w, tile_h

    def _pick_products(self, count: int, label_w: int) -> list:
        fm = QFontMetrics(ui_font(9, QFont.Weight.DemiBold))
        flat = [p for row in self.layout_products for p in row if p is not None]
        fits = [p for p in flat if fm.horizontalAdvance(product_title(p)) <= label_w]
        picked, seen = [], set()
        for p in fits:  # one per department first, for a varied shelf
            dept = getattr(p, "department", "")
            if dept not in seen:
                seen.add(dept)
                picked.append(p)
        for p in fits:
            if p not in picked:
                picked.append(p)
        return picked[:count]

    CAPTION_H = 18

    def art_rect(self, tile: QRect) -> QRect:
        """Square art box above the caption, so package art keeps its shape."""
        side = max(12, min(tile.width() - 12, tile.height() - self.CAPTION_H - 8))
        return QRect(tile.x() + (tile.width() - side) // 2, tile.y() + 5, side, side)

    def _paint_tile(self, painter: QPainter, tile: QRect, product, status) -> None:
        painter.setPen(QPen(QColor("#D5DAE2"), 1))
        painter.setBrush(QColor("#F7F4EE"))
        painter.drawRoundedRect(tile.adjusted(1, 1, -1, -1), 7, 7)
        painter.save()
        art = self.art_rect(tile)
        painter.setClipRect(tile.adjusted(2, 2, -2, -self.CAPTION_H))
        paint_product_art(painter, art, product)
        painter.restore()
        painter.setPen(QColor(HQ_TITLE))
        painter.setFont(ui_font(9, QFont.Weight.DemiBold))
        painter.drawText(
            QRect(tile.x() + 6, tile.bottom() - self.CAPTION_H - 1, tile.width() - 12, self.CAPTION_H),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
            product_title(product),
        )
        if status and status in STATUS_COLOR:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(STATUS_COLOR[status]))
            painter.drawEllipse(tile.right() - 11, tile.y() + 5, 6, 6)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        w, h = self.width(), self.height()
        tiers, cols, tile_w, tile_h = self.preview_grid(w, h)
        products = self._pick_products(tiers * cols, tile_w - 12)
        if products and len(products) < tiers * cols:
            cols = min(cols, max(1, -(-len(products) // tiers)))
            tiers = min(tiers, max(1, -(-len(products) // cols)))
        tier_h = tile_h + self.GLASS + self.GAP
        content_w = cols * tile_w + (cols + 1) * self.GAP
        content_h = tiers * tier_h
        cab_w = content_w + 2 * self.FRAME
        cab_h = content_h + 2 * self.FRAME + self.VALANCE
        cabinet = QRect((w - cab_w) // 2, (h - cab_h) // 2, cab_w, cab_h)
        self.cabinet_rect = QRect(cabinet)
        painter.setBrush(QColor("#2F3236"))
        painter.setPen(QPen(QColor("#1A1B1C"), 1))
        painter.drawRoundedRect(cabinet, 8, 8)
        inner = cabinet.adjusted(self.FRAME, self.FRAME, -self.FRAME, -self.FRAME)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#3A3D42"))
        painter.drawRect(inner)
        painter.setBrush(QColor("#26282B"))
        painter.drawRect(inner.x(), inner.y(), inner.width(), self.VALANCE)
        self.blocks = []
        self.tile_rects = []
        self.preview_titles = []
        top = inner.y() + self.VALANCE
        for t in range(tiers):
            y = top + t * tier_h
            shelf_y = y + self.GAP + tile_h
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, 40))
            painter.drawRect(inner.x(), shelf_y - 3, inner.width(), 3)
            glass = QLinearGradient(0, shelf_y, 0, shelf_y + self.GLASS)
            glass.setColorAt(0.0, QColor(255, 255, 255, 230))
            glass.setColorAt(0.4, QColor(210, 222, 232, 230))
            glass.setColorAt(1.0, QColor(150, 160, 170, 200))
            painter.setBrush(glass)
            painter.setPen(QPen(QColor(255, 255, 255, 90), 1))
            painter.drawRect(inner.x(), shelf_y, inner.width(), self.GLASS)
            for c in range(cols):
                i = t * cols + c
                if i >= len(products):
                    break
                product = products[i]
                tile = QRect(inner.x() + self.GAP + c * (tile_w + self.GAP), shelf_y - tile_h, tile_w, tile_h)
                dept = getattr(product, "department", "") or getattr(product, "id", "")
                status = self.facing.get(str(getattr(product, "id", ""))) or self.facing.get(str(dept))
                self._paint_tile(painter, tile, product, status)
                self.tile_rects.append(QRect(tile))
                self.preview_titles.append(product_title(product))
        painter.end()


class PlanogramPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("planogramPage")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            QWidget#planogramPage {{ background:{FRAME}; color:#F4F8FF; }}
            QWidget#planogramEditorBar {{ background:{FRAME}; border-bottom:1px solid {FRAME_LINE}; }}
            QFrame#card {{ background:#0E2035; border:1px solid #173A55; border-radius:7px; }}
            QLabel {{ color:#F4F8FF; background:transparent; }}
            QLabel#pageDeck, QLabel#skuRailHint, QLabel#skuRailPage {{ color:#7897AE; }}
            QLineEdit, QComboBox {{ background:#0B1A2D; color:#F4F8FF; border:1px solid #173A55; border-radius:4px; padding:5px 8px; }}
            QPushButton {{ background:{FRAME_BTN}; color:{FRAME_INK}; border:1px solid {FRAME_BTN_LINE}; border-radius: 8px; padding:6px 14px; font-weight:600; }}
            QPushButton:hover {{ background:#16405A; border-color:#16884C; }}
            QPushButton#templateChipOn, QPushButton#pushStores {{ background:#19E86A; color:#03150A; border:1px solid #72FFA8; font-weight:800; }}
            QPushButton#templateChip {{ background:#0B1A2D; color:#7897AE; }}
            QScrollArea, QScrollArea > QWidget > QWidget {{ background:transparent; border:none; }}
        """)
        self.host = None
        self.fixture_id = "glass_4"
        self.template_id = "balanced"
        self.dept_filter = ""
        self.sku_query = ""
        self.sku_page = 0
        self.saved = True
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.top = QHBoxLayout()
        self.top.setContentsMargins(12, 4, 12, 4)
        self.title = _label("PLANOGRAMS  ·  FLOOR & SHELF COMMAND", 15, QFont.Weight.Bold, "#F4F8FF", "pageTitle")
        self.crumb = _label("Fixtures  /  Glass Shelf 4-Tier", 11, color=HQ_MUTED, name="pageDeck")
        head = QVBoxLayout()
        head.setSpacing(0)
        head.addWidget(self.title)
        head.addWidget(self.crumb)
        self.title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.crumb.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.top.addLayout(head, stretch=1)
        self.view_btns = {}
        self.floor = None
        for key, text in (
            ("workbench", "Planogram View"),
            ("floor", "Floor Plan"),
            ("aisles", "Store aisles"),
            ("editor", "Shelf Editor"),
            ("layout", "Item Placement"),
            ("endcaps", "Endcaps & Displays"),
        ):
            vb = QPushButton(text)
            vb.setObjectName("templateChipOn" if key == "workbench" else "templateChip")
            vb.clicked.connect(lambda _=False, k=key: self._show_view(k))
            self.view_btns[key] = vb
            self.top.addWidget(vb, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.layout_view = None
        self.push = QPushButton("Push to stores")
        self.push.setObjectName("pushStores")
        self.push.clicked.connect(self._push)
        self.top.addWidget(self.push, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.editor_bar = QWidget()
        self.editor_bar.setObjectName("planogramEditorBar")
        # Styled by the page-local dark stylesheet so the global HQ shell is untouched.
        self.editor_bar.setLayout(self.top)
        root.addWidget(self.editor_bar)

        body = QHBoxLayout()
        body.setContentsMargins(12, 0, 12, 8)
        body.setSpacing(8)
        # Fixtures
        fixtures = QFrame()
        fixtures.setObjectName("card")
        fixtures.setMinimumWidth(156)
        fixtures.setMaximumWidth(200)
        fl = QVBoxLayout(fixtures)
        fl.setContentsMargins(8, 8, 8, 8)
        fl.addWidget(_label("FIXTURES", 11, QFont.Weight.DemiBold, HQ_FAINT))
        self.fixture_host = QWidget()
        self.fixture_box = QVBoxLayout(self.fixture_host)
        self.fixture_box.setContentsMargins(0, 0, 0, 0)
        self.fixture_box.setSpacing(4)
        self.fixture_scroll = QScrollArea()
        self.fixture_scroll.setWidgetResizable(True)
        self.fixture_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.fixture_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.fixture_scroll.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
        self.fixture_scroll.setMinimumHeight(80)
        self.fixture_scroll.setWidget(self.fixture_host)
        fl.addWidget(self.fixture_scroll, stretch=1)
        body.addWidget(fixtures)

        # Center
        center = QVBoxLayout()
        center.setSpacing(8)
        self.canvas_caption = _label("GLASS SHELF 4-TIER  ·  48\"W", 13, QFont.Weight.DemiBold, HQ_FAINT)
        center.addWidget(self.canvas_caption)
        chips = QHBoxLayout()
        chips.setContentsMargins(0, 0, 0, 0)
        chips.addWidget(_label("TEMPLATE", 11, QFont.Weight.DemiBold, HQ_FAINT))
        self.chip_buttons: dict[str, QPushButton] = {}
        for ident, name in TEMPLATES:
            btn = QPushButton(name)
            btn.setObjectName("templateChipOn" if ident == self.template_id else "templateChip")
            btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            btn.setMinimumHeight(26)
            btn.setMinimumWidth(btn.fontMetrics().horizontalAdvance(name) + 36)
            btn.clicked.connect(lambda _=False, i=ident: self._set_template(i))
            self.chip_buttons[ident] = btn
            chips.addWidget(btn)
        chips.addStretch(1)
        chip_host = QWidget()
        chip_host.setLayout(chips)
        chip_host.setMinimumWidth(sum(btn.minimumWidth() + 8 for btn in self.chip_buttons.values()) + 90)
        chip_host.setMinimumHeight(30)
        chip_scroll = QScrollArea()
        chip_scroll.setObjectName("templateChips")
        chip_scroll.setWidget(chip_host)
        chip_scroll.setWidgetResizable(False)
        chip_scroll.setFrameShape(QFrame.Shape.NoFrame)
        chip_scroll.setFixedHeight(36)
        chip_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        chip_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        chip_scroll.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        center.addWidget(chip_scroll)
        self.canvas = ShelfCanvas()
        self.canvas.set_layout(_layout_products("balanced"))
        center.addWidget(self.canvas, stretch=1)
        legend = QVBoxLayout()
        legend.setContentsMargins(0, 0, 0, 0)
        legend.setSpacing(2)
        self.save_lab = _label("All changes saved", 12, color=OPEN_GREEN, name="planoSaved")
        legend.addWidget(self.save_lab)
        legend.addWidget(_label(
            "SALES HEAT   Low to high     FACING STATUS   Optimal, at risk, overstock",
            11,
            color=HQ_MUTED,
            wrap=True,
        ))
        center.addLayout(legend)
        body.addLayout(center, stretch=1)

        # SKU rail
        rail = QFrame()
        rail.setObjectName("card")
        rail.setMinimumWidth(180)
        rail.setMaximumWidth(240)
        rl = QVBoxLayout(rail)
        rl.setContentsMargins(12, 12, 12, 12)
        rl.addWidget(_label("SKU RAIL", 11, QFont.Weight.DemiBold, HQ_FAINT, name="skuRailTitle"))
        self.sku_search = QLineEdit()
        self.sku_search.setObjectName("topSearch")
        self.sku_search.setPlaceholderText("Search SKUs…")
        self.sku_search.textChanged.connect(self._on_sku_search)
        rl.addWidget(self.sku_search)
        self.sku_dept = QComboBox()
        self.sku_dept.setObjectName("skuDeptFilter")
        self.sku_dept.addItem("All departments", "")
        for ident, label, _color in planogram_departments():
            self.sku_dept.addItem(label, ident)
        self.sku_dept.currentIndexChanged.connect(self._on_sku_dept_changed)
        rl.addWidget(self.sku_dept)
        self.sku_host = QWidget()
        self.sku_host.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.sku_box = QVBoxLayout(self.sku_host)
        self.sku_box.setContentsMargins(0, 0, 0, 0)
        self.sku_box.setSpacing(6)
        self.sku_scroll = QScrollArea()
        self.sku_scroll.setObjectName("skuRailScroll")
        self.sku_scroll.setWidgetResizable(True)
        self.sku_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.sku_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sku_scroll.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
        self.sku_scroll.setMinimumHeight(80)
        self.sku_scroll.setWidget(self.sku_host)
        rl.addWidget(self.sku_scroll, stretch=1)
        self.sku_hint = _label("", 10, color=HQ_MUTED, wrap=True, name="skuRailHint")
        rl.addWidget(self.sku_hint)
        pager = QHBoxLayout()
        pager.setContentsMargins(0, 0, 0, 0)
        self.sku_prev = QPushButton("Prev")
        self.sku_prev.setObjectName("skuRailPrev")
        self.sku_prev.clicked.connect(lambda: self._step_sku_page(-1))
        self.sku_page_lab = _label("", 10, color=HQ_MUTED, name="skuRailPage")
        self.sku_next = QPushButton("Next")
        self.sku_next.setObjectName("skuRailNext")
        self.sku_next.clicked.connect(lambda: self._step_sku_page(1))
        pager.addWidget(self.sku_prev)
        pager.addWidget(self.sku_page_lab, stretch=1)
        pager.addWidget(self.sku_next)
        rl.addLayout(pager)
        body.addWidget(rail)
        self.editor = QWidget()
        self.editor.setLayout(body)
        from open_late.ui.osprey_docs import StoreFloorBoard

        self.floor_board = StoreFloorBoard()
        self.floor_board.canvas.picked.connect(self._from_floor)
        from open_late.ui.plano_bench import PlanoWorkbench

        self.workbench = PlanoWorkbench()
        from open_late.ui.dept_floor import DeptFloorView

        self.dept_floor = DeptFloorView()
        self.dept_floor.skuPicked.connect(self._from_dept_sku)
        self.dept_floor.movePicked.connect(self._from_dept_move)
        self.dept_floor.navPicked.connect(self._show_view)
        self.dept_floor.deptPicked.connect(self._from_dept_zone)
        from open_late.ui.living_store import LivingStoreView

        self.living = LivingStoreView()
        self.living.canvas.timer.stop()
        self.living.skuPicked.connect(self._from_dept_sku)
        self.views = QStackedWidget()
        self.views.addWidget(self.workbench)
        self.views.addWidget(self.floor_board)
        self.views.addWidget(self.dept_floor)
        self.views.addWidget(self.living)
        self.views.addWidget(self.editor)
        self.views.setCurrentWidget(self.workbench)
        root.addWidget(self.views, stretch=1)
        self.push.setVisible(False)

    def hideEvent(self, event) -> None:
        living = getattr(self, "living", None)
        if living is not None:
            living.canvas.timer.stop()
        super().hideEvent(event)

    def _from_floor(self, ident: str) -> None:
        state = getattr(self.host, "state", None) if self.host is not None else None
        if state is None or not getattr(state, "doors", None):
            self.floor_board.note.setText("The store layout opens in a corporate game.")
            self.floor_board.note.setVisible(True)
            return
        self._layout_target = str(ident or "")
        self._show_view("layout")

    def _from_dept_move(self, ident: str) -> None:
        self._layout_target = str(ident or "")
        self._show_view("layout")

    def _from_dept_zone(self, dept: str) -> None:
        ident = str(dept or "")
        if not ident:
            return
        index = self.sku_dept.findData(ident)
        if index >= 0:
            self.sku_dept.setCurrentIndex(index)
        self.crumb.setText(f"Planograms  /  {ident.replace('_', ' ')}")

    def _from_dept_sku(self, ident: str) -> None:
        host = self.host
        pid = str(ident or "")
        if host is None or not pid:
            return
        host.inventory_focus_sku = pid
        if hasattr(host, "_open_app"):
            host._open_app("inventory")

    def _show_view(self, key: str) -> None:
        if key in ("layout", "endcaps") and self.layout_view is None:
            from open_late.ui.hq_store_layout import StoreLayoutView

            self.layout_view = StoreLayoutView(self)
            self.floor = self.layout_view.floor
            self.views.addWidget(self.layout_view)
        for k, vb in self.view_btns.items():
            vb.setObjectName("templateChipOn" if k == key else "templateChip")
            vb.style().unpolish(vb)
            vb.style().polish(vb)
        if key in ("layout", "endcaps"):
            self.views.setCurrentWidget(self.layout_view)
        elif key == "editor":
            self.views.setCurrentWidget(self.editor)
        elif key == "workbench":
            self.views.setCurrentWidget(self.workbench)
        elif key == "floor":
            self.views.setCurrentWidget(self.dept_floor)
        elif key == "aisles":
            self.views.setCurrentWidget(self.living)
        else:
            self.views.setCurrentWidget(self.floor_board)
            self.floor_board.set_mode("layout")
        self.editor_bar.setVisible(True)
        self.push.setVisible(key == "editor")
        if getattr(self, "living", None) is not None:
            if key == "aisles":
                self.living.canvas.timer.start()
            else:
                self.living.canvas.timer.stop()
        pending = getattr(self, "_layout_target", "")
        self._layout_target = ""
        if key in ("layout", "endcaps") and self.layout_view is not None:
            self.layout_view.set_board("endcaps" if key == "endcaps" else "layout")
        self.rebuild()
        if pending and key in ("layout", "endcaps") and self.layout_view is not None:
            self.layout_view.select_target(pending)
        if pending and str(pending).endswith((".F", ".B")):
            self.crumb.setText(f"Endcaps  /  {pending}")
        elif key == "endcaps" and self.layout_view is not None:
            self.layout_view.focus_endcaps()
            self.crumb.setText("Endcaps  /  three products on the cap")

    def rebuild(self) -> None:
        current = self.views.currentWidget()
        if self.layout_view is not None and current is self.layout_view:
            self.crumb.setText("Store layout  /  aisles, templates and eye-level picks")
            self.layout_view.refresh()
            return
        self._fill_fixtures()
        self._sync_dept_filter()
        self._fill_skus()
        if current is getattr(self, "workbench", None):
            state = self.host.state if self.host is not None else None
            self.crumb.setText("Planograms  /  the shelf")
            self.workbench.load(state, self.template_id)
            return
        if current is getattr(self, "dept_floor", None):
            self.crumb.setText("Planograms  /  floor plan")
            self._load_dept_floor()
            return
        if current is getattr(self, "living", None):
            self.crumb.setText("Planograms  /  store aisles")
            self._load_living()
            return
        if current is self.floor_board:
            self.floor_board.load(self.host)
            return
        self._apply_heat()
        fixture = next((item for item in FIXTURES if item[0] == self.fixture_id), FIXTURES[0])
        self.canvas_caption.setText(f"{fixture[1].upper()}  ·  {fixture[2].split('×')[0].strip()}")
        self.crumb.setText(f"Fixtures  /  {fixture[1]}")
        self.save_lab.setText("All changes saved" if self.saved else "Unsaved layout")
        save_css = f"color: {'#1F9A56' if self.saved else '#C9A227'}; background: transparent;"
        if getattr(self, "_x_save_css", None) != save_css:
            self.save_lab.setStyleSheet(save_css)
            self._x_save_css = save_css

    def _load_dept_floor(self) -> None:
        state = getattr(self.host, "state", None) if self.host is not None else None
        door = None
        layout = None
        products = {}
        if state is not None and getattr(state, "doors", None):
            products = getattr(state, "products", {}) or {}
            door = next((item for item in state.doors if getattr(item, "status", "") == "open"), state.doors[0])
            try:
                from open_late.shelves import compile_for, shelves_on

                if shelves_on(state):
                    layout = compile_for(state, door)
            except Exception:
                layout = None
        self.dept_floor.load(layout, products, door=door)

    def _load_living(self) -> None:
        state = getattr(self.host, "state", None) if self.host is not None else None
        door = None
        layout = None
        products = {}
        if state is not None and getattr(state, "doors", None):
            products = getattr(state, "products", {}) or {}
            door = next((item for item in state.doors if getattr(item, "status", "") == "open"), state.doors[0])
            try:
                from open_late.shelves import compile_for, shelves_on

                if shelves_on(state):
                    layout = compile_for(state, door)
            except Exception:
                layout = None
        self.living.load(layout, products, door=door)

    def _fill_fixtures(self) -> None:
        # The fixture list only depends on which fixture is picked; keep it otherwise.
        if getattr(self, "_x_fixture_built", None) == self.fixture_id and self.fixture_box.count() == len(FIXTURES):
            return
        self._x_fixture_built = self.fixture_id
        while self.fixture_box.count():
            item = self.fixture_box.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        for ident, name, size in FIXTURES:
            row = QFrame()
            row.setObjectName("fixtureRowOn" if ident == self.fixture_id else "fixtureRow")
            row.setCursor(Qt.CursorShape.PointingHandCursor)
            box = QVBoxLayout(row)
            box.setContentsMargins(6, 4, 6, 4)
            box.setSpacing(1)
            box.addWidget(_label(name, 12, QFont.Weight.DemiBold))
            box.addWidget(_label(size, 10, color=HQ_MUTED))
            row.mousePressEvent = lambda event, i=ident: self._set_fixture(i)  # noqa: E731
            self.fixture_box.addWidget(row)

    def _sync_dept_filter(self) -> None:
        # Keep the combo in sync without rebuilding it on every refresh.
        combo = getattr(self, "sku_dept", None)
        if combo is None:
            return
        combo.blockSignals(True)
        wanted = {ident: label for ident, label, _color in planogram_departments()}
        existing = {combo.itemData(i): i for i in range(combo.count())}
        if set(existing) - {""} != set(wanted):
            combo.clear()
            combo.addItem("All departments", "")
            for ident, label, _color in planogram_departments():
                combo.addItem(label, ident)
        index = combo.findData(self.dept_filter)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)

    def _on_sku_dept_changed(self, _index: int) -> None:
        combo = getattr(self, "sku_dept", None)
        ident = ""
        if combo is not None:
            ident = str(combo.currentData() or "")
        self._set_dept(ident)

    def _sku_entries(self) -> tuple[list[tuple[str, str, object]], bool]:
        """Return ((dept_id, dept_label, product), ...) and whether this is the mixed All view."""
        host = self.host
        state = host.state if host is not None else None
        grouped = products_by_department(state)
        query = (self.sku_query or "").strip().lower()
        entries: list[tuple[str, str, object]] = []
        mixed = not self.dept_filter and not query
        for ident, label, _color in planogram_departments():
            if self.dept_filter and ident != self.dept_filter:
                continue
            rows = list(grouped.get(ident, []))
            if query:
                rows = [product for product in rows if query in _sku_blob(product, ident, label)]
            if mixed:
                rows = rows[:SKU_RAIL_MIXED]
            for product in rows:
                entries.append((ident, label, product))
        return entries, mixed

    def _sku_shape(self, page_rows) -> tuple:
        shape = []
        last = None
        for ident, _label_text, _product in page_rows:
            if ident != last:
                shape.append(("h", ident))
                last = ident
            shape.append(("r",))
        return tuple(shape)

    def _refill_skus_in_place(self, page_rows) -> bool:
        """Same rail shape as last time: retarget the existing tiles and labels."""
        cache = getattr(self, "_x_sku_cache", None)
        if not cache or not page_rows or cache["shape"] != self._sku_shape(page_rows):
            return False
        rows = iter(cache["rows"])
        headers = iter(cache["headers"])
        last = None
        for ident, label, product in page_rows:
            if ident != last:
                header = next(headers)
                if header.text() != label:
                    header.setText(label)
                last = ident
            tile, title_lab, sku_lab = next(rows)
            name = getattr(product, "name", "") or getattr(product, "id", "")
            sku = getattr(product, "id", "")
            title = product_title(product) or name
            if title_lab.text() != title:
                title_lab.setText(title)
            sku_text = f"SKU: {sku}  ·  {label}"
            if sku_lab.text() != sku_text:
                sku_lab.setText(sku_text)
            tile.set_product(product, tile.status)
        return True

    def _fill_skus(self) -> None:
        entries, mixed = self._sku_entries()
        total = len(entries)
        if mixed:
            page_rows = entries
            start = 0
        else:
            pages = max(1, (total + SKU_RAIL_PAGE - 1) // SKU_RAIL_PAGE) if total else 1
            if self.sku_page >= pages:
                self.sku_page = pages - 1
            if self.sku_page < 0:
                self.sku_page = 0
            start = self.sku_page * SKU_RAIL_PAGE
            page_rows = entries[start:start + SKU_RAIL_PAGE]
        if self._refill_skus_in_place(page_rows):
            self._finish_sku_fill(total, start, len(page_rows), mixed)
            return
        self._x_sku_cache = None
        while self.sku_box.count():
            item = self.sku_box.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        last_dept = None
        count = 0
        cache = {"shape": self._sku_shape(page_rows), "headers": [], "rows": []}
        for ident, label, product in page_rows:
            if ident != last_dept:
                header = _label(label, 11, QFont.Weight.DemiBold, HQ_FAINT, name=f"skuDeptHeader_{ident}")
                self.sku_box.addWidget(header)
                cache["headers"].append(header)
                last_dept = ident
            name = getattr(product, "name", "") or getattr(product, "id", "")
            sku = getattr(product, "id", "")
            row = QFrame()
            row.setObjectName("skuRow")
            box = QHBoxLayout(row)
            box.setContentsMargins(6, 6, 6, 6)
            tile = ProductTile(product, compact=True)
            tile.setFixedSize(64, 72)
            box.addWidget(tile)
            col = QVBoxLayout()
            col.setSpacing(0)
            title_lab = _label(product_title(product) or name, 12, QFont.Weight.DemiBold, wrap=True)
            title_lab.setToolTip(product_title(product) or name)
            sku_lab = _label(f"SKU: {sku}  ·  {label}", 10, color=HQ_MUTED, wrap=True)
            sku_lab.setToolTip(f"{sku}  ·  {name}")
            col.addWidget(title_lab)
            col.addWidget(sku_lab)
            cache["rows"].append((tile, title_lab, sku_lab))
            box.addLayout(col, stretch=1)
            self.sku_box.addWidget(row)
            count += 1
        if count == 0:
            self.sku_box.addWidget(_label("No SKUs in this filter.", 12, color=HQ_MUTED))
        else:
            self._x_sku_cache = cache
        self.sku_box.addStretch(1)
        self._finish_sku_fill(total, start, count, mixed)

    def _finish_sku_fill(self, total: int, start: int, count: int, mixed: bool) -> None:
        self.sku_host.setMinimumHeight(0)
        self.sku_host.updateGeometry()
        scroll = getattr(self, "sku_scroll", None)
        if scroll is not None:
            scroll.verticalScrollBar().setValue(0)
        self._sync_sku_pager(total, start, count, mixed)

    def _sync_sku_pager(self, total: int, start: int, shown: int, mixed: bool) -> None:
        if mixed:
            self.sku_hint.setText(
                "Showing a few families from every department. Pick a department or search to page the rest."
            )
            self.sku_page_lab.setText(f"{total} on the rail")
            self.sku_prev.setEnabled(False)
            self.sku_next.setEnabled(False)
            self.sku_prev.setVisible(True)
            self.sku_next.setVisible(True)
            return
        end = start + shown
        if total == 0:
            self.sku_hint.setText("")
            self.sku_page_lab.setText("0 SKUs")
            self.sku_prev.setEnabled(False)
            self.sku_next.setEnabled(False)
            return
        self.sku_hint.setText("")
        self.sku_page_lab.setText(f"{start + 1}–{end} of {total}")
        self.sku_prev.setEnabled(start > 0)
        self.sku_next.setEnabled(end < total)

    def _step_sku_page(self, delta: int) -> None:
        self.sku_page += delta
        self._fill_skus()

    def _apply_heat(self) -> None:
        host = self.host
        state = host.state if host is not None else None
        heat: dict[str, float] = {}
        facing: dict[str, str] = {}
        if state is not None:
            kind, scope_id = host.shell.scope if host is not None else ("all", None)
            ids = scoped_store_ids(state, kind, scope_id) if host is not None else []
            store_id = ids[0] if ids else "evansville"
            sales = department_sales(state, store_id, days=7)
            peak = max(sales.values()) if sales and max(sales.values()) > 0 else 1
            for dept, amount in sales.items():
                heat[dept] = amount / peak
                if amount <= 0:
                    facing[dept] = "risk"
                elif heat[dept] >= 0.7:
                    facing[dept] = "optimal"
                else:
                    facing[dept] = "optimal"
        rows = _layout_products(self.template_id, state)
        stats = {}
        if state is not None:
            try:
                stats = department_week_compare(state, store_id, days=7)
            except Exception:
                stats = {}
        self.canvas.set_layout(rows, heat, facing, stats=stats)

    def _set_fixture(self, ident: str) -> None:
        self.fixture_id = ident
        self.saved = False
        self.rebuild()

    def _set_template(self, ident: str) -> None:
        self.template_id = ident
        for key, btn in self.chip_buttons.items():
            btn.setObjectName("templateChipOn" if key == ident else "templateChip")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.saved = False
        self.rebuild()

    def _set_dept(self, ident: str) -> None:
        self.dept_filter = ident or ""
        self.sku_page = 0
        self._sync_dept_filter()
        self._fill_skus()

    def _on_sku_search(self, text: str) -> None:
        self.sku_query = text
        self.sku_page = 0
        self._fill_skus()

    def _push(self) -> None:
        host = self.host
        if host is None or getattr(host, "state", None) is None:
            return
        state = host.state
        shares = template_shares(self.template_id, state)
        if sum(shares.values()) != 100:
            host._say("This template has no facings to push.")
            return
        kind, scope_id = host.shell.scope if getattr(host, "shell", None) is not None else ("all", None)
        ids = scoped_store_ids(state, kind, scope_id)
        if not ids:
            host._say("No stores are on this scope.")
            return
        from open_late.shelves import apply_layout

        notes: list[str] = []
        applied = 0
        for store_id in ids:
            door = door_by_id(state, store_id) if door_by_id is not None else None
            payload = shares_for_door(shares, door)
            choice = facing_choice(self.template_id, state, door)
            if choice is not None:
                try:
                    layout_note, _preview = apply_layout(state, [store_id], choice)
                except Exception:
                    layout_note = "The shelves could not take those facings."
                if layout_note and not layout_note.startswith(("Reset sent", "Nothing changed")):
                    notes.append(layout_note)
            # Shares are written after the shelf reset, which also stores a derived mix.
            try:
                text = set_planogram(state, store_id, payload)
            except Exception:
                text = "The engine cannot take a planogram push."
            if text:
                notes.append(text)
            else:
                applied += 1
        self.saved = True
        self.rebuild()
        if hasattr(host, "_save"):
            host._save()
        if hasattr(host, "refresh"):
            host.refresh()
        if notes and not applied:
            host._say(" ".join(notes))
            return
        cities = []
        if door_by_id is not None:
            for store_id in ids:
                door = door_by_id(state, store_id)
                if door is not None:
                    cities.append(door.city)
        where = ", ".join(cities) if cities else f"{applied} store" + ("s" if applied != 1 else "")
        extra = (" " + " ".join(notes)) if notes else ""
        host._say(
            f"Planogram pushed to {where}. The wall adds up. "
            f"The manager has to catch up to it.{extra}"
        )
