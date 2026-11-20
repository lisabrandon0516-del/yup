"""Landed-cost choice and how hard a department flinches at a higher shelf price.

The economy still sets landed cost. Nothing here raises a price on its own.
"""

from __future__ import annotations

from open_late.departments import DEPARTMENT_IDS, DEPARTMENT_LABELS
from open_late.models import Choice, GameState

# 100 is a normal reaction. Grocery is stiff. Electronics and seasonal are loose.
ELASTICITY = {
    "grocery": 0.25,
    "produce": 0.35,
    "meat_dairy": 0.35,
    "frozen": 0.40,
    "household": 0.55,
    "health_beauty": 0.60,
    "pharmacy": 0.30,
    "electronics": 1.40,
    "clothing": 1.00,
    "toys": 0.90,
    "home_garden": 0.85,
    "sporting": 0.90,
    "seasonal": 1.50,
}

ASK_AT = 102
ASK_STEP = 2


def demand_index(department: str) -> int:
    """How hard this department walks when the shelf price rises. 100 is normal."""
    return int(round(100 * ELASTICITY.get(department or "", 1.0)))


def department_flex(product) -> float:
    """1.0 at the list price. A rise trims conversion, barely in grocery, hard in seasonal."""
    from open_late.engine import _list_price

    listed = _list_price(product)
    price = int(product.price)
    if listed <= 0 or price <= listed:
        return 1.0
    lift = price / listed - 1.0
    elasticity = ELASTICITY.get(product.department or product.category or "", 1.0)
    return max(0.55, 1.0 - lift * elasticity)


def offer_landed_choice(state: GameState) -> str:
    """File one inbox note when landed cost has risen. Empty when there is nothing new to ask."""
    fresh = _fresh_rises(state)
    if not fresh:
        return ""
    if any(not message.resolved and message.kind == "landed" for message in state.inbox):
        return ""
    state.cost_pending = {dept: index for dept, index in fresh}
    lines = []
    for dept, index in fresh:
        label = DEPARTMENT_LABELS.get(dept, dept.replace("_", " ").title())
        lines.append(f"{label} is {index - 100}% above the sheet.")
    body = (
        " ".join(lines)
        + " Pass it through and the shelf price rises by that percent, where a whole dollar moves."
        + " Hold and the price stays. The margin takes the rise."
        + " Grocery barely flinches. Electronics and seasonal walk."
    )
    from open_late.inbox import add

    add(
        state,
        kind="landed",
        title="Landed cost is up",
        body=body,
        choices=[
            Choice(id="pass", label="Pass it through", effect="pass_landed"),
            Choice(id="hold", label="Hold the price", effect="hold_landed"),
        ],
    )
    return "Landed cost is up. Pass it through or hold the price. The inbox has the choice."


def apply_pass_through(state: GameState) -> str:
    pending = dict(state.cost_pending or {})
    if not pending:
        return "There is no landed-cost rise waiting."
    moved = 0
    stuck = 0
    for product in state.products.values():
        dept = product.department or product.category
        index = pending.get(dept)
        if not index or index < ASK_AT:
            continue
        raised = int(round(int(product.price) * index / 100))
        cap = int(product.cost) * 5
        if raised > cap:
            raised = cap
        if raised <= int(product.price):
            stuck += 1
            continue
        state.price_was[product.id] = int(product.price)
        product.price = raised
        moved += 1
    _remember(state, pending)
    from open_late.books import note_decision

    result = f"{moved} shelf prices rose with the cost."
    if stuck:
        result += f" {stuck} stayed because the rise is smaller than a dollar."
    note_decision(
        state,
        "price",
        "Passed the landed-cost rise through.",
        result=result,
    )
    return result + " The next close counts who walked."


def apply_hold(state: GameState) -> str:
    pending = dict(state.cost_pending or {})
    if not pending:
        return "There is no landed-cost rise waiting."
    _remember(state, pending)
    from open_late.books import note_decision

    note_decision(
        state,
        "price",
        "Held the shelf price against the landed-cost rise.",
        result="The shelf price did not move. The margin takes the rise.",
    )
    return "The shelf price stays. The margin takes the rise."


def _fresh_rises(state: GameState) -> list[tuple[str, int]]:
    from open_late.economy import cost_mult, economy_difficulty
    from open_late.hq import HOME_STORE_ID

    if economy_difficulty(state) == "off":
        return []
    asked = state.cost_asked or {}
    fresh = []
    for dept in DEPARTMENT_IDS:
        index = int(round(cost_mult(state, HOME_STORE_ID, dept) * 100))
        prior = int(asked.get(dept, 100))
        if index >= ASK_AT and index >= prior + ASK_STEP:
            fresh.append((dept, index))
    return fresh


def _remember(state: GameState, pending: dict[str, int]) -> None:
    asked = dict(state.cost_asked or {})
    for dept, index in pending.items():
        asked[dept] = max(int(asked.get(dept, 100)), int(index))
    state.cost_asked = asked
    state.cost_pending = {}
