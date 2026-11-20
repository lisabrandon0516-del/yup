"""Day resolver and desk actions.

Close order: deliveries, attendance, sales, regulars, event, staff, reputation,
Sunday bills, failure check, inbox, then the evening report.
"""

from __future__ import annotations

import random
import uuid

from open_late import situations
from open_late.content import (
    LABEL_MIN_DAY,
    LABEL_MIN_REP,
    LABEL_PRODUCTS,
    LABEL_SETUP_COST,
    OFFERS,
    ONLINE_SETUP_COST,
    ONLINE_STOCK,
    PRODUCTS,
    REGULARS,
    SHOP_STOCK,
    SIDE_STREET,
    STAFF,
    SUPPLIERS,
)
from open_late.books import (
    TERMS_RELATIONSHIP,
    close_quarter,
    format_margin,
    note_decision,
    post,
    stamp_decision_results,
    tax_on,
)
from open_late.finance import (CREW_MULT, 
    CREDIT_LIMIT,
    RIVAL_ENTRY_MIN_DAY,
    RIVAL_ENTRY_WEEK_SALES,
    SIZE_MULT,
    SIZE_WEIGHTS,
    STABLE_MONTH_CASH,
    allocate_sizes,
    card_fee,
    close_labor,
    damage_chance,
    freight_for,
    income_tax_due,
    insurance_weekly,
    interest_due,
    is_sized,
    payroll_parts,
    record_payday,
    shipping_for,
    size_int,
    starting_reserve,
    utilities_weekly,
    weekly_depreciation,
)
from open_late.inbox import add
from open_late.models import (
    Campaign,
    Choice,
    DayReport,
    EventPlan,
    GameState,
    Product,
    PurchaseOrder,
    Site,
    StockLine,
    SupplierAccount,
    Target,
)
from open_late.text import clamp, is_sunday, money, weekday_name

CONVERSION = 0.42
BASKET_SIZE = 10
# Named baskets per door for flavor; the rest of demand is aggregated (E7b).
NAMED_BASKET_CAP = 300
DOW_MULT = (0.84, 0.90, 0.96, 1.04, 1.34, 1.50, 0.76)
ASSIGNMENTS = ("floor", "fulfillment", "modeling", "private", "event", "training", "off")
CAMPAIGN_COST = {
    "social": size_int(70),
    "email": size_int(150),
    "local_ad": size_int(400),
    "influencer": size_int(980),
}
CAMPAIGN_DAYS = {"social": 3, "email": 4, "local_ad": 5, "influencer": 6}
CAMPAIGN_TRAFFIC = {"social": 1.14, "email": 1.08, "local_ad": 1.20, "influencer": 1.30}


class Rng:
    def __init__(self, state: GameState):
        self.state = state

    def _py(self) -> random.Random:
        self.state.rng_counter += 1
        return random.Random(f"{self.state.seed}:{self.state.rng_counter}")

    def random(self) -> float:
        return self._py().random()

    def randint(self, a: int, b: int) -> int:
        return a if a >= b else self._py().randint(a, b)

    def chance(self, probability: float) -> bool:
        if probability <= 0:
            return False
        if probability >= 1:
            return True
        return self.random() < probability

    def uniform(self, low: float, high: float) -> float:
        return low + (high - low) * self.random()

    def choice(self, seq):
        return seq[self.randint(0, len(seq) - 1)]

    def weighted(self, weights: dict[str, float], total: float | None = None) -> str:
        if total is None:
            total = sum(max(0.0, weight) for weight in weights.values())
        if total <= 0:
            return self.choice(list(weights))
        roll = self.random() * total
        upto = 0.0
        last = next(iter(weights))
        for key, weight in weights.items():
            last = key
            upto += max(0.0, weight)
            if roll <= upto:
                return key
        return last


def new_game(
    shop_name: str,
    mode: str,
    seed: int | None = None,
    chain_id: str | None = None,
    economy_difficulty: str | None = None,
    rival_ai: bool | None = None,
) -> GameState:
    """``rival_ai``: True starts the three AI rival chains (economy must be on);
    None follows ``open_late.rival_ai.default_enabled`` (off unless the launcher
    turned it on); False keeps the single Northline rival."""
    state = _new_game(shop_name, mode, seed, chain_id, economy_difficulty)
    from open_late import rival_ai as _rival_ai

    if rival_ai is None:
        rival_ai = _rival_ai.default_enabled(state.economy.difficulty)
    if rival_ai:
        _rival_ai.enable(state)
    from open_late import shelves as _shelves  # Lite shelves: on for new corporate games when the launcher says so

    if state.mode == "corporate" and _shelves.default_enabled():
        _shelves.enable_shelves(state)
    from open_late import shopperlife as _shoppers

    _shoppers.ensure(state)
    from open_late.books import ensure_owner_capital

    ensure_owner_capital(state)
    return state


def _new_game(shop_name: str, mode: str, seed: int | None = None, chain_id: str | None = None, economy_difficulty: str | None = None) -> GameState:
    if mode == "corporate":
        from open_late.corporate import new_corporate

        return new_corporate(shop_name, seed, chain_id=chain_id, economy_difficulty=economy_difficulty)
    if mode not in ("shop", "online"):
        raise ValueError("mode must be shop or online")
    from open_late import GAME_NAME

    name = shop_name.strip() or GAME_NAME
    catalog = {product.id: product.model_copy(deep=True) for product in PRODUCTS}
    quantities = SHOP_STOCK if mode == "shop" else ONLINE_STOCK
    stock = {}
    for product_id in catalog:
        on_hand = quantities.get(product_id, 0)
        sizes = allocate_sizes(on_hand) if is_sized(catalog[product_id]) and on_hand else {}
        stock[product_id] = StockLine(product_id=product_id, on_hand=on_hand, sizes=sizes)
    stock_cost = sum(catalog[pid].cost * line.on_hand for pid, line in stock.items())
    reserve = starting_reserve(mode, economy_difficulty)
    staff = [person.model_copy(deep=True) for person in STAFF]
    starters = ("alyssa", "jordan", "priya", "naomi", "marisol", "dean") if mode == "shop" else ("chris", "marisol")
    for person in staff:
        person.wage_ask = person.wage
        person.review_due = 28
        if person.id in starters:
            person.employed = True
            person.assignment = "fulfillment" if person.id == "chris" else "floor"
    state = GameState(
        slot=uuid.uuid4().hex,
        shop_name=name,
        mode=mode,  # type: ignore[arg-type]
        seed=seed if seed is not None else random.randrange(1, 10_000_000),
        save_version=4,
        cash=stock_cost + reserve,
        credit_limit=CREDIT_LIMIT,
        products=catalog,
        stock=stock,
        staff=staff,
        regulars=[person.model_copy(deep=True) for person in REGULARS],
        sites=[SIDE_STREET.model_copy(deep=True)] if mode == "shop" else [],
        reputation_respectable=48 if mode == "shop" else 44,
        reputation_nightlife=32 if mode == "shop" else 36,
    )
    state.cash -= stock_cost
    state.flags.online_open = mode == "online"
    state.list_size = 140 if mode == "online" else 60
    state.fixtures = 1800 if mode == "online" else 2400
    _ensure_accounts(state)
    _seed_targets(state, 28)
    from open_late.chains import DEFAULT_CHAIN_ID, set_chain

    set_chain(state, chain_id or DEFAULT_CHAIN_ID)
    from open_late.economy import configure_new_game

    configure_new_game(state, economy_difficulty)
    if mode == "shop":
        body = (
            f"Monday, day one. {name} has the riverside lease and the float is in the drawer. "
            "Alyssa is building the seasonal endcap. Jordan is stocking the frozen wall and asked you not "
            "to put him in the weekly ad. Rent and payroll come out on Sunday. "
            "Urgent notes have to be answered before you can close."
        )
    else:
        body = (
            f"Monday, day one. {name} is a plain site and a packing table. Chris has the mailers. "
            "Marisol is answering people in a careful voice. There is no shop floor yet, so in-store events "
            "wait until you rent a room. Sunday is payroll. Urgent notes have to be answered before you can close."
        )
    add(state, kind="opening", title="Opening note", body=body)
    return state


def staff_by_id(state: GameState, staff_id: str):
    return next((person for person in state.staff if person.id == staff_id), None)


def regular_by_id(state: GameState, regular_id: str):
    return next((person for person in state.regulars if person.id == regular_id), None)


def blocking(state: GameState):
    return [message for message in state.inbox if message.urgent and not message.resolved]


def open_desk(state: GameState) -> str:
    if state.failed:
        return "The shop is closed."
    if state.phase != "morning":
        return ""
    state.phase = "desk"
    return ""


def set_price(state: GameState, product_id: str, price: int) -> str:
    product = state.products.get(product_id)
    if product is None:
        return "That item is not on the sheet."
    if price < product.cost:
        return "Price stays at cost or above."
    if price > product.cost * 5:
        return "Cap is five times cost."
    price = int(price)
    if price != int(product.price):
        old = int(product.price)
        state.price_was[product.id] = old
        product.price = price
        prior = state.last_report
        had_close = bool(prior.day)
        note_decision(
            state,
            "price",
            f"{product.name} was {money(old)}. It is {money(price)}.",
            ref=product.id,
            before_units=int((prior.units_by_product or {}).get(product.id, 0) or 0) if had_close else 0,
            before_walked=int((prior.lost_price_by_product or {}).get(product.id, 0) or 0) if had_close else 0,
        )
        return ""
    product.price = price
    return ""


def set_assignment(state: GameState, staff_id: str, assignment: str) -> str:
    person = staff_by_id(state, staff_id)
    if person is None or not person.employed:
        return "They are not on payroll."
    if state.mode == "corporate":
        from open_late.corporate import manager_blocks_schedule

        blocked = manager_blocks_schedule(state, staff_id)
        if blocked:
            return blocked
    if assignment not in ASSIGNMENTS:
        return "That is not a shift."
    person.assignment = assignment  # type: ignore[assignment]
    return "Shift set." + _boundary_warning(person, assignment)


def _boundary_warning(person, assignment: str) -> str:
    if assignment == "modeling" and ("no_modeling" in person.boundaries or person.comfort_modeling < 35):
        return f" {person.name} has already said they will not pose for the weekly ad."
    if assignment == "private" and "no_private" in person.boundaries:
        return f" {person.name} does not work the appointment desk."
    if assignment == "event" and "no_events" in person.boundaries:
        return f" {person.name} does not host."
    if assignment == "event" and "no_intense_demo" in person.boundaries:
        return f" {person.name} will host, and will not work a pharmacy rush alone."
    return ""


def hire(state: GameState, staff_id: str) -> str:
    person = staff_by_id(state, staff_id)
    if person is None:
        return "No one by that name."
    if person.employed:
        return f"{person.name} is already on the sheet."
    if sum(1 for member in state.staff if member.employed) >= _headcount_cap(state):
        return "The room cannot hold another name. Expand, or let someone go."
    person.employed = True
    person.assignment = "fulfillment" if person.aptitude_fulfillment > person.aptitude_floor + 15 else "floor"
    person.mood = 70
    person.burnout = 10
    state.actions_today.append(f"Hired {person.name}.")
    return f"{person.name} is on the sheet. Wage {money(person.wage)} a week."


def release(state: GameState, staff_id: str) -> str:
    person = staff_by_id(state, staff_id)
    if person is None or not person.employed:
        return "They are not on payroll."
    if state.cash < person.wage:
        return f"Severance is a week's wage, {money(person.wage)}, and the drawer does not have it."
    state.cash -= person.wage
    state.spent_today += person.wage
    state.spent_severance += person.wage
    person.employed = False
    person.assignment = "off"
    if person.loyalty >= 70:
        for other in state.staff:
            if other.employed:
                other.loyalty = clamp(other.loyalty - 4, 0, 100)
    state.actions_today.append(f"Let {person.name} go.")
    left = sum(1 for member in state.staff if member.employed)
    tail = " No one is left to open tomorrow." if left == 0 else ""
    return f"{person.name} is off the sheet. Severance {money(person.wage)}.{tail}"


def _headcount_cap(state: GameState) -> int:
    physical = sum(1 for site in state.sites if site.is_physical)
    warehouse = any(site.is_warehouse for site in state.sites)
    return 4 + 3 * max(1, physical) + (2 if warehouse else 0)


def place_order(state: GameState, supplier_id: str, quantities: dict[str, int]) -> str:
    ok, message = _add_order(state, supplier_id, quantities, ignore_minimum=False)
    return message if ok or message else message


def _add_order(
    state: GameState,
    supplier_id: str,
    quantities: dict[str, int],
    ignore_minimum: bool,
) -> tuple[bool, str]:
    supplier = SUPPLIERS.get(supplier_id)
    if supplier is None:
        return False, "Unknown supplier."
    if supplier_id == "labelco" and not state.flags.private_label:
        return False, "Private Label Co waits until you pay for the label."
    deal = None
    if state.mode == "corporate":
        from open_late.corporate import deal_for

        deal = deal_for(state, supplier_id)
    off = deal.cost_off_percent if deal is not None else 0
    clean: dict[str, int] = {}
    cost = 0
    standard = 0
    for product_id, qty in quantities.items():
        amount = int(qty)
        if amount <= 0:
            continue
        product = state.products.get(product_id)
        if product is None:
            return False, "That item is not on the sheet."
        if product.supplier_id != supplier_id:
            return False, f"{product.name} is not on {supplier.name}'s sheet."
        clean[product_id] = amount
        standard += product.cost * amount
        line_cost = product.cost * amount * (100 - off) // 100
        from open_late.economy import landed_cost
        from open_late.hq import HOME_STORE_ID

        line_cost = landed_cost(state, HOME_STORE_ID, product.department, line_cost)
        cost += line_cost
    if not clean:
        return False, "The order is empty."
    if not ignore_minimum and cost < supplier.minimum_order:
        return False, f"{supplier.name} minimum is {money(supplier.minimum_order)}. This sheet is {money(cost)}."
    freight = freight_for(supplier.lead_time_days, cost)
    from open_late.economy import adjust_freight
    from open_late.hq import HOME_STORE_ID

    freight = adjust_freight(state, HOME_STORE_ID, freight)
    bill = cost + freight
    account = _account(state, supplier_id)
    term_span = 0
    if deal is not None and deal.terms in ("net14", "net30"):
        on_terms = account is not None
        term_span = 30 if deal.terms == "net30" else 14
    elif account is not None and account.terms == "net30":
        on_terms = True
        term_span = 30
    elif account is not None and account.terms == "net14" and account.relationship >= TERMS_RELATIONSHIP:
        on_terms = True
        term_span = 14
    else:
        on_terms = False
    if on_terms and account is not None:
        account.payable += bill
        account.due_day = max(account.due_day, state.day + term_span)
        account.volume += cost
        post(state, "payable", bill, f"Net 14 with {supplier.name}, freight included.")
    else:
        if state.cash < bill:
            return False, (
                f"That order is {money(bill)} with freight and the drawer has {money(state.cash)}. "
                "Credit does not pay suppliers."
            )
        state.cash -= bill
        state.spent_today += bill
        if account is not None:
            account.volume += cost
        post(state, "inventory", -bill, f"Paid {supplier.name}, including freight.")
    state.spent_merchandise += standard
    state.spent_freight += freight
    state.spent_variance += cost - standard
    for product_id, amount in clean.items():
        state.stock[product_id].on_order += amount
    lead = supplier.lead_time_days
    if account is not None and account.relationship >= 75:
        lead = max(1, lead - 1)
    from open_late.economy import lead_slip_days

    depts = {state.products[pid].department for pid in clean if pid in state.products}
    lead += max((lead_slip_days(state, dept) for dept in depts), default=0)
    arrives = state.day + lead
    state.orders.append(
        PurchaseOrder(
            id=f"po{state.next_order_id}",
            supplier_id=supplier_id,
            lines=clean,
            arrives_on=arrives,
            cost=cost,
            placed_on=state.day,
            freight=freight,
        )
    )
    state.next_order_id += 1
    state.actions_today.append(f"Ordered from {supplier.name} for {money(bill)}.")
    if freight:
        from open_late.hq import HOME_STORE_ID, record
        record(state, HOME_STORE_ID, freight=freight)
    if deal is not None and deal.coop_percent and cost:
        deal.coop_accrued += cost * deal.coop_percent // 100
    how = f"on net {term_span}" if on_terms else "paid from the drawer"
    placed = state.orders[-1]
    note_decision(
        state,
        "order",
        f"Ordered from {supplier.name} for {money(bill)}. Arrives in {lead} days.",
        ref=placed.id,
        result=f"Due day {placed.arrives_on}.",
    )
    return True, (
        f"Order placed with {supplier.name} for {money(cost)} plus {money(freight)} freight, {how}. "
        f"It arrives in {lead} days."
    )


def order_qty_max() -> int:
    """Highest quantity the shop order sheet should accept for one SKU."""
    from open_late.content import WANT_STAPLE

    return max(40 * SIZE_MULT, WANT_STAPLE)


def suggested_restock_quantities(state: GameState, supplier_id: str) -> dict[str, int]:
    """Modest fill: quality 3+ SKUs up to the family share of department want."""
    from open_late.content import case_round, family_want_map, family_want_units

    cap = order_qty_max()
    wants = family_want_map(state.products.values())
    quantities: dict[str, int] = {}
    for product in state.products.values():
        if product.supplier_id != supplier_id or product.quality < 3:
            continue
        line = state.stock.get(product.id)
        on_hand = int(line.on_hand) if line is not None else 0
        on_order = int(getattr(line, "on_order", 0) or 0) if line is not None else 0
        want = wants.get(product.department)
        if want is None:
            want = family_want_units(product.department, state.products.values())
        need = want - on_hand - on_order
        if need > 0:
            quantities[product.id] = min(cap, case_round(need, getattr(product, "case_size", 1)))
    return quantities


def fit_order_to_budget(state: GameState, items: dict[str, int], budget: int) -> dict[str, int]:
    """Shrink a supplier sheet so its merchandise cost fits in budget."""
    priced: list[tuple[str, int, int]] = []
    for product_id, qty in items.items():
        amount = int(qty)
        if amount <= 0:
            continue
        product = state.products.get(product_id)
        if product is None or product.cost <= 0:
            continue
        priced.append((product_id, amount, int(product.cost)))
    total = sum(qty * cost for _pid, qty, cost in priced)
    if total <= 0 or budget <= 0:
        return {}
    if total <= budget:
        return {product_id: qty for product_id, qty, _cost in priced}
    fitted: dict[str, int] = {}
    for product_id, qty, cost in priced:
        take = (qty * budget) // total
        if take > 0:
            fitted[product_id] = take
    spent = sum(state.products[pid].cost * qty for pid, qty in fitted.items())
    leftover = budget - spent
    for product_id, qty, cost in priced:
        if leftover < cost:
            continue
        have = fitted.get(product_id, 0)
        add = min(qty - have, leftover // cost)
        if add > 0:
            fitted[product_id] = have + add
            leftover -= add * cost
    return fitted


def place_capped_restock(
    state: GameState,
    basket: dict[str, dict[str, int]],
    cap: int,
    reserve: int,
    ignore_minimum: bool = True,
) -> int:
    """Place restock orders under a dollar cap without skipping a whole expensive sheet.

    Each supplier that still needs stock gets an equal first slice of the cap, then
    any leftover is offered cheap-first, shrinking a sheet to fit when required.
    """
    if cap <= 0 or state.cash <= reserve or not basket:
        return 0
    budget = min(int(cap), max(0, int(state.cash) - int(reserve)))
    rows: list[tuple[int, str, dict[str, int]]] = []
    for supplier_id, items in basket.items():
        cost = sum(state.products[pid].cost * qty for pid, qty in items.items() if pid in state.products)
        if cost > 0:
            rows.append((cost, supplier_id, dict(items)))
    if not rows:
        return 0
    rows.sort()
    planned: dict[str, dict[str, int]] = {supplier_id: {} for _cost, supplier_id, _items in rows}

    # When the whole basket fits, take it (still cash-safe).
    total = sum(cost for cost, _sid, _items in rows)
    slices: list[tuple[str, dict[str, int], int]] = []
    if total <= budget:
        for cost, supplier_id, items in rows:
            slices.append((supplier_id, items, cost))
    else:
        first = budget // len(rows)
        leftover_need: list[tuple[int, str, dict[str, int]]] = []
        allocated = 0
        for cost, supplier_id, items in rows:
            allow = min(cost, first, budget - allocated)
            fitted = items if allow >= cost else fit_order_to_budget(state, items, allow)
            if fitted:
                fcost = sum(state.products[pid].cost * qty for pid, qty in fitted.items())
                planned[supplier_id] = dict(fitted)
                allocated += fcost
                rest = {
                    pid: qty - fitted.get(pid, 0)
                    for pid, qty in items.items()
                    if qty - fitted.get(pid, 0) > 0
                }
                if rest:
                    leftover_need.append((
                        sum(state.products[pid].cost * qty for pid, qty in rest.items()),
                        supplier_id,
                        rest,
                    ))
            else:
                leftover_need.append((cost, supplier_id, items))
        leftover_need.sort()
        leftover = budget - allocated
        for cost, supplier_id, items in leftover_need:
            if leftover <= 0:
                break
            allow = min(cost, leftover)
            fitted = items if allow >= cost else fit_order_to_budget(state, items, allow)
            if not fitted:
                continue
            fcost = sum(state.products[pid].cost * qty for pid, qty in fitted.items())
            current = planned.setdefault(supplier_id, {})
            for pid, qty in fitted.items():
                current[pid] = current.get(pid, 0) + qty
            leftover -= fcost
        slices = [(sid, items, sum(state.products[pid].cost * qty for pid, qty in items.items()))
                  for sid, items in planned.items() if items]

    spent = 0
    for supplier_id, items, cost in slices:
        allow = max(0, min(cost, state.cash - reserve))
        fitted = items if allow >= cost else fit_order_to_budget(state, items, allow)
        if not fitted:
            continue
        ok, _message = _add_order(state, supplier_id, fitted, ignore_minimum=ignore_minimum)
        if ok:
            spent += sum(state.products[pid].cost * qty for pid, qty in fitted.items())
    return spent


def set_supplier_terms(state: GameState, supplier_id: str, terms: str) -> str:
    _ensure_accounts(state)
    supplier = SUPPLIERS.get(supplier_id)
    account = _account(state, supplier_id)
    if supplier is None or account is None:
        return "Unknown supplier."
    if terms not in ("cash", "net14"):
        return "Terms are cash or net 14."
    if terms == "net14" and account.relationship < TERMS_RELATIONSHIP:
        return (
            f"{supplier.name} will not carry you. Relationship is {account.relationship}. "
            f"They open terms at {TERMS_RELATIONSHIP}."
        )
    account.terms = terms  # type: ignore[assignment]
    if terms == "cash":
        return f"{supplier.name} is back to cash with the order."
    return f"{supplier.name} will take net 14. The bill is still real. It is just not today."


def offer_raise(state: GameState, staff_id: str) -> str:
    person = staff_by_id(state, staff_id)
    if person is None or not person.employed:
        return "They are not on payroll."
    bump = max(25, person.wage // 12)
    person.wage += bump
    person.wage_ask = person.wage
    person.loyalty = clamp(person.loyalty + 10, 0, 100)
    person.mood = clamp(person.mood + 6, 0, 100)
    person.review_due = state.day + 28
    state.actions_today.append(f"Raised {person.name} to {money(person.wage)}.")
    return f"{person.name} is at {money(person.wage)} a week. The next look is in four weeks. Sunday payroll moved with it."


def set_hours(state: GameState, open_hour: int, close_hour: int) -> str:
    open_hour = int(open_hour)
    close_hour = int(close_hour)
    if not (8 <= open_hour < close_hour <= 23):
        return "Hours have to sit between 8 and 23."
    if close_hour - open_hour < 4:
        return "Fewer than four hours is not a shop."
    state.open_hour = open_hour
    state.close_hour = close_hour
    span = close_hour - open_hour
    return (
        f"Open {open_hour}:00 to {close_hour}:00 ({span} hours). "
        "Traffic and Sunday payroll both move with the hours. Eight hours is the base week."
    )


def owner_draw(state: GameState, amount: int) -> str:
    amount = int(amount)
    if amount <= 0:
        return "Nothing to take."
    if state.cash < amount:
        return f"The drawer has {money(state.cash)}. A draw cannot use the credit line."
    state.cash -= amount
    state.owner_draws += amount
    state.spent_today += amount
    state.spent_draws += amount
    post(state, "draw", -amount, "Owner draw.")
    return f"You took {money(amount)}. Draws are not an expense. They still will not pay Sunday."


def launch_campaign(
    state: GameState,
    kind: str,
    tone: str,
    category: str,
    staff_id: str | None,
    door_id: str | None = None,
) -> str:
    if kind not in CAMPAIGN_COST:
        return "That is not a campaign."
    if tone not in ("discreet", "playful", "bold"):
        return "Pick a tone."
    if category not in state.products and category not in {product.category for product in state.products.values()}:
        return "Pick a category you actually sell."
    if category not in {product.category for product in state.products.values()}:
        return "Pick a category you actually sell."
    if state.campaign and state.campaign.days_left > 0:
        return "A campaign is already running."
    person = None
    if kind == "social":
        if not staff_id:
            return "Pick a person for the post, or send an email instead."
        person = staff_by_id(state, staff_id)
        if person is None or not person.employed:
            return "That person is not on payroll."
    cities = max(1, len(state.doors)) if state.mode == "corporate" and not door_id else 1
    if door_id and not any(door.id == door_id for door in state.doors):
        return "That city is not on the lease."
    cost = CAMPAIGN_COST[kind] * cities
    rebate = 0
    if state.mode == "corporate":
        from open_late.corporate import coop_claimable

        rebate = min(cost, coop_claimable(state))
    due = cost - rebate
    if state.cash < due:
        return f"The campaign is {money(due)} and the drawer has {money(state.cash)}."
    state.cash -= due
    state.spent_today += due
    state.spent_advertising += due
    rng = Rng(state)
    if tone == "bold" and kind in ("local_ad", "influencer"):
        threshold = 0.10 + max(0, 60 - state.flags.platform_trust) / 200
        if state.reputation_nightlife > state.reputation_respectable + 18:
            threshold += 0.08
        if rng.chance(threshold):
            state.flags.platform_trust = clamp(state.flags.platform_trust - 8, 0, 100)
            state.flags.neighbor_heat = clamp(state.flags.neighbor_heat + 4, 0, 100)
            state.flags.ad_rejected = True
            add(
                state,
                kind="ad",
                title="Ad rejected",
                body=(
                    f"The {kind.replace('_', ' ')} in a bold tone was rejected. "
                    f"{money(due)} is gone and nothing ran. Platform trust is {state.flags.platform_trust}."
                ),
            )
            state.actions_today.append("Bold ad rejected.")
            note_decision(
                state,
                "ad",
                f"The {kind.replace('_', ' ')} was rejected. {money(due)} is gone and nothing ran.",
                ref=kind,
                result="Nothing ran.",
            )
            return "The platform rejected the ad. The money is gone and nothing ran."
    respect = {"discreet": 2, "playful": 0, "bold": -2}[tone]
    night = {"discreet": 0, "playful": 2, "bold": 3}[tone]
    traffic = CAMPAIGN_TRAFFIC[kind] + {"discreet": -0.02, "playful": 0.0, "bold": 0.05}[tone]
    state.campaign = Campaign(
        kind=kind,  # type: ignore[arg-type]
        tone=tone,  # type: ignore[arg-type]
        days_left=CAMPAIGN_DAYS[kind],
        category=category,
        staff_id=staff_id if kind == "social" else None,
        traffic_mult=traffic,
        respect=respect,
        night=night,
        door_id=door_id or "",
    )
    state.flags.campaign_this_week = True
    note = f"{kind.replace('_', ' ').title()} is up for {CAMPAIGN_DAYS[kind]} days, tone {tone}."
    if person is not None and state.mode != "corporate":
        person.assignment = "modeling"
        if "no_modeling" in person.boundaries or person.comfort_modeling < 35:
            note += f" {person.name} did not want the camera. The shift is posted anyway."
        else:
            note += f" {person.name} will shoot it on shift."
    elif person is not None:
        note += f" {person.name} is the face. The store manager still writes the floor."
    if rebate:
        from open_late.corporate import claim_coop

        claim_coop(state, rebate)
        note += f" Co-op covered {money(rebate)}."
    if cities > 1:
        note += f" It runs in all {cities} cities."
    state.actions_today.append(note)
    prior_people = int(state.last_report.visits or 0) if state.last_report.day else 0
    note_decision(
        state,
        "ad",
        f"{note} Spent {money(due)}.",
        ref=kind,
        before_visits=prior_people,
    )
    return note


def schedule_event(state: GameState, kind: str, host_id: str, strict_rules: bool, category: str) -> str:
    if state.mode == "corporate":
        return "A night belongs to the store. The office does not book the floor."
    if kind not in ("try_on", "demo", "couples"):
        return "That is not a night you run."
    if not any(site.is_physical for site in state.sites):
        return "Events need a room. The online counter does not have one."
    if state.scheduled_event is not None:
        return "A night is already on the book."
    host = staff_by_id(state, host_id)
    if host is None or not host.employed:
        return "Pick a host who is on payroll."
    if category not in {product.category for product in state.products.values()}:
        return "Pick a category to feature."
    state.scheduled_event = EventPlan(kind=kind, host_id=host.id, strict_rules=strict_rules, category=category)  # type: ignore[arg-type]
    host.assignment = "event"
    rules = "Rules will be posted at the door." if strict_rules else "You are running it loose."
    warning = _boundary_warning(host, "event")
    if kind == "demo" and category == "pharmacy" and "no_intense_demo" in host.boundaries:
        warning = f" {host.name} will not work a pharmacy rush."
    state.actions_today.append(f"Booked {kind.replace('_', ' ')} with {host.name}.")
    return f"Booked. {host.name} hosts tonight. {rules}{warning}"


def cancel_event(state: GameState) -> str:
    if state.scheduled_event is None:
        return "Nothing is booked."
    state.scheduled_event = None
    return "The night is off the book."


def set_policy(state: GameState, policy: str) -> str:
    if policy not in ("keep_light", "balanced", "lean_in"):
        return "Pick a buying stance."
    state.flags.policy = policy  # type: ignore[assignment]
    labels = {
        "keep_light": "You are keeping the destination aisles light.",
        "balanced": "The floor will stock a bit of everything.",
        "lean_in": "You are leaning into electronics, seasonal, and the late close.",
    }
    return labels[policy]


def repay_credit(state: GameState, amount: int) -> str:
    payment = min(max(0, int(amount)), state.credit_used, state.cash)
    if payment <= 0:
        return "Nothing to pay, or nothing to pay it with."
    state.cash -= payment
    state.credit_used -= payment
    state.spent_today += payment
    state.spent_debt += payment
    return f"Paid {money(payment)} on the line. Balance {money(state.credit_used)}."


def open_online(state: GameState) -> str:
    if state.flags.online_open:
        return "The site is already up."
    if state.cash < ONLINE_SETUP_COST:
        return f"The site costs {money(ONLINE_SETUP_COST)}. The drawer has {money(state.cash)}."
    state.cash -= ONLINE_SETUP_COST
    state.spent_today += ONLINE_SETUP_COST
    state.spent_fixtures += ONLINE_SETUP_COST
    state.fixtures += ONLINE_SETUP_COST
    state.flags.online_open = True
    state.actions_today.append("Opened the online counter.")
    return "The site is plain and live. Someone still has to pack the orders."


def open_label(state: GameState) -> str:
    if state.flags.private_label:
        return "The label is already yours."
    if state.day < LABEL_MIN_DAY:
        return f"Private Label Co will talk after day {LABEL_MIN_DAY}. You are on day {state.day}."
    if max(state.reputation_respectable, state.reputation_nightlife) < LABEL_MIN_REP:
        return f"You need {LABEL_MIN_REP} on either reputation. The higher one is {max(state.reputation_respectable, state.reputation_nightlife)}."
    if state.cash < LABEL_SETUP_COST:
        return f"Setup is {money(LABEL_SETUP_COST)}. The drawer has {money(state.cash)}."
    state.cash -= LABEL_SETUP_COST
    state.spent_today += LABEL_SETUP_COST
    state.spent_fixtures += LABEL_SETUP_COST
    state.fixtures += LABEL_SETUP_COST
    state.flags.private_label = True
    for product in LABEL_PRODUCTS:
        state.products[product.id] = product.model_copy(deep=True)
        state.stock[product.id] = StockLine(product_id=product.id, on_hand=0, on_order=0)
    state.actions_today.append("Paid for a private label.")
    return "Private Label Co is open. Aisle House flour, paper towels, and dish soap can be ordered."


def open_site(state: GameState, offer_id: str) -> str:
    offer = OFFERS.get(offer_id)
    if offer is None:
        return "That site is not on the list."
    if any(site.id == offer_id for site in state.sites):
        return "That door is already yours."
    if offer.for_online_start and state.mode != "online":
        return "You already have a riverside supercenter."
    if offer.needs_online and not state.flags.online_open:
        return "Open the online counter before you rent a warehouse."
    if state.reputation_respectable < offer.min_respectable:
        return f"Respectable reputation is {state.reputation_respectable}. This site wants {offer.min_respectable}."
    if state.reputation_nightlife < offer.min_nightlife:
        return f"Nightlife reputation is {state.reputation_nightlife}. This site wants {offer.min_nightlife}."
    needed = offer.opening_cost + offer.min_cash_after
    if state.cash < needed:
        return (
            f"Opening costs {money(offer.opening_cost)} and you would have less than "
            f"{money(offer.min_cash_after)} left. The drawer has {money(state.cash)}."
        )
    state.cash -= offer.opening_cost
    state.spent_today += offer.opening_cost
    state.spent_fixtures += offer.opening_cost
    state.fixtures += offer.opening_cost
    state.sites.append(
        Site(
            id=offer.id,
            label=offer.label,
            rent_weekly=offer.rent_weekly,
            foot_traffic=offer.foot_traffic,
            neighbor_sensitivity=offer.neighbor_sensitivity,
            allows_intense=offer.allows_intense,
            is_physical=offer.is_physical,
            is_warehouse=offer.is_warehouse,
        )
    )
    state.actions_today.append(f"Opened {offer.label}.")
    return (
        f"Lease signed for {offer.label}. Opening costs {money(offer.opening_cost)}. "
        f"Rent {money(offer.rent_weekly)} every Sunday."
    )


def answer(state: GameState, message_id: str, choice_id: str) -> str:
    message = next((item for item in state.inbox if item.id == message_id), None)
    if message is None:
        return "That note is gone."
    if message.resolved:
        return "Already handled."
    choice = next((item for item in message.choices if item.id == choice_id), None)
    if choice is None:
        return "That is not one of the options."
    ok, text = apply_effect(state, choice)
    if not ok:
        return text
    message.resolved = True
    message.resolution = text
    state.actions_today.append(f"{message.title}: {choice.label}")
    return text


def apply_effect(state: GameState, choice: Choice) -> tuple[bool, str]:
    effect = choice.effect
    args = choice.args
    if effect == "pass_landed":
        from open_late.pricing import apply_pass_through

        return True, apply_pass_through(state)
    if effect == "hold_landed":
        from open_late.pricing import apply_hold

        return True, apply_hold(state)
    if effect == "story":
        return True, str(args.get("text") or "Noted.")
    if effect == "respect_boundary":
        person = staff_by_id(state, str(args.get("staff_id", "")))
        if person:
            person.loyalty = clamp(person.loyalty + 5, 0, 100)
            person.burnout = clamp(person.burnout - 6, 0, 100)
            person.mood = clamp(person.mood + 4, 0, 100)
            return True, f"You kept the limit {person.name} already set. They heard you."
        return True, "Noted."
    if effect == "push_offshift":
        person = staff_by_id(state, str(args.get("staff_id", "")))
        if person is None:
            return True, "There was no one to push."
        person.burnout = clamp(person.burnout + 14, 0, 100)
        person.loyalty = clamp(person.loyalty - 8, 0, 100)
        person.mood = clamp(person.mood - 8, 0, 100)
        person.following += 6
        return True, f"You asked {person.name} for more than the shift. They did not argue. They also did not look glad."
    if effect == "discreet_floor":
        regular = regular_by_id(state, str(args.get("customer_id", "")))
        if regular:
            regular.loyalty = clamp(regular.loyalty + 4, 0, 100)
            regular.pushiness = clamp(regular.pushiness - 8, 0, 100)
        state.reputation_respectable = clamp(state.reputation_respectable + 2, 0, 100)
        name = regular.name if regular else "They"
        return True, f"A short appointment on the open floor, no closed door. {name} did not love it. They stayed."
    if effect == "decline_private":
        regular = regular_by_id(state, str(args.get("customer_id", "")))
        if regular:
            regular.loyalty = clamp(regular.loyalty - 8, 0, 100)
            regular.pushiness = clamp(regular.pushiness - 4, 0, 100)
        state.reputation_respectable = clamp(state.reputation_respectable + 1, 0, 100)
        name = regular.name if regular else "They"
        return True, f"You told {name} manager overrides are not on the menu."
    if effect == "ban_private":
        regular = regular_by_id(state, str(args.get("customer_id", "")))
        if regular:
            regular.banned_private = True
            regular.loyalty = clamp(regular.loyalty - 28, 0, 100)
            if regular.pushiness >= 60:
                state.review_score = max(1.0, state.review_score - 0.35)
                state.review_count += 1
                state.reputation_nightlife = clamp(state.reputation_nightlife - 2, 0, 100)
                return True, f"You cut {regular.name} off from appointments. A review is already up, and it is not generous."
            return True, f"You cut {regular.name} off from appointments."
        return True, "No such regular."
    if effect == "private_booking":
        return _book_private(state, str(args.get("customer_id", "")))
    if effect == "introduce":
        regular = regular_by_id(state, str(args.get("customer_id", "")))
        if regular:
            regular.introduced = True
            regular.loyalty = clamp(regular.loyalty + int(args.get("loyalty", 6)), 0, 100)
        return True, str(args.get("text") or "They know the shop now.")
    if effect == "customer_loyalty":
        regular = regular_by_id(state, str(args.get("customer_id", "")))
        if regular:
            regular.loyalty = clamp(regular.loyalty + int(args.get("delta", 0)), 0, 100)
            if int(args.get("delta", 0)) < 0 and regular.loyalty < 15:
                regular.active = False
        return True, str(args.get("text") or "Noted.")
    if effect == "rep":
        state.reputation_respectable = clamp(state.reputation_respectable + int(args.get("respect", 0)), 0, 100)
        state.reputation_nightlife = clamp(state.reputation_nightlife + int(args.get("night", 0)), 0, 100)
        return True, str(args.get("text") or "Reputation moved.")
    if effect == "heat":
        state.flags.neighbor_heat = clamp(state.flags.neighbor_heat + int(args.get("delta", 0)), 0, 100)
        return True, str(args.get("text") or "The block noticed.")
    if effect == "cool_down":
        state.flags.neighbor_heat = clamp(state.flags.neighbor_heat - 18, 0, 100)
        state.reputation_respectable = clamp(state.reputation_respectable + 3, 0, 100)
        state.reputation_nightlife = clamp(state.reputation_nightlife - 2, 0, 100)
        state.flags.policy = "keep_light"
        return True, "You pulled the tone back. The late-hour buy is lighter this week, and the block has less to point at."
    if effect == "ignore_neighbor":
        state.flags.neighbor_heat = clamp(state.flags.neighbor_heat + 6, 0, 100)
        state.reputation_nightlife = clamp(state.reputation_nightlife + 1, 0, 100)
        return True, "You thanked them and changed nothing. The note is still on the counter."
    if effect == "back_staff":
        host = staff_by_id(state, str(args.get("host_id", "")))
        if host:
            host.loyalty = clamp(host.loyalty + 6, 0, 100)
            host.mood = clamp(host.mood + 4, 0, 100)
        state.flags.neighbor_heat = clamp(state.flags.neighbor_heat - 2, 0, 100)
        state.review_score = max(1.0, state.review_score - 0.08)
        return True, "You backed the staff in writing. That guest will not be at the next night."
    if effect == "smooth_incident":
        if state.cash < 60:
            return False, "A comp is $60 and the drawer does not have it."
        state.cash -= 60
        state.spent_today += 60
        state.spent_period += 60
        host = staff_by_id(state, str(args.get("host_id", "")))
        if host:
            host.loyalty = clamp(host.loyalty - 5, 0, 100)
            host.mood = clamp(host.mood - 4, 0, 100)
        state.flags.neighbor_heat = clamp(state.flags.neighbor_heat + 3, 0, 100)
        return True, "You comped the guest. The host noticed which side you took."
    if effect == "special_order":
        product_id = str(args.get("product_id", ""))
        product = state.products.get(product_id)
        if product is None:
            return False, "That item is not on the sheet."
        qty = int(args.get("qty", 0))
        ok, message = _add_order(state, product.supplier_id, {product_id: qty}, ignore_minimum=True)
        return ok, message
    if effect == "exclusive_run":
        product_id = str(args.get("product_id", ""))
        product = state.products.get(product_id)
        if product is None:
            return False, "That item is not on the sheet."
        qty = int(args.get("qty", 0))
        ok, message = _add_order(state, product.supplier_id, {product_id: qty}, ignore_minimum=True)
        if not ok:
            return False, message
        product.exclusive = True
        product.trend = "rising"
        return True, message + " They marked it exclusive to you."
    if effect == "book_couples":
        return _book_couples(state)
    if effect == "unlock_label":
        before = state.cash
        text = open_label(state)
        if state.cash == before and not state.flags.private_label:
            return False, text
        if "already" in text:
            return True, text
        return True, text
    if effect == "staff_rest":
        person = staff_by_id(state, str(args.get("staff_id", "")))
        if person and person.employed:
            person.assignment = "off"
            person.burnout = clamp(person.burnout - 12, 0, 100)
            person.mood = clamp(person.mood + 8, 0, 100)
            return True, f"{person.name} is off today. You said so before the shift, not after."
        return True, "They were not on the sheet."
    if effect == "review":
        state.review_score = min(5.0, max(1.0, state.review_score + int(args.get("tenths", 0)) / 10))
        return True, str(args.get("text") or "Reviews moved.")
    if effect == "markdown":
        product = state.products.get(str(args.get("product_id", "")))
        if product is None:
            return True, "The item was already gone."
        cut = max(1, product.price // 10)
        product.price = max(product.cost, product.price - cut)
        return True, f"{product.name} is {money(product.price)}. You marked it to move."
    return False, "That reply does not do anything yet."


def _book_private(state: GameState, customer_id: str) -> tuple[bool, str]:
    regular = regular_by_id(state, customer_id)
    if regular and regular.banned_private:
        return False, f"{regular.name} is already cut off from appointments."
    hosts = [person for person in state.staff if person.employed and "no_private" not in person.boundaries]
    if not hosts:
        if regular:
            regular.loyalty = clamp(regular.loyalty - 4, 0, 100)
        return False, "Nobody on payroll will take an appointment-desk request. Pick another reply."
    host = max(hosts, key=lambda person: person.product_knowledge)
    host.assignment = "private"
    if customer_id == "mark":
        state.flags.mark_private_open = True
    if regular:
        regular.loyalty = clamp(regular.loyalty + 6, 0, 100)
        regular.pushiness = clamp(regular.pushiness + 3, 0, 100)
    state.reputation_nightlife = clamp(state.reputation_nightlife + 2, 0, 100)
    name = regular.name if regular else "The guest"
    return True, f"{host.name} will take {name} today, with the rules said at the door."


def _book_couples(state: GameState) -> tuple[bool, str]:
    if not any(site.is_physical for site in state.sites):
        return False, "You need a room before you can host them."
    if state.scheduled_event is not None:
        return False, "A night is already on the book."
    hosts = [person for person in state.staff if person.employed and "no_events" not in person.boundaries]
    if not hosts:
        return False, "No one on payroll will host. Pick another reply."
    host = max(hosts, key=lambda person: person.aptitude_events)
    state.scheduled_event = EventPlan(kind="couples", host_id=host.id, strict_rules=True, category="grocery")
    host.assignment = "event"
    regular = regular_by_id(state, "samira")
    if regular:
        regular.introduced = True
        regular.loyalty = clamp(regular.loyalty + 8, 0, 100)
    return True, f"{host.name} will host Samira and Luis tonight. Rules posted."


_SELL_CACHE_KEY: tuple | None = None
_SELL_CACHE: dict = {}


def _sell_cache(state: GameState) -> dict:
    """Per-day memo for sale-time multipliers. Bit-identical; values are stable during close_day sales."""
    global _SELL_CACHE_KEY, _SELL_CACHE
    key = (id(state), int(state.day))
    if _SELL_CACHE_KEY != key:
        _SELL_CACHE = {}
        _SELL_CACHE_KEY = key
    return _SELL_CACHE


def _sale_tax(state: GameState, amount: int, store_id: str) -> int:
    if amount <= 0:
        return 0
    cache = _sell_cache(state)
    index = cache.get("tax_index")
    if index is None:
        from open_late.economy import economy_difficulty
        if economy_difficulty(state) == "off":
            index = 100
        else:
            from open_late.economy_e4 import sales_tax_index
            index = sales_tax_index(state, store_id)
        cache["tax_index"] = index
    return (amount * 8 * index) // 10000


def _sale_fee(state: GameState, store_id: str, charged: int) -> int:
    if charged <= 0:
        return 0
    cache = _sell_cache(state)
    pack = cache.get("card_fee")
    if pack is None:
        from open_late.finance import CARD_FEE_PER_THOUSAND
        from open_late.hq import _FEE_PER_THOUSAND, _active_pos_id
        from open_late.economy_e3 import card_fee_mult
        pos_id = _active_pos_id(state, store_id)
        pack = (_FEE_PER_THOUSAND.get(pos_id, CARD_FEE_PER_THOUSAND), card_fee_mult(state, store_id))
        cache["card_fee"] = pack
    rate, mult = pack
    return int(round((charged * rate) // 1000 * mult))


def _sale_cogs(state: GameState, store_id: str, department: str, base: int) -> int:
    if base <= 0:
        return 0
    cache = _sell_cache(state)
    costs = cache.setdefault("cost_mult", {})
    if department not in costs:
        from open_late.economy import cost_mult, economy_difficulty
        costs[department] = 1.0 if economy_difficulty(state) == "off" else cost_mult(state, store_id, department)
    return max(0, int(round(base * costs[department])))


_LIST_PRICES: dict[str, int] | None = None


def _list_price(product) -> int:
    """The shelf price the item was given. A lower price is a sale."""
    global _LIST_PRICES
    if _LIST_PRICES is None:
        from open_late.content import LABEL_PRODUCTS, PRODUCTS

        _LIST_PRICES = {item.id: int(item.price) for item in list(PRODUCTS) + list(LABEL_PRODUCTS)}
    authored = _LIST_PRICES.get(product.id)
    if authored is not None:
        return authored
    product_id = str(product.id)
    if product_id.startswith("cat-") and product_id[4:].isdigit():
        from open_late.catalog import catalog_record

        return int(catalog_record(int(product_id[4:]) - 1)["price"])
    return int(product.price)


def _sale_departments(state: GameState, stock) -> set[str]:
    """Departments with something in stock priced under its list price."""
    found: set[str] = set()
    for product in state.products.values():
        line = stock.get(product.id) if stock is not None else None
        if line is None or int(getattr(line, "on_hand", 0) or 0) <= 0:
            continue
        if int(product.price) < _list_price(product):
            found.add(product.department or product.category)
    return found


def close_day(state: GameState) -> str:
    _sell_cache(state)  # start a fresh day memo before traffic
    if state.mode == "corporate":
        from open_late.corporate import close_corporate_day

        return close_corporate_day(state)
    if state.failed:
        return "The shop is already closed for good."
    if state.phase not in ("morning", "desk"):
        return "The day is already closed."
    from open_late.pricing import offer_landed_choice

    offer_landed_choice(state)
    if blocking(state):
        return "Answer the urgent notes before you close."
    from open_late.shopperlife.day import run_day

    run_day(state)
    _ensure_books(state)
    rng = Rng(state)
    report = DayReport(day=state.day, weekday=weekday_name(state.day), purchases=state.spent_today)
    _stamp_spend(state, report)
    report.cash_open = state.cash
    report.credit_open = state.credit_used
    _receive_orders(state, report, rng)
    _age_stock(state)
    _spoil_stock(state.stock, state.products, report)
    from open_late.economy import apply_daily_spoil
    from open_late.hq import HOME_STORE_ID

    apply_daily_spoil(state, state.stock, state.products, HOME_STORE_ID, report)
    _shrink(state, report, rng)
    worked = _attendance(state, report, rng)
    _apply_event_host(state, report, worked)
    staff_mult = _staff_multiplier(state, worked)
    visits, online_target = _traffic(state, rng)
    from open_late.shoppers import population_draw

    from open_late.hq import HOME_STORE_ID
    from open_late.shoppers import scale_draw

    from open_late.shoppers import census_city

    shop_city = "Evansville"
    if state.sites:
        shop_city = str(getattr(state.sites[0], "label", "") or shop_city)
    extra, note = population_draw(
        census_city(shop_city),
        state.campaign,
        _sale_departments(state, state.stock),
        state.day,
    )
    extra = scale_draw(state, HOME_STORE_ID, extra)
    if extra:
        visits += extra
        report.trade_visits += extra
        report.notes.append(note)
    _run_traffic(state, report, rng, visits, online_target, staff_mult, worked)
    _note_expiry(state, report, [state.stock])
    from open_late.hq import finish_close, record_home_trading_day
    record_home_trading_day(state, report)
    _run_regulars(state, report, rng, worked)
    _resolve_event(state, report, rng, worked)
    _update_staff(state, report, rng, worked)
    report.labor_hours, report.labor_overtime = close_labor(state, report)
    _update_reputation(state, report)
    if is_sunday(state.day):
        _sunday_bills(state, report)
        _sunday_world(state, report)
        from open_late.economy import economy_tick

        economy_tick(state)
    from open_late.economy import economy_daily_news, economy_end_day

    economy_daily_news(state)
    economy_end_day(state)
    _settle_payables(state, report)
    _close_books(state, report)
    _top_sellers(state, report)
    _milestones(state, report)
    _check_failure(state)
    from open_late.dc import units_on_road

    report.on_road = units_on_road(state)
    state.last_report = report
    state.history.append(report)
    if len(state.history) > 60:
        state.history = state.history[-60:]
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


def continue_morning(state: GameState) -> str:
    if state.failed or state.phase not in ("evening",):
        return ""
    state.day += 1
    state.phase = "morning"
    state.spent_today = 0
    state.spent_merchandise = 0
    state.spent_freight = 0
    state.spent_variance = 0
    state.spent_advertising = 0
    state.spent_severance = 0
    state.spent_draws = 0
    state.spent_debt = 0
    state.spent_fixtures = 0
    state.spent_period = 0
    state.spent_planogram = 0
    state.actions_today = []
    state.flags.ad_rejected = False
    if (state.day - 1) % 7 == 0:
        _drift_trend(state, Rng(state))
    return ""


def _stamp_spend(state: GameState, report: DayReport) -> None:
    """Copy the day's classified spends onto the report before the morning clears them."""
    report.merchandise_paid = state.spent_merchandise
    report.freight_paid = state.spent_freight
    report.variance_paid = state.spent_variance
    report.advertising_paid = state.spent_advertising
    report.severance_paid = state.spent_severance
    report.draws_paid = state.spent_draws
    report.debt_paid = state.spent_debt
    report.fixtures_paid = state.spent_fixtures
    report.period_paid = state.spent_period
    report.planogram_labor = state.spent_planogram


def _spend_note(report: DayReport) -> str:
    """What left the drawer, or hit a payable, before the bell. Each line says where it sits."""
    pieces = [
        (report.merchandise_paid, f"merchandise {money(report.merchandise_paid)} is on order at standard cost"),
        (report.freight_paid, f"freight {money(report.freight_paid)} is an operating cost"),
        (report.variance_paid, f"cost variance {money(report.variance_paid)} is an operating cost"),
        (report.advertising_paid, f"advertising {money(report.advertising_paid)} is an operating cost"),
        (report.severance_paid, f"severance {money(report.severance_paid)} is an operating cost"),
        (report.period_paid, f"other period cost {money(report.period_paid)} is an operating cost"),
        (report.planogram_labor, f"planogram labor {money(report.planogram_labor)} is an operating cost"),
        (report.fixtures_paid, f"fixtures {money(report.fixtures_paid)} are on the balance sheet"),
        (report.draws_paid, f"owner draw {money(report.draws_paid)} came out of equity"),
        (report.debt_paid, f"credit principal {money(report.debt_paid)} paid down the line"),
    ]
    shown = [text for amount, text in pieces if amount]
    if not shown and not report.purchases:
        return ""
    text = "Before the bell: " + "; ".join(shown) + "." if shown else ""
    if report.purchases:
        text += f" Cash already out of the opening drawer: {money(report.purchases)}."
    return text.strip()


def _drawer_tape(report: DayReport) -> str:
    """Cash bridge for the close. Identified lines are the ones the day actually posted."""
    identified = (
        report.revenue
        + report.tax_collected
        + report.credit_drawn
        - report.refunds
        - report.tax_refunded
        - report.card_fees
        - report.shipping
        - report.rent_paid
        - report.payroll_paid
        - report.payroll_tax_paid
        - report.insurance_paid
        - report.utilities_paid
        - report.interest_paid
        - report.tax_remitted
        - report.income_tax_paid
        - report.payables_paid
        - report.license_paid
        - report.loan_principal_paid
    )
    delta = report.cash_end - report.cash_open
    plug = delta - identified
    pieces = [
        ("sales", report.revenue),
        ("sales tax held", report.tax_collected),
        ("credit drawn", report.credit_drawn),
        ("refunds", -report.refunds),
        ("sales tax refunded", -report.tax_refunded),
        ("card fees", -report.card_fees),
        ("shipping", -report.shipping),
        ("rent", -report.rent_paid),
        ("wages", -report.payroll_paid),
        ("employer tax", -report.payroll_tax_paid),
        ("insurance", -report.insurance_paid),
        ("utilities", -report.utilities_paid),
        ("interest", -report.interest_paid),
        ("sales tax sent", -report.tax_remitted),
        ("income tax", -report.income_tax_paid),
        ("supplier bills", -report.payables_paid),
        ("register licenses", -report.license_paid),
        ("loan principal", -report.loan_principal_paid),
    ]
    shown = ", ".join(f"{name} {money(amount)}" for name, amount in pieces if amount)
    tie = "The drawer ties to the penny." if plug == 0 else f"Untied drawer movement {money(plug)}."
    text = (
        f"Drawer at the bell {money(report.cash_open)}. "
        f"Drawer at the close {money(report.cash_end)}. "
        f"Movement {money(delta)}. "
        f"Identified {money(identified)}"
        + (f": {shown}." if shown else ".")
        + f" {tie}"
    )
    if report.trade_visits:
        text += (
            f" {report.trade_visits:,} of {report.visits:,} visits were drawn from the trade area "
            "by an ad or a price cut."
        )
    spend = _spend_note(report)
    if spend:
        text += " " + spend
    if report.depreciation:
        text += (
            f" Depreciation {money(report.depreciation)} is on the books and did not leave the drawer."
        )
    return text


def narrate(state: GameState, report: DayReport) -> str:
    parts: list[str] = []
    parts.append(
        f"{report.weekday} brought in {money(report.revenue)}. "
        f"{report.visits:,} people came through and bought {report.units:,} units"
        f"{f', {report.units / report.visits:.2f} units per visit' if report.visits else ''}. "
        f"{report.online_orders} online orders shipped. "
        f"Average selling price {money(report.revenue // report.units) if report.units else money(0)}. "
        f"Gross margin on net sales, after shrink, {format_margin(report.revenue, report.refunds, report.cogs)}."
    )
    parts.append(_drawer_tape(report))
    if report.top_sellers:
        parts.append("Top of the sheet: " + ", ".join(report.top_sellers[:3]) + ".")
    if report.refunds:
        parts.append(
            f"Refunds {money(report.refunds)} on {report.returns} returns. Those goods did not go back on the shelf."
        )
    if report.shipping:
        parts.append(f"Shipping on the online orders was {money(report.shipping)}.")
    if report.card_fees:
        parts.append(f"Card fees {money(report.card_fees)}.")
    if report.damage_units:
        parts.append(
            f"Damaged on arrival: {report.damage_units} unit, {money(report.damage_cost)} at cost. It did not go on the shelf."
        )
    if getattr(report, "on_road", 0):
        parts.append(f"{int(report.on_road):,} units are still on a truck.")
    if report.missed_online:
        parts.append(f"{report.missed_online} online orders sat because nobody was packing.")
    if report.event_blurb:
        parts.append(report.event_blurb)
    if report.staff_lines:
        parts.append(" ".join(report.staff_lines[:3]))
    if report.flags:
        parts.append(" ".join(report.flags[:3]))
    if report.notes:
        trade = [note for note in report.notes if "trade area" in note]
        other = [note for note in report.notes if "trade area" not in note]
        if trade:
            parts.append(" ".join(trade))
        if other:
            parts.append(" ".join(other))
    if is_sunday(report.day):
        parts.append(
            f"Sunday out: rent {money(report.rent_paid)}, wages {money(report.payroll_paid)}, "
            f"employer tax {money(report.payroll_tax_paid)}, insurance {money(report.insurance_paid)}, "
            f"utilities {money(report.utilities_paid)}, interest {money(report.interest_paid)}."
        )
    if report.income_tax_paid:
        parts.append(f"Quarter income tax {money(report.income_tax_paid)}.")
        if report.shortfall:
            parts.append(f"Short {money(report.shortfall)}.")
    lost = report.lost_stockout + report.lost_price + report.lost_staff + report.lost_walk
    if lost:
        parts.append(
            f"Turned away: {report.lost_stockout} for an empty shelf, "
            f"{report.lost_price} because the price was too high, "
            f"{report.lost_staff} because the crew was short, "
            f"{report.lost_walk} who left without buying, "
            f"{report.lost_size} who did not find their size. "
            f"The floor could serve {report.capacity}."
        )
    if report.tax_collected:
        parts.append(f"Sales tax collected {money(report.tax_collected)}. It is not yours. Sunday sends it on.")
    if report.shrink_units:
        parts.append(f"Shrink: {report.shrink_units} unit, {money(report.shrink_cost)} at cost. It did not ring.")
    if report.gross_profit or report.revenue:
        parts.append(f"Gross profit on the day {money(report.gross_profit)}. Drawer at close {money(report.cash_end)}.")
    if report.milestone_notes:
        parts.extend(report.milestone_notes)
    if state.failed:
        parts.append(state.fail_reason)
    return "\n\n".join(parts)


def _receive_orders(state: GameState, report: DayReport, rng: Rng) -> None:
    from open_late.living import short_delivery

    pending: list[PurchaseOrder] = []
    for order in state.orders:
        if order.arrives_on > state.day:
            pending.append(order)
            continue
        supplier = SUPPLIERS[order.supplier_id]
        ordered = dict(order.lines)
        shorted = short_delivery(state, order)
        if shorted:
            missing_cost = 0
            for product_id, amount in ordered.items():
                kept = int(order.lines.get(product_id) or 0)
                missing = int(amount) - kept
                if missing > 0 and product_id in state.products:
                    missing_cost += int(state.products[product_id].cost) * missing
            if missing_cost:
                account = _account(state, order.supplier_id)
                if account is not None and account.terms in ("net14", "net30") and int(account.payable) >= missing_cost:
                    account.payable -= missing_cost
                    post(state, "payable", -missing_cost, f"{supplier.name} shorted the household truck.")
                else:
                    state.cash += missing_cost
                    post(state, "inventory", missing_cost, f"{supplier.name} shorted the household truck.")
            report.notes.append(
                f"The household truck from {supplier.name} arrived short. {shorted} units did not come."
            )
        for product_id, amount in ordered.items():
            line = state.stock[product_id]
            product = state.products[product_id]
            held = line.on_hand
            _add_stock(line, product, int(order.lines.get(product_id) or 0))
            line.on_order = max(0, line.on_order - int(amount))
            if line.on_hand:
                line.age_days = int(line.age_days * held / line.on_hand)
        account = _account(state, order.supplier_id)
        if account is not None:
            account.relationship = clamp(account.relationship + 1, 0, 100)
        damaged = _damage_delivery(state, report, rng, order, supplier.lead_time_days)
        if damaged:
            report.notes.append(f"Delivery from {supplier.name} hit the shelf. {damaged}")
        else:
            report.notes.append(f"Delivery from {supplier.name} hit the shelf.")
    state.orders = pending


def _attendance(state: GameState, report: DayReport, rng: Rng) -> dict[str, str]:
    worked: dict[str, str] = {}
    for person in state.staff:
        if not person.employed:
            continue
        if rng.chance((100 - person.reliability) / 520):
            worked[person.id] = "off"
            report.noshow_ids.append(person.id)
            report.staff_lines.append(f"Staff note: {person.name} did not come in.")
        else:
            worked[person.id] = person.assignment
    return worked


def _apply_event_host(state: GameState, report: DayReport, worked: dict[str, str]) -> None:
    event = state.scheduled_event
    if event is None:
        return
    report.event_host_id = event.host_id
    if event.host_id in worked and event.host_id not in report.noshow_ids:
        worked[event.host_id] = "event"


def _staff_multiplier(state: GameState, worked: dict[str, str]) -> float:
    floor = [person for person in state.staff if worked.get(person.id) == "floor"]
    if not floor:
        return 0.4
    knowledge = sum(person.product_knowledge for person in floor) / len(floor) / 100
    mood = sum(person.mood for person in floor) / len(floor) / 100
    aptitude = sum(person.aptitude_floor for person in floor) / len(floor) / 100
    coverage = min(1.16, 0.8 + 0.14 * len(floor))
    return coverage * (0.72 + 0.42 * knowledge) * (0.8 + 0.28 * mood) * (0.92 + 0.12 * aptitude)


def _traffic(state: GameState, rng: Rng) -> tuple[int, int]:
    dow = DOW_MULT[(state.day - 1) % 7]
    rep = 0.74 + state.reputation_respectable / 240 + state.reputation_nightlife / 300
    competitor = max(0.72, 1 - state.flags.competitor / 220)
    campaign = state.campaign.traffic_mult if state.campaign else 1.0
    neighbor = 1.0
    physical = [site for site in state.sites if site.is_physical]
    if physical:
        limit = max(site.neighbor_sensitivity for site in physical)
        if state.flags.neighbor_heat > limit + 18:
            neighbor = 0.86
    foot = sum(site.foot_traffic for site in physical)
    hours = max(4, state.close_hour - state.open_hour) / 8
    if state.campaign is not None and state.campaign.kind == "email":
        campaign *= 1 + min(0.4, state.list_size / 1800)
    from open_late.economy_e3 import campaign_lift_mult
    from open_late.hq import HOME_STORE_ID as _HOME

    fade = campaign_lift_mult(state, _HOME)
    campaign = 1.0 + (campaign - 1.0) * fade
    visits = int(round(foot * dow * rep * competitor * campaign * neighbor * hours * rng.uniform(0.9, 1.1)))
    online = 0
    if state.flags.online_open:
        base = 12 if state.mode == "online" else 6
        if any(site.is_warehouse for site in state.sites):
            base = int(base * 1.55)
        trust = 0.55 + state.flags.platform_trust / 180
        online = int(round(base * dow * rep * campaign * trust * rng.uniform(0.88, 1.12)))
    from open_late.economy import adjust_visits
    from open_late.hq import HOME_STORE_ID

    visits = adjust_visits(state, HOME_STORE_ID, visits) * SIZE_MULT
    online = adjust_visits(state, HOME_STORE_ID, online) * SIZE_MULT
    return max(0, visits), max(0, online)


def _category_weights(state: GameState, worked: dict[str, str]) -> dict[str, float]:
    respect = state.reputation_respectable
    night = state.reputation_nightlife
    weights = {
        "grocery": 1.40 + respect / 160,
        "produce": 1.15 + respect / 180,
        "meat_dairy": 1.10 + respect / 200,
        "frozen": 0.95,
        "household": 1.05 + respect / 200,
        "health_beauty": 0.88 + respect / 220,
        "pharmacy": 0.55 + respect / 180,
        "electronics": 0.70 + night / 140,
        "clothing": 0.90 + respect / 200,
        "toys": 0.80 + night / 180,
        "home_garden": 0.75,
        "sporting": 0.70 + night / 200,
        "seasonal": 0.62 + night / 180,
    }
    if state.flags.policy == "keep_light":
        weights["electronics"] *= 0.7
        weights["seasonal"] *= 0.85
        weights["grocery"] *= 1.08
        weights["household"] *= 1.08
        weights["pharmacy"] *= 1.05
    elif state.flags.policy == "lean_in":
        weights["electronics"] *= 1.35
        weights["seasonal"] *= 1.20
        weights["sporting"] *= 1.10
    if not _intense_outlet(state):
        weights["pharmacy"] *= 0.1
    elif any(site.is_physical and not site.allows_intense for site in state.sites):
        weights["pharmacy"] *= 0.72
    for person in state.staff:
        if worked.get(person.id) != "modeling":
            continue
        if "no_modeling" in person.boundaries or person.comfort_modeling < 35:
            continue
        weights["seasonal"] *= 1.16
        weights["clothing"] *= 1.08
    if any(worked.get(person.id) == "private" and "no_private" not in person.boundaries for person in state.staff):
        weights["pharmacy"] *= 1.12
        weights["health_beauty"] *= 1.08
    if state.campaign is not None:
        weights[state.campaign.category] = weights.get(state.campaign.category, 1) * 1.45
        if state.campaign.tone == "bold":
            weights["electronics"] *= 1.08
            weights["seasonal"] *= 1.12
        elif state.campaign.tone == "discreet":
            weights["grocery"] *= 1.1
            weights["household"] *= 1.08
    from open_late.economy import adjust_weight
    from open_late.hq import HOME_STORE_ID

    for category in list(weights):
        weights[category] = adjust_weight(state, HOME_STORE_ID, category, weights[category])
    from open_late.shoppers import aisle_tilt

    from open_late.shoppers import census_city

    shop_city = str(getattr(state.sites[0], "label", "") or "Evansville") if state.sites else "Evansville"
    tilt = aisle_tilt(census_city(shop_city))
    for category, factor in tilt.items():
        if category in weights:
            weights[category] *= factor
    return weights


def _intense_outlet(state: GameState) -> bool:
    if state.flags.online_open:
        return True
    return any(site.is_physical and site.allows_intense for site in state.sites)


def _run_traffic(
    state: GameState,
    report: DayReport,
    rng: Rng,
    visits: int,
    online_target: int,
    staff_mult: float,
    worked: dict[str, str],
) -> None:
    report.visits = visits
    floor = [person for person in state.staff if worked.get(person.id) == "floor"]
    # Each named person is a department crew that can ring ~70-80 tickets in 8 hours.
    capacity = sum(40 + person.product_knowledge // 2 for person in floor)
    if not floor:
        capacity = 20
    capacity = int(capacity * max(4, state.close_hour - state.open_hour) / 8) * CREW_MULT
    report.capacity = capacity
    if visits > capacity:
        report.lost_staff += visits - capacity
        visits = capacity
    weights = _category_weights(state, worked)
    # Stocked options and the walked multiplier are stable for the day except
    # when a SKU hits zero; keep both off the per-visit path but bit-identical.
    stocked: dict[str, list] = {}
    for product in state.products.values():
        if state.stock[product.id].on_hand > 0:
            stocked.setdefault(product.category, []).append(product)
    from open_late.hq import HOME_STORE_ID, apply_walked

    walked = apply_walked(state, HOME_STORE_ID, 1.0)
    named = min(visits, NAMED_BASKET_CAP)
    remaining = visits - named
    # Pick weights are stable for the day until a SKU sells out (age and tickets
    # do not change mid-traffic). Rebuilds would be bit-identical; skip the
    # O(SKU) scan on every visit.
    pick_weights: dict[str, dict[str, float]] = {}
    pick_totals: dict[str, float] = {}
    category_total = sum(max(0.0, value) for value in weights.values())
    for _ in range(named):
        for _ in range(BASKET_SIZE):
            _attempt_sale(
                state,
                report,
                rng,
                rng.weighted(weights, category_total),
                staff_mult,
                "foot",
                stocked,
                walked,
                pick_weights,
                pick_totals,
            )
    if remaining:
        _run_aggregate(
            state,
            report,
            remaining,
            weights,
            stocked,
            walked,
            staff_mult,
            store_id=HOME_STORE_ID,
            stock=state.stock,
            sell=lambda product, qty, sell_rng: _sell(state, report, sell_rng, product, qty, None),
        )
    if not state.flags.online_open:
        return
    packers = [person for person in state.staff if worked.get(person.id) == "fulfillment"]
    cap = 4 + 12 * len(packers) if packers else 3
    taken = min(online_target, cap)
    report.missed_online = max(0, online_target - taken)
    if packers:
        knowledge = sum(person.product_knowledge for person in packers) / len(packers) / 100
        online_mult = 0.82 + 0.3 * knowledge
    else:
        online_mult = 0.5
    if any(worked.get(person.id) == "floor" for person in state.staff):
        online_mult *= 1.06
    for _ in range(taken):
        if _attempt_sale(
            state,
            report,
            rng,
            rng.weighted(weights, category_total),
            online_mult,
            "online",
            stocked,
            walked,
            pick_weights,
            pick_totals,
        ):
            report.online_orders += 1



class _Crng:
    """Thin chance/random wrapper around a dedicated stdlib stream."""

    def __init__(self, stream: random.Random) -> None:
        self._stream = stream

    def random(self) -> float:
        return self._stream.random()

    def chance(self, probability: float) -> bool:
        if probability <= 0:
            return False
        if probability >= 1:
            return True
        return self.random() < probability


def _count_stockout(report: DayReport, category: str, count: int) -> None:
    count = max(0, int(count))
    if count <= 0:
        return
    report.lost_stockout += count
    key = category or "other"
    report.lost_stockout_by_category[key] = report.lost_stockout_by_category.get(key, 0) + count


def _dept_sell_expectation(options: list, staff_mult: float, walked: float) -> float:
    """Expected units per attempt for a department, matching the named-sale chance including the cheap double."""
    if not options:
        return 0.0
    from open_late.shoppers import trip_afford_share

    from open_late.pricing import department_flex

    total = 0.0
    for product in options:
        fit = _price_fit(product)
        afford = trip_afford_share(product.price)
        chance = CONVERSION * fit * department_flex(product) * afford * (0.75 + product.quality * 0.06) * staff_mult * walked
        chance = max(0.04, min(0.9, chance))
        extra = 0.35 if product.price <= 24 else 0.0
        total += chance * (1.0 + extra)
    return total / len(options)


def _run_aggregate(
    state: GameState,
    report: DayReport,
    remaining: int,
    weights: dict[str, float],
    stocked: dict[str, list],
    walked: float,
    staff_mult: float,
    *,
    store_id: str,
    stock: dict,
    sell,
    shelf=None,
) -> None:
    """Seeded per-department demand for the visits past the named-basket cap.

    The unit shock is common across difficulty tiers (same seed, day, and department
    salt); only SIGMA_MULT changes the noise amplitude, the same way walks work.
    """
    import math

    from open_late.economy import SIGMA_MULT, demand_rng, economy_difficulty

    if remaining <= 0 or not weights:
        return
    total_w = sum(max(0.0, value) for value in weights.values()) or 1.0
    attempts = remaining * BASKET_SIZE
    sigma = float(SIGMA_MULT.get(economy_difficulty(state), 1.0) or 0.0)
    for department, weight in weights.items():
        if weight <= 0:
            continue
        options = [item for item in (stocked.get(department) or []) if stock.get(item.id) and stock[item.id].on_hand > 0]
        if not options:
            _count_stockout(report, department, max(1, int(round(attempts * (weight / total_w) / BASKET_SIZE))))
            continue
        expected = attempts * (weight / total_w) * _dept_sell_expectation(options, staff_mult, walked)
        if shelf is not None:  # Lite shelves: department volume lift (off = None, p2 path)
            expected *= shelf.lift.get(department, 1.0)
        stream = demand_rng(state, state.day, store_id, department)
        shock = stream.gauss(0.0, 1.0)
        rng = _Crng(stream)
        qty = max(0, int(round(expected + sigma * shock * math.sqrt(max(1.0, expected)))))
        if qty <= 0:
            continue
        pick = {}
        for product in options:
            trend = {"rising": 1.25, "steady": 1.0, "fading": 0.62}[product.trend]
            age = stock[product.id].age_days
            stale = 0.82 if age >= 28 else 0.92 if age >= 18 else 1
            from open_late.shoppers import trip_afford_share

            pick[product.id] = (
                trend * stale * (0.55 + product.quality * 0.16) * _price_fit(product)
                * trip_afford_share(product.price) * (1.18 if product.exclusive else 1)
            )
            if shelf is not None:
                pick[product.id] *= shelf.sku.get(product.id, 1.0)
        mass = sum(pick.values()) or 1.0
        leftover = qty
        planned: list[tuple] = []
        for product in options:
            share = max(0, int(round(qty * pick[product.id] / mass)))
            take = min(share, stock[product.id].on_hand)
            if take:
                planned.append((product, take))
                leftover -= take
        if leftover > 0:
            for product in options:
                room = stock[product.id].on_hand - sum(take for item, take in planned if item.id == product.id)
                if room <= 0:
                    continue
                take = min(room, leftover)
                planned.append((product, take))
                leftover -= take
                if leftover <= 0:
                    break
        if leftover > 0:
            _count_stockout(report, department, max(1, int(round(leftover / BASKET_SIZE))))
        for product, take in planned:
            sold = sell(product, take, rng)
            if sold and stock[product.id].on_hand <= 0:
                bucket = stocked.get(department) or []
                stocked[department] = [item for item in bucket if item.id != product.id]


def _attempt_sale(
    state: GameState,
    report: DayReport,
    rng: Rng,
    category: str,
    staff_mult: float,
    channel: str,
    stocked: dict[str, list] | None = None,
    walked: float | None = None,
    pick_weights: dict[str, dict[str, float]] | None = None,
    pick_totals: dict[str, float] | None = None,
) -> bool:
    if stocked is not None:
        options = stocked.get(category) or []
    else:
        options = [
            product
            for product in state.products.values()
            if product.category == category and state.stock[product.id].on_hand > 0
        ]
    if not options:
        _count_stockout(report, category, 1)
        return False
    weights = pick_weights.get(category) if pick_weights is not None else None
    from open_late.shoppers import trip_afford_share

    if not weights:
        weights = {}
        for product in options:
            trend = {"rising": 1.25, "steady": 1.0, "fading": 0.62}[product.trend]
            age = state.stock[product.id].age_days
            stale = 0.82 if age >= 28 else 0.92 if age >= 18 else 1
            weights[product.id] = (
                trend * stale * (0.55 + product.quality * 0.16) * _price_fit(product)
                * trip_afford_share(product.price) * (1.18 if product.exclusive else 1)
            )
        if pick_weights is not None:
            pick_weights[category] = weights
            if pick_totals is not None:
                pick_totals[category] = sum(max(0.0, value) for value in weights.values())
    product = state.products[rng.weighted(weights, None if pick_totals is None else pick_totals.get(category))]
    line = state.stock[product.id]
    size = _wanted_size(product, line, rng)
    if size == "":
        report.lost_size += 1
        return False
    from open_late.pricing import department_flex

    fit = _price_fit(product)
    flex = department_flex(product)
    afford = trip_afford_share(product.price)
    chance = CONVERSION * fit * flex * afford * (0.75 + product.quality * 0.06) * staff_mult
    if product.trend == "rising":
        chance *= 1.08
    elif product.trend == "fading":
        chance *= 0.8
    if product.exclusive:
        chance *= 1.1
    if state.flags.competitor >= 20 and product.category == state.rival.focus:
        chance *= max(0.72, state.rival.price_index / 130)
    chance = max(0.04, min(0.9, chance))
    if walked is None:
        from open_late.hq import HOME_STORE_ID, apply_walked

        walked = apply_walked(state, HOME_STORE_ID, 1.0)
    chance = chance * walked
    if not rng.chance(chance):
        if fit < 0.7 or afford < 0.999 or flex < 0.98:
            report.lost_price += 1
            report.lost_price_by_product[product.id] = report.lost_price_by_product.get(product.id, 0) + 1
        elif staff_mult < 0.55:
            report.lost_staff += 1
        else:
            report.lost_walk += 1
        return False
    qty = 1
    available = line.sizes.get(size, 0) if size else line.on_hand
    if product.price <= 24 and available > 1 and rng.chance(0.35):
        qty = 2
    sold = _sell(state, report, rng, product, qty, size or None)
    if sold and stocked is not None and state.stock[product.id].on_hand <= 0:
        bucket = stocked.get(category) or []
        stocked[category] = [item for item in bucket if item.id != product.id]
        if pick_weights is not None and category in pick_weights:
            pick_weights[category].pop(product.id, None)
            if pick_totals is not None:
                remaining = pick_weights[category]
                pick_totals[category] = sum(max(0.0, value) for value in remaining.values())
    if sold and channel == "foot":
        _attribute_sale(state, product.price * sold)
    if sold and channel == "online":
        parcel = shipping_for(product) * sold
        report.shipping += parcel
        _pay(state, parcel)
    return sold > 0


_PRICE_FIT_CACHE: dict[tuple[int, int], float] = {}


def _price_fit(product: Product) -> float:
    key = (int(product.cost), int(product.price))
    cached = _PRICE_FIT_CACHE.get(key)
    if cached is not None:
        return cached
    fair = max(1, int(round(product.cost * 1.70)))
    ratio = product.price / fair
    if ratio < 0.8:
        fit = 1.1
    elif ratio < 1.15:
        fit = 1.02
    elif ratio < 1.55:
        fit = 1.02 - (ratio - 1.15) * 1.15
    else:
        fit = 0.28
    fit = max(0.15, min(1.15, fit))
    _PRICE_FIT_CACHE[key] = fit
    return fit


def _add_stock(line: StockLine, product: Product, qty: int) -> None:
    if qty <= 0:
        return
    if line.on_hand <= 0:
        line.sizes = {}
        line.on_hand = 0
        line.age_days = 0
    else:
        line.age_days = (line.age_days * line.on_hand) // (line.on_hand + qty)
    line.on_hand += qty
    if is_sized(product):
        for name, count in allocate_sizes(qty).items():
            line.sizes[name] = line.sizes.get(name, 0) + count


def _take_stock(line: StockLine, product: Product, qty: int, size: str | None = None) -> int:
    if qty <= 0 or line.on_hand <= 0:
        return 0
    if is_sized(product):
        if sum(line.sizes.values()) != line.on_hand:
            line.sizes = allocate_sizes(line.on_hand)
        if size:
            qty = min(qty, line.sizes.get(size, 0))
        else:
            qty = min(qty, line.on_hand)
        if qty <= 0:
            return 0
        left = qty
        if size:
            line.sizes[size] = line.sizes.get(size, 0) - qty
            if line.sizes[size] <= 0:
                line.sizes.pop(size, None)
        else:
            while left and line.sizes:
                name = max(line.sizes, key=line.sizes.get)
                step = min(left, line.sizes[name])
                line.sizes[name] -= step
                left -= step
                if line.sizes[name] <= 0:
                    del line.sizes[name]
    else:
        qty = min(qty, line.on_hand)
    line.on_hand -= qty
    if line.on_hand <= 0:
        line.on_hand = 0
        line.age_days = 0
        line.sizes = {}
    return qty


def _wanted_size(product: Product, line: StockLine, rng: Rng) -> str | None:
    if not is_sized(product):
        return None
    if sum(line.sizes.values()) != line.on_hand:
        line.sizes = allocate_sizes(line.on_hand) if line.on_hand else {}
    size = rng.weighted({name: float(weight) for name, weight in SIZE_WEIGHTS.items()})
    if line.sizes.get(size, 0) <= 0:
        return ""
    return size


def _damage_delivery(state: GameState, report: DayReport, rng: Rng, order: PurchaseOrder, lead_days: int) -> str:
    if not rng.chance(damage_chance(lead_days)):
        return ""
    victims = [
        product_id
        for product_id, qty in order.lines.items()
        if qty > 0 and state.stock[product_id].on_hand > 0
    ]
    if not victims:
        return ""
    product_id = rng.choice(victims)
    product = state.products[product_id]
    line = state.stock[product_id]
    size = None
    if is_sized(product) and line.sizes:
        size = max(line.sizes, key=line.sizes.get)
    if not _take_stock(line, product, 1, size):
        return ""
    report.damage_units += 1
    report.damage_cost += product.cost
    report.cogs += product.cost
    account = _account(state, order.supplier_id)
    if account is not None:
        account.relationship = clamp(account.relationship - 2, 0, 100)
    return f"One {product.name} arrived damaged and did not go on the shelf."


def return_chance(product: Product) -> float:
    by_quality = {5: 0.03, 4: 0.055, 3: 0.09, 2: 0.15, 1: 0.2}
    chance = by_quality.get(product.quality, 0.12)
    department = getattr(product, "department", "") or product.category
    if department in ("clothing", "seasonal"):
        chance += 0.04
    if product.intensity >= 3:
        chance += 0.03
    return min(0.24, chance)


def _sell(
    state: GameState,
    report: DayReport,
    rng: Rng,
    product: Product,
    qty: int,
    size: str | None = None,
) -> int:
    from open_late.departments import selling_price

    line = state.stock[product.id]
    unit = selling_price(product, line)
    qty = _take_stock(line, product, qty, size)
    if qty <= 0:
        return 0
    revenue = unit * qty
    if unit < product.price:
        report.expiry_markdown += (product.price - unit) * qty
    from open_late.hq import HOME_STORE_ID as _TAX_STORE

    tax = _sale_tax(state, revenue, _TAX_STORE)
    state.cash += revenue + tax
    from open_late.hq import HOME_STORE_ID
    fee = _sale_fee(state, HOME_STORE_ID, revenue + tax)
    if fee:
        report.card_fees += fee
        _pay(state, fee)
    state.tax_held += tax
    report.tax_collected += tax
    state.list_size = min(8000, state.list_size + qty)
    report.revenue += revenue
    report.units += qty
    from open_late.hq import HOME_STORE_ID

    report.cogs += _sale_cogs(state, HOME_STORE_ID, product.department, product.cost * qty)
    report.by_category[product.category] = report.by_category.get(product.category, 0) + revenue
    report.units_by_product[product.id] = report.units_by_product.get(product.id, 0) + qty
    state.totals.revenue += revenue
    state.totals.units += qty
    chance = return_chance(product)
    returned = 0
    for _ in range(qty):
        if rng.chance(chance):
            returned += 1
    if returned:
        refund = unit * returned
        report.returns += returned
        report.refunds += refund
        state.totals.returns += returned
        state.totals.refunds += refund
        if unit < product.price:
            report.expiry_markdown = max(0, report.expiry_markdown - (product.price - unit) * returned)
        from open_late.hq import HOME_STORE_ID as _TAX_STORE

        tax_back = _sale_tax(state, refund, _TAX_STORE)
        state.tax_held = max(0, state.tax_held - tax_back)
        report.tax_refunded += tax_back
        _pay(state, refund + tax_back)
        account = _account(state, product.supplier_id)
        if account is not None:
            account.relationship = clamp(account.relationship - 4, 0, 100)
    return qty


def _pay(state: GameState, amount: int) -> int:
    if amount <= 0:
        return 0
    if state.cash >= amount:
        state.cash -= amount
        return 0
    need = amount - max(state.cash, 0)
    from open_late.economy_e3 import credit_available_mult

    room = max(0, int(state.credit_limit * credit_available_mult(state)) - state.credit_used)
    draw = min(room, need)
    state.credit_used += draw
    state.cash += draw
    state.cash -= amount
    if state.cash < 0:
        unpaid = -state.cash
        state.cash = 0
        return unpaid
    return 0


def _run_regulars(state: GameState, report: DayReport, rng: Rng, worked: dict[str, str]) -> None:
    online_only = not any(site.is_physical for site in state.sites)
    for regular in state.regulars:
        if not regular.active or not regular.introduced:
            continue
        chance = 0.06 + regular.loyalty / 460
        if regular.last_visit and state.day - regular.last_visit > 6:
            chance += 0.05
        if not rng.chance(chance):
            continue
        options = [
            product
            for product in state.products.values()
            if product.category in regular.preferences and state.stock[product.id].on_hand > 0
        ]
        if not options:
            regular.loyalty = clamp(regular.loyalty - 6, 0, 100)
            report.stockout_ids.append(regular.id)
            label = regular.preferences[0].replace("_", " ")
            report.flags.append(f"Customer flag: {regular.name} came for {label} and the shelf was empty.")
            if regular.loyalty < 12:
                regular.active = False
                report.flags.append(f"Customer flag: {regular.name} is not coming back.")
            continue
        weights = {product.id: product.quality + (1.4 if product.trend == "rising" else 0.6) for product in options}
        product = state.products[rng.weighted(weights)]
        if not rng.chance(min(0.9, 0.5 + _price_fit(product) * 0.35)):
            continue
        size = _wanted_size(product, state.stock[product.id], rng)
        if size == "":
            report.lost_size += 1
            regular.loyalty = clamp(regular.loyalty - 2, 0, 100)
            report.flags.append(f"Customer flag: {regular.name} did not find their size in {product.name}.")
            continue
        available = state.stock[product.id].sizes.get(size, 0) if size else state.stock[product.id].on_hand
        qty = 2 if product.price < 30 and available > 1 and rng.chance(0.3) else 1
        sold = _sell(state, report, rng, product, qty, size or None)
        if not sold:
            continue
        if online_only:
            parcel = shipping_for(product) * sold
            report.shipping += parcel
            report.online_orders += 1
            _pay(state, parcel)
        regular.spend += product.price * sold
        regular.visits += 1
        regular.last_visit = state.day
        regular.loyalty = clamp(regular.loyalty + 2, 0, 100)
        report.buyer_ids.append(regular.id)
        if regular.discretion >= 75:
            discreet = any(
                person.personality == "discreet" and worked.get(person.id) in ("floor", "private")
                for person in state.staff
            )
            if discreet:
                regular.loyalty = clamp(regular.loyalty + 2, 0, 100)
            elif any(worked.get(person.id) == "floor" and person.personality == "playful" for person in state.staff):
                regular.loyalty = clamp(regular.loyalty - 2, 0, 100)


def _resolve_event(state: GameState, report: DayReport, rng: Rng, worked: dict[str, str]) -> None:
    event = state.scheduled_event
    if event is None:
        return
    state.totals.events += 1
    host = staff_by_id(state, event.host_id)
    showed = host is not None and worked.get(host.id) == "event"
    names = {"try_on": "After-hours try-on", "demo": "Product demo", "couples": "Couples night"}
    title = names[event.kind]
    if not showed or host is None:
        report.incident = True
        state.flags.incidents += 1
        report.event_blurb = f"{title}: the host did not make it. You closed early."
        state.scheduled_event = None
        return
    boundary = "no_events" in host.boundaries or (
        event.kind == "demo" and event.category == "pharmacy" and "no_intense_demo" in host.boundaries
    )
    if boundary:
        incident = True
    elif not event.strict_rules:
        incident = rng.chance(0.36)
    else:
        incident = rng.chance(0.08)
    options = [
        product
        for product in state.products.values()
        if product.category == event.category and state.stock[product.id].on_hand > 0
    ]
    left = rng.randint(4, 9)
    sold_revenue = 0
    guard = 0
    while left > 0 and guard < 24:
        guard += 1
        options = [product for product in options if state.stock[product.id].on_hand > 0]
        if not options:
            break
        product = options[rng.randint(0, len(options) - 1)]
        size = _wanted_size(product, state.stock[product.id], rng)
        if size == "":
            report.lost_size += 1
            continue
        before = report.revenue
        got = _sell(state, report, rng, product, 1, size or None)
        if not got:
            break
        sold_revenue += report.revenue - before
        left -= got
    premium = 40 if incident and boundary else (160 if event.strict_rules else 90)
    if not options and sold_revenue == 0:
        premium = 30
    state.cash += premium
    report.revenue += premium
    report.event_revenue = sold_revenue + premium
    if boundary:
        report.incident = True
        state.flags.incidents += 1
        state.flags.neighbor_heat = clamp(state.flags.neighbor_heat + 8, 0, 100)
        state.review_score = max(1.0, state.review_score - 0.12)
        report.event_blurb = (
            f"{title}: you booked {host.name}, who does not host that night. "
            "Sales happened. So did the note they will remember."
        )
    elif incident:
        report.incident = True
        state.flags.incidents += 1
        state.flags.neighbor_heat = clamp(state.flags.neighbor_heat + 6, 0, 100)
        report.event_blurb = (
            f"{title}: strong sales on the featured items, one couple asked about a return visit, "
            "one staff member flagged a guest who ignored the rules."
        )
    else:
        state.reputation_nightlife = clamp(state.reputation_nightlife + 3, 0, 100)
        if sold_revenue == 0:
            report.event_blurb = f"{title}: the room was fine and the featured shelf was thin."
        else:
            report.event_blurb = (
                f"{title}: strong sales on the featured items. One couple asked about a return visit. The rules held."
            )
    state.scheduled_event = None


def _update_staff(state: GameState, report: DayReport, rng: Rng, worked: dict[str, str]) -> None:
    for person in state.staff:
        if not person.employed:
            continue
        job = worked.get(person.id, "off")
        report.assigned[person.id] = job
        if person.id in report.noshow_ids:
            person.mood = clamp(person.mood - 4, 0, 100)
            person.loyalty = clamp(person.loyalty - 2, 0, 100)
            continue
        if job == "off":
            person.burnout = clamp(person.burnout - 12, 0, 100)
            person.mood = clamp(person.mood + 6, 0, 100)
        elif job == "floor":
            extra = 0
            span = state.close_hour - state.open_hour
            if span > 10:
                extra = 2
            elif span > 8:
                extra = 1
            person.burnout = clamp(person.burnout + 2 + extra, 0, 100)
            person.mood = clamp(person.mood + 1, 0, 100)
            if state.day > person.review_due:
                person.loyalty = clamp(person.loyalty - 1, 0, 100)
        elif job == "fulfillment":
            person.burnout = clamp(person.burnout + 1, 0, 100)
        elif job == "training":
            person.burnout = clamp(person.burnout + 1, 0, 100)
            person.product_knowledge = clamp(person.product_knowledge + 2, 0, 98)
            person.mood = clamp(person.mood + 2, 0, 100)
            report.staff_lines.append(
                f"Staff note: {person.name} spent the shift on the book. Knowledge is {person.product_knowledge}."
            )
        elif job == "modeling":
            if "no_modeling" in person.boundaries or person.comfort_modeling < 35:
                person.burnout = clamp(person.burnout + 26, 0, 100)
                person.mood = clamp(person.mood - 16, 0, 100)
                person.loyalty = clamp(person.loyalty - 12, 0, 100)
                report.staff_lines.append(
                    f"Staff note: {person.name} was put in front of the camera anyway. They had already drawn that line."
                )
            else:
                person.burnout = clamp(person.burnout + 5, 0, 100)
                person.mood = clamp(person.mood + 3, 0, 100)
                person.loyalty = clamp(person.loyalty + 1, 0, 100)
                person.following += rng.randint(2, 6)
                report.staff_lines.append(
                    f"Staff note: {person.name} posted during the shift and was fine with it. Following is {person.following}."
                )
        elif job == "private":
            if "no_private" in person.boundaries:
                person.burnout = clamp(person.burnout + 24, 0, 100)
                person.mood = clamp(person.mood - 14, 0, 100)
                person.loyalty = clamp(person.loyalty - 12, 0, 100)
                report.staff_lines.append(
                    f"Staff note: {person.name} took an appointment-desk shift they do not offer."
                )
            else:
                person.burnout = clamp(person.burnout + 7, 0, 100)
                person.mood = clamp(person.mood + 1, 0, 100)
                report.staff_lines.append(f"Staff note: {person.name} ran the appointment desk with the rules said out loud.")
        elif job == "event":
            if "no_events" in person.boundaries:
                person.burnout = clamp(person.burnout + 22, 0, 100)
                person.mood = clamp(person.mood - 12, 0, 100)
                person.loyalty = clamp(person.loyalty - 10, 0, 100)
            else:
                person.burnout = clamp(person.burnout + 9, 0, 100)
                person.mood = clamp(person.mood + 2, 0, 100)
                person.loyalty = clamp(person.loyalty + 1, 0, 100)
        if person.burnout >= 100 or (person.burnout >= 88 and person.loyalty < 35 and rng.chance(0.45)):
            person.employed = False
            person.assignment = "off"
            report.quit_ids.append(person.id)
            state.totals.quits += 1
            report.flags.append(f"Staff note: {person.name} quit. The limit was not a suggestion.")
        elif person.burnout >= 68:
            report.flags.append(f"Staff note: {person.name} is burning out ({person.burnout}).")
    floor_names = [
        person.name
        for person in state.staff
        if report.assigned.get(person.id) == "floor"
    ]
    if floor_names and not report.staff_lines:
        report.staff_lines.append("On the floor: " + ", ".join(floor_names) + ".")


def _update_reputation(state: GameState, report: DayReport) -> None:
    total = max(1, report.revenue)
    destination_share = (
        report.by_category.get("electronics", 0)
        + report.by_category.get("seasonal", 0)
        + report.by_category.get("sporting", 0)
    ) / total
    night_delta = int(destination_share * 6)
    respect_delta = 0
    if report.units >= 5 and report.returns == 0:
        respect_delta += 1
    respect_delta -= min(4, report.returns)
    if destination_share > 0.34:
        respect_delta -= 2
        night_delta += 1
    if state.flags.policy == "keep_light" and report.units:
        respect_delta += 1
    elif state.flags.policy == "lean_in" and report.units:
        night_delta += 1
    if state.campaign is not None:
        respect_delta += state.campaign.respect
        night_delta += state.campaign.night
        if state.campaign.tone == "bold":
            state.flags.neighbor_heat = clamp(state.flags.neighbor_heat + 4, 0, 100)
        elif state.campaign.tone == "discreet":
            state.flags.neighbor_heat = clamp(state.flags.neighbor_heat - 2, 0, 100)
    state.reputation_nightlife = clamp(state.reputation_nightlife + night_delta, 0, 100)
    state.reputation_respectable = clamp(state.reputation_respectable + respect_delta, 0, 100)
    state.flags.neighbor_heat = clamp(state.flags.neighbor_heat + int(destination_share * 8) - 1, 0, 100)
    if report.returns:
        weight = min(0.28, 0.06 * report.returns)
        state.review_score = state.review_score * (1 - weight) + 2.3 * weight
        state.review_count += report.returns
    elif report.units >= 5:
        state.review_score = state.review_score * 0.94 + 4.65 * 0.06
        state.review_count += 1
    state.review_score = min(5.0, max(1.0, state.review_score))


def _sunday_bills(state: GameState, report: DayReport) -> None:
    rent = sum(site.rent_weekly for site in state.sites)
    payroll, payroll_tax = payroll_parts(state)
    interest = interest_due(state)
    insurance = insurance_weekly(state)
    utilities = utilities_weekly(state)
    from open_late.economy_e3 import adjust_sunday_bills

    rent, payroll, payroll_tax, insurance, utilities, interest = adjust_sunday_bills(
        state, rent, payroll, payroll_tax, insurance, utilities, interest
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
    remit = state.tax_held
    if remit:
        missed_tax = _pay(state, remit)
        report.tax_remitted = remit - missed_tax
        state.tax_held = missed_tax
        state.tax_lifetime += report.tax_remitted
        state.quarter_tax += report.tax_remitted
        unpaid += missed_tax
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
        for person in state.staff:
            if person.employed:
                person.mood = clamp(person.mood - 8, 0, 100)
                person.loyalty = clamp(person.loyalty - 6, 0, 100)
    else:
        state.flags.shortfalls = 0
    from open_late.hq import close_sunday_shop
    close_sunday_shop(state, report)


def _sunday_world(state: GameState, report: DayReport) -> None:
    week = [item for item in state.history if item.day > state.day - 7]
    week_revenue = sum(item.revenue for item in week) + report.revenue
    from open_late.economy import economy_difficulty

    # Off keeps the historical $6,800 first-Sunday trigger so traffic stays bit-identical.
    # On a live difficulty, wait for a month of supercenter-volume weeks, then seed
    # Northline heat so the E3 sync does not blend the entry back below the notice line.
    if economy_difficulty(state) == "off":
        entered = week_revenue >= 6800
    else:
        entered = week_revenue >= RIVAL_ENTRY_WEEK_SALES and state.day >= RIVAL_ENTRY_MIN_DAY
    if entered:
        if state.flags.competitor < 18:
            state.flags.competitor = 34
            state.flags.competitor_announced = False
            if economy_difficulty(state) != "off":
                from open_late.economy import _key, store_ids_for

                for store_id in store_ids_for(state) or ["evansville"]:
                    state.economy.values[_key(81, store_id)] = 34
    elif state.flags.competitor and state.flags.campaign_this_week:
        state.flags.competitor = max(0, state.flags.competitor - 8)
    if state.flags.competitor >= 20:
        state.rival.price_index = max(86, state.rival.price_index - 2)
        state.rival.reputation = min(78, state.rival.reputation + 2)
        if state.rival.blocks_away > 3:
            state.rival.blocks_away -= 1
        report.notes.append(
            f"{state.rival.name} is {state.rival.blocks_away} blocks off, pricing at {state.rival.price_index} "
            f"against your sheet. Their weight is on {state.rival.focus.replace('_', ' ')}."
        )
    state.flags.campaign_this_week = False
    state.flags.neighbor_heat = clamp(state.flags.neighbor_heat - 2, 0, 100)
    report.notes.append(f"Week's sales on the tape: {money(week_revenue)}.")


def _top_sellers(state: GameState, report: DayReport) -> None:
    ranked = sorted(report.units_by_product.items(), key=lambda item: item[1], reverse=True)
    report.top_sellers = [
        f"{state.products[product_id].name} × {qty}" for product_id, qty in ranked[:3] if qty and product_id in state.products
    ]


def _grant(state: GameState, report: DayReport, key: str, note: str) -> None:
    if key in state.milestones:
        return
    state.milestones.append(key)
    report.milestone_notes.append(note)


def _milestones(state: GameState, report: DayReport) -> None:
    if (
        state.day >= 28
        and state.cash >= STABLE_MONTH_CASH
        and state.review_score >= 3.9
        and state.flags.shortfalls == 0
        and not state.failed
    ):
        _grant(state, report, "stable_month", "Milestone: a month on the books, bills paid, reviews holding.")
    physical = [site for site in state.sites if site.is_physical]
    if len(physical) >= 2 or (state.mode == "online" and physical):
        _grant(state, report, "second_location", "Milestone: another door is open.")
    if state.mode == "shop" and state.flags.online_open:
        _grant(state, report, "online_counter", "Milestone: the online counter is live.")
    if state.flags.private_label:
        _grant(state, report, "private_label", "Milestone: the house label is on the books.")


def _check_failure(state: GameState) -> None:
    if state.flags.shortfalls >= 2:
        state.failed = True
        state.fail_reason = "Two Sundays in a row, the bills did not clear. The lease is done."
        return
    if not any(person.employed for person in state.staff):
        state.failed = True
        state.fail_reason = "No one is left to open. A shop with an empty sheet does not open tomorrow."


def _tick_campaign(state: GameState) -> None:
    if state.campaign is None:
        return
    state.campaign.days_left -= 1
    if state.campaign.days_left <= 0:
        state.campaign = None


def _drift_trend(state: GameState, rng: Rng) -> None:
    if not state.products:
        return
    product = rng.choice(list(state.products.values()))
    if product.exclusive:
        return
    if product.trend == "steady":
        product.trend = "rising" if rng.chance(0.5) else "fading"
    elif rng.chance(0.45):
        product.trend = "steady"


def _attribute_sale(state: GameState, revenue: int) -> None:
    floor = [person for person in state.staff if person.employed and person.assignment == "floor"]
    if not floor or revenue <= 0:
        return
    seller = max(floor, key=lambda person: (person.aptitude_floor, person.product_knowledge))
    seller.sales_attributed += revenue


def _ensure_accounts(state: GameState) -> None:
    have = {account.supplier_id for account in state.supplier_accounts}
    for supplier in SUPPLIERS.values():
        if supplier.id in have:
            continue
        state.supplier_accounts.append(SupplierAccount(supplier_id=supplier.id))


def _account(state: GameState, supplier_id: str) -> SupplierAccount | None:
    _ensure_accounts(state)
    return next((account for account in state.supplier_accounts if account.supplier_id == supplier_id), None)


def _seed_targets(state: GameState, due_day: int) -> None:
    if any(not target.closed and target.due_day == due_day for target in state.targets):
        return
    state.targets = [target for target in state.targets if target.closed or target.due_day != due_day]
    state.targets.extend(
        [
            Target(
                id=f"cash-{due_day}",
                label="Keep the drawer at the opening reserve",
                metric="cash",
                goal=8000,
                due_day=due_day,
            ),
            Target(
                id=f"review-{due_day}",
                label="Hold reviews at 4.0",
                metric="review",
                goal=40,
                due_day=due_day,
            ),
            Target(
                id=f"quits-{due_day}",
                label="No one walks this quarter",
                metric="quits",
                goal=state.totals.quits,
                due_day=due_day,
            ),
        ]
    )


def _ensure_books(state: GameState) -> None:
    _ensure_accounts(state)
    for person in state.staff:
        if person.wage_ask <= 0:
            person.wage_ask = person.wage
        if person.review_due <= 0:
            person.review_due = state.day + 28
    if not state.targets:
        due = ((max(state.day, 1) - 1) // 28 + 1) * 28
        _seed_targets(state, due)


def _age_stock(state: GameState) -> None:
    for line in state.stock.values():
        if line.on_hand > 0:
            line.age_days += 1


def _spoil_stock(stock: dict[str, StockLine], products: dict[str, Product], report: DayReport) -> int:
    """Write off perishable lots whose average age has reached shelf life."""
    units = 0
    cost = 0
    for product_id, line in stock.items():
        product = products.get(product_id)
        if product is None or int(getattr(product, "shelf_life_days", 0) or 0) <= 0:
            continue
        if line.on_hand <= 0 or line.age_days < product.shelf_life_days:
            continue
        qty = line.on_hand
        taken = _take_stock(line, product, qty)
        if taken <= 0:
            continue
        units += taken
        cost += product.cost * taken
    if units:
        report.spoilage_units += units
        report.spoilage_cost += cost
        report.shrink_units += units
        report.shrink_cost += cost
        report.cogs += cost
        report.notes.append(f"Spoilage wrote off {units} units ({money(cost)}) at expiry.")
    return cost


def _note_expiry(state: GameState, report: DayReport, stocks: list[dict[str, StockLine]]) -> None:
    from open_late.departments import in_markdown_window

    if report.expiry_markdown:
        report.notes.append(
            f"Markdowns on goods near expiry came to {money(report.expiry_markdown)}."
        )
    pending = 0
    for stock in stocks:
        for product_id, line in stock.items():
            product = state.products.get(product_id)
            if product is None or line.on_hand <= 0:
                continue
            if in_markdown_window(product, line):
                pending += line.on_hand
    if pending:
        report.notes.append(
            f"{pending} perishable units are marked 30% off, last day or two on the shelf."
        )


def _shrink(state: GameState, report: DayReport, rng: Rng) -> None:
    candidates = [product_id for product_id, line in state.stock.items() if line.on_hand > 0]
    from open_late.hq import HOME_STORE_ID, shrink_mult
    if not candidates or not rng.chance(0.08 * shrink_mult(state, HOME_STORE_ID)):
        return
    product_id = rng.choice(candidates)
    line = state.stock[product_id]
    product = state.products[product_id]
    _take_stock(line, product, 1)
    report.shrink_units = 1
    report.shrink_cost = product.cost
    report.cogs += product.cost


def _settle_payables(state: GameState, report: DayReport) -> None:
    for account in state.supplier_accounts:
        if account.payable <= 0 or account.due_day > state.day:
            continue
        supplier = SUPPLIERS.get(account.supplier_id)
        name = supplier.name if supplier else account.supplier_id
        if state.cash >= account.payable:
            paid = account.payable
            state.cash -= paid
            report.payables_paid += paid
            post(state, "payable", -paid, f"Paid {name} on terms.")
            report.notes.append(f"Paid {name} {money(paid)} on the open terms.")
            account.payable = 0
            account.relationship = clamp(account.relationship + 2, 0, 100)
            continue
        account.late_payments += 1
        account.relationship = clamp(account.relationship - 8, 0, 100)
        account.due_day = state.day + 3
        if account.relationship < TERMS_RELATIONSHIP:
            account.terms = "cash"
        report.notes.append(f"{name}'s bill is late. Terms are not a second credit line.")


def _score_targets(state: GameState, report: DayReport) -> None:
    for target in state.targets:
        if target.closed or target.due_day != state.day:
            continue
        if target.metric == "cash":
            met = state.cash >= target.goal
        elif target.metric == "review":
            met = int(round(state.review_score * 10)) >= target.goal
        else:
            met = state.totals.quits <= target.goal
        target.met = met
        target.closed = True
        if met:
            state.reputation_respectable = clamp(state.reputation_respectable + 1, 0, 100)
            report.notes.append(f"Quarter mark met: {target.label}.")
        else:
            report.notes.append(f"Quarter mark missed: {target.label}.")


def _close_books(state: GameState, report: DayReport) -> None:
    report.gross_profit = report.revenue - report.refunds - report.cogs
    state.quarter_sales += report.revenue
    state.quarter_cogs += report.cogs
    state.quarter_refunds += report.refunds
    state.quarter_rent += report.rent_paid
    state.quarter_wages += report.payroll_paid
    state.quarter_payroll_tax += report.payroll_tax_paid
    state.quarter_insurance += report.insurance_paid
    state.quarter_utilities += report.utilities_paid
    state.quarter_interest += report.interest_paid
    state.quarter_shipping += report.shipping
    state.quarter_card_fees += report.card_fees
    state.quarter_licenses += report.license_paid
    state.quarter_freight += report.freight_paid
    state.quarter_variance += report.variance_paid
    state.quarter_ads += report.advertising_paid
    state.quarter_severance += report.severance_paid
    state.quarter_period += report.period_paid
    state.quarter_shrink += report.shrink_cost
    state.quarter_opex += (
        report.rent_paid
        + report.payroll_paid
        + report.payroll_tax_paid
        + report.insurance_paid
        + report.utilities_paid
        + report.interest_paid
        + report.shipping
        + report.card_fees
        + report.license_paid
        + report.freight_paid
        + report.variance_paid
        + report.advertising_paid
        + report.severance_paid
        + report.period_paid
    )
    if report.revenue:
        post(state, "sales", report.revenue, f"{report.weekday} sales.")
    if report.refunds:
        post(state, "refund", -report.refunds, f"{report.weekday} refunds.")
    if is_sunday(state.day) and (report.rent_paid or report.payroll_paid):
        post(
            state,
            "bills",
            -(report.rent_paid + report.payroll_paid + report.interest_paid),
            "Sunday rent, wages, employer tax, insurance, utilities, and interest.",
        )
    if state.day % 28 == 0:
        bill = income_tax_due(state)
        if bill:
            missed = _pay(state, bill)
            report.income_tax_paid = bill - missed
            post(state, "tax", -report.income_tax_paid, "Quarter income tax.")
            if missed:
                already = report.shortfall
                report.shortfall += missed
                if already == 0:
                    state.flags.shortfalls += 1
                report.flags.append(
                    f"Income tax missed {money(missed)}. The quarter's profit is still on the statement."
                )
        _score_targets(state, report)
        statement = close_quarter(
            state,
            f"Quarter through day {state.day}. Drawer {money(state.cash)}. Income tax {money(report.income_tax_paid)}.",
        )
        report.notes.append(
            f"Quarter closed. Net {money(statement.net)} on sales {money(statement.sales)}."
        )
        _seed_targets(state, state.day + 28)
    report.credit_drawn = max(0, state.credit_used - report.credit_open)
    report.cash_end = state.cash


def spendable_offers(state: GameState) -> list:
    owned = {site.id for site in state.sites}
    available = []
    for offer in OFFERS.values():
        if offer.id in owned:
            continue
        if offer.for_online_start and state.mode != "online":
            continue
        available.append(offer)
    return available
