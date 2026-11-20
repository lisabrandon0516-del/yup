"""How sure the reading is. This is not how serious it is."""

from __future__ import annotations


def band(score: int) -> str:
    if score >= 75:
        return "high"
    if score >= 45:
        return "moderate"
    return "low"


def rate(reliability: int, *, measured: bool) -> tuple[int, str]:
    """A counted figure scores higher than a public sentence."""
    score = int(reliability)
    if not measured:
        score -= 20
    score = max(0, min(100, score))
    return score, band(score)
