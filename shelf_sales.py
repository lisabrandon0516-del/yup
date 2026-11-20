"""Shoppers + Planograms LITE: shelves into units.

``door_shelf(state, door)`` is the only call the engine makes. It returns ``None``
when the feature is off (the engine then runs exactly as in p2) or a ``DoorShelf``:

* ``sku[product_id]``  within-department pick multiplier (the department total is unchanged)
* ``lift[dept]``       department unit multiplier; with the SKU mix it lands department sales on
                        a 0.90-1.08 clamp, times the reset dip

    vis(sku)   = inline: avg(exposure x POS[tier]) x FACE(facings)  + feature slots + pairs
    shelf(sku) = (1 - impulse) + impulse x vis / vis_neutral(sku)   (0.05 when off the shelf)
    sales(dept) = demand x price weighted mean shelf(sku), clamped; lift = sales / price-mix shift

Results are cached per (door, layout, week, dip day, trend/price signature).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from open_late.planogram_api import RESET_DIP, shelf_effect_full, visibility
from open_late.shelf_model import Layout, sku_index_v1


@dataclass
class DoorShelf:
    sku: dict[str, float] = field(default_factory=dict)
    lift: dict[str, float] = field(default_factory=dict)


_CACHE: dict[tuple, DoorShelf] = {}
_VIS_CACHE: dict[tuple, dict[int, float]] = {}


def _vis(layout: Layout, ages: dict[str, int]) -> dict[int, float]:
    from open_late.shelves import stale_factor

    key = (layout.fingerprint(), tuple(sorted(ages.items())))
    hit = _VIS_CACHE.get(key)
    if hit is None:
        if len(_VIS_CACHE) > 512:
            _VIS_CACHE.clear()
        hit = visibility(layout, {k: stale_factor(v) for k, v in ages.items()})
        _VIS_CACHE[key] = hit
    return hit


def multipliers(state, door, layout: Layout, ages: dict[str, int]) -> tuple[dict[str, float], dict[str, float]]:
    """(per-SKU pick multipliers by product id, per-department unit lift before the dip)."""
    sku, unit, _rev = multipliers_full(state, door, layout, ages)
    return sku, unit


def multipliers_full(state, door, layout: Layout, ages: dict[str, int]):
    """(sku multipliers by product id, dept unit lift, dept sales lift) before the dip."""
    from open_late.shelves import demand_weights, neutral_ages, neutral_for, shelf_prices, week_of

    week = week_of(state.day)
    neutral = neutral_for(state, door, week)
    vis = _vis(layout, ages)
    vis_n = _vis(neutral, neutral_ages(neutral, week))
    sku_i, unit, rev = shelf_effect_full(vis, vis_n, demand_weights(state, door), price=shelf_prices(state))
    ids = sku_index_v1()
    return {ids[i]: m for i, m in sku_i.items()}, unit, rev


def door_shelf(state, door) -> DoorShelf | None:
    data = getattr(state, "shelves", None)
    if not data or not data.get("on"):
        return None
    from open_late.shelves import compile_for, door_entry, endcap_ages, week_of

    entry = door_entry(state, door)
    week = week_of(state.day)
    dip = entry.get("dip") or {}
    dip_on = bool(dip) and state.day <= int(dip.get("until", 0))
    sig = hash(tuple((p.trend, p.price, p.quality) for p in state.products.values()))
    layout = compile_for(state, door)
    key = (door.id, layout.fingerprint(), int(entry.get("rev", 0)), week, dip_on, sig, len(state.products))
    hit = _CACHE.get(key)
    if hit is not None:
        return hit
    if len(_CACHE) > 256:
        _CACHE.clear()
    ages = endcap_ages(state, door, layout, week=week)
    sku, lift = multipliers(state, door, layout, ages)
    if dip_on:
        aff = dip.get("aff") or {}
        for d in list(lift):
            share = int(aff.get(d, 0)) / 1000.0
            if share:
                lift[d] = lift[d] * (1.0 - (1.0 - RESET_DIP) * share)
    out = DoorShelf(sku=sku, lift=lift)
    _CACHE[key] = out
    return out
