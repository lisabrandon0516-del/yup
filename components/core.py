from __future__ import annotations
from collections.abc import Iterable
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPushButton, QScrollArea, QSizePolicy, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

GREEN='#3D7EFF'; GREEN_ACTIVE='#3D7EFF'; PAGE='#09152D'; CARD='#0E1C3A'
INK='#E8EEF8'; MUTED='#8BA0C0'; LINE='#1A2E55'; RED='#EF4444'; AMBER='#F5C542'; BLUE='#7C5CFF'


def label(text:str='', size:int=12, bold:bool=False, color:str=INK, wrap:bool=False)->QLabel:
    out=QLabel(text); out.setWordWrap(wrap)
    font=out.font(); font.setPixelSize(size); font.setBold(bold); out.setFont(font)
    out.setStyleSheet(f'color:{color};background:transparent;')
    return out

class PageCanvas(QWidget):
    def __init__(self, title:str, deck:str='', parent=None):
        super().__init__(parent); self.setObjectName('boPage'); self.setAttribute(Qt.WA_StyledBackground,True)
        root=QVBoxLayout(self); root.setContentsMargins(0,0,0,0)
        self.scroll=QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setFrameShape(QFrame.NoFrame)
        self.inner=QWidget(); self.inner.setObjectName('boPageInner'); self.body=QVBoxLayout(self.inner)
        self.body.setContentsMargins(14,12,14,16); self.body.setSpacing(12)
        head=QHBoxLayout(); titles=QVBoxLayout(); titles.setSpacing(2)
        titles.addWidget(label(title,24,True)); titles.addWidget(label(deck,12,color=MUTED,wrap=True))
        head.addLayout(titles,1); self.actions=QHBoxLayout(); self.actions.setSpacing(6); head.addLayout(self.actions)
        self.body.addLayout(head); self.scroll.setWidget(self.inner); root.addWidget(self.scroll)
        self.setStyleSheet(f'QWidget#boPage,QWidget#boPageInner{{background:{PAGE};}}')
    def add_action(self,text:str,callback=None,primary:bool=False)->QPushButton:
        button=QPushButton(text); button.setObjectName('boPrimary' if primary else 'boButton')
        if callback: button.clicked.connect(callback)
        self.actions.addWidget(button); return button

class Section(QFrame):
    def __init__(self,title:str,link:str='',parent=None):
        super().__init__(parent); self.setObjectName('boSection'); self.setAttribute(Qt.WA_StyledBackground,True)
        outer=QVBoxLayout(self); outer.setContentsMargins(0,0,0,0); outer.setSpacing(0)
        head=QFrame(); head.setObjectName('boSectionHead'); head.setFixedHeight(34)
        row=QHBoxLayout(head); row.setContentsMargins(12,0,8,0); row.addWidget(label(title,13,True,'#FFFFFF')); row.addStretch(1)
        self.link=QPushButton(link); self.link.setObjectName('boSectionLink'); self.link.setVisible(bool(link)); row.addWidget(self.link)
        outer.addWidget(head); self.body=QVBoxLayout(); self.body.setContentsMargins(10,8,10,10); self.body.setSpacing(7); outer.addLayout(self.body)

class KpiCard(QFrame):
    def __init__(self,caption:str,value:str='—',detail:str='',tone:str='neutral',parent=None):
        super().__init__(parent); self.setObjectName('boCard'); self.setAttribute(Qt.WA_StyledBackground,True)
        box=QVBoxLayout(self); box.setContentsMargins(10,8,10,8); box.setSpacing(1)
        self.caption=label(caption.upper(),10,True,MUTED); self.value=label(value,18,True); self.detail=label(detail,11,color=MUTED,wrap=True)
        box.addWidget(self.caption); box.addWidget(self.value); box.addWidget(self.detail)
        self.set_data(value,detail,tone)
    def set_data(self,value:str,detail:str='',tone:str='neutral'):
        colors={'good':GREEN_ACTIVE,'bad':RED,'warning':AMBER,'info':BLUE,'neutral':INK}
        self.value.setText(str(value)); self.value.setStyleSheet(f"color:{colors.get(tone,INK)};background:transparent;"); self.detail.setText(str(detail))

class StatusChip(QLabel):
    def __init__(self,text:str,tone:str='neutral',parent=None):
        super().__init__(text,parent); self.setObjectName('boChip'); self.setProperty('tone',tone)

class FilterBar(QFrame):
    search_changed=Signal(str)
    def __init__(self,placeholder='Search…',parent=None):
        super().__init__(parent); self.setObjectName('boFilter'); row=QHBoxLayout(self); row.setContentsMargins(8,6,8,6)
        self.search=QLineEdit(); self.search.setPlaceholderText(placeholder); self.search.textChanged.connect(self.search_changed)
        row.addWidget(self.search,1); self.extra=QHBoxLayout(); row.addLayout(self.extra)
    def add_button(self,text,callback=None):
        b=QPushButton(text); b.setObjectName('boButton');
        if callback: b.clicked.connect(callback)
        self.extra.addWidget(b); return b

class DataTable(QTableWidget):
    def __init__(self,columns:Iterable[str],parent=None):
        columns=list(columns); super().__init__(0,len(columns),parent); self.setHorizontalHeaderLabels(columns)
        self.setObjectName('boTable'); self.setAlternatingRowColors(True); self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers); self.verticalHeader().hide()
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)
    def set_rows(self,rows:Iterable[Iterable[object]])->None:
        rows=list(rows); self.setRowCount(len(rows))
        for r,row in enumerate(rows):
            for c,value in enumerate(row): self.setItem(r,c,QTableWidgetItem(str(value)))
        self.resizeRowsToContents()
        self.setMinimumHeight(min(420,max(120,36+len(rows)*30)))

class EmptyState(QFrame):
    def __init__(self,title='Nothing to show',detail='',parent=None):
        super().__init__(parent); self.setObjectName('boEmpty'); box=QVBoxLayout(self); box.setContentsMargins(18,24,18,24)
        title_lab=label(title,14,True); title_lab.setAlignment(Qt.AlignCenter); box.addWidget(title_lab)
        detail_lab=label(detail,12,color=MUTED,wrap=True); detail_lab.setAlignment(Qt.AlignCenter); box.addWidget(detail_lab)

class TwoColumn(QWidget):
    def __init__(self,left_stretch=3,right_stretch=2,parent=None):
        super().__init__(parent); row=QHBoxLayout(self); row.setContentsMargins(0,0,0,0); row.setSpacing(12)
        self.left=QVBoxLayout(); self.left.setSpacing(12); self.right=QVBoxLayout(); self.right.setSpacing(12)
        row.addLayout(self.left,left_stretch); row.addLayout(self.right,right_stretch)
