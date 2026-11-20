"""Small reusable model/view table implementation for large Phase 2 tables."""
from __future__ import annotations
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

class MappingTableModel(QAbstractTableModel):
    def __init__(self,columns:list[tuple[str,str]],rows=None,parent=None):
        super().__init__(parent); self.columns=list(columns); self.rows=list(rows or [])
    def rowCount(self,parent=QModelIndex()): return 0 if parent.isValid() else len(self.rows)
    def columnCount(self,parent=QModelIndex()): return 0 if parent.isValid() else len(self.columns)
    def data(self,index,role=Qt.DisplayRole):
        if not index.isValid() or not (0<=index.row()<len(self.rows)): return None
        key=self.columns[index.column()][0]; value=self.rows[index.row()].get(key,'')
        if role in (Qt.DisplayRole,Qt.ToolTipRole): return str(value)
        if role==Qt.UserRole: return self.rows[index.row()]
        return None
    def headerData(self,section,orientation,role=Qt.DisplayRole):
        if role==Qt.DisplayRole and orientation==Qt.Horizontal and 0<=section<len(self.columns): return self.columns[section][1]
        return super().headerData(section,orientation,role)
    def replace(self,rows):
        self.beginResetModel(); self.rows=list(rows or []); self.endResetModel()
