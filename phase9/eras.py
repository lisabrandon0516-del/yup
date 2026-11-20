"""Eras inferred from stores and recent results. Nothing is written back."""

from __future__ import annotations

from open_late.ui.overview_data import _profit

from .models import CorporateEra
from .timeline import _reports


def identify(state) -> list[CorporateEra]:
    if state is None:
        return []
    day = max(1, int(getattr(state, "day", 1) or 1))
    doors = list(getattr(state, "doors", []) or [])
    eras = [CorporateEra("founding", "Founding Era", 1, None, "The company began operations.")]
    opened = sorted(int(getattr(door, "opens_on", 0) or 0) for door in doors if int(getattr(door, "opens_on", 0) or 0) > 1)
    if opened:
        eras[-1] = CorporateEra("founding", "Founding Era", 1, opened[0] - 1, "The company operated its original footprint.")
        eras.append(CorporateEra("expansion", "First Expansion", opened[0], None, "The company opened an additional store."))
    history = _reports(state)
    if history:
        recent = history[-28:]
        profit = sum(_profit(row) for row in recent)
        if profit < 0 and eras:
            previous = eras[-1]
            eras[-1] = CorporateEra(previous.id, previous.title, previous.start_day, max(previous.start_day, day - 28), "The prior era ended as recent operations became unprofitable.")
            eras.append(CorporateEra("turnaround", "Turnaround", max(1, day - 27), None, "Recent operating results are negative."))
    return eras
