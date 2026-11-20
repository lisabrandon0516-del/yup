"""Phase 5 coordinates the desks Phase 4 already installed. It does not replace them."""

from __future__ import annotations

from open_late.ui.phase4.integration import merged_page_classes as phase4_classes


def merged_page_classes():
    return phase4_classes()


def install_into_registry_module():
    import open_late.ui.page_registry as registry

    registry.PAGE_CLASSES = merged_page_classes()
    return registry.PAGE_CLASSES
