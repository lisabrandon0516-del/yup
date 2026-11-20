"""Cash rules shared by the resolver and the desk."""

from __future__ import annotations

from dataclasses import dataclass

from open_late.models import GameState, Product, Staff, StockLine

INTEREST_RATE = 0.02
# Visible supercenter size pack (E7a). BASE figures are the pre-pack shop.
# SIZE_MULT=15 is a real supercenter: rent, crews, starting cash, credit, and shelves.
# Hybrid traffic that matches this volume is E7b.
SIZE_MULT = 15
CREW_MULT = 15  # each named lead is a department crew of this many
CREDIT_LIMIT_BASE = 40_000
SHOP_RESERVE_BASE = 52_000
CALM_RESERVE_BASE = 68_000
STERN_RESERVE_BASE = 36_000
ONLINE_RESERVE_BASE = 45_000
UTILITY_PER_OPEN_HOUR_BASE = 190
INSURANCE_PER_DOOR_BASE = 350
INSURANCE_PER_WAREHOUSE_BASE = 200

def size_int(amount: int) -> int:
    return int(amount) * SIZE_MULT

CREDIT_LIMIT = size_int(CREDIT_LIMIT_BASE)
# Visible starting-cash lever. Off and standard share the same float;
# calm starts with more, stern with less. Inventory is paid separately
# at new_game, so these figures are the drawer after opening stock.
SHOP_RESERVE = size_int(SHOP_RESERVE_BASE)
CALM_RESERVE = size_int(CALM_RESERVE_BASE)
STERN_RESERVE = size_int(STERN_RESERVE_BASE)
ONLINE_RESERVE = size_int(ONLINE_RESERVE_BASE)
UTILITY_PER_OPEN_HOUR = size_int(UTILITY_PER_OPEN_HOUR_BASE)
INSURANCE_PER_DOOR = size_int(INSURANCE_PER_DOOR_BASE)
INSURANCE_PER_WAREHOUSE = size_int(INSURANCE_PER_WAREHOUSE_BASE)
CARD_FEE_PER_THOUSAND = 26
PAYROLL_TAX_PER_TEN_THOUSAND = 765
INCOME_TAX_PERCENT = 21
SIZE_ORDER = ("XS", "S", "M", "L", "XL")
SIZE_WEIGHTS = {"XS": 8, "S": 22, "M": 36, "L": 24, "XL": 10}



# E7e: leftover small-store money, scaled to the supercenter. Shop staff
# lead wages stay at lead rates; Sunday shop payroll already multiplies by
# CREW_MULT. These constants are the ones that were still 1x.
RIVAL_ENTRY_WEEK_SALES = size_int(6800)
RIVAL_ENTRY_MIN_DAY = 28  # a month of trading before Northline arrives
STABLE_MONTH_CASH = size_int(7000)
LABOR_BUDGET_DEFAULT = size_int(12_000)


def starting_reserve(mode: str, difficulty: str | None) -> int:
    """Drawer cash after opening inventory is paid. Documented difficulty lever."""
    if mode == "online":
        return ONLINE_RESERVE
    if difficulty == "calm":
        return CALM_RESERVE
    if difficulty == "stern":
        return STERN_RESERVE
    return SHOP_RESERVE


def interest_due(state: GameState) -> int:
    return int(round(state.credit_used * INTEREST_RATE))


# 2026 single-filer federal tax. A direct-deposit advice withholds this from the gross.
FEDERAL_STANDARD_DEDUCTION = 16_100
FEDERAL_BRACKETS = (
    (12_400, 10),
    (50_400, 12),
    (105_700, 22),
    (201_775, 24),
    (256_225, 32),
    (640_600, 35),
    (10**12, 37),
)
STATE_TAX_PER_TEN_THOUSAND = 295
COUNTY_TAX_PER_TEN_THOUSAND = 125
SOCIAL_SECURITY_WAGE_BASE = 184_500


def pay_ratio(state: GameState) -> tuple[int, int]:
    """Straight time through eight hours. Time and a half after that."""
    span = max(4, state.close_hour - state.open_hour)
    if span <= 8:
        return span, 8
    return 16 + 3 * (span - 8), 16


def week_hours(state: GameState) -> tuple[int, int]:
    """Regular hours, then overtime, for a five-day week at the shop's open hours."""
    span = max(4, state.close_hour - state.open_hour)
    return 5 * min(span, 8), 5 * max(0, span - 8)


def close_labor(state: GameState, report) -> tuple[int, int]:
    """Hours on the clock for the close, then hours past eight.

    A person marked off or absent does not count. Each named lead is a crew, the same crew the wage bill uses.
    """
    hours = 0
    overtime = 0
    absent = set(getattr(report, "noshow_ids", None) or [])
    assigned = getattr(report, "assigned", None) or {}
    for person in state.staff:
        if not person.employed:
            continue
        job = assigned.get(person.id, "off") if assigned else person.assignment
        if person.id in absent or job == "off":
            continue
        door = None
        if state.mode == "corporate" and person.door_id:
            door = next((item for item in state.doors if item.id == person.door_id), None)
        if door is not None:
            span = door.close_hour - door.open_hour
        else:
            span = state.close_hour - state.open_hour
        span = max(0, int(span))
        hours += span * CREW_MULT
        overtime += max(0, span - 8) * CREW_MULT
    return hours, overtime


def _span_ratio(span: int) -> tuple[int, int]:
    span = max(4, span)
    if span <= 8:
        return span, 8
    return 16 + 3 * (span - 8), 16


def lead_weekly(wage: int, wage_floor: int) -> int:
    """The door floor is already the crew's weekly cost. A lead who was set to that floor is paid once."""
    wage = int(wage)
    floor = int(wage_floor or 0)
    if floor >= SIZE_MULT and wage >= floor:
        return max(1, wage // SIZE_MULT)
    return wage


def gross_shares(state: GameState) -> dict[str, int]:
    """Each employed person's gross for the week. The shares add up to the Sunday wage bill."""
    people = [person for person in state.staff if person.employed]
    if state.mode == "corporate":
        shares: dict[str, int] = {}
        for person in people:
            if person.assignment == "off":
                shares[person.id] = 0
                continue
            door = next((item for item in state.doors if item.id == person.door_id), None)
            span = (door.close_hour - door.open_hour) if door is not None else max(4, state.close_hour - state.open_hour)
            numerator, denominator = _span_ratio(span)
            wage = lead_weekly(person.wage, door.wage_floor) if door is not None else int(person.wage)
            shares[person.id] = int(round(wage * numerator / denominator))
        return shares
    numerator, denominator = pay_ratio(state)
    shares = {person.id: int(round(person.wage * numerator / denominator)) for person in people}
    target = int(round(sum(person.wage for person in people) * numerator / denominator))
    drift = target - sum(shares.values())
    if people and drift:
        top = max(people, key=lambda person: (person.wage, person.id))
        shares[top.id] += drift
    return shares


def payroll_parts(state: GameState) -> tuple[int, int]:
    """Wages, then the employer payroll tax on those wages.

    Eight hours is straight time. Every hour past that is time and a half.
    The wage is the gross. Employee withholding comes out of it and does not add a second bill.
    """
    wages = sum(gross_shares(state).values()) * CREW_MULT
    payroll_tax = (wages * PAYROLL_TAX_PER_TEN_THOUSAND) // 10000
    return wages, payroll_tax


def federal_withholding(gross: int) -> int:
    """One week of federal income tax for a single filer, from the annualized gross."""
    taxable = gross * 52 - FEDERAL_STANDARD_DEDUCTION
    if taxable <= 0:
        return 0
    tax = 0
    floor = 0
    for cap, rate in FEDERAL_BRACKETS:
        band = min(taxable, cap) - floor
        if band > 0:
            tax += band * rate // 100
        if taxable <= cap:
            break
        floor = cap
    return tax // 52


@dataclass(frozen=True)
class PayAdvice:
    regular_hours: int
    overtime_hours: int
    rate_cents: int
    regular_pay: int
    overtime_pay: int
    gross: int
    federal: int
    social: int
    medicare: int
    state_tax: int
    county_tax: int
    net: int

    @property
    def overtime_rate_cents(self) -> int:
        return self.rate_cents * 3 // 2


def pay_advice(state: GameState, person: Staff, gross: int | None = None) -> PayAdvice:
    """The direct-deposit advice for one week.

    Social Security is 6.2% until the wage base. Medicare is 1.45%.
    A single shop withholds Indiana state tax at 2.95% and county tax at 1.25%.
    A company door withholds the rates for the city where that person works.
    The ledger is in whole dollars.
    """
    if gross is None:
        gross = gross_shares(state).get(person.id, 0)
    door = next((item for item in state.doors if item.id == person.door_id), None) if state.mode == "corporate" and person.door_id else None
    if door is not None:
        span = max(4, door.close_hour - door.open_hour)
        regular_hours = 5 * min(span, 8)
        overtime_hours = 5 * max(0, span - 8)
        state_rate = door.state_tax_per_ten_thousand
        county_rate = door.county_tax_per_ten_thousand
    else:
        regular_hours, overtime_hours = week_hours(state)
        state_rate = STATE_TAX_PER_TEN_THOUSAND
        county_rate = COUNTY_TAX_PER_TEN_THOUSAND
    rate_cents = person.wage * 100 // 40
    if overtime_hours:
        overtime_pay = overtime_hours * (rate_cents * 3 // 2) // 100
        regular_pay = gross - overtime_pay
    else:
        regular_pay = gross
        overtime_pay = 0
    room = max(0, SOCIAL_SECURITY_WAGE_BASE - person.ytd_gross)
    social = min(gross, room) * 62 // 1000
    medicare = gross * 145 // 10000
    federal = federal_withholding(gross)
    from open_late.economy_e4 import scale_state_withholding

    city_id = door.id if door is not None else "evansville"
    state_rate = scale_state_withholding(state, state_rate, city_id)
    state_tax = gross * state_rate // 10000
    county_tax = gross * county_rate // 10000
    withheld = federal + social + medicare + state_tax + county_tax
    if withheld > gross:
        federal = max(0, federal - (withheld - gross))
        withheld = federal + social + medicare + state_tax + county_tax
    return PayAdvice(
        regular_hours=regular_hours,
        overtime_hours=overtime_hours,
        rate_cents=rate_cents,
        regular_pay=regular_pay,
        overtime_pay=overtime_pay,
        gross=gross,
        federal=federal,
        social=social,
        medicare=medicare,
        state_tax=state_tax,
        county_tax=county_tax,
        net=gross - withheld,
    )


def record_payday(state: GameState) -> None:
    """Add this week's advice to each person's year-to-date totals."""
    shares = gross_shares(state)
    for person in state.staff:
        gross = shares.get(person.id)
        if gross is None:
            continue
        advice = pay_advice(state, person, gross)
        person.ytd_gross += advice.gross
        person.ytd_federal += advice.federal
        person.ytd_social += advice.social
        person.ytd_medicare += advice.medicare
        person.ytd_state += advice.state_tax
        person.ytd_county += advice.county_tax
        person.ytd_net += advice.net


def insurance_weekly(state: GameState) -> int:
    doors = sum(1 for site in state.sites if site.is_physical and not site.is_warehouse)
    warehouses = sum(1 for site in state.sites if site.is_warehouse)
    if doors == 0 and warehouses == 0:
        return 80
    return INSURANCE_PER_DOOR * doors + INSURANCE_PER_WAREHOUSE * warehouses


def utilities_weekly(state: GameState) -> int:
    if state.mode == "corporate" and state.doors:
        door_bill = sum(max(4, door.close_hour - door.open_hour) * UTILITY_PER_OPEN_HOUR for door in state.doors)
        warehouse = 240 if any(site.is_warehouse for site in state.sites) else 0
        return door_bill + warehouse
    doors = sum(1 for site in state.sites if site.is_physical and not site.is_warehouse)
    if doors == 0:
        return 120
    span = max(4, state.close_hour - state.open_hour)
    return doors * span * UTILITY_PER_OPEN_HOUR


def weekly_obligations(state: GameState) -> int:
    rent = sum(site.rent_weekly for site in state.sites)
    wages, payroll_tax = payroll_parts(state)
    if state.mode == "corporate":
        salaries = sum(person.wage for person in state.managers if person.employed)
        wages += salaries
        payroll_tax += salaries * PAYROLL_TAX_PER_TEN_THOUSAND // 10000
    return (
        rent
        + wages
        + payroll_tax
        + insurance_weekly(state)
        + utilities_weekly(state)
        + interest_due(state)
        + state.tax_held
    )


def card_fee(charged: int) -> int:
    if charged <= 0:
        return 0
    return (charged * CARD_FEE_PER_THOUSAND) // 1000


def shipping_for(product: Product) -> int:
    department = getattr(product, "department", "") or product.category
    if product.price >= 180:
        return 13
    if department in ("clothing", "seasonal"):
        return 7
    if product.price >= 90:
        return 10
    if department in ("grocery", "produce", "frozen", "household", "health_beauty") or product.price <= 30:
        return 5
    return 8


def freight_for(lead_days: int, merchandise: int) -> int:
    if merchandise <= 0:
        return 0
    if lead_days <= 6:
        rate = 3
    elif lead_days <= 10:
        rate = 5
    else:
        rate = 8
    return max(12, (merchandise * rate) // 100)


def damage_chance(lead_days: int) -> float:
    return min(0.12, 0.02 + max(0, lead_days - 6) * 0.004)


def weekly_depreciation(fixtures: int, accumulated: int) -> int:
    book = max(0, fixtures - accumulated)
    if book <= 0 or fixtures <= 0:
        return 0
    amount = fixtures * 7 // 1825
    if amount <= 0:
        amount = 1
    return min(book, amount)


def pretax_profit(state: GameState) -> int:
    gross = state.quarter_sales - state.quarter_refunds - state.quarter_cogs
    return gross - state.quarter_opex - state.quarter_depreciation


def income_tax_due(state: GameState) -> int:
    profit = pretax_profit(state)
    if profit <= 0:
        return 0
    return profit * INCOME_TAX_PERCENT // 100


def is_sized(product: Product) -> bool:
    department = getattr(product, "department", "") or product.category
    return department == "clothing"


def allocate_sizes(qty: int) -> dict[str, int]:
    if qty <= 0:
        return {}
    raw = [(name, qty * weight / 100) for name, weight in SIZE_WEIGHTS.items()]
    counts = {name: int(value) for name, value in raw}
    left = qty - sum(counts.values())
    ranked = sorted(raw, key=lambda item: item[1] - int(item[1]), reverse=True)
    for index in range(left):
        counts[ranked[index % len(ranked)][0]] += 1
    return {name: counts[name] for name in SIZE_ORDER if counts.get(name)}


def size_label(line: StockLine) -> str:
    if not line.sizes:
        return str(line.on_hand)
    parts = " ".join(f"{name}{line.sizes[name]}" for name in SIZE_ORDER if line.sizes.get(name))
    return f"{line.on_hand} ({parts})"


def size_pack() -> dict[str, int]:
    """Documented size-pack numbers for tests and for the desk."""
    return {
        "size_mult": SIZE_MULT,
        "crew_mult": CREW_MULT,
        "credit_limit": CREDIT_LIMIT,
        "shop_reserve": SHOP_RESERVE,
        "calm_reserve": CALM_RESERVE,
        "stern_reserve": STERN_RESERVE,
        "utility_per_open_hour": UTILITY_PER_OPEN_HOUR,
        "insurance_per_door": INSURANCE_PER_DOOR,
    }
