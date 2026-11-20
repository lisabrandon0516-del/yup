"""E3: remaining factors 15–22, 27–36, 47–56, 80–120, Sunday P&L folds, rival sync.

Rent pressure (88), CAM (89), fixture wear (92), parking fees (93), and
warehouse rent (94) all fold into the existing rent line. Off stays an
identity. Harvest Card (24) lifts grocery, meat_dairy, and frozen in reload weeks.
"""

from __future__ import annotations

import random
from typing import Any

from open_late.departments import DEPARTMENT_IDS
from open_late.models import GameState

LABOR_CAP = 0.12
RENT_CAP = 0.06
RENT_EVENT_CAP = 0.15
CARD_CAP = 0.12
INTEREST_CAP = 0.20

E3_IDS = frozenset(list(range(15, 23)) + list(range(27, 37)) + list(range(47, 57)) + list(range(80, 121)))
E3_CITY_WALKS = (16, 18, 19, 20, 47, 51, 53, 85, 88, 89, 91, 95, 104, 106, 108)
E3_NATIONAL_WALKS = (86, 96, 97, 105, 112, 113, 114, 115, 116, 117, 118)
E3_STORE_WALKS = (48, 55, 80, 81, 90, 92, 93, 94)

WALKS_E3: dict[int, tuple] = {
    16: (0.08, 0.30, 100, 70, 120),
    18: (0.08, 0.70, 100, 60, 140),
    19: (0.07, 0.50, 100, 80, 150),
    20: (0.14, 1.00, 100, 70, 160),
    47: (0.14, 0.80, 100, 70, 150),
    48: (0.15, 0.70, 100, 70, 150),
    51: (0.10, 0.40, 100, 90, 130),
    53: (0.10, 0.80, 108, 80, 150),
    55: (0.20, 0.60, 100, 80, 120),
    80: (0.15, 0.80, 100, 86, 120),
    81: (0.15, 0.80, 0, 0, 100),
    85: (0.15, 0.70, 100, 80, 140),
    86: (0.08, 0.60, 100, 80, 130),
    88: (0.06, 0.35, 100, 90, 130),
    89: (0.08, 0.40, 100, 90, 125),
    90: (0.08, 0.40, 100, 90, 140),
    91: (0.12, 0.70, 100, 80, 150),
    92: (0.05, 0.30, 100, 90, 130),
    93: (0.08, 0.30, 100, 90, 120),
    94: (0.07, 0.35, 100, 90, 125),
    95: (0.08, 0.50, 100, 90, 140),
    96: (0.12, 0.50, 100, 80, 140),
    97: (0.08, 0.25, 100, 90, 120),
    104: (0.04, 0.15, 100, 96, 108),
    105: (0.05, 0.20, 100, 95, 115),
    106: (0.04, 0.20, 100, 95, 110),
    108: (0.10, 0.40, 100, 100, 130),
    112: (0.12, 0.70, 100, 80, 125),
    113: (0.14, 0.80, 100, 80, 130),
    114: (0.12, 0.60, 100, 80, 125),
    115: (0.10, 0.80, 100, 80, 130),
    116: (0.12, 0.70, 100, 80, 125),
    117: (0.10, 0.50, 100, 80, 125),
    118: (0.12, 0.70, 100, 80, 130),
}

EVENT_SPEC_E3 = {
    15: {"p": 0.05, "days": (7, 7), "cooldown": 8, "severity": 2, "city": True, "kind": "calendar"},
    16: {"p": 0.04, "days": (7, 21), "cooldown": 8, "severity": 2, "city": True, "kind": "weather"},
    17: {"p": 0.06, "days": (7, 21), "cooldown": 6, "severity": 2, "city": True, "kind": "disaster"},
    18: {"p": 0.02, "days": (14, 28), "cooldown": 20, "severity": 3, "city": True, "kind": "weather"},
    31: {"p": 1.0, "days": (7, 7), "cooldown": 51, "severity": 2, "city": False, "kind": "calendar", "fixed_week": 26},
    32: {"p": 1.0, "days": (3, 3), "cooldown": 51, "severity": 2, "city": False, "kind": "calendar", "fixed_week": 35},
    36: {"p": 0.08, "days": (7, 7), "cooldown": 8, "severity": 1, "city": False, "kind": "calendar"},
    49: {"p": 0.05, "days": (1, 2), "cooldown": 2, "severity": 2, "city": True, "kind": "labor"},
    53: {"p": 0.03, "days": (7, 14), "cooldown": 12, "severity": 2, "city": True, "kind": "labor"},
    83: {"p": 0.01, "days": (84, 84), "cooldown": 40, "severity": 3, "city": True, "kind": "competition"},
    84: {"p": 0.03, "days": (14, 35), "cooldown": 12, "severity": 3, "city": True, "kind": "competition"},
    87: {"p": 0.02, "days": (56, 112), "cooldown": 24, "severity": 2, "city": True, "kind": "competition"},
    88: {"p": 0.015, "days": (28, 28), "cooldown": 30, "severity": 3, "city": True, "kind": "property"},
    97: {"p": 0.02, "days": (14, 21), "cooldown": 20, "severity": 3, "city": False, "kind": "finance"},
    98: {"p": 0.02, "days": (14, 21), "cooldown": 16, "severity": 3, "city": False, "kind": "finance"},
    107: {"p": 0.015, "days": (28, 28), "cooldown": 26, "severity": 4, "city": True, "kind": "labor"},
    108: {"p": 0.03, "days": (7, 7), "cooldown": 10, "severity": 2, "city": True, "kind": "labor"},
    109: {"p": 0.03, "days": (1, 3), "cooldown": 10, "severity": 3, "city": False, "kind": "regulation"},
    110: {"p": 0.02, "days": (365, 365), "cooldown": 80, "severity": 2, "city": True, "kind": "regulation"},
    111: {"p": 0.02, "days": (28, 56), "cooldown": 20, "severity": 2, "city": False, "kind": "regulation"},
    115: {"p": 0.03, "days": (21, 21), "cooldown": 16, "severity": 2, "city": False, "kind": "trend"},
    118: {"p": 0.04, "days": (14, 21), "cooldown": 10, "severity": 2, "city": False, "kind": "trend"},
    119: {"p": 0.04, "days": (14, 28), "cooldown": 8, "severity": 2, "city": True, "kind": "trend"},
}

# 17 is a city disaster for the one-per-city rule (milder than ice).
E3_DISASTER_RANK = {17: 4, 83: 3}

GROCERY_WEIGHT = {
    "grocery": 4,
    "produce": 2,
    "meat_dairy": 2,
    "frozen": 1,
    "household": 1,
    "health_beauty": 1,
    "pharmacy": 1,
    "electronics": 1,
    "clothing": 1,
    "toys": 1,
    "home_garden": 1,
    "sporting": 1,
    "seasonal": 1,
}


def starting_priors(values: dict[str, int]) -> dict[str, int]:
    values["19:seattle"] = 108
    values["19:naperville"] = 110
    values["51:seattle"] = 110
    values["108:seattle"] = 110
    values["53:evansville"] = 108
    values["53:seattle"] = 108
    values["53:houston"] = 108
    values["53:las_vegas"] = 108
    values["53:naperville"] = 108
    return values


def apply_e3_cycles(state: GameState, week: int, day: int) -> None:
    from open_late.economy import (
        CITIES,
        _clamp,
        _cycle_boost,
        _key,
        _value,
        economy_difficulty,
        week_of_year,
    )

    if economy_difficulty(state) == "off":
        return
    eco = state.economy
    year_week = week % 52
    # 27 refund, 28 grill, 29 winter, 30 spring, 33 new year, 34 sweetheart, 35 harvest night.
    eco.values["27"] = 100 + _cycle_boost(year_week, 8, 14, 10)
    eco.values["28"] = 100 + _cycle_boost(year_week, 22, 32, 12)
    eco.values["29"] = 100 + _cycle_boost((year_week - 48) % 52, 0, 12, 12) if year_week >= 48 or year_week <= 8 else 100
    # Winter comfort peaks weeks 48–8, which wraps the year.
    if year_week >= 48 or year_week <= 8:
        # Distance into the window.
        eco.values["29"] = 100 + 12
        if year_week in (47, 9):
            eco.values["29"] = 106
    eco.values["30"] = 100 + _cycle_boost(year_week, 12, 20, 16)
    if year_week in (1, 2):
        eco.values["33"] = 90
    else:
        eco.values["33"] = 100
    eco.values["34"] = 100 + _cycle_boost(year_week, 7, 7, 8)
    eco.values["35"] = 100 + _cycle_boost(year_week, 43, 44, 14)
    eco.values["31"] = 1 if year_week == 26 else 0
    eco.values["32"] = 1 if year_week == 35 else 0
    # 15 tourism pulse by city.
    amp = {"las_vegas": 18, "seattle": 8}
    for city in CITIES:
        a = amp.get(city, 2)
        # Las Vegas summer/holiday bump around weeks 22–35 and 47–52.
        peak = 28 if city != "las_vegas" else (28 if 22 <= year_week <= 35 or year_week >= 47 else 8)
        boost = int(round(a * (0.6 if 22 <= year_week <= 35 or year_week >= 47 or year_week <= 2 else 0.2)))
        if city == "las_vegas" and (22 <= year_week <= 35 or year_week >= 47):
            boost = a
        elif city == "seattle" and 22 <= year_week <= 36:
            boost = a
        eco.values[_key(15, city)] = _clamp(100 + boost, 60, 160)
        # 22 late-hour: weekly average; daily overlay reads DOW.
        eco.values[_key(22, city)] = 100 + (12 if city == "las_vegas" else 4)
        # 52 summer youth.
        eco.values[_key(52, city)] = 100 + _cycle_boost(year_week, 22, 32, 10)
    # 86 mild 26-week cycle.
    eco.values["86"] = _clamp(_value(state, 86) + int(round(4 * __import__("math").cos(2 * 3.1415926535 * year_week / 26))), 80, 130)
    # 103 float timing: payday week before Sunday is easier.
    from open_late.economy import is_payday, is_harvest_card_week

    eco.values["103"] = 108 if is_payday(day) or is_payday(day + 1) else 96
    if is_harvest_card_week(day):
        eco.values["103"] = max(eco.values["103"], 104)
    # 36 default 0 unless an event is active.
    if not _active(state, 36):
        eco.values["36"] = 0


def apply_e3_links(state: GameState, week: int, sigma_mult: float, rng: random.Random) -> None:
    from open_late.economy import (
        CITIES,
        _clamp,
        _key,
        _value,
        active_events,
        city_of,
        store_ids_for,
    )

    eco = state.economy
    prev = lambda fid, city=None: _value(state, fid, city, previous=True)
    now = lambda fid, city=None: _value(state, fid, city, previous=False)

    # 96 credit spread: 0.6 × policy rate.
    eco.values["96"] = _clamp(0.40 * now(96) + 0.60 * prev(1), 80, 140)
    # 13 already walked; pull housing 19 and inverted unemployment.
    for city in CITIES:
        housing = now(19, city)
        eco.values[_key(19, city)] = _clamp(0.70 * housing + 0.30 * prev(9), 80, 150)
        eco.values[_key(13, city)] = _clamp(
            0.30 * now(13, city) + 0.40 * (200 - now(12, city)) + 0.30 * now(19, city),
            80,
            150,
        )
        # 12 also feels anchor employer 18 in Evansville and Houston.
        if city in ("evansville", "houston"):
            eco.values[_key(12, city)] = _clamp(0.70 * now(12, city) + 0.30 * (200 - now(18, city)), 70, 150)
        # 20 energy: 0.45 × diesel.
        eco.values[_key(20, city)] = _clamp(0.55 * now(20, city) + 0.45 * prev(6), 70, 160)
        # 47 hire tightness: inverted unemployment + activity.
        eco.values[_key(47, city)] = _clamp(
            0.30 * now(47, city) + 0.50 * (200 - now(12, city)) + 0.20 * now(8),
            70,
            150,
        )
        # 91 utilities: 0.5 × energy + heat/cold.
        heat = max(0, now(37, city) - 100)
        cold = max(0, now(38, city) - 100)
        eco.values[_key(91, city)] = _clamp(0.50 * now(91, city) + 0.50 * now(20, city) + 0.15 * (heat + cold), 80, 150)
        # 88 rent pressure: 0.3 × housing, sticky except event.
        eco.values[_key(88, city)] = _clamp(0.70 * now(88, city) + 0.30 * now(19, city), 90, 130)
        # 54 night premium.
        late = now(22, city)
        mu = 108 if city == "las_vegas" else 100
        eco.values[_key(54, city)] = _clamp(mu + 0.4 * (late - 100) + 0.3 * (now(13, city) - 100), 100, 125)
        # 93 parking follows road work.
        if _active(state, 17, city):
            eco.values[_key(93, city)] = _clamp(now(93, city) + 8, 90, 120)
    # 95 build-out inflation (city-scoped).
    for city in CITIES:
        eco.values[_key(95, city)] = _clamp(0.50 * now(95, city) + 0.30 * prev(4) + 0.20 * prev(77), 90, 140)
    # 101 FX lag-1 import cost.
    eco.values["101"] = _clamp(0.20 * now(101) + 0.80 * prev(10), 80, 150)
    # 113 value/trade-down.
    eco.values["113"] = _clamp(0.30 * now(113) + 0.40 * (200 - now(5)) + 0.30 * now(4), 80, 130)
    # 117 house-brand willingness follows trade-down.
    eco.values["117"] = _clamp(0.60 * now(117) + 0.40 * now(113), 80, 125)
    # 116 outdoor mood: seasonal 28/30 prior.
    eco.values["116"] = _clamp(0.50 * now(116) + 0.25 * now(28) + 0.25 * now(30), 80, 125)
    # Store-scoped links.
    for store_id in store_ids_for(state):
        city = city_of(state, store_id)
        # 56 wage gap: player wage vs floor × 13/100.
        eco.values[_key(56, store_id)] = _wage_gap(state, store_id, city)
        # 48 turnover: 0.4×56 + 0.3×47.
        eco.values[_key(48, store_id)] = _clamp(
            0.30 * now(48, store_id) + 0.40 * now(56, store_id) + 0.30 * now(47, city),
            70,
            150,
        )
        # 49 weather no-shows.
        weather = max(now(37, city) - 115, now(38, city) - 115, 30 if _active(state, 40, city) else 0, 0)
        noshow = 0.5 * max(0, weather) / 2
        if _active(state, 49, city) or _active(state, 40, city):
            noshow = max(noshow, 8)
        eco.values[_key(49, store_id)] = max(0, min(25, int(round(noshow))))
        # 50 overtime: hours over 8 + peaks + tightness.
        span = _hours(state, store_id)
        ot = 100 + max(0, span - 8) * 4 + (8 if now(26) >= 110 or now(31) or now(32) else 0)
        ot += (now(47, city) - 100) * 0.2
        eco.values[_key(50, store_id)] = _clamp(ot, 100, 140)
        # 99 / 100 / 102 / 120 / 98 computed from books.
        eco.values[_key(99, store_id)] = _working_capital(state)
        eco.values[_key(100, store_id)] = _inventory_carrying(state)
        short = 100 + min(40, int(getattr(state.flags, "shortfalls", 0) or 0) * 15)
        short = _clamp(0.5 * short + 0.5 * now(96), 100, 160)
        eco.values[_key(102, store_id)] = short
        score = float(getattr(state, "review_score", 4.2) or 4.2)
        eco.values[_key(120, store_id)] = _clamp(80 + (score - 1.0) * 10, 80, 120)
        eco.values[_key(98, store_id)] = _clamp(0.5 * now(99, store_id) + 0.5 * now(96), 80, 130)
        # 55 training quality improves if someone is on training.
        training = any(getattr(person, "assignment", "") == "training" and person.employed for person in state.staff)
        trained = now(55, store_id) + (4 if training else -1)
        eco.values[_key(55, store_id)] = _clamp(trained, 80, 120)
        # 90 insurance jumps after 41/44/45.
        ins = now(90, store_id)
        if _active(state, 41, city) or _active(state, 44) or _active(state, 45, city):
            ins = max(ins, 118)
        eco.values[_key(90, store_id)] = _clamp(ins, 90, 140)
        # 92 fixture wear jumps after wind.
        wear = now(92, store_id)
        if _active(state, 45, city):
            wear = max(wear, 118)
        eco.values[_key(92, store_id)] = _clamp(wear, 90, 130)
    # Bag rule 110 steps packaging 62.
    if _active(state, 110):
        eco.values["62"] = _clamp(now(62) + 6, 80, 140)


def sync_rival(state: GameState, week: int, rng: random.Random) -> None:
    """Share one rival object with factors 80–84. No-op when off (caller checks)."""
    from open_late.economy import _clamp, _key, _value, active_events, event_p_mult, store_ids_for, city_of, force_event, cooldown_clear

    eco = state.economy
    competitor = int(getattr(state.flags, "competitor", 0) or 0)
    for store_id in store_ids_for(state):
        # 81 extends flags.competitor with a residual walk already taken.
        # A live Sunday entry sets flags.competitor to 34; hold that heat so the
        # walk cannot blend a new entry back under the notice line the same week.
        walked = _value(state, 81, store_id)
        heat = _clamp(0.55 * walked + 0.45 * competitor, 0, 100)
        if competitor >= 28:
            heat = _clamp(max(heat, competitor), 0, 100)
        eco.values[_key(81, store_id)] = heat
        # 80 extends rival.price_index.
        price = int(getattr(state.rival, "price_index", 100) or 100)
        walked_p = _value(state, 80, store_id)
        index = _clamp(0.50 * walked_p + 0.50 * price, 86, 120)
        war = active_events(state, factor_id=84, city_id=city_of(state, store_id))
        if war:
            off = int(war[0].get("intensity") or 12)
            index = _clamp(index - off, 86, 120)
            eco.values[_key(84, city_of(state, store_id))] = off
        eco.values[_key(80, store_id)] = index
    # Write back the home-store view so _traffic / sale chance stay in sync.
    home = store_ids_for(state)[0] if store_ids_for(state) else "evansville"
    state.flags.competitor = int(_value(state, 81, home))
    state.rival.price_index = int(_value(state, 80, home))
    # Focus rotation every 4–8 weeks, grocery-weighted.
    period = 4 + (week % 5)
    if week % period == 0 or not getattr(state.rival, "focus", ""):
        picks = []
        weights = []
        for dept, weight in GROCERY_WEIGHT.items():
            picks.append(dept)
            weights.append(weight)
        # rng.choices in 3.11+
        total = sum(weights)
        roll = rng.random() * total
        acc = 0.0
        choice = "grocery"
        for dept, weight in zip(picks, weights):
            acc += weight
            if roll <= acc:
                choice = dept
                break
        state.rival.focus = choice
    eco.values["82"] = 1
    # War rolls when heat is high (handled in event roll with a p gate too).
    p_mult = event_p_mult(state)
    if state.flags.competitor >= 28 and p_mult and cooldown_clear(state, 84, "evansville"):
        # Actual roll happens in _roll_e3_events with p raised when 81 is high.
        pass


def _roll_fixed_calendar(state: GameState, week: int) -> None:
    """31 and 32 fire on a fixed week of the year, not a random roll."""
    from open_late.economy import EVENT_SPEC, force_event, week_of_year, cooldown_clear, event_p_mult

    if event_p_mult(state) <= 0:
        return
    year_week = week % 52
    if year_week == 26 and cooldown_clear(state, 31):
        force_event(state, 31, days=7, start_day=state.day + 1, severity=2)
    if year_week == 35 and cooldown_clear(state, 32):
        force_event(state, 32, days=3, start_day=state.day + 1, severity=2)


def should_roll_war(state: GameState, city: str) -> bool:
    from open_late.economy import _value, city_of, store_ids_for

    for store_id in store_ids_for(state):
        if city_of(state, store_id) == city and _value(state, 81, store_id) >= 28:
            return True
    return False


def apply_e3_demand(state: GameState, store_id: str, department: str, base: float) -> float:
    """Stack E3 calendar, trends, competition, tourism onto an already-live demand mult."""
    from open_late.economy import _value, city_of, active_events, economy_difficulty

    if economy_difficulty(state) == "off":
        return base
    city = city_of(state, store_id)
    delta = 0.0
    # Seasonal department lifts.
    if department in ("electronics", "home_garden", "clothing", "sporting") and _value(state, 27) > 100:
        delta += (_value(state, 27) - 100) / 100 * 0.8
    if department in ("meat_dairy", "produce", "frozen", "sporting", "seasonal") and _value(state, 28) > 100:
        delta += (_value(state, 28) - 100) / 100 * 0.7
    if department in ("frozen", "grocery", "pharmacy", "seasonal", "household") and _value(state, 29) > 100:
        delta += (_value(state, 29) - 100) / 100 * 0.7
    if department in ("home_garden", "household", "sporting") and _value(state, 30) > 100:
        delta += (_value(state, 30) - 100) / 100 * 0.8
    if _value(state, 33) < 100:
        if department in ("household", "health_beauty"):
            delta += 0.04
        else:
            delta -= (100 - _value(state, 33)) / 200
    if department in ("seasonal", "grocery", "health_beauty") and _value(state, 34) > 100:
        delta += (_value(state, 34) - 100) / 100
    if department in ("seasonal", "grocery", "toys") and _value(state, 35) > 100:
        delta += (_value(state, 35) - 100) / 100 * 0.8
    # Trends.
    fresh = (_value(state, 112) - 100) / 100
    if department in ("produce", "meat_dairy", "health_beauty"):
        delta += fresh * 0.5
    if department in ("frozen", "grocery"):
        delta -= fresh * 0.25
    trade = (_value(state, 113) - 100) / 100
    if department in ("grocery", "frozen"):
        delta += trade * 0.4
    if department in ("electronics", "clothing", "seasonal"):
        delta -= trade * 0.4
    cook = (_value(state, 114) - 100) / 100
    if department in ("grocery", "produce"):
        delta += cook * 0.4
    if department == "frozen":
        delta -= cook * 0.3
    if department == "electronics":
        delta += (_value(state, 115) - 100) / 100 * 0.6
    if department in ("sporting", "home_garden", "produce"):
        delta += (_value(state, 116) - 100) / 100 * 0.4
    if department in ("pharmacy", "health_beauty"):
        delta += (_value(state, 118) - 100) / 100 * 0.5
    # Tourism mix.
    tour = (_value(state, 15, city) - 100) / 100
    if department in ("seasonal", "electronics", "clothing", "pharmacy"):
        delta += tour * 0.35
    # Northline focus and war: demand − on the focused dept, 50% on neighbors.
    focus = getattr(state.rival, "focus", "") or ""
    heat = _value(state, 81, store_id)
    if heat >= 18 and focus:
        if department == focus:
            delta -= 0.10 + min(0.08, heat / 800)
            war = _value(state, 84, city)
            if war or active_events(state, factor_id=84, city_id=city):
                delta -= 0.08
        # nearby 50%
        elif focus == "grocery" and department in ("produce", "meat_dairy", "household"):
            delta -= 0.05
    if department in ("electronics", "toys", "sporting", "clothing"):
        delta -= (_value(state, 86) - 100) / 100 * 0.35
        if getattr(state, "mode", "") == "online":
            delta -= (_value(state, 86) - 100) / 100 * 0.2
    # Local specialist 87, fad 119, inspection 109, pharmacy scarcity 53.
    for event in active_events(state, factor_id=87, city_id=city):
        if (event.get("department") or "produce") == department:
            delta -= 0.12
    for event in active_events(state, factor_id=119, city_id=city):
        if (event.get("department") or "") == department:
            delta += (int(event.get("intensity") or 20)) / 100
    if active_events(state, factor_id=109, store_id=store_id) and department in ("pharmacy", "grocery", "produce"):
        delta -= 0.15
    if department == "pharmacy" and _value(state, 53, city) >= 120:
        # Demand wasted if the counter is thin; Naperville has no counter.
        door = next((item for item in (state.doors or []) if item.id == store_id), None)
        if door is not None and not getattr(door, "allows_intense", True):
            delta -= 0.10
        elif _value(state, 53, city) >= 135:
            delta -= 0.06
    # Anchor 18: Evansville/Houston demand.
    if city in ("evansville", "houston"):
        delta += (_value(state, 18, city) - 100) / 100 * 0.25
    # Midyear holiday grocery lift.
    if _value(state, 31) and department in ("grocery", "meat_dairy", "seasonal"):
        delta += 0.08
    if _value(state, 32) and department in ("grocery", "frozen", "sporting"):
        delta += 0.06
    return max(0.0, base + delta)


def apply_e3_visits(state: GameState, store_id: str, base: float) -> float:
    from open_late.economy import _value, city_of, active_events, is_payday, economy_difficulty

    if economy_difficulty(state) == "off":
        return base
    city = city_of(state, store_id)
    mult = base
    tour = _value(state, 15, city) / 100.0
    mult *= 0.85 + 0.15 * tour
    access = _value(state, 16, city) / 100.0
    mult *= 0.9 + 0.1 * access
    if active_events(state, factor_id=17, city_id=city) or active_events(state, factor_id=16, city_id=city):
        ev = (active_events(state, factor_id=17, city_id=city) or active_events(state, factor_id=16, city_id=city))[0]
        cut = 0.08 + min(0.12, int(ev.get("intensity") or 2) * 0.04)
        mult *= 1.0 - cut
    # Late-hour: only if the door is actually open late.
    close = _close_hour(state, store_id)
    dow = (state.day - 1) % 7  # 0=Mon
    if close >= 21:
        amp = 0.12 if city == "las_vegas" and dow in (4, 5) else 0.04
        mult *= 1.0 + amp * ((_value(state, 22, city) - 100) / 20 if _value(state, 22, city) else 1)
    if _value(state, 31):
        mult *= 1.12
    if _value(state, 32) and city in ("las_vegas", "houston"):
        mult *= 1.08
    if _value(state, 33) < 100:
        mult *= 0.95
    # Competition visits.
    heat = _value(state, 81, store_id)
    # flags.competitor already sits in _traffic; add banner/war only.
    if active_events(state, factor_id=83, city_id=city):
        ev = active_events(state, factor_id=83, city_id=city)[0]
        # 12-week fade.
        span = max(1, int(ev.get("day_end") or 1) - int(ev.get("day_start") or 1))
        spent = max(0, state.day - int(ev.get("day_start") or state.day))
        fade = max(0.0, 1.0 - spent / span)
        cut = 0.08 + 0.07 * fade
        mult *= 1.0 - cut
    park = _value(state, 93, store_id)
    if park and park != 100:
        mult *= 0.95 + 0.05 * (park / 100.0) if park <= 100 else 1.0 - (park - 100) / 400
    trust = _value(state, 120, store_id)
    if trust and trust != 100:
        mult *= 1.0 + (trust - 100) / 500.0
    noshow = _value(state, 49, store_id)
    if noshow:
        # Coverage gaps show up as walked/lost staff more than raw door count,
        # but a severe no-show week still trims visits slightly.
        mult *= 1.0 - min(0.08, noshow / 400)
    return max(0.0, mult)


def campaign_lift_mult(state: GameState, store_id: str | None = None) -> float:
    """High ad clutter (85) and labeling rules (111) fade campaign lift. Identity at 100 / off."""
    from open_late.economy import _value, city_of, active_events, economy_difficulty, store_ids_for

    if economy_difficulty(state) == "off" or not getattr(state, "campaign", None):
        return 1.0
    store_id = store_id or (store_ids_for(state)[0] if store_ids_for(state) else "evansville")
    city = city_of(state, store_id)
    clutter = _value(state, 85, city)
    # 100 = no fade; 140 = heavy fade of the extra lift.
    fade = 1.0 - max(0, clutter - 100) / 200
    if active_events(state, factor_id=111) and getattr(state.campaign, "tone", "") == "bold":
        fade *= 0.85
    return max(0.5, fade)


def labor_mult(state: GameState, store_id: str) -> float:
    from open_late.economy import _value, city_of, active_events, economy_difficulty, CAP_MULT, _cap_mult

    if economy_difficulty(state) == "off":
        return 1.0
    city = city_of(state, store_id)
    raw = 100.0
    raw += (_value(state, 13, city) - 100) * 0.35
    raw += (_value(state, 50, store_id) - 100) * 0.30
    raw += (_value(state, 47, city) - 100) * 0.15
    raw += (_value(state, 105) - 100) * 0.40
    if _close_hour(state, store_id) >= 21:
        raw += (_value(state, 54, city) - 100) * 0.25
    if city == "seattle" or (state.doors and any(d.id == store_id and getattr(d, "fair_workweek", False) for d in state.doors)):
        raw += (_value(state, 108, city) - 100) * 0.30
        raw += (_value(state, 51, city) - 100) * 0.15
    if active_events(state, factor_id=107, city_id=city):
        ev = active_events(state, factor_id=107, city_id=city)[0]
        raw += int(ev.get("intensity") or 4)
    youth = _value(state, 52, city)
    raw -= max(0, youth - 100) * 0.15
    cap = LABOR_CAP * CAP_MULT[economy_difficulty(state)]
    from open_late.economy import apply_player_bias

    return apply_player_bias(_cap_mult(raw, cap) if cap else 1.0, helpful=False, difficulty=economy_difficulty(state), cap=cap)


def rent_mult(state: GameState, store_id: str) -> float:
    from open_late.economy import _value, city_of, active_events, economy_difficulty, CAP_MULT, _cap_mult

    if economy_difficulty(state) == "off":
        return 1.0
    city = city_of(state, store_id)
    eco = state.economy
    sticky = getattr(eco, "rent_index", None) or {}
    applied = getattr(eco, "rent_week", None) or {}
    from open_late.economy import week_id

    week = week_id(state.day)
    event = bool(active_events(state, factor_id=88, city_id=city))
    raw = 100.0
    raw += (_value(state, 88, city) - 100) * 0.70
    raw += (_value(state, 89, city) - 100) * 0.40  # CAM 0–8-ish
    raw += (_value(state, 92, store_id) - 100) * 0.15
    raw += (_value(state, 93, store_id) - 100) * 0.10
    if store_id == "evansville":
        raw += (_value(state, 94, "evansville") - 100) * 0.50
    cap = (RENT_EVENT_CAP if event else RENT_CAP) * CAP_MULT[economy_difficulty(state)]
    index = int(round(_cap_mult(raw, cap) * 100)) if cap else 100
    # Sticky: apply at most once per 4 weeks, except a reassessment event.
    if not event and store_id in sticky and week - int(applied.get(store_id, -99)) < 4:
        index = int(sticky[store_id])
    else:
        sticky[store_id] = index
        applied[store_id] = week
        eco.rent_index = sticky
        eco.rent_week = applied
    from open_late.economy import apply_player_bias

    return apply_player_bias(index / 100.0, helpful=False, difficulty=economy_difficulty(state), cap=cap)


def utilities_mult(state: GameState, store_id: str) -> float:
    from open_late.economy import _value, city_of, economy_difficulty, _cap_mult, CAP_MULT

    if economy_difficulty(state) == "off":
        return 1.0
    city = city_of(state, store_id)
    raw = 0.50 * _value(state, 91, city) + 0.50 * _value(state, 20, city)
    from open_late.economy import apply_player_bias

    cap = 0.20 * CAP_MULT[economy_difficulty(state)]
    return apply_player_bias(_cap_mult(raw, cap), helpful=False, difficulty=economy_difficulty(state), cap=cap)


def insurance_mult(state: GameState, store_id: str) -> float:
    from open_late.economy import _value, economy_difficulty, _cap_mult, CAP_MULT

    if economy_difficulty(state) == "off":
        return 1.0
    from open_late.economy import apply_player_bias

    cap = 0.20 * CAP_MULT[economy_difficulty(state)]
    return apply_player_bias(_cap_mult(_value(state, 90, store_id), cap), helpful=False, difficulty=economy_difficulty(state), cap=cap)


def interest_mult(state: GameState) -> float:
    from open_late.economy import _value, economy_difficulty, store_ids_for, _cap_mult, CAP_MULT

    if economy_difficulty(state) == "off":
        return 1.0
    store_id = store_ids_for(state)[0] if store_ids_for(state) else "evansville"
    raw = 0.70 * _value(state, 96) + 0.30 * _value(state, 102, store_id)
    from open_late.economy import apply_player_bias

    cap = INTEREST_CAP * CAP_MULT[economy_difficulty(state)]
    return apply_player_bias(_cap_mult(raw, cap), helpful=False, difficulty=economy_difficulty(state), cap=cap)


def card_fee_mult(state: GameState, store_id: str) -> float:
    from open_late.economy import _value, active_events, economy_difficulty, _cap_mult, CAP_MULT

    if economy_difficulty(state) == "off":
        return 1.0
    raw = _value(state, 97)
    if active_events(state, factor_id=97):
        raw = min(120, raw + 6)
    cap = CARD_CAP * CAP_MULT[economy_difficulty(state)]
    from open_late.economy import apply_player_bias

    return apply_player_bias(_cap_mult(raw, cap) if cap else 1.0, helpful=False, difficulty=economy_difficulty(state), cap=cap)


def walked_mult(state: GameState, store_id: str) -> float:
    """>1 means more guests walk (conversion falls). Identity at 1.0 when off."""
    from open_late.economy import _value, economy_difficulty

    if economy_difficulty(state) == "off":
        return 1.0
    gap = _value(state, 56, store_id)
    noshow = _value(state, 49, store_id)
    train = _value(state, 55, store_id)
    extra = 0.0
    if gap > 110:
        extra += (gap - 110) / 200
    if noshow:
        extra += noshow / 200
    if train and train < 100:
        extra += (100 - train) / 400
    return 1.0 + min(0.20, extra)


def opening_cost_mult(state: GameState, city_id: str) -> float:
    from open_late.economy import _value, economy_difficulty

    if economy_difficulty(state) == "off":
        return 1.0
    return max(0.9, min(1.4, _value(state, 95, city_id) / 100.0))


def credit_available_mult(state: GameState) -> float:
    from open_late.economy import active_events, _value, economy_difficulty, store_ids_for

    if economy_difficulty(state) == "off":
        return 1.0
    if active_events(state, factor_id=98):
        return 0.55
    store_id = store_ids_for(state)[0] if store_ids_for(state) else "evansville"
    tight = _value(state, 98, store_id)
    if tight > 110:
        return max(0.7, 1.0 - (tight - 100) / 250)
    return 1.0


def adjust_money(state: GameState, kind: str, amount: int, store_id: str | None = None) -> int:
    from open_late.economy import economy_difficulty, store_ids_for

    if amount == 0 or economy_difficulty(state) == "off":
        return amount
    store_id = store_id or (store_ids_for(state)[0] if store_ids_for(state) else "evansville")
    if kind == "rent":
        # Corporate chain: weight by door rents if store_id is None already defaulted.
        if store_id == "__chain__":
            return _adjust_chain(state, "rent", amount)
        return max(0, int(round(amount * rent_mult(state, store_id))))
    if kind == "labor":
        if store_id == "__chain__":
            return _adjust_chain(state, "labor", amount)
        return max(0, int(round(amount * labor_mult(state, store_id))))
    if kind == "payroll_tax":
        # Employer load 105 already sits inside labor_mult; don't double the wage
        # bill, only scale the tax if 105 moved.
        from open_late.economy import _value

        return max(0, int(round(amount * (_value(state, 105) / 100.0))))
    if kind == "utilities":
        if store_id == "__chain__":
            return _adjust_chain(state, "utilities", amount)
        return max(0, int(round(amount * utilities_mult(state, store_id))))
    if kind == "insurance":
        if store_id == "__chain__":
            return _adjust_chain(state, "insurance", amount)
        return max(0, int(round(amount * insurance_mult(state, store_id))))
    if kind == "interest":
        return max(0, int(round(amount * interest_mult(state))))
    return amount


def adjust_sunday_bills(state, rent, payroll, payroll_tax, insurance, utilities, interest, *, store_id=None):
    from open_late.economy import economy_difficulty

    if economy_difficulty(state) == "off":
        return rent, payroll, payroll_tax, insurance, utilities, interest
    tag = store_id or ("__chain__" if getattr(state, "mode", "") == "corporate" else "evansville")
    from open_late.economy_e4 import apply_bill_grace

    rent_adj = apply_bill_grace(state, rent, adjust_money(state, "rent", rent, tag))
    labor_adj = apply_bill_grace(state, payroll, adjust_money(state, "labor", payroll, tag))
    tax_adj = apply_bill_grace(state, payroll_tax, adjust_money(state, "payroll_tax", payroll_tax, tag))
    ins_adj = apply_bill_grace(state, insurance, adjust_money(state, "insurance", insurance, tag))
    util_adj = apply_bill_grace(state, utilities, adjust_money(state, "utilities", utilities, tag))
    int_adj = apply_bill_grace(state, interest, adjust_money(state, "interest", interest, tag))
    return rent_adj, labor_adj, tax_adj, ins_adj, util_adj, int_adj


def _adjust_chain(state: GameState, kind: str, amount: int) -> int:
    from open_late.economy import store_ids_for

    ids = store_ids_for(state)
    if not ids:
        return amount
    if kind == "rent":
        fn = rent_mult
    elif kind == "labor":
        fn = labor_mult
    elif kind == "utilities":
        fn = utilities_mult
    else:
        fn = insurance_mult
    avg = sum(fn(state, item) for item in ids) / len(ids)
    return max(0, int(round(amount * avg)))


def apply_wage_floor_event(state: GameState) -> None:
    """On a 107 start, bump the city's wage_floor once (live games only)."""
    from open_late.economy import active_events, economy_difficulty, city_of

    if economy_difficulty(state) == "off":
        return
    if not (getattr(state, "doors", None) or []):
        events = active_events(state, factor_id=107, city_id="evansville")
        if events and not events[0].get("applied_floor"):
            # Shop payroll is already * CREW_MULT, and labor_mult also adds
            # the event intensity for the 28-day window. Applying the full
            # percentage to every wage is a permanent, supercenter-scaled
            # swing (seed 47's 6% raise alone was ~$9k/week). Cap the
            # once-only bump; the temporary labor_mult effect is unchanged.
            pct = int(events[0].get("intensity") or 4)
            pct = min(max(pct, 0), 2)
            events[0]["applied_floor"] = True
            if pct:
                for person in state.staff:
                    if person.employed:
                        person.wage = int(round(person.wage * (100 + pct) / 100))
        return
    for door in getattr(state, "doors", []) or []:
        events = active_events(state, factor_id=107, city_id=door.id)
        if not events:
            continue
        ev = events[0]
        if ev.get("applied_floor"):
            continue
        pct = int(ev.get("intensity") or 4)
        door.wage_floor = int(round(door.wage_floor * (100 + pct) / 100))
        ev["applied_floor"] = True
        from open_late.finance import SIZE_MULT

        lead_floor = max(1, int(door.wage_floor) // SIZE_MULT)
        for person in state.staff:
            if not person.employed or getattr(person, "door_id", "") != door.id:
                continue
            if person.wage >= int(door.wage_floor):
                person.wage = max(lead_floor, int(person.wage) // SIZE_MULT)
            elif person.wage < lead_floor:
                person.wage = lead_floor


def cost_fx_delta(state: GameState, department: str) -> float:
    """Import FX (101) soft add on imported depts, plus 110 bag rule already in 62."""
    from open_late.economy import _value, IMPORT_DEPTS, economy_difficulty

    if economy_difficulty(state) == "off":
        return 0.0
    if department in IMPORT_DEPTS:
        return (_value(state, 101) - 100) * 0.20
    return 0.0


def build_store_impact(state: GameState, store_id: str, days: int, pnl: dict) -> dict:
    """Cheap attribution from the current week card. No visit replay."""
    from open_late.economy import (
        DEPARTMENT_IDS,
        cost_mult,
        demand_mult,
        economy_difficulty,
        freight_mult,
        visits_mult,
        _value,
        city_of,
        FACTORS,
    )

    keys = ("sales", "cogs", "labor", "rent", "freight", "shrink", "card_fees", "pos_fees")
    from open_late.economy import week_id

    # Attribution uses the current live card. Days before the first live
    # card (the Monday after the first non-off Sunday tick) stay neutral so
    # an off week that just switched on Sunday still reports empty reasons.
    live_ticks = int(getattr(state.economy, "live_ticks", 0) or 0)
    last = state.day if state.phase in ("evening", "gameover") else state.day - 1
    live_from = (int(state.economy.last_week_id) - live_ticks + 1) * 7 + 8 if live_ticks else 10**9
    if economy_difficulty(state) == "off" or last < live_from:
        delta = {key: 0 for key in pnl}
        delta["store_id"] = pnl["store_id"]
        delta["name"] = pnl["name"]
        delta["days"] = pnl["days"]
        return {
            "store_id": store_id,
            "days": int(days),
            "pnl": pnl,
            "neutral_pnl": dict(pnl),
            "delta": delta,
            "reasons": [],
        }

    demands = [demand_mult(state, store_id, dept) for dept in DEPARTMENT_IDS]
    sales_m = visits_mult(state, store_id) * (sum(demands) / len(demands) if demands else 1.0)
    costs = [cost_mult(state, store_id, dept) for dept in DEPARTMENT_IDS]
    cost_m = sum(costs) / len(costs) if costs else 1.0
    fr_m = freight_mult(state, store_id)
    lab_m = labor_mult(state, store_id)
    r_m = rent_mult(state, store_id)
    card_m = card_fee_mult(state, store_id)
    # Shrink: noshow / thaw presence as a soft ratio from the live line vs 1.0
    sh_m = 1.0 + min(0.35, _value(state, 49, store_id) / 100)

    def invert(val: int, m: float) -> int:
        if not val or abs(m - 1.0) < 1e-9:
            return int(val)
        return int(round(val / m))

    neutral = dict(pnl)
    maps = {
        "sales": sales_m,
        "cogs": cost_m,
        "labor": lab_m,
        "rent": r_m,
        "freight": fr_m,
        "shrink": sh_m if pnl.get("shrink") else 1.0,
        "card_fees": card_m,
        "pos_fees": 1.0,
    }
    for key, m in maps.items():
        if key in neutral:
            neutral[key] = invert(int(pnl.get(key) or 0), m)
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
        if isinstance(pnl[key], int) and key in neutral:
            delta[key] = int(pnl[key]) - int(neutral[key])
    delta["store_id"] = pnl["store_id"]
    delta["name"] = pnl["name"]
    delta["days"] = pnl["days"]

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
        (46, "shrink", None),
        (49, "shrink", None),
        (59, "shrink", None),
    ]
    # Collect weighted |delta-from-100| per line, then scale dollars to the line delta.
    buckets: dict[str, list] = {}
    for fid, line, dept in factor_lines:
        val = _value(state, fid, city if fid in (11, 13, 15, 88, 89, 84) else (store_id if fid in (50, 80, 81, 94, 49) else None))
        if fid in (23, 31, 32, 46, 84, 107) and val in (0, 100) and not _active(state, fid, city):
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
        total_w = sum(item[2] for item in contribs) or 1
        allocated = 0
        for i, (fid, dept, weight, val) in enumerate(contribs):
            dollars = int(round(line_delta * weight / total_w))
            if i == len(contribs) - 1:
                dollars = line_delta - allocated
            allocated += dollars
            if dollars == 0:
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
    # Reconcile: reasons dollars per line should sum to delta[line] within $1 (exact after last-item fix).
    return {
        "store_id": store_id,
        "days": int(days),
        "pnl": pnl,
        "neutral_pnl": neutral,
        "delta": delta,
        "reasons": reasons,
    }


def factors_in_range(state: GameState) -> list[int]:
    """Return ids whose stored value sits outside the planned range (should be empty)."""
    from open_late.economy import FACTORS, CITIES, _value, store_ids_for

    bad = []
    for fid, info in FACTORS.items():
        low, high = info["range"]
        scope = info["scope"]
        if scope == "city":
            places = CITIES
        elif scope == "store":
            places = store_ids_for(state) or ["evansville"]
        else:
            places = [None]
        for place in places:
            val = _value(state, fid, place)
            if val < low or val > high:
                bad.append(fid)
                break
    return bad


def live_factor_ids() -> list[int]:
    from open_late.economy import FACTORS

    return [fid for fid in range(1, 121) if "Reserved" not in FACTORS[fid]["driver"]]


def live_factor_count() -> int:
    return len(live_factor_ids())


def category_counts() -> dict[str, int]:
    from open_late.economy import FACTORS

    counts: dict[str, int] = {}
    for fid in range(1, 121):
        cat = FACTORS[fid]["category"]
        counts[cat] = counts.get(cat, 0) + 1
    return counts


# --- helpers ---

def _active(state, factor_id, city=None, store_id=None):
    from open_late.economy import active_events

    return bool(active_events(state, factor_id=factor_id, city_id=city, store_id=store_id))


def _wage_gap(state, store_id, city) -> int:
    from open_late.economy import _clamp, _value

    floor = 290
    door = next((item for item in (state.doors or []) if item.id == store_id), None)
    if door is not None:
        floor = int(door.wage_floor or floor)
    wages = [person.wage for person in state.staff if person.employed and (not getattr(person, "door_id", None) or person.door_id == store_id)]
    if not wages:
        wages = [person.wage for person in state.staff if person.employed]
    if not wages:
        return 100
    avg = sum(wages) / len(wages)
    market = floor * (_value(state, 13, city) / 100.0)
    if market <= 0:
        return 100
    # High = player lags the market.
    gap = 100 * market / max(1.0, avg)
    return _clamp(gap, 70, 140)


def _working_capital(state) -> int:
    from open_late.economy import _clamp

    payables = sum(int(getattr(account, "payable", 0) or 0) for account in (state.supplier_accounts or []))
    inventory = 0
    for product_id, line in (state.stock or {}).items():
        product = state.products.get(product_id)
        if product is not None:
            inventory += int(product.cost) * int(line.on_hand or 0)
    cash = max(1, int(state.cash or 0))
    ratio = (payables + inventory) / cash
    # 1.0 books ≈ 100; stressed books climb toward 160.
    return _clamp(70 + ratio * 30, 70, 160)


def _inventory_carrying(state) -> int:
    from open_late.economy import _clamp, IMPORT_DEPTS

    cost = 0
    heavy = 0
    for product_id, line in (state.stock or {}).items():
        product = state.products.get(product_id)
        if product is None:
            continue
        line_cost = int(product.cost) * int(line.on_hand or 0)
        cost += line_cost
        if getattr(product, "department", "") in IMPORT_DEPTS or getattr(product, "department", "") == "clothing":
            heavy += line_cost
    return _clamp(80 + (cost + heavy) / 400, 80, 140)


def _hours(state, store_id) -> int:
    door = next((item for item in (state.doors or []) if item.id == store_id), None)
    if door is not None:
        return max(4, int(door.close_hour) - int(door.open_hour))
    return max(4, int(state.close_hour) - int(state.open_hour))


def _close_hour(state, store_id) -> int:
    door = next((item for item in (state.doors or []) if item.id == store_id), None)
    if door is not None:
        return int(door.close_hour)
    return int(state.close_hour)


def _payday_day(state) -> int:
    from open_late.economy import _value

    lag = int(_value(state, 36) or 0)
    return int(state.day) - max(0, min(2, lag))
