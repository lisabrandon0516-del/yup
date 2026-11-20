"""Living Store floor canvas for Back Office: Retail.

The canvas is read-only visualization plus selection/drill-down. It consumes the
compiled planogram Layout already produced by open_late.shelves and emits stable
bay/department/SKU identifiers back to the existing Planogram controller.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from PySide6.QtCore import QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QSlider, QStackedWidget, QVBoxLayout, QWidget

BG = QColor("#071425"); FLOOR = QColor("#E7E0D4"); WALL = QColor("#182331")
PANEL = "#0E2035"; LINE = "#173A55"; TEXT = "#F4F8FF"; MUTED = "#7897AE"
GREEN = QColor("#19E86A"); RED = QColor("#FF5757"); AMBER = QColor("#F4C84A"); BLUE = QColor("#39A7FF")
DEPT = {
    "produce":"#3FAE63", "grocery":"#C59A45", "meat_dairy":"#C65B67", "frozen":"#3B8FD1",
    "household":"#3FA7A2", "health_beauty":"#8F5BC1", "pharmacy":"#2FA6A1", "electronics":"#367DCE",
    "clothing":"#B76FAF", "toys":"#BA5AAE", "home_garden":"#8B7E63", "sporting":"#4E9B73",
    "seasonal":"#D2574E", "pet":"#D28A39", "*":"#65758A",
}

@dataclass
class Hit:
    rect: QRectF
    kind: str
    ident: str
    label: str
    payload: object = None


_LABELS = {
    "meat_dairy": "Meat & Dairy",
    "health_beauty": "Health & Beauty",
    "home_garden": "Home & Garden",
    "clothing": "Apparel",
}
_PACKS = ("#E24B4B", "#F0C419", "#3FAE63", "#3B8FD1", "#E07A3D", "#8F5BC1", "#F4F1EA", "#C65B67", "#4E9B73", "#367DCE")


def _name(raw: str) -> str:
    key = str(raw or "")
    if key in _LABELS:
        return _LABELS[key]
    return key.replace("_", " ").title() or "General"


class LivingStoreCanvas(QWidget):
    departmentPicked = Signal(str)
    bayPicked = Signal(str)
    skuPicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("livingStoreCanvas")
        self.layout_data = None
        self.products = {}
        self.stock = {}
        self.sales = {}
        self.overlay = "traffic"
        self.zoom = 100
        self.hits: list[Hit] = []
        self.selected = ""
        self.shoppers: list[QPointF] = []
        self.walkers: list[tuple[int, float]] = []
        self._lanes: list[QRectF] = []
        self.tick = 0
        self.setMinimumHeight(220)
        self.setMouseTracking(True)
        self.timer = QTimer(self); self.timer.setInterval(140); self.timer.timeout.connect(self._animate); self.timer.start()

    def set_store(self, layout, products: dict, *, door=None, overlay="traffic", sales=None):
        self.layout_data = layout
        self.products = dict(products or {})
        self.stock = dict(getattr(door, "stock", {}) or {}) if door is not None else {}
        self.sales = dict(sales or {})
        self.overlay = overlay
        self.walkers = [(index, (index * 0.17) % 1) for index in range(12)]
        self._seed_shoppers()
        self.update()

    def set_overlay(self, overlay: str):
        self.overlay = str(overlay or "none").lower(); self.update()

    def set_zoom(self, value: int):
        self.zoom = max(70, min(160, int(value))); self.update()

    def _seed_shoppers(self):
        self.shoppers = []
        count = 18
        for i in range(count):
            x = 0.12 + ((i * 37) % 76) / 100
            y = 0.16 + ((i * 53) % 70) / 100
            self.shoppers.append(QPointF(x, y))

    def _animate(self):
        if not self.isVisible():
            return
        self.tick += 1
        if not self._lanes:
            return
        moved = []
        for index, (lane_index, progress) in enumerate(self.walkers):
            direction = 1 if index % 2 == 0 else -1
            progress += direction * 0.01
            if progress > 1:
                progress = 0
            elif progress < 0:
                progress = 1
            moved.append((lane_index, progress))
        self.walkers = moved
        self.update()

    def mousePressEvent(self, event):
        pos = event.position() if hasattr(event, "position") else QPointF(event.pos())
        for hit in reversed(self.hits):
            if hit.rect.contains(pos):
                self.selected = hit.ident
                if hit.kind == "bay": self.bayPicked.emit(hit.ident)
                elif hit.kind == "department": self.departmentPicked.emit(hit.ident)
                elif hit.kind == "sku": self.skuPicked.emit(hit.ident)
                self.update(); event.accept(); return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.position() if hasattr(event, "position") else QPointF(event.pos())
        tip = ""
        for hit in reversed(self.hits):
            if hit.rect.contains(pos): tip = hit.label; break
        self.setToolTip(tip); super().mouseMoveEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setClipRect(self.rect())
        painter.fillRect(self.rect(), BG)
        scale = max(0.7, min(1.6, self.zoom / 100.0))
        base = QRectF(8, 8, max(40, self.width() - 16), max(40, self.height() - 16))
        canvas = QRectF(0, 0, base.width() * scale, base.height() * scale)
        canvas.moveCenter(base.center())
        store = canvas.adjusted(16, 12, -16, -18)
        painter.setBrush(FLOOR)
        painter.setPen(QPen(QColor("#5B6975"), 2))
        painter.drawRoundedRect(store, 10, 10)
        self._paint_tiles(painter, store)
        self.hits = []
        self._lanes = []
        if not list(getattr(self.layout_data, "bays", ()) or ()):
            painter.setPen(QColor(MUTED))
            painter.drawText(store, Qt.AlignmentFlag.AlignCenter, "This store has no shelf layout yet.")
            painter.end()
            return
        self._paint_floor(painter, store)
        self._paint_shoppers(painter, store)
        self._paint_legend(painter, canvas)
        painter.end()

    def _box(self, store: QRectF, x: float, y: float, w: float, h: float) -> QRectF:
        return QRectF(store.left() + store.width() * x, store.top() + store.height() * y, store.width() * w, store.height() * h)

    def _paint_floor(self, painter, store: QRectF) -> None:
        from open_late.shelf_model import aisle_label

        layout = self.layout_data
        floor = list(getattr(layout, "floor", ()) or ())
        bays = list(getattr(layout, "bays", ()) or ())
        center = [aisle for aisle in floor if aisle.kind == "center"]
        gm = [aisle for aisle in floor if aisle.kind == "gm"]
        by_aisle: dict[str, list] = {}
        for bay in bays:
            by_aisle.setdefault(str(bay.aisle), []).append(bay)
        if not center:
            seen = []
            for bay in bays:
                if bay.kind == "center" and bay.aisle not in seen:
                    seen.append(bay.aisle)
                    center.append(bay)
        produce = [bay for bay in bays if bay.dept == "produce" and bay.kind == "perimeter"]
        meat = [bay for bay in bays if bay.dept == "meat_dairy" and bay.kind == "perimeter"]
        frozen = [bay for bay in bays if bay.dept == "frozen" and bay.kind == "perimeter"]
        pharmacy = [bay for bay in bays if bay.kind == "pharmacy"]
        seasonal = [bay for bay in bays if bay.kind == "seasonal"]
        promo = [bay for bay in bays if bay.kind == "action_alley"]
        checkout = [bay for bay in bays if bay.kind == "checkout"]
        top_gm = gm[:2]
        low_gm = gm[2:] or gm
        if produce:
            self._paint_role(painter, self._box(store, 0.025, 0.03, 0.30, 0.15), "produce", produce, "cooler")
        if meat:
            self._paint_role(painter, self._box(store, 0.675, 0.03, 0.30, 0.15), "meat_dairy", meat, "cooler")
        if top_gm:
            span = 0.30 / len(top_gm)
            for index, aisle in enumerate(top_gm):
                self._paint_gondola(
                    painter,
                    self._box(store, 0.35 + index * span, 0.03, span - 0.012, 0.15),
                    _name(aisle.dept),
                    aisle.dept,
                    str(aisle.uid),
                    by_aisle.get(str(aisle.uid), []),
                )
        if frozen:
            self._paint_role(painter, self._box(store, 0.025, 0.21, 0.145, 0.40), "frozen", frozen, "cooler")
        origin = 0.19 if frozen else 0.025
        count = max(1, len(center))
        span = (0.96 - origin) / count
        for index, aisle in enumerate(center):
            uid = str(getattr(aisle, "uid", "") or getattr(aisle, "aisle", f"C{index + 1}"))
            try:
                title = aisle_label(tuple(floor), aisle) if floor and hasattr(aisle, "uid") else f"Aisle {index + 1}"
            except Exception:
                title = f"Aisle {index + 1}"
            rect = self._box(store, origin + index * span, 0.21, max(0.02, span - 0.012), 0.40)
            if index + 1 < count:
                self._lanes.append(self._box(store, origin + index * span + span - 0.012, 0.21, 0.012, 0.40))
            self._paint_gondola(painter, rect, title, str(getattr(aisle, "dept", "") or ""), uid, by_aisle.get(uid, []))
        if low_gm:
            span = 0.77 / len(low_gm)
            for index, aisle in enumerate(low_gm):
                self._paint_gondola(
                    painter,
                    self._box(store, 0.19 + index * span, 0.635, span - 0.012, 0.13),
                    _name(aisle.dept),
                    aisle.dept,
                    str(aisle.uid),
                    by_aisle.get(str(aisle.uid), []),
                )
        if pharmacy:
            self._paint_role(painter, self._box(store, 0.025, 0.79, 0.20, 0.11), "pharmacy", pharmacy, "service")
        self._paint_checkout_block(painter, self._box(store, 0.25, 0.79, 0.48, 0.11), checkout)
        if seasonal:
            self._paint_role(painter, self._box(store, 0.76, 0.79, 0.215, 0.11), "seasonal", seasonal, "promo")
        if promo:
            shown = promo[:5]
            for index, bay in enumerate(shown):
                table = self._box(store, 0.36 + index * 0.055, 0.755, 0.04, 0.025)
                painter.setBrush(QColor("#D2574E"))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(table, 2, 2)
                self.hits.append(Hit(table, "bay", str(bay.key), "Promotional display", bay))
        door = self._box(store, 0.39, 0.925, 0.22, 0.055)
        painter.setBrush(QColor("#C9C2B6"))
        painter.setPen(QPen(QColor("#8C8478"), 1))
        painter.drawRoundedRect(door, 2, 2)
        painter.setPen(QColor("#3A342C"))
        painter.drawText(door, Qt.AlignmentFlag.AlignCenter, "ENTRANCE")

    def _paint_role(self, painter, rect: QRectF, dept: str, bays: list, role: str) -> None:
        color = QColor(DEPT.get(dept, "#65758A"))
        edges = {"cooler": "#7EC8F0", "service": "#8F5BC1", "promo": "#D2574E"}
        painter.setBrush(QColor("#243244"))
        painter.setPen(QPen(QColor(edges.get(role, color.name())), 2))
        painter.drawRoundedRect(rect, 4, 4)
        header_h = min(16.0, max(12.0, rect.height() * 0.28))
        header = QRectF(rect.left() + 2, rect.top() + 2, rect.width() - 4, header_h)
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(header, 3, 3)
        painter.setPen(QColor("#FFFFFF"))
        font = painter.font()
        font.setPixelSize(8)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(header, Qt.AlignmentFlag.AlignCenter, painter.fontMetrics().elidedText(_name(dept), Qt.TextElideMode.ElideRight, int(header.width())))
        self.hits.append(Hit(header, "department", dept, _name(dept)))
        body = rect.adjusted(3, header_h + 4, -3, -3)
        self._paint_packages(painter, body, abs(hash(dept)) % 7)
        if bays:
            self.hits.append(Hit(body, "bay", str(bays[0].key), _name(dept), bays[0]))
        if self.overlay in ("stockouts", "availability") and self._row_empty(bays):
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#FF5757"), 2))
            painter.drawRoundedRect(rect, 4, 4)

    def _paint_checkout_block(self, painter, rect: QRectF, bays: list) -> None:
        painter.setBrush(QColor("#1A2433"))
        painter.setPen(QPen(QColor("#91A4B5"), 1))
        painter.drawRoundedRect(rect, 4, 4)
        header = QRectF(rect.left() + 2, rect.top() + 2, rect.width() - 4, min(12.0, rect.height() * 0.4))
        painter.setBrush(QColor("#2C3C52"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(header, 2, 2)
        painter.setPen(QColor("#FFFFFF"))
        font = painter.font()
        font.setPixelSize(8)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(header, Qt.AlignmentFlag.AlignCenter, "Checkout")
        lanes = 4
        belt = rect.adjusted(4, header.height() + 4, -4, -3)
        lane_w = belt.width() / lanes
        for index in range(lanes):
            lane = QRectF(belt.left() + index * lane_w + 2, belt.top(), max(4.0, lane_w - 4), belt.height())
            painter.setBrush(QColor("#31445C"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(lane, 2, 2)
        if bays:
            self.hits.append(Hit(rect, "bay", str(bays[0].key), "Checkout", bays[0]))

    def _paint_wall(self, painter, rect: QRectF, walls: list) -> None:
        if not walls or rect.width() < 16:
            return
        height = rect.height() / len(walls)
        for index, (dept, ident) in enumerate(walls):
            block = QRectF(rect.left(), rect.top() + index * height + 3, rect.width(), max(16.0, height - 6))
            if dept in ("produce", "meat_dairy", "frozen"):
                color = QColor("#3B8FD1")
            elif dept == "pharmacy":
                color = QColor("#8F5BC1")
            elif dept == "seasonal":
                color = QColor("#D2574E")
            else:
                color = QColor(DEPT.get(dept, "#65758A"))
            painter.setBrush(QColor(color.red(), color.green(), color.blue(), 70))
            painter.setPen(QPen(color, 1.5))
            painter.drawRoundedRect(block, 5, 5)
            painter.setPen(QColor("#F4F8FF"))
            font = painter.font()
            font.setPixelSize(10)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(block.adjusted(4, 0, -4, 0), Qt.AlignmentFlag.AlignCenter, _name(dept))
            self.hits.append(Hit(block, "department", dept, f"{_name(dept)} wall", ident))

    def _paint_gondola(self, painter, rect: QRectF, title: str, dept: str, uid: str, bays: list) -> None:
        color = QColor(DEPT.get(dept, "#65758A"))
        selected = self.selected in {uid, dept} or any(self.selected == str(getattr(bay, "key", "")) for bay in bays)
        painter.setBrush(QColor("#1C2836"))
        painter.setPen(QPen(GREEN if selected else color, 2 if selected else 1))
        painter.drawRoundedRect(rect, 4, 4)
        header_h = 15 if rect.height() > 34 else 0
        if header_h:
            header = QRectF(rect.left() + 2, rect.top() + 2, rect.width() - 4, header_h)
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(header, 3, 3)
            painter.setPen(QColor("#FFFFFF"))
            font = painter.font()
            font.setPixelSize(8)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(header.adjusted(2, 0, -2, 0), Qt.AlignmentFlag.AlignCenter, painter.fontMetrics().elidedText(_name(dept), Qt.TextElideMode.ElideRight, int(header.width())))
            self.hits.append(Hit(header, "department", dept, _name(dept)))
        body = rect.adjusted(3, header_h + 3, -3, -10)
        self._paint_packages(painter, body, abs(hash(dept or uid)) % 7)
        if any(str(getattr(bay, "fixture", "")) == "peg" for bay in bays):
            painter.setPen(QPen(QColor("#3FAE63"), 3))
            painter.drawLine(int(rect.left() + 1), int(rect.top() + 2), int(rect.left() + 1), int(rect.bottom() - 2))
        self.hits.append(Hit(body, "bay", uid, f"{title} · {_name(dept)}"))
        lead = self._lead_product(bays)
        if lead is not None and body.height() > 16 and body.width() > 12:
            pid, name, _product = lead
            mark = QRectF(body.center().x() - 4, body.bottom() - 8, 8, 7)
            painter.setBrush(QColor("#F4C84A"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(mark, 1, 1)
            self.hits.append(Hit(mark, "sku", pid, name))
        if self.overlay in ("stockouts", "availability") and self._row_empty(bays):
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#FF5757"), 2))
            painter.drawRoundedRect(rect, 4, 4)
        cap = next((bay for bay in bays if str(getattr(bay, "key", "")).endswith(".F")), None)
        if cap is not None and rect.width() > 24:
            cap_rect = QRectF(rect.left(), rect.bottom() - 8, rect.width(), 8)
            painter.setBrush(QColor("#F4C84A"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(cap_rect)
            self.hits.append(Hit(cap_rect, "bay", str(cap.key), f"{title} endcap", cap))

    def _paint_packages(self, painter, body: QRectF, salt: int) -> None:
        if body.width() < 8 or body.height() < 8:
            return
        shelves = max(3, min(9, int(body.height() / 16)))
        cols = max(2, min(10, int(body.width() / 9)))
        shelf_h = body.height() / shelves
        cell_w = body.width() / cols
        painter.setPen(Qt.PenStyle.NoPen)
        for row in range(shelves):
            top = body.top() + row * shelf_h
            painter.setBrush(QColor("#4A5668"))
            painter.drawRect(QRectF(body.left(), top + shelf_h - 2.5, body.width(), 2.5))
            for col in range(cols):
                painter.setBrush(QColor(_PACKS[(row * 5 + col * 3 + salt) % len(_PACKS)]))
                painter.drawRoundedRect(
                    QRectF(body.left() + col * cell_w + 1.2, top + 1.5, max(2.0, cell_w - 2.4), max(3.0, shelf_h * 0.62)),
                    1.2,
                    1.2,
                )

    def _row_empty(self, bays) -> bool:
        for bay in bays:
            for _tier, items in getattr(bay, "tiers", ()) or ():
                if any(self._stock_for(sku) <= 0 for sku, _facings in items or ()):
                    return True
        return False

    def _lead_product(self, bays):
        rows = self._bay_products(bays[0]) if bays else []
        if rows:
            return rows[0]
        for bay in bays[1:]:
            rows = self._bay_products(bay)
            if rows:
                return rows[0]
        return None

    def _aisle_tone(self, bays, color: QColor) -> QColor:
        if self.overlay in ("stockouts", "availability"):
            empty = False
            for bay in bays:
                for _tier, items in getattr(bay, "tiers", ()) or ():
                    if any(self._stock_for(sku) <= 0 for sku, _facings in items or ()):
                        empty = True
            return QColor("#7A2630") if empty else QColor("#245B42")
        if self.overlay in ("profit", "margin"):
            return QColor("#604A86")
        if self.overlay in ("sales", "traffic"):
            exposure = max((float(getattr(bay, "exposure", 0) or 0) for bay in bays), default=0)
            return QColor("#7A5028") if exposure >= 0.5 else QColor("#35566F")
        return QColor(color.red(), color.green(), color.blue(), 150)

    def _paint_tiles(self, p, rect):
        p.save(); p.setPen(QPen(QColor(255,255,255,22), 1))
        step=24
        x=int(rect.left())
        while x<rect.right(): p.drawLine(x,int(rect.top()),x,int(rect.bottom())); x+=step
        y=int(rect.top())
        while y<rect.bottom(): p.drawLine(int(rect.left()),y,int(rect.right()),y); y+=step
        p.restore()

    def _paint_department(self, p, rect, dept, bays):
        color = QColor(DEPT.get(dept, "#65758A")); selected = self.selected == dept
        p.setBrush(QColor(color.red(), color.green(), color.blue(), 42 if not selected else 80))
        p.setPen(QPen(GREEN if selected else color, 3 if selected else 1.5)); p.drawRoundedRect(rect, 7, 7)
        label = _name(dept); header = QRectF(rect.left()+7, rect.top()+6, rect.width()-14, 24)
        p.setBrush(QColor("#102235")); p.setPen(QPen(color,1)); p.drawRoundedRect(header,5,5)
        p.setPen(QColor("#FFFFFF")); f=p.font(); f.setPixelSize(11); f.setBold(True); p.setFont(f); p.drawText(header,Qt.AlignmentFlag.AlignCenter,label)
        self.hits.append(Hit(QRectF(rect),"department",dept,f"{label}: {len(bays)} bays"))
        bay_area=rect.adjusted(8,36,-8,-8); n=max(1,len(bays)); bcols=max(1,min(3,ceil(n/3))); brows=ceil(n/bcols)
        bw=(bay_area.width()-5*(bcols-1))/bcols; bh=(bay_area.height()-5*(brows-1))/brows
        for i,bay in enumerate(bays):
            r,c=divmod(i,bcols); br=QRectF(bay_area.left()+c*(bw+5),bay_area.top()+r*(bh+5),bw,bh)
            key=str(getattr(bay,"key",f"bay{i}")); tone=self._bay_tone(bay)
            p.setBrush(tone); p.setPen(QPen(GREEN if self.selected==key else QColor("#465767"),2 if self.selected==key else 1)); p.drawRoundedRect(br,3,3)
            p.setPen(QColor("#E8EEF7")); f.setPixelSize(8); f.setBold(False); p.setFont(f)
            p.drawText(QRectF(br.left()+2, br.top()+1, br.width()-4, 12), Qt.AlignmentFlag.AlignLeft, key)
            self.hits.append(Hit(QRectF(br),"bay",key,f"{label} · {key}",bay))
            self._paint_skus(p, br, bay)

    def _bay_products(self, bay):
        try:
            from open_late.shelf_model import sku_index_v1
            index = sku_index_v1()
        except Exception:
            return []
        found = []
        seen = set()
        tiers = list(getattr(bay, "tiers", ()) or ())
        tiers.sort(key=lambda item: 0 if item and item[0] == "eye" else 1)
        for _tier, items in tiers:
            for sku, _facings in items or ():
                try:
                    pos = int(sku)
                except (TypeError, ValueError):
                    continue
                if not (0 <= pos < len(index)):
                    continue
                pid = index[pos]
                if pid in seen:
                    continue
                seen.add(pid)
                product = self.products.get(pid)
                found.append((pid, str(getattr(product, "name", pid) or pid), product))
                if len(found) >= 4:
                    return found
        return found

    def _paint_skus(self, painter, bay_rect, bay):
        products = self._bay_products(bay)
        if not products or bay_rect.height() < 26 or bay_rect.width() < 28:
            return
        from open_late.ui.hq_product import paint_product_art

        slot = bay_rect.width() / len(products)
        art_h = min(28.0, max(12.0, bay_rect.height() * 0.55))
        top = bay_rect.bottom() - art_h - 2
        for index, (pid, name, product) in enumerate(products):
            rect = QRectF(bay_rect.left() + index * slot + 2, top, max(8.0, slot - 4), art_h)
            self.hits.append(Hit(rect, "sku", pid, name, product))
            if product is None:
                continue
            paint_product_art(
                painter,
                QRect(int(rect.x()), int(rect.y()), max(8, int(rect.width())), max(8, int(rect.height()))),
                product,
            )

    def _bay_tone(self,bay):
        if self.overlay in ("stockouts","availability"):
            ids=[]
            for _tier,items in getattr(bay,"tiers",()) or ():
                ids += [sku for sku,_f in items]
            if ids and any(self._stock_for(sku)<=0 for sku in ids): return QColor("#7A2630")
            return QColor("#245B42")
        if self.overlay in ("sales","traffic"):
            return QColor("#7A5028") if int(getattr(bay,"order",0))%3==0 else QColor("#35566F")
        if self.overlay in ("profit","margin"): return QColor("#604A86")
        return QColor("#334657")

    def _stock_for(self, sku):
        ids=[]
        try:
            from open_late.shelf_model import sku_index_v1
            ids=list(sku_index_v1())
        except Exception: pass
        pid=ids[sku] if isinstance(sku,int) and 0<=sku<len(ids) else str(sku)
        line=self.stock.get(pid); return int(getattr(line,"on_hand",0) or 0) if line is not None else 0

    def _paint_checkout(self,p,store):
        rect=QRectF(store.center().x()-95,store.bottom()-40,190,27)
        p.setBrush(QColor("#172A3B")); p.setPen(QPen(QColor("#91A4B5"),1)); p.drawRoundedRect(rect,4,4)
        p.setPen(QColor("#FFFFFF")); p.drawText(rect,Qt.AlignmentFlag.AlignCenter,"CHECKOUT  ·  LIVE QUEUES")

    def _paint_shoppers(self, painter, _store):
        painter.setPen(Qt.PenStyle.NoPen)
        if not self._lanes:
            return
        shirts = ("#3B82F6", "#E24B4B", "#3FAE63", "#F0C419", "#8F5BC1", "#1F2937")
        for index, (lane_index, progress) in enumerate(self.walkers):
            lane = self._lanes[lane_index % len(self._lanes)]
            x = lane.center().x()
            y = lane.top() + progress * lane.height()
            painter.setBrush(QColor(shirts[index % len(shirts)]))
            painter.drawRoundedRect(QRectF(x - 2.2, y - 1, 4.4, 6), 1, 1)
            painter.setBrush(QColor("#E6C2A0"))
            painter.drawEllipse(QPointF(x, y - 4), 2.1, 2.1)

    LEGEND = (
        ("Gondola", QColor("#35566F")),
        ("Endcap", QColor("#F4C84A")),
        ("Wall Run", QColor("#3FAE63")),
        ("Cooler/Freezer", QColor("#3B8FD1")),
        ("Service Area", QColor("#8F5BC1")),
        ("Promotional Display", QColor("#D2574E")),
    )

    def _paint_legend(self, painter, canvas):
        labels = self.LEGEND
        x = canvas.left() + 8
        y = canvas.bottom() - 12
        font = painter.font()
        font.setPixelSize(8)
        painter.setFont(font)
        for text, color in labels:
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(x, y - 8, 9, 9), 2, 2)
            painter.setPen(QColor(MUTED))
            width = painter.fontMetrics().horizontalAdvance(text) + 8
            painter.drawText(QRectF(x + 12, y - 12, width, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
            x += 14 + width


class _ShelfFace(QWidget):
    """The selected aisle, drawn as numbered tiers the way the floor plan's side panel is."""

    skuPicked = Signal(str)
    _ORDER = ("top", "eye", "hand", "well", "bottom")
    _LABEL = {"top": "Top", "eye": "Eye", "hand": "Hand", "well": "Well", "bottom": "Bottom"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("livingShelf")
        self.setMinimumWidth(280)
        self.bay = None
        self.products = {}
        self.stock = {}
        self.selected = ""
        self.feet = 0
        self.caption = ""
        self.detail = ""
        self.hits = []
        self.setMinimumHeight(220)
        self.open_btn = QPushButton("View in inventory", self)
        self.open_btn.setObjectName("livingOpenInventory")
        self.open_btn.clicked.connect(self._open_selected)
        self.open_btn.setEnabled(False)

    def resizeEvent(self, event):
        self.open_btn.setGeometry(max(8, self.width() - 148), self.height() - 32, 136, 26)
        super().resizeEvent(event)

    def set_bay(self, bay, products, stock, feet: int = 0) -> None:
        self.bay = bay
        self.products = dict(products or {})
        self.stock = dict(stock or {})
        self.feet = int(feet or 0)
        self.selected = self._first_sku(bay)
        dept = _name(getattr(bay, "dept", "") or "Shelf")
        self.caption = f"{dept}  ·  {self.feet} ft" if self.feet else dept
        self.open_btn.setEnabled(bool(self.selected))
        self.update()

    def select(self, product_id: str) -> None:
        self.selected = str(product_id or "")
        self.open_btn.setEnabled(bool(self.selected))
        self.update()

    def _open_selected(self) -> None:
        if self.selected:
            self.skuPicked.emit(self.selected)

    def _first_sku(self, bay) -> str:
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
        for rect, pid in self.hits:
            if rect.contains(pos):
                self.select(pid)
                return
        super().mousePressEvent(event)

    def paintEvent(self, _event):
        from open_late.shelf_model import sku_index_v1
        from open_late.text import money
        from open_late.ui.hq_product import paint_product_art, product_size, product_title

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#071425"))
        painter.setPen(QPen(QColor("#173A55"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -2, -2), 8, 8)
        self.hits = []
        bay = self.bay
        if bay is None:
            painter.setPen(QColor(MUTED))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Select an aisle")
            painter.end()
            return
        index = []
        try:
            index = list(sku_index_v1())
        except Exception:
            index = []
        banner = QRect(8, 8, self.width() - 16, 26)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#143B29"))
        painter.drawRoundedRect(banner, 5, 5)
        painter.setPen(QColor("#19E86A"))
        font = painter.font()
        font.setPixelSize(13)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(banner.adjusted(10, 0, -8, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.caption or _name(getattr(bay, "dept", "") or "Shelf"))
        tiers = {name: items for name, items in (getattr(bay, "tiers", ()) or ())}
        ordered = [name for name in self._ORDER if name in tiers]
        ordered += [name for name in tiers if name not in ordered]
        top = 44
        bottom = self.height() - 118
        count = max(1, len(ordered))
        band = max(28, (bottom - top) / count)
        chosen = None
        chosen_facings = 0
        for row, name in enumerate(ordered):
            y = int(top + row * band)
            number = len(ordered) - row
            label = f"{number} {self._LABEL.get(name, name.title())}".strip()
            painter.setPen(QColor("#19E86A") if name == "eye" else QColor(MUTED))
            font.setPixelSize(10)
            font.setBold(name == "eye")
            painter.setFont(font)
            painter.drawText(QRect(8, y, 52, int(band)), Qt.AlignmentFlag.AlignVCenter, label)
            items = list(tiers.get(name) or ())[:6]
            if not items:
                continue
            cell = max(8, (self.width() - 68) / len(items))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#243044"))
            painter.drawRect(QRect(64, y + int(band) - 6, self.width() - 76, 4))
            for col, (sku, facings) in enumerate(items):
                try:
                    pos = int(sku)
                except (TypeError, ValueError):
                    continue
                pid = index[pos] if 0 <= pos < len(index) else ""
                product = self.products.get(pid)
                if product is None:
                    continue
                rect = QRect(int(64 + col * cell), y + 4, max(8, int(cell) - 6), max(16, int(band) - 10))
                self.hits.append((rect, pid))
                painter.setPen(QPen(QColor("#19E86A") if pid == self.selected else QColor("#173A55"), 2 if pid == self.selected else 1))
                painter.setBrush(QColor("#F7F3EA"))
                painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 4, 4)
                if pid == self.selected:
                    chosen = product
                    chosen_facings = int(facings)
                paint_product_art(painter, rect.adjusted(4, 4, -4, -4), product)
        card = QRect(8, self.height() - 112, self.width() - 16, 74)
        painter.setBrush(QColor("#0E2035"))
        painter.setPen(QPen(QColor("#173A55"), 1))
        painter.drawRoundedRect(card, 6, 6)
        if chosen is None:
            self.detail = "Click a package"
            painter.setPen(QColor(MUTED))
            painter.drawText(card.adjusted(10, 8, -10, -8), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, self.detail)
        else:
            line = self.stock.get(self.selected)
            on_hand = int(getattr(line, "on_hand", 0) or 0) if line is not None else 0
            bits = [bit for bit in (str(getattr(chosen, "brand", "") or ""), product_size(chosen), f"{chosen_facings} facings", f"{on_hand} on hand", _name(getattr(chosen, "department", "") or getattr(bay, "dept", ""))) if bit]
            supplier = str(getattr(chosen, "supplier_id", "") or "")
            if supplier:
                bits.append(supplier)
            bits.append(f"Cost {money(int(getattr(chosen, 'cost', 0) or 0))}")
            bits.append(f"Retail {money(int(getattr(chosen, 'price', 0) or 0))}")
            self.detail = "   ·   ".join(bits)
            painter.setPen(QColor(TEXT))
            font.setPixelSize(12)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(card.adjusted(10, 6, -10, -40), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, product_title(chosen))
            font.setPixelSize(10)
            font.setBold(False)
            painter.setFont(font)
            painter.setPen(QColor(MUTED))
            painter.drawText(card.adjusted(10, 26, -10, -8), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap, self.detail)
        painter.end()


class LivingStoreView(QWidget):
    """Toolbar + live floor. Drop-in child for PlanogramPage or StoreLayoutView."""
    bayPicked = Signal(str); departmentPicked = Signal(str); skuPicked = Signal(str)
    def __init__(self,parent=None):
        super().__init__(parent); self.setObjectName("livingStoreView")
        self.setStyleSheet(f"""
        QWidget#livingStoreView{{background:#071425;color:{TEXT};}}
        QFrame#livingToolbar{{background:{PANEL};border:1px solid {LINE};border-radius:7px;}}
        QLabel{{color:{TEXT};background:transparent;}} QComboBox{{background:#0B1A2D;color:{TEXT};border:1px solid {LINE};border-radius:4px;padding:5px 8px;}}
        QPushButton{{background:#10273D;color:{TEXT};border:1px solid {LINE};border-radius:4px;padding:5px 9px;font-weight:600;}} QPushButton:hover{{border-color:#19E86A;}}
        """)
        root=QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(7)
        bar=QFrame(); bar.setObjectName("livingToolbar"); row=QHBoxLayout(bar); row.setContentsMargins(8,6,8,6)
        self.heading=QLabel("Store Floor Plan"); self.heading.setObjectName("livingHeading"); f=self.heading.font(); f.setBold(True); f.setPixelSize(14); self.heading.setFont(f); row.addWidget(self.heading)
        self.stats=QLabel(""); self.stats.setObjectName("livingStats"); row.addWidget(self.stats)
        row.addStretch(1); row.addWidget(QLabel("Live")); row.addWidget(QLabel("Overlay")); self.overlay=QComboBox();
        for label,key in (("Customer Traffic","traffic"),("Sales","sales"),("Profit","profit"),("Availability","availability"),("Stockouts","stockouts"),("Planogram Performance","planogram")): self.overlay.addItem(label,key)
        row.addWidget(self.overlay); row.addWidget(QLabel("Zoom")); self.zoom=QSlider(Qt.Orientation.Horizontal); self.zoom.setRange(70,160); self.zoom.setValue(100); self.zoom.setFixedWidth(110); row.addWidget(self.zoom)
        self.reset=QPushButton("Reset View"); row.addWidget(self.reset)
        self.refs=QPushButton("References"); self.refs.setObjectName("livingReferences"); row.addWidget(self.refs)
        root.addWidget(bar)
        self.note=QLabel("Click an aisle to show its shelf. Click the gold package, or View in inventory, to open that product.")
        self.note.setWordWrap(True)
        root.addWidget(self.note)
        self.canvas=LivingStoreCanvas()
        self.gallery=None
        self.face=_ShelfFace()
        self.stack=QStackedWidget(); self.stack.addWidget(self.canvas)
        split=QHBoxLayout(); split.setSpacing(8); split.addWidget(self.stack, 3); split.addWidget(self.face, 2); root.addLayout(split, 1)
        self.foot=QLabel(""); self.foot.setObjectName("livingFoot"); root.addWidget(self.foot)
        self.overlay.currentIndexChanged.connect(lambda: self.canvas.set_overlay(self.overlay.currentData())); self.zoom.valueChanged.connect(self.canvas.set_zoom); self.reset.clicked.connect(lambda: self.zoom.setValue(100))
        self.refs.clicked.connect(self._toggle_refs)
        self.canvas.bayPicked.connect(self._picked)
        self.canvas.departmentPicked.connect(self._picked)
        self.canvas.skuPicked.connect(self._picked)
        self.canvas.bayPicked.connect(self.bayPicked); self.canvas.departmentPicked.connect(self.departmentPicked); self.canvas.skuPicked.connect(self.skuPicked)
        self.face.skuPicked.connect(self.skuPicked)

    def _picked(self, ident: str) -> None:
        label = next((hit.label for hit in reversed(self.canvas.hits) if hit.ident == str(ident)), str(ident))
        self.note.setText(label)
        self._show_ident(str(ident))

    def _show_ident(self, ident: str) -> None:
        layout = self.canvas.layout_data
        bays = list(getattr(layout, "bays", ()) or ())
        bay = next((item for item in bays if str(getattr(item, "key", "")) == ident and not item.is_feature), None)
        if bay is None:
            bay = next((item for item in bays if str(getattr(item, "aisle", "")) == ident and not item.is_feature), None)
        if bay is None:
            bay = next((item for item in bays if str(getattr(item, "dept", "")) == ident and not item.is_feature), None)
        if bay is None:
            return
        widths = {"gondola": 3, "cooler": 3, "cooler_well": 3, "peg": 3, "endcap": 3, "table": 6, "rack": 4}
        mates = [item for item in bays if str(getattr(item, "aisle", "")) == str(getattr(bay, "aisle", ""))]
        feet = sum(widths.get(str(getattr(item, "fixture", "")), 3) for item in mates)
        self.face.set_bay(bay, self.canvas.products, self.canvas.stock, feet=feet)

    def load(self, layout, products, door=None, sales=None):
        self.canvas.set_store(layout, products, door=door, overlay=self.overlay.currentData(), sales=sales)
        city = str(getattr(door, "city", "") or "Store")
        sq = 0
        try:
            from open_late.shelf_model import size_spec

            sq = int((size_spec(getattr(layout, "size_id", "") or "") or {}).get("sq_ft") or 0)
        except Exception:
            sq = 0
        bays = list(getattr(layout, "bays", ()) or ())
        depts = {str(getattr(item, "dept", "")) for item in bays if str(getattr(item, "dept", "")) not in ("", "*")}
        self.heading.setText(f"Store Floor Plan  ·  {city}")
        self.stats.setText(f"{sq:,} sq ft    ·    {len(depts)} departments    ·    {len(bays)} fixtures" if sq else f"{len(depts)} departments    ·    {len(bays)} fixtures")
        first = next((item for item in bays if getattr(item, "kind", "") == "center" and not item.is_feature), None)
        if first is not None:
            self._show_ident(str(first.aisle))
        traffic = int(getattr(door, "foot_traffic", 0) or 0)
        sold = int(getattr(door, "last_sales", 0) or 0)
        days = list(getattr(door, "sales_days", []) or [])
        if days:
            sold = int(getattr(days[-1], "sales", sold) or 0)
        missing = 0
        try:
            from open_late.shelf_model import sku_index_v1
            from open_late.text import money

            index = list(sku_index_v1())
            seen = set()
            for bay in bays:
                for _tier, items in getattr(bay, "tiers", ()) or ():
                    for sku, _facings in items or ():
                        try:
                            pos = int(sku)
                        except (TypeError, ValueError):
                            continue
                        if not (0 <= pos < len(index)) or index[pos] in seen:
                            continue
                        seen.add(index[pos])
                        line = self.canvas.stock.get(index[pos])
                        if line is None or int(getattr(line, "on_hand", 0) or 0) <= 0:
                            missing += 1
        except Exception:
            from open_late.text import money
        self.foot.setText(f"Traffic  {traffic}      Sales  {money(sold)}      Out of stock  {missing}")

    def _toggle_refs(self) -> None:
        if self.gallery is None:
            from open_late.ui.visual_asset_gallery import VisualAssetGallery

            self.gallery = VisualAssetGallery()
            self.gallery.setObjectName("visualAssetGallery")
            self.stack.addWidget(self.gallery)
        showing = self.stack.currentWidget() is self.gallery
        self.stack.setCurrentWidget(self.canvas if showing else self.gallery)
        self.refs.setText("Live floor" if not showing else "References")
