"""Install the workstations without covering the screens that are already finished."""

from __future__ import annotations

from .workstations import PHASE4_PAGE_CLASSES


def merged_page_classes():
    return dict(PHASE4_PAGE_CLASSES)


def install_into_registry_module():
    import open_late.ui.page_registry as registry

    registry.PAGE_CLASSES = merged_page_classes()
    return registry.PAGE_CLASSES
