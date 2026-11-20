"""Connects the Action Center, briefing, scope, and row drill-down to the shell."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from .action_center import build, counts
from .briefing import morning
from .navigation import DrillTarget
from .scope import Scope


class ConnectedCommandCenter(QObject):
    navigate = Signal(object)
    scope_changed = Signal(object)
    action_center_changed = Signal(object)
    briefing_changed = Signal(object)

    def __init__(self, registry, state_provider, navigator=None):
        super().__init__()
        self.registry = registry
        self.state_provider = state_provider
        self.navigator = navigator
        self.scope = Scope()
        self.navigate.connect(self._navigate)
        for page in registry.pages.values():
            table = getattr(page, "table", None)
            signal = getattr(table, "itemDoubleClicked", None)
            if signal is not None:
                signal.connect(lambda item, page=page: self._row(page, item.row()))

    def refresh(self) -> None:
        state = self.state_provider()
        items = build(state, self.scope)
        brief = morning(state, self.scope)
        self.action_center_changed.emit({"items": items, "counts": counts(items)})
        self.briefing_changed.emit(brief)

    def set_scope(self, kind, ident=None) -> None:
        if kind in ("all", "", None):
            kind = "company"
        self.scope = Scope(kind, ident)
        self.scope_changed.emit(self.scope)
        state = self.state_provider()
        if state is None:
            self.refresh()
            return
        for page in self.registry.pages.values():
            if hasattr(page, "set_scope"):
                page.set_scope(self.scope)
            page.load(state)
        self.refresh()

    def _navigate(self, drill: DrillTarget) -> None:
        if self.navigator is not None:
            self.navigator(drill)
            return
        page = self.registry.pages.get(drill.page_id)
        if page is None:
            return
        search = getattr(getattr(page, "filters", None), "search", None)
        query = drill.filters.get("query") or drill.entity_id
        if search is not None and query:
            search.setText(str(query))
        table = getattr(page, "table", None)
        if table is not None and table.rowCount():
            table.selectRow(0)

    def _row(self, page, row: int) -> None:
        table = page.table
        if row < 0 or row >= table.rowCount():
            return
        record = {}
        for column in range(table.columnCount()):
            header = table.horizontalHeaderItem(column)
            name = header.text() if header is not None else str(column)
            cell = table.item(row, column)
            record[name] = cell.text() if cell is not None else ""
        drawer = getattr(page, "detail_drawer", None)
        if drawer is not None:
            drawer.show_record(page.title, record, "Opened from the desk")
