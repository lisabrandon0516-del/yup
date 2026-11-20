"""Economic news feed for Back Office: Retail (patch E2).

Fictional outlets only. Quota, dedupe, and prompts live here so the tick
module stays smaller. economy_news() itself stays on open_late.economy.
"""

from __future__ import annotations

from typing import Any

OUTLETS = (
    "Harbor Ledger",
    "Prairie Wire",
    "Basin Review",
    "Nightcourt Dispatch",
    "Lakeshore Notice",
    "Riverbend Desk",
)

# Factor id -> default outlet and a prompt the desk can show as a verb.
OUTLET_FOR = {
    1: "Harbor Ledger",
    6: "Basin Review",
    7: "Basin Review",
    18: "Prairie Wire",
    23: "Prairie Wire",
    24: "Prairie Wire",
    37: "Lakeshore Notice",
    38: "Lakeshore Notice",
    39: "Lakeshore Notice",
    40: "Lakeshore Notice",
    41: "Lakeshore Notice",
    44: "Basin Review",
    45: "Riverbend Desk",
    46: "Lakeshore Notice",
    57: "Basin Review",
    58: "Basin Review",
    59: "Basin Review",
    63: "Riverbend Desk",
    64: "Harbor Ledger",
    65: "Basin Review",
    66: "Prairie Wire",
    80: "Riverbend Desk",
    81: "Riverbend Desk",
}

PROMPT_FOR = {
    1: "Reticket a department (price-fit vs thin grocery margins).",
    6: "Reallocate a truck from Evansville, or wait a storm out.",
    7: "Reallocate a truck from Evansville, or wait a storm out.",
    24: "Order or hold a house (especially perishables and seasonal).",
    37: "Order or hold a house (especially perishables and seasonal).",
    38: "Order or hold a house (especially perishables and seasonal).",
    39: "Reallocate a truck from Evansville, or wait a storm out.",
    40: "Reallocate a truck from Evansville, or wait a storm out.",
    41: "Reallocate a truck from Evansville, or wait a storm out.",
    44: "Reallocate a truck from Evansville, or wait a storm out.",
    45: "Reallocate a truck from Evansville, or wait a storm out.",
    46: "Order or hold a house (especially perishables and seasonal).",
    57: "Order or hold a house (especially perishables and seasonal).",
    58: "Reallocate a truck from Evansville, or wait a storm out.",
    59: "Order or hold a house (especially perishables and seasonal).",
    63: "Reallocate a truck from Evansville, or wait a storm out.",
    64: "Order or hold a house (especially perishables and seasonal).",
    65: "Reticket a department (price-fit vs thin grocery margins).",
    66: "Order or hold a house (especially perishables and seasonal).",
    80: "Claim co-op and pick a campaign dept vs Northline.",
}

CITY_LABEL = {
    "evansville": "Evansville",
    "seattle": "Seattle",
    "houston": "Houston",
    "las_vegas": "Las Vegas",
    "naperville": "Naperville",
}


def city_label(city_id: str | None) -> str:
    if not city_id:
        return "the chain"
    return CITY_LABEL.get(city_id, city_id.replace("_", " ").title())


def default_outlet(factor_ids: list[int], city_id: str | None = None) -> str:
    for fid in factor_ids:
        if fid in OUTLET_FOR:
            return OUTLET_FOR[fid]
    if city_id == "las_vegas":
        return "Nightcourt Dispatch"
    if city_id == "houston":
        return "Basin Review"
    if city_id in ("seattle", "naperville"):
        return "Lakeshore Notice"
    if city_id == "evansville":
        return "Riverbend Desk"
    return "Harbor Ledger"


def default_prompt(factor_ids: list[int]) -> str:
    for fid in factor_ids:
        if fid in PROMPT_FOR:
            return PROMPT_FOR[fid]
    return "Order or hold a house (especially perishables and seasonal)."


def move_size(extra: dict | None) -> str:
    """A percent, or sharply / slightly, from an index delta when the caller has one."""
    extra = extra or {}
    if extra.get("delta") is None:
        return "noticeably"
    ad = abs(int(extra["delta"]))
    if ad >= 12:
        return "sharply"
    if ad <= 6:
        return "slightly"
    return f"by {ad} percent"


def headline_for(factor_id: int, *, city_id: str | None, department: str | None, direction: str, extra: dict | None = None) -> tuple[str, str]:
    """Return (headline, body) from the up/down template table for factors 1–120."""
    from open_late.economy_headlines import HEADLINES

    extra = extra or {}
    city = city_label(city_id)
    dept = (department or "grocery").replace("_", " ")
    store = extra.get("store_name") or city
    name = extra.get("factor_name")
    if not name:
        from open_late.economy import FACTORS

        name = (FACTORS.get(int(factor_id)) or {}).get("name") or "the economy desk"
    size = move_size(extra)
    key = "up" if direction != "down" else "down"
    pair = HEADLINES.get(int(factor_id))
    if pair is None:
        template = "{name} is {size} on the desk."
    else:
        template = pair[0] if key == "up" else pair[1]
    headline = template.format(name=name, city=city, dept=dept, store=store, size=size)
    outlet = default_outlet([int(factor_id)], city_id)
    body = f"{outlet} has the move on the rail. Watch the aisle it names."
    return headline, body


def difficulty_story(label: str) -> tuple[str, str, str]:
    return (
        "Riverbend Desk",
        f"The desk switched the economy to {label} this Sunday.",
        "Calm, Standard, and Stern only scale swings and event odds, not the long-run mean.",
    )


def append_news(
    state,
    *,
    factor_ids: list[int],
    headline: str,
    body: str,
    outlet: str | None = None,
    city_id: str | None = None,
    store_ids: list[str] | None = None,
    severity: int = 1,
    prompt: str | None = None,
    department: str | None = None,
    week: int | None = None,
) -> dict | None:
    """Append a news row if quota and dedupe allow. Returns the row or None."""
    eco = state.economy
    from open_late.economy import week_id, store_ids_for

    week = int(week if week is not None else week_id(state.day))
    factor_ids = [int(fid) for fid in factor_ids]
    primary = factor_ids[0] if factor_ids else 0
    city_key = city_id or ""
    # Dedupe by (factor id, city, week).
    for item in eco.news:
        if int(item.get("week_id", -1)) != week:
            continue
        if primary in [int(x) for x in item.get("factor_ids", [])] and (item.get("city_id") or "") == city_key:
            return None
    owned = list(store_ids_for(state))
    stores = list(store_ids or ([] if not city_id else [city_id] if city_id in owned else []))
    if city_id and city_id in owned and city_id not in stores:
        stores.append(city_id)
    national = not stores
    # Quota: 3 national + 1 per owned store, this Sunday (or this day for bulletins).
    if not _quota_allows(eco.news, week=week, national=national, store_ids=stores, owned=owned, severity=severity, factor_ids=factor_ids):
        return None
    outlet = outlet or default_outlet(factor_ids, city_id)
    prompt = prompt or default_prompt(factor_ids)
    row = {
        "id": f"en{eco.next_news_id}",
        "day": int(state.day),
        "week_id": week,
        "outlet": outlet,
        "headline": headline,
        "body": body,
        "factor_ids": factor_ids,
        "store_ids": stores,
        "city_id": city_id or "",
        "severity": int(severity),
        "prompt": prompt,
        "department": department or "",
        "daily": False,
    }
    eco.next_news_id += 1
    eco.news.append(row)
    if len(eco.news) > 40:
        eco.news = eco.news[-40:]
    return row


def append_daily_bulletin(
    state,
    *,
    factor_ids: list[int],
    headline: str,
    body: str,
    store_id: str,
    city_id: str | None = None,
    severity: int = 2,
    outlet: str | None = None,
    prompt: str | None = None,
    department: str | None = None,
) -> dict | None:
    """At most one intra-week bulletin per store per day."""
    eco = state.economy
    from open_late.economy import week_id

    key = str(store_id)
    if eco.daily_news_day.get(key) == int(state.day):
        return None
    factor_ids = [int(fid) for fid in factor_ids]
    primary = factor_ids[0] if factor_ids else 0
    week = week_id(state.day)
    city_key = city_id or ""
    for item in eco.news:
        if int(item.get("week_id", -1)) != week:
            continue
        if primary in [int(x) for x in item.get("factor_ids", [])] and (item.get("city_id") or "") == city_key:
            return None
    eco.daily_news_day[key] = int(state.day)
    outlet = outlet or default_outlet(factor_ids, city_id)
    prompt = prompt or default_prompt(factor_ids)
    row = {
        "id": f"en{eco.next_news_id}",
        "day": int(state.day),
        "week_id": week,
        "outlet": outlet,
        "headline": headline,
        "body": body,
        "factor_ids": factor_ids,
        "store_ids": [store_id],
        "city_id": city_id or "",
        "severity": int(severity),
        "prompt": prompt,
        "department": department or "",
        "daily": True,
    }
    eco.next_news_id += 1
    eco.news.append(row)
    if len(eco.news) > 40:
        eco.news = eco.news[-40:]
    return row


def _quota_allows(news: list[dict], *, week: int, national: bool, store_ids: list[str], owned: list[str], severity: int, factor_ids: list[int]) -> bool:
    # A thaw always gets a slot: evict the lowest-severity same-bucket Sunday item if needed.
    always = 46 in factor_ids
    existing = [item for item in news if int(item.get("week_id", -1)) == week and not item.get("daily")]
    nats = [item for item in existing if not item.get("store_ids")]
    if national:
        if len(nats) < 3:
            return True
        if always or severity >= 4:
            weakest = min(nats, key=lambda item: int(item.get("severity", 0)))
            if int(weakest.get("severity", 0)) < severity or always:
                news.remove(weakest)
                return True
        return False
    for store_id in store_ids or owned:
        taken = [item for item in existing if store_id in (item.get("store_ids") or [])]
        if len(taken) < 1:
            return True
        if always or severity >= 4:
            weakest = min(taken, key=lambda item: int(item.get("severity", 0)))
            if int(weakest.get("severity", 0)) < severity or always:
                news.remove(weakest)
                return True
    return False


def public_row(item: dict) -> dict:
    return {
        "id": item["id"],
        "day": int(item["day"]),
        "outlet": item["outlet"],
        "headline": item["headline"],
        "body": item["body"],
        "factor_ids": list(item.get("factor_ids") or []),
        "store_ids": list(item.get("store_ids") or []),
        "severity": int(item.get("severity") or 0),
        "prompt": item.get("prompt") or "",
    }
