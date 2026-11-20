"""What Phase 10 expects to find already installed."""

from __future__ import annotations

PHASES = {
    1: ("open_late.ui.components", "open_late.ui.pages", "open_late.ui.page_registry"),
    2: ("open_late.ui.phase2",),
    4: ("open_late.ui.phase4",),
    5: ("open_late.ui.phase5",),
    6: ("open_late.ui.phase6",),
    7: ("open_late.ui.phase7",),
    8: ("open_late.ui.phase8",),
    9: ("open_late.ui.phase9",),
}

CORE_REQUIRED = (
    "open_late.ui.hq_shell",
    "open_late.ui.hq_pages",
    "open_late.ui.theme",
    "open_late.ui.window",
)

OPTIONAL_REQUIRED = (
    "open_late.ui.inventory_sheet",
    "open_late.ui.overview_data",
    "open_late.ui.hq_adapter",
)
