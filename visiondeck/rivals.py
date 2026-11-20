"""One public rival move. Private plans stay off the morning line."""

from __future__ import annotations

from dataclasses import dataclass

from open_late.ai.constants import week_of
from open_late.living import public_move


@dataclass(frozen=True)
class PublicMove:
    chain_id: str
    name: str
    text: str
    day: int
    action: str = ""
    door_id: str = ""


def public_rival_alert(state) -> PublicMove | None:
    if state is None:
        return None
    try:
        from open_late.rival_ai import rival_snapshot

        public = rival_snapshot(state) or {}
    except Exception:
        return None
    names = {
        str(row.get("id") or ""): str(row.get("name") or "")
        for row in (public.get("chains") or [])
    }
    day = max(1, int(getattr(state, "day", 1) or 1))
    current = week_of(day)
    for item in reversed(list(public.get("feed") or [])):
        if _week(item, day) != current:
            continue
        shown = public_move(str(item.get("text") or ""))
        if not shown:
            continue
        chain_id = str(item.get("chain_id") or "")
        name = names.get(chain_id) or chain_id
        if name and name not in shown:
            shown = f"{name}. {shown}"
        outlook = _projection(state, item, shown)
        choice, action, door_id = _choice(state, item, shown)
        text = f"{shown} This is only what the company can see."
        if outlook:
            text = f"{text} {outlook}"
        if choice:
            text = f"{text} {choice}"
        return PublicMove(
            chain_id,
            name,
            text,
            int(item.get("day") or day),
            action,
            door_id,
        )
    return None


def _projection(state, item, shown: str) -> str:
    pressure = _pressure(str(item.get("kind") or ""), shown)
    if not pressure:
        return ""
    city = _city_label(str(item.get("city") or ""), shown)
    door, _door_id = _shared_door(state, city, str(item.get("city") or ""))
    if door:
        return f"Projection: the pressure is on {pressure} at your {door} door."
    if city:
        return f"Projection: the pressure is on {pressure}. None of your doors shares {city}."
    return f"Projection: the pressure is on {pressure}."


def _choice(state, item, shown: str) -> tuple[str, str, str]:
    kind = str(item.get("kind") or "")
    if not _pressure(kind, shown):
        return "", "", ""
    city = _city_label(str(item.get("city") or ""), shown)
    door, door_id = _shared_door(state, city, str(item.get("city") or ""))
    if kind in {"start_price_war", "end_price_war"} or "price war" in shown.lower():
        if door:
            return f"Review prices at your {door} door, or do nothing.", "review_prices", door_id
    return "Do nothing.", "do_nothing", door_id


def _pressure(kind: str, shown: str) -> str:
    text = shown.lower()
    if kind in {"start_price_war", "end_price_war"} or "price war" in text:
        return "visits"
    if kind in {"open_store", "store_opened", "reenter"} or "supercenter" in text or "new door" in text:
        return "visits"
    if kind in {"copy_best_seller"} or "restock" in text:
        return "the shelf"
    return ""


def _city_label(slug: str, shown: str) -> str:
    from open_late.ai.constants import city_name

    if slug:
        label = city_name(slug)
        if label and label != slug:
            return label
        if slug[:1].isupper():
            return slug
    marker = " in "
    if marker in shown:
        tail = shown.split(marker, 1)[1]
        tail = tail.split(".", 1)[0].strip()
        if tail:
            return tail.split(" because ", 1)[0].strip()
    return ""


def _shared_door(state, label: str, slug: str) -> tuple[str, str]:
    wanted = {label.lower(), slug.lower()}
    wanted.discard("")
    for door in getattr(state, "doors", []) or []:
        city = str(getattr(door, "city", "") or "")
        if city.lower() in wanted:
            return city, str(getattr(door, "id", "") or "")
    return "", ""


def _week(item, fallback_day: int) -> int:
    marked = int(item.get("week") or 0)
    if marked > 0:
        return marked
    day = int(item.get("day") or fallback_day or 1)
    return week_of(max(1, day))
