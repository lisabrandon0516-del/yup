"""One supercenter build-cost table for the player and the rivals.

Evansville's first door is the company the player already owns, so the
player market row stays at zero. A rival's first Evansville door is a new
building and uses the table.
"""

from __future__ import annotations

SUPERCENTER_BUILD_COST: dict[str, int] = {
    "seattle": 30_000_000,
    "naperville": 26_180_000,
    "las_vegas": 24_000_000,
    "houston": 19_640_000,
    "evansville": 15_000_000,
}


def build_cost(city: str) -> int:
    return SUPERCENTER_BUILD_COST[city]
