"""Shoppers + Planograms LITE: game-state glue and player actions.

All Lite state lives in ``GameState.shelves`` (empty = off, bit-identical to p2):

    {"v": 1, "on": True,
     "doors": {door_id: {"size": "supercenter_v1", "choice": {packed LiteChoice},
                          "floor": "" | "C1:grocery,...", "base": {dept: share},
                          "rev": 3, "reset_week": 12, "endcap_since": {"C1.F": 12},
                          "dip": {"until": 87, "aff": {"grocery": 420}},
                          "last": {"day": 85, "changed": 84, "labor": 9135}}},
     "templates": {custom_id: {...LayoutPolicy fields}},   # <= 10
     "groups": {group_id: {"name": str, "doors": [...], "choice": {...}}},
     "scouts": []}                                         # filled in phase 2

The compiled Layout is never saved; it is rebuilt from (size, floor, choice,
catalog version, rotation) and cached in memory.
"""

from __future__ import annotations

import copy
from functools import lru_cache
from typing import Any

from open_late.planogram_api import (
    TEMPLATES,
    LayoutPolicy,
    ResetCost,
    ScoreCtx,
    ShelfScore,
    auto_planogram,
    check_pins,
    derived_shares,
    policy_for,
    reset_cost,
    score_layout,
    validate_layout,
)
from open_late.shelf_model import (
    CATALOG_VERSION,
    DEFAULT_SIZE,
    Aisle,
    Layout,
    LiteChoice,
    default_floor,
    floor_limits,
    formats,
    next_uid,
    pack_choice,
    pack_floor,
    size_spec,
    sku_pos,
    unpack_choice,
    unpack_floor,
)

MAX_CUSTOM_TEMPLATES = 10
NEUTRAL_REFRESH = 3


_DEFAULT_ON = False  # the playable launcher turns this on (like rival_ai); library/test callers stay off


def set_default_enabled(on: bool) -> None:
    """New corporate games from ``engine.new_game`` start with store layouts on when True."""
    global _DEFAULT_ON
    _DEFAULT_ON = bool(on)


def default_enabled() -> bool:
    return _DEFAULT_ON


def week_of(day: int) -> int:
    return max(0, (int(day) - 1) // 7)


def shelves_on(state) -> bool:
    data = getattr(state, "shelves", None)
    return bool(data) and bool(data.get("on"))


def _root(state) -> dict[str, Any]:
    data = state.shelves
    if not data:
        data = {"v": 1, "on": False, "doors": {}, "templates": {}, "groups": {}, "scouts": []}
        state.shelves = data
    data.setdefault("doors", {})
    data.setdefault("templates", {})
    data.setdefault("groups", {})
    data.setdefault("scouts", [])
    return data


def _default_entry(door) -> dict[str, Any]:
    return {
        "size": DEFAULT_SIZE,
        "choice": None,  # None = follow the store group, else Balanced
        "floor": "",
        "base": dict(getattr(door, "planogram", {}) or {}),
        "rev": 0,
        "reset_week": 0,
        "endcap_since": {},
    }


def door_entry(state, door) -> dict[str, Any]:
    """Read-only view (a fresh default when the door has no entry yet)."""
    data = getattr(state, "shelves", None) or {}
    entry = (data.get("doors") or {}).get(door.id)
    if entry is None:
        return _default_entry(door)
    spec = entry.get("size_spec")
    size_id = entry.get("size")
    if spec and size_id:
        from open_late.shelf_model import register_size

        register_size(str(size_id), spec)
    return entry


_LAYOUT_AISLES = {
    "balanced": (
        ["grocery", "household", "health_beauty"],
        ["electronics", "clothing", "toys", "home_garden", "sporting", "household"],
    ),
    "fresh_first": (
        ["grocery", "grocery", "household", "health_beauty"],
        ["home_garden", "household", "toys"],
    ),
    "value_grocery": (
        ["grocery", "grocery", "grocery", "household"],
        ["household", "health_beauty", "toys"],
    ),
    "gm_push": (
        ["household", "health_beauty", "grocery"],
        ["electronics", "electronics", "clothing", "sporting", "toys", "home_garden"],
    ),
    "seasonal_push": (
        ["grocery", "household", "health_beauty"],
        ["toys", "sporting", "home_garden", "clothing", "electronics"],
    ),
}
SUPER_SQFT = 115_000


def custom_size_spec(sq_ft: int, center: int, gm: int, template_id: str = "balanced") -> dict[str, Any]:
    """A full building: square feet set the fixed rooms, and the aisle counts are the starting floor."""
    import copy

    from open_late.shelf_model import formats

    spec = copy.deepcopy(formats()["sizes"]["supercenter_v1"])
    sq_ft = max(20_000, min(300_000, int(sq_ft)))
    center = max(2, min(30, int(center)))
    gm = max(2, min(30, int(gm)))
    scale = max(0.35, min(3.0, sq_ft / SUPER_SQFT))
    center_depts, gm_depts = _LAYOUT_AISLES.get(template_id, _LAYOUT_AISLES["balanced"])
    spec["label"] = f"{sq_ft:,} sq ft"
    spec["sq_ft"] = sq_ft
    spec["lanes"] = max(4, min(20, int(round(10 * scale))))
    for row in spec["fixed"]:
        row["bays"] = max(1, int(round(int(row["bays"]) * scale)))
    spec["center"]["bays"] = max(4, int(round(6 * scale)))
    spec["center"]["min"] = 2
    spec["center"]["max"] = 30
    spec["center"]["default"] = [center_depts[i % len(center_depts)] for i in range(center)]
    spec["gm"]["bays"] = max(3, int(round(4 * scale)))
    spec["gm"]["min"] = 2
    spec["gm"]["max"] = 30
    spec["gm"]["default"] = [gm_depts[i % len(gm_depts)] for i in range(gm)]
    return spec


def install_store_build(state, door, sq_ft: int, center: int, gm: int, template_id: str) -> str:
    """Write this door's size, floor, and template. Later aisle edits still work inside that building."""
    from open_late.shelf_model import LiteChoice, pack_choice, pack_floor, register_size

    template_id = template_id if template_id in _LAYOUT_AISLES else "balanced"
    spec = custom_size_spec(sq_ft, center, gm, template_id)
    size_id = f"custom_{door.id}"
    register_size(size_id, spec)
    enable_shelves(state)
    from open_late.shelf_model import default_floor

    entry = _default_entry(door)
    entry["size"] = size_id
    entry["size_spec"] = spec
    entry["floor"] = pack_floor(default_floor(size_id))
    entry["choice"] = pack_choice(LiteChoice(template_id=template_id))
    _root(state)["doors"][door.id] = entry
    return f"{spec['sq_ft']:,} sq ft, {center} center aisles, {gm} GM aisles"


def enable_shelves(state) -> str:
    """Opt in (old saves and phase 1 games). Keeps each door's department shares as the base,
    so the default template reproduces today's wall."""
    root = _root(state)
    if root.get("on"):
        return ""
    root["on"] = True
    for door in state.doors:
        root["doors"].setdefault(door.id, _default_entry(door))
    state.actions_today.append("Store layouts are on. Every store starts on the Balanced template.")
    return ""


# ---------------------------------------------------------------- choices and groups


def group_of(state, door_id: str) -> str:
    for gid, group in sorted(((getattr(state, "shelves", None) or {}).get("groups") or {}).items()):
        if door_id in (group.get("doors") or []):
            return gid
    return ""


def effective_choice(state, door) -> LiteChoice:
    entry = door_entry(state, door)
    if entry.get("choice") is not None and not entry.get("follow_group"):
        return unpack_choice(entry.get("choice"))
    gid = group_of(state, door.id)
    if gid:
        return unpack_choice(state.shelves["groups"][gid].get("choice"))
    return LiteChoice()


def custom_templates(state) -> dict[str, Any]:
    return dict(((getattr(state, "shelves", None) or {}).get("templates") or {}))


def save_custom_template(state, name: str, focus_dept: str, facings_rule: str, endcap_mode: str,
                         refresh_weeks: int, place: str = "family") -> str:
    root = _root(state)
    templates = root["templates"]
    if len(templates) >= MAX_CUSTOM_TEMPLATES:
        return f"You can keep up to {MAX_CUSTOM_TEMPLATES} custom templates."
    n = 1
    while f"custom:{n}" in templates:
        n += 1
    templates[f"custom:{n}"] = {
        "name": name[:28] or f"Custom {n}", "focus_dept": focus_dept, "facings_rule": facings_rule,
        "endcap_mode": endcap_mode, "refresh_weeks": max(1, min(8, int(refresh_weeks))), "place": place,
    }
    return ""


def set_group(state, group_id: str, name: str, door_ids: list[str]) -> None:
    root = _root(state)
    for group in root["groups"].values():
        group["doors"] = [d for d in group.get("doors", []) if d not in door_ids]
    root["groups"][group_id] = {"name": name, "doors": list(door_ids), "choice": {"t": "balanced"}}


# ---------------------------------------------------------------- compile (cached)


def _sku_ids(state) -> tuple[str, ...]:
    pos = sku_pos()
    return tuple(sorted((pid for pid in state.products if pid in pos), key=pos.get))


@lru_cache(maxsize=256)
def _compile_cached(size_id: str, floor_text: str, choice_key: str, policy: LayoutPolicy, sku_ids: tuple[str, ...],
                    rotation: int, allows_pharmacy: bool) -> Layout:
    import json

    choice = unpack_choice(json.loads(choice_key))
    return auto_planogram(
        size_id,
        unpack_floor(floor_text, size_id),
        policy,
        sku_ids,
        pins=choice.priorities,
        facing_targets=choice.facing_map(),
        endcap_fill=choice.endcap_map(),
        alley_fill=choice.alley_map(),
        checkout_mix=choice.checkout_mix,
        rotation=rotation,
        allows_pharmacy=allows_pharmacy,
    )


def _choice_key(choice: LiteChoice) -> str:
    import json

    return json.dumps(pack_choice(choice), sort_keys=True, separators=(",", ":"))


def rotation_for(policy: LayoutPolicy, reset_week: int, week: int) -> tuple[int, int]:
    """(rotation index for auto endcaps, weeks since the last auto rotation)."""
    span = max(0, week - reset_week)
    refresh = max(1, int(policy.refresh_weeks))
    return span // refresh, span % refresh


def compile_for(state, door, *, choice: LiteChoice | None = None, floor_text: str | None = None,
                week: int | None = None, reset_week: int | None = None) -> Layout:
    entry = door_entry(state, door)
    choice = choice if choice is not None else effective_choice(state, door)
    policy = policy_for(choice.template_id, custom_templates(state))
    week = week_of(state.day) if week is None else week
    reset_week = int(entry.get("reset_week", 0)) if reset_week is None else reset_week
    rotation, _age = rotation_for(policy, reset_week, week)
    return _compile_cached(
        entry.get("size", DEFAULT_SIZE),
        entry.get("floor", "") if floor_text is None else floor_text,
        _choice_key(choice),
        policy,
        _sku_ids(state),
        rotation,
        bool(getattr(door, "allows_intense", True)),
    )


def neutral_for(state, door, week: int | None = None) -> Layout:
    """The 'average store': Balanced on the default floor, endcaps rotating every 3 weeks from week 0."""
    entry = door_entry(state, door)
    week = week_of(state.day) if week is None else week
    return _compile_cached(
        entry.get("size", DEFAULT_SIZE), "", _choice_key(LiteChoice()), TEMPLATES["balanced"], _sku_ids(state),
        week // NEUTRAL_REFRESH, bool(getattr(door, "allows_intense", True)),
    )


def stale_factor(weeks: int) -> float:
    return max(0.3, 0.5 ** (max(0, weeks) / 3.0))


def endcap_ages(state, door, layout: Layout, *, choice: LiteChoice | None = None, week: int | None = None) -> dict[str, int]:
    entry = door_entry(state, door)
    choice = choice if choice is not None else effective_choice(state, door)
    policy = policy_for(choice.template_id, custom_templates(state))
    week = week_of(state.day) if week is None else week
    _rot, auto_age = rotation_for(policy, int(entry.get("reset_week", 0)), week)
    manual = choice.endcap_map()
    since = entry.get("endcap_since") or {}
    out = {}
    for bay in layout.bays:
        if bay.kind != "endcap":
            continue
        if bay.key in manual:
            out[bay.key] = max(0, week - int(since.get(bay.key, entry.get("reset_week", 0))))
        else:
            out[bay.key] = auto_age
    return out


def neutral_ages(layout: Layout, week: int) -> dict[str, int]:
    return {bay.key: week % NEUTRAL_REFRESH for bay in layout.bays if bay.kind == "endcap"}


# ---------------------------------------------------------------- demand weights and score


def demand_weights(state, door) -> dict[int, float]:
    """The engine's own within-department pick weight (trend x quality x price fit), by SKU index."""
    from open_late.engine import _price_fit

    pos = sku_pos()
    out: dict[int, float] = {}
    trend = {"rising": 1.25, "steady": 1.0, "fading": 0.62}
    carried = getattr(door, "stock", None) or None  # the engine only picks among what the door carries
    for pid, product in state.products.items():
        i = pos.get(pid)
        if i is None or (carried is not None and pid not in carried):
            continue
        out[i] = trend.get(product.trend, 1.0) * (0.55 + product.quality * 0.16) * _price_fit(product) * (1.18 if product.exclusive else 1.0)
    return out


def shelf_prices(state) -> dict[int, float]:
    """Current shelf price by SKU index (what the dollar-side of the shelf math weighs by)."""
    pos = sku_pos()
    return {pos[pid]: float(p.price) for pid, p in state.products.items() if pid in pos}


def score_for(state, door, layout: Layout | None = None, *, choice: LiteChoice | None = None) -> ShelfScore:
    week = week_of(state.day)
    layout = layout or compile_for(state, door, choice=choice)
    neutral = neutral_for(state, door, week)
    ages = endcap_ages(state, door, layout, choice=choice, week=week)
    stock = getattr(door, "stock", {}) or {}
    pos = sku_pos()
    in_stock = frozenset(pos[pid] for pid, line in stock.items() if pid in pos and line.on_hand > 0)
    ctx = ScoreCtx(
        velocity=demand_weights(state, door),
        neutral=neutral,
        stale={k: stale_factor(v) for k, v in ages.items()},
        neutral_stale={k: stale_factor(v) for k, v in neutral_ages(neutral, week).items()},
        in_stock=in_stock if stock else None,
        base_shares=dict(door_entry(state, door).get("base") or door.planogram),
        compliance=50,
        price=shelf_prices(state),
    )
    return score_layout(layout, ctx)


def alerts_for(state, door, layout: Layout | None = None, *, choice: LiteChoice | None = None) -> list[str]:
    choice = choice if choice is not None else effective_choice(state, door)
    layout = layout or compile_for(state, door, choice=choice)
    promo = ""
    campaign = getattr(state, "campaign", None)
    if campaign is not None and (not campaign.door_id or campaign.door_id == door.id):
        promo = campaign.category
    return validate_layout(
        layout, pins=choice.priorities, velocity=demand_weights(state, door),
        stale_weeks=endcap_ages(state, door, layout, choice=choice), promo_category=promo,
        allows_pharmacy=bool(getattr(door, "allows_intense", True)),
    )


# ---------------------------------------------------------------- floor edits (pure)


def floor_of(state, door) -> tuple[Aisle, ...]:
    entry = door_entry(state, door)
    return unpack_floor(entry.get("floor", ""), entry.get("size", DEFAULT_SIZE))


def move_aisle(floor: tuple[Aisle, ...], uid: str, delta: int) -> tuple[tuple[Aisle, ...], str]:
    items = list(floor)
    i = next((k for k, a in enumerate(items) if a.uid == uid), -1)
    if i < 0:
        return floor, "That aisle isn't on this floor."
    kind = items[i].kind
    same = [k for k, a in enumerate(items) if a.kind == kind]
    at = same.index(i)
    to = at + delta
    if to < 0 or to >= len(same):
        return floor, "That aisle is already at the end."
    j = same[to]
    items[i], items[j] = items[j], items[i]
    return tuple(items), ""


def add_aisle(floor: tuple[Aisle, ...], size_id: str, kind: str, dept: str, used: tuple[str, ...] = ()) -> tuple[tuple[Aisle, ...], str]:
    lo, hi = floor_limits(size_id, kind)
    count = sum(1 for a in floor if a.kind == kind)
    if count >= hi:
        return floor, f"The floor has room for {hi} {'center' if kind == 'center' else 'GM'} aisles."
    allowed = formats()["aisle_kinds"][kind]["depts"]
    if dept not in allowed:
        return floor, f"{dept.replace('_', ' ').title()} doesn't go in that kind of aisle."
    uid = next_uid(floor, kind, used)
    return tuple(list(floor) + [Aisle(uid, kind, dept)]), ""


def remove_aisle(floor: tuple[Aisle, ...], size_id: str, uid: str) -> tuple[tuple[Aisle, ...], str]:
    aisle = next((a for a in floor if a.uid == uid), None)
    if aisle is None:
        return floor, "That aisle isn't on this floor."
    lo, _hi = floor_limits(size_id, aisle.kind)
    if sum(1 for a in floor if a.kind == aisle.kind) <= lo:
        return floor, f"A store keeps at least {lo} of those aisles."
    return tuple(a for a in floor if a.uid != uid), ""


def set_aisle_dept(floor: tuple[Aisle, ...], uid: str, dept: str) -> tuple[tuple[Aisle, ...], str]:
    aisle = next((a for a in floor if a.uid == uid), None)
    if aisle is None:
        return floor, "That aisle isn't on this floor."
    if dept not in formats()["aisle_kinds"][aisle.kind]["depts"]:
        return floor, f"{dept.replace('_', ' ').title()} doesn't go in that kind of aisle."
    return tuple(Aisle(a.uid, a.kind, dept) if a.uid == uid else a for a in floor), ""


def new_aisle_cost(old: tuple[Aisle, ...], new: tuple[Aisle, ...], size_id: str) -> int:
    from open_late.finance import SIZE_MULT

    spec = size_spec(size_id)
    old_ids = {a.uid for a in old}
    bays = sum(int(spec[a.kind]["bays"]) + 2 for a in new if a.uid not in old_ids)
    return int(spec.get("add_bay_cost", 2400)) * bays * SIZE_MULT // 10


# ---------------------------------------------------------------- preview and apply


def preview(state, door, choice: LiteChoice, floor: tuple[Aisle, ...] | None = None) -> dict[str, Any]:
    entry = door_entry(state, door)
    size_id = entry.get("size", DEFAULT_SIZE)
    week = week_of(state.day)
    old = compile_for(state, door)
    floor_text = pack_floor(floor) if floor is not None else entry.get("floor", "")
    new = compile_for(state, door, choice=choice, floor_text=floor_text, reset_week=week)
    cost: ResetCost = reset_cost(old, new, int(door.wage_floor))
    fixtures = new_aisle_cost(unpack_floor(entry.get("floor", ""), size_id), unpack_floor(floor_text, size_id), size_id)
    before = score_for(state, door, old)
    after = _score_new(state, door, new, choice)
    return {
        "door_id": door.id, "city": door.city, "changed": cost.changed, "labor": cost.labor,
        "fixtures": fixtures, "dip_days": cost.dip_days, "affected": cost.affected,
        "score_before": before.quality, "score_after": after.quality, "shares": after.dept_space,
        "alerts": alerts_for(state, door, new, choice=choice), "layout": new, "cost": cost,
        "est_sales_pct": estimate_sales_change(state, door, new, choice),
    }


def _score_new(state, door, layout: Layout, choice: LiteChoice) -> ShelfScore:
    week = week_of(state.day)
    neutral = neutral_for(state, door, week)
    policy = policy_for(choice.template_id, custom_templates(state))
    ages = {b.key: 0 for b in layout.bays if b.kind == "endcap"}
    del policy
    ctx = ScoreCtx(
        velocity=demand_weights(state, door), neutral=neutral,
        stale={k: stale_factor(v) for k, v in ages.items()},
        neutral_stale={k: stale_factor(v) for k, v in neutral_ages(neutral, week).items()},
        base_shares=dict(door_entry(state, door).get("base") or door.planogram),
        price=shelf_prices(state),
    )
    return score_layout(layout, ctx)


def estimate_sales_change(state, door, layout: Layout, choice: LiteChoice) -> float:
    """Expected weekly sales change vs the average store (percent, sales-weighted dept lifts)."""
    from open_late.shelf_sales import multipliers_full

    ages = {b.key: 0 for b in layout.bays if b.kind == "endcap"}
    _sku, _unit, lift = multipliers_full(state, door, layout, ages)
    weights = {k: max(0, int(v)) for k, v in door.planogram.items()}
    total = sum(weights.values()) or 1
    return round(100.0 * (sum(weights[d] * lift.get(d, 1.0) for d in weights) / total - 1.0), 2)


def apply_layout(state, door_ids: list[str], choice: LiteChoice, floor: tuple[Aisle, ...] | None = None) -> tuple[str, list[dict]]:
    """Commit a Lite choice (and optionally a new floor) to stores. Charges reset labor and new
    fixtures, starts the changed-bay dip, and derives the department shares."""
    from open_late.books import post
    from open_late.corporate import door_by_id
    from open_late.hq import record
    from open_late.text import money

    msg = check_pins(choice.priorities)
    if msg:
        return msg, []
    if choice.template_id not in TEMPLATES and choice.template_id not in custom_templates(state):
        return "That template isn't on the list.", []
    doors = [door_by_id(state, d) for d in door_ids]
    doors = [d for d in doors if d is not None]
    if not doors:
        return "No stores are selected.", []
    if floor is not None and len(doors) != 1:
        return "Aisle changes apply to one store at a time.", []
    previews = [preview(state, d, choice, floor) for d in doors]
    total = sum(p["labor"] + p["fixtures"] for p in previews)
    if total > state.cash:
        return f"The resets cost {money(total)} and the drawer has {money(state.cash)}.", previews
    enable_shelves(state)
    root = _root(state)
    week = week_of(state.day)
    for door, p in zip(doors, previews):
        entry = root["doors"].setdefault(door.id, _default_entry(door))
        old_choice = effective_choice(state, door)
        old_layout = compile_for(state, door)
        entry["choice"] = pack_choice(choice)
        entry.pop("follow_group", None)
        if floor is not None:
            entry["floor"] = pack_floor(floor) if floor != default_floor(entry.get("size", DEFAULT_SIZE)) else ""
        if p["changed"] <= 0 and not p["fixtures"]:
            continue
        if choice.template_id != old_choice.template_id or p["changed"] > 0:
            entry["reset_week"] = week
        since = dict(entry.get("endcap_since") or {})
        old_caps = {b.key: b.tiers for b in old_layout.bays if b.kind == "endcap"}
        new_layout: Layout = p["layout"]
        for bay in new_layout.bays:
            if bay.kind == "endcap" and old_caps.get(bay.key) != bay.tiers:
                since[bay.key] = week
        entry["endcap_since"] = {k: v for k, v in sorted(since.items()) if k in choice.endcap_map()}
        entry["rev"] = int(entry.get("rev", 0)) + 1
        cost = p["labor"] + p["fixtures"]
        if cost:
            state.cash -= cost
            state.spent_today += cost
            state.spent_planogram += p["labor"]
            state.quarter_opex += p["labor"]
            state.quarter_planogram += p["labor"]
            if p["fixtures"]:
                state.spent_fixtures += p["fixtures"]
                state.fixtures += p["fixtures"]
            record(state, door.id, labor=p["labor"])
            post(state, "planogram_reset", -cost, f"Planogram reset in {door.city}: {p['changed']} facings.")
        if p["dip_days"]:
            entry["dip"] = {"until": state.day + p["dip_days"] - 1, "aff": dict(p["affected"])}
        entry["last"] = {"day": state.day, "changed": p["changed"], "labor": p["labor"], "fixtures": p["fixtures"]}
        shares = p["shares"]
        if shares and sum(shares.values()) == 100:
            door.planogram = dict(shares)
    cities = ", ".join(d.city for d in doors)
    labor = sum(p["labor"] for p in previews)
    fixtures = sum(p["fixtures"] for p in previews)
    dip = max((p["dip_days"] for p in previews), default=0)
    changed = sum(p["changed"] for p in previews)
    if changed <= 0 and not fixtures:
        return f"Nothing changed on the shelves in {cities}.", previews
    parts = [f"Reset sent to {cities}: {changed} facings, {money(labor)} of labor"]
    if fixtures:
        parts.append(f"{money(fixtures)} of new fixtures")
    note = ", ".join(parts) + "."
    if dip:
        note += f" Changed shelves sell a little slower for {dip} days."
    state.actions_today.append(note)
    return note, previews


def snapshot_copy(state) -> dict[str, Any]:
    return copy.deepcopy(getattr(state, "shelves", {}) or {})


__all__ = [
    "CATALOG_VERSION", "shelves_on", "enable_shelves", "door_entry", "effective_choice", "compile_for", "neutral_for",
    "score_for", "alerts_for", "preview", "apply_layout", "move_aisle", "add_aisle", "remove_aisle",
    "set_aisle_dept", "floor_of", "save_custom_template", "set_group", "week_of", "stale_factor",
]


def store_pull_inputs(state, door) -> dict[str, int]:
    """What the rival AI's store-choice model reads for one player door (ai/shoppers.store_utility:
    ``planogram`` and ``selection``, 0-100, 50 = neutral). Off -> both 50, so it changes nothing."""
    if not shelves_on(state):
        return {"planogram": 50, "selection": 50}
    sc = score_for(state, door)
    return {"planogram": int(sc.quality), "selection": int(sc.selection)}
