"""Store layout (Shoppers + Planograms LITE, phase 1).

Left: the store's aisles (move up/down, add, remove, change department). Center: the floor
plan. Click a gondola, an endcap, a perimeter cooler, the action alley, or a checkout lane
and the bay and the pick list follow that click. The five Lite templates and the score sit
with the floor. Right: up to 3 eye-level picks per department, or the 3 products on one
endcap. Apply sends the reset (labor + new fixtures, short sales dip).
Nothing here is drag-and-drop. Built only when the player opens the view.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from open_late import shelves as SH
from open_late.planogram_api import TEMPLATE_ORDER, TEMPLATES, check_pins, shipped_facts
from open_late.shelf_model import (
    MAX_PINS_PER_DEPT,
    MAX_PINS_PER_STORE,
    LiteChoice,
    aisle_label,
    formats,
    pack_choice,
    sku_index_v1,
)
from open_late.text import money
from open_late.ui.hq_product import paint_product_tile, product_title
from open_late.ui.theme import HQ_FAINT, HQ_MUTED, HQ_TITLE, OPEN_GREEN, RR_BLUE, TEXT

FIXED_NAMES = {
    "PR": "Produce", "MD": "Meat & dairy", "FZ": "Frozen", "SN": "Seasonal", "RX": "Pharmacy",
    "AA": "Action alley", "CK": "Checkout",
}
SKU_LIST_LEN = 24
CHIP_NAMES = {"balanced": "Balanced", "fresh_first": "Fresh first", "value_grocery": "Value",
              "gm_push": "GM push", "seasonal_push": "Seasonal"}


def _label(text: str, size: int = 12, weight=QFont.Weight.Normal, color: str = TEXT, name: str = "",
           wrap: bool = False) -> QLabel:
    lab = QLabel(text)
    font = lab.font()
    font.setPointSize(size)
    font.setWeight(weight)
    lab.setFont(font)
    lab.setStyleSheet(f"color: {color}; background: transparent;")
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


def _dept_name(dept: str) -> str:
    try:
        from open_late.text import CATEGORY_LABELS

        return CATEGORY_LABELS.get(dept, dept.replace("_", " ").title())
    except Exception:  # pragma: no cover
        return dept.replace("_", " ").title()


class BayCanvas(QWidget):
    """Paint one compiled bay and let the player inspect its real SKU/facing placements."""

    productSelected = Signal(object, str, int, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("bayCanvas")
        self.bay = None
        self.products: dict = {}
        self.pins: set[int] = set()
        self.hits: list[tuple[QRect, object, str, int, bool]] = []
        self.selected_product_id = ""
        self.setMinimumHeight(96)
        self.setMaximumHeight(120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def set_bay(self, bay, products: dict, pins: set[int]) -> None:
        self.bay, self.products, self.pins = bay, products, set(pins)
        self.update()

    def mousePressEvent(self, event) -> None:
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        for rect, product, tier, facings, pinned in reversed(self.hits):
            if rect.contains(pos):
                self.selected_product_id = str(getattr(product, "id", "") or "")
                self.productSelected.emit(product, tier, facings, pinned)
                self.update()
                event.accept()
                return
        super().mousePressEvent(event)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        self.hits = []
        painter.fillRect(0, 0, w, h, QColor("#071018"))
        cab = QRect(4, 2, max(40, w - 8), max(40, h - 6))
        painter.setBrush(QColor("#2F3236"))
        painter.setPen(QPen(QColor("#1A1B1C"), 1))
        painter.drawRoundedRect(cab, 10, 10)
        inner = cab.adjusted(10, 12, -10, -10)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#3A3D42"))
        painter.drawRect(inner)
        bay = self.bay
        if bay is None:
            painter.setPen(QColor("#C9D1DB"))
            painter.drawText(inner, Qt.AlignmentFlag.AlignCenter, "No bay on this aisle.")
            painter.end()
            return
        ids = sku_index_v1()
        tiers = list(bay.tiers) or [("eye", ())]
        tier_h = inner.height() / len(tiers)
        tag_w = 46
        for t, (tier, items) in enumerate(tiers):
            y = inner.y() + int(t * tier_h)
            shelf_y = y + int(tier_h) - 9
            glass = QLinearGradient(0, shelf_y, 0, shelf_y + 8)
            glass.setColorAt(0.0, QColor("#8AA4BE"))
            glass.setColorAt(1.0, QColor("#243656"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(glass)
            painter.drawRect(inner.x(), shelf_y, inner.width(), 8)
            painter.setPen(QColor("#FFC40A") if tier == "eye" else QColor("#AEB8C4"))
            f = painter.font()
            f.setPointSize(8)
            f.setBold(tier == "eye")
            painter.setFont(f)
            painter.drawText(QRect(inner.x() + 2, y + 2, tag_w - 4, 16), Qt.AlignmentFlag.AlignLeft,
                             "EYE" if tier == "eye" else tier.upper()[:6])
            total = sum(max(1, fc) for _s, fc in items) or 1
            x = inner.x() + tag_w
            span = inner.width() - tag_w - 4
            for sku, fc in items:
                cw = span * max(1, fc) / total
                th = max(26, int(tier_h - 22))
                tile = QRect(int(x) + 2, shelf_y - th, max(20, int(cw) - 4), th)
                pid = ids[sku] if 0 <= sku < len(ids) else ""
                product = self.products.get(pid)
                if product is not None:
                    paint_product_tile(painter, tile, product, status=None)
                    pinned = sku in self.pins
                    self.hits.append((QRect(tile), product, tier, int(fc), pinned))
                    if str(getattr(product, "id", "") or "") == self.selected_product_id:
                        painter.setBrush(Qt.BrushStyle.NoBrush)
                        painter.setPen(QPen(QColor(OPEN_GREEN), 3))
                        painter.drawRoundedRect(tile.adjusted(-2, -2, 2, 2), 6, 6)
                else:
                    painter.setBrush(QColor("#1A2A40"))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawRoundedRect(tile, 4, 4)
                if sku in self.pins:
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.setPen(QPen(QColor(RR_BLUE), 2.5))
                    painter.drawRoundedRect(tile.adjusted(-1, -1, 1, 1), 5, 5)
                painter.setPen(QColor("#E8EEF6"))
                f.setBold(True)
                painter.setFont(f)
                painter.drawText(QRect(tile.x(), tile.y() + 2, tile.width() - 6, 14),
                                 Qt.AlignmentFlag.AlignRight, f"×{fc}")
                x += cw
        painter.end()


class StoreLayoutView(QWidget):
    def __init__(self, page, parent=None):
        super().__init__(parent)
        self.setObjectName("storeLayoutView")
        self.page = page
        self.door_id = ""
        self.draft_floor = None
        self.template_id = "balanced"
        self.pins: list[int] = []
        self.endcaps: dict[str, tuple[int, ...]] = {}
        self.facing_targets: dict[int, int] = {}
        self.aisle_uid = ""
        self.bay_index = 0
        self.pick_mode = "eye"  # "eye" or an endcap bay key
        self.board = "layout"
        self.pick_dept = "grocery"
        self.last_preview: dict | None = None
        self._busy = False
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 0, 12, 8)
        root.setSpacing(6)

        head = QHBoxLayout()
        head.addWidget(_label("STORE", 11, QFont.Weight.DemiBold, HQ_FAINT))
        self.store_combo = QComboBox()
        self.store_combo.setObjectName("layoutStore")
        self.store_combo.currentIndexChanged.connect(self._on_store)
        head.addWidget(self.store_combo)
        self.status = _label("", 12, color=HQ_MUTED, name="layoutStatus")
        self.status.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        head.addWidget(self.status, stretch=1)
        self.reset_btn = QPushButton("Discard changes")
        self.reset_btn.setObjectName("layoutDiscard")
        self.reset_btn.clicked.connect(self._discard)
        head.addWidget(self.reset_btn)
        self.apply_btn = QPushButton("Apply reset")
        self.apply_btn.setObjectName("pushStores")
        self.apply_btn.clicked.connect(self._apply)
        head.addWidget(self.apply_btn)
        root.addLayout(head)

        body = QHBoxLayout()
        body.setSpacing(12)
        # Aisles
        left = QFrame()
        left.setObjectName("card")
        left.setMinimumWidth(156)
        left.setMaximumWidth(210)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(12, 12, 12, 12)
        ll.addWidget(_label("AISLES", 11, QFont.Weight.DemiBold, HQ_FAINT))
        self.aisles = QListWidget()
        self.aisles.setObjectName("aisleList")
        self.aisles.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
        self.aisles.setMinimumHeight(72)
        self.aisles.currentRowChanged.connect(self._on_aisle)
        ll.addWidget(self.aisles, stretch=1)
        row1 = QHBoxLayout()
        self.up_btn = QPushButton("Up")
        self.up_btn.clicked.connect(lambda: self._move(-1))
        self.down_btn = QPushButton("Down")
        self.down_btn.clicked.connect(lambda: self._move(1))
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.clicked.connect(self._remove)
        for b in (self.up_btn, self.down_btn, self.remove_btn):
            b.setStyleSheet("QPushButton { padding: 2px 4px; }")
            row1.addWidget(b)
        ll.addLayout(row1)
        self.aisle_dept = QComboBox()
        self.aisle_dept.setObjectName("aisleDept")
        self.aisle_dept.activated.connect(self._on_aisle_dept)
        ll.addWidget(self.aisle_dept)
        row2 = QHBoxLayout()
        self.add_center = QPushButton("+ Center")
        self.add_center.clicked.connect(lambda: self._add("center"))
        self.add_gm = QPushButton("+ GM")
        self.add_gm.clicked.connect(lambda: self._add("gm"))
        row2.addWidget(self.add_center)
        row2.addWidget(self.add_gm)
        ll.addLayout(row2)
        self.floor_hint = _label("", 10, color=HQ_MUTED, wrap=True, name="floorHint")
        ll.addWidget(self.floor_hint)
        body.addWidget(left)

        # Center
        center = QVBoxLayout()
        center.setSpacing(6)
        chips = QHBoxLayout()
        chips.setContentsMargins(0, 0, 0, 0)
        chips.addWidget(_label("TEMPLATE", 11, QFont.Weight.DemiBold, HQ_FAINT))
        self.chips: dict[str, QPushButton] = {}
        for ident in TEMPLATE_ORDER:
            name = CHIP_NAMES.get(ident, TEMPLATES[ident].name)
            btn = QPushButton(name)
            btn.setObjectName("templateChip")
            btn.setMinimumHeight(26)
            btn.setMinimumWidth(btn.fontMetrics().horizontalAdvance(name) + 36)
            btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            btn.setToolTip(f"{TEMPLATES[ident].name}: {TEMPLATES[ident].blurb}")
            btn.clicked.connect(lambda _=False, i=ident: self._set_template(i))
            self.chips[ident] = btn
            chips.addWidget(btn)
        chips.addStretch(1)
        chip_host = QWidget()
        chip_host.setLayout(chips)
        chip_host.setMinimumWidth(sum(btn.minimumWidth() + 8 for btn in self.chips.values()) + 90)
        chip_host.setMinimumHeight(30)
        chip_scroll = QScrollArea()
        chip_scroll.setWidget(chip_host)
        chip_scroll.setWidgetResizable(False)
        chip_scroll.setFrameShape(QFrame.Shape.NoFrame)
        chip_scroll.setFixedHeight(36)
        chip_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        chip_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        chip_scroll.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        center.addWidget(chip_scroll)
        from open_late.ui.osprey_docs import FloorCanvas

        self.floor = FloorCanvas()
        self.floor.setObjectName("floorPane")
        self.floor.setMinimumHeight(148)
        self.floor.picked.connect(lambda ident: self.select_target(ident))
        center.addWidget(self.floor, stretch=1)
        self.score = _label("", 14, QFont.Weight.Bold, HQ_TITLE, name="layoutScore")
        center.addWidget(self.score)
        self.bay_caption = _label("", 12, QFont.Weight.DemiBold, HQ_FAINT, name="bayCaption")
        center.addWidget(self.bay_caption)
        self.canvas = BayCanvas()
        self.canvas.setMinimumHeight(96)
        self.canvas.setMaximumHeight(120)
        self.canvas.productSelected.connect(self._on_bay_product)
        center.addWidget(self.canvas)

        self.sku_detail = QFrame()
        self.sku_detail.setObjectName("card")
        self.sku_detail.setMaximumHeight(92)
        sd = QVBoxLayout(self.sku_detail)
        sd.setContentsMargins(10, 8, 10, 8)
        sd.setSpacing(4)
        detail_head = QHBoxLayout()
        self.sku_detail_title = _label("Select a product in this bay", 12, QFont.Weight.DemiBold, HQ_TITLE)
        self.sku_detail_flag = _label("", 10, QFont.Weight.DemiBold, OPEN_GREEN)
        detail_head.addWidget(self.sku_detail_title, stretch=1)
        detail_head.addWidget(self.sku_detail_flag)
        sd.addLayout(detail_head)
        self.sku_detail_meta = _label("Click a product to inspect tier, facings, stock, cost and retail.", 10, color=HQ_MUTED, wrap=True)
        sd.addWidget(self.sku_detail_meta)
        detail_actions = QHBoxLayout()
        self.facing_down = QPushButton("− Facing")
        self.facing_up = QPushButton("+ Facing")
        self.pin_toggle = QPushButton("Pin / unpin")
        self.sku_detail_inventory = QPushButton("Open inventory")
        for button in (self.facing_down, self.facing_up, self.pin_toggle, self.sku_detail_inventory):
            button.setEnabled(False)
        self.facing_down.clicked.connect(lambda: self._change_selected_facings(-1))
        self.facing_up.clicked.connect(lambda: self._change_selected_facings(1))
        self.pin_toggle.clicked.connect(self._toggle_selected_pin)
        self.sku_detail_inventory.clicked.connect(self._open_inventory_for_selected)
        detail_actions.addStretch(1)
        detail_actions.addWidget(self.facing_down)
        detail_actions.addWidget(self.facing_up)
        detail_actions.addWidget(self.pin_toggle)
        detail_actions.addWidget(self.sku_detail_inventory)
        sd.addLayout(detail_actions)
        center.addWidget(self.sku_detail)
        pager = QHBoxLayout()
        self.bay_prev = QPushButton("‹ Bay")
        self.bay_prev.setObjectName("bayPrev")
        self.bay_prev.clicked.connect(lambda: self._step_bay(-1))
        self.bay_lab = _label("", 11, color=HQ_MUTED, name="bayPage")
        self.bay_next = QPushButton("Bay ›")
        self.bay_next.setObjectName("bayNext")
        self.bay_next.clicked.connect(lambda: self._step_bay(1))
        pager.addWidget(self.bay_prev)
        pager.addWidget(self.bay_lab, stretch=1, alignment=Qt.AlignmentFlag.AlignCenter)
        pager.addWidget(self.bay_next)
        center.addLayout(pager)
        self.cost = _label("", 12, color=TEXT, wrap=True, name="resetCost")
        center.addWidget(self.cost)
        self.alerts = _label("", 11, color="#9A6B00", wrap=True, name="layoutAlerts")
        center.addWidget(self.alerts)
        body.addLayout(center, stretch=1)

        # Picks
        right = QFrame()
        right.setObjectName("card")
        right.setMinimumWidth(180)
        right.setMaximumWidth(240)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(12, 12, 12, 12)
        rl.addWidget(_label("PICKS", 11, QFont.Weight.DemiBold, HQ_FAINT))
        self.mode_combo = QComboBox()
        self.mode_combo.setObjectName("pickMode")
        self.mode_combo.activated.connect(self._on_mode)
        rl.addWidget(self.mode_combo)
        self.dept_combo = QComboBox()
        self.dept_combo.setObjectName("pickDept")
        self.dept_combo.activated.connect(self._on_pick_dept)
        rl.addWidget(self.dept_combo)
        self.sku_list = QListWidget()
        self.sku_list.setObjectName("pickList")
        self.sku_list.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
        self.sku_list.setMinimumHeight(72)
        self.sku_list.itemChanged.connect(self._on_tick)
        rl.addWidget(self.sku_list, stretch=1)
        self.pick_hint = _label("", 10, color=HQ_MUTED, wrap=True, name="pickHint")
        rl.addWidget(self.pick_hint)
        body.addWidget(right)
        root.addLayout(body, stretch=1)

    # ------------------------------------------------------------ data
    def _state(self):
        host = getattr(self.page, "host", None)
        return getattr(host, "state", None)

    def _door(self):
        state = self._state()
        if state is None:
            return None
        return next((d for d in state.doors if d.id == self.door_id), None)

    def _size(self, door) -> str:
        return SH.door_entry(self._state(), door).get("size", "supercenter_v1")

    def _choice(self) -> LiteChoice:
        return LiteChoice(template_id=self.template_id, priorities=tuple(self.pins),
                          endcaps=tuple(sorted(self.endcaps.items())),
                          facings=tuple(sorted(self.facing_targets.items())))

    def _load_door(self) -> None:
        state, door = self._state(), self._door()
        if state is None or door is None:
            return
        ch = SH.effective_choice(state, door)
        self.template_id = ch.template_id if ch.template_id in TEMPLATES else "balanced"
        self.pins = list(ch.priorities)
        self.endcaps = dict(ch.endcaps)
        self.facing_targets = dict(ch.facings)
        self.draft_floor = SH.floor_of(state, door)
        self.aisle_uid = ""
        self.bay_index = 0
        self.pick_mode = "eye"

    def dirty(self) -> bool:
        state, door = self._state(), self._door()
        if state is None or door is None:
            return False
        return (pack_choice(self._choice()) != pack_choice(SH.effective_choice(state, door))
                or self.draft_floor != SH.floor_of(state, door))

    # ------------------------------------------------------------ refresh
    def refresh(self) -> None:
        state = self._state()
        if state is None or not getattr(state, "doors", None):
            self.status.setText("Store layouts need a corporate game.")
            return
        self._busy = True
        try:
            ids = [d.id for d in state.doors]
            if self.store_combo.count() != len(ids) or [self.store_combo.itemData(i) for i in range(len(ids))] != ids:
                self.store_combo.clear()
                for d in state.doors:
                    self.store_combo.addItem(d.city, d.id)
            if self.door_id not in ids:
                self.door_id = ids[0]
                self._load_door()
            self.store_combo.setCurrentIndex(ids.index(self.door_id))
            door = self._door()
            pv = SH.preview(state, door, self._choice(), self.draft_floor)
            self.last_preview = pv
            self._fill_aisles(pv["layout"])
            self._fill_floor(pv["layout"])
            self._fill_chips()
            self._fill_score(pv)
            self._fill_bay(pv["layout"])
            self._fill_picks(state, door, pv["layout"])
            on = SH.shelves_on(state)
            entry = SH.door_entry(state, door)
            rev = int(entry.get("rev", 0))
            since = ("no resets yet" if rev == 0 else f"{rev} reset{'s' if rev != 1 else ''}") if on else \
                "store layouts are off until the first reset"
            self.status.setText(f"{door.city} · {_size_name(self._size(door))} · {since}")
            self.apply_btn.setEnabled(self.dirty())
            self.reset_btn.setEnabled(self.dirty())
        finally:
            self._busy = False

    def _fill_aisles(self, layout) -> None:
        floor = self.draft_floor or ()
        rows: list[tuple[str, str]] = []
        for a in floor:
            rows.append((a.uid, f"{aisle_label(floor, a)} · {_dept_name(a.dept)}"))
        for fid in ("PR", "MD", "FZ", "SN", "RX", "AA", "CK"):
            if any(b.aisle == fid for b in layout.bays):
                rows.append((fid, f"{FIXED_NAMES[fid]} (fixed)"))
        if self.aisle_uid not in [r[0] for r in rows] and rows:
            self.aisle_uid = rows[0][0]
        self.aisles.blockSignals(True)
        if self.aisles.count() != len(rows) or any(self.aisles.item(i).text() != rows[i][1] for i in range(len(rows))):
            self.aisles.clear()
            for uid, text in rows:
                item = QListWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, uid)
                self.aisles.addItem(item)
        idx = [r[0] for r in rows].index(self.aisle_uid) if rows else -1
        self.aisles.setCurrentRow(idx)
        self.aisles.blockSignals(False)
        aisle = next((a for a in floor if a.uid == self.aisle_uid), None)
        editable = aisle is not None
        for b in (self.up_btn, self.down_btn, self.remove_btn, self.aisle_dept):
            b.setEnabled(editable)
        self.aisle_dept.blockSignals(True)
        self.aisle_dept.clear()
        if aisle is not None:
            for d in formats()["aisle_kinds"][aisle.kind]["depts"]:
                self.aisle_dept.addItem(_dept_name(d), d)
            self.aisle_dept.setCurrentIndex(max(0, self.aisle_dept.findData(aisle.dept)))
        self.aisle_dept.blockSignals(False)
        door = self._door()
        size = self._size(door) if door is not None else "supercenter_v1"
        from open_late.shelf_model import floor_limits

        lc, hc = floor_limits(size, "center")
        lg, hg = floor_limits(size, "gm")
        nc = sum(1 for a in floor if a.kind == "center")
        ng = sum(1 for a in floor if a.kind == "gm")
        self.add_center.setEnabled(nc < hc)
        self.add_gm.setEnabled(ng < hg)
        self.floor_hint.setText(f"Center {nc} of {lc}-{hc} · GM {ng} of {lg}-{hg}. A new aisle buys fixtures.")

    def _fill_floor(self, layout) -> None:
        floor = self.draft_floor or ()
        short = {"grocery": "Pantry", "meat_dairy": "Dairy", "health_beauty": "Beauty",
                 "home_garden": "Garden", "sporting": "Sporting"}
        rows = []
        for aisle in floor:
            name = short.get(aisle.dept, _dept_name(aisle.dept))
            rows.append((aisle_label(floor, aisle), aisle.dept, name, aisle.uid))
        front: dict[str, str] = {}
        back: dict[str, str] = {}
        for bay in layout.bays:
            if bay.kind != "endcap":
                continue
            if bay.key.endswith(".F"):
                front[bay.aisle] = bay.key
            elif bay.key.endswith(".B"):
                back[bay.aisle] = bay.key
        selected = self.pick_mode if self.pick_mode not in ("", "eye") else self.aisle_uid
        from open_late.shelf_model import sku_index_v1

        state = self._state()
        texts: dict[str, tuple[str, ...]] = {}
        if self.board == "endcaps":
            catalog = sku_index_v1()
            for bay in layout.bays:
                if bay.kind != "endcap":
                    continue
                lines: list[str] = []
                for _tier, items in bay.tiers:
                    for sku, _facings in items:
                        pid = catalog[sku] if 0 <= int(sku) < len(catalog) else ""
                        product = state.products.get(pid) if state is not None else None
                        lines.append(product_title(product) if product is not None else pid or str(sku))
                        if len(lines) >= 3:
                            break
                    if len(lines) >= 3:
                        break
                texts[bay.key] = tuple(lines)
        mode = "endcaps" if self.board == "endcaps" else "layout"
        self.floor.set_plan(rows, mode, selected=selected, front_caps=front, back_caps=back, cap_text=texts)

    def set_board(self, board: str) -> None:
        self.board = "endcaps" if board == "endcaps" else "layout"

    def _describe(self, target: str) -> str:
        painted = self.floor.tip_for(target)
        if painted and painted != target:
            return painted
        if target in FIXED_NAMES:
            return f"{FIXED_NAMES[target]}. Fixed fixture."
        if target.endswith(".F"):
            return f"Front endcap {target}. Three products, toward the door."
        if target.endswith(".B"):
            return f"Back endcap {target}. Three products, far from the door."
        floor = self.draft_floor or ()
        aisle = next((item for item in floor if item.uid == target), None)
        if aisle is not None:
            return f"{aisle_label(floor, aisle)} · {_dept_name(aisle.dept)}."
        return target

    def select_target(self, target: str, refresh: bool = True, announce: bool = True) -> None:
        """Open the aisle, endcap, or fixed fixture the floor plan was clicked on."""
        target = str(target or "")
        if not target:
            return
        self._seek_bay = ""
        if target.endswith(".F") or target.endswith(".B"):
            self.aisle_uid = target.rsplit(".", 1)[0]
            self.pick_mode = target
            self._seek_bay = target
        elif target.startswith("CK"):
            self.aisle_uid = "CK"
            self.pick_mode = "eye"
            self._seek_bay = "CK.1"
            self.bay_index = 0
        else:
            self.aisle_uid = target
            self.pick_mode = "eye"
            self.bay_index = 0
        if announce:
            self._say(self._describe(target))
        if refresh:
            self.refresh()

    def _fill_chips(self) -> None:
        for ident, btn in self.chips.items():
            want = "templateChipOn" if ident == self.template_id else "templateChip"
            if btn.objectName() != want:
                btn.setObjectName(want)
                btn.style().unpolish(btn)
                btn.style().polish(btn)

    def _fill_score(self, pv: dict) -> None:
        est = pv["est_sales_pct"]
        sign = "+" if est >= 0 else "−"
        self.score.setText(f"Layout score {pv['score_before']} → {pv['score_after']}  ·  est. {sign}{abs(est):.1f}% sales")
        self.score.setToolTip("50 is the average store (Balanced on the default floor). The estimate is weekly "
                              "sales vs that store once the reset dip is over; shelves alone move it at most +8%.")
        if pv["changed"] or pv["fixtures"]:
            parts = [f"{pv['changed']} facings to reset", f"{money(pv['labor'])} labor"]
            if pv["fixtures"]:
                parts.append(f"{money(pv['fixtures'])} new fixtures")
            parts.append(f"changed shelves sell slower for {pv['dip_days']} days")
            self.cost.setText("Reset: " + " · ".join(parts) + ".")
        else:
            self.cost.setText("No changes yet. Pick a template, aisles or picks to preview a reset.")
        self.alerts.setText("  ".join(pv["alerts"][:3]))

    def _bays(self, layout) -> list:
        bays = [b for b in layout.bays if b.aisle == self.aisle_uid]
        return [b for b in bays if b.kind != "endcap"] + [b for b in bays if b.kind == "endcap"]

    def _fill_bay(self, layout) -> None:
        bays = self._bays(layout)
        seek = getattr(self, "_seek_bay", "")
        if seek:
            for index, bay in enumerate(bays):
                if bay.key == seek:
                    self.bay_index = index
                    break
            self._seek_bay = ""
        self.bay_index = max(0, min(self.bay_index, len(bays) - 1))
        bay = bays[self.bay_index] if bays else None
        state = self._state()
        previous_bay_key = getattr(self, "_selected_bay_key", "")
        current_bay_key = getattr(bay, "key", "") if bay is not None else ""
        if previous_bay_key != current_bay_key:
            self._selected_bay_key = current_bay_key
            self._clear_bay_product()
        self.canvas.set_bay(bay, state.products if state is not None else {}, set(self.pins))
        if bay is None:
            self.bay_caption.setText("")
            self.bay_lab.setText("")
        else:
            kind = "Endcap" if bay.kind == "endcap" else bay.fixture.replace("_", " ").title()
            self.bay_caption.setText(f"{kind.upper()}  ·  {_dept_name(bay.dept) if bay.dept != '*' else 'Mixed'}  ·  {bay.key}")
            self.bay_lab.setText(f"Bay {self.bay_index + 1} of {len(bays)}")
        self.bay_prev.setEnabled(self.bay_index > 0)
        self.bay_next.setEnabled(self.bay_index < len(bays) - 1)
        show_cabinet = self.board != "endcaps" and not str(self.pick_mode).endswith((".F", ".B"))
        if self.canvas.isVisible() != show_cabinet:
            self.canvas.setVisible(show_cabinet)
            self.bay_prev.setVisible(show_cabinet)
            self.bay_next.setVisible(show_cabinet)
            self.bay_lab.setVisible(show_cabinet)
        if not show_cabinet and bay is not None and bay.kind == "endcap":
            self.bay_caption.setText("")

    def _on_bay_product(self, product, tier: str, facings: int, pinned: bool) -> None:
        pid = str(getattr(product, "id", "") or "")
        self._selected_product_id = pid
        try:
            self._selected_sku_index = sku_index_v1().index(pid)
        except ValueError:
            self._selected_sku_index = -1
        self._selected_facings = int(facings)
        self._selected_pinned = bool(pinned)
        state, door = self._state(), self._door()
        line = (getattr(door, "stock", None) or {}).get(pid) if door is not None else None
        on_hand = int(getattr(line, "on_hand", 0) or 0) if line is not None else 0
        on_order = int(getattr(line, "on_order", 0) or 0) if line is not None else 0
        cost = int(getattr(product, "cost", 0) or 0)
        price = int(getattr(product, "price", 0) or 0)
        margin = 0.0 if price <= 0 else (price - cost) / price
        brand = str(getattr(product, "brand", "") or "Unbranded")
        bay = None
        layout = (self.last_preview or {}).get("layout")
        if layout is not None:
            bays = self._bays(layout)
            if bays:
                bay = bays[max(0, min(self.bay_index, len(bays) - 1))]
        location = getattr(bay, "key", "") or "—"
        self.sku_detail_title.setText(product_title(product) or pid)
        self.sku_detail_flag.setText("PINNED" if pinned else "SELECTED")
        self.sku_detail_meta.setText(
            f"{brand}  ·  SKU {pid}  ·  Bay {location}  ·  Tier {tier.upper()}  ·  Facings {facings}  ·  "
            f"On hand {on_hand:,}  ·  On order {on_order:,}  ·  Cost {money(cost)}  ·  Retail {money(price)}  ·  Margin {margin * 100:.1f}%"
        )
        enabled = bool(pid and self._selected_sku_index >= 0)
        self.sku_detail_inventory.setEnabled(enabled)
        self.facing_down.setEnabled(enabled and facings > 1)
        self.facing_up.setEnabled(enabled and facings < 8)
        self.pin_toggle.setEnabled(enabled)

    def _clear_bay_product(self) -> None:
        self._selected_product_id = ""
        self.canvas.selected_product_id = ""
        self.sku_detail_title.setText("Select a product in this bay")
        self.sku_detail_flag.setText("")
        self.sku_detail_meta.setText("Click a product to inspect tier, facings, stock, cost and retail.")
        for button in (self.sku_detail_inventory, self.facing_down, self.facing_up, self.pin_toggle):
            button.setEnabled(False)

    def _change_selected_facings(self, delta: int) -> None:
        idx = int(getattr(self, "_selected_sku_index", -1))
        if idx < 0:
            return
        current = int(self.facing_targets.get(idx, getattr(self, "_selected_facings", 1)))
        target = max(1, min(8, current + int(delta)))
        self.facing_targets[idx] = target
        self._say(f"Requested {target} facing{'s' if target != 1 else ''}. Apply reset to commit it.")
        self._changed()

    def _toggle_selected_pin(self) -> None:
        idx = int(getattr(self, "_selected_sku_index", -1))
        if idx < 0:
            return
        if idx in self.pins:
            self.pins = [value for value in self.pins if value != idx]
            self._say("Eye-level pin removed. Apply reset to commit it.")
        else:
            candidate = list(self.pins) + [idx]
            msg = check_pins(candidate)
            if msg:
                self._say(msg)
                return
            self.pins = candidate
            self._say("Product pinned for eye-level priority. Apply reset to commit it.")
        self._changed()

    def _open_inventory_for_selected(self) -> None:
        host = getattr(self.page, "host", None)
        pid = getattr(self, "_selected_product_id", "")
        if host is None or not pid:
            return
        setattr(host, "inventory_focus_sku", pid)
        opener = getattr(host, "_open_app", None)
        if callable(opener):
            opener("inventory")

    def _fill_picks(self, state, door, layout) -> None:
        caps = [b.key for b in layout.bays if b.kind == "endcap"]
        modes = [("eye", "Eye-level picks")] + [(k, f"Endcap {k}") for k in caps]
        if self.pick_mode not in [m[0] for m in modes]:
            self.pick_mode = "eye"
        if self.mode_combo.count() != len(modes):
            self.mode_combo.clear()
            for key, text in modes:
                self.mode_combo.addItem(text, key)
        self.mode_combo.setCurrentIndex(max(0, self.mode_combo.findData(self.pick_mode)))
        facts = shipped_facts()
        ids = sku_index_v1()
        carried = set(state.products)
        if self.pick_mode == "eye":
            depts = sorted({f.dept for f in facts if f.id in carried}, key=_dept_name)
            if self.dept_combo.count() != len(depts):
                self.dept_combo.clear()
                for d in depts:
                    self.dept_combo.addItem(_dept_name(d), d)
            if self.pick_dept not in depts:
                self.pick_dept = depts[0]
            self.dept_combo.setEnabled(True)
            self.dept_combo.setCurrentIndex(max(0, self.dept_combo.findData(self.pick_dept)))
            dept = self.pick_dept
            chosen = [p for p in self.pins if facts[p].dept == dept]
        else:
            bay = next((b for b in layout.bays if b.key == self.pick_mode), None)
            dept = bay.dept if bay is not None and bay.dept != "*" else self.pick_dept
            self.dept_combo.setEnabled(False)
            chosen = list(self.endcaps.get(self.pick_mode, ()))
        vel = SH.demand_weights(state, door)
        rows = sorted((-vel.get(f.idx, 0.0), f.idx) for f in facts if f.dept == dept and f.id in carried)
        show = [i for _v, i in rows[:SKU_LIST_LEN]]
        for p in chosen:
            if p not in show:
                show.append(p)
        self.sku_list.blockSignals(True)
        self.sku_list.clear()
        for rank, idx in enumerate(show, 1):
            product = state.products.get(ids[idx])
            name = product_title(product) if product is not None else ids[idx]
            item = QListWidgetItem(f"{rank:>2}. {name}")
            item.setData(Qt.ItemDataRole.UserRole, idx)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if idx in chosen else Qt.CheckState.Unchecked)
            self.sku_list.addItem(item)
        self.sku_list.blockSignals(False)
        if self.pick_mode == "eye":
            self.pick_hint.setText(f"{len(chosen)} of {MAX_PINS_PER_DEPT} in {_dept_name(dept)} · "
                                   f"{len(self.pins)} of {MAX_PINS_PER_STORE} in the store. "
                                   "Ranked by what sells here.")
        else:
            self.pick_hint.setText(f"{len(chosen)} of 3 on {self.pick_mode}. None picked = the template fills it.")

    # ------------------------------------------------------------ actions
    def focus_endcaps(self) -> None:
        """Open the first endcap on this floor so the picks and the bay match."""
        self.refresh()
        layout = (self.last_preview or {}).get("layout")
        if layout is None:
            return
        caps = [bay for bay in layout.bays if bay.kind == "endcap"]
        if not caps:
            self._say("This floor has no endcap. Add a center aisle, then open Endcaps again.")
            return
        cap = caps[0]
        self.aisle_uid = cap.aisle
        self.pick_mode = cap.key
        self.bay_index = 0
        self.refresh()
        layout = (self.last_preview or {}).get("layout")
        if layout is None:
            return
        for index, bay in enumerate(self._bays(layout)):
            if bay.key == cap.key:
                self.bay_index = index
                break
        self.refresh()

    def _changed(self) -> None:
        self.refresh()
        page = self.page
        if hasattr(page, "_layout_dirty"):
            page._layout_dirty(self.dirty())

    def _on_store(self, index: int) -> None:
        if self._busy or index < 0:
            return
        self.door_id = self.store_combo.itemData(index)
        self._load_door()
        self._changed()

    def _on_aisle(self, row: int) -> None:
        if self._busy or row < 0:
            return
        self.aisle_uid = self.aisles.item(row).data(Qt.ItemDataRole.UserRole)
        self.bay_index = 0
        self.refresh()

    def _say(self, text: str) -> None:
        host = getattr(self.page, "host", None)
        if text and host is not None and hasattr(host, "_say"):
            host._say(text)

    def _move(self, delta: int) -> None:
        floor, err = SH.move_aisle(self.draft_floor, self.aisle_uid, delta)
        self.draft_floor = floor
        self._say(err)
        self._changed()

    def _remove(self) -> None:
        door = self._door()
        floor, err = SH.remove_aisle(self.draft_floor, self._size(door), self.aisle_uid)
        self.draft_floor = floor
        self._say(err)
        self._changed()

    def _add(self, kind: str) -> None:
        door = self._door()
        depts = formats()["aisle_kinds"][kind]["depts"]
        current = next((a for a in self.draft_floor if a.uid == self.aisle_uid and a.kind == kind), None)
        dept = current.dept if current is not None else depts[0]
        used = tuple(a.uid for a in SH.floor_of(self._state(), door))
        floor, err = SH.add_aisle(self.draft_floor, self._size(door), kind, dept, used)
        if not err:
            new = [a for a in floor if a.uid not in {b.uid for b in self.draft_floor}]
            if new:
                self.aisle_uid = new[0].uid
        self.draft_floor = floor
        self._say(err)
        self._changed()

    def _on_aisle_dept(self, index: int) -> None:
        if self._busy or index < 0:
            return
        floor, err = SH.set_aisle_dept(self.draft_floor, self.aisle_uid, self.aisle_dept.itemData(index))
        self.draft_floor = floor
        self._say(err)
        self._changed()

    def _set_template(self, ident: str) -> None:
        self.template_id = ident
        self._changed()

    def _step_bay(self, delta: int) -> None:
        self.bay_index += delta
        self.refresh()

    def _on_mode(self, index: int) -> None:
        if index >= 0:
            self.pick_mode = self.mode_combo.itemData(index)
            self.refresh()

    def _on_pick_dept(self, index: int) -> None:
        if index >= 0:
            self.pick_dept = self.dept_combo.itemData(index)
            self.refresh()

    def _on_tick(self, item: QListWidgetItem) -> None:
        if self._busy:
            return
        idx = int(item.data(Qt.ItemDataRole.UserRole))
        on = item.checkState() == Qt.CheckState.Checked
        if self.pick_mode == "eye":
            pins = [p for p in self.pins if p != idx] + ([idx] if on else [])
            msg = check_pins(pins)
            if msg:
                self._say(msg)
            else:
                self.pins = pins
        else:
            cur = [p for p in self.endcaps.get(self.pick_mode, ()) if p != idx] + ([idx] if on else [])
            if len(cur) > 3:
                self._say("An endcap holds 3 products.")
            elif cur:
                self.endcaps[self.pick_mode] = tuple(cur)
            else:
                self.endcaps.pop(self.pick_mode, None)
        self._changed()

    def _discard(self) -> None:
        self._load_door()
        self._changed()

    def _apply(self) -> None:
        state, door = self._state(), self._door()
        if state is None or door is None:
            return
        floor = self.draft_floor if self.draft_floor != SH.floor_of(state, door) else None
        msg, _pv = SH.apply_layout(state, [door.id], self._choice(), floor)
        self._say(msg)
        host = getattr(self.page, "host", None)
        if msg.startswith("Reset sent") and host is not None:
            if hasattr(host, "_save"):
                host._save()
            if hasattr(host, "refresh"):
                host.refresh()
        self._load_door()
        self._changed()


def _size_name(size_id: str) -> str:
    return {"compact_v1": "Compact", "supercenter_v1": "Supercenter", "large_v1": "Large supercenter"}.get(size_id, size_id)
