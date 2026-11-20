"""Dashboard-dark visual extension for Back Office: Retail.

Append dashboard_all_screens_stylesheet() after the existing HQ stylesheet so
legacy and component-based pages share the Dashboard visual language.
"""

DASH_BG = "#09152D"
DASH_CARD = "#0E1C3A"
DASH_CARD_2 = "#0B1730"
DASH_LINE = "#1A2E55"
DASH_TEXT = "#E8EEF8"
DASH_MUTED = "#8BA0C0"
DASH_FAINT = "#6B82A8"
DASH_GLOW = "#3D7EFF"
DASH_ACCENT = "#7C5CFF"
GOOD = "#22C55E"
WARN = "#F5C542"
BAD = "#EF4444"


def dashboard_all_screens_stylesheet() -> str:
    return f"""
    /* Global module canvas */
    QWidget#hqMain, QWidget#hqBody, QStackedWidget#hqPages,
    QWidget#hqPages > QWidget, QWidget#boPage, QWidget#boPageInner,
    QWidget#inventoryLedger, QWidget#planogramPage {{
        background: {DASH_BG};
        background-color: {DASH_BG};
        color: {DASH_TEXT};
    }}

    /* General typography */
    QWidget#hqMain QLabel, QWidget#hqBody QLabel,
    QWidget#boPage QLabel, QWidget#inventoryLedger QLabel {{
        color: {DASH_TEXT};
        background: transparent;
    }}
    QLabel#pageDeck, QLabel#quiet, QLabel#hint, QLabel#meta,
    QLabel#pnlNote, QLabel#skuRailHint, QLabel#skuRailPage,
    QLabel#layoutStatus, QLabel#floorHint {{ color: {DASH_MUTED}; }}
    QLabel#kicker, QLabel#figureCaption, QLabel#skuRailTitle {{ color: {DASH_FAINT}; }}

    /* Cards / sections */
    QFrame#card, QFrame#hero, QFrame#kpi, QFrame#figure, QFrame#stat,
    QFrame#boCard, QFrame#boSection, QFrame#boFilter, QFrame#boEmpty,
    QFrame#inventoryDetails {{
        background: {DASH_CARD};
        background-color: {DASH_CARD};
        border: 1px solid {DASH_LINE};
        border-radius: 8px;
        color: {DASH_TEXT};
    }}
    QFrame#boSectionHead, QFrame#ospreyHead {{
        background: #12254A;
        border: none;
        border-bottom: 1px solid {DASH_LINE};
    }}

    /* Inputs */
    QLineEdit, QComboBox, QSpinBox {{
        background: {DASH_CARD_2};
        color: {DASH_TEXT};
        border: 1px solid {DASH_LINE};
        border-radius: 6px;
        padding: 5px 8px;
        min-height: 26px;
        selection-background-color: {DASH_GLOW};
        selection-color: #FFFFFF;
    }}
    QComboBox QAbstractItemView {{
        background: {DASH_CARD};
        color: {DASH_TEXT};
        border: 1px solid {DASH_LINE};
        selection-background-color: #17376D;
        selection-color: #FFFFFF;
    }}

    /* Buttons */
    QPushButton, QPushButton#boButton {{
        background: #102343;
        color: {DASH_TEXT};
        border: 1px solid #294571;
        border-radius: 6px;
        padding: 5px 10px;
        font-weight: 600;
    }}
    QPushButton:hover, QPushButton#boButton:hover {{
        background: #17376D;
        border-color: {DASH_GLOW};
    }}
    QPushButton:pressed {{ background: #1D478F; }}
    QPushButton:disabled {{
        background: #0C1931;
        color: #536987;
        border-color: #172A49;
    }}
    QPushButton#boPrimary, QPushButton#pushStores, QPushButton#newShop,
    QPushButton#startGame {{
        background: {DASH_GLOW};
        color: #FFFFFF;
        border: 1px solid #6596FF;
        font-weight: 700;
    }}
    QPushButton#boPrimary:hover, QPushButton#pushStores:hover {{ background: #4F86FF; }}

    /* Tables */
    QTableWidget, QTableWidget#boTable, QTableWidget#inventorySheet,
    QTreeWidget, QListWidget {{
        background: {DASH_CARD};
        alternate-background-color: #0B1934;
        color: {DASH_TEXT};
        gridline-color: {DASH_LINE};
        border: 1px solid {DASH_LINE};
        selection-background-color: #17376D;
        selection-color: #FFFFFF;
    }}
    QHeaderView::section {{
        background: #102343;
        color: {DASH_MUTED};
        border: none;
        border-bottom: 1px solid {DASH_LINE};
        border-right: 1px solid {DASH_LINE};
        padding: 6px 8px;
        font-weight: 700;
    }}
    QTableCornerButton::section {{ background: #102343; border: 1px solid {DASH_LINE}; }}

    /* Tabs */
    QTabWidget::pane {{ border: 1px solid {DASH_LINE}; background: {DASH_CARD}; }}
    QTabBar::tab {{
        background: {DASH_CARD_2}; color: {DASH_MUTED};
        border: 1px solid {DASH_LINE}; padding: 6px 12px;
    }}
    QTabBar::tab:selected {{ background: #17376D; color: #FFFFFF; border-bottom-color: {DASH_GLOW}; }}
    QTabBar::tab:hover {{ color: #FFFFFF; }}

    /* Scroll areas / scroll bars */
    QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
    QScrollBar:vertical {{ background: {DASH_BG}; width: 12px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: #294571; border-radius: 5px; min-height: 32px; }}
    QScrollBar::handle:vertical:hover {{ background: #3A5E92; }}
    QScrollBar:horizontal {{ background: {DASH_BG}; height: 12px; margin: 2px; }}
    QScrollBar::handle:horizontal {{ background: #294571; border-radius: 5px; min-width: 32px; }}
    QScrollBar::handle:horizontal:hover {{ background: #3A5E92; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0px; width: 0px; }}

    /* Status chips */
    QLabel#boChip {{ background: #12254A; color: {DASH_MUTED}; border: 1px solid {DASH_LINE}; }}
    QLabel#boChip[tone="good"] {{ background: #103620; color: {GOOD}; border-color: #1F6E3E; }}
    QLabel#boChip[tone="warning"] {{ background: #3C3212; color: {WARN}; border-color: #725F1C; }}
    QLabel#boChip[tone="bad"] {{ background: #3F1720; color: {BAD}; border-color: #782A37; }}
    QLabel#boChip[tone="info"] {{ background: #162C5A; color: #72A7FF; border-color: #315A9C; }}

    /* Planogram/store-layout specific pieces */
    QWidget#planogramEditorBar {{ background: {DASH_BG}; border-bottom: 1px solid {DASH_LINE}; }}
    QWidget#shelfCanvas, QWidget#floorPane {{ background: {DASH_CARD}; }}
    QFrame#fixtureRow, QFrame#skuRow {{ background: {DASH_CARD_2}; border: 1px solid {DASH_LINE}; border-radius: 5px; }}
    QFrame#fixtureRowOn {{ background: #17376D; border: 1px solid {DASH_GLOW}; border-radius: 5px; }}
    QPushButton#templateChip {{ background: #102343; color: {DASH_MUTED}; border: 1px solid {DASH_LINE}; }}
    QPushButton#templateChipOn {{ background: #17376D; color: #FFFFFF; border: 1px solid {DASH_GLOW}; }}
    """
