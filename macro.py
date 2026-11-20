"""Weekly national macro layer for Back Office: Retail (Mandate port, phases 1-2).

Ported from Mandate's monthly NumPy model (presim/simulation/macro.py) as pure
Python, one step per in-game week (the Sunday economy tick). Phase 1 covers the
real side only: output gap, potential and real GDP growth, unemployment (Okun),
inflation (expectations-augmented Phillips curve) and consumer confidence.

Translation from monthly to weekly (52/12 weeks per month):
  * every partial-adjustment weight a (x' = a x + (1 - a) target) becomes
    a_w = a ** (12/52), so the half-life in calendar time is unchanged;
  * shock sigmas are rescaled so the stationary spread is unchanged:
    s_w = s_m * sqrt((1 - a_w^2) / (1 - a_m^2));
  * trend growth compounds weekly, (1 + g) ** (1/52);
  * instant GDP growth is annualised with ** 52 instead of ** 12.

The macro layer sets the NATIONAL numbers. Four national factors of the
120-factor card (2 confidence, 3 unemployment, 4 basket inflation, 8 activity)
are driven by it: value = macro anchor + RESID_FRAC x (their own mean-100 walk
- 100). Their old national link equations are skipped while the macro layer is
on (the macro model already contains those links). Every other factor keeps its
own dynamics and picks up the national move only through its existing links,
so nothing is counted twice. See PHASE1_NOTES.md for the full factor map.

The game world is priced in real (constant) dollars: index 100 on factor 4
means "inflation at the 2% target", not "price level of week 0". Product costs,
prices, wages and rents are integer dollars and are never scaled by a
cumulative price level here (open question for phase 2).

Determinism: one named hash stream, stream_rng(state, "macro", week), with a
fixed draw order (4 unit normals per week). Draws happen on every tier and
the tier only scales the amplitude (common random numbers, as in E6). No
Python hash(), no network, no outside AI.

Off: nothing here runs and state.economy.macro stays {} on a new game, so the
'off' path is bit-identical to HQ.

Phase 2 (Fed, interest rates, jobs and wages) is wired in directly, not via
the hook lists: open_late/fed.py runs before each step on last week's numbers
and supplies monetary_demand, inflation_target and the expectations anchor;
open_late/labor_market.py runs after each step. The Fed also drives factor 1
(policy rate) as anchor + residual, which reaches loan interest through the
existing 96 credit-spread link. Factor 4 is centred on expected inflation
(Kendra's Phase 1 answer), not on the 2% target.

Phases 3-5 plug in through EFFECT_PROVIDERS (crises and event chains),
STEP_LISTENERS (news, headlines, inbox, memory) and fed.MEETING_LISTENERS
(Fed statements). Nothing is registered by default.
"""

from __future__ import annotations

import math
from typing import Any, Callable

from open_late.models import GameState

MACRO_VERSION = 2  # 2: phase 2 adds the "fed" and "labor" sub-blocks

# --- Mandate MacroParams defaults (monthly), unchanged -----------------------
TREND_GROWTH = 0.02
BASE_NAT_U = 0.043
INFLATION_TARGET = 0.02
GAP_PERSISTENCE_M = 0.85
PHILLIPS_SLOPE = 0.3
OKUN = 0.5
RATE_SENSITIVITY = 1.2
SIGMA_GAP_M = 0.08
SIGMA_U_M = 0.0005
SIGMA_PI_M = 0.0007
U_ADJ_M = 0.8           # unemployment keeps 0.8 of last month
PI_ADJ_M = 0.75         # inflation keeps 0.75 of last month
GROWTH_SMOOTH_M = 0.85  # reported growth keeps 0.85 of last month
CONF_ADJ_M = 0.8        # confidence keeps 0.8 of last month
EXP_KEEP_M = 0.92       # expectations: 0.94 - w with w = 0.02 (normal anchor)
EXP_PI_M = 0.06
EXP_TARGET_M = 0.02

# Mandate initial EconomicIndicators.
INITIAL = {
    "gdp": 28.0,
    "potential_gdp": 28.0,
    "gdp_growth": 0.02,
    "output_gap": 0.0,
    "inflation": 0.03,
    "expected_inflation": 0.028,
    "unemployment": 0.042,
    "natural_unemployment": BASE_NAT_U,
    "neutral_real_rate": 0.012,
    "consumer_confidence": 60.0,
    "trend_growth": TREND_GROWTH,
}

WEEKS_PER_MONTH = 52.0 / 12.0


def weekly_weight(monthly: float) -> float:
    """Partial-adjustment weight with the same calendar half-life."""
    return float(monthly) ** (1.0 / WEEKS_PER_MONTH)


def weekly_sigma(sigma_m: float, a_m: float) -> float:
    """Shock sigma for an AR(1) with weight a_m so the stationary spread is unchanged."""
    a_w = weekly_weight(a_m)
    return float(sigma_m) * math.sqrt((1.0 - a_w * a_w) / (1.0 - a_m * a_m))


GAP_W = weekly_weight(GAP_PERSISTENCE_M)
U_W = weekly_weight(U_ADJ_M)
PI_W = weekly_weight(PI_ADJ_M)
GROWTH_W = weekly_weight(GROWTH_SMOOTH_M)
CONF_W = weekly_weight(CONF_ADJ_M)
EXP_KEEP_W = weekly_weight(EXP_KEEP_M)
EXP_PI_W = (1.0 - EXP_KEEP_W) * EXP_PI_M / (EXP_PI_M + EXP_TARGET_M)
EXP_TARGET_W = (1.0 - EXP_KEEP_W) * EXP_TARGET_M / (EXP_PI_M + EXP_TARGET_M)
SIGMA_GAP_W = weekly_sigma(SIGMA_GAP_M, GAP_PERSISTENCE_M)
SIGMA_U_W = weekly_sigma(SIGMA_U_M, U_ADJ_M)
SIGMA_PI_W = weekly_sigma(SIGMA_PI_M, PI_ADJ_M)

# --- Phase-1 business-cycle stand-in ---------------------------------------
# Mandate drives cycles with fiscal policy, the Fed and crises (phases 2-3).
# Until those land, two slow AR(1) shocks give the national economy a cycle:
# a demand impulse (gap points) and a supply/inflation impulse (percent points).
DEMAND_SHOCK_PERSIST_M = 0.92
SUPPLY_SHOCK_PERSIST_M = 0.85
DEMAND_SHOCK_PERSIST_W = weekly_weight(DEMAND_SHOCK_PERSIST_M)
SUPPLY_SHOCK_PERSIST_W = weekly_weight(SUPPLY_SHOCK_PERSIST_M)
# Stationary standard deviation by tier: demand in gap points, supply in pp.
DEMAND_SHOCK_SD = {"off": 0.0, "calm": 0.55, "standard": 0.75, "stern": 1.2}
SUPPLY_SHOCK_SD = {"off": 0.0, "calm": 0.2, "standard": 0.25, "stern": 0.45}
# Mandate's own small per-step noise, scaled by tier.
MACRO_NOISE_MULT = {"off": 0.0, "calm": 0.8, "standard": 1.0, "stern": 1.3}

# --- Card mapping: macro anchor + residual walk -----------------------------
# fid -> (anchor function name, residual fraction, low, high)
# Phase 2 adds factor 1 (policy rate), set by the Fed in open_late/fed.py.
DRIVEN_FACTORS = (1, 2, 3, 4, 8)
RESID_FRAC = {1: 0.5, 2: 0.5, 3: 0.5, 4: 0.5, 8: 0.5}
FACTOR_RANGE = {1: (70, 140), 2: (60, 140), 3: (70, 140), 4: (80, 140), 8: (75, 125)}
# Factor 4: index points per pp of inflation above EXPECTED inflation (Kendra's
# Phase 1 answer 4: centre on expectations, not the 2% target).
INFLATION_PTS_PER_PP = 4.0
# Factor 1: index points per pp of policy rate above Mandate's starting 4.0%
# (index 100 = HQ's calibrated "today" credit cost).
RATE_PTS_PER_PP = 6.0
REF_POLICY_RATE = 0.04
UNEMPLOYMENT_PTS_PER_PP = 5.0   # factor 3: index points per pp of unemployment above natural
ACTIVITY_PTS_PER_GAP = 2.5      # factor 8: index points per point of output gap
CONFIDENCE_PTS_PER_PT = 0.8     # factor 2: index points per Mandate confidence point (60 = neutral)

HISTORY_WEEKS = 156

# --- Hooks for phases 2-5 ----------------------------------------------------
# provider(state, week, macro) -> {"eff": {...}, "shocks": {...}} or None.
# Recognised eff keys (Mandate names): demand, spending, tax, trend, inflation,
# nat_u, monetary_demand, policy_rate, inflation_target, anchor.
# Recognised shock keys: gap, inflation, trend, confidence.
EFFECT_PROVIDERS: list[Callable[[GameState, int, dict], dict | None]] = []
# listener(state, week, before, after) after each weekly step (news, inbox, memory).
STEP_LISTENERS: list[Callable[[GameState, int, dict, dict], None]] = []


def _difficulty(state: GameState) -> str:
    from open_late.economy import economy_difficulty

    return economy_difficulty(state)


def macro_active(state: GameState) -> bool:
    return _difficulty(state) != "off"


def initial_macro() -> dict[str, Any]:
    row: dict[str, Any] = {key: float(value) for key, value in INITIAL.items()}
    row.update(
        {
            "version": MACRO_VERSION,
            "week": -1,
            "steps": 0,
            "price_level": 100.0,
            "demand_shock": 0.0,
            "supply_shock": 0.0,
            "resid": {},
            "history": [],
            "fed": {},
            "labor": {},
        }
    )
    from open_late.fed import initial_fed
    from open_late.labor_market import initial_labor

    row["fed"] = initial_fed()
    row["labor"] = initial_labor()
    return row


def ensure_macro(state: GameState) -> dict[str, Any]:
    """Initialise or migrate the macro block. Only called when the economy is on."""
    eco = state.economy
    macro = getattr(eco, "macro", None)
    if not isinstance(macro, dict) or not macro:
        macro = initial_macro()
        eco.macro = macro
        return macro
    base = initial_macro()
    for key, value in base.items():
        if key not in macro:
            macro[key] = value
    # Phase-1 saves (version 1) have no fed/labor sub-blocks; partial sub-blocks
    # are filled key by key, existing numbers kept.
    from open_late.fed import ensure_fed
    from open_late.labor_market import ensure_labor

    ensure_fed(macro)
    ensure_labor(macro)
    macro["version"] = MACRO_VERSION
    return macro


def _gather_effects(state: GameState, week: int, macro: dict) -> tuple[dict, dict]:
    eff: dict[str, float] = {}
    shocks: dict[str, float] = {}
    for provider in list(EFFECT_PROVIDERS):
        out = provider(state, week, macro) or {}
        for key, value in (out.get("eff") or {}).items():
            if key in ("policy_rate", "inflation_target", "anchor"):
                eff[key] = float(value)
            else:
                eff[key] = eff.get(key, 0.0) + float(value)
        for key, value in (out.get("shocks") or {}).items():
            shocks[key] = shocks.get(key, 0.0) + float(value)
    return eff, shocks


def _clip(value: float, low: float, high: float) -> float:
    return low if value < low else high if value > high else value


def macro_step(state: GameState, week: int) -> dict | None:
    """Advance the national economy one week. No-op when off or already stepped this week."""
    if not macro_active(state):
        return None
    macro = ensure_macro(state)
    if int(macro.get("week", -1)) == int(week):
        return macro
    from open_late.economy import stream_rng

    tier = _difficulty(state)
    rng = stream_rng(state, "macro", int(week))
    # Fixed draw order on every tier: gap noise, unemployment noise, inflation noise,
    # demand impulse, supply impulse.
    z = [rng.gauss(0.0, 1.0) for _ in range(5)]
    noise = MACRO_NOISE_MULT.get(tier, 1.0)
    before = {key: macro[key] for key in ("output_gap", "inflation", "unemployment", "gdp_growth", "consumer_confidence")}

    d_sd = DEMAND_SHOCK_SD.get(tier, 0.0)
    s_sd = SUPPLY_SHOCK_SD.get(tier, 0.0)
    macro["demand_shock"] = DEMAND_SHOCK_PERSIST_W * float(macro["demand_shock"]) + d_sd * math.sqrt(
        1.0 - DEMAND_SHOCK_PERSIST_W**2
    ) * z[3]
    macro["supply_shock"] = SUPPLY_SHOCK_PERSIST_W * float(macro["supply_shock"]) + s_sd * math.sqrt(
        1.0 - SUPPLY_SHOCK_PERSIST_W**2
    ) * z[4]

    # Phase 2: the Fed runs first on last week's numbers (Mandate order) and
    # supplies monetary_demand, inflation_target and the expectations anchor.
    # Phase 3+ providers can still add to or override these.
    from open_late.fed import fed_step

    fed_eff = fed_step(state, int(week), macro, tier)
    eff, shocks = _gather_effects(state, int(week), macro)
    for key, value in fed_eff.items():
        eff.setdefault(key, value)
    g = lambda d, k: float(d.get(k, 0.0))
    x = dict(macro)

    # Demand side. Phase 1 has no policy rate, so the real-rate gap is zero unless
    # a phase-2 provider supplies monetary_demand or a policy_rate.
    if "monetary_demand" in eff:
        monetary = eff["monetary_demand"]
    elif "policy_rate" in eff:
        real_rate_gap = (eff["policy_rate"] - x["expected_inflation"]) - x["neutral_real_rate"]
        monetary = -RATE_SENSITIVITY * real_rate_gap * 100.0
    else:
        monetary = 0.0
    fiscal = g(eff, "spending") - 0.6 * g(eff, "tax")
    confidence = (x["consumer_confidence"] - 60.0) * 0.02
    demand = _clip(
        fiscal + g(eff, "demand") + monetary + confidence + g(shocks, "gap") + macro["demand_shock"], -12.0, 8.0
    )
    gap = GAP_W * x["output_gap"] + (1.0 - GAP_W) * demand + SIGMA_GAP_W * noise * z[0]
    gap = _clip(gap, -12.0, 8.0)

    # Supply side and GDP.
    trend = _clip(TREND_GROWTH + (g(eff, "trend") + g(shocks, "trend")) / 100.0, -0.01, 0.05)
    potential = x["potential_gdp"] * (1.0 + trend) ** (1.0 / 52.0)
    gdp = potential * (1.0 + gap / 100.0)
    inst = (gdp / x["gdp"]) ** 52 - 1.0 if x["gdp"] > 0 else 0.0
    growth = _clip(GROWTH_W * x["gdp_growth"] + (1.0 - GROWTH_W) * inst, -0.15, 0.15)

    # Labour market (Okun).
    nat_u = _clip(BASE_NAT_U + g(eff, "nat_u") / 100.0, 0.025, 0.08)
    u_target = nat_u - OKUN * gap / 100.0
    u = _clip(U_W * x["unemployment"] + (1.0 - U_W) * u_target + SIGMA_U_W * noise * z[1], 0.02, 0.25)

    # Prices (expectations-augmented Phillips curve + supply impulse).
    supply = (g(eff, "inflation") + g(shocks, "inflation") + macro["supply_shock"]) / 100.0
    pi_target = x["expected_inflation"] + PHILLIPS_SLOPE * gap / 100.0 + supply
    pi = _clip(PI_W * x["inflation"] + (1.0 - PI_W) * pi_target + SIGMA_PI_W * noise * z[2], -0.03, 0.25)
    target = float(eff.get("inflation_target", INFLATION_TARGET))
    anchor = float(eff.get("anchor", 1.0))
    exp_target = EXP_TARGET_W * anchor
    expected = _clip(
        (1.0 - EXP_PI_W - exp_target) * x["expected_inflation"] + EXP_PI_W * pi + exp_target * target, -0.01, 0.2
    )

    conf_target = 60.0 + 4.0 * gap - 300.0 * max(0.0, pi - 0.03) + g(shocks, "confidence")
    conf = _clip(CONF_W * x["consumer_confidence"] + (1.0 - CONF_W) * conf_target, 0.0, 100.0)

    macro.update(
        {
            "week": int(week),
            "steps": int(macro.get("steps", 0)) + 1,
            "output_gap": gap,
            "trend_growth": trend,
            "potential_gdp": potential,
            "gdp": gdp,
            "gdp_growth": growth,
            "natural_unemployment": nat_u,
            "unemployment": u,
            "inflation": pi,
            "expected_inflation": expected,
            "consumer_confidence": conf,
            "price_level": float(macro.get("price_level", 100.0)) * (1.0 + pi) ** (1.0 / 52.0),
        }
    )
    hist = list(macro.get("history") or [])
    hist.append(
        {
            "week": int(week),
            "inflation": round(pi, 6),
            "unemployment": round(u, 6),
            "output_gap": round(gap, 4),
            "gdp_growth": round(growth, 6),
            "confidence": round(conf, 3),
        }
    )
    macro["history"] = hist[-HISTORY_WEEKS:]
    # Phase 2: national jobs and wages read this week's macro numbers.
    from open_late.labor_market import labor_step

    labor = labor_step(state, int(week), macro, tier)
    hist[-1]["policy_rate"] = round(float(macro["fed"]["policy_rate"]), 6)
    hist[-1]["wage_level"] = round(float(labor["wage_level"]), 6)
    hist[-1]["vu_ratio"] = round(float(labor["vu_ratio"]), 4)
    macro["history"] = hist[-HISTORY_WEEKS:]
    after = {key: macro[key] for key in before}
    for listener in list(STEP_LISTENERS):
        listener(state, int(week), before, after)
    return macro


def factor_anchor(macro: dict, fid: int) -> float:
    if fid == 4:
        return 100.0 + INFLATION_PTS_PER_PP * (float(macro["inflation"]) - float(macro["expected_inflation"])) * 100.0
    if fid == 1:
        rate = float((macro.get("fed") or {}).get("policy_rate", REF_POLICY_RATE))
        return 100.0 + RATE_PTS_PER_PP * (rate - REF_POLICY_RATE) * 100.0
    if fid == 3:
        return 100.0 + UNEMPLOYMENT_PTS_PER_PP * (
            float(macro["unemployment"]) - float(macro.get("natural_unemployment", BASE_NAT_U))
        ) * 100.0
    if fid == 8:
        return 100.0 + ACTIVITY_PTS_PER_GAP * float(macro["output_gap"])
    if fid == 2:
        return 100.0 + CONFIDENCE_PTS_PER_PT * (float(macro["consumer_confidence"]) - 60.0)
    raise KeyError(fid)


def walk_current(state: GameState, fid: int, current: int) -> int:
    """Hook for the national walk step: driven factors walk on their own residual."""
    if fid not in DRIVEN_FACTORS or not macro_active(state):
        return current
    macro = ensure_macro(state)
    resid = macro.get("resid") or {}
    if int(getattr(state.economy, "live_ticks", 0) or 0) == 0:
        return 100
    return int(resid.get(str(fid), 100))


def apply_macro_factors(state: GameState) -> bool:
    """Write macro-driven national factors after the walks. Returns False when off."""
    if not macro_active(state):
        return False
    from open_late.economy import _clamp

    macro = ensure_macro(state)
    eco = state.economy
    resid = dict(macro.get("resid") or {})
    for fid in DRIVEN_FACTORS:
        walked = int(eco.values.get(str(fid), 100))
        resid[str(fid)] = walked
        low, high = FACTOR_RANGE[fid]
        value = factor_anchor(macro, fid) + RESID_FRAC[fid] * (walked - 100)
        eco.values[str(fid)] = _clamp(value, low, high)
    macro["resid"] = resid
    return True


def macro_snapshot(state: GameState) -> dict:
    """Read API for the UI (x). Percent values are annual rates in percent."""
    if not macro_active(state) or not getattr(state.economy, "macro", None):
        return {"active": False}
    macro = state.economy.macro
    from open_late.fed import fed_snapshot
    from open_late.labor_market import labor_snapshot

    return {
        "active": True,
        "week": int(macro.get("week", -1)),
        "inflation_pct": round(100.0 * float(macro["inflation"]), 2),
        "expected_inflation_pct": round(100.0 * float(macro["expected_inflation"]), 2),
        "unemployment_pct": round(100.0 * float(macro["unemployment"]), 2),
        "natural_unemployment_pct": round(100.0 * float(macro["natural_unemployment"]), 2),
        "output_gap_pct": round(float(macro["output_gap"]), 2),
        "gdp_growth_pct": round(100.0 * float(macro["gdp_growth"]), 2),
        "consumer_confidence": round(float(macro["consumer_confidence"]), 1),
        "price_level": round(float(macro.get("price_level", 100.0)), 2),
        "history": list(macro.get("history") or []),
        # Phase 2 additions (engine only; for x's economy desk).
        "fed": fed_snapshot(macro),
        "labor": labor_snapshot(macro),
    }
