"""The books. Cash, inventory, tax, fixtures, and what the quarter actually earned."""

from __future__ import annotations

from open_late.finance import income_tax_due, pretax_profit
from open_late.models import GameState, LedgerLine, MonthClose
from open_late.text import money

SALES_TAX_PERCENT = 8
TERMS_RELATIONSHIP = 55


def tax_on(amount: int, state=None, store_id: str | None = None) -> int:
    """Sales tax on a sale or refund. Optional state applies 104; off stays identical."""
    if amount <= 0:
        return 0
    tax = (amount * SALES_TAX_PERCENT) // 100
    if state is None:
        return tax
    from open_late.economy import economy_difficulty

    if economy_difficulty(state) == "off":
        return tax
    # (amount * 8 * index) // 10000 equals (amount * 8) // 100 when index is 100.
    from open_late.economy_e4 import sales_tax_index

    index = sales_tax_index(state, store_id)
    return (amount * SALES_TAX_PERCENT * index) // 10000


def _stock_value(stock: dict, products: dict) -> int:
    total = 0
    for product_id, line in stock.items():
        product = products.get(product_id)
        if product is None:
            continue
        total += product.cost * line.on_hand
    return total


def inventory_on_hand(state: GameState) -> int:
    total = _stock_value(state.stock, state.products)
    for door in state.doors:
        total += _stock_value(door.stock, state.products)
    return total


def inventory_on_order(state: GameState) -> int:
    total = 0
    for product_id, line in state.stock.items():
        product = state.products.get(product_id)
        if product is None:
            continue
        total += product.cost * line.on_order
    return total


def fixtures_net(state: GameState) -> int:
    return max(0, state.fixtures - state.accumulated_depreciation)


def payables(state: GameState) -> int:
    return sum(account.payable for account in state.supplier_accounts)


def assets(state: GameState) -> int:
    return state.cash + inventory_on_hand(state) + inventory_on_order(state) + fixtures_net(state)


def liabilities(state: GameState) -> int:
    total = state.credit_used + state.tax_held + payables(state)
    if getattr(state, "rival_ai", None) is not None:
        from open_late.rival_ai import player_loan_balance

        total += player_loan_balance(state)
    return total


def equity(state: GameState) -> int:
    return assets(state) - liabilities(state)


def ensure_owner_capital(state: GameState) -> None:
    """Opening equity is owner's capital. Later quarters add net income to retained earnings."""
    if state.owner_capital_set:
        return
    state.owner_capital = equity(state) - state.retained_earnings - quarter_net(state) + state.owner_draws
    state.owner_capital_set = True


def note_decision(
    state: GameState,
    kind: str,
    text: str,
    *,
    ref: str = "",
    result: str = "",
    before_units: int = -1,
    before_walked: int = -1,
    before_visits: int = -1,
) -> None:
    from open_late.models import DecisionNote

    state.decisions.append(DecisionNote(
        day=int(state.day),
        kind=kind,
        text=text,
        ref=ref,
        result=result,
        before_units=before_units,
        before_walked=before_walked,
        before_visits=before_visits,
    ))
    if len(state.decisions) > 40:
        state.decisions = state.decisions[-40:]


def decision_line(note) -> str:
    """The choice, then the next close beside it when that close has been written."""
    text = f"Day {int(note.day)}: {note.text}"
    result = str(getattr(note, "result", "") or "")
    if result:
        return f"{text} {result}"
    kind = str(getattr(note, "kind", "") or "")
    waiting = kind == "price" and int(getattr(note, "before_units", -1)) >= 0
    waiting = waiting or (kind == "ad" and int(getattr(note, "before_visits", -1)) >= 0)
    if waiting:
        return f"{text} Result waits for the next close."
    return text


def stamp_decision_results(state: GameState, report) -> None:
    """Write the close next to price changes and ads. Orders already name their due day."""
    if report is None or not int(getattr(report, "day", 0) or 0):
        return
    units = getattr(report, "units_by_product", None) or {}
    walked = getattr(report, "lost_price_by_product", None) or {}
    people = int(getattr(report, "visits", 0) or 0)
    for note in state.decisions:
        if note.result or int(note.day) > int(report.day):
            continue
        if note.kind == "price" and note.before_units >= 0:
            sold = int(units.get(note.ref, 0) or 0)
            lost = int(walked.get(note.ref, 0) or 0)
            note.result = f"Sold {sold}, was {note.before_units}. Walked {lost}, was {note.before_walked}."
        elif note.kind == "ad" and note.before_visits >= 0:
            note.result = f"People {people}, was {note.before_visits}."


def hours_open(state: GameState) -> int:
    return max(0, state.close_hour - state.open_hour)


def gross_margin(sales: int, refunds: int, cogs: int) -> int | None:
    net = sales - refunds
    if net <= 0:
        return None
    return int(round(100 * (net - cogs) / net))


def runway_days(state: GameState) -> int:
    from open_late.finance import weekly_obligations

    daily = max(1, weekly_obligations(state) // 7)
    return state.cash // daily


def post(state: GameState, kind: str, amount: int, note: str) -> None:
    state.ledger.append(LedgerLine(day=state.day, kind=kind, amount=amount, note=note))
    if len(state.ledger) > 160:
        state.ledger = state.ledger[-160:]


def quarter_net(state: GameState) -> int:
    return pretax_profit(state) - income_tax_due(state)


def close_quarter(state: GameState, note: str) -> MonthClose:
    statement = MonthClose(
        day=state.day,
        sales=state.quarter_sales,
        cogs=state.quarter_cogs,
        refunds=state.quarter_refunds,
        gross_profit=state.quarter_sales - state.quarter_refunds - state.quarter_cogs,
        operating=state.quarter_opex,
        tax=state.quarter_tax,
        depreciation=state.quarter_depreciation,
        income_tax=income_tax_due(state),
        net=quarter_net(state),
        cash=state.cash,
        inventory=inventory_on_hand(state),
        note=note,
    )
    ensure_owner_capital(state)
    state.retained_earnings += statement.net
    state.months.append(statement)
    state.months = state.months[-12:]
    state.quarter_sales = 0
    state.quarter_cogs = 0
    state.quarter_refunds = 0
    state.quarter_opex = 0
    state.quarter_tax = 0
    state.quarter_depreciation = 0
    state.quarter_rent = 0
    state.quarter_wages = 0
    state.quarter_payroll_tax = 0
    state.quarter_insurance = 0
    state.quarter_utilities = 0
    state.quarter_interest = 0
    state.quarter_shipping = 0
    state.quarter_card_fees = 0
    state.quarter_licenses = 0
    state.quarter_freight = 0
    state.quarter_variance = 0
    state.quarter_ads = 0
    state.quarter_severance = 0
    state.quarter_period = 0
    state.quarter_planogram = 0
    state.quarter_shrink = 0
    return statement


def income_lines(state: GameState) -> list[tuple[str, int]]:
    """Quarter lines. The named costs add up to Operating costs. Shrink is already inside cost of goods."""
    gross = state.quarter_sales - state.quarter_refunds - state.quarter_cogs
    named = [
        ("Rent", state.quarter_rent),
        ("Wages", state.quarter_wages),
        ("Employer tax", state.quarter_payroll_tax),
        ("Insurance", state.quarter_insurance),
        ("Utilities", state.quarter_utilities),
        ("Interest", state.quarter_interest),
        ("Shipping", state.quarter_shipping),
        ("Card fees", state.quarter_card_fees),
        ("Register licenses", state.quarter_licenses),
        ("Freight", state.quarter_freight),
        ("Purchase variance", state.quarter_variance),
        ("Advertising", state.quarter_ads),
        ("Severance", state.quarter_severance),
        ("Planogram labor", state.quarter_planogram),
        ("Other period costs", state.quarter_period),
    ]
    other = state.quarter_opex - sum(amount for _name, amount in named)
    lines = [
        ("Sales", state.quarter_sales),
        ("Refunds", -state.quarter_refunds),
        ("Cost of goods sold", -state.quarter_cogs),
        ("Gross profit", gross),
    ]
    for name, amount in named:
        if amount:
            lines.append((name, -amount))
    if other:
        lines.append(("Other operating costs", -other))
    lines.append(("Operating costs", -state.quarter_opex))
    if state.quarter_shrink:
        lines.append(("Shrink, already in cost of goods", -state.quarter_shrink))
    lines.extend([
        ("Depreciation", -state.quarter_depreciation),
        ("Income tax, 21%", -income_tax_due(state)),
        ("Quarter net", quarter_net(state)),
    ])
    return lines


def balance_lines(state: GameState) -> list[tuple[str, int]]:
    ensure_owner_capital(state)
    draws = int(state.owner_draws or 0)
    explained = state.owner_capital + state.retained_earnings + quarter_net(state) - draws
    gap = equity(state) - explained
    lines = [
        ("Cash", state.cash),
        ("Inventory", inventory_on_hand(state)),
        ("Prepaid orders", inventory_on_order(state)),
        ("Fixtures, net", fixtures_net(state)),
        ("Assets", assets(state)),
        ("Credit line", state.credit_used),
        ("Sales tax held", state.tax_held),
        ("Accounts payable", payables(state)),
        ("Liabilities", liabilities(state)),
        ("Owner's capital", state.owner_capital),
        ("Retained earnings", state.retained_earnings),
        ("This quarter", quarter_net(state)),
    ]
    if draws:
        lines.append(("Owner draws", -draws))
    if gap:
        lines.append(("Not in retained earnings", gap))
    lines.append(("Equity", equity(state)))
    return lines


def oldest_stock(state: GameState, limit: int = 6) -> list[tuple[str, int, int, int]]:
    rows = []
    for product_id, line in state.stock.items():
        if line.on_hand <= 0:
            continue
        product = state.products[product_id]
        rows.append((product.name, line.on_hand, line.age_days, product.cost * line.on_hand))
    rows.sort(key=lambda row: row[2], reverse=True)
    return rows[:limit]


def format_margin(sales: int, refunds: int, cogs: int) -> str:
    margin = gross_margin(sales, refunds, cogs)
    if margin is None:
        return "no sales yet"
    return f"{margin}%"


def describe_runway(state: GameState) -> str:
    days = runway_days(state)
    return f"About {days} days of Sunday bills sit in the drawer ({money(state.cash)})."
