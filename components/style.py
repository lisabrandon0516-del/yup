from .core import GREEN, GREEN_ACTIVE, PAGE, CARD, INK, MUTED, LINE

def stylesheet()->str:
    return f'''
    QWidget#boPage,QWidget#boPageInner{{background:{PAGE};color:{INK};}}
    QFrame#boSection,QFrame#boCard,QFrame#boFilter,QFrame#boEmpty{{background:{CARD};border:1px solid {LINE};border-radius:4px;}}
    QFrame#boSectionHead{{background:{GREEN};border:none;}}
    QPushButton#boSectionLink{{color:#FFFFFF;background:transparent;border:none;font-weight:600;}}
    QPushButton#boPrimary{{background:{GREEN_ACTIVE};color:#FFFFFF;border:none;border-radius:3px;padding:6px 12px;font-weight:700;}}
    QPushButton#boButton{{background:#FFFFFF;color:{INK};border:1px solid #D0D4DA;border-radius:3px;padding:5px 10px;font-weight:600;}}
    QFrame#boFilter QLineEdit{{background:#FFFFFF;color:{INK};border:1px solid {LINE};border-radius:4px;padding:5px 8px;min-height:26px;}}
    QLabel#boChip{{padding:2px 7px;border-radius:8px;background:#EEF1F4;color:{MUTED};font-weight:600;}}
    QLabel#boChip[tone="good"]{{background:#E7F6EE;color:#16803C;}}
    QLabel#boChip[tone="warning"]{{background:#FFF4E5;color:#C2410C;}}
    QLabel#boChip[tone="bad"]{{background:#FDECEC;color:#C24141;}}
    QLabel#boChip[tone="info"]{{background:#E8F1FB;color:#1D4E89;}}
    QTableWidget#boTable{{background:#FFFFFF;alternate-background-color:#F7F9FB;color:{INK};gridline-color:{LINE};border:1px solid {LINE};}}
    QTableWidget#boTable QHeaderView::section{{background:#F7F9FB;color:{MUTED};border:none;border-bottom:1px solid {LINE};border-right:1px solid {LINE};padding:6px 8px;font-weight:700;}}
    '''
