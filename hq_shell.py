"""Corporate HQ play shell: navy rail, top bar, store switcher, alerts, one pane."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRect, QRegularExpression, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QPalette, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMenuBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from open_late.content import HELP
from open_late.text import money, weekday_name
from open_late.ui.hq_adapter import chain_info, chain_logo_path, regions_for, store_ids, store_pos
from open_late.ui.hq_economy import EconomyPage
from open_late.ui.hq_pages import DashboardPage, PosPage, StoresPage
from open_late.ui.hq_planogram import PlanogramPage
from open_late.ui.icons import icon_pixmap, quiet_icon
from open_late.ui.dashboard_theme_all_screens import dashboard_all_screens_stylesheet
from open_late.ui.theme import ACCENT, DASH_BG, DASH_MUTED, DASH_TEXT, DOWN, HQ_MUTED, HQ_TITLE, RAIL, RR_YELLOW, TEXT, dash_chrome_stylesheet, hq_stylesheet, ui_font


# app_id, label, icon id (from icons.TILE), desk index or None
RAIL_ITEMS = [
    ("home", "Dashboard", "overview", None),
    ("stores", "Store Portfolio", "expansion", None),
    ("sales", "Sales", "sales", 1),
    ("inventory", "Inventory", "inventory", 2),
    ("orders", "Orders", "orders", 3),
    ("staff", "Staff", "staff", 4),
    ("customers", "Customers", "customers", 5),
    ("marketing", "Marketing", "marketing", 6),
    ("books", "Finance", "books", 7),
    ("economy", "Economy", "economy", None),
    ("planograms", "Planograms", "expansion", None),
    ("market", "Market", "market", 9),
    ("journal", "Inbox", "journal", 10),
    ("settings", "Hours", "settings", 11),
    ("pos", "POS", "settings", None),
]

LEGACY_IDS = {item[0] for item in RAIL_ITEMS if item[3] is not None} | {"planograms", "expansion", "overview"}

BUTTON_TEXT = {
    "home": "Dashboard",
    "stores": "Stores",
    "sales": "Sales & Analytics",
    "inventory": "Inventory",
    "orders": "Purchasing & Suppliers",
    "staff": "Workforce",
    "delegation": "Delegation",
    "board": "Board",
    "archive": "Archive",
    "customers": "Customers & Loyalty",
    "marketing": "Marketing",
    "books": "Finance & Budget",
    "economy": "Market Intelligence",
    "planograms": "Planograms",
    "market": "Competitors",
    "journal": "Alerts",
    "settings": "Settings",
    "pos": "POS",
    "reporting": "Reports",
    "visiondeck": "Command Center",
}

# The bottom explorer list, in the order the BackOffice screens show it.
MODULES = [
    ("home", "Dashboard"),
    ("stores", "Stores"),
    ("sales", "Sales & Analytics"),
    ("inventory", "Inventory"),
    ("orders", "Purchasing & Suppliers"),
    ("customers", "Customers & Loyalty"),
    ("staff", "Workforce"),
    ("marketing", "Marketing"),
    ("books", "Finance & Budget"),
    ("market", "Competitors"),
    ("economy", "Market Intelligence"),
    ("visiondeck", "Command Center"),
    ("journal", "Alerts"),
    ("reporting", "Reports"),
    ("planograms", "Planograms"),
    ("pos", "POS"),
    ("settings", "Settings"),
]
PURPLE = "#3F1D72"
OSPREY = "#0E5C32"
OSPREY_DEEP = "#0C3B22"
OSPREY_BAR = "#145C32"
RAIL_WIDTH = 228

# Section title and the task links under it. The module buttons below stay the
# tested rail entries; these are the BackOffice explorer items from each screen.
EXPLORER = {
    "home": ("Dashboard", (("Today", "home"), ("Command Center", "visiondeck"), ("Inbox", "journal"), ("The book", "books"))),
    "stores": (
        "Stores",
        (
            ("Store Portfolio", "stores"),
            ("Open New Store", "market"),
            ("Leases and Loans", "market"),
            ("Staffing", "staff"),
            ("Store P&L", "books"),
        ),
    ),
    "sales": ("Merchandising", (("Sales", "sales"),)),
    "inventory": (
        "Inventory",
        (
            ("Item Maintenance", "inventory"),
            ("Stock Levels", "inventory"),
            ("Purchase Orders", "orders"),
            ("Receiving", "orders"),
            ("Vendors", "inventory"),
            ("Shrink", "inventory"),
        ),
    ),
    "orders": ("Ordering", (("Open deliveries", "orders"), ("Purchase orders", "inventory"))),
    "staff": ("Staffing", (("Roster", "staff"),)),
    "customers": ("Customers", (("Customers", "customers"),)),
    "marketing": ("Marketing", (("Campaigns", "marketing"),)),
    "books": (
        "Accounting",
        (
            ("Profit and Loss", "books"),
            ("Balance Sheet", "books"),
            ("Cash Flow", "books"),
            ("Loans", "market"),
            ("Taxes", "books"),
            ("Budget", "books"),
        ),
    ),
    "economy": ("Economy", (("The economy", "economy"), ("Rivals", "market"))),
    "planograms": (
        "Planograms",
        (
            ("Store Layout", "planograms"),
            ("Aisles", "planograms"),
            ("Endcaps", "planograms"),
            ("Out of Stocks", "planograms"),
            ("Scout Rival", "planograms"),
        ),
    ),
    "market": ("Rivals", (("Market", "market"), ("Open New Store", "market"))),
    "journal": ("Inbox", (("Open notes", "journal"), ("Dashboard", "home"))),
    "settings": ("Daily Operations", (("Store Hours", "settings"), ("Open the floor", "home"))),
    "pos": ("POS", (("Switch System", "pos"), ("Store tills", "stores"))),
    "reporting": (
        "Reporting",
        (("Weekly sales", "sales"), ("Profit and Loss", "books"), ("Balance Sheet", "books")),
    ),
}


def _scoped_dash_sheet() -> str:
    """dash_chrome_stylesheet() with every rule gated on hqShell[dashDark="true"].

    The shell keeps one fixed sheet (light rules + these gated dark rules), so
    switching chrome flips a property and repolishes the few widgets the dark
    rules name instead of re-running setStyleSheet over every page (~180 ms).
    """
    gate = 'QWidget#hqShell[dashDark="true"]'
    out = []
    for block in dash_chrome_stylesheet().split("}"):
        if "{" not in block:
            out.append(block)
            continue
        head, body = block.split("{", 1)
        selectors = []
        for sel in head.split(","):
            sel = sel.strip()
            if not sel:
                continue
            if sel == "QWidget#hqShell":
                selectors.append(gate)
            else:
                selectors.append(f"{gate} {sel}")
        out.append(",\n    ".join(selectors) + " {" + body)
    return "}".join(out)


# objectNames named as rule subjects in dash_chrome_stylesheet(); these are the
# only widgets whose computed style changes when the gate property flips.
_DASH_SUBJECT_RE = QRegularExpression(
    "^(hqMain|hqBody|hqPages|dashboardPage|economyPage|hqTopBar|breadcrumb|chainName|dayChip|trayCash|"
    "pageTitle|pageDeck|pnlNote|topSearch|scopeBtn|scopeBtnOn|chainChip|alertsBtn|economyStrip|railNavOn)$"
)


def rail_label(app_id: str, corporate: bool) -> str:
    if app_id == "planograms":
        return "Planograms" if corporate else "Expansion"
    for ident, label, _icon, _index in RAIL_ITEMS:
        if ident == app_id:
            return label
    return app_id.title()



BRAND_LOGO = Path(__file__).resolve().parent.parent / "assets" / "brand" / "game_icon.png"


def brand_logo_pixmap(max_w: int, max_h: int) -> QPixmap:
    if not BRAND_LOGO.exists():
        return QPixmap()
    pix = QPixmap(str(BRAND_LOGO))
    if pix.isNull():
        return pix
    # The official wordmark is a large RGBA canvas with padding; crop to the
    # opaque ink so the rail mark is not a tiny tile in empty space.
    image = pix.toImage()
    rect = image.alphaRegion().boundingRect() if hasattr(image, "alphaRegion") else None
    if rect is None or not rect.isValid():
        min_x, min_y, max_x, max_y = image.width(), image.height(), -1, -1
        for y in range(0, image.height(), 2):
            for x in range(0, image.width(), 2):
                if image.pixelColor(x, y).alpha() > 20:
                    if x < min_x:
                        min_x = x
                    if y < min_y:
                        min_y = y
                    if x > max_x:
                        max_x = x
                    if y > max_y:
                        max_y = y
        if max_x >= min_x:
            from PySide6.QtCore import QRect
            # step-2 scan; pad a couple of pixels back out
            rect = QRect(max(0, min_x - 2), max(0, min_y - 2), max_x - min_x + 5, max_y - min_y + 5)
            rect = rect.intersected(image.rect())
        else:
            from PySide6.QtCore import QRect
            rect = image.rect()
    else:
        from PySide6.QtCore import QRect
        rect = QRect(rect)
    if rect.width() > 8 and rect.height() > 8:
        pix = QPixmap.fromImage(image.copy(rect))
    return pix.scaled(
        max_w,
        max_h,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def _lab(text: str, size: int = 13, weight=QFont.Weight.Normal, color: str = TEXT) -> QLabel:
    label = QLabel(text)
    label.setFont(ui_font(size, weight))
    label.setStyleSheet(f"color: {color}; background: transparent;")
    return label


_NAV_OFF = (
    "QPushButton { color: #E7EEF8; background: #07111F; border: none; border-radius: 6px; text-align: left;"
    " padding: 0px 10px; margin: 1px 8px; font-size: 12px; font-weight: 600; }"
    "QPushButton:hover { background: #163A6E; }"
)
_NAV_ON = (
    "QPushButton { color: #FFFFFF; background: #1D4E9C; border: none; border-radius: 6px; text-align: left;"
    " padding: 0px 10px; margin: 1px 8px; font-size: 12px; font-weight: 700; }"
)


def _cart_mark() -> QPixmap:
    pix = QPixmap(28, 28)
    pix.fill(Qt.GlobalColor.transparent)
    from PySide6.QtGui import QPainter, QPen

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#12B7E8"))
    painter.drawRoundedRect(0, 0, 28, 28, 6, 6)
    painter.setPen(QPen(QColor("#FFFFFF"), 1.6))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(7, 9, 14, 9, 2, 2)
    painter.drawLine(9, 9, 10, 6)
    painter.drawLine(10, 6, 18, 6)
    painter.drawLine(18, 6, 19, 9)
    painter.setBrush(QColor("#FFFFFF"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(9, 19, 3, 3)
    painter.drawEllipse(16, 19, 3, 3)
    painter.end()
    return pix


def _deck_mark() -> QPixmap:
    """The blue VisionDeck chevron that sits beside the word in the header."""
    pix = QPixmap(18, 16)
    pix.fill(Qt.GlobalColor.transparent)
    from PySide6.QtGui import QPainter, QPolygonF

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#2E9BFF"))
    painter.drawPolygon(QPolygonF([QPointF(1, 2), QPointF(9, 14), QPointF(17, 2), QPointF(13, 2), QPointF(9, 9), QPointF(5, 2)]))
    painter.end()
    return pix


def _nav_icon(app_id: str) -> QIcon:
    """A small white mark for the green rail."""
    pix = QPixmap(16, 16)
    pix.fill(Qt.GlobalColor.transparent)
    painter_pen = QColor("#FFFFFF")
    from PySide6.QtGui import QPainter, QPen

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(painter_pen, 1.4))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    if app_id == "home":
        painter.drawRect(3, 7, 10, 7)
        painter.drawLine(2, 7, 8, 2)
        painter.drawLine(8, 2, 14, 7)
    elif app_id == "stores":
        painter.drawRect(2, 6, 12, 8)
        painter.drawRect(6, 9, 4, 5)
    elif app_id in ("sales", "reporting", "economy"):
        painter.drawLine(2, 12, 6, 7)
        painter.drawLine(6, 7, 10, 10)
        painter.drawLine(10, 10, 14, 3)
    elif app_id == "planograms":
        painter.drawRect(2, 2, 5, 5)
        painter.drawRect(9, 2, 5, 5)
        painter.drawRect(2, 9, 5, 5)
        painter.drawRect(9, 9, 5, 5)
    elif app_id == "inventory":
        painter.drawRect(3, 5, 10, 8)
        painter.drawLine(3, 8, 13, 8)
    elif app_id == "orders":
        painter.drawRect(3, 4, 10, 8)
        painter.drawLine(3, 12, 1, 14)
    elif app_id == "books":
        painter.drawRect(4, 2, 8, 12)
        painter.drawLine(6, 5, 10, 5)
        painter.drawLine(6, 8, 10, 8)
    elif app_id == "customers":
        painter.drawEllipse(6, 2, 4, 4)
        painter.drawArc(3, 8, 10, 8, 0, 180 * 16)
    elif app_id == "marketing":
        painter.drawEllipse(3, 5, 6, 6)
        painter.drawLine(9, 8, 13, 5)
    elif app_id == "market":
        painter.drawEllipse(3, 3, 10, 10)
        painter.drawLine(8, 3, 8, 13)
    elif app_id == "pos":
        painter.drawRect(2, 3, 12, 8)
        painter.drawLine(5, 11, 5, 14)
        painter.drawLine(11, 11, 11, 14)
    else:
        painter.drawEllipse(3, 3, 10, 10)
        painter.drawLine(8, 8, 12, 12)
    painter.end()
    return QIcon(pix)


class Rail(QFrame):
    open_app = Signal(str)
    open_task = Signal(str, str)
    new_shop = Signal()
    save_now = Signal()
    front_door = Signal()
    help = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("hqRail")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(True)
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor("#FFFFFF"))
        pal.setColor(QPalette.ColorRole.Base, QColor("#FFFFFF"))
        self.setPalette(pal)
        self.setFixedWidth(RAIL_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self._corporate = False
        self._compact = False
        self.buttons: dict[str, QPushButton] = {}
        self.quiet_buttons: dict[str, QPushButton] = {}
        self.scroll = None
        self.inbox_badge = 0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.header = QFrame()
        self.header.setObjectName("ospreyHead")
        self.header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.header.setFixedHeight(32)
        head = QHBoxLayout(self.header)
        head.setContentsMargins(8, 0, 8, 0)
        head.setSpacing(6)
        self.section_icon = QLabel()
        self.section_icon.setFixedSize(18, 18)
        self.section_icon.setStyleSheet("background: transparent;")
        head.addWidget(self.section_icon)
        self.section_title = QLabel("Dashboard")
        self.section_title.setObjectName("ospreySection")
        head.addWidget(self.section_title, stretch=1)
        layout.addWidget(self.header)
        self.logo = QLabel(self)
        self.logo.setObjectName("railLogo")
        self.logo.setToolTip("Back Office: Retail")
        self._apply_logo()
        self.logo.hide()
        self.tasks_host = QWidget()
        self.tasks_host.setObjectName("ospreyTasks")
        self.tasks_box = QVBoxLayout(self.tasks_host)
        self.tasks_box.setContentsMargins(8, 6, 8, 4)
        self.tasks_box.setSpacing(0)
        layout.addWidget(self.tasks_host)
        self.module_head = QFrame()
        self.module_head.setObjectName("ospreyHead")
        self.module_head.setFixedHeight(28)
        module_row = QHBoxLayout(self.module_head)
        module_row.setContentsMargins(10, 0, 8, 0)
        self.module_title = QLabel("Dashboard")
        self.module_title.setObjectName("ospreySection")
        module_row.addWidget(self.module_title)
        layout.addWidget(self.module_head)
        self.nav_host = QWidget()
        self.nav_host.setObjectName("railNavHost")
        nav = QVBoxLayout(self.nav_host)
        nav.setContentsMargins(0, 0, 0, 0)
        nav.setSpacing(0)
        self.nav = nav
        for app_id, label in MODULES:
            btn = QPushButton(label)
            btn.setObjectName("railNav")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setIcon(_nav_icon(app_id))
            btn.setIconSize(QPixmap(16, 16).size())
            btn.setFixedHeight(26)
            btn.setStyleSheet(_NAV_OFF)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setToolTip(label)
            btn.clicked.connect(lambda _=False, ident=app_id: self.open_app.emit(ident))
            nav.addWidget(btn)
            self.buttons[app_id] = btn
            if app_id == "economy":
                section = QLabel("VISIONDECK")
                section.setObjectName("visiondeckSection")
                nav.addWidget(section)
        nav.addStretch(1)
        layout.addWidget(self.nav_host, stretch=1)
        self.footer = QWidget(self)
        self.footer.setObjectName("railTool")
        self.footer_box = QVBoxLayout(self.footer)
        self.footer.hide()
        for text, signal, kind in (
            ("Help", self.help, "help"),
            ("Save", self.save_now, "save"),
            ("Front door", self.front_door, "door"),
        ):
            btn = QPushButton(text, self.footer)
            btn.setObjectName("railQuiet")
            btn.setToolTip(text)
            btn.hide()
            glyph = quiet_icon(kind, 14)
            btn.setIcon(QIcon(glyph))
            btn.setIconSize(glyph.size())
            btn.clicked.connect(signal.emit)
            self.quiet_buttons[text] = btn
        self._show_tasks("home")
        self.header.hide()
        self.tasks_host.hide()
        self.module_head.hide()
        self.logo.hide()
        brand = QWidget()
        brand.setObjectName("railBrand")
        brand_row = QHBoxLayout(brand)
        brand_row.setContentsMargins(10, 8, 8, 4)
        brand_row.setSpacing(8)
        mark = QLabel()
        mark.setPixmap(_cart_mark())
        mark.setFixedSize(28, 28)
        brand_row.addWidget(mark, alignment=Qt.AlignmentFlag.AlignTop)
        brand_box = QVBoxLayout()
        brand_box.setSpacing(1)
        title = QLabel("Back Office: Retail")
        title.setObjectName("railBrandTitle")
        title.setWordWrap(True)
        kicker = QLabel("MANAGE  ·  GROW  ·  COMPETE")
        kicker.setObjectName("railBrandKicker")
        kicker.setWordWrap(True)
        brand_box.addWidget(title)
        brand_box.addWidget(kicker)
        brand_row.addLayout(brand_box, stretch=1)
        layout.insertWidget(0, brand)
        brand.hide()
        motto = QLabel("v1.0   A VISIONDECK EXPERIENCE\nREAL STORES. REAL PEOPLE.\nREAL POSSIBILITIES.")
        motto.setObjectName("railMotto")
        motto.setContentsMargins(10, 4, 8, 8)
        layout.addWidget(motto)
        self.setStyleSheet(
            "QFrame#hqRail, QWidget#railNavHost, QWidget#railBrand { background: #07111F; }"
            "QWidget#railBrand, QLabel#railBrandTitle, QLabel#railBrandKicker, QLabel#railMotto {"
            " background: transparent; }"
            "QLabel#railBrandTitle { color: #FFFFFF; font-size: 16px; font-weight: 700; }"
            "QLabel#railBrandKicker { color: #8FB4FF; font-size: 9px; letter-spacing: 0.6px; }"
            "QLabel#railMotto { color: #9FB0C8; font-size: 11px; }"
            "QLabel#visiondeckSection { color: #7AA2FF; background: transparent; font-size: 10px; font-weight: 700; padding: 4px 10px 0px 10px; }"
            "QPushButton#railNav, QPushButton#railNavOn {"
            " color: #E7EEF8; background: transparent; border: none; text-align: left; padding: 0 12px; }"
            "QPushButton#railNavOn { background: #1D4E9C; }"
            "QPushButton#railNav:hover { background: #163A6E; }"
        )

    def _apply_logo(self) -> None:
        self.logo.setMinimumHeight(32)
        self.logo.setPixmap(QPixmap())
        self.logo.setText("Back Office: Retail")
        self.logo.setStyleSheet("color: #FFFFFF; background: transparent; font-weight: 700;")

    def mount_topbar(self, topbar) -> None:
        self.footer_box.addWidget(topbar, stretch=1)

    def _face(self, app_id: str) -> str:
        label = BUTTON_TEXT.get(app_id, rail_label(app_id, self._corporate))
        if app_id == "journal" and self.inbox_badge:
            label = f"{label}  {self.inbox_badge}"
        return label

    def set_compact(self, compact: bool) -> None:
        self._compact = compact
        self.setFixedWidth(RAIL_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        for app_id, btn in self.buttons.items():
            btn.setText(self._face(app_id))
        for text, btn in self.quiet_buttons.items():
            btn.setText(text)
            btn.setToolTip(text)

    def _show_tasks(self, app_id: str) -> None:
        from open_late.ui.osprey_docs import section_icon

        title, tasks = EXPLORER.get(app_id, (BUTTON_TEXT.get(app_id, app_id.title()), ()))
        if getattr(self, "_task_section", None) == app_id and self.tasks_box.count() == len(tasks):
            return
        self._task_section = app_id
        self.section_title.setText(title)
        self.module_title.setText("Screens")
        kind = "inventory" if app_id == "inventory" else "books" if app_id in ("books", "reporting") else "planograms" if app_id == "planograms" else "stores"
        self.section_icon.setPixmap(section_icon(kind, 18))
        while self.tasks_box.count():
            item = self.tasks_box.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        for text, _ident in tasks:
            btn = QPushButton(f"{text}    ›")
            btn.setObjectName("ospreyTask")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(24)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            if text == "Scout Rival":
                btn.setEnabled(False)
                btn.setToolTip("Scout is not on the floor yet.")
            btn.clicked.connect(lambda _=False, section=app_id, label=text: self.open_task.emit(section, label))
            self.tasks_box.addWidget(btn)

    def set_corporate(self, corporate: bool) -> None:
        self._corporate = corporate
        if "planograms" in self.buttons:
            self.buttons["planograms"].setText(self._face("planograms"))
            self.buttons["planograms"].setToolTip(rail_label("planograms", corporate))

    def set_active(self, app_id: str) -> None:
        self._show_tasks(app_id)
        for ident, btn in self.buttons.items():
            btn.setObjectName("railNavOn" if ident == app_id else "railNav")
            btn.setStyleSheet(_NAV_ON if ident == app_id else _NAV_OFF)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def set_inbox(self, count: int, urgent: int) -> None:
        self.inbox_badge = count
        btn = self.buttons.get("journal")
        if btn is None:
            return
        btn.setText(self._face("journal"))
        label = BUTTON_TEXT.get("journal", "Inbox")
        btn.setToolTip(f"{count} open notes" if count else label)
        if urgent:
            btn.setStyleSheet("QPushButton#railNav, QPushButton#railNavOn { color: #FFB4AC; }")
        else:
            btn.setStyleSheet("")


class TopBar(QFrame):
    open_alerts = Signal()
    scope_changed = Signal(str, object)
    open_floor = Signal()
    close_day = Signal()
    next_morning = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("hqTopBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(44)
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 2, 4, 2)
        row.setSpacing(6)
        self.switcher = QPushButton("All stores")
        self.switcher.setObjectName("scopeBtn")
        self.switcher.setMinimumWidth(96)
        self.switcher.setMinimumHeight(26)
        self.switcher.setCursor(Qt.CursorShape.PointingHandCursor)
        self.menu = QMenu(self.switcher)
        self.switcher.setMenu(self.menu)
        self.switcher.clicked.connect(self.switcher.showMenu)
        self.chain_chip = QFrame()
        self.chain_chip.setObjectName("chainChip")
        chip = QHBoxLayout(self.chain_chip)
        chip.setContentsMargins(6, 2, 10, 2)
        chip.setSpacing(6)
        self.chain_logo = QLabel()
        self.chain_logo.setObjectName("chainLogo")
        self.chain_logo.setFixedSize(36, 24)
        self.chain_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chain_name = _lab("Northstar Market", 12, QFont.Weight.DemiBold)
        self.chain_name.setObjectName("chainName")
        chip.addWidget(self.chain_logo)
        chip.addWidget(self.chain_name)
        row.addWidget(self.chain_chip)
        row.addWidget(self.switcher)
        self.search = QLineEdit()
        self.search.setObjectName("topSearch")
        self.search.setPlaceholderText("Search stores or items")
        self.search.setMinimumWidth(188)
        self.search.setMaximumWidth(230)
        row.addWidget(self.search)
        self.breadcrumb = _lab("Dashboard  /  All stores", 12, color=HQ_MUTED)
        self.breadcrumb.setObjectName("breadcrumb")
        self.breadcrumb.setMinimumWidth(48)
        self.breadcrumb.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row.addWidget(self.breadcrumb, stretch=1)
        self.alerts = QPushButton("0")
        self.alerts.setObjectName("alertsBtn")
        self.alerts.setFixedSize(28, 28)
        self.alerts.setCursor(Qt.CursorShape.PointingHandCursor)
        self.alerts.setToolTip("Notifications")
        self.alerts.clicked.connect(self.open_alerts.emit)
        row.addWidget(self.alerts)
        self.cash = _lab("$0", 12, QFont.Weight.DemiBold)
        self.cash.setObjectName("trayCash")
        row.addWidget(self.cash)
        self.day = _lab("Mon  ·  Day 1  ·  Morning", 11, color=HQ_MUTED)
        self.day.setObjectName("dayChip")
        self.day.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self.day)
        self.to_desk = QPushButton("Open the floor")
        self.to_desk.setObjectName("toDesk")
        self.to_desk.setMinimumHeight(26)
        self.to_desk.clicked.connect(self.open_floor.emit)
        self.close_button = QPushButton("Advance day")
        self.close_button.setObjectName("closeDay")
        self.close_button.setMinimumHeight(26)
        self.close_button.clicked.connect(self.close_day.emit)
        self.next_button = QPushButton("Next morning")
        self.next_button.setObjectName("nextMorning")
        self.next_button.setMinimumHeight(26)
        self.next_button.clicked.connect(self.next_morning.emit)
        for button in (self.to_desk, self.close_button, self.next_button):
            button.hide()
            row.addWidget(button)
        self._scope = ("all", None)

    def set_scope_menu(self, state) -> None:
        self.menu.clear()
        action = self.menu.addAction("All stores")
        action.triggered.connect(lambda: self.scope_changed.emit("all", None))
        if state is None or not state.doors:
            if state is not None:
                action = self.menu.addAction(state.shop_name)
                action.triggered.connect(lambda: self.scope_changed.emit("store", "evansville"))
            return
        for region in regions_for(state):
            self.menu.addSeparator()
            region_action = self.menu.addAction(region)
            region_action.triggered.connect(lambda _=False, name=region: self.scope_changed.emit("region", name))
            for door in state.doors:
                if door.region != region:
                    continue
                pip = "●" if door.status == "open" else "○"
                store_action = self.menu.addAction(f"    {pip}  {door.city}, {door.state_name}")
                store_action.triggered.connect(lambda _=False, ident=door.id: self.scope_changed.emit("store", ident))

    def set_scope_label(self, kind: str, scope_id: str | None, state) -> None:
        self._scope = (kind, scope_id)
        if kind == "region" and scope_id:
            text = scope_id
        elif kind == "store" and scope_id:
            door = next((item for item in (state.doors if state else []) if item.id == scope_id), None)
            text = f"{door.city}, {door.state_name}" if door else (state.shop_name if state else "Store")
        else:
            text = "All stores"
        self.switcher.setText(text)

    def set_chain(self, info: dict) -> None:
        name = str(info.get("name") or "Northstar Market")
        self.chain_name.setText(name)
        self.chain_chip.setToolTip(name)
        path = chain_logo_path(info)
        pix = QPixmap(str(path)) if path.exists() else QPixmap()
        if not pix.isNull():
            self.chain_logo.setPixmap(pix.scaled(36, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self.chain_logo.setText(name[:1])

    def set_breadcrumb(self, module: str, scope: str) -> None:
        self.breadcrumb.setText(f"{module}  /  {scope}")

    def set_tray(self, cash: str, urgent: int, day: str, cash_tip: str | None = None) -> None:
        self.cash.setText(cash)
        self.cash.setToolTip(cash_tip or cash)
        self.alerts.setText(str(urgent))
        self.day.setText(day)
        if urgent:
            self.alerts.setStyleSheet(
                f"QPushButton {{ color: #FFFFFF; background: {DOWN}; border: none; border-radius: 14px; font-weight: 700; }}"
            )
        else:
            self.alerts.setStyleSheet(
                "QPushButton { color: #1A1A1A; background: rgba(0,0,0,16); border: none; border-radius: 14px; }"
            )

    def set_phase(self, phase: str, failed: bool = False, urgent: int = 0) -> None:
        if phase == "morning":
            self.to_desk.setText("OPEN THE FLOOR" if urgent == 0 else f"OPEN THE FLOOR ({urgent})")
        self.next_button.setText("Back to the front" if failed else "Next morning")
        self.to_desk.setVisible(phase == "morning")
        self.to_desk.setEnabled(phase == "morning")
        self.close_button.setVisible(phase == "desk")
        self.close_button.setEnabled(phase == "desk")
        self.next_button.setVisible(phase in ("evening", "gameover"))
        self.next_button.setEnabled(phase in ("evening", "gameover"))


class AlertsDrawer(QFrame):
    open_inbox = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("alertsDrawer")
        self.setFixedWidth(320)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        head = QHBoxLayout()
        head.setSpacing(8)
        self.clock = _lab("11:00", 28, QFont.Weight.Bold)
        head.addWidget(self.clock, stretch=1)
        close = QPushButton("Close")
        close.setObjectName("alertsClose")
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setStyleSheet(
            "QPushButton#alertsClose { background: #0E2244; color: #F4F7FB;"
            " border: 1px solid #2A4A72; border-radius: 8px; padding: 4px 12px; font-weight: 600; }"
        )
        close.clicked.connect(self.hide)
        head.addWidget(close, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(head)
        self.meta = _lab("Monday  ·  Day 1  ·  Morning", 12, color=HQ_MUTED)
        layout.addWidget(self.meta)
        self.stats = QHBoxLayout()
        layout.addLayout(self.stats)
        layout.addWidget(_lab("NOTIFICATIONS", 10, QFont.Weight.DemiBold, HQ_MUTED))
        self.feed = QVBoxLayout()
        self.feed.setSpacing(8)
        layout.addLayout(self.feed)
        layout.addStretch(1)
        more = QPushButton("Open Inbox")
        more.setObjectName("quiet")
        more.clicked.connect(self.open_inbox.emit)
        layout.addWidget(more)

    def mount_command(self, widget) -> None:
        from PySide6.QtWidgets import QScrollArea

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(widget)
        self.layout().insertWidget(max(0, self.layout().count() - 2), scroll, stretch=1)

    def set_header(self, clock: str, meta: str, cash: str, urgent: int, reviews: str, cash_tip: str | None = None) -> None:
        self.clock.setText(clock)
        self.meta.setText(meta)
        self._cash_tip = cash_tip or cash
        while self.stats.count():
            item = self.stats.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        for caption, value in (("Drawer", cash), ("Urgent", str(urgent)), ("Reviews", reviews)):
            col = QVBoxLayout()
            col.setSpacing(0)
            col.addWidget(_lab(caption, 10, QFont.Weight.DemiBold, HQ_MUTED))
            figure = _lab(value, 14, QFont.Weight.DemiBold)
            if caption == "Drawer":
                figure.setToolTip(getattr(self, "_cash_tip", None) or cash)
            col.addWidget(figure)
            wrap = QWidget()
            wrap.setLayout(col)
            self.stats.addWidget(wrap)

    def set_notes(self, notes: list[tuple[bool, str, str, list]]) -> None:
        while self.feed.count():
            item = self.feed.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        if not notes:
            self.feed.addWidget(_lab("The desk is clear.", 13, color=HQ_MUTED))
            return
        from open_late.ui.theme import DOWN as DOWN_COLOR
        for urgent, title, body, actions in notes[:5]:
            card = QFrame()
            card.setObjectName("noteCard")
            box = QVBoxLayout(card)
            box.setContentsMargins(10, 8, 10, 8)
            box.setSpacing(4)
            box.addWidget(_lab("Urgent" if urgent else "Note", 10, QFont.Weight.DemiBold, DOWN_COLOR if urgent else HQ_MUTED))
            box.addWidget(_lab(title, 13, QFont.Weight.DemiBold))
            snippet = body.split(".")[0].strip()
            if snippet and not snippet.endswith("."):
                snippet += "."
            note = _lab(snippet, 11, color=HQ_MUTED)
            note.setWordWrap(True)
            box.addWidget(note)
            if actions:
                row = QHBoxLayout()
                for index, (label, slot) in enumerate(actions[:2]):
                    btn = QPushButton(label)
                    if index != 0:
                        btn.setObjectName("quiet")
                    btn.setMinimumHeight(26)
                    btn.clicked.connect(slot)
                    row.addWidget(btn)
                row.addStretch(1)
                box.addLayout(row)
            self.feed.addWidget(card)


class FavoritesBar(QFrame):
    """Right-hand explorer from the BackOffice screenshots."""

    open_app = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("favoritesBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(176)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        title = QLabel("Favorites")
        title.setObjectName("favoritesTitle")
        title.setFixedHeight(28)
        title.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        title.setContentsMargins(8, 0, 8, 0)
        layout.addWidget(title)
        self.picker = QComboBox()
        self.picker.setObjectName("favoritesPick")
        self.picker.addItem("Favorites", "")
        self.picker.currentIndexChanged.connect(self._open)
        layout.addWidget(self.picker)
        self.recent = QLabel("Open a screen and it stays here.")
        self.recent.setObjectName("favoritesBody")
        self.recent.setWordWrap(True)
        self.recent.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self.recent)
        layout.addStretch(1)

    def remember(self, app_id: str, label: str) -> None:
        """Keep the screens that were actually opened, newest first."""
        if not app_id or not label:
            return
        self.picker.blockSignals(True)
        for index in range(self.picker.count() - 1, 0, -1):
            if self.picker.itemData(index) == app_id:
                self.picker.removeItem(index)
        self.picker.insertItem(1, label, app_id)
        while self.picker.count() > 8:
            self.picker.removeItem(self.picker.count() - 1)
        found = self.picker.findData(app_id)
        if found >= 0:
            self.picker.setCurrentIndex(found)
        self.picker.blockSignals(False)
        names = [self.picker.itemText(i) for i in range(1, self.picker.count())]
        self.recent.setText("\n".join(names))

    def _open(self, index: int) -> None:
        ident = self.picker.itemData(index)
        if ident:
            self.open_app.emit(str(ident))


_SEARCH_KINDS = ("store", "product", "order", "shipment", "staff", "manager", "inbox")
_SEARCH_LABEL = {
    "store": "Store",
    "product": "Item",
    "catalog": "Warehouse",
    "order": "Order",
    "shipment": "Truck",
    "staff": "Staff",
    "manager": "Manager",
    "inbox": "Inbox",
}


def company_hits(state, text: str, limit: int = 8) -> list[dict]:
    """Stores, items, orders, trucks, people, and inbox lines that match one query."""
    query = (text or "").strip().lower()
    if state is None or len(query) < 2:
        return []
    buckets: dict[str, list[dict]] = {kind: [] for kind in _SEARCH_KINDS}

    def add(kind: str, ident: str, label: str, page: str, **extra) -> None:
        rows = buckets[kind]
        if len(rows) >= 3 or any(row["id"] == ident for row in rows):
            return
        row = {"kind": kind, "id": ident, "label": label, "page": page}
        row.update(extra)
        rows.append(row)

    for door in state.doors:
        blob = " ".join((door.city, door.state_name, door.id, getattr(door, "region", "") or "")).lower()
        if query in blob:
            add("store", door.id, door.city, "stores")
    for product in state.products.values():
        blob = f"{product.name} {product.id} {product.brand}".lower()
        if query in blob:
            add("product", product.id, product.name, "inventory")
    for order in getattr(state, "orders", ()) or ():
        blob = f"{order.id} {order.supplier_id}".lower()
        if query in blob:
            add("order", order.id, order.id, "orders")
    for shipment in getattr(state, "shipments", ()) or ():
        door = next((item for item in state.doors if item.id == shipment.door_id), None)
        city = door.city if door is not None else shipment.door_id
        blob = f"{shipment.id} {shipment.door_id} {city}".lower()
        if query in blob:
            add("shipment", shipment.id, f"Truck to {city}", "orders")
    for person in getattr(state, "staff", ()) or ():
        if query in person.name.lower() or query in person.id.lower():
            add("staff", person.id, person.name, "staff")
    for manager in getattr(state, "managers", ()) or ():
        if query in manager.name.lower() or query in manager.id.lower():
            add("manager", manager.id, manager.name, "stores", door_id=manager.door_id)
    for message in getattr(state, "inbox", ()) or ():
        if getattr(message, "resolved", False):
            continue
        blob = f"{getattr(message, 'title', '')} {getattr(message, 'body', '')}".lower()
        if query in blob:
            add("inbox", str(getattr(message, "id", "")), str(getattr(message, "title", "Message")), "journal")
    hits: list[dict] = []
    for kind in _SEARCH_KINDS:
        for row in buckets[kind]:
            if len(hits) >= limit:
                return hits
            hits.append(row)
    return hits


class CompanySearch(QFrame):
    picked = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("companySearch")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "QFrame#companySearch { background: #FFFFFF; border: 1px solid #C5CED6; }"
        )
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(0, 4, 0, 4)
        self.box.setSpacing(0)
        self.hide()

    def show_hits(self, hits: list[dict]) -> None:
        while self.box.count():
            item = self.box.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        if not hits:
            self.hide()
            return
        for hit in hits:
            kind = _SEARCH_LABEL.get(hit["kind"], hit["kind"].title())
            button = QPushButton(f"{kind}   {hit['label']}")
            button.setObjectName("companyHit")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(
                "QPushButton { background: #FFFFFF; color: #1C2430; border: none;"
                " text-align: left; padding: 6px 10px; }"
                "QPushButton:hover { background: #E8F5EC; }"
            )
            button.clicked.connect(lambda _=False, item=hit: self.picked.emit(item))
            self.box.addWidget(button)
        self.setFixedHeight(min(320, 8 + 32 * len(hits)))
        self.show()
        self.raise_()


class HQShell(QFrame):
    open_app = Signal(str)
    open_floor = Signal()
    close_day = Signal()
    next_morning = Signal()
    new_shop = Signal()
    save_now = Signal()
    front_door = Signal()
    help = Signal()
    scope_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("hqShell")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        from open_late.ui.components import stylesheet as component_stylesheet

        self.setStyleSheet(
            hq_stylesheet() + _scoped_dash_sheet() + component_stylesheet() + dashboard_all_screens_stylesheet()
        )
        self._dash_dark = None
        self.host = None
        self.scope = ("all", None)
        self.current_id = "home"
        self._corporate = False
        self._favorites_open = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.menu = QMenuBar()
        self.menu.setObjectName("ospreyMenu")
        self.rail = Rail()
        self.topbar = TopBar()
        self._build_menu()
        menu_row = QWidget()
        menu_row.setObjectName("ospreyMenuRow")
        menu_lay = QHBoxLayout(menu_row)
        menu_row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        menu_row.setStyleSheet(
            "QWidget#ospreyMenuRow { background: #071A33; border-bottom: 1px solid #123056; }"
            "QLabel#barTitle { color: #FFFFFF; font-size: 18px; font-weight: 800; background: transparent; }"
            "QLabel#barManage { color: #8AA4C4; font-size: 8px; font-weight: 700; background: transparent; letter-spacing: 1.2px; }"
            "QLabel#barKicker { color: #7EB6FF; font-size: 8px; font-weight: 700; background: transparent; letter-spacing: 1px; }"
            "QLabel#barWord { color: #2E9BFF; font-size: 18px; font-weight: 800; background: transparent; letter-spacing: 1.4px; }"
            "QLabel#barTag { color: #9FB0C8; font-size: 8px; background: transparent; letter-spacing: 0.4px; }"
            "QPushButton#scopeBtn { background: #0E2244; color: #F4F7FB; border: 1px solid #2A4A72;"
            " border-radius: 8px; padding: 6px 14px; font-weight: 600; }"
            "QLineEdit#topSearch { background: #101C33; color: #F4F7FB; border: 1px solid #243656;"
            " border-radius: 4px; padding: 4px 8px; }"
            "QLabel#dayChip, QLabel#trayCash { color: #F4F7FB; background: transparent; font-weight: 700; }"
            "QPushButton#toDesk, QPushButton#closeDay, QPushButton#nextMorning {"
            " background: #1D4E9C; color: #FFFFFF; border: none; border-radius: 8px;"
            " padding: 4px 10px; font-weight: 700; }"
            "QPushButton#barQuiet { background: transparent; color: #D5E2F2; border: none;"
            " border-radius: 6px; padding: 2px 6px; font-weight: 600; }"
            "QPushButton#alertsBtn { background: #6B1D2A; color: #FFFFFF; border: none; border-radius: 14px; font-weight: 700; }"
        )
        menu_row.setMinimumHeight(58)
        menu_row.setMaximumHeight(64)
        menu_lay.setContentsMargins(16, 6, 12, 6)
        menu_lay.setSpacing(8)
        self.menu.hide()
        from open_late import GAME_NAME
        brand = QHBoxLayout()
        brand.setSpacing(8)
        cart = QLabel()
        cart.setPixmap(_cart_mark())
        cart.setFixedSize(28, 28)
        brand.addWidget(cart, alignment=Qt.AlignmentFlag.AlignVCenter)
        names = QVBoxLayout()
        names.setSpacing(0)
        self.bar_title = QLabel()
        self.bar_title.setObjectName("barTitle")
        self.bar_title.setTextFormat(Qt.TextFormat.RichText)
        self.bar_title.setText(
            '<span style="color:#FFFFFF;">Back Office:</span> '
            '<span style="color:#2EC8FF;">Retail</span>'
        )
        self.bar_title.setToolTip(GAME_NAME)
        manage = QLabel("MANAGE  ·  GROW  ·  COMPETE")
        manage.setObjectName("barManage")
        names.addWidget(self.bar_title)
        names.addWidget(manage)
        brand.addLayout(names)
        menu_lay.addLayout(brand)
        lock = QVBoxLayout()
        lock.setSpacing(0)
        kicker = QLabel("POWERED BY")
        kicker.setObjectName("barKicker")
        word_row = QHBoxLayout()
        word_row.setSpacing(6)
        mark = QLabel()
        mark.setPixmap(_deck_mark())
        mark.setFixedSize(18, 16)
        word = QLabel("VISIONDECK")
        word.setObjectName("barWord")
        word_row.addWidget(mark, alignment=Qt.AlignmentFlag.AlignVCenter)
        word_row.addWidget(word)
        tag = QLabel("INTELLIGENCE TODAY. A STRONGER TOMORROW.")
        tag.setObjectName("barTag")
        lock.addWidget(kicker)
        lock.addLayout(word_row)
        lock.addWidget(tag)
        menu_lay.addLayout(lock)
        self.topbar.search.setMinimumWidth(72)
        self.topbar.search.setMaximumWidth(140)
        self.topbar.search.setPlaceholderText("Search stores, items, reports...")
        self.topbar.search.returnPressed.connect(self._run_search)
        for widget in (
            self.topbar.switcher,
            self.topbar.search,
            self.topbar.cash,
            self.topbar.alerts,
            self.topbar.day,
            self._bar_button("Save", self.save_now),
            self._bar_button("Help", self.help),
            self._chuck_button(),
            self._board_button(),
            self._archive_button(),
            self.topbar.to_desk,
            self.topbar.close_button,
            self.topbar.next_button,
        ):
            self.topbar.layout().removeWidget(widget)
            menu_lay.addWidget(widget)
        self.topbar.cash.hide()
        self.topbar.alerts.setToolTip("Action Center")
        self.return_alert = QPushButton("Return to the alert")
        self.return_alert.setObjectName("returnAlert")
        self.return_alert.setCursor(Qt.CursorShape.PointingHandCursor)
        self.return_alert.hide()
        self.return_alert.clicked.connect(self.back_to_alert)
        menu_lay.addWidget(self.return_alert)
        menu_lay.insertStretch(2, 1)
        self.topbar.setFixedHeight(0)
        self.menu_row = menu_row
        layout.addWidget(self.menu_row)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        right = QWidget()
        right.setObjectName("hqMain")
        column = QVBoxLayout(right)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        self.topbar.setFixedHeight(0)
        column.addWidget(self.topbar)
        self.body = QWidget()
        self.body.setObjectName("hqBody")
        body_layout = QVBoxLayout(self.body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        self.stack.setObjectName("hqPages")
        body_layout.addWidget(self.stack)
        column.addWidget(self.body, stretch=1)
        self.favorites = FavoritesBar()
        self.favorites.open_app.connect(self.open_app)
        row.addWidget(self.rail)
        row.addWidget(right, stretch=1)
        self.favorites.hide()
        row.addWidget(self.favorites)
        layout.addLayout(row, stretch=1)

        from open_late.ui.osprey_docs import InventoryLedger, RecordSheet, StatementPage

        self.home = DashboardPage()
        from open_late.ui.visiondeck.command_center import CommandCenter

        self.command_center = CommandCenter()
        self._return_alert = ("", "", "")
        self.command_center.follow.connect(self._follow_alert)
        self.stores = StoresPage()
        self.ledger = InventoryLedger()
        self.statement = StatementPage()
        self.records = RecordSheet()
        self.pos_page = PosPage()
        self.planogram = PlanogramPage()
        self.economy = EconomyPage()
        self.help_page = QScrollArea()
        self.help_page.setWidgetResizable(True)
        self.help_page.setFrameShape(QFrame.Shape.NoFrame)
        self.help_page.setObjectName("helpPage")
        self.help_page.setStyleSheet(
            "QScrollArea#helpPage { background: #09152D; border: none; }"
            "QWidget#helpInner { background: #09152D; }"
        )
        help_inner = QWidget()
        help_inner.setObjectName("helpInner")
        help_inner.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        help_box = QVBoxLayout(help_inner)
        help_box.setContentsMargins(16, 16, 16, 20)
        title = QLabel("  How the desk works")
        title.setFont(ui_font(16, QFont.Weight.Bold))
        title.setStyleSheet("background: #12254A; color: #F4F7FB; padding: 8px 12px;")
        body = QLabel(HELP.strip())
        body.setWordWrap(True)
        body.setFont(ui_font(13))
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body.setStyleSheet(
            "QLabel { background: #0E1C3A; color: #E8EEF8; border: 1px solid #1A2E55; padding: 14px; }"
        )
        help_box.addWidget(title)
        help_box.addWidget(body)
        studio = QLabel()
        studio.setObjectName("studioLogo")
        studio_pix = QPixmap(str(Path(__file__).resolve().parent.parent / "assets" / "brand" / "studio_logo.png"))
        if not studio_pix.isNull():
            studio.setPixmap(studio_pix.scaledToWidth(180, Qt.TransformationMode.SmoothTransformation))
            help_box.addWidget(studio, alignment=Qt.AlignmentFlag.AlignLeft)
        help_box.addStretch(1)
        self.help_page.setWidget(help_inner)
        self.module_scroll = QScrollArea()
        self.module_scroll.setWidgetResizable(True)
        self.module_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.module_scroll.setObjectName("modulePage")
        self.module_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.module_scroll.setStyleSheet(
            "QScrollArea#modulePage { background: #09152D; border: none; }"
            "QWidget#windowInner { background: #09152D; }"
            "QFrame#card, QFrame#cardUrgent, QFrame#stat, QFrame#figure {"
            " background: #0E1C3A; border: 1px solid #1A2E55; border-radius: 4px; color: #E8EEF8; }"
            "QLabel#section, QLabel#cardTitle { color: #0E5C32; }"
        )
        self.module_inner = QWidget()
        self.module_inner.setObjectName("windowInner")
        self.module_inner.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.module_layout = QVBoxLayout(self.module_inner)
        self.module_layout.setContentsMargins(16, 10, 22, 16)
        self.module_layout.setSpacing(10)
        self.module_scroll.setWidget(self.module_inner)

        for page in (
            self.home, self.command_center, self.stores, self.pos_page, self.planogram, self.economy,
            self.help_page, self.module_scroll, self.ledger, self.statement, self.records,
        ):
            self.stack.addWidget(page)

        from open_late.ui.phase7 import create as create_delegation

        self.delegation = create_delegation(None, self)
        self.stack.addWidget(self.delegation)
        from open_late.ui.phase8 import create as create_board

        self.board = create_board(None, self)
        self.stack.addWidget(self.board)
        from open_late.ui.phase9 import create as create_archive

        self.archive = create_archive(None, self)
        self.stack.addWidget(self.archive)

        from open_late.ui.page_registry import PageRegistry
        from open_late.ui.phase4 import WorkstationController, install_into_registry_module

        install_into_registry_module()
        self.page_registry = PageRegistry(self.stack)
        self.module_pages = self.page_registry.install_all(self)
        self.workstation_controller = WorkstationController(
            self.page_registry,
            lambda: self.host.state if self.host is not None else None,
            on_changed=self._workstation_saved,
        )
        from open_late.ui.phase5 import (
            ActionCenterWidget,
            BriefingWidget,
            ConnectedCommandCenter,
            DetailDrawer,
        )
        from PySide6.QtWidgets import QWidget as _Phase5Host

        self.detail_drawer = DetailDrawer(self)
        self.detail_drawer.on_show = self._place_detail
        for page in self.module_pages.values():
            page.detail_drawer = self.detail_drawer
        self.action_center = ActionCenterWidget()
        self.briefing = BriefingWidget()
        command_host = _Phase5Host()
        command_box = QVBoxLayout(command_host)
        command_box.setContentsMargins(0, 0, 0, 0)
        command_box.addWidget(self.briefing)
        command_box.addWidget(self.action_center)
        self.connected_center = ConnectedCommandCenter(
            self.page_registry,
            lambda: self.host.state if self.host is not None else None,
            navigator=self.open_drill,
        )
        self.connected_center.action_center_changed.connect(self.action_center.set_payload)
        self.connected_center.briefing_changed.connect(self.briefing.set_items)
        self.action_center.chosen.connect(self.connected_center.navigate.emit)
        self.briefing.chosen.connect(self.connected_center.navigate.emit)
        from open_late.ui.phase6 import attach as attach_deep_drill

        self.deep_drill = attach_deep_drill(
            self.page_registry,
            lambda: self.host.state if self.host is not None else None,
            self,
        )
        self.deep_drill.view.on_show = self._place_deep
        for page in self.module_pages.values():
            page.detail_drawer = None

        self.center = AlertsDrawer(self)
        self.center.mount_command(command_host)
        self.center.hide()
        self.center.open_inbox.connect(lambda: self.open_app.emit("journal"))
        self.company_search = CompanySearch(self)
        self.company_search.picked.connect(self._open_hit)
        self.company_search.hide()

        self.status = QLabel(self)
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        self.status.hide()

        # Aliases used by MainWindow and older tests.
        self.to_desk = self.topbar.to_desk
        self.close_button = self.topbar.close_button
        self.next_button = self.topbar.next_button

        self.rail.open_app.connect(self.open_app)
        self.rail.open_task.connect(self.show_task)
        self.rail.help.connect(self.help)
        self.rail.save_now.connect(self.save_now)
        self.rail.front_door.connect(self.front_door)
        self.topbar.open_floor.connect(self.open_floor)
        self.topbar.close_day.connect(self.close_day)
        self.topbar.next_morning.connect(self.next_morning)
        self.topbar.open_alerts.connect(self.toggle_center)
        self.topbar.scope_changed.connect(self._on_scope)
        from open_late.ui.phase10 import FeatureFlags, bootstrap

        self.integrated_ui = bootstrap(
            self.stack,
            lambda: self.host.state if self.host is not None else None,
            navigator=self.open_drill,
            host=self,
            flags=FeatureFlags(
                phase4_mutations=True,
                phase7_delegation=True,
                phase8_scenarios=True,
            ),
        )

    def _chuck_button(self) -> QWidget:
        from open_late.ui.chuck import ChuckButton

        self.chuck = ChuckButton()
        self.chuck.clicked.connect(self._open_chuck)
        return self.chuck

    def refresh_chuck(self) -> None:
        from open_late.ui.chuck import notes

        state = self.host.state if self.host is not None else None
        self.chuck.set_waiting(bool(notes(state)))

    def _open_chuck(self) -> None:
        from open_late.ui.chuck import ChuckOverlay, destinations

        state = self.host.state if self.host is not None else None
        overlay = getattr(self, "chuck_overlay", None)
        if overlay is None:
            overlay = ChuckOverlay(self)
            self.chuck_overlay = overlay
        overlay.set_notes(destinations(state), self._follow_chuck)
        overlay.reveal()

    def _follow_chuck(self, desk: str) -> None:
        """Open the desk Chuck already named. He still does not change the books."""
        host = self.host
        if host is None:
            return
        if desk == "decide":
            from types import SimpleNamespace

            from open_late.visiondeck.signals import remembered

            state = getattr(host, "state", None)
            alert = None
            if state is not None:
                alert = next(
                    (
                        item
                        for item in remembered(state)
                        if getattr(item, "kind", "") == "stockout_pressure" and getattr(item, "recommendations", None)
                    ),
                    None,
                )
            if alert is not None:
                self.open_drill(SimpleNamespace(filters={"action": "decide", "alert": alert.id, "desk": "decisions"}))
                return
            desk = "visiondeck"
        if desk == "visiondeck" and hasattr(host, "_open_app"):
            host._open_app("visiondeck")
            center = getattr(self, "command_center", None)
            if center is not None:
                center.show_desk("competitors")
            return
        if hasattr(host, "_open_app"):
            host._open_app(desk)

    def _bar_button(self, text: str, signal) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("barQuiet")
        button.clicked.connect(signal.emit)
        return button

    def _board_button(self) -> QPushButton:
        button = QPushButton("Board")
        button.setObjectName("barQuiet")
        button.clicked.connect(lambda: self.open_app.emit("board"))
        return button

    def _archive_button(self) -> QPushButton:
        button = QPushButton("Archive")
        button.setObjectName("barQuiet")
        button.clicked.connect(lambda: self.open_app.emit("archive"))
        return button

    def _build_menu(self) -> None:
        file_menu = self.menu.addMenu("File")
        file_menu.addAction("Save", self.save_now.emit)
        file_menu.addAction("Front door", self.front_door.emit)
        edit = self.menu.addMenu("Edit")
        edit.addAction("Find", self._edit_find)
        view = self.menu.addMenu("View")
        view.addAction("Favorites", self._toggle_favorites)
        tools = self.menu.addMenu("Tools")
        tools.addAction("Save", self.save_now.emit)
        tools.addAction("Open the floor", self.open_floor.emit)
        tools.addAction("Front door", self.front_door.emit)
        tools.addAction("Advance day", self.close_day.emit)
        tools.addAction("Next morning", self.next_morning.emit)
        windows = self.menu.addMenu("Windows")
        for app_id, label in MODULES:
            windows.addAction(label, lambda _=False, ident=app_id: self.open_app.emit(ident))
        help_menu = self.menu.addMenu("Help")
        help_menu.addAction("How the desk works", self.help.emit)

    def _edit_find(self) -> None:
        self.stack.setCurrentWidget(self.ledger)
        self.rail.set_active("inventory")
        self.current_id = "inventory"
        state = self.host.state if self.host is not None else None
        if state is not None:
            self.ledger.load(state, self.ledger._mode)
        self.ledger.find_items()

    def _toggle_favorites(self) -> None:
        self._favorites_open = not self.favorites.isVisible()
        self.favorites.setVisible(self._favorites_open and self.width() >= 1240)
        self.layout_chrome()

    def _workstation_saved(self) -> None:
        host = self.host
        if host is not None and hasattr(host, "_save"):
            host._save()

    def set_host(self, host) -> None:
        self.host = host
        self.home.host = host
        self.stores.host = host
        self.pos_page.host = host
        self.planogram.host = host
        self.economy.host = host
        self.ledger.bind(host)
        self.statement.bind(host)
        self.records.bind(host)
        state = host.state if host is not None else None
        if state is not None:
            for page in getattr(self, "module_pages", {}).values():
                page.load(state)
            delegation = getattr(self, "delegation", None)
            if delegation is not None:
                delegation.load(state)
            board = getattr(self, "board", None)
            if board is not None:
                board.load(state)
            archive = getattr(self, "archive", None)
            if archive is not None:
                archive.load(state)
            self.refresh_connected()
        if not getattr(self, "_search_wired", False):
            self.topbar.search.textChanged.connect(self._on_search_text)
            self._search_wired = True
        self.set_chain_chrome(host.state if host is not None else None)

    def _on_scope(self, kind: str, scope_id) -> None:
        self.set_scope(kind, scope_id)

    def set_scope(self, kind: str, scope_id: str | None = None, silent: bool = False) -> None:
        self.scope = (kind, scope_id)
        state = self.host.state if self.host is not None else None
        self.topbar.set_scope_label(kind, scope_id, state)
        self._update_breadcrumb()
        if not silent:
            self.scope_changed.emit()
            self._sync_phase5_scope()

    def scope_text(self) -> str:
        kind, scope_id = self.scope
        state = self.host.state if self.host is not None else None
        if kind == "region" and scope_id:
            return scope_id
        if kind == "store" and scope_id and state is not None:
            door = next((item for item in state.doors if item.id == scope_id), None)
            if door is not None:
                return f"{door.city}, {door.state_name}"
            return state.shop_name
        return "All stores"

    def _update_breadcrumb(self) -> None:
        self.topbar.set_breadcrumb(rail_label(self.current_id, self._corporate), self.scope_text())

    def _fill_surface(self, widget, color: str, *, auto: bool = True) -> None:
        if widget is None:
            return
        widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        pal = widget.palette()
        fill = QColor(color)
        pal.setColor(QPalette.ColorRole.Window, fill)
        pal.setColor(QPalette.ColorRole.Base, fill)
        widget.setPalette(pal)
        widget.setAutoFillBackground(auto)

    def _recolor_topbar_labels(self, dark: bool) -> None:
        ink = DASH_TEXT if dark else HQ_TITLE
        muted = DASH_MUTED if dark else HQ_MUTED
        colors = {
            "chainName": ink,
            "breadcrumb": muted,
            "trayCash": ink,
            "dayChip": muted,
        }
        for name, color in colors.items():
            lab = self.topbar.findChild(QLabel, name)
            if lab is not None:
                lab.setStyleSheet(f"color: {color}; background: transparent;")

    def set_dashboard_chrome(self, dark: bool) -> None:
        dark = bool(dark)
        if getattr(self, "_dash_dark", None) is dark:
            # Same chrome as the last click: nothing to restyle.
            return
        self._dash_dark = dark
        main = self.findChild(QWidget, "hqMain")
        for widget in (self, self.topbar, self.body, main, self.stack, self.home, getattr(self, "economy", None)):
            if widget is None:
                continue
            widget.setProperty("dashDark", "true" if dark else "false")
        # The dashboard sheet stays on every page. Leaving home only flips the property.
        self._fill_surface(self, DASH_BG)
        self._fill_surface(main, DASH_BG)
        self._fill_surface(self.body, DASH_BG)
        self._fill_surface(self.stack, DASH_BG)
        self._fill_surface(self.topbar, "#07111F")
        self._fill_surface(self.home, DASH_BG)
        self._fill_surface(getattr(self, "economy", None), DASH_BG)
        self._fill_surface(self.rail, "#07111F")
        # The fixed shell sheet gates its dark rules on this property; repolish
        # just the widgets those rules can match (no whole-tree setStyleSheet).
        restyle: dict[int, QWidget] = {}
        for widget in (self, self.topbar, self.body, main, self.stack, self.home, getattr(self, "economy", None), self.rail):
            if widget is not None:
                restyle[id(widget)] = widget
        for index in range(self.stack.count()):
            page = self.stack.widget(index)
            restyle[id(page)] = page
        for widget in self.topbar.findChildren(QWidget):
            restyle[id(widget)] = widget
        for widget in self.findChildren(QWidget, _DASH_SUBJECT_RE):
            restyle[id(widget)] = widget
        for widget in restyle.values():
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()
        self._recolor_topbar_labels(dark)

    def set_chain_chrome(self, state) -> None:
        self.topbar.set_chain(chain_info(state) if state is not None else {"id": "megamart", "name": "Northstar Market", "logo": "megamart.png"})

    def set_corporate(self, corporate: bool) -> None:

        self._corporate = corporate
        self.rail.set_corporate(corporate)

    def show_page(self, app_id: str) -> None:
        search = getattr(self, "company_search", None)
        if search is not None:
            search.hide()
        # Shop starts label this rail item "Expansion"; it must not open Planogram.
        if app_id in ("expansion", "planograms") and not self._corporate:
            mapped = "expansion"
        else:
            mapped = {"overview": "home", "expansion": "stores"}.get(app_id, app_id)
        self.current_id = mapped
        if mapped == "home":
            self.stack.setCurrentWidget(self.home)
            self.home.show_desk()
        elif mapped == "stores":
            self.stack.setCurrentWidget(self.stores)
            self.stores.rebuild()
            self.stores.reveal()
        elif mapped == "pos":
            self.stack.setCurrentWidget(self.pos_page)
            self.pos_page.rebuild()
        elif mapped == "planograms":
            self.stack.setCurrentWidget(self.planogram)
            self.planogram.rebuild()
        elif mapped == "economy":
            self.stack.setCurrentWidget(self.economy)
            self.economy.rebuild()
        elif mapped == "help":
            self.stack.setCurrentWidget(self.help_page)
        elif mapped == "inventory" and self._corporate:
            self.stack.setCurrentWidget(self.ledger)
            if not getattr(self, "_keep_query", False):
                self.ledger._query = ""
            self._keep_query = False
            state = self.host.state if self.host is not None else None
            if state is not None:
                self.ledger.load(state, "items")
                focus = str(getattr(self.host, "inventory_focus_sku", "") or "")
                if focus:
                    self.ledger.focus_sku(focus)
                    self.host.inventory_focus_sku = ""
        elif mapped == "inventory":
            # A single shop still uses the desk sheet that fits the 1100-wide window.
            self.stack.setCurrentWidget(self.module_scroll)
        elif mapped == "reporting":
            self.stack.setCurrentWidget(self.records)
            if self.host is not None:
                self.records.load(self.host, "weekly")
        elif mapped == "books":
            self.stack.setCurrentWidget(self.statement)
            state = self.host.state if self.host is not None else None
            if state is not None:
                self.statement.load(state, "pnl")
        elif mapped == "delegation":
            self.stack.setCurrentWidget(self.delegation)
            state = self.host.state if self.host is not None else None
            if state is not None:
                self.delegation.load(state)
        elif mapped == "board":
            self.stack.setCurrentWidget(self.board)
            state = self.host.state if self.host is not None else None
            if state is not None:
                self.board.load(state)
        elif mapped == "archive":
            self.stack.setCurrentWidget(self.archive)
            state = self.host.state if self.host is not None else None
            if state is not None:
                self.archive.load(state)
        elif mapped == "visiondeck":
            self.stack.setCurrentWidget(self.command_center)
            state = self.host.state if self.host is not None else None
            self.command_center.load(state)
        elif mapped in getattr(self, "module_pages", {}):
            page = self.module_pages[mapped]
            self.stack.setCurrentWidget(page)
            state = self.host.state if self.host is not None else None
            if state is not None:
                page.load(state)
        else:
            self.stack.setCurrentWidget(self.module_scroll)
        highlight = mapped
        if mapped == "expansion":
            highlight = "planograms"
        elif mapped == "delegation":
            highlight = "staff"
        elif mapped == "board":
            highlight = "home"
        elif mapped == "archive":
            highlight = "home"
        elif mapped == "visiondeck":
            highlight = "visiondeck"
        self.rail.set_active(highlight)
        label = BUTTON_TEXT.get(mapped)
        if label is None:
            label = "Expansion" if mapped == "expansion" else mapped.replace("_", " ").title()
        self.favorites.remember(mapped, label)
        self.set_dashboard_chrome(False)
        self._update_breadcrumb()
        self.lift_chrome()

    def show_task(self, section: str, task: str) -> None:
        """Open one explorer task and keep that module's list on the left."""
        state = self.host.state if self.host is not None else None
        highlight = section if section in self.rail.buttons else self.current_id
        if section == "home" and task in ("Today", "The book"):
            self.stack.setCurrentWidget(self.home)
            self.home.show_desk()
            self.rail.set_active(highlight)
            self.current_id = "home"
            if task == "The book":
                board = self.home.findChild(QWidget, "commandBoard")
                book = getattr(board, "book", None)
                if book is not None:
                    book.setFocus()
            return
        if section == "stores" and task == "Store Portfolio":
            self.stack.setCurrentWidget(self.stores)
            self.stores.rebuild()
            self.stores.reveal()
            self.rail.set_active("stores")
            self.current_id = "stores"
            return
        if section in ("planograms", "stores") and task == "Store Layout":
            self.stack.setCurrentWidget(self.planogram)
            self.planogram._show_view("floor")
            self.rail.set_active(highlight)
            self.current_id = "planograms" if section == "planograms" else section
            return
        if section == "planograms" and task == "Aisles":
            self.stack.setCurrentWidget(self.planogram)
            self.planogram._show_view("editor")
            self.rail.set_active("planograms")
            self.current_id = "planograms"
            return
        if section == "planograms" and task == "Endcaps":
            self.stack.setCurrentWidget(self.planogram)
            self.planogram._show_view("endcaps")
            self.rail.set_active("planograms")
            self.current_id = "planograms"
            return
        if section == "planograms" and task == "Out of Stocks":
            self._open_record("outs", "planograms")
            return
        if section == "planograms" and task == "Scout Rival":
            return
        if section == "settings" and task == "Open the floor":
            self.open_floor.emit()
            self.rail.set_active("settings")
            return
        if section == "pos" and task == "Store tills":
            self._open_record("tills", "pos")
            return
        if section == "stores" and task == "Leases and Loans":
            self._open_record("leases", "stores")
            return
        if task == "Open New Store":
            self._open_record("markets", section if section in self.rail.buttons else "stores")
            return
        if task == "Weekly sales":
            self._open_record("weekly", "reporting" if "reporting" in self.rail.buttons else section)
            return
        if section == "inventory" and task in ("Item Maintenance", "Stock Levels", "Vendors", "Shrink", "Receiving"):
            kind = {
                "Item Maintenance": "items",
                "Stock Levels": "levels",
                "Vendors": "vendors",
                "Shrink": "shrink",
                "Receiving": "receiving",
            }[task]
            self._open_record(kind, "inventory")
            return
        if task in ("Purchase Orders", "Purchase orders", "Open deliveries") and self.host is not None:
            self.host._open_app("orders")
            self.rail.set_active(highlight)
            self.current_id = "orders" if "orders" in self.rail.buttons else highlight
            return
        if section == "books" and task == "Loans":
            if state is not None:
                self.statement.load(state, "loans")
            self.stack.setCurrentWidget(self.statement)
            self.rail.set_active("books")
            self.current_id = "books"
            return
        if task in ("Profit and Loss", "Store P&L", "Balance Sheet", "Cash Flow", "Taxes", "Budget"):
            kind = {
                "Balance Sheet": "balance",
                "Cash Flow": "cash",
                "Taxes": "tax",
                "Budget": "budget",
            }.get(task, "pnl")
            if state is not None:
                self.statement.load(state, kind)
            self.stack.setCurrentWidget(self.statement)
            self.rail.set_active(highlight)
            return
        _title, tasks = EXPLORER.get(section, ("", ()))
        target = next((ident for label, ident in tasks if label == task), section)
        if self.host is not None:
            self.host._open_app(target)
        self.rail.set_active(highlight)

    def refresh_connected(self) -> None:
        if hasattr(self, "chuck"):
            self.refresh_chuck()
        center = getattr(self, "connected_center", None)
        if center is not None:
            center.refresh()

    def _sync_phase5_scope(self) -> None:
        center = getattr(self, "connected_center", None)
        if center is None:
            return
        kind, ident = self.scope
        center.set_scope("company" if kind in ("all", "company", None, "") else kind, ident)

    def _follow_alert(self, app_id: str, alert_id: str, desk: str) -> None:
        """Open the workstation an alert already points at. The choice stays with the player."""
        from types import SimpleNamespace

        self._return_alert = (str(app_id or ""), str(alert_id or ""), str(desk or ""))
        if app_id == "decide":
            self.open_drill(SimpleNamespace(filters={"action": "decide", "alert": alert_id, "desk": desk}))
            return
        self.return_alert.show()
        if app_id == "visiondeck":
            if self.host is not None:
                self.host._open_app("visiondeck")
            else:
                self.show_page("visiondeck")
            self.command_center.show_desk(desk or "alerts")
            return
        if self.host is not None:
            self.host._open_app(app_id)
        else:
            self.show_page(app_id)

    def back_to_alert(self) -> None:
        _app, alert_id, _desk = getattr(self, "_return_alert", ("", "", ""))
        self.return_alert.hide()
        if self.host is not None:
            self.host._open_app("visiondeck")
        else:
            self.show_page("visiondeck")
        self.command_center.focus_alert(alert_id)

    def open_drill(self, drill) -> None:
        filters = getattr(drill, "filters", {}) or {}
        action = str(filters.get("action") or "")
        if action == "decide":
            if self.host is None or self.host.state is None:
                return
            from open_late.ui.visiondeck.decision_lab import DecisionLab
            from open_late.visiondeck.signals import remembered

            alert_id = str(filters.get("alert") or "")
            alert = next((item for item in remembered(self.host.state) if item.id == alert_id), None)
            if alert is None:
                return
            if DecisionLab(self.host.state, alert, self).exec():
                save = getattr(self.host, "_save", None)
                refresh = getattr(self.host, "refresh", None)
                if save is not None:
                    save()
                if refresh is not None:
                    refresh()
            return
        if action == "do_nothing":
            if self.host is not None and self.host.state is not None and filters.get("door"):
                from open_late.visiondeck.memory import remember_rival_hold, visits_on

                door = str(filters.get("door") or "")
                place = str(filters.get("place") or door)
                before = visits_on(self.host.state, door, int(self.host.state.day) - 1)
                remember_rival_hold(self.host.state, door, place, 0 if before is None else before)
            if self.host is not None:
                self.host._say("Do nothing.")
            return
        if action == "review_prices":
            if self.host is not None:
                self.host._say("Prices are unchanged.")
            self.open_app.emit("sales")
            return
        if action == "wait":
            if self.host is not None and self.host.state is not None and filters.get("category"):
                from open_late.visiondeck.memory import remember_wait

                remember_wait(
                    self.host.state,
                    str(filters.get("door") or ""),
                    str(filters.get("place") or filters.get("door") or ""),
                    str(filters.get("category") or ""),
                    int(filters.get("lost") or 0),
                )
            if self.host is not None:
                self.host._say("Wait. Units are already on order.")
            return
        if action == "send":
            door = str(filters.get("door") or getattr(drill, "entity_id", "") or "")
            self.stores.selected = door
            self.stores._truck_arm = {
                "door": door,
                "product": str(filters.get("product") or ""),
                "qty": int(filters.get("qty") or 0),
            }
            if self.host is not None:
                self.host._stockout_follow = {
                    "action": "send",
                    "door": door,
                    "product": str(filters.get("product") or ""),
                    "qty": int(filters.get("qty") or 0),
                    "category": str(filters.get("category") or ""),
                    "place": str(filters.get("place") or door),
                }
            self.open_app.emit("stores")
            return
        if action == "order":
            if self.host is not None:
                self.host._catalog_query = str(filters.get("query") or "")
                self.host._catalog_dept = ""
                self.host._catalog_offset = 0
                self.host._stockout_follow = {
                    "action": "order",
                    "door": str(filters.get("door") or ""),
                    "product": str(filters.get("query") or ""),
                    "category": str(filters.get("category") or ""),
                    "place": str(filters.get("place") or ""),
                }
            self.open_app.emit("orders")
            return
        query = str(filters.get("query") or "")
        page_id = getattr(drill, "page_id", str(drill))
        if page_id == "inventory" and not query:
            query = str(getattr(drill, "entity_id", "") or "")
        if page_id == "inventory" and query:
            self._keep_query = True
            self.ledger._query = str(query).lower()
        self.open_app.emit(page_id)
        page = getattr(self, "module_pages", {}).get(page_id)
        if page is not None and query:
            search = getattr(getattr(page, "filters", None), "search", None)
            if search is not None:
                search.setText(str(query))

    def _on_search_text(self, text: str) -> None:
        if self.stack.currentWidget() is self.stores:
            self.stores.set_query(text)
        self._show_company_hits(text)

    def _show_company_hits(self, text: str) -> None:
        popup = getattr(self, "company_search", None)
        if popup is None:
            return
        state = self.host.state if self.host is not None else None
        hits = company_hits(state, text)
        if not hits:
            popup.hide()
            return
        popup.show_hits(hits)
        self._place_search()

    def _place_search(self) -> None:
        popup = getattr(self, "company_search", None)
        if popup is None or not popup.isVisible():
            return
        box = self.topbar.search
        origin = box.mapTo(self, box.rect().bottomLeft())
        popup.setFixedWidth(max(280, box.width()))
        popup.move(origin.x(), origin.y() + 4)
        popup.raise_()

    def _run_search(self) -> None:
        if self.host is None:
            return
        text = self.topbar.search.text().strip()
        if self.stack.currentWidget() is self.stores:
            self.stores.set_query(text)
        hits = company_hits(self.host.state, text)
        if not hits and text:
            from open_late.catalog import find_items

            for row in find_items(text, limit=6):
                hits.append({
                    "kind": "catalog",
                    "id": str(row.get("id") or ""),
                    "label": str(row.get("name") or row.get("id") or ""),
                    "page": "orders",
                })
        popup = getattr(self, "company_search", None)
        if popup is not None:
            popup.show_hits(hits)
            if hits:
                self._place_search()
        if hits:
            self._open_hit(hits[0])
            return
        if text:
            self.host._say(f"Nothing in the company matches {text}.")

    def _open_hit(self, hit: dict) -> None:
        popup = getattr(self, "company_search", None)
        if popup is not None:
            popup.hide()
        if self.host is None:
            return
        kind = hit.get("kind")
        ident = str(hit.get("id") or "")
        page = str(hit.get("page") or "")
        if kind == "store":
            self.stores.selected = ident
            self.open_app.emit("stores")
            return
        if kind == "manager":
            door_id = str(hit.get("door_id") or "")
            if door_id:
                self.stores.selected = door_id
            self.open_app.emit("stores" if door_id else "staff")
            return
        if kind == "product":
            if self._corporate:
                self._keep_query = True
                self.ledger._query = ident.lower()
                self.open_app.emit("inventory")
            else:
                self.host._inv_query = ident
                self.open_app.emit("inventory")
            return
        if kind == "catalog":
            self.host._catalog_query = ident
            self.host._catalog_dept = ""
            self.host._catalog_offset = 0
            self.open_app.emit("orders")
            self.host._say(f"{hit.get('label') or ident} is in the warehouse catalog.")
            return
        self.open_app.emit(page)
        if kind in ("order", "staff"):
            self._arm_page_search(page, ident if kind == "order" else str(hit.get("label") or ""))

    def _arm_page_search(self, page_id: str, text: str) -> None:
        page = getattr(self, "module_pages", {}).get(page_id)
        search = getattr(getattr(page, "filters", None), "search", None)
        if search is not None and text:
            search.setText(text)

    def _open_record(self, kind: str, section: str) -> None:
        if self.host is not None:
            self.records.load(self.host, kind)
        self.stack.setCurrentWidget(self.records)
        highlight = section if section in self.rail.buttons else self.current_id
        self.rail.set_active(highlight)
        self.current_id = highlight

    def current_page(self) -> str:
        return self.current_id

    def clear_module(self) -> QVBoxLayout:
        layout = self.module_layout
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
            elif item.layout() is not None:
                nested = item.layout()
                while nested.count():
                    child = nested.takeAt(0)
                    w = child.widget()
                    if w is not None:
                        w.hide()
                        w.setParent(None)
                        w.deleteLater()
        return layout

    def layout_chrome(self) -> None:
        compact = self.width() < 1180
        self.rail.set_compact(compact)
        # The favorites pane is the right explorer. Hide it on the narrow
        # test sizes so the store drawer and the tool strip still fit.
        self.favorites.setVisible(self._favorites_open and self.width() >= 1240)
        if self.stores.drawer is not None:
            self.stores.drawer.setFixedWidth(260 if compact else 320)
        if self.center.isVisible():
            self._place_center()
        self._place_search()
        drawer = getattr(self, "detail_drawer", None)
        if drawer is not None and drawer.isVisible():
            self._place_detail()
        deep = getattr(getattr(self, "deep_drill", None), "view", None)
        if deep is not None and deep.isVisible():
            self._place_deep()
        self.lift_chrome()

    def lift_chrome(self) -> None:
        if self.center.isVisible():
            self.center.raise_()
        popup = getattr(self, "company_search", None)
        if popup is not None and popup.isVisible():
            popup.raise_()
        drawer = getattr(self, "detail_drawer", None)
        if drawer is not None and drawer.isVisible():
            drawer.raise_()
        deep = getattr(getattr(self, "deep_drill", None), "view", None)
        if deep is not None and deep.isVisible():
            deep.raise_()
        if self.status.isVisible():
            self.status.raise_()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.layout_chrome()

    def _chrome_top(self) -> int:
        # The menu bar is hidden. An unparented bar still reports the default
        # 480px height, which would push the work area off a 720px window.
        menu = self.menu.height() if self.menu.isVisible() else 0
        bar = self.topbar.height() if self.topbar.isVisible() else 0
        row = self.menu_row.height() if getattr(self, "menu_row", None) is not None and self.menu_row.isVisible() else 0
        return menu + bar + row

    def _place_center(self) -> None:
        top = self._chrome_top()
        height = min(self.height() - top - 24, 620)
        self.center.setFixedHeight(max(280, height))
        right = self.favorites.width() if self.favorites.isVisible() else 0
        self.center.move(self.width() - right - self.center.width() - 12, top + 8)

    def _place_detail(self) -> None:
        drawer = getattr(self, "detail_drawer", None)
        if drawer is None:
            return
        top = self._chrome_top()
        height = min(self.height() - top - 24, 620)
        drawer.setFixedHeight(max(280, height))
        right = self.favorites.width() if self.favorites.isVisible() else 0
        drawer.move(self.width() - right - drawer.width() - 12, top + 8)
        drawer.raise_()

    def _place_deep(self) -> None:
        view = getattr(getattr(self, "deep_drill", None), "view", None)
        if view is None:
            return
        top = self._chrome_top()
        height = min(self.height() - top - 24, 640)
        view.setFixedHeight(max(280, height))
        right = self.favorites.width() if self.favorites.isVisible() else 0
        view.move(self.width() - right - view.width() - 12, top + 8)
        view.raise_()

    def toggle_center(self) -> None:
        if self.center.isVisible():
            self.center.hide()
        else:
            self._place_center()
            self.center.show()
        self.lift_chrome()

    def toggle_menu(self) -> None:
        # Compatibility no-op for older tests: the start menu is gone.
        if self.center.isVisible():
            self.center.hide()

    def hide_overlays(self) -> None:
        # The Action Center stays with the player. A desk change only closes
        # the record drawers that belonged to the page they left.
        if self.center.isVisible():
            self._place_center()
        drawer = getattr(self, "detail_drawer", None)
        if drawer is not None:
            drawer.hide()
        deep = getattr(getattr(self, "deep_drill", None), "view", None)
        if deep is not None:
            deep.hide()

    def work_area(self):
        from PySide6.QtCore import QRect
        left = self.rail.width()
        right = self.favorites.width() if self.favorites.isVisible() else 0
        top = self._chrome_top()
        return QRect(left, top, max(480, self.width() - left - right), max(300, self.height() - top))
