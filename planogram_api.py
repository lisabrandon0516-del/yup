"""Shoppers + Planograms LITE: the planogram toolkit (same functions for player and rivals).

* ``LayoutPolicy`` and the built-in templates
* ``auto_planogram`` compiles a floor + policy + pins + endcap picks into a ``Layout``
* ``score_layout`` (quality 0-100, 50 = the default template on the default floor)
* ``validate_layout`` (alerts), ``reset_cost`` (labor and the sales dip)

Pure and deterministic: the same inputs give a byte-identical layout. No RNG is
used; ties break on the frozen SKU index.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Iterable

from open_late.shelf_model import (
    DEFAULT_SIZE,
    MAX_ENDCAP_SKUS,
    MAX_PINS_PER_DEPT,
    MAX_PINS_PER_STORE,
    Aisle,
    Bay,
    Layout,
    default_floor,
    formats,
    pairs,
    size_spec,
    sku_index_v1,
    sku_pos,
    zone_exposure,
)

FACE_EXP = 0.17
FACE_REF = 2
FACE_CAP = 8
PIN_FACINGS = 3
RESET_HOURS_PER_FACING = 0.25
RESET_DIP = 0.88
LIFT_MIN, LIFT_MAX = 0.90, 1.08  # clamp on department SALES (dollars): no combination passes +8%
FEATURE_WEIGHT = 0.45  # tuned: a fresh endcap pick lands at +25..30% units for an impulse SKU
END_LIFT = 0.30
END_KEEP = 0.70  # 30% of an endcap's lift is cannibalized from the same item and department
PAIR_BONUS = 1.04


@dataclass(frozen=True)
class LayoutPolicy:
    id: str
    name: str
    focus_dept: str = ""
    facings_rule: str = "velocity"  # velocity | margin | even
    place: str = "family"  # family | velocity | price (what gets the eye-level tier)
    endcap_mode: str = "traffic"  # promo | seasonal | margin | traffic
    refresh_weeks: int = 3
    skill: int = 50
    blurb: str = ""


TEMPLATES: dict[str, LayoutPolicy] = {
    "balanced": LayoutPolicy(
        "balanced", "Balanced", "", "velocity", "family", "family", 3, 50,
        "The average store: families stay together, facings follow sales, endcaps rotate through each aisle.",
    ),
    "fresh_first": LayoutPolicy(
        "fresh_first", "Fresh first", "produce", "velocity", "velocity", "traffic", 2, 50,
        "Produce leads the action alley and front endcaps; best sellers at eye level.",
    ),
    "value_grocery": LayoutPolicy(
        "value_grocery", "Value grocery", "grocery", "even", "price", "promo", 3, 50,
        "Cheapest families at eye level, even facings, deal items on the endcaps.",
    ),
    "gm_push": LayoutPolicy(
        "gm_push", "GM push", "electronics", "margin", "velocity", "margin", 4, 50,
        "General merchandise up front; facings follow margin.",
    ),
    "seasonal_push": LayoutPolicy(
        "seasonal_push", "Seasonal push", "seasonal", "velocity", "family", "seasonal", 2, 50,
        "Seasonal items take the front endcaps and the action alley; fast rotation.",
    ),
}
TEMPLATE_ORDER = ("balanced", "fresh_first", "value_grocery", "gm_push", "seasonal_push")


def policy_for(template_id: str, custom: dict[str, Any] | None = None) -> LayoutPolicy:
    if template_id in TEMPLATES:
        return TEMPLATES[template_id]
    data = (custom or {}).get(template_id)
    if data:
        return LayoutPolicy(
            id=template_id,
            name=str(data.get("name", template_id)),
            focus_dept=str(data.get("focus_dept", "")),
            facings_rule=str(data.get("facings_rule", "velocity")),
            place=str(data.get("place", "family")),
            endcap_mode=str(data.get("endcap_mode", "traffic")),
            refresh_weeks=max(1, int(data.get("refresh_weeks", 3))),
        )
    return TEMPLATES["balanced"]


# ---------------------------------------------------------------- catalog facts


@dataclass(frozen=True)
class SkuFact:
    idx: int
    id: str
    dept: str
    price: int
    cost: int
    case_size: int
    hint: float  # static velocity hint (shipped catalog), used for compile ranking


def _trend_mult(trend: str) -> float:
    return {"rising": 1.25, "steady": 1.0, "fading": 0.62}.get(trend, 1.0)


def _price_fit(cost: int, price: int) -> float:
    from open_late.engine import _price_fit as engine_fit

    class _P:  # the engine helper only reads cost and price
        pass

    item = _P()
    item.cost, item.price = int(cost), int(price)
    return engine_fit(item)  # type: ignore[arg-type]


@lru_cache(maxsize=None)
def shipped_facts() -> tuple[SkuFact, ...]:
    from open_late.content import LABEL_PRODUCTS, PRODUCTS

    by_id = {p.id: p for p in list(PRODUCTS) + list(LABEL_PRODUCTS)}
    out = []
    for idx, sku in enumerate(sku_index_v1()):
        p = by_id[sku]
        hint = (0.55 + p.quality * 0.16) * _price_fit(p.cost, p.price) * _trend_mult(p.trend) * (1.18 if p.exclusive else 1.0)
        out.append(SkuFact(idx, sku, str(p.department or p.category), int(p.price), int(p.cost), int(p.case_size or 1), round(hint, 4)))
    return tuple(out)


@lru_cache(maxsize=None)
def shipped_core_facts() -> tuple[SkuFact, ...]:
    from open_late.content import PRODUCTS

    return facts_for(p.id for p in PRODUCTS)


def facts_for(sku_ids: Iterable[str]) -> tuple[SkuFact, ...]:
    pos = sku_pos()
    facts = shipped_facts()
    wanted = sorted(pos[s] for s in set(sku_ids) if s in pos)
    return tuple(facts[i] for i in wanted)


# ---------------------------------------------------------------- compile


def _position_factor(i: int, default_count: int) -> float:
    step = float(formats()["aisle_position_step"])
    mid = (default_count - 1) / 2.0
    return max(0.6, round(1.0 + step * (mid - i), 4))


def _largest_remainder(total: int, weights: list[float], base: list[int], cap: int) -> list[int]:
    out = list(base)
    extra = total - sum(out)
    if extra <= 0:
        return out
    for _round in range(4):
        open_ix = [i for i in range(len(out)) if out[i] < cap]
        if not open_ix or extra <= 0:
            break
        wsum = sum(weights[i] for i in open_ix) or float(len(open_ix))
        raw = {i: extra * (weights[i] if wsum else 1.0) / wsum for i in open_ix}
        given = 0
        for i in open_ix:
            add = min(cap - out[i], int(raw[i]))
            out[i] += add
            given += add
        extra -= given
        order = sorted(open_ix, key=lambda i: (-(raw[i] - int(raw[i])), i))
        for i in order:
            if extra <= 0:
                break
            if out[i] < cap:
                out[i] += 1
                extra -= 1
    return out


def _rank(facts: list[SkuFact], mode: str) -> list[SkuFact]:
    if mode == "margin":
        key = lambda f: (-(f.price - f.cost) * f.hint, f.idx)  # noqa: E731
    elif mode == "promo":
        key = lambda f: (-(f.hint / max(1, f.price)), f.idx)  # noqa: E731
    elif mode == "price":
        key = lambda f: (f.price, f.idx)  # noqa: E731
    elif mode == "family":
        key = lambda f: f.idx  # noqa: E731
    else:
        key = lambda f: (-f.hint, f.idx)  # noqa: E731
    return sorted(facts, key=key)


def _pick_rotating(ranked: list[SkuFact], count: int, offset: int, taken: set[int]) -> list[int]:
    out: list[int] = []
    if not ranked:
        return out
    n = len(ranked)
    i = 0
    while len(out) < count and i < n:
        f = ranked[(offset + i) % n]
        if f.idx not in taken and f.idx not in out:
            out.append(f.idx)
        i += 1
    return out


def auto_planogram(
    size_id: str,
    floor: tuple[Aisle, ...] | None,
    policy: LayoutPolicy,
    sku_ids: Iterable[str] | None = None,
    *,
    pins: Iterable[int] = (),
    facing_targets: dict[int, int] | None = None,
    endcap_fill: dict[str, tuple[int, ...]] | None = None,
    alley_fill: dict[str, tuple[int, ...]] | None = None,
    checkout_mix: str = "auto",
    rotation: int = 0,
    allows_pharmacy: bool = True,
) -> Layout:
    """Compile a fixed floor + policy (+ optional pins and endcap picks) into a Layout."""
    spec = size_spec(size_id)
    fmt = formats()
    fixtures = fmt["fixtures"]
    floor = tuple(floor) if floor else default_floor(size_id)
    facts = facts_for(sku_ids) if sku_ids is not None else shipped_core_facts()
    by_dept: dict[str, list[SkuFact]] = {}
    for f in facts:
        by_dept.setdefault(f.dept, []).append(f)
    fact_by_idx = {f.idx: f for f in facts}
    pin_set = [p for p in dict.fromkeys(int(x) for x in pins) if p in fact_by_idx][:MAX_PINS_PER_STORE]
    facing_targets = {int(k): max(1, min(FACE_CAP, int(v))) for k, v in (facing_targets or {}).items() if int(k) in fact_by_idx}
    notes: list[str] = []

    # 1) bays in walk order, inline only for now (endcaps added per aisle)
    inline: list[dict] = []  # mutable bay drafts
    order = 0

    def add_bay(key, aisle, kind, zone, fixture, dept, exposure):
        nonlocal order
        fx = fixtures[fixture]
        draft = {
            "key": key, "aisle": aisle, "kind": kind, "zone": zone, "fixture": fixture, "dept": dept,
            "order": order, "exposure": round(exposure, 4),
            "tiers": [[t, fx["width"], []] for t in fx["tiers"]],
        }
        order += 1
        inline.append(draft)
        return draft

    fixed = {row["id"]: row for row in spec["fixed"]}
    for fid in ("AA", "SN", "PR", "MD", "FZ"):
        row = fixed[fid]
        for b in range(int(row["bays"])):
            add_bay(f"{fid}.{b + 1}", fid, row["kind"], row["zone"], row["fixture"], row["dept"], zone_exposure(row["zone"]))
    counts = {"center": 0, "gm": 0}
    defaults = {"center": len(spec["center"]["default"]), "gm": len(spec["gm"]["default"])}
    kinds = fmt["aisle_kinds"]
    for aisle in floor:
        i = counts[aisle.kind]
        counts[aisle.kind] += 1
        factor = _position_factor(i, defaults[aisle.kind])
        kind = kinds[aisle.kind]
        add_bay(f"{aisle.uid}.F", aisle.uid, "endcap", "front_endcap", "endcap", aisle.dept, zone_exposure("front_endcap") * factor)
        for b in range(int(spec[aisle.kind]["bays"])):
            add_bay(f"{aisle.uid}.{b + 1}", aisle.uid, aisle.kind, kind["zone"], kind["fixture"], aisle.dept, zone_exposure(kind["zone"]) * factor)
        add_bay(f"{aisle.uid}.B", aisle.uid, "endcap", "back_endcap", "endcap", aisle.dept, zone_exposure("back_endcap") * factor)
    rx = fixed["RX"]
    rx_dept = "pharmacy" if allows_pharmacy else "household"
    if not allows_pharmacy:
        notes.append("This lease keeps the pharmacy counter closed; its bays carry household.")
    for b in range(int(rx["bays"])):
        add_bay(f"RX.{b + 1}", "RX", rx["kind"], rx["zone"], rx["fixture"], rx_dept, zone_exposure(rx["zone"]))
    ck = fixed["CK"]
    add_bay("CK.1", "CK", "checkout", "checkout", ck["fixture"], "*", zone_exposure("checkout"))

    # 2) inline facings per department
    taken_pins_per_dept: dict[str, int] = {}
    left_out: list[int] = []
    dept_bays: dict[str, list[dict]] = {}
    for draft in inline:
        if draft["kind"] in ("center", "gm", "perimeter", "seasonal", "pharmacy"):
            dept_bays.setdefault(draft["dept"], []).append(draft)
    shown = 0
    for dept in sorted(by_dept):
        items = by_dept[dept]
        bays = dept_bays.get(dept, [])
        if not allows_pharmacy and dept == "pharmacy":
            left_out.extend(f.idx for f in items)
            continue
        cap = sum(t[1] for b in bays for t in b["tiers"])
        dept_pins = []
        for p in pin_set:
            if fact_by_idx[p].dept == dept and taken_pins_per_dept.get(dept, 0) < MAX_PINS_PER_DEPT:
                dept_pins.append(p)
                taken_pins_per_dept[dept] = taken_pins_per_dept.get(dept, 0) + 1
        if cap <= 0:
            left_out.extend(f.idx for f in items)
            continue
        keep = list(items)
        if len(keep) > cap:
            ranked = sorted(keep, key=lambda f: (0 if f.idx in dept_pins else 1, -f.hint, f.idx))
            kept = {f.idx for f in ranked[:cap]}
            left_out.extend(f.idx for f in items if f.idx not in kept)
            keep = [f for f in items if f.idx in kept]
        base = [PIN_FACINGS if f.idx in dept_pins else 1 for f in keep]
        while sum(base) > cap:  # tiny fixtures: shrink pins back toward 1
            j = max(range(len(base)), key=lambda k: (base[k], -k))
            base[j] -= 1
        rule = policy.facings_rule
        if rule == "margin":
            weights = [max(0.01, (f.price - f.cost) / max(1, f.price)) * f.hint for f in keep]
        elif rule == "even":
            weights = [1.0 for _ in keep]
        else:
            weights = [f.hint for f in keep]
        facings = _largest_remainder(cap, weights, base, FACE_CAP)
        # Manual targets are compact player intent, not saved shelf geometry. Honor them
        # deterministically, then take/give space from the least important unpinned SKUs.
        index_of = {f.idx: i for i, f in enumerate(keep)}
        for sku in sorted(facing_targets):
            i = index_of.get(sku)
            if i is None:
                continue
            target = min(FACE_CAP, facing_targets[sku])
            delta = target - facings[i]
            if delta > 0:
                donors = sorted(
                    (j for j, f in enumerate(keep) if j != i and f.idx not in dept_pins and facings[j] > 1),
                    key=lambda j: (weights[j], keep[j].idx),
                )
                for j in donors:
                    take = min(delta, facings[j] - 1)
                    facings[j] -= take
                    facings[i] += take
                    delta -= take
                    if delta <= 0:
                        break
            elif delta < 0:
                give = -delta
                facings[i] -= give
                receivers = sorted(
                    (j for j in range(len(keep)) if j != i and facings[j] < FACE_CAP),
                    key=lambda j: (-weights[j], keep[j].idx),
                )
                for j in receivers:
                    add = min(give, FACE_CAP - facings[j])
                    facings[j] += add
                    give -= add
                    if give <= 0:
                        break
        shown += len(keep)
        # placement: pins take eye (then hand/well) tiers first, the rest follow the policy order
        slots = [(b, t) for b in bays for t in b["tiers"]]
        prime = [s for s in slots if s[1][0] == "eye"] + [s for s in slots if s[1][0] in ("hand", "well")]
        prime_ids = {id(s[1]) for s in prime}
        rest_slots = prime + [s for s in slots if id(s[1]) not in prime_ids]
        place = policy.place if (not policy.focus_dept or policy.focus_dept == dept or policy.place == "price") else "family"
        if place == "velocity":
            rest = sorted([f for f in keep if f.idx not in dept_pins], key=lambda f: (-f.hint, f.idx))
            order_slots = rest_slots
        elif place == "price":
            rest = sorted([f for f in keep if f.idx not in dept_pins], key=lambda f: (f.price, f.idx))
            order_slots = rest_slots
        else:
            rest = [f for f in keep if f.idx not in dept_pins]
            order_slots = slots
        fmap = {f.idx: n for f, n in zip(keep, facings)}

        def put(sku: int, n: int, slot_list: list) -> None:
            for _b, tier in slot_list:
                if n <= 0:
                    return
                room = tier[1] - sum(c for _s, c in tier[2])
                if room <= 0:
                    continue
                c = min(room, n)
                tier[2].append((sku, c))
                n -= c

        for p in dept_pins:
            put(p, fmap[p], prime + slots)
        for f in rest:
            put(f.idx, fmap[f.idx], order_slots)
    total_families = len(facts) - (len([f for f in facts if f.dept == "pharmacy"]) if not allows_pharmacy else 0)
    if left_out and size_id.startswith("compact"):
        notes.append(f"Compact: {shown} of {total_families} families on the shelf.")

    # 3) features: endcaps, action alley, checkout
    endcap_fill = endcap_fill or {}
    alley_fill = alley_fill or {}
    focus = policy.focus_dept
    focus_left = {"center": 2, "gm": 2}
    aisle_kind = {a.uid: a.kind for a in floor}
    ranked_cache: dict[tuple[str, str], list[SkuFact]] = {}

    def ranked_for(dept: str, mode: str) -> list[SkuFact]:
        key = (dept, mode)
        if key not in ranked_cache:
            ranked_cache[key] = _rank(by_dept.get(dept, []), "traffic" if mode == "seasonal" else mode)
        return ranked_cache[key]

    on_endcap: set[int] = set()
    for draft in inline:
        if draft["kind"] != "endcap":
            continue
        tiers = draft["tiers"]
        picked = endcap_fill.get(draft["key"])
        if picked is not None:
            skus = [s for s in picked if s in fact_by_idx][:MAX_ENDCAP_SKUS]
        else:
            dept = draft["dept"]
            front = draft["key"].endswith(".F")
            mode = policy.endcap_mode
            if front and mode == "seasonal":
                dept = "seasonal"
            elif front and focus and focus_left.get(aisle_kind.get(draft["aisle"], "center"), 0) > 0 and by_dept.get(focus):
                focus_left[aisle_kind.get(draft["aisle"], "center")] -= 1
                dept = focus
            ranked = ranked_for(dept, mode)
            offset = (rotation * 3 + (0 if front else 3)) % max(1, len(ranked))
            skus = _pick_rotating(ranked, MAX_ENDCAP_SKUS, offset, on_endcap)
        for j, sku in enumerate(skus[: len(tiers)]):
            tiers[j][2].append((sku, tiers[j][1]))
            on_endcap.add(sku)
    alley_ranked = None
    for draft in inline:
        if draft["kind"] != "action_alley":
            continue
        tier = draft["tiers"][0]
        picked = alley_fill.get(draft["key"])
        if picked is not None:
            skus = [s for s in picked if s in fact_by_idx][:3]
        else:
            if alley_ranked is None:
                dept = focus or ("seasonal" if policy.endcap_mode in ("seasonal", "traffic") else "grocery")
                pool = list(by_dept.get(dept, []))
                if dept != "seasonal":
                    pool += [f for f in by_dept.get("seasonal", [])]
                alley_ranked = _rank(pool, "promo" if policy.endcap_mode == "promo" else "traffic")
            n = int(draft["key"].split(".")[1]) - 1
            skus = _pick_rotating(alley_ranked, 3, (rotation * 3 + n * 3) % max(1, len(alley_ranked)), on_endcap)
        per = max(1, tier[1] // max(1, len(skus))) if skus else 0
        for sku in skus:
            tier[2].append((sku, per))
            on_endcap.add(sku)
    mixes = formats()["checkout_mixes"]
    mix = checkout_mix if checkout_mix in mixes else ("seasonal" if policy.endcap_mode == "seasonal" else "candy_drinks")
    pos = sku_pos()
    ck_skus = [pos[s] for s in mixes[mix] if s in pos and pos[s] in fact_by_idx]
    ck = next(d for d in inline if d["kind"] == "checkout")
    i = 0
    for tier in ck["tiers"]:
        while sum(c for _s, c in tier[2]) < tier[1] and i < len(ck_skus):
            tier[2].append((ck_skus[i], 1))
            i += 1

    bays = tuple(
        Bay(
            key=d["key"], aisle=d["aisle"], kind=d["kind"], zone=d["zone"], fixture=d["fixture"], dept=d["dept"],
            order=d["order"], exposure=d["exposure"],
            tiers=tuple((t[0], tuple(t[2])) for t in d["tiers"]),
        )
        for d in inline
    )
    return Layout(size_id, floor, bays, tuple(sorted(left_out)), tuple(notes), rotation)


# ---------------------------------------------------------------- visibility


def face(f: int) -> float:
    return (min(max(f, 1), FACE_CAP) / FACE_REF) ** FACE_EXP


@lru_cache(maxsize=None)
def _pair_map() -> dict[int, tuple[int, ...]]:
    pos = sku_pos()
    out: dict[int, list[int]] = {}
    for a, b in pairs():
        if a in pos and b in pos:
            out.setdefault(pos[a], []).append(pos[b])
            out.setdefault(pos[b], []).append(pos[a])
    return {k: tuple(v) for k, v in out.items()}


def visibility(layout: Layout, stale: dict[str, float] | None = None, part: str = "all") -> dict[int, float]:
    """vis(sku) = inline position x facings, plus feature slots (endcap/alley/checkout) and pairs.

    ``stale`` maps endcap bay key -> staleness factor in 0.3..1 (missing = fresh).
    ``part`` = "all" | "position" (inline, facings ignored) | "facings" (inline, position ignored)
    | "feature" (endcap/alley/checkout slots only); used by score_layout.
    """
    use_pos = part in ("all", "position", "feature")
    use_face = part in ("all", "facings", "feature")
    pos_mult = formats()["pos"]
    stale = stale or {}
    slots = layout.sku_slots()
    bays = layout.bays
    out: dict[int, float] = {}
    inline_orders: dict[int, list[int]] = {}
    for sku, rows in slots.items():
        total_f = 0
        weighted = 0.0
        feature = 0.0
        for bi, tier, f in rows:
            bay = bays[bi]
            if bay.is_feature:
                lift = 1.0
                if bay.kind == "endcap":
                    lift = 1.0 + END_LIFT * END_KEEP * stale.get(bay.key, 1.0)
                feature += bay.exposure * pos_mult[tier] * face(f) * lift
            else:
                total_f += f
                weighted += f * bay.exposure * (pos_mult[tier] if use_pos else 1.0)
                inline_orders.setdefault(sku, []).append(bay.order)
        vis = (weighted / total_f) * (face(total_f) if use_face else 1.0) if total_f else 0.0
        if part == "feature":
            out[sku] = FEATURE_WEIGHT * feature
        elif part == "all":
            out[sku] = vis + FEATURE_WEIGHT * feature
        else:
            out[sku] = vis
    if part != "all":
        return out
    pm = _pair_map()
    for sku in list(out):
        partners = pm.get(sku)
        if not partners or sku not in inline_orders:
            continue
        mine = inline_orders[sku]
        for other in partners:
            theirs = inline_orders.get(other)
            if theirs and any(abs(a - b) <= 2 for a in mine for b in theirs):
                out[sku] *= PAIR_BONUS
                break
    return out


# ---------------------------------------------------------------- scoring


@dataclass(frozen=True)
class ShelfScore:
    quality: int
    selection: int
    oos_rate_bp: int
    endcap_fresh: int
    dept_space: dict[str, int] = field(default_factory=dict)
    parts: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class ScoreCtx:
    """What score_layout needs besides the layout. Player and rivals fill the same fields."""

    velocity: dict[int, float]  # sku -> demand weight (actual sellers); missing -> 0
    neutral: Layout  # the default template on the default floor for this size
    stale: dict[str, float] = field(default_factory=dict)
    neutral_stale: dict[str, float] = field(default_factory=dict)
    in_stock: frozenset[int] | None = None
    base_shares: dict[str, int] = field(default_factory=dict)
    compliance: int = 50
    price: dict[int, float] | None = None  # sku -> shelf price; scores then follow dollars


def _dept_of_idx() -> dict[int, str]:
    return {f.idx: f.dept for f in shipped_facts()}


@lru_cache(maxsize=None)
def impulse_shares() -> dict[int, float]:
    fmt = formats()
    dept_share = fmt["impulse_share"]
    snack = set(fmt["impulse_skus"])
    snack_share = float(fmt["impulse_sku_share"])
    return {f.idx: (snack_share if f.id in snack else float(dept_share.get(f.dept, 0.25))) for f in shipped_facts()}


MIX_MAX = 0.03  # shelf position moves a department's dollars-per-unit by at most 3%
OFF_SHELF = 0.05  # a family with no facings sells only by special order


def shelf_effect_full(vis: dict[int, float], vis_n: dict[int, float], velocity: dict[int, float],
                      clamp: bool = True, price: dict[int, float] | None = None,
                      ) -> tuple[dict[int, float], dict[str, float], dict[str, float]]:
    """(per-SKU pick multiplier, per-department UNIT lift, per-department SALES lift).

    shelf(sku) = (1 - impulse) + impulse x vis / vis_neutral(sku); the average store is 1.0
    for every SKU, so 'feature on, default layout' sells exactly like 'feature off'.

    Moving pick weight between SKUs also moves the department's dollars per unit (eye level on a
    pricier item sells more dollars). With ``price`` the clamp is applied to the department's
    sales ratio R = sum(v p s) / sum(v p); the unit lift handed to the engine is
    clamp(R) / M where M = (R / U) is the price-mix shift, so dollars land exactly on clamp(R).
    """
    imp = impulse_shares()
    dept = _dept_of_idx()
    sku: dict[int, float] = {}
    cu: dict[str, float] = {}
    du: dict[str, float] = {}
    cr: dict[str, float] = {}
    dr: dict[str, float] = {}
    for i, v in velocity.items():
        x = vis.get(i, 0.0)
        xn = vis_n.get(i, 0.0)
        share = imp.get(i, 0.25)
        if not x and xn:
            s = OFF_SHELF
        elif not xn:
            s = 1.0 if not x else 1.0 + share * 0.25
        else:
            s = (1.0 - share) + share * (x / xn)
        sku[i] = s
        d = dept.get(i, "")
        p = float(price.get(i, 1.0)) if price else 1.0
        cu[d] = cu.get(d, 0.0) + v * s
        du[d] = du.get(d, 0.0) + v
        cr[d] = cr.get(d, 0.0) + v * p * s
        dr[d] = dr.get(d, 0.0) + v * p
    unit: dict[str, float] = {}
    rev: dict[str, float] = {}
    damp: dict[str, tuple[float, float]] = {}
    for d in cu:
        u = cu[d] / du[d] if du.get(d) else 1.0
        r = cr[d] / dr[d] if dr.get(d) else u
        mix = (r / u) if u > 0 else 1.0
        k = 1.0
        if abs(mix - 1.0) > MIX_MAX:  # trade-up/down from shelf position alone is capped
            k = MIX_MAX / abs(mix - 1.0)
            mix = 1.0 + k * (mix - 1.0)
        damp[d] = (u, k)
        r = u * mix
        rc = max(LIFT_MIN, min(LIFT_MAX, r)) if clamp else r
        unit[d] = rc / mix if mix > 0 else rc
        rev[d] = rc
    for i, s in sku.items():  # s' = u + k (s - u) keeps the department's units and ranking
        u, k = damp.get(dept.get(i, ""), (1.0, 1.0))
        if k < 1.0:
            sku[i] = u + k * (s - u)
    return sku, unit, rev


def shelf_effect(vis: dict[int, float], vis_n: dict[int, float], velocity: dict[int, float],
                 clamp: bool = True, price: dict[int, float] | None = None,
                 ) -> tuple[dict[int, float], dict[str, float]]:
    """Per-SKU multiplier and per-department unit lift against the average store."""
    sku, unit, _rev = shelf_effect_full(vis, vis_n, velocity, clamp, price)
    return sku, unit


def store_ratio(lift: dict[str, float], shares: dict[str, int] | None = None) -> float:
    """Sales-share-weighted mean of department lifts (1.0 = the average store)."""
    if not lift:
        return 1.0
    if shares:
        tot = sum(max(0, int(shares.get(d, 0))) for d in lift) or 1
        return sum(lift[d] * max(0, int(shares.get(d, 0))) for d in lift) / tot
    return sum(lift.values()) / len(lift)


def _band(ratio: float, k: float = 250.0) -> int:
    return int(max(0, min(100, round(50 + k * (ratio - 1.0)))))


def dept_positions(layout: Layout) -> dict[str, int]:
    out: dict[str, int] = {}
    for bay in layout.bays:
        if bay.is_feature:
            continue
        n = sum(f for _t, items in bay.tiers for _s, f in items)
        out[bay.dept] = out.get(bay.dept, 0) + n
    return out


def derived_shares(layout: Layout, neutral: Layout, base: dict[str, int]) -> dict[str, int]:
    """Base department shares scaled by space vs the default floor, renormalized to 100."""
    cur, neu = dept_positions(layout), dept_positions(neutral)
    keys = list(base)
    raw = {}
    for k in keys:
        b = int(base.get(k, 0))
        if b <= 0:
            raw[k] = 0.0
            continue
        n = neu.get(k, 0)
        raw[k] = b * (cur.get(k, 0) / n if n else 1.0)
    total = sum(raw.values()) or 1.0
    scaled = {k: raw[k] * 100.0 / total for k in keys}
    out = {k: int(scaled[k]) for k in keys}
    left = 100 - sum(out.values())
    for k in sorted(keys, key=lambda k: (-(scaled[k] - out[k]), keys.index(k))):
        if left <= 0:
            break
        if raw[k] > 0:
            out[k] += 1
            left -= 1
    return out


def _pair_count(lay: Layout) -> int:
    pm = _pair_map()
    orders: dict[int, list[int]] = {}
    for bay in lay.bays:
        if bay.is_feature:
            continue
        for _t, items in bay.tiers:
            for s_, _f in items:
                orders.setdefault(s_, []).append(bay.order)
    n = 0
    for a, partners in pm.items():
        if a in orders and any(b in orders and any(abs(x - y) <= 2 for x in orders[a] for y in orders[b]) for b in partners):
            n += 1
    return n


def score_layout(layout: Layout, ctx: ScoreCtx) -> ShelfScore:
    """Quality 0-100 where the average store (default template, default floor) = 50.

    quality = 50 + 500 x (sales-weighted shelf lift - 1), from the same math the sales use.
    ``parts`` carries the plan's sub-scores (position, facings, endcaps, pairs, tidy,
    compliance) for the screen; ``parts["blend"]`` is their 40/20/15/10/10/5 mix.
    """
    vel = ctx.velocity
    shares = ctx.base_shares or None
    nst = ctx.neutral_stale or ctx.stale

    def ratio(part: str) -> float:
        a = visibility(layout, ctx.stale, part)
        b = visibility(ctx.neutral, nst, part)
        if part == "feature":  # most SKUs have no feature slot: compare demand x impulse weighted totals
            imp = impulse_shares()
            num = sum(v * imp.get(i, 0.25) * a.get(i, 0.0) for i, v in vel.items())
            den = sum(v * imp.get(i, 0.25) * b.get(i, 0.0) for i, v in vel.items())
            return num / den if den else 1.0
        _s, _u, lift = shelf_effect_full(a, b, vel, clamp=False, price=ctx.price)
        return store_ratio(lift, shares)

    comps = {
        "position": _band(ratio("position"), 1500.0),
        "facings": _band(ratio("facings"), 3000.0),
        "endcaps": _band(ratio("feature"), 600.0),
        "pairs": int(max(0, min(100, 50 + 4 * (_pair_count(layout) - _pair_count(ctx.neutral))))),
        "tidy": 50,
        "compliance": int(max(0, min(100, ctx.compliance))),
    }
    # The headline score follows the same clamped department lifts the sales use, so it
    # always moves with expected sales (+8% -> 90, -10% -> 0). The plan's weighted parts
    # (40/20/15/10/10/5) are kept in ``parts`` to explain it on screen.
    _s, _u, lift_all = shelf_effect_full(visibility(layout, ctx.stale), visibility(ctx.neutral, nst), vel, price=ctx.price)
    total = store_ratio(lift_all, shares)
    quality = round(50 + 500 * (total - 1.0))
    comps["blend"] = int(round(
        0.40 * comps["position"] + 0.20 * comps["facings"] + 0.15 * comps["endcaps"]
        + 0.10 * comps["pairs"] + 0.10 * comps["tidy"] + 0.05 * comps["compliance"]
    ))
    on_shelf = set(layout.sku_slots())
    vtot = sum(vel.values()) or 1.0
    stocked = ctx.in_stock if ctx.in_stock is not None else frozenset(on_shelf)
    cov = sum(v for s_, v in vel.items() if s_ in on_shelf and s_ in stocked) / vtot
    neu_on = set(ctx.neutral.sku_slots())
    cov_n = sum(v for s_, v in vel.items() if s_ in neu_on) / vtot
    selection = int(max(0, min(100, round(50 + 35 * (cov - cov_n) / max(0.05, 1.0 - cov_n)))))
    oos = 0
    if ctx.in_stock is not None and on_shelf:
        oos = int(round(10000 * sum(1 for s_ in on_shelf if s_ not in ctx.in_stock) / len(on_shelf)))
    caps = [b for b in layout.bays if b.kind == "endcap"]
    fresh = int(round(100 * sum(ctx.stale.get(b.key, 1.0) for b in caps) / max(1, len(caps))))
    shares_out = derived_shares(layout, ctx.neutral, ctx.base_shares) if ctx.base_shares else {}
    return ShelfScore(int(max(0, min(100, quality))), selection, oos, fresh, shares_out, comps)


# ---------------------------------------------------------------- resets and alerts


@dataclass(frozen=True)
class ResetCost:
    changed: int
    labor: int
    dip_days: int
    bays: frozenset[str]
    affected: dict[str, int]  # dept -> permille of that dept's inline facings in changed bays


def reset_cost(old: Layout | None, new: Layout, wage_floor_weekly: int) -> ResetCost:
    """0.25 labor hours per changed facing at the door's wage floor; changed bays dip x0.88
    for 2 + ceil(changed/60) days, capped at 7. Same for player and rivals."""
    if old is None:
        return ResetCost(0, 0, 0, frozenset(), {})
    a, b = old.facing_map(), new.facing_map()
    added = removed = 0
    bays: set[str] = set()
    for key in set(a) | set(b):
        d = b.get(key, 0) - a.get(key, 0)
        if d > 0:
            added += d
        elif d < 0:
            removed -= d
        if d:
            bays.add(key[0])
    changed = max(added, removed)
    if changed <= 0:
        return ResetCost(0, 0, 0, frozenset(), {})
    hourly = max(1.0, wage_floor_weekly / 40.0)
    # Door wage floors are already supercenter-scaled (x SIZE_MULT), so no extra scale here.
    labor = int(round(changed * RESET_HOURS_PER_FACING * hourly))
    dip = min(7, 2 + math.ceil(changed / 60))
    per_dept: dict[str, int] = {}
    hit: dict[str, int] = {}
    for bay in list(old.bays) + list(new.bays):
        if bay.dept == "*":
            continue
        n = sum(f for _t, items in bay.tiers for _s, f in items)
        per_dept[bay.dept] = per_dept.get(bay.dept, 0) + n
        if bay.key in bays:
            hit[bay.dept] = hit.get(bay.dept, 0) + n
    affected = {d: min(1000, int(round(1000 * hit[d] / per_dept[d]))) for d in sorted(hit) if per_dept.get(d)}
    return ResetCost(changed, labor, dip, frozenset(bays), affected)


def validate_layout(layout: Layout, *, pins: Iterable[int] = (), velocity: dict[int, float] | None = None,
                    stale_weeks: dict[str, int] | None = None, promo_category: str = "",
                    allows_pharmacy: bool = True) -> list[str]:
    fmt = formats()
    fixtures = fmt["fixtures"]
    facts = {f.idx: f for f in shipped_facts()}
    out: list[str] = list(layout.notes)
    misfit = 0
    for sku, rows in layout.sku_slots().items():
        inline = [(layout.bays[bi], f) for bi, _t, f in rows if not layout.bays[bi].is_feature]
        if not inline:
            continue
        units = sum(f * fixtures[b.fixture]["depth_units"] for b, f in inline)
        if units < facts[sku].case_size:
            misfit += 1
    if misfit:
        out.append(f"{misfit} families won't fit a full case on their facings.")
    stale_weeks = stale_weeks or {}
    stale = sorted(k for k, w in stale_weeks.items() if w >= 6)
    if stale:
        out.append(f"{len(stale)} endcaps unchanged for 6+ weeks (stale): {', '.join(stale[:4])}.")
    if promo_category:
        on_feature = any(
            facts[s].dept == promo_category
            for b in layout.bays if b.kind in ("endcap", "action_alley")
            for _t, items in b.tiers for s, _f in items
        )
        if not on_feature:
            out.append(f"The running {promo_category.replace('_', ' ')} promo isn't on an endcap or the action alley.")
    if velocity:
        for p in pins:
            f = facts.get(p)
            if f is None:
                continue
            peers = sorted((velocity.get(x.idx, 0.0) for x in facts.values() if x.dept == f.dept), reverse=True)
            if peers and velocity.get(p, 0.0) < peers[len(peers) // 2]:
                out.append(f"Eye-level priority on a slow seller: {f.id}.")
    return out


def check_pins(pins: Iterable[int]) -> str:
    """'' when the priority list is legal, else the message to show."""
    facts = {f.idx: f for f in shipped_facts()}
    seen: dict[str, int] = {}
    pins = list(dict.fromkeys(pins))
    if len(pins) > MAX_PINS_PER_STORE:
        return f"A store takes at most {MAX_PINS_PER_STORE} eye-level priorities."
    for p in pins:
        f = facts.get(p)
        if f is None:
            return "That product isn't in the catalog."
        seen[f.dept] = seen.get(f.dept, 0) + 1
        if seen[f.dept] > MAX_PINS_PER_DEPT:
            return f"{f.dept.replace('_', ' ').title()} already has {MAX_PINS_PER_DEPT} eye-level priorities."
    return ""


__all__ = [
    "DEFAULT_SIZE", "LayoutPolicy", "TEMPLATES", "TEMPLATE_ORDER", "policy_for", "auto_planogram",
    "visibility", "score_layout", "ScoreCtx", "ShelfScore", "reset_cost", "ResetCost", "validate_layout",
    "check_pins", "derived_shares", "dept_positions", "shipped_facts", "facts_for", "face",
]
