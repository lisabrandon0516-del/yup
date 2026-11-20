"""One corporate year. Revenue, expenses, and profit are dollars."""

from __future__ import annotations

from open_late.text import money
from open_late.ui.overview_data import _expenses

from .eras import identify
from .models import AnnualReport
from .records import calculate
from .timeline import YEAR_DAYS, build, year_for_day


def create(state, year: int) -> AnnualReport:
    start = (int(year) - 1) * YEAR_DAYS + 1
    end = int(year) * YEAR_DAYS
    reports = [row for row in list(getattr(state, "history", []) or []) if start <= int(getattr(row, "day", 0) or 0) <= end]
    last = getattr(state, "last_report", None)
    if last is not None and start <= int(getattr(last, "day", 0) or 0) <= end and not any(int(row.day) == int(last.day) for row in reports):
        reports.append(last)
    revenue = sum(int(getattr(row, "revenue", 0) or 0) for row in reports)
    costs = sum(_expenses(row) for row in reports)
    visits = sum(int(getattr(row, "visits", 0) or 0) for row in reports)
    ending_cash = _ending_cash(state, year, reports)
    financials = {
        "revenue": revenue,
        "expenses": costs,
        "net_profit": revenue - costs,
        "ending_cash": ending_cash,
    }
    doors = [door for door in getattr(state, "doors", []) or [] if int(getattr(door, "opens_on", 0) or 0) <= end]
    operations = {
        "days_reported": len(reports),
        "customer_visits": visits,
        "average_basket": revenue // visits if visits else 0,
        "store_count": len(doors),
    }
    highlights = tuple(event for event in build(state) if event.year == year and event.importance >= 2)
    records = tuple(row for row in calculate(state) if start <= row.day <= end)
    eras = tuple(era for era in identify(state) if era.start_day <= end and (era.end_day is None or era.end_day >= start))
    lessons = []
    if revenue - costs < 0:
        lessons.append(f"The year closed with an operating loss of {money(costs - revenue)}.")
    elif revenue:
        lessons.append(f"The year cleared {money(revenue - costs)} after expenses.")
    if visits and revenue // visits:
        lessons.append(f"Average basket was {money(revenue // visits)}.")
    if not highlights:
        lessons.append("No major corporate milestone was recorded for this year.")
    return AnnualReport(year, start, end, financials, operations, highlights, records, eras, tuple(lessons))


def _ending_cash(state, year: int, reports) -> int:
    if reports:
        last = max(reports, key=lambda row: int(row.day))
        ended = int(getattr(last, "cash_end", 0) or 0)
        if ended:
            return ended
    if year_for_day(int(getattr(state, "day", 1) or 1)) == int(year):
        return int(getattr(state, "cash", 0) or 0)
    return 0
