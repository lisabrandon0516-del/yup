"""Company-owned doors. The office buys, allocates, and sets the wall. Managers run the floor."""

from __future__ import annotations

from dataclasses import dataclass

from open_late.content import SHOP_STOCK, STAFF, SUPPLIERS
from open_late.finance import CREW_MULT, LABOR_BUDGET_DEFAULT, PAYROLL_TAX_PER_TEN_THOUSAND, SIZE_MULT, allocate_sizes, card_fee, is_sized, size_int
from open_late.inbox import add
from open_late.models import Door, GameState, SalesDay, Shipment, Site, StockLine, StoreManager, VendorDeal
from open_late.text import CATEGORY_LABELS, clamp, is_sunday, money, weekday_name

CATEGORIES = list(CATEGORY_LABELS)
RESERVE_BASE = 90_000
CREDIT_BASE = 70_000
CALM_RESERVE_BASE = 120_000
STERN_RESERVE_BASE = 60_000
WAREHOUSE_RENT_BASE = 3000
RESERVE = size_int(RESERVE_BASE)
CREDIT = size_int(CREDIT_BASE)
CALM_RESERVE = size_int(CALM_RESERVE_BASE)
STERN_RESERVE = size_int(STERN_RESERVE_BASE)
WAREHOUSE_RENT = size_int(WAREHOUSE_RENT_BASE)

def corporate_reserve(difficulty: str | None) -> int:
    if difficulty == "calm":
        return CALM_RESERVE
    if difficulty == "stern":
        return STERN_RESERVE
    return RESERVE

DEFAULT_PLANOGRAM = {
    "grocery": 14,
    "produce": 8,
    "meat_dairy": 9,
    "frozen": 7,
    "household": 9,
    "health_beauty": 7,
    "pharmacy": 5,
    "electronics": 7,
    "clothing": 8,
    "toys": 6,
    "home_garden": 7,
    "sporting": 6,
    "seasonal": 7,
}


def _demand(**overrides: int) -> dict[str, int]:
    base = {key: 100 for key in CATEGORIES}
    base.update(overrides)
    return base


@dataclass(frozen=True)
class Market:
    id: str
    city: str
    state_name: str
    region: str
    blurb: str
    rent_weekly: int
    opening_cost: int
    min_cash_after: int
    foot_traffic: int
    neighbor_sensitivity: int
    allows_intense: bool
    sales_tax_bps: int
    state_tax_per_ten_thousand: int
    county_tax_per_ten_thousand: int
    wage_floor: int
    freight_per_unit: int
    open_hour: int
    close_hour: int
    fair_workweek: bool
    demand: dict[str, int]
    transit_days: int
    build_days: int


MARKETS: dict[str, Market] = {
    "evansville": Market(
        id="evansville",
        city="Evansville",
        state_name="Indiana",
        region="Midwest",
        blurb="The first door, a few miles from the warehouse. State tax and the county tax both come out of the paycheck. Sales tax is 7%.",
        rent_weekly=4700,
        opening_cost=0,
        min_cash_after=0,
        foot_traffic=320,
        neighbor_sensitivity=46,
        allows_intense=True,
        sales_tax_bps=700,
        state_tax_per_ten_thousand=295,
        county_tax_per_ten_thousand=125,
        wage_floor=580,
        freight_per_unit=2,
        open_hour=11,
        close_hour=19,
        fair_workweek=False,
        demand=_demand(),
        transit_days=1,
        build_days=0,
    ),
    "seattle": Market(
        id="seattle",
        city="Seattle",
        state_name="Washington",
        region="West Coast",
        blurb="High wage, no state income tax, and a posted schedule. Change the hours after Monday and Sunday owes predictability pay. Sales tax is 10.35%.",
        rent_weekly=10700,
        opening_cost=55000,
        min_cash_after=25000,
        foot_traffic=400,
        neighbor_sensitivity=68,
        allows_intense=True,
        sales_tax_bps=1035,
        state_tax_per_ten_thousand=0,
        county_tax_per_ten_thousand=0,
        wage_floor=1660,
        freight_per_unit=8,
        open_hour=11,
        close_hour=19,
        fair_workweek=True,
        demand=_demand(grocery=120, produce=130, pharmacy=70, clothing=90, health_beauty=120),
        transit_days=6,
        build_days=18,
    ),
    "houston": Market(
        id="houston",
        city="Houston",
        state_name="Texas",
        region="South",
        blurb="No state income tax on the paycheck. Sales tax is 8.25%. The freight from Evansville is real.",
        rent_weekly=6000,
        opening_cost=36000,
        min_cash_after=20000,
        foot_traffic=375,
        neighbor_sensitivity=40,
        allows_intense=True,
        sales_tax_bps=825,
        state_tax_per_ten_thousand=0,
        county_tax_per_ten_thousand=0,
        wage_floor=580,
        freight_per_unit=6,
        open_hour=11,
        close_hour=21,
        fair_workweek=False,
        demand=_demand(grocery=120, household=115, frozen=110),
        transit_days=4,
        build_days=10,
    ),
    "las_vegas": Market(
        id="las_vegas",
        city="Las Vegas",
        state_name="Nevada",
        region="West",
        blurb="A late tourist street. No state income tax. The crowd wants electronics and seasonal, and the shift runs long enough to pay overtime.",
        rent_weekly=8700,
        opening_cost=44000,
        min_cash_after=22000,
        foot_traffic=520,
        neighbor_sensitivity=18,
        allows_intense=True,
        sales_tax_bps=837,
        state_tax_per_ten_thousand=0,
        county_tax_per_ten_thousand=0,
        wage_floor=960,
        freight_per_unit=7,
        open_hour=12,
        close_hour=23,
        fair_workweek=False,
        demand=_demand(grocery=70, produce=80, clothing=140, electronics=150, seasonal=160),
        transit_days=5,
        build_days=8,
    ),
    "naperville": Market(
        id="naperville",
        city="Naperville",
        state_name="Illinois",
        region="Midwest",
        blurb="A suburb lease. The pharmacy counter stays off this floor. Illinois income tax is 4.95% of the gross. Sales tax is 7.75%.",
        rent_weekly=10000,
        opening_cost=48000,
        min_cash_after=22000,
        foot_traffic=460,
        neighbor_sensitivity=88,
        allows_intense=False,
        sales_tax_bps=775,
        state_tax_per_ten_thousand=495,
        county_tax_per_ten_thousand=0,
        wage_floor=1200,
        freight_per_unit=3,
        open_hour=10,
        close_hour=20,
        fair_workweek=False,
        demand=_demand(grocery=140, produce=130, household=120, pharmacy=0, clothing=90),
        transit_days=2,
        build_days=16,
    ),
}


from dataclasses import replace as _replace

MARKETS = {
    key: _replace(
        market,
        rent_weekly=size_int(market.rent_weekly),
        opening_cost=size_int(market.opening_cost),
        min_cash_after=size_int(market.min_cash_after),
        wage_floor=size_int(market.wage_floor),
    )
    for key, market in MARKETS.items()
}


def _managers() -> list[StoreManager]:
    return [
        StoreManager(
            id="dana",
            name="Dana Ruiz",
            short="Runs a calm floor and keeps the wall close to the planogram you sent.",
            operations=78,
            merchandising=74,
            leadership=76,
            local_sense=64,
            wage=size_int(2200),
            employed=True,
            door_id="evansville",
        ),
        StoreManager(
            id="marcus",
            name="Marcus Hale",
            short="Strict about the schedule and the count. The wall is whatever you last sent.",
            operations=88,
            merchandising=62,
            leadership=80,
            local_sense=58,
            wage=size_int(2900),
        ),
        StoreManager(
            id="renee",
            name="Renee Cho",
            short="The wall is the job. Shrink and call-outs get less of the week.",
            operations=64,
            merchandising=92,
            leadership=68,
            local_sense=74,
            wage=size_int(2560),
        ),
        StoreManager(
            id="owen",
            name="Owen Briggs",
            short="Knows a late street. Will chase a local crowd past the national ad.",
            operations=66,
            merchandising=60,
            leadership=72,
            local_sense=90,
            wage=size_int(2360),
        ),
    ]


def fresh_planogram(allows_intense: bool) -> dict[str, int]:
    shares = dict(DEFAULT_PLANOGRAM)
    if not allows_intense:
        shares["grocery"] += shares["pharmacy"]
        shares["pharmacy"] = 0
    return shares


def tax_for(amount: int, bps: int, state=None, city_id: str | None = None) -> int:
    if amount <= 0 or bps <= 0:
        return 0
    if state is not None:
        from open_late.economy_e4 import scale_bps

        bps = scale_bps(state, bps, city_id)
        if bps <= 0:
            return 0
    return amount * bps // 10000


def rate_label(bps: int) -> str:
    if bps % 100 == 0:
        return f"{bps // 100}%"
    return f"{bps / 100:.2f}%"


def openable_markets(state: GameState) -> list[Market]:
    owned = {door.id for door in state.doors}
    return [market for market in MARKETS.values() if market.id not in owned and market.opening_cost > 0]


_CAPITAL_MARKETS: dict[str, Market] | None = None


def _build_capital_markets() -> dict[str, Market]:
    from open_late.us_capitals import CAPITALS, demographic_line, lease_scale

    built: dict[str, Market] = {}
    for item in CAPITALS:
        scale = lease_scale(item)
        sales = item.sales_tax_bps / 100
        withhold = item.withhold_per_ten_thousand / 100
        blurb = (
            f"{item.city} is the capital of {item.state}. "
            f"2020 Census: {item.population:,} people. {demographic_line(item)}. "
            f"Hispanic/Latino overlaps the race shares. "
            f"State sales tax is {sales:.2f}%. Paycheck withholding is modeled at {withhold:.2f}%. "
            f"A truck from Evansville takes {scale['transit_days']} days."
        )
        built[item.ident] = Market(
            id=item.ident,
            city=item.city,
            state_name=item.state,
            region=item.region,
            blurb=blurb,
            rent_weekly=size_int(scale["rent_weekly"]),
            opening_cost=size_int(scale["opening_cost"]),
            min_cash_after=size_int(scale["min_cash_after"]),
            foot_traffic=scale["foot_traffic"],
            neighbor_sensitivity=50,
            allows_intense=True,
            sales_tax_bps=item.sales_tax_bps,
            state_tax_per_ten_thousand=item.withhold_per_ten_thousand,
            county_tax_per_ten_thousand=0,
            wage_floor=size_int(scale["wage_floor"]),
            freight_per_unit=scale["freight_per_unit"],
            open_hour=10,
            close_hour=21,
            fair_workweek=False,
            demand=_demand(),
            transit_days=scale["transit_days"],
            build_days=scale["build_days"],
        )
    return built


def capital_markets() -> list[Market]:
    """One leasable door for each state capital. Not part of the original five."""
    global _CAPITAL_MARKETS
    if _CAPITAL_MARKETS is None:
        _CAPITAL_MARKETS = _build_capital_markets()
    return list(_CAPITAL_MARKETS.values())


def capital_market(market_id: str) -> Market | None:
    capital_markets()
    assert _CAPITAL_MARKETS is not None
    return _CAPITAL_MARKETS.get(market_id)


def door_by_id(state: GameState, door_id: str) -> Door | None:
    return next((door for door in state.doors if door.id == door_id), None)


def manager_by_id(state: GameState, manager_id: str) -> StoreManager | None:
    return next((person for person in state.managers if person.id == manager_id), None)


def deal_for(state: GameState, supplier_id: str) -> VendorDeal | None:
    return next((deal for deal in state.deals if deal.supplier_id == supplier_id), None)


def coop_claimable(state: GameState) -> int:
    return sum(deal.coop_accrued for deal in state.deals)


def claim_coop(state: GameState, amount: int) -> int:
    left = max(0, amount)
    taken = 0
    for deal in sorted(state.deals, key=lambda item: item.coop_accrued, reverse=True):
        if left <= 0:
            break
        bite = min(deal.coop_accrued, left)
        deal.coop_accrued -= bite
        left -= bite
        taken += bite
    return taken


def holding_capacity(door: Door) -> int:
    """Floor facings plus a back room. A planogram point holds 280 units, times the size pack."""
    return (400 + sum(door.planogram.values()) * 280) * SIZE_MULT


def crowd_factor(state: GameState, door: Door) -> float:
    """The part of traffic that belongs to the city, not the chain."""
    dow = (state.day - 1) % 7
    factor = 1.0
    if door.id == "las_vegas" and dow in (4, 5):
        factor *= 1.45
    if door.id == "las_vegas" and dow == 0:
        factor *= 0.85
    if door.id == "seattle":
        week = (state.day - 1) // 7
        swing = (state.seed + week * 13) % 7
        factor *= 0.84 + swing * 0.04
    if door.id == "houston" and dow in (0, 1):
        factor *= 0.9
    if door.id == "naperville" and dow in (4, 5):
        factor *= 1.15
    return factor


def week_gross(person, door: Door) -> int:
    span = max(4, door.close_hour - door.open_hour)
    if span <= 8:
        numerator, denominator = span, 8
    else:
        numerator, denominator = 16 + 3 * (span - 8), 16
    # Named shop wages are lead rates; the door pays a crew of CREW_MULT.
    # A floor already scaled by SIZE_MULT is the crew cost, so it is not scaled again.
    from open_late.finance import lead_weekly

    wage = lead_weekly(person.wage, door.wage_floor)
    return int(round(wage * numerator / denominator)) * CREW_MULT


def _stock_lines(catalog: dict, quantities: dict[str, int]) -> dict[str, StockLine]:
    stock: dict[str, StockLine] = {}
    for product_id, product in catalog.items():
        on_hand = quantities.get(product_id, 0)
        sizes = allocate_sizes(on_hand) if is_sized(product) and on_hand else {}
        stock[product_id] = StockLine(product_id=product_id, on_hand=on_hand, sizes=sizes)
    return stock


def _door_from(market: Market, stock: dict[str, StockLine]) -> Door:
    return Door(
        id=market.id,
        city=market.city,
        state_name=market.state_name,
        region=market.region,
        blurb=market.blurb,
        stock=stock,
        open_hour=market.open_hour,
        close_hour=market.close_hour,
        posted_open=market.open_hour,
        posted_close=market.close_hour,
        planogram=fresh_planogram(market.allows_intense),
        sales_tax_bps=market.sales_tax_bps,
        state_tax_per_ten_thousand=market.state_tax_per_ten_thousand,
        county_tax_per_ten_thousand=market.county_tax_per_ten_thousand,
        wage_floor=market.wage_floor,
        freight_per_unit=market.freight_per_unit,
        fair_workweek=market.fair_workweek,
        allows_intense=market.allows_intense,
        foot_traffic=market.foot_traffic,
        neighbor_sensitivity=market.neighbor_sensitivity,
        demand=dict(market.demand),
        rent_weekly=market.rent_weekly,
        transit_days=market.transit_days,
        status="open" if market.build_days <= 0 else "buildout",
        opens_on=1,
        labor_budget=LABOR_BUDGET_DEFAULT,
    )


def _site_from(market: Market) -> Site:
    return Site(
        id=market.id,
        label=f"{market.city}, {market.state_name}",
        rent_weekly=market.rent_weekly,
        foot_traffic=market.foot_traffic,
        neighbor_sensitivity=market.neighbor_sensitivity,
        allows_intense=market.allows_intense,
    )


def new_corporate(shop_name: str, seed: int | None, chain_id: str | None = None, economy_difficulty: str | None = None) -> GameState:
    import random
    import uuid

    from open_late.content import PRODUCTS
    from open_late.engine import _ensure_accounts, _seed_targets

    from open_late import GAME_NAME

    name = shop_name.strip() or GAME_NAME
    catalog = {product.id: product.model_copy(deep=True) for product in PRODUCTS}
    warehouse = _stock_lines(catalog, SHOP_STOCK)
    door_stock = _stock_lines(catalog, SHOP_STOCK)
    staff = [person.model_copy(deep=True) for person in STAFF]
    for person in staff:
        person.wage_ask = person.wage
        person.review_due = 28
        person.assignment = "off"
        if person.id in ("alyssa", "jordan", "priya", "naomi", "marisol", "dean"):
            person.employed = True
            person.door_id = "evansville"
            person.assignment = "floor"
    evansville = MARKETS["evansville"]
    door = _door_from(evansville, door_stock)
    door.manager_id = "dana"
    state = GameState(
        slot=uuid.uuid4().hex,
        shop_name=name,
        mode="corporate",
        seed=seed if seed is not None else random.randrange(1, 10_000_000),
        save_version=4,
        cash=corporate_reserve(economy_difficulty),
        credit_limit=CREDIT,
        products=catalog,
        stock=warehouse,
        staff=staff,
        regulars=[],
        sites=[
            Site(
                id="distribution",
                label="Evansville warehouse",
                rent_weekly=WAREHOUSE_RENT,
                foot_traffic=0,
                neighbor_sensitivity=10,
                allows_intense=True,
                is_physical=False,
                is_warehouse=True,
            ),
            _site_from(evansville),
        ],
        doors=[door],
        managers=_managers(),
        open_hour=evansville.open_hour,
        close_hour=evansville.close_hour,
        fixtures=6400,
        reputation_respectable=48,
        reputation_nightlife=32,
    )
    from open_late.content import REGULARS

    state.regulars = [person.model_copy(deep=True) for person in REGULARS]
    _ensure_accounts(state)
    _seed_targets(state, 28)
    from open_late.chains import DEFAULT_CHAIN_ID, set_chain

    set_chain(state, chain_id or DEFAULT_CHAIN_ID)
    from open_late.economy import configure_new_game

    configure_new_game(state, economy_difficulty)
    add(
        state,
        kind="opening",
        title="The office",
        body=(
            f"Monday. {name} is a company, not one room. The warehouse is in Evansville and Dana Ruiz "
            "has that door. Alyssa and Jordan are on her payroll. You do not write their shifts. "
            "You set the planogram, the labor budget, the ads, which truck leaves Evansville, and the deals with the houses. "
            "A truck takes a day to cross town and most of a week to reach Seattle. A cold-chain drop has to stay cold. "
            "Seattle, Houston, Las Vegas, and Naperville need zoning and a build-out before they can sell. "
            "Rent starts when you sign. Co-op money accrues on what you buy, and you claim it when you run an ad."
        ),
    )
    return state


def _build_scale(build: dict | None) -> tuple[float, int]:
    """Square feet against a 115,000 sq ft supercenter, and the build-out the player asked for."""
    if not build:
        return 1.0, -1
    sq_ft = max(20_000, min(300_000, int(build.get("sq_ft") or 115_000)))
    days = max(0, min(120, int(build.get("build_days", 0))))
    return max(0.35, min(3.0, sq_ft / 115_000)), days


def _apply_store_build(state: GameState, door: Door, site: Site, build: dict | None, scale: float, build_days: int) -> str:
    if not build:
        return ""
    if scale != 1.0:
        door.rent_weekly = max(1, int(round(door.rent_weekly * scale)))
        door.foot_traffic = max(1, int(round(door.foot_traffic * scale)))
        site.rent_weekly = max(1, int(round(site.rent_weekly * scale)))
    if build_days >= 0:
        door.opens_on = state.day + build_days
        door.status = "open" if build_days <= 0 else "buildout"
    from open_late.shelves import install_store_build

    shape = install_store_build(
        state,
        door,
        int(build.get("sq_ft") or 115_000),
        int(build.get("center") or 6),
        int(build.get("gm") or 7),
        str(build.get("template") or "balanced"),
    )
    return f" The building is {shape}. It opens on day {door.opens_on}."


def open_market(state: GameState, market_id: str, loan: bool = False, build: dict | None = None) -> str:
    """Sign a new city. ``loan=True`` (rival AI on) finances 70% with the rivals' building loan.

    ``build`` may set sq_ft, build_days, center aisles, GM aisles, and a layout template.
    Leaving it out signs the city's usual supercenter.
    """
    market = MARKETS.get(market_id) or capital_market(market_id)
    if market is None or market.opening_cost <= 0:
        return "That city is not on the list."
    if door_by_id(state, market_id) is not None:
        return f"{market.city} is already on the lease."
    from open_late.economy_e3 import opening_cost_mult

    base_cost = market.opening_cost
    if getattr(state, "rival_ai", None) is not None:
        # Rival AI on: the player builds a supercenter at the same price as the rivals.
        from open_late.rival_ai import player_opening_base

        base_cost = player_opening_base(state, market_id, base_cost)
    opening_cost = int(round(base_cost * opening_cost_mult(state, market_id)))
    scale, build_days = _build_scale(build)
    if build:
        opening_cost = int(round(opening_cost * scale))
        if "build_days" not in build:
            build_days = int(market.build_days)
    if loan:
        from open_late.rival_ai import player_store_loan_offer, take_store_loan

        offer = player_store_loan_offer(state, market_id)
        if not offer["approved"]:
            return f"No building loan for {market.city}: {offer['reason']}."
        if build and scale != 1.0:
            offer = dict(offer)
            offer["principal"] = int(round(int(offer["principal"]) * scale))
            offer["equity"] = opening_cost - int(offer["principal"])
            offer["weekly_principal"] = int(round(int(offer["weekly_principal"]) * scale))
            offer["weekly_interest"] = int(round(int(offer["weekly_interest"]) * scale))
            offer["weekly_payment"] = int(offer["weekly_principal"]) + int(offer["weekly_interest"])
        down = opening_cost - int(offer["principal"])
        state.cash -= down
        state.spent_today += down
        state.spent_fixtures += down
        state.fixtures += opening_cost
        take_store_loan(state, market_id, offer)
        door = _door_from(market, _stock_lines(state.products, {}))
        door.status = "buildout"
        door.opens_on = state.day + (build_days if build else market.build_days)
        state.doors.append(door)
        site = _site_from(market)
        state.sites.append(site)
        shaped = _apply_store_build(state, door, site, build, scale, build_days if build else -1)
        state.actions_today.append(f"Signed {market.city} with a building loan. Opens day {door.opens_on}.")
        from open_late.books import note_decision

        note_decision(state, "lease", f"Signed {market.city}. Opens day {door.opens_on}.")
        return (
            f"Lease signed for {market.city}, {market.state_name}. Building {money(opening_cost)}: "
            f"{money(down)} down, {money(int(offer['principal']))} on a {int(offer['term_weeks']) // 52}-year building loan "
            f"at {100 * float(offer['annual_rate']):.2f}% today, about {money(int(offer['weekly_payment']))} a week. "
            f"Rent {money(door.rent_weekly)} every Sunday, starting now. "
            f"The door opens on day {door.opens_on}.{shaped}"
        )
    needed = opening_cost + market.min_cash_after
    if state.cash < needed:
        return (
            f"Opening {market.city} costs {money(opening_cost)} and you would have less than "
            f"{money(market.min_cash_after)} left. The drawer has {money(state.cash)}."
        )
    state.cash -= opening_cost
    state.spent_today += opening_cost
    state.spent_fixtures += opening_cost
    state.fixtures += opening_cost
    door = _door_from(market, _stock_lines(state.products, {}))
    door.status = "buildout"
    door.opens_on = state.day + (build_days if build else market.build_days)
    state.doors.append(door)
    site = _site_from(market)
    state.sites.append(site)
    shaped = _apply_store_build(state, door, site, build, scale, build_days if build else -1)
    state.actions_today.append(f"Signed {market.city}. Opens day {door.opens_on}.")
    from open_late.books import note_decision

    note_decision(state, "lease", f"Signed {market.city}. Opens day {door.opens_on}.")
    return (
        f"Lease signed for {market.city}, {market.state_name}. Opening costs {money(opening_cost)}. "
        f"Rent {money(door.rent_weekly)} every Sunday, starting now. "
        f"Zoning and build-out take {door.opens_on - state.day} days. The door opens on day {door.opens_on}. "
        f"{'It can sell today.' if door.opens_on <= state.day else 'It will not sell before then.'} "
        "You can still hire, set the wall, and put a truck on the road."
        f"{shaped}"
    )


def hire_manager(state: GameState, manager_id: str) -> str:
    person = manager_by_id(state, manager_id)
    if person is None:
        return "No one by that name."
    if person.employed:
        return f"{person.name} is already on the office sheet."
    person.employed = True
    state.actions_today.append(f"Hired {person.name}.")
    return f"{person.name} is on the office sheet. Salary {money(person.wage)} a week. Assign them to a door."


def assign_manager(state: GameState, manager_id: str, door_id: str) -> str:
    person = manager_by_id(state, manager_id)
    door = door_by_id(state, door_id)
    if person is None:
        return "No one by that name."
    if not person.employed:
        return f"Hire {person.name} before you give them a door."
    if door is None:
        return "That door is not on the lease."
    for other in state.doors:
        if other.manager_id == person.id:
            other.manager_id = ""
    previous = manager_by_id(state, door.manager_id) if door.manager_id else None
    if previous is not None and previous.id != person.id:
        previous.door_id = ""
    door.manager_id = person.id
    person.door_id = door.id
    state.actions_today.append(f"{person.name} has {door.city}.")
    return f"{person.name} has {door.city}. They write the schedule. You still own the wall and the truck."


def assign_door(state: GameState, staff_id: str, door_id: str) -> str:
    person = next((member for member in state.staff if member.id == staff_id), None)
    door = door_by_id(state, door_id)
    if person is None or not person.employed:
        return "They are not on payroll."
    if door is None:
        return "That door is not on the lease."
    person.door_id = door.id
    note = f"{person.name} is on the {door.city} floor."
    lead_floor = max(1, int(door.wage_floor) // SIZE_MULT)
    if person.wage >= int(door.wage_floor):
        person.wage = max(lead_floor, int(person.wage) // SIZE_MULT)
    if person.wage < lead_floor:
        person.wage = lead_floor
        person.wage_ask = max(person.wage_ask, person.wage)
        note += (
            f" Wage moves to {money(person.wage)}."
            f" One crew costs {money(door.wage_floor)} a week."
        )
    state.actions_today.append(note)
    return note


def set_planogram(state: GameState, door_id: str, shares: dict[str, int]) -> str:
    door = door_by_id(state, door_id)
    if door is None:
        return "That door is not on the lease."
    cleaned = {key: int(shares.get(key, -1)) for key in CATEGORIES}
    if any(value < 0 for value in cleaned.values()):
        return "The planogram needs every category."
    if sum(cleaned.values()) != 100:
        return "The wall has to add up to 100."
    if not door.allows_intense and cleaned.get("pharmacy", 0) > 0:
        return f"The {door.city} lease keeps the pharmacy counter off the floor."
    door.planogram = cleaned
    door.planogram_days = 0
    state.actions_today.append(f"Planogram sent to {door.city}.")
    return ""


def set_door_hours(state: GameState, door_id: str, open_hour: int, close_hour: int) -> str:
    door = door_by_id(state, door_id)
    if door is None:
        return "That door is not on the lease."
    open_hour = int(open_hour)
    close_hour = int(close_hour)
    if not (8 <= open_hour < close_hour <= 23):
        return "Hours have to sit between 8 and 23."
    if close_hour - open_hour < 4:
        return "Fewer than four hours is not a shop."
    monday = (state.day - 1) % 7 == 0
    penalty = 0
    posted = (door.posted_open, door.posted_close)
    if door.fair_workweek and not monday and (open_hour, close_hour) != posted:
        delta = abs((close_hour - open_hour) - (door.posted_close - door.posted_open))
        crew = [person for person in state.staff if person.employed and person.door_id == door.id]
        rate = sum(max(1, person.wage // 40) for person in crew) or 1
        penalty = rate * max(1, delta) * 5
        door.predictability_due += penalty
    door.open_hour = open_hour
    door.close_hour = close_hour
    if monday or not door.fair_workweek:
        door.posted_open = open_hour
        door.posted_close = close_hour
    if penalty:
        return (
            f"{door.city} hours are {open_hour}:00 to {close_hour}:00. "
            f"Predictability pay of {money(penalty)} is due Sunday. "
            f"The posted schedule was {posted[0]}:00 to {posted[1]}:00."
        )
    return f"Posted hours in {door.city} are {open_hour}:00 to {close_hour}:00."


def transfer_freight(door: Door, units: int) -> int:
    """Warehouse-to-door freight: trailers by distance, not a dollar per can."""
    if units <= 0:
        return 0
    trailers = max(1, (int(units) + 3999) // 4000)
    rate = max(1, int(getattr(door, "freight_per_unit", 2) or 2))
    days = max(1, int(door.transit_days))
    return trailers * rate * 100 * days


def allocate(state: GameState, door_id: str, quantities: dict[str, int]) -> str:
    from open_late.engine import _add_stock, _take_stock

    door = door_by_id(state, door_id)
    if door is None:
        return "That door is not on the lease."
    clean: dict[str, int] = {}
    for product_id, qty in quantities.items():
        amount = int(qty)
        if amount <= 0:
            continue
        product = state.products.get(product_id)
        line = state.stock.get(product_id)
        if product is None or line is None:
            return "That item is not on the sheet."
        if line.on_hand < amount:
            return f"The warehouse has {line.on_hand} of {product.name}."
        clean[product_id] = amount
    if not clean:
        return "Nothing to send."
    units = sum(clean.values())
    freight = transfer_freight(door, units)
    from open_late.economy import adjust_freight

    freight = adjust_freight(state, door.id, freight)
    if freight and state.cash < freight:
        return f"Freight to {door.city} is {money(freight)}. The drawer has {money(state.cash)}."
    shipped: dict[str, int] = {}
    for product_id, amount in clean.items():
        product = state.products[product_id]
        moved = _take_stock(state.stock[product_id], product, amount)
        if moved:
            shipped[product_id] = moved
    units = sum(shipped.values())
    if not units:
        return "Nothing left the warehouse."
    freight = transfer_freight(door, units)
    freight = adjust_freight(state, door.id, freight)
    if freight:
        state.cash -= freight
        state.spent_today += freight
        state.spent_freight += freight
    arrives = state.day + door.transit_days
    from open_late.economy import lead_slip_days

    arrives += lead_slip_days(state)
    state.shipments.append(
        Shipment(
            id=f"sh{state.next_shipment_id}",
            door_id=door.id,
            lines=shipped,
            departs_on=state.day,
            arrives_on=arrives,
            freight=freight,
            transit_days=door.transit_days,
        )
    )
    state.next_shipment_id += 1
    door.week_freight += freight
    if freight:
        from open_late.hq import record
        record(state, door.id, freight=freight)
    state.actions_today.append(f"Truck to {door.city} arrives day {arrives}.")
    return f"Sent {units} units to {door.city}. Arrives day {arrives}. Freight {money(freight)}."


def receive_shipments(state: GameState, report) -> None:
    from open_late.engine import _add_stock

    pending: list[Shipment] = []
    for shipment in state.shipments:
        if shipment.arrives_on > state.day:
            pending.append(shipment)
            continue
        door = door_by_id(state, shipment.door_id)
        if door is None:
            pending.append(shipment)
            continue
        room = holding_capacity(door) - sum(line.on_hand for line in door.stock.values())
        returned = 0
        damaged = 0
        damage_cost = 0
        from open_late.catalog import carry_item

        for product_id, qty in shipment.lines.items():
            product = state.products.get(product_id)
            if product is None or qty <= 0:
                continue
            carry_item(state, product_id)
            lost = qty * max(0, shipment.transit_days - 2) // 40
            good = qty - lost
            damaged += lost
            damage_cost += lost * product.cost
            take = min(good, max(0, room))
            back = good - take
            if take:
                _add_stock(door.stock[product_id], product, take)
                room -= take
            if back:
                _add_stock(state.stock[product_id], product, back)
                returned += back
        if damaged:
            report.damage_units += damaged
            report.damage_cost += damage_cost
            report.shrink_units += damaged
            report.shrink_cost += damage_cost
            report.cogs += damage_cost
            door.week_shrink += damage_cost
            from open_late.hq import record
            record(state, door.id, shrink=damage_cost)
            report.notes.append(
                f"The truck to {door.city} arrived short {damaged} "
                f"{'unit' if damaged == 1 else 'units'} after {shipment.transit_days} days on the road."
            )
        if returned:
            report.notes.append(
                f"{door.city} was at capacity. {returned} units came back to the warehouse."
            )
    state.shipments = pending


def replenish(state: GameState, door_id: str) -> str:
    door = door_by_id(state, door_id)
    if door is None:
        return "That door is not on the lease."
    lines: dict[str, int] = {}
    names: list[str] = []
    for product in state.products.values():
        recent = 0
        for row in door.sales_days:
            if state.day - 7 < row.day <= state.day:
                recent += row.units.get(product.id, 0)
        recent = max(0, recent)
        target = recent * door.weeks_of_supply
        if target <= 0:
            continue
        inbound = sum(
            shipment.lines.get(product.id, 0)
            for shipment in state.shipments
            if shipment.door_id == door.id
        )
        have = door.stock[product.id].on_hand + inbound
        gap = target - have
        available = state.stock[product.id].on_hand
        take = min(gap, available)
        if take > 0:
            lines[product.id] = take
            names.append(product.name)
    if not lines:
        from open_late.dc import fill_thin_pools

        ordered = fill_thin_pools(state)
        return (
            f"Nothing to send to {door.city}. The last week of sales is covered for "
            f"{door.weeks_of_supply} weeks, or the pool does not have it. {ordered}"
        )
    sent = allocate(state, door_id, lines)
    from open_late.dc import drawn_labels

    drew = drawn_labels(state, lines)
    if names:
        return f"{sent} Drew {drew}. Covered {', '.join(names[:4])}."
    return f"{sent} Drew {drew}."


def sign_deal(state: GameState, supplier_id: str) -> str:
    supplier = SUPPLIERS.get(supplier_id)
    if supplier is None:
        return "Unknown supplier."
    account = next((item for item in state.supplier_accounts if item.supplier_id == supplier_id), None)
    volume = account.volume if account else 0
    doors = len(state.doors)
    if volume >= 4000 or doors >= 4:
        tier, off, terms, coop = "partner", 8, "net30", 25
    elif volume >= 1200 or doors >= 2:
        tier, off, terms, coop = "volume", 4, "net30", 10
    else:
        return (
            f"{supplier.name} will not move off list price until the chain is buying. "
            "Two doors, or $1,200 with this house."
        )
    existing = deal_for(state, supplier_id)
    if existing is not None and existing.tier == tier and existing.cost_off_percent == off:
        return f"The {tier} deal with {supplier.name} is already on the sheet."
    carried = existing.coop_accrued if existing is not None else 0
    deal = VendorDeal(
        supplier_id=supplier_id,
        tier=tier,
        cost_off_percent=off,
        terms=terms,  # type: ignore[arg-type]
        coop_percent=coop,
        coop_accrued=carried,
    )
    state.deals = [item for item in state.deals if item.supplier_id != supplier_id]
    state.deals.append(deal)
    if account is not None:
        account.terms = terms  # type: ignore[assignment]
    label = "net 30" if terms == "net30" else "net 14"
    state.actions_today.append(f"{tier.title()} deal with {supplier.name}.")
    return (
        f"{tier.title()} deal with {supplier.name}. Cost is {off}% under the sheet. "
        f"Terms are {label}. Co-op accrues at {coop}% of what you buy and is claimed when you run an ad."
    )


def _schedule(state: GameState, door: Door) -> str:
    crew = [person for person in state.staff if person.employed and person.door_id == door.id]
    manager = manager_by_id(state, door.manager_id) if door.manager_id else None
    if manager is None:
        return ""
    monday = (state.day - 1) % 7 == 0
    if not monday and door.roster_set:
        working = [person for person in crew if person.assignment == "floor"]
        if not working:
            return f"{manager.name} kept {door.city}'s posted roster. Nobody is on the floor."
        names = " and ".join(person.name for person in working[:3])
        return f"{manager.name} kept {door.city}'s posted roster. {names} on the floor."
    ranked = sorted(crew, key=lambda person: (-person.aptitude_floor, person.id))
    spent = 0
    working = []
    for person in ranked:
        cost = week_gross(person, door)
        if spent + cost <= door.labor_budget:
            person.assignment = "floor"
            spent += cost
            working.append(person)
        else:
            person.assignment = "off"
    door.roster_set = True
    if not working:
        return (
            f"{manager.name} is at {door.city}. The labor budget of {money(door.labor_budget)} "
            "does not cover a shift."
        )
    names = " and ".join(person.name for person in working[:3])
    parked = [person.name for person in ranked if person.assignment == "off"]
    note = f"{manager.name} scheduled {door.city} inside {money(door.labor_budget)}. {names} on the floor."
    if parked:
        note += f" Off the roster: {', '.join(parked[:3])}."
    return note


def _compliance(door: Door, manager: StoreManager | None) -> None:
    if manager is None:
        door.compliance = 24
    else:
        lag = min(1.0, 0.45 + door.planogram_days / 7)
        door.compliance = int(round(min(100, manager.merchandising * lag)))
    door.planogram_days += 1


def _visits(state: GameState, door: Door, manager: StoreManager | None, rng) -> int:
    from open_late.engine import DOW_MULT

    dow = DOW_MULT[(state.day - 1) % 7]
    if door.id == "las_vegas":
        rep = 0.7 + state.reputation_nightlife / 180
    else:
        rep = 0.74 + state.reputation_respectable / 240 + state.reputation_nightlife / 300
    hours = max(4, door.close_hour - door.open_hour) / 8
    lead = 0.42 if manager is None else 0.72 + manager.leadership / 250
    local = 1 + ((manager.local_sense / 500) if manager else 0)
    campaign = 1.0
    if state.campaign is not None and (not state.campaign.door_id or state.campaign.door_id == door.id):
        campaign = state.campaign.traffic_mult
        from open_late.economy_e3 import campaign_lift_mult

        fade = campaign_lift_mult(state, door.id)
        campaign = 1.0 + (campaign - 1.0) * fade
    noise = rng.uniform(0.92, 1.08) * crowd_factor(state, door)
    visits = max(0, int(round(door.foot_traffic * dow * rep * hours * lead * local * campaign * noise)))
    from open_late.economy import adjust_visits

    from open_late.finance import SIZE_MULT

    return adjust_visits(state, door.id, visits) * SIZE_MULT


def _weights(state: GameState, door: Door) -> dict[str, float]:
    weights: dict[str, float] = {}
    grasp = 0.5 + door.compliance / 200
    for category, share in door.planogram.items():
        if share <= 0:
            continue
        demand = door.demand.get(category, 100) / 100
        weights[category] = share * demand * grasp
    from open_late.economy import adjust_weight

    for category in list(weights):
        weights[category] = adjust_weight(state, door.id, category, weights[category])
    from open_late.shoppers import aisle_tilt

    tilt = aisle_tilt(door.city)
    for category, factor in tilt.items():
        if category in weights:
            weights[category] *= factor
    return weights


def _ring(state: GameState, door: Door, report, rng, product, qty: int, size: str | None) -> int:
    from open_late.engine import _pay, _take_stock, return_chance

    from open_late.departments import selling_price

    line = door.stock[product.id]
    unit = selling_price(product, line)
    sold = _take_stock(line, product, qty, size)
    if sold <= 0:
        return 0
    revenue = unit * sold
    if unit < product.price:
        report.expiry_markdown += (product.price - unit) * sold
    tax = tax_for(revenue, door.sales_tax_bps, state, door.id)
    state.cash += revenue + tax
    from open_late.hq import card_fee_for
    fee = card_fee_for(state, door.id, revenue + tax)
    if fee:
        report.card_fees += fee
        _pay(state, fee)
    state.tax_held += tax
    report.tax_collected += tax
    report.revenue += revenue
    report.units += sold
    from open_late.economy import landed_cost

    report.cogs += landed_cost(state, door.id, product.department, product.cost * sold)
    report.by_category[product.category] = report.by_category.get(product.category, 0) + revenue
    report.units_by_product[product.id] = report.units_by_product.get(product.id, 0) + sold
    state.totals.revenue += revenue
    state.totals.units += sold
    state.list_size = min(8000, state.list_size + sold)
    _note_units(door, state.day, product.id, sold)
    returned = sum(1 for _ in range(sold) if rng.chance(return_chance(product)))
    if returned:
        _note_units(door, state.day, product.id, -returned)
        refund = unit * returned
        report.returns += returned
        report.refunds += refund
        state.totals.returns += returned
        state.totals.refunds += refund
        if unit < product.price:
            report.expiry_markdown = max(0, report.expiry_markdown - (product.price - unit) * returned)
        tax_back = tax_for(refund, door.sales_tax_bps, state, door.id)
        state.tax_held = max(0, state.tax_held - tax_back)
        report.tax_refunded += tax_back
        _pay(state, refund + tax_back)
    return sold


def _note_units(door: Door, day: int, product_id: str, qty: int) -> None:
    if qty == 0:
        return
    if door.sales_days and door.sales_days[-1].day == day:
        row = door.sales_days[-1]
    else:
        row = SalesDay(day=day)
        door.sales_days.append(row)
    row.units[product_id] = row.units.get(product_id, 0) + qty
    if len(door.sales_days) > 21:
        door.sales_days = door.sales_days[-21:]


def _sell_door(state: GameState, door: Door, report, rng) -> None:
    from open_late.catalog import carry_item
    from open_late.engine import CONVERSION, _price_fit, _wanted_size

    for product_id in state.products:
        carry_item(state, product_id)

    if door.status != "open":
        if state.day >= door.opens_on:
            door.status = "open"
            report.notes.append(f"{door.city} opens today.")
        else:
            from open_late.engine import _spoil_stock
            from open_late.hq import record_door_trading_day

            spoil = _spoil_stock(door.stock, state.products, report)
            from open_late.economy import apply_daily_spoil

            spoil += apply_daily_spoil(state, door.stock, state.products, door.id, report)
            if spoil:
                door.week_shrink += spoil
                record_door_trading_day(state, door.id, sales=0, cogs=0, shrink=spoil, card_fees=0)
            door.last_sales = 0
            report.notes.append(f"{door.city} is in build-out. It opens on day {door.opens_on}.")
            return
    manager = manager_by_id(state, door.manager_id) if door.manager_id else None
    fees_before = report.card_fees
    shrink_before = report.shrink_cost
    cogs_before_door = report.cogs
    dept_before = dict(report.by_category)
    from open_late.engine import _spoil_stock

    spoil = _spoil_stock(door.stock, state.products, report)
    from open_late.economy import apply_daily_spoil

    spoil += apply_daily_spoil(state, door.stock, state.products, door.id, report)
    if spoil:
        door.week_shrink += spoil
    note = _schedule(state, door)
    if note:
        report.staff_lines.append(note)
    _compliance(door, manager)
    crew = [person for person in state.staff if person.employed and person.door_id == door.id and person.assignment == "floor"]
    if crew:
        knowledge = sum(person.product_knowledge for person in crew) / len(crew)
        capacity = sum(40 + person.product_knowledge // 2 for person in crew)
        staff_mult = 0.62 + knowledge / 220 + door.compliance / 500
    else:
        capacity = 20
        staff_mult = 0.4
    span = max(4, door.close_hour - door.open_hour)
    capacity = int(capacity * span / 8) * CREW_MULT
    report.capacity += capacity
    visits = _visits(state, door, manager, rng)
    from open_late.engine import _sale_departments
    from open_late.shoppers import population_draw

    campaign = state.campaign
    if campaign is not None and campaign.door_id and campaign.door_id != door.id:
        campaign = None
    from open_late.shoppers import scale_draw

    extra, note = population_draw(door.city, campaign, _sale_departments(state, door.stock), state.day)
    extra = scale_draw(state, door.id, extra)
    if extra:
        visits += extra
        report.trade_visits += extra
        report.notes.append(note)
    report.visits += visits
    arrived = visits
    if visits > capacity:
        report.lost_staff += visits - capacity
        visits = capacity
    weights = _weights(state, door)
    if state.campaign is not None and (not state.campaign.door_id or state.campaign.door_id == door.id):
        weights[state.campaign.category] = weights.get(state.campaign.category, 1) * 1.45
    revenue_before = report.revenue
    refunds_before = report.refunds
    cogs_before = report.cogs
    units_before = report.units
    tax_before = report.tax_collected
    if weights and visits:
        from open_late.engine import BASKET_SIZE
        from open_late.hq import apply_walked

        stocked: dict[str, list] = {}
        for product in state.products.values():
            if door.stock[product.id].on_hand > 0 and (door.allows_intense or product.intensity < 3):
                stocked.setdefault(product.category, []).append(product)
        walked = apply_walked(state, door.id, 1.0)
        from open_late.shelf_sales import door_shelf

        shelf = door_shelf(state, door)  # None unless Lite shelves are on
        from open_late.engine import NAMED_BASKET_CAP, _run_aggregate

        named = min(visits, NAMED_BASKET_CAP)
        remaining = visits - named
        for _ in range(named):
            for _ in range(BASKET_SIZE):
                category = rng.weighted(weights)
                options = stocked.get(category) or []
                if not options:
                    from open_late.engine import _count_stockout

                    _count_stockout(report, category, 1)
                    continue
                from open_late.shoppers import trip_afford_share

                pick = {
                    product.id: (0.55 + product.quality * 0.16) * _price_fit(product) * trip_afford_share(product.price)
                    for product in options
                }
                if shelf is not None:
                    pick = {pid: weight * shelf.sku.get(pid, 1.0) for pid, weight in pick.items()}
                product = state.products[rng.weighted(pick)]
                line = door.stock[product.id]
                size = _wanted_size(product, line, rng)
                if size == "":
                    report.lost_size += 1
                    continue
                from open_late.pricing import department_flex

                afford = trip_afford_share(product.price)
                flex = department_flex(product)
                chance = CONVERSION * _price_fit(product) * flex * afford * (0.75 + product.quality * 0.06) * staff_mult
                chance = max(0.05, min(0.9, chance))
                chance = chance * walked
                if shelf is not None:
                    chance = min(0.95, chance * shelf.lift.get(category, 1.0))
                if not rng.chance(chance):
                    if afford < 0.999 or _price_fit(product) < 0.7 or flex < 0.98:
                        report.lost_price += 1
                        report.lost_price_by_product[product.id] = report.lost_price_by_product.get(product.id, 0) + 1
                    else:
                        report.lost_walk += 1
                    continue
                qty = 1
                available = line.sizes.get(size, 0) if size else line.on_hand
                if product.price <= 24 and available > 1 and rng.chance(0.35):
                    qty = 2
                _ring(state, door, report, rng, product, qty, size or None)
                if door.stock[product.id].on_hand <= 0:
                    stocked[category] = [item for item in options if item.id != product.id]
        if remaining:
            _run_aggregate(
                state,
                report,
                remaining,
                weights,
                stocked,
                walked,
                staff_mult,
                store_id=door.id,
                stock=door.stock,
                sell=lambda product, qty, sell_rng: _ring(state, door, report, sell_rng, product, qty, None),
                shelf=shelf,
            )
        sold_revenue = report.revenue - revenue_before
    sold_units = report.units - units_before
    sold_tax = report.tax_collected - tax_before
    door.week_sales += sold_revenue - (report.refunds - refunds_before)
    door.week_cogs += report.cogs - cogs_before
    door.last_sales = sold_revenue
    who = manager.name if manager else "No manager"
    report.notes.append(
        f"{door.city} ({who}) did {money(sold_revenue)} on {sold_units} sales. "
        f"Sales tax {money(sold_tax)} at {rate_label(door.sales_tax_bps)}. "
        f"The wall matched the planogram at {door.compliance}."
    )
    _shrink_door(state, door, report, rng, manager)
    shrink = report.shrink_cost - shrink_before
    sold_cogs = report.cogs - cogs_before_door - shrink
    if sold_cogs < 0:
        sold_cogs = 0
    from open_late.hq import record_door_trading_day

    by_department = {
        key: report.by_category.get(key, 0) - dept_before.get(key, 0)
        for key in set(report.by_category) | set(dept_before)
        if report.by_category.get(key, 0) - dept_before.get(key, 0)
    }
    record_door_trading_day(
        state,
        door.id,
        sales=sold_revenue - (report.refunds - refunds_before),
        cogs=sold_cogs,
        shrink=shrink,
        card_fees=report.card_fees - fees_before,
        by_department=by_department,
        visits=arrived,
    )


def _shrink_door(state: GameState, door: Door, report, rng, manager: StoreManager | None) -> None:
    from open_late.engine import _take_stock

    rate = 0.04 if manager is None else max(0.004, (100 - manager.operations) / 2500)
    from open_late.hq import shrink_mult
    rate = rate * shrink_mult(state, door.id)
    for product_id, line in door.stock.items():
        if line.on_hand <= 0 or not rng.chance(rate):
            continue
        product = state.products[product_id]
        lost = _take_stock(line, product, 1)
        if not lost:
            continue
        report.shrink_units += lost
        report.shrink_cost += product.cost * lost
        report.cogs += product.cost * lost
        door.week_shrink += product.cost * lost


def _sunday(state: GameState, report) -> None:
    from open_late.engine import _pay
    from open_late.finance import insurance_weekly, interest_due, payroll_parts, record_payday, utilities_weekly

    rent = sum(site.rent_weekly for site in state.sites)
    staff_wages, staff_tax = payroll_parts(state)
    manager_wages = sum(person.wage for person in state.managers if person.employed)
    manager_tax = manager_wages * PAYROLL_TAX_PER_TEN_THOUSAND // 10000
    predictability = sum(door.predictability_due for door in state.doors)
    payroll = staff_wages + manager_wages + predictability
    payroll_tax = staff_tax + manager_tax
    interest = interest_due(state)
    loan_principal = 0
    if getattr(state, "rival_ai", None) is not None:
        # Rival AI on: building-loan interest joins the interest bill (same Fed multiplier).
        from open_late.rival_ai import player_loan_service

        loan_interest, loan_principal = player_loan_service(state)
        interest += loan_interest
    insurance = insurance_weekly(state)
    utilities = utilities_weekly(state)
    from open_late.economy_e3 import adjust_sunday_bills

    rent, payroll, payroll_tax, insurance, utilities, interest = adjust_sunday_bills(
        state, rent, payroll, payroll_tax, insurance, utilities, interest, store_id="__chain__"
    )
    record_payday(state)
    unpaid = 0
    for field, amount in (
        ("interest_paid", interest),
        ("rent_paid", rent),
        ("payroll_paid", payroll),
        ("payroll_tax_paid", payroll_tax),
        ("insurance_paid", insurance),
        ("utilities_paid", utilities),
    ):
        missed = _pay(state, amount)
        setattr(report, field, amount - missed)
        unpaid += missed
    if loan_principal:
        missed = _pay(state, loan_principal)
        report.loan_principal_paid = loan_principal - missed
        unpaid += missed
        from open_late.books import post

        post(state, "loan", -report.loan_principal_paid, "Building loan principal.")
        if report.loan_principal_paid:
            report.notes.append(f"Building loan principal {money(report.loan_principal_paid)}.")
    remit = state.tax_held
    if remit:
        missed_tax = _pay(state, remit)
        report.tax_remitted = remit - missed_tax
        state.tax_held = missed_tax
        state.tax_lifetime += report.tax_remitted
        state.quarter_tax += report.tax_remitted
        unpaid += missed_tax
    from open_late.finance import weekly_depreciation

    depreciation = weekly_depreciation(state.fixtures, state.accumulated_depreciation)
    state.accumulated_depreciation += depreciation
    report.depreciation = depreciation
    state.quarter_depreciation += depreciation
    report.shortfall = unpaid
    if unpaid:
        state.flags.shortfalls += 1
        report.flags.append(
            f"Sunday bills missed {money(unpaid)}. Credit is {money(state.credit_used)} of {money(state.credit_limit)}."
        )
    else:
        state.flags.shortfalls = 0
    if predictability:
        report.notes.append(f"Predictability pay {money(predictability)} for a schedule that moved after Monday.")
    from open_late.hq import close_sunday_corporate
    close_sunday_corporate(state, report)
    for door in state.doors:
        manager = manager_by_id(state, door.manager_id) if door.manager_id else None
        labor = 0
        if manager is not None and manager.employed and manager.door_id == door.id:
            labor += manager.wage
        for person in state.staff:
            if person.employed and person.door_id == door.id and person.assignment != "off":
                labor += week_gross(person, door)
        labor += door.predictability_due
        contribution = door.week_sales - door.week_cogs - door.week_shrink - labor - door.rent_weekly - door.week_freight
        door.last_week_sales = door.week_sales
        door.last_contribution = contribution
        report.notes.append(
            f"{door.city} contribution {money(contribution)} on sales {money(door.week_sales)} "
            "after cost, shrink, labor, rent, and freight."
        )
        door.week_sales = 0
        door.week_cogs = 0
        door.week_shrink = 0
        door.week_freight = 0
        door.predictability_due = 0
    _markdown(state, report)


def _markdown(state: GameState, report) -> None:
    for product in state.products.values():
        if product.id in state.cleared_ids:
            continue
        ages = []
        warehouse = state.stock.get(product.id)
        if warehouse is not None and warehouse.on_hand > 0:
            ages.append(warehouse.age_days)
        for door in state.doors:
            line = door.stock.get(product.id)
            if line is not None and line.on_hand > 0:
                ages.append(line.age_days)
        if not ages or max(ages) < state.markdown_after_days:
            continue
        if int(getattr(product, "shelf_life_days", 0) or 0) > 0:
            continue
        cut = max(1, product.price * state.markdown_percent // 100)
        new_price = max(product.cost, product.price - cut)
        if new_price >= product.price:
            state.cleared_ids.append(product.id)
            continue
        product.price = new_price
        state.cleared_ids.append(product.id)
        report.notes.append(
            f"Markdown on {product.name} to {money(new_price)}. The oldest piece has sat {max(ages)} days."
        )


def close_corporate_day(state: GameState) -> str:
    from open_late import situations
    from open_late.engine import (
        Rng,
        _check_failure,
        _close_books,
        _receive_orders,
        _settle_payables,
        _stamp_spend,
        _tick_campaign,
        _top_sellers,
        narrate,
    )

    if state.failed:
        return "The company is already closed for good."
    if state.phase not in ("morning", "desk"):
        return "The day is already closed."
    from open_late.engine import blocking
    from open_late.pricing import offer_landed_choice

    offer_landed_choice(state)
    if blocking(state):
        return "Answer the urgent notes before you close."
    from open_late.engine import _ensure_books

    _ensure_books(state)
    rng = Rng(state)
    from open_late.models import DayReport

    report = DayReport(day=state.day, weekday=weekday_name(state.day), purchases=state.spent_today)
    _stamp_spend(state, report)
    _receive_orders(state, report, rng)
    receive_shipments(state, report)
    report.cash_open = state.cash
    report.credit_open = state.credit_used
    for line in state.stock.values():
        if line.on_hand > 0:
            line.age_days += 1
    from open_late.engine import _note_expiry, _spoil_stock
    from open_late.hq import HOME_STORE_ID, record_door_trading_day

    warehouse_spoil = _spoil_stock(state.stock, state.products, report)
    from open_late.economy import apply_daily_spoil, economy_daily_news, economy_end_day

    warehouse_spoil += apply_daily_spoil(state, state.stock, state.products, HOME_STORE_ID, report)
    if warehouse_spoil:
        record_door_trading_day(
            state,
            HOME_STORE_ID,
            sales=0,
            cogs=0,
            shrink=warehouse_spoil,
            card_fees=0,
        )
    stocks = [state.stock]
    for door in state.doors:
        for line in door.stock.values():
            if line.on_hand > 0:
                line.age_days += 1
        _sell_door(state, door, report, rng)
        stocks.append(door.stock)
    _note_expiry(state, report, stocks)
    if is_sunday(state.day):
        _sunday(state, report)
        from open_late.economy import economy_tick

        economy_tick(state)
    from open_late.economy import economy_daily_news, economy_end_day

    economy_daily_news(state)
    economy_end_day(state)
    _settle_payables(state, report)
    from open_late.dc import fill_thin_pools, units_on_road

    if not state.failed:
        fill_thin_pools(state)
    report.on_road = units_on_road(state)
    _close_books(state, report)
    _top_sellers(state, report)
    _check_failure(state)
    from open_late.finance import close_labor

    report.labor_hours, report.labor_overtime = close_labor(state, report)
    state.last_report = report
    state.history.append(report)
    if len(state.history) > 60:
        state.history = state.history[-60:]
    from open_late.books import stamp_decision_results

    stamp_decision_results(state, report)
    text = narrate(state, report)
    state.journal.append(text)
    state.journal = state.journal[-40:]
    situations.collect(state, report, rng)
    _tick_campaign(state)
    from open_late.hq import finish_close
    finish_close(state)
    state.phase = "gameover" if state.failed else "evening"
    return ""


def manager_blocks_schedule(state: GameState, staff_id: str) -> str:
    person = next((member for member in state.staff if member.id == staff_id), None)
    if person is None or not person.door_id:
        return ""
    door = door_by_id(state, person.door_id)
    if door is None or not door.manager_id:
        return ""
    manager = manager_by_id(state, door.manager_id)
    if manager is None:
        return ""
    return f"{manager.name} writes the schedule at {door.city}."
