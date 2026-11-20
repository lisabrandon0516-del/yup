"""Drop only the pages this harness added. The live desks stay where they are."""

from __future__ import annotations


def disable(integrated) -> bool:
    created = getattr(integrated, "created", None) or []
    for page in created:
        try:
            page.hide()
            page.setParent(None)
            page.deleteLater()
        except Exception:
            pass
    return True
