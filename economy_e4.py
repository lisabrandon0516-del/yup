"""E4: attribution desk contract, multi-week card replay, tax fold, difficulty grace.

Sales-tax drift (104) scales the existing sales-tax path. State withholding
climate (106) scales employee state withholding (Houston, Seattle, and Las
Vegas stay at 0 bps). Off is an identity. Stern keeps E3 sigma, event p,
caps, and zero sales/bill grace.
"""

from __future__ import annotations

from typing import Any

from open_late.departments import DEPARTMENT_IDS
from open_late.models import GameState

PNL_LINES = ("sales", "cogs", "labor", "rent", "freight", "shrink", "card_fees", "pos_fees")
HISTORY_LIMIT = 20

# Stern is unchanged from E3. Calm and Standard get a favorable sales bias
# and a grace on daily visits (skipped during visit-cutting events) plus a
# partial forgive on Sunday bill *increases*.
VISIT_BIAS = {"off": 0, "calm": 0, "standard": 0, "stern": 0}
SALES_GRACE = {"off": 0.0, "calm": 0.0, "standard": 0.0, "stern": 0.0}
BILL_GRACE = {"off": 0.0, "calm": 0.0, "standard": 0.0, "stern": 0.0}
BILL_DISCOUNT = {"off": 0.0, "calm": 0.0, "standard": 0.0, "stern": 0.0}

ZERO_WITHHOLDING_CITIES = frozenset({"houston", "seattle", "las_vegas"})


def sales_tax_index(state: GameState, store_id: str | None = None) -> int:
    """104, identity 100 when off or missing."""
    from open_late.economy import CITIES, _value, city_of, economy_difficulty, store_ids_for

    if economy_difficulty(state) == "off":
        return 100
    if store_id in CITIES:
        city = store_id
    elif store_id:
        city = city_of(state, store_id)
    else:
        home = store_ids_for(state)[0] if store_ids_for(state) else "evansville"
        city = city_of(state, home)
    return int(_value(state, 104, city) or 100)


def withholding_index(state: GameState, city_id: str | None = None) -> int:
    """106. Cities with no state tax stay at a no-op 100; the 0 bps rate is what matters."""
    from open_late.economy import _value, economy_difficulty

    if economy_difficulty(state) == "off":
        return 100
    city = city_id or "evansville"
    if city in ZERO_WITHHOLDING_CITIES:
        return 100
    return int(_value(state, 106, city) or 100)


def scale_sales_tax(state: GameState, amount: int, store_id: str | None = None) -> int:
    """Scale a posted-rate tax dollar amount by 104. Identity at 100 / off."""
    from open_late.economy import economy_difficulty

    if amount <= 0 or state is None or economy_difficulty(state) == "off":
        return amount
    index = sales_tax_index(state, store_id)
    if index == 100:
        return amount
    return int(round(amount * index / 100.0))


def scale_bps(state: GameState, bps: int, store_id: str | None = None) -> int:
    from open_late.economy import economy_difficulty

    if bps <= 0 or state is None or economy_difficulty(state) == "off":
        return bps
    index = sales_tax_index(state, store_id)
    if index == 100:
        return bps
    return int(round(bps * index / 100.0))


def scale_state_withholding(state: GameState, rate: int, city_id: str | None = None) -> int:
    from open_late.economy import economy_difficulty

    if rate <= 0 or state is None or economy_difficulty(state) == "off":
        return rate
    city = city_id or "evansville"
    if city in ZERO_WITHHOLDING_CITIES:
        return rate
    index = withholding_index(state, city)
    if index == 100:
        return rate
    return int(round(rate * index / 100.0))


def visit_bias(state: GameState) -> int:
    from open_late.economy import economy_difficulty

    return int(VISIT_BIAS.get(economy_difficulty(state), 0) or 0)


def sales_grace(state: GameState) -> float:
    from open_late.economy import economy_difficulty

    return float(SALES_GRACE.get(economy_difficulty(state), 0.0) or 0.0)


def apply_sales_grace(state: GameState, store_id: str, base: float, *, cut: bool) -> float:
    """E5: hidden sales grace is removed. Always identity."""
    if cut or base <= 0:
        return base
    grace = sales_grace(state)
    bias = visit_bias(state) / 100.0
    if not grace and not bias:
        return base
    return base * (1.0 + grace) * (1.0 + bias)


def apply_bill_grace(state: GameState, base: int, adjusted: int) -> int:
    """E5: hidden bill grace and discount are removed. Always identity."""
    from open_late.economy import economy_difficulty

    difficulty = economy_difficulty(state)
    grace = float(BILL_GRACE.get(difficulty, 0.0) or 0.0)
    if grace and adjusted > base:
        adjusted = base + int(round((adjusted - base) * (1.0 - grace)))
    discount = float(BILL_DISCOUNT.get(difficulty, 0.0) or 0.0)
    if discount:
        adjusted = int(round(adjusted * (1.0 - discount)))
    return adjusted


def gauge_band(value: int, kind: str | None = None) -> str:
    """Desk color contract: ±10 watch, ±20 alert, else steady. State factors stay steady."""
    if kind == "state":
        return "steady"
    gap = abs(int(value) - 100)
    if gap >= 20:
        return "alert"
    if gap >= 10:
        return "watch"
    return "steady"


def snapshot_card(state: GameState) -> dict:
    from open_late.economy_e3 import card_fee_mult, labor_mult, rent_mult
    from open_late.economy import freight_mult, store_ids_for

    card = {
        "visits": {sid: int((state.economy.visits or {}).get(sid, 100) or 100) for sid in store_ids_for(state)},
        "demand": {
            sid: {dept: int(((state.economy.demand or {}).get(sid) or {}).get(dept, 100) or 100) for dept in DEPARTMENT_IDS}
            for sid in store_ids_for(state)
        },
        "cost": {
            sid: {dept: int(((state.economy.cost or {}).get(sid) or {}).get(dept, 100) or 100) for dept in DEPARTMENT_IDS}
            for sid in store_ids_for(state)
        },
        "freight": {sid: int((state.economy.freight or {}).get(sid, 100) or 100) for sid in store_ids_for(state)},
        "labor": {},
        "rent": {},
        "card_fees": {},
    }
    for sid in store_ids_for(state):
        card["labor"][sid] = int(round(labor_mult(state, sid) * 100))
        card["rent"][sid] = int(round(rent_mult(state, sid) * 100))
        card["card_fees"][sid] = int(round(card_fee_mult(state, sid) * 100))
        card["freight"][sid] = int(round(freight_mult(state, sid) * 100))
    return card


def record_history_row(state: GameState, week: int, *, opening: bool = False) -> dict:
    """Attach the just-baked card (applies to the next week) and the week-just-ended P&L."""
    from open_late.economy import CITIES, _value, store_ids_for, FACTORS, week_id
    from open_late.hq import store_pnl

    applies_to = 0 if opening else int(week) + 1
    city_values: dict[str, dict[str, int]] = {}
    for city in CITIES:
        row: dict[str, int] = {}
        for fid, info in FACTORS.items():
            if info["scope"] == "city":
                row[str(fid)] = int(_value(state, fid, city))
        city_values[city] = row
    store_values: dict[str, dict[str, int]] = {}
    for sid in store_ids_for(state):
        row = {}
        for fid, info in FACTORS.items():
            if info["scope"] == "store":
                row[str(fid)] = int(_value(state, fid, sid))
        store_values[sid] = row
    pnl = {}
    if not opening:
        for sid in store_ids_for(state):
            pnl[sid] = store_pnl(state, sid, days=7)
    return {
        "week_id": int(week),
        "applies_to": applies_to,
        "card": snapshot_card(state),
        "city_values": city_values,
        "store_values": store_values,
        "pnl": pnl,
    }


def enrich_history(state: GameState, week: int, row: dict, *, opening: bool = False) -> dict:
    extra = record_history_row(state, week, opening=opening)
    row.update({k: v for k, v in extra.items() if k != "week_id" or "week_id" not in row})
    row["week_id"] = int(week) if not opening else int(row.get("week_id", week))
    if opening:
        row["week_id"] = -1
        row["applies_to"] = week_id_safe(state)
    return row


def week_id_safe(state: GameState) -> int:
    from open_late.economy import week_id

    return week_id(state.day)


def trim_history(history: list) -> list:
    if len(history) > HISTORY_LIMIT:
        return history[-HISTORY_LIMIT:]
    return history


def card_for_week(state: GameState, applies_to: int) -> dict | None:
    for row in reversed(state.economy.history or []):
        if int(row.get("applies_to", -999)) == int(applies_to) and row.get("card"):
            return row["card"]
    # Current baked card applies to the open week (after last Sunday, or week 0 at start).
    from open_late.economy import week_id, is_sunday
    from open_late.text import is_sunday as _is_sun

    current = week_id(state.day)
    if applies_to == current:
        return snapshot_card(state)
    return None


def window_bounds(state: GameState, days: int) -> tuple[int, int]:
    days = max(1, int(days))
    if state.phase in ("evening", "gameover"):
        last = int(state.day)
    else:
        last = int(state.day) - 1
    return last - days + 1, last


def slice_pnl(state: GameState, store_id: str, lo: int, hi: int) -> tuple[dict[str, int], dict[str, int]]:
    totals = {key: 0 for key in PNL_LINES}
    depts: dict[str, int] = {}
    for item in getattr(state, "store_days", []) or []:
        if item.store_id != store_id or int(item.day) < lo or int(item.day) > hi:
            continue
        for key in PNL_LINES:
            totals[key] += int(getattr(item, key) or 0)
        for dept, amount in (item.by_department or {}).items():
            depts[dept] = depts.get(dept, 0) + int(amount)
    return totals, depts


def _mult_from_card(card: dict | None, line: str, store_id: str, dept_sales: dict[str, int] | None = None) -> float:
    if not card:
        return 1.0
    if line == "sales":
        visits = int((card.get("visits") or {}).get(store_id, 100) or 100) / 100.0
        demand = (card.get("demand") or {}).get(store_id) or {}
        if dept_sales and sum(dept_sales.values()) > 0:
            total = sum(dept_sales.values())
            avg = sum(int(demand.get(dept, 100) or 100) / 100.0 * dept_sales.get(dept, 0) for dept in DEPARTMENT_IDS) / total
        else:
            vals = [int(demand.get(dept, 100) or 100) / 100.0 for dept in DEPARTMENT_IDS] or [1.0]
            avg = sum(vals) / len(vals)
        return visits * avg
    if line == "cogs":
        cost = (card.get("cost") or {}).get(store_id) or {}
        if dept_sales and sum(dept_sales.values()) > 0:
            total = sum(dept_sales.values())
            return sum(int(cost.get(dept, 100) or 100) / 100.0 * dept_sales.get(dept, 0) for dept in DEPARTMENT_IDS) / total
        vals = [int(cost.get(dept, 100) or 100) / 100.0 for dept in DEPARTMENT_IDS] or [1.0]
        return sum(vals) / len(vals)
    if line == "freight":
        return int((card.get("freight") or {}).get(store_id, 100) or 100) / 100.0
    if line == "labor":
        return int((card.get("labor") or {}).get(store_id, 100) or 100) / 100.0
    if line == "rent":
        return int((card.get("rent") or {}).get(store_id, 100) or 100) / 100.0
    if line == "card_fees":
        return int((card.get("card_fees") or {}).get(store_id, 100) or 100) / 100.0
    if line == "pos_fees":
        return 1.0
    if line == "shrink":
        return 1.0
    return 1.0


def invert(val: int, m: float) -> int:
    if not val or abs(m - 1.0) < 1e-9:
        return int(val)
    return int(round(val / m))


def build_store_impact(
    state: GameState,
    store_id: str,
    days: int,
    pnl: dict,
    *,
    department: str | None = None,
    category: str | None = None,
    events_only: bool = False,
    min_dollars: int = 0,
) -> dict:
    """Multi-week card replay. Reasons dollars sum to each line's delta (unfiltered)."""
    from open_late.economy import (
        FACTORS,
        _value,
        active_events,
        city_of,
        economy_difficulty,
        week_id,
    )

    def identity() -> dict:
        delta = {key: 0 for key in pnl}
        delta["store_id"] = pnl.get("store_id")
        delta["name"] = pnl.get("name")
        delta["days"] = pnl.get("days")
        return {
            "store_id": store_id,
            "days": int(days),
            "pnl": pnl,
            "neutral_pnl": dict(pnl),
            "delta": delta,
            "reasons": [],
        }

    live_ticks = int(getattr(state.economy, "live_ticks", 0) or 0)
    lo, last = window_bounds(state, days)
    live_from = (int(state.economy.last_week_id) - live_ticks + 1) * 7 + 8 if live_ticks else 10**9
    if economy_difficulty(state) == "off" or last < live_from:
        return identity()

    # Split the window by week and invert each slice with the card that applied to it.
    from open_late.economy import week_id as _wid

    weeks: dict[int, tuple[int, int]] = {}
    for day in range(max(lo, 1), last + 1):
        if day < live_from:
            continue
        wid = _wid(day)
        start, end = weeks.get(wid, (day, day))
        weeks[wid] = (min(start, day), max(end, day))

    if not weeks:
        return identity()

    merged = {key: 0 for key in PNL_LINES}
    merged_neutral = {key: 0 for key in PNL_LINES}
    merged_depts: dict[str, int] = {}
    week_meta: list[tuple[int, dict, dict, dict]] = []
    for wid, (wlo, whi) in sorted(weeks.items()):
        slice_tot, depts = slice_pnl(state, store_id, wlo, whi)
        for dept, amount in depts.items():
            merged_depts[dept] = merged_depts.get(dept, 0) + amount
        card = card_for_week(state, wid)
        maps = {line: _mult_from_card(card, line, store_id, depts) for line in PNL_LINES}
        # Shrink: soft, same as E3, from no-show if we have a value.
        noshow = _value(state, 49, store_id)
        maps["shrink"] = 1.0 + min(0.35, noshow / 100) if slice_tot.get("shrink") else 1.0
        for key in PNL_LINES:
            merged[key] += int(slice_tot.get(key) or 0)
            merged_neutral[key] += invert(int(slice_tot.get(key) or 0), maps[key])
        week_meta.append((wid, slice_tot, maps, depts))

    # Prefer the official store_pnl totals for the window (source of truth).
    # Scale neutrals so inverted dollars match the published pnl line ratios.
    official = {key: int(pnl.get(key) or 0) for key in PNL_LINES}
    for key in PNL_LINES:
        # If our slice missed a day, fall back to official for that line proportionally.
        if merged[key] and official[key] and merged[key] != official[key]:
            # Keep official as pnl; scale neutral by the same ratio.
            scale = official[key] / merged[key]
            merged_neutral[key] = int(round(merged_neutral[key] * scale))
        elif not merged[key]:
            merged_neutral[key] = official[key]

    neutral = dict(pnl)
    for key in PNL_LINES:
        if key in neutral:
            neutral[key] = merged_neutral[key]
    neutral["contribution"] = (
        int(neutral.get("sales") or 0)
        - int(neutral.get("cogs") or 0)
        - int(neutral.get("labor") or 0)
        - int(neutral.get("rent") or 0)
        - int(neutral.get("freight") or 0)
        - int(neutral.get("shrink") or 0)
        - int(neutral.get("card_fees") or 0)
        - int(neutral.get("pos_fees") or 0)
    )
    delta = dict(pnl)
    for key in list(pnl):
        if isinstance(pnl.get(key), int) and key in neutral:
            delta[key] = int(pnl[key]) - int(neutral[key])
    delta["store_id"] = pnl.get("store_id")
    delta["name"] = pnl.get("name")
    delta["days"] = pnl.get("days")

    city = city_of(state, store_id)
    factor_lines = [
        (6, "freight", None),
        (7, "freight", None),
        (65, "freight", None),
        (58, "freight", None),
        (88, "rent", None),
        (89, "rent", None),
        (94, "rent", None),
        (13, "labor", None),
        (50, "labor", None),
        (105, "labor", None),
        (107, "labor", None),
        (97, "card_fees", None),
        (2, "sales", None),
        (5, "sales", None),
        (11, "sales", city),
        (15, "sales", city),
        (23, "sales", None),
        (80, "sales", None),
        (81, "sales", None),
        (84, "sales", city),
        (68, "cogs", "produce"),
        (67, "cogs", "grocery"),
        (4, "cogs", None),
        (101, "cogs", None),
        (104, "sales", city),
        (46, "shrink", None),
        (49, "shrink", None),
        (59, "shrink", None),
    ]
    # Use latest live values; week-scoped values when history has them.
    def value_for(fid: int) -> int:
        place = city if fid in (11, 13, 15, 88, 89, 84, 104, 107) else (store_id if fid in (50, 80, 81, 94, 49) else None)
        return _value(state, fid, place)

    buckets: dict[str, list] = {}
    for fid, line, dept in factor_lines:
        if department and dept and dept != department:
            continue
        if department and line in ("sales", "cogs") and dept and dept != department:
            continue
        info = FACTORS.get(fid) or {}
        if category and info.get("category") != category:
            continue
        if events_only and not active_events(state, factor_id=fid, city_id=city if info.get("scope") == "city" else None):
            # National events still count.
            if not active_events(state, factor_id=fid):
                continue
        val = value_for(fid)
        if fid in (23, 31, 32, 46, 84, 107) and val in (0, 100) and not active_events(state, factor_id=fid, city_id=city):
            if abs(val - (0 if fid in (31, 32, 46, 84, 107) else 100)) < 1:
                continue
        center = 0 if fid in (46, 49, 81, 84, 107) else 100
        weight = abs(int(val) - center)
        if weight < 2:
            continue
        buckets.setdefault(line, []).append((fid, dept, weight, val))

    reasons = []
    for line, contribs in buckets.items():
        line_delta = int(delta.get(line) or 0)
        if line_delta == 0 or not contribs:
            continue
        # Department filter: scale sales/cogs dollars to that department's share.
        if department and line in ("sales", "cogs") and merged_depts:
            share = merged_depts.get(department, 0) / max(1, sum(merged_depts.values()))
            line_delta = int(round(line_delta * share))
            if line_delta == 0:
                continue
        total_w = sum(item[2] for item in contribs) or 1
        allocated = 0
        for i, (fid, dept, weight, val) in enumerate(contribs):
            dollars = int(round(line_delta * weight / total_w))
            if i == len(contribs) - 1:
                dollars = line_delta - allocated
            allocated += dollars
            if dollars == 0:
                continue
            if min_dollars and abs(dollars) < int(min_dollars):
                # Still keep last-item exactness on unfiltered; when filtering, drop small.
                continue
            reasons.append(
                {
                    "factor_id": fid,
                    "name": FACTORS[fid]["name"],
                    "line": line,
                    "department": dept,
                    "dollars": dollars,
                    "note": f"Index {val} vs a neutral card.",
                }
            )

    # When we dropped rows for min_dollars, do not break the unfiltered sum test:
    # re-sum only if nothing was filtered out. If filtered, leave as is.
    if not department and not category and not events_only and not min_dollars:
        by_line: dict[str, int] = {}
        for row in reasons:
            by_line[row["line"]] = by_line.get(row["line"], 0) + int(row["dollars"])
        # Fix any drift from mid-list rounding if a line is missing the last adjust
        # (already last-item corrected). If a line is in delta but missing reasons, skip.

    reasons.sort(key=lambda row: abs(int(row["dollars"])), reverse=True)
    return {
        "store_id": store_id,
        "days": int(days),
        "pnl": pnl,
        "neutral_pnl": neutral,
        "delta": delta,
        "reasons": reasons,
    }


def sparkline_payload(
    state: GameState,
    factor_ids: list[int],
    weeks: int,
    store_id: str | None,
    lines: list[str] | None,
) -> dict:
    """Factor series plus optional P&L lines and a chain overlay."""
    from open_late.economy import E1_LOCAL, city_of, store_ids_for

    history = list(state.economy.history or [])[-max(1, int(weeks)) :]
    week_ids = [int(row["week_id"]) for row in history if int(row.get("week_id", -1)) >= 0]
    # Opening row is week_id -1; drop it from the visible week list but use its card if needed.
    visible = [row for row in history if int(row.get("week_id", -1)) >= 0]
    week_ids = [int(row["week_id"]) for row in visible]
    series: dict[str, list[int]] = {}
    city = city_of(state, store_id) if store_id else None
    for fid in factor_ids or []:
        key = str(int(fid))
        path = []
        for row in visible:
            values = row.get("values") or {}
            city_values = (row.get("city_values") or {}).get(city or "", {}) if city else {}
            store_values = (row.get("store_values") or {}).get(store_id or "", {}) if store_id else {}
            if store_id and key in store_values:
                path.append(int(store_values[key]))
            elif city and key in city_values:
                path.append(int(city_values[key]))
            elif city and int(fid) == 11:
                path.append(int(row.get(f"traffic:{city}", values.get(key, 100))))
            else:
                path.append(int(values.get(key, 100)))
        series[key] = path

    if lines:
        ids = store_ids_for(state)
        for line in lines:
            if line not in PNL_LINES and line != "contribution":
                continue
            store_path = []
            chain_path = []
            for row in visible:
                pnl_map = row.get("pnl") or {}
                if store_id:
                    store_path.append(int((pnl_map.get(store_id) or {}).get(line, 0) or 0))
                chain_vals = [int((pnl_map.get(sid) or {}).get(line, 0) or 0) for sid in ids]
                chain_path.append(sum(chain_vals))
            if store_id:
                series[line] = store_path
            series[f"chain:{line}"] = chain_path
    return {"weeks": week_ids, "series": series}
