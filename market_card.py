"""The four lines a door can read from the city card it already uses.

100 is neutral. A capital reads the nearest of the five city cards.
This does not change the visit math.
"""

from __future__ import annotations

from open_late.models import GameState

_CITY_NAMES = {
    "evansville": "Evansville",
    "seattle": "Seattle",
    "houston": "Houston",
    "las_vegas": "Las Vegas",
    "naperville": "Naperville",
}


def market_lines(state: GameState, store_id: str) -> tuple[str, str]:
    """One line for the door, and a longer tip."""
    from open_late.economy import _value, city_of

    city = city_of(state, store_id or "")
    income = int(_value(state, 14, city))
    unemployment = int(_value(state, 12, city))
    fuel = int(_value(state, 20, city))
    diesel = int(_value(state, 6))
    tax = _tax_bps(state, store_id)
    crowd = _crowd(income, unemployment, fuel)
    where = _CITY_NAMES.get(city, city.replace("_", " ").title())
    borrowed = ""
    if store_id and city and store_id.replace(" ", "_").lower() != city:
        borrowed = f" Read from {where}."
    face = (
        f"Income {income} · Unemployment {unemployment} · Fuel {fuel} · "
        f"Tax {_tax_label(tax)} · Crowd {crowd}.{borrowed}"
    )
    week = int((getattr(state.economy, "visits", None) or {}).get(store_id) or 0)
    week_line = f" This week's visit index is {week}." if week else ""
    tip = (
        f"{where}. Income is neighborhood income, unemployment is the local rate, "
        f"and fuel is the regional energy price. Diesel is {diesel}. "
        f"100 is neutral. {_reason(income, unemployment, fuel)}{week_line} "
        f"Sales tax is the rate on this door."
    )
    return face, tip


def _crowd(income: int, unemployment: int, fuel: int) -> int:
    raw = 100 + (income - 100) * 0.25 - (unemployment - 100) * 0.25 - (fuel - 100) * 0.15
    return int(round(max(70, min(130, raw))))


def _reason(income: int, unemployment: int, fuel: int) -> str:
    notes = []
    if income <= 98:
        notes.append("income is soft")
    elif income >= 102:
        notes.append("income is strong")
    if unemployment >= 102:
        notes.append("unemployment is high")
    elif unemployment <= 98:
        notes.append("unemployment is low")
    if fuel >= 102:
        notes.append("fuel is high")
    elif fuel <= 98:
        notes.append("fuel is cheap")
    if not notes:
        return "The card is even, so the crowd is this city's usual draw."
    quiet = income < 100 or unemployment > 100 or fuel > 100
    busy = income > 100 or unemployment < 100 or fuel < 100
    if quiet and not busy:
        ending = "so this door's card is quiet"
    elif busy and not quiet:
        ending = "so this door's card is busy"
    else:
        ending = "so the card is mixed"
    text = ", ".join(notes)
    return text[0].upper() + text[1:] + f", {ending}."


def _tax_bps(state: GameState, store_id: str) -> int:
    for door in state.doors:
        if door.id == store_id:
            return int(door.sales_tax_bps)
    from open_late.corporate import MARKETS, capital_market

    market = MARKETS.get(store_id) or capital_market(store_id)
    if market is not None:
        return int(market.sales_tax_bps)
    return 0


def _tax_label(bps: int) -> str:
    if bps % 100 == 0:
        return f"{bps // 100}%"
    return f"{bps / 100:.2f}%"
