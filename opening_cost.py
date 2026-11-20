"""The opening cost a city card shows: what corporate.open_market will charge.

Rival AI on: ``rival_ai.player_opening_cost`` (supercenter table x factor 95, the exact charge).
AI off: the old ``market.opening_cost`` text, unchanged.
"""

from __future__ import annotations


def shown_opening_cost(state, market) -> int:
    if state is not None and getattr(state, "rival_ai", None) is not None:
        from open_late.rival_ai import is_on, player_opening_cost

        if is_on(state):
            priced = int(player_opening_cost(state, market.id))
            if priced > 0:
                return priced
            from open_late.economy_e3 import opening_cost_mult

            return int(round(int(market.opening_cost) * opening_cost_mult(state, market.id)))
    return int(market.opening_cost)
