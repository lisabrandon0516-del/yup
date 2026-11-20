from __future__ import annotations
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout
from open_late.ui.components import DataTable, FilterBar, KpiCard, PageCanvas, Section, TwoColumn

class ModulePage(PageCanvas):
    open_page=Signal(str)
    title='Module'; deck=''; columns=(); kpis=()
    def __init__(self,parent=None):
        super().__init__(self.title,self.deck,parent); self._state=None
        self.filters=FilterBar(f'Search {self.title.lower()}…'); self.body.addWidget(self.filters)
        self.kpi_row=QHBoxLayout(); self.kpi_row.setSpacing(8); self.body.addLayout(self.kpi_row)
        self.kpi_cards=[]
        for caption in self.kpis:
            card=KpiCard(caption); self.kpi_row.addWidget(card); self.kpi_cards.append(card)
        self.columns_widget=TwoColumn(); self.body.addWidget(self.columns_widget)
        self.primary=Section(self.primary_title()); self.table=DataTable(self.columns); self.primary.body.addWidget(self.table)
        self.columns_widget.left.addWidget(self.primary)
        self.insight=Section('Management Notes'); self.columns_widget.right.addWidget(self.insight)
        self.body.addStretch(1); self.filters.search_changed.connect(self._filter)
    def primary_title(self): return self.title
    def load(self,state):
        self._state=state
        self.refresh()
        self._apply_scope()
    def refresh(self): self.table.set_rows([])
    def set_scope(self,scope):
        self._scope=scope
        self._apply_scope()
    def _filter(self,text):
        self._apply_scope()
    def _apply_scope(self):
        table=getattr(self,'table',None)
        if table is None: return
        query=''
        search=getattr(getattr(self,'filters',None),'search',None)
        if search is not None: query=search.text().strip().lower()
        scope=getattr(self,'_scope',None)
        needle=''
        kind=getattr(scope,'kind','company') if scope is not None else 'company'
        ident=getattr(scope,'ident',None) if scope is not None else None
        if kind not in ('company','all') and ident:
            needle=str(ident).lower()
            state=getattr(self,'_state',None)
            if kind=='store' and state is not None:
                door=next((item for item in state.doors if item.id==ident), None)
                if door is not None: needle=door.city.lower()
        texts=[]
        for row in range(table.rowCount()):
            texts.append(' '.join(table.item(row,col).text().lower() if table.item(row,col) else '' for col in range(table.columnCount())))
        scoped=bool(needle) and any(needle in text for text in texts)
        for row,text in enumerate(texts):
            hidden=bool(query) and query not in text
            if scoped and needle not in text: hidden=True
            table.setRowHidden(row,hidden)
    def set_kpi(self,index,value,detail='',tone='neutral'):
        if 0<=index<len(self.kpi_cards): self.kpi_cards[index].set_data(value,detail,tone)
