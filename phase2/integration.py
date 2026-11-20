"""The five desks Phase 2 fills. Inventory, finance, and the floor stay on their own screens."""
from __future__ import annotations
from open_late.ui.pages.modules import PAGE_CLASSES
from .pages import PHASE2_PAGE_CLASSES

def merged_page_classes():
    return {**PAGE_CLASSES,**PHASE2_PAGE_CLASSES}

def install_into_registry_module():
    import open_late.ui.page_registry as registry
    # Only the desks that are still the older pages. Inventory, merchandising,
    # overview, stores, and planograms stay on the screens already in the game.
    registry.PAGE_CLASSES = dict(PHASE2_PAGE_CLASSES)
    return registry.PAGE_CLASSES
