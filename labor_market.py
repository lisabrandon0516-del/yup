"""National jobs and wages for Back Office: Retail (Mandate port, phase 2).

Ported (read only) from Mandate's LaborManager (presim/simulation/labor.py),
keeping the two national pieces a store game can use:

  * tightness: the Beveridge-curve vacancy/unemployment ratio
        V/U = 1.1 x exp(0.12 x gap - 0.35 x (u - u*) in pp) x (1 + 0.04 z),
    clipped to 0.2-3.0 (Mandate LaborManager.update);
  * national wage growth: Mandate's wage Phillips curve
        nominal = expected inflation + 0.8 x productivity + 0.4 x slack,
    where slack is read from the tightness signal, ln(V/U / 1.1) / 0.35, in pp
    of unemployment below natural.

Constant dollars (Kendra's Phase 1 answer): the game's prices do not carry a
price level, so the wage level here is the REAL wage relative to trend
productivity. Its weekly growth is the real, non-trend part of Mandate's
nominal growth: 0.4 x slack + (expected - actual inflation). The level mean-
reverts toward 1.0 with a 2-year half-life (real wages catch up with
productivity, which the flat real price level already absorbs) and is capped
at +/- WAGE_LEVEL_CAP.

How it reaches store labour cost, in integer dollars, at a quarterly wage
review (every 13 weeks):
  * indexed wage floor: every employee's market floor is round(base x level),
    base = their wage when the labour block started. Employed wages below it
    are lifted to it (never cut). It is a max, not a sum, with the E8 107
    wage-event bump, so the two never stack;
  * hiring cost: everyone in the hiring pool (not employed) has wage and
    wage_ask rescaled by the change in the level since the last review;
  * corporate doors: door.wage_floor (applied by HQ only when a manager is
    hired) is rescaled to the level; current staff are not lifted to it.

It writes NO economy factor. Factors 2/3/8 (and 12/13/47 via their links) stay
exactly as Phase 1 sets them; labor_mult keeps its capped weekly multiplier.
See PHASE2_NOTES.md for the double-counting map.

Determinism: stream_rng(state, "labor", week), two unit normals per week on
every tier. No network, no outside AI.
"""

from __future__ import annotations

import math
from typing import Any

from open_late.models import GameState

LABOR_VERSION = 1

# Mandate constants (labor.py), unchanged.
WAGE_PHILLIPS = 0.4          # pp wage growth per pp of unemployment below natural
VU_BASE = 1.1
VU_GAP = 0.12
VU_UGAP = 0.35
VU_NOISE = 0.04
PRODUCTIVITY_AVG = 1.5       # % a year, used only for the displayed nominal wage growth

# Store-game translation.
WAGE_NOISE_SD = 0.002        # annual-rate noise on real wage growth (Mandate 0.0004 monthly x 12 / sqrt(4.33), rounded)
WAGE_HALF_LIFE_WEEKS = 104.0
WAGE_REVERT_W = 0.5 ** (1.0 / WAGE_HALF_LIFE_WEEKS)
WAGE_LEVEL_CAP = 0.04
REVIEW_WEEKS = 13            # quarterly wage review
LABOR_NOISE_MULT = {"off": 0.0, "calm": 0.8, "standard": 1.0, "stern": 1.3}
HISTORY_KEEP = 13


def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def initial_labor() -> dict[str, Any]:
    return {
        "version": LABOR_VERSION,
        "week": -1,
        "wage_level": 1.0,
        "applied_level": 1.0,
        "applied_week": -1,
        "vu_ratio": VU_BASE,
        "slack_pp": 0.0,
        "real_wage_growth": 0.0,
        "nominal_wage_growth": 0.0,
        "base_wage": {},
        "door_floor_base": {},
        "door_floor_written": {},
        "reviews": [],
    }


def ensure_labor(macro: dict) -> dict[str, Any]:
    lab = macro.get("labor")
    if not isinstance(lab, dict) or not lab:
        lab = initial_labor()
        macro["labor"] = lab
        return lab
    for key, value in initial_labor().items():
        if key not in lab:
            lab[key] = value
    lab["version"] = LABOR_VERSION
    return lab


def tightness(macro: dict, z: float, noise: float) -> float:
    u_gap_pp = (float(macro["unemployment"]) - float(macro["natural_unemployment"])) * 100.0
    vu = VU_BASE * math.exp(VU_GAP * float(macro["output_gap"]) - VU_UGAP * u_gap_pp) * (1.0 + VU_NOISE * noise * z)
    return clamp(vu, 0.2, 3.0)


def labor_step(state: GameState, week: int, macro: dict, tier: str) -> dict:
    """Weekly national jobs and wages step, after the macro step. Idempotent per week."""
    lab = ensure_labor(macro)
    if int(lab.get("week", -1)) == int(week):
        return lab
    from open_late.economy import stream_rng

    rng = stream_rng(state, "labor", int(week))
    z = [rng.gauss(0.0, 1.0) for _ in range(2)]  # fixed order: V/U noise, wage noise
    noise = LABOR_NOISE_MULT.get(tier, 1.0)
    vu = tightness(macro, z[0], noise)
    slack_pp = math.log(vu / VU_BASE) / VU_UGAP
    real_growth = (
        WAGE_PHILLIPS * slack_pp / 100.0
        + (float(macro["expected_inflation"]) - float(macro["inflation"]))
        + WAGE_NOISE_SD * noise * z[1]
    )
    level = 1.0 + (float(lab["wage_level"]) - 1.0) * WAGE_REVERT_W + real_growth / 52.0
    lab.update(
        {
            "week": int(week),
            "vu_ratio": float(vu),
            "slack_pp": float(slack_pp),
            "real_wage_growth": float(real_growth),
            "nominal_wage_growth": float(
                float(macro["expected_inflation"]) + 0.8 * PRODUCTIVITY_AVG / 100.0 + WAGE_PHILLIPS * slack_pp / 100.0
            ),
            "wage_level": float(clamp(level, 1.0 - WAGE_LEVEL_CAP, 1.0 + WAGE_LEVEL_CAP)),
        }
    )
    if int(week) % REVIEW_WEEKS == 0:
        apply_wage_review(state, lab, int(week))
    return lab


def apply_wage_review(state: GameState, lab: dict, week: int) -> dict:
    """Quarterly: move integer-dollar wage floors and hiring asks to the national level."""
    level = float(lab["wage_level"])
    applied = float(lab.get("applied_level", 1.0)) or 1.0
    ratio = level / applied
    base: dict[str, int] = dict(lab.get("base_wage") or {})
    lifted = 0
    lifted_dollars = 0
    pool_moved = 0
    for person in state.staff:
        if person.id not in base:
            base[person.id] = max(1, int(round(int(person.wage) / applied)))
        if person.employed:
            floor = max(1, int(round(base[person.id] * level)))
            if person.wage < floor:
                lifted += 1
                lifted_dollars += floor - person.wage
                person.wage = floor
            if person.wage_ask < person.wage:
                person.wage_ask = person.wage
        else:
            new = max(1, int(round(int(person.wage) * ratio)))
            if new != person.wage:
                pool_moved += 1
            person.wage = new
            person.wage_ask = new
    door_base: dict[str, float] = dict(lab.get("door_floor_base") or {})
    written: dict[str, int] = dict(lab.get("door_floor_written") or {})
    for door in getattr(state, "doors", None) or []:
        # Re-base when something else (the E8/107 wage-floor event) moved the
        # floor since our last write, so that bump is kept, never re-applied.
        if door.id not in door_base or written.get(door.id) != int(door.wage_floor):
            door_base[door.id] = int(door.wage_floor) / applied
        # The door floor is a hiring-cost input (corporate.hire_manager lifts a
        # new manager to it). Current staff are NOT lifted here: HQ keeps lead
        # wages and supercenter-scaled door floors in different units, and only
        # applies the floor at hire. Their national floor is the indexed one above.
        door.wage_floor = max(1, int(round(door_base[door.id] * level)))
        written[door.id] = int(door.wage_floor)
    lab["base_wage"] = base
    lab["door_floor_base"] = door_base
    lab["door_floor_written"] = written
    lab["applied_level"] = level
    lab["applied_week"] = int(week)
    row = {
        "week": int(week),
        "level": round(level, 5),
        "ratio": round(ratio, 5),
        "lifted": lifted,
        "lifted_weekly_dollars": int(lifted_dollars),
        "pool_moved": pool_moved,
    }
    reviews = list(lab.get("reviews") or [])
    reviews.append(row)
    lab["reviews"] = reviews[-HISTORY_KEEP:]
    return row


def labor_snapshot(macro: dict) -> dict:
    lab = macro.get("labor") or {}
    if not lab:
        return {}
    reviews = list(lab.get("reviews") or [])
    return {
        "vu_ratio": round(float(lab["vu_ratio"]), 3),
        "slack_pp": round(float(lab["slack_pp"]), 3),
        "real_wage_level": round(float(lab["wage_level"]), 4),
        "real_wage_growth_pct": round(100.0 * float(lab["real_wage_growth"]), 2),
        "nominal_wage_growth_pct": round(100.0 * float(lab["nominal_wage_growth"]), 2),
        "last_review": reviews[-1] if reviews else None,
        "next_review_week": (int(lab.get("week", 0)) // REVIEW_WEEKS + 1) * REVIEW_WEEKS,
    }
