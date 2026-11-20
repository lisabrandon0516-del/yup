"""Double-click opens a read-only record. The engine is not called from here."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from .detail_view import DeepDetailView
from .inspectors import inspect
from .routes import infer


class DeepDrillController(QObject):
    opened = Signal(object)

    def __init__(self, registry, state_provider, host=None):
        super().__init__(host)
        self.registry = registry
        self.state_provider = state_provider
        self.host = host
        self.view = DeepDetailView(host)
        for page_id, page in registry.pages.items():
            self._watch(page_id, page)
        ledger = getattr(host, "ledger", None)
        if ledger is not None:
            self._watch("inventory", ledger)

    def _watch(self, page_id: str, page) -> None:
        table = getattr(page, "table", None)
        signal = getattr(table, "itemDoubleClicked", None)
        if signal is not None:
            signal.connect(lambda item, pid=page_id, page=page: self.open_row(pid, page, item.row()))

    def open_row(self, page_id: str, page, row: int) -> None:
        table = getattr(page, "table", None)
        if table is None or row < 0 or row >= table.rowCount():
            return
        headers = []
        values = []
        for column in range(table.columnCount()):
            header = table.horizontalHeaderItem(column)
            headers.append(header.text() if header is not None else "")
            cell = table.item(row, column)
            values.append(cell.text() if cell is not None else "")
        ref = infer(page_id, headers, values, self.state_provider())
        if ref is not None:
            self.open_entity(ref.kind, ref.entity_id)

    def open_entity(self, kind: str, entity_id: str) -> None:
        record = inspect(self.state_provider(), kind, entity_id)
        shallow = getattr(self.host, "detail_drawer", None)
        if shallow is not None:
            shallow.hide()
        self.view.show_record(record)
        self.opened.emit(record)
