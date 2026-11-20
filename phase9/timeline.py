"""Timeline from stores, closed days, the inbox, and the public rival tape."""

from __future__ import annotations

from hashlib import sha1

from open_late.text import money

from .models import CorporateEvent

YEAR_DAYS = 336


def year_for_day(day: int) -> int:
    return max(1, (max(1, int(day)) - 1) // YEAR_DAYS + 1)


def _id(*parts) -> str:
    return sha1("|".join(map(str, parts)).encode()).hexdigest()[:14]


def _reports(state) -> list:
    reports = list(getattr(state, "history", []) or [])
    last = getattr(state, "last_report", None)
    if last is not None and int(getattr(last, "day", 0) or 0) and not any(int(getattr(row, "day", 0) or 0) == int(last.day) for row in reports):
        reports.append(last)
    return reports


def build(state) -> list[CorporateEvent]:
    if state is None:
        return []
    events = []
    for door in list(getattr(state, "doors", []) or []):
        day = int(getattr(door, "opens_on", 0) or 0)
        if day > 0:
            city = str(getattr(door, "city", "") or getattr(door, "id", "Store"))
            events.append(CorporateEvent(
                _id("store_open", getattr(door, "id", ""), day),
                day,
                year_for_day(day),
                "store",
                "Store opened",
                city,
                3,
                (str(getattr(door, "id", "")),),
            ))
        closed = int(getattr(door, "closed_on", 0) or 0)
        if closed > 0:
            events.append(CorporateEvent(
                _id("store_close", getattr(door, "id", ""), closed),
                closed,
                year_for_day(closed),
                "store",
                "Store closed",
                str(getattr(door, "city", "Store")),
                4,
                (str(getattr(door, "id", "")),),
            ))
    from open_late.ui.overview_data import _expenses, _profit

    for report in _reports(state):
        day = int(getattr(report, "day", 0) or 0)
        if day <= 0:
            continue
        revenue = int(getattr(report, "revenue", 0) or 0)
        if revenue <= 0:
            continue
        profit = _profit(report)
        events.append(CorporateEvent(
            _id("close", day),
            day,
            year_for_day(day),
            "finance",
            "Daily close",
            f"Revenue {money(revenue)}; profit {money(profit)}",
            1,
            metrics={"revenue": revenue, "profit": profit, "visits": int(getattr(report, "visits", 0) or 0), "expenses": _expenses(report)},
        ))
    current_day = int(getattr(state, "day", 1) or 1)
    for index, text in enumerate(list(getattr(state, "journal", []) or [])):
        clean = " ".join(str(text).split())
        if clean:
            events.append(CorporateEvent(
                _id("journal", index, clean),
                current_day,
                year_for_day(current_day),
                "journal",
                "Company journal",
                clean[:500],
                1,
            ))
    for message in list(getattr(state, "inbox", []) or []):
        day = int(getattr(message, "day", 0) or current_day)
        title = str(getattr(message, "title", "") or "Note")
        body = " ".join(str(getattr(message, "body", "") or "").split())
        events.append(CorporateEvent(
            _id("inbox", getattr(message, "id", title), day),
            day,
            year_for_day(day),
            str(getattr(message, "kind", "journal") or "journal"),
            title,
            body[:500],
            3 if getattr(message, "urgent", False) else 2,
        ))
    events.extend(_public_rivals(state, current_day))
    return sorted(events, key=lambda event: (event.day, -event.importance, event.id))


def _public_rivals(state, current_day: int) -> list[CorporateEvent]:
    """Moves a person could already see. No cash and no internal plan."""
    try:
        from open_late.rival_ai import rival_snapshot

        public = rival_snapshot(state) if state is not None else {}
    except Exception:
        return []
    rows = []
    for index, item in enumerate(public.get("feed") or []):
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        day = int(item.get("day") or current_day)
        rows.append(CorporateEvent(
            _id("rival", index, text),
            day,
            year_for_day(day),
            "rival",
            "Rival activity",
            text[:500],
            2,
            (str(item.get("chain_id") or ""),),
        ))
    return rows
