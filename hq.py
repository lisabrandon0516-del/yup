"""Corporate HQ desk: tills, per-store days, and the chain board.

Money in this engine is integer dollars, the same unit as cash and wages,
not cents. weekly_license, install fees, and P&L fields follow that convention.
card_fee_rate is a fraction; fees are computed with integer per-thousand math
so Counter Ledger matches the existing 26-per-thousand (2.6%) card fee exactly.
"""

from __future__ import annotations

from open_late.finance import CARD_FEE_PER_THOUSAND
from open_late.models import GameState, StoreDay
from open_late.text import is_sunday, money

HOME_STORE_ID = "evansville"
DEFAULT_POS = "counter_ledger"
STORE_DAY_KEEP = 56

# Install fees are one-time and are not part of the public pos_options() rows.
INSTALL_FEE = {
    "open_drawer": 200,
    "counter_ledger": 350,
    "chain_link": 800,
}

# Integer per-thousand rates, kept beside the public fractions so 0.026 stays 26.
_FEE_PER_THOUSAND = {
    "open_drawer": 32,
    "counter_ledger": CARD_FEE_PER_THOUSAND,
    "chain_link": 21,
}

POS_OPTIONS: dict[str, dict] = {
    "open_drawer": {
        "name": "Open Drawer",
        "blurb": (
            "A cheap till and a cash drawer. No weekly license. "
            "Card fees are higher, more units walk off the count, and a few more guests leave the line."
        ),
        "weekly_license": 0,
        "card_fee_rate": 0.032,
        "shrink_mult": 1.35,
        "walked_sales_mult": 1.20,
    },
    "counter_ledger": {
        "name": "Counter Ledger",
        "blurb": (
            "The till already on the desk. Card fees stay at 2.6%. "
            "Shrink and walked sales stay where they were. No weekly license."
        ),
        "weekly_license": 0,
        "card_fee_rate": 0.026,
        "shrink_mult": 1.0,
        "walked_sales_mult": 1.0,
    },
    "chain_link": {
        "name": "Chain Link",
        "blurb": (
            "A tighter till that knows the size run. A weekly license, lower card fees, "
            "a cleaner count, and fewer guests walking out of a long ticket."
        ),
        "weekly_license": 110,
        "card_fee_rate": 0.021,
        "shrink_mult": 0.65,
        "walked_sales_mult": 0.80,
    },
}


def pos_options() -> list[dict]:
    rows = []
    for pos_id, spec in POS_OPTIONS.items():
        row = {"id": pos_id}
        row.update(spec)
        rows.append(row)
    return rows


def store_ids(state: GameState) -> list[str]:
    if state.doors:
        ids = []
        if any(door.id == HOME_STORE_ID for door in state.doors):
            ids.append(HOME_STORE_ID)
        ids.extend(door.id for door in state.doors if door.id != HOME_STORE_ID)
        return ids
    return [HOME_STORE_ID]


def store_name(state: GameState, store_id: str) -> str:
    door = next((item for item in state.doors if item.id == store_id), None)
    if door is not None:
        return door.city
    if store_id == HOME_STORE_ID:
        return state.shop_name or "Evansville"
    return store_id


def _active_pos_id(state: GameState, store_id: str) -> str:
    pos_id = state.store_pos_by_id.get(store_id) or DEFAULT_POS
    if pos_id not in POS_OPTIONS:
        return DEFAULT_POS
    return pos_id


def _spec(pos_id: str) -> dict:
    return POS_OPTIONS[pos_id if pos_id in POS_OPTIONS else DEFAULT_POS]


def _option_row(pos_id: str) -> dict:
    spec = _spec(pos_id)
    row = {"id": pos_id if pos_id in POS_OPTIONS else DEFAULT_POS}
    row.update(spec)
    return row


def store_pos(state: GameState, store_id: str) -> dict:
    row = _option_row(_active_pos_id(state, store_id))
    pending = state.pending_store_pos.get(store_id) or None
    if pending not in POS_OPTIONS:
        pending = None
    row["pending"] = pending
    return row


def set_store_pos(state: GameState, store_id: str, pos_id: str) -> str:
    if store_id not in store_ids(state):
        return "That store is not on the lease."
    if pos_id not in POS_OPTIONS:
        return "That till is not on the list."
    current = _active_pos_id(state, store_id)
    pending = state.pending_store_pos.get(store_id)
    name = POS_OPTIONS[pos_id]["name"]
    current_name = POS_OPTIONS[current]["name"]
    if pos_id == current and not pending:
        return f"{store_name(state, store_id)} is already on {name}."
    if pos_id == current and pending:
        state.pending_store_pos.pop(store_id, None)
        return f"The switch is off. {store_name(state, store_id)} stays on {current_name}."
    if pending == pos_id:
        return (
            f"{name} is already booked for {store_name(state, store_id)}. "
            "It takes over at the next Sunday close."
        )
    fee = INSTALL_FEE[pos_id]
    if state.cash < fee:
        return (
            f"Installing {name} costs {money(fee)} and the drawer has {money(state.cash)}."
        )
    state.cash -= fee
    state.spent_today += fee
    state.spent_period += fee
    state.pending_store_pos[store_id] = pos_id
    record(state, store_id, pos_fees=fee)
    state.actions_today.append(f"Booked {name} for {store_name(state, store_id)}.")
    return (
        f"{name} is booked for {store_name(state, store_id)}. "
        f"Install {money(fee)} left the drawer today. "
        "The new till takes over at the next Sunday close."
    )


def _empty_pnl(state: GameState, store_id: str, days: int) -> dict:
    return {
        "store_id": store_id,
        "name": "Chain" if store_id == "chain" else store_name(state, store_id),
        "days": days,
        "sales": 0,
        "cogs": 0,
        "labor": 0,
        "rent": 0,
        "freight": 0,
        "shrink": 0,
        "card_fees": 0,
        "pos_fees": 0,
        "contribution": 0,
    }


def _window(state: GameState, days: int) -> tuple[int, int]:
    days = max(1, int(days))
    if state.phase in ("evening", "gameover"):
        last = state.day
    else:
        last = state.day - 1
    return last - days + 1, last


def store_pnl(state: GameState, store_id: str, days: int = 7) -> dict:
    days = max(1, int(days))
    row = _empty_pnl(state, store_id, days)
    low, last = _window(state, days)
    keys = ("sales", "cogs", "labor", "rent", "freight", "shrink", "card_fees", "pos_fees")
    for item in state.store_days:
        if item.store_id != store_id or item.day < low or item.day > last:
            continue
        for key in keys:
            row[key] += int(getattr(item, key))
    row["contribution"] = (
        row["sales"]
        - row["cogs"]
        - row["labor"]
        - row["rent"]
        - row["freight"]
        - row["shrink"]
        - row["card_fees"]
        - row["pos_fees"]
    )
    return row


def chain_board(state: GameState, days: int = 7) -> list[dict]:
    days = max(1, int(days))
    rows = [store_pnl(state, store_id, days=days) for store_id in store_ids(state)]
    total = _empty_pnl(state, "chain", days)
    total["name"] = "Chain"
    keys = ("sales", "cogs", "labor", "rent", "freight", "shrink", "card_fees", "pos_fees", "contribution")
    for row in rows:
        for key in keys:
            total[key] += row[key]
    rows.append(total)
    return rows


def card_fee_for(state: GameState, store_id: str, charged: int) -> int:
    if charged <= 0:
        return 0
    pos_id = _active_pos_id(state, store_id)
    rate = _FEE_PER_THOUSAND.get(pos_id, CARD_FEE_PER_THOUSAND)
    fee = (charged * rate) // 1000
    from open_late.economy_e3 import card_fee_mult

    return int(round(fee * card_fee_mult(state, store_id)))


def shrink_mult(state: GameState, store_id: str) -> float:
    return float(_spec(_active_pos_id(state, store_id))["shrink_mult"])


def apply_walked(state: GameState, store_id: str, chance: float) -> float:
    mult = float(_spec(_active_pos_id(state, store_id))["walked_sales_mult"])
    if mult != 1.0 and mult > 0:
        chance = chance / mult
    from open_late.economy_e3 import walked_mult

    return chance * walked_mult(state, store_id)


def record(state: GameState, store_id: str, by_department: dict[str, int] | None = None, **fields: int) -> None:
    row = None
    for item in reversed(state.store_days):
        if item.day == state.day and item.store_id == store_id:
            row = item
            break
    if row is None:
        row = StoreDay(day=state.day, store_id=store_id)
        state.store_days.append(row)
    for key, value in fields.items():
        amount = int(value)
        if not amount:
            continue
        setattr(row, key, int(getattr(row, key)) + amount)
    if by_department:
        for dept, amount in by_department.items():
            if not amount:
                continue
            row.by_department[dept] = row.by_department.get(dept, 0) + int(amount)


def trim_store_days(state: GameState) -> None:
    cutoff = state.day - STORE_DAY_KEEP + 1
    if cutoff > 1:
        state.store_days = [item for item in state.store_days if item.day >= cutoff]


def record_home_trading_day(state: GameState, report) -> None:
    if state.doors:
        return
    shrink = int(report.shrink_cost) + int(getattr(report, "damage_cost", 0) or 0)
    cogs = int(report.cogs) - shrink
    if cogs < 0:
        cogs = 0
    record(
        state,
        HOME_STORE_ID,
        sales=int(report.revenue) - int(report.refunds),
        cogs=cogs,
        shrink=shrink,
        card_fees=int(report.card_fees),
        by_department=dict(getattr(report, "by_category", {}) or {}),
    )


def record_door_trading_day(
    state: GameState,
    store_id: str,
    *,
    sales: int,
    cogs: int,
    shrink: int,
    card_fees: int,
    by_department: dict[str, int] | None = None,
    visits: int = 0,
) -> None:
    record(
        state,
        store_id,
        sales=sales,
        cogs=cogs,
        shrink=shrink,
        card_fees=card_fees,
        by_department=by_department,
        visits=visits,
    )


def close_sunday_shop(state: GameState, report) -> None:
    labor = int(report.payroll_paid)
    rent = int(report.rent_paid)
    record(state, HOME_STORE_ID, labor=labor, rent=rent)
    _charge_weekly_licenses(state, report)
    _apply_pending(state)


def close_sunday_corporate(state: GameState, report=None) -> None:
    from open_late.corporate import manager_by_id, week_gross

    for door in state.doors:
        manager = manager_by_id(state, door.manager_id) if door.manager_id else None
        labor = 0
        if manager is not None and manager.employed and manager.door_id == door.id:
            labor += manager.wage
        for person in state.staff:
            if person.employed and person.door_id == door.id and person.assignment != "off":
                labor += week_gross(person, door)
        labor += door.predictability_due
        rent = door.rent_weekly
        if door.id == HOME_STORE_ID:
            rent += sum(site.rent_weekly for site in state.sites if site.is_warehouse)
        record(state, door.id, labor=labor, rent=rent)
    _charge_weekly_licenses(state, report)
    _apply_pending(state)


def _charge_weekly_licenses(state: GameState, report=None) -> None:
    from open_late.engine import _pay

    for store_id in store_ids(state):
        fee = int(_spec(_active_pos_id(state, store_id))["weekly_license"])
        if fee <= 0:
            continue
        missed = _pay(state, fee)
        paid = fee - missed
        if paid <= 0:
            continue
        record(state, store_id, pos_fees=paid)
        if report is not None:
            report.license_paid += paid


def _apply_pending(state: GameState) -> None:
    if not state.pending_store_pos:
        return
    for store_id, pos_id in list(state.pending_store_pos.items()):
        if pos_id in POS_OPTIONS:
            state.store_pos_by_id[store_id] = pos_id
    state.pending_store_pos.clear()


def finish_close(state: GameState) -> None:
    trim_store_days(state)
