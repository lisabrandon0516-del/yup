"""Small display helpers shared by the sim and the desk."""

from __future__ import annotations

import math

from open_late.departments import DEPARTMENT_LABELS, DEPARTMENTS

WEEKDAYS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

CATEGORY_LABELS = dict(DEPARTMENT_LABELS)
CATEGORY_SHORT = {dept: label for dept, label in DEPARTMENTS}


def weekday_name(day: int) -> str:
    return WEEKDAYS[(day - 1) % 7]


def is_sunday(day: int) -> bool:
    return (day - 1) % 7 == 6


def money(amount: int) -> str:
    sign = "-" if amount < 0 else ""
    return f"{sign}${abs(int(amount)):,}"


def money_compact(amount) -> str:
    """Tight display form for six-figure HQ chrome ($128.4k, $1.2M).

    Exact figures stay on money() and belong in tooltips.
    """
    try:
        value = float(amount or 0)
    except (TypeError, ValueError):
        value = 0.0
    sign = "-" if value < 0 else ""
    av = abs(value)
    if av >= 1_000_000:
        # Up to two decimals so $1.84M stays $1.84M; trailing zeros drop ($1.2M, $2M).
        body = f"${av / 1_000_000:.2f}".rstrip("0").rstrip(".") + "M"
        return sign + body
    if av >= 1_000:
        body = f"${av / 1_000:.1f}k".replace(".0k", "k")
        return sign + body
    return money(int(round(value)))


def money_compact_signed(amount) -> str:
    """Movement form: +$128.4k / −$12.5k, with an exact-style $0 at rest."""
    try:
        value = float(amount or 0)
    except (TypeError, ValueError):
        value = 0.0
    if abs(value) < 0.5:
        return money(0)
    compact = money_compact(abs(value))
    return f"+{compact}" if value > 0 else f"−{compact}"


def count_compact(amount) -> str:
    """Tight count form: 4,100 stays grouped; 28.7k when five digits get tight."""
    try:
        value = float(amount or 0)
    except (TypeError, ValueError):
        value = 0.0
    sign = "-" if value < 0 else ""
    av = abs(value)
    if av >= 1_000_000:
        body = f"{av / 1_000_000:.2f}".rstrip("0").rstrip(".") + "M"
        return sign + body
    if av >= 10_000:
        body = f"{av / 1_000:.1f}k".replace(".0k", "k")
        return sign + body
    return sign + f"{int(round(av)):,}"


def nice_money_ceiling(peak) -> int:
    """Nice chart-axis ceiling just above peak, in a 1 / 1.5 / 2 / … / 10 step."""
    try:
        peak = max(0.0, float(peak or 0))
    except (TypeError, ValueError):
        peak = 0.0
    if peak <= 10:
        return 10
    # Headroom so point labels sit above the top of the series at million scale.
    target = peak * 1.15
    exp = int(math.floor(math.log10(target)))
    base = 10 ** exp
    frac = target / base
    for mult in (1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if frac <= mult + 1e-9:
            return max(10, int(round(mult * base)))
    return max(10, int(10 * base))


def money_axis_ticks(peak, steps: int = 4) -> tuple[int, list[tuple[float, str]]]:
    """Zero-based compact ticks and a sensible ceiling for million-scale charts."""
    try:
        steps = max(1, int(steps))
    except (TypeError, ValueError):
        steps = 4
    ceiling = nice_money_ceiling(peak)
    ticks: list[tuple[float, str]] = []
    for index in range(steps + 1):
        value = ceiling * index / steps
        label = money_compact(value) if value else "$0"
        ticks.append((value, label))
    return ceiling, ticks


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))
