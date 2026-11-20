"""Rule-based Fed for Back Office: Retail (Mandate port, phase 2).

Ported (read only) from Mandate's FedManager (presim/simulation/fed.py) and
reduced to the parts the store game needs:

  * shadow rate = Taylor-type target, recomputed every week
        i* = r* + pi_obs + phi_pi (pi_obs - target) + phi_u (u* - u) + bias
            + 0.00005 x max(0, 80 - credibility)
    with pi_obs = 0.4 headline + 0.6 expected inflation (Mandate's core proxy);
  * the policy rate moves only at 8 meetings a year (Mandate MEETING_MONTHS,
    mapped onto weeks of the year), with inertia 0.4, a 75bp cap per meeting,
    a 25bp grid, a hold band inside a quarter point and a zero lower bound
    (0-0.25% range, midpoint 0.125%);
  * credibility (0-100) anchors inflation expectations through macro.py's
    `anchor` effect (cred / 80, as Mandate's FedManager.macro_inputs);
  * transmission: a lagged short real rate (6-month e-folding, Mandate's
    consumption/housing lags blended) gives macro.py a `monetary_demand`
    effect in gap points, -RATE_SENSITIVITY x (lagged real rate - r*) x 100.

Not ported (no counterpart in the store game yet): chair nominations and
Senate votes, public pressure, target changes, balance sheet / QE, yield
curve, stock and housing markets, bond tantrum and bank-stress events. Their
state keys are reserved (stance, inflation_target, independence) so later
phases can add levers without a save migration.

Determinism: one named stream, stream_rng(state, "fed", week), one unit
normal per week on every tier ("judgement noise" on the shadow rate, scaled
by tier). No Python hash(), no network, no outside AI.

Money: this module never touches cash. The rate reaches the books only
through factor 1 (policy rate index) -> factor 96 (credit spread link, E3)
-> economy_e3.interest_mult on the Sunday interest bill. See
`loan_rate_index` / `rival_interest_due` for the engine-side hook rival code
can call; nothing here reads or writes rival or CEO decision state.
"""

from __future__ import annotations

import math
from typing import Any, Callable

from open_late.models import GameState

FED_VERSION = 1

# --- Mandate tuning (models/fed.py, simulation/fed.py), unchanged -----------
RATE_INERTIA = 0.4          # weight on the current rate at each meeting
MAX_MOVE = 0.0075           # largest move per meeting (75bp)
ZLB_RATE = 0.00125          # 0-0.25% target range midpoint
PI_WEIGHT_ACTUAL = 0.4      # 40% headline, 60% expected inflation
STANCE_RULE = {"hawk": (0.9, 1.3, 0.25), "centrist": (0.5, 2.0, 0.0), "dove": (0.3, 2.6, -0.25)}
MEETING_MONTHS = (1, 3, 5, 6, 7, 9, 11, 12)
START_RATE = 0.04           # Mandate EconomicIndicators.interest_rate
START_CREDIBILITY = 80.0
START_INDEPENDENCE = 85.0
CRED_ADJ_M = 0.04           # monthly pull of credibility toward its target

# --- Weekly translation ------------------------------------------------------
WEEKS_PER_MONTH = 52.0 / 12.0
# Meetings fall in the last week of each Mandate meeting month (week of year 0-51).
MEETING_WEEKS = tuple(int(round(m * WEEKS_PER_MONTH)) - 1 for m in MEETING_MONTHS)
CRED_ADJ_W = 1.0 - (1.0 - CRED_ADJ_M) ** (1.0 / WEEKS_PER_MONTH)
# Lagged real rate: Mandate lags consumption 4 mo, housing 6 mo, investment 9 mo.
# A single 6-month e-folding lag in weeks.
TRANSMISSION_LAG_WEEKS = 6.0 * WEEKS_PER_MONTH
RATE_SENSITIVITY = 1.2      # gap pts per pp real-rate gap (macro.py RATE_SENSITIVITY)
# Judgement noise on the shadow rate (rate units), by tier. Draw happens on every tier.
SHADOW_NOISE_SD = 0.0005
FED_NOISE_MULT = {"off": 0.0, "calm": 0.8, "standard": 1.0, "stern": 1.3}

MEETING_LOG = 24
RATE_PATH_WEEKS = 156

# Phase 4 (news / headlines / inbox) and phase 5 (memory) hook:
# listener(state, week, meeting_row) after every meeting (hold or move).
MEETING_LISTENERS: list[Callable[[GameState, int, dict], None]] = []


def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def snap_to_grid(r: float) -> float:
    """Round to a 25bp target-range midpoint (0.125%, 0.375%, ...)."""
    return round((r - ZLB_RATE) / 0.0025) * 0.0025 + ZLB_RATE


def initial_fed() -> dict[str, Any]:
    return {
        "version": FED_VERSION,
        "week": -1,
        "policy_rate": START_RATE,
        "shadow_rate": START_RATE,
        "last_change": 0.0,
        "credibility": START_CREDIBILITY,
        "independence": START_INDEPENDENCE,
        "inflation_target": 0.02,
        "stance": "centrist",
        # Mandate init_anchors: short real rate at the start (4.0% - 2.8%).
        "lag_real": START_RATE - 0.028,
        "monetary_demand": 0.0,
        "meetings": [],
        "rate_path": [],
    }


def ensure_fed(macro: dict) -> dict[str, Any]:
    fed = macro.get("fed")
    if not isinstance(fed, dict) or not fed:
        fed = initial_fed()
        macro["fed"] = fed
        return fed
    for key, value in initial_fed().items():
        if key not in fed:
            fed[key] = value
    fed["version"] = FED_VERSION
    return fed


def is_meeting_week(week: int) -> bool:
    return int(week) % 52 in MEETING_WEEKS


def taylor_target(macro: dict, fed: dict) -> float:
    """Unconstrained (shadow) policy-rate target, Mandate's taylor_target without markets."""
    phi_pi, phi_u, bias = STANCE_RULE.get(fed.get("stance", "centrist"), STANCE_RULE["centrist"])
    pi_obs = PI_WEIGHT_ACTUAL * float(macro["inflation"]) + (1 - PI_WEIGHT_ACTUAL) * float(macro["expected_inflation"])
    u_gap = float(macro["natural_unemployment"]) - float(macro["unemployment"])
    return (
        float(macro["neutral_real_rate"])
        + pi_obs
        + phi_pi * (pi_obs - float(fed["inflation_target"]))
        + phi_u * u_gap
        + bias / 100.0
        + 0.00005 * max(0.0, 80.0 - float(fed["credibility"]))
    )


def _update_credibility(macro: dict, fed: dict) -> None:
    target = float(fed["inflation_target"])
    gap_pi = abs(float(macro["expected_inflation"]) - target)
    stance_adj = {"hawk": 4.0, "centrist": 0.0, "dove": -4.0}.get(fed.get("stance", "centrist"), 0.0)
    cred_tgt = clamp(
        88.0
        - 1500.0 * gap_pi
        - 600.0 * max(0.0, float(macro["inflation"]) - target - 0.01)
        + 0.3 * (float(fed["independence"]) - 85.0)
        + stance_adj,
        0.0,
        100.0,
    )
    fed["credibility"] = clamp(float(fed["credibility"]) + CRED_ADJ_W * (cred_tgt - float(fed["credibility"])), 0.0, 100.0)


def _meeting(state: GameState, week: int, macro: dict, fed: dict, shadow: float) -> dict:
    i = float(fed["policy_rate"])
    desired = RATE_INERTIA * i + (1 - RATE_INERTIA) * max(ZLB_RATE, shadow)
    new = snap_to_grid(clamp(desired, i - MAX_MOVE, i + MAX_MOVE))
    new = max(ZLB_RATE, new)
    change = new - i
    if abs(change) < 0.00124:  # inside a quarter point: hold, but stay on the grid
        new = snap_to_grid(i)
        change = new - i
    fed["policy_rate"] = float(new)
    fed["last_change"] = float(change)
    bp = int(round(change * 1e4))
    pi = float(macro["inflation"])
    target = float(fed["inflation_target"])
    pi_txt = "elevated" if pi > target + 0.005 else "subdued" if pi < target - 0.005 else "near target"
    u, nat = float(macro["unemployment"]), float(macro["natural_unemployment"])
    lab_txt = "tight" if u < nat - 0.003 else "softening" if u > nat + 0.003 else "balanced"
    lo = max(0.0, new - 0.00125)
    verb = (("raises" if bp > 0 else "cuts") + f" rates {abs(bp)}bp to") if abs(bp) >= 13 else "holds rates at"
    row = {
        "week": int(week),
        "rate": round(float(new), 6),
        "change_bp": bp,
        "shadow": round(float(shadow), 6),
        "statement": (
            f"The Fed {verb} {lo * 100:.2f}-{(lo + 0.0025) * 100:.2f}%. Inflation is {pi_txt} ({pi * 100:.1f}%) "
            f"and the job market is {lab_txt} ({u * 100:.1f}% unemployment)."
        ),
    }
    meetings = list(fed.get("meetings") or [])
    meetings.append(row)
    fed["meetings"] = meetings[-MEETING_LOG:]
    for listener in list(MEETING_LISTENERS):
        listener(state, int(week), row)
    return row


def fed_step(state: GameState, week: int, macro: dict, tier: str) -> dict[str, float]:
    """One weekly Fed step, before the macro step. Returns macro.py effects.

    Reads last week's macro numbers (Mandate runs the Fed before the economy).
    Idempotent within a week: a second call returns the same effects.
    """
    fed = ensure_fed(macro)
    if int(fed.get("week", -1)) != int(week):
        from open_late.economy import stream_rng

        z = stream_rng(state, "fed", int(week)).gauss(0.0, 1.0)
        _update_credibility(macro, fed)
        shadow = taylor_target(macro, fed) + SHADOW_NOISE_SD * FED_NOISE_MULT.get(tier, 1.0) * z
        fed["shadow_rate"] = float(shadow)
        if is_meeting_week(week):
            _meeting(state, week, macro, fed, shadow)
        real_now = float(fed["policy_rate"]) - float(macro["expected_inflation"])
        fed["lag_real"] = float(fed["lag_real"]) + (real_now - float(fed["lag_real"])) / TRANSMISSION_LAG_WEEKS
        fed["monetary_demand"] = -RATE_SENSITIVITY * (float(fed["lag_real"]) - float(macro["neutral_real_rate"])) * 100.0
        path = list(fed.get("rate_path") or [])
        path.append(round(float(fed["policy_rate"]), 6))
        fed["rate_path"] = path[-RATE_PATH_WEEKS:]
        fed["week"] = int(week)
    return {
        "monetary_demand": float(fed["monetary_demand"]),
        "inflation_target": float(fed["inflation_target"]),
        "anchor": clamp(float(fed["credibility"]) / 80.0, 0.0, 1.25),
    }


# --- Engine-side borrowing-cost hooks ----------------------------------------

def policy_rate(state: GameState) -> float | None:
    """Current policy rate (annual, fraction) or None when the economy is off."""
    macro = getattr(state.economy, "macro", None) or {}
    fed = macro.get("fed") or {}
    if not fed:
        return None
    return float(fed["policy_rate"])


def loan_rate_index(state: GameState) -> float:
    """Multiplier on a loan's base interest charge; exactly 1.0 when off.

    The same multiplier the player's Sunday interest uses
    (economy_e3.interest_mult: factors 96 credit spread <- 1 policy rate, and 102).
    """
    from open_late.economy_e3 import interest_mult

    return float(interest_mult(state))


def rival_interest_due(state: GameState, principal: int, weekly_rate: float | None = None) -> int:
    """Interest in integer dollars on a rival's existing loan for one week.

    Engine-side cost plumbing only. HQ has no rival balance sheet yet (the
    Rival model carries name, price index, reputation and focus), so nothing
    calls this today. When Brandon's rival AI adds loans, its Sunday books can
    charge `rival_interest_due(state, principal)` and the Fed reaches rivals
    through exactly the same path as the player. Default base rate is the
    player's finance.INTEREST_RATE.
    """
    from open_late.finance import INTEREST_RATE

    base = INTEREST_RATE if weekly_rate is None else float(weekly_rate)
    return max(0, int(round(int(principal) * base * loan_rate_index(state))))


def fed_snapshot(macro: dict) -> dict:
    fed = macro.get("fed") or {}
    if not fed:
        return {}
    meetings = list(fed.get("meetings") or [])
    return {
        "policy_rate_pct": round(100.0 * float(fed["policy_rate"]), 3),
        "shadow_rate_pct": round(100.0 * float(fed["shadow_rate"]), 3),
        "last_change_bp": int(round(1e4 * float(fed.get("last_change", 0.0)))),
        "credibility": round(float(fed["credibility"]), 1),
        "inflation_target_pct": round(100.0 * float(fed["inflation_target"]), 2),
        "stance": fed.get("stance", "centrist"),
        "real_rate_lagged_pct": round(100.0 * float(fed["lag_real"]), 3),
        "monetary_demand_gap_pts": round(float(fed["monetary_demand"]), 3),
        "last_meeting": meetings[-1] if meetings else None,
        "next_meeting_week": _next_meeting(int(fed.get("week", -1))),
    }


def _next_meeting(week: int) -> int:
    for ahead in range(1, 53):
        if is_meeting_week(week + ahead):
            return week + ahead
    return week + 1
