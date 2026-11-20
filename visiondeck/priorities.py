"""How serious a condition is. Confidence is not an input."""

from __future__ import annotations


def rank(*, customer: int = 0, financial: int = 0, competitive: int = 0, urgency: int = 0, opportunity: bool = False) -> str:
    if opportunity:
        return "opportunity"
    top = max(int(customer), int(financial), int(competitive), int(urgency))
    if top >= 3:
        return "critical"
    if top >= 2:
        return "high"
    if top >= 1:
        return "moderate"
    return "watch"
