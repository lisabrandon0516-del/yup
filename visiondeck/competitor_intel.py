"""Public rival record. Posture is inferred from what the company can see."""

from __future__ import annotations

from dataclasses import dataclass

from open_late.visiondeck.confidence import rate
from open_late.visiondeck.config import LOST_PRICE_MIN
from open_late.visiondeck.models import Observation


@dataclass(frozen=True)
class TimelineEntry:
    day: int
    chain_id: str
    name: str
    city: str
    kind: str
    text: str


@dataclass(frozen=True)
class Objective:
    text: str
    evidence: str
    confidence: str


@dataclass(frozen=True)
class RivalProfile:
    chain_id: str
    name: str
    posture: str
    pressure: str
    confidence: str
    moves: tuple[str, ...]
    objectives: tuple[Objective, ...]
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class Pressure:
    chain_id: str
    name: str
    city: str
    subject: str
    level: str
    evidence: str
    exposure: str


@dataclass(frozen=True)
class _Fact:
    chain_id: str
    name: str
    day: int
    city_slug: str
    city: str
    kind: str
    metric: str
    text: str
    value: int
    reliability: int
    store_id: str = ""


def public_observations(state) -> list[Observation]:
    rows = []
    for fact in _facts(state):
        rows.append(Observation(
            _ident(fact),
            fact.day,
            "rival",
            fact.chain_id,
            fact.kind,
            fact.metric,
            fact.value,
            None,
            "",
            fact.store_id,
            "public",
            fact.reliability,
            0,
            (
                ("text", fact.text),
                ("chain", fact.name),
                ("city", fact.city_slug),
                ("kind", fact.kind),
            ),
        ))
    return rows


def timelines(state) -> list[TimelineEntry]:
    entries = [
        TimelineEntry(fact.day, fact.chain_id, fact.name, fact.city, fact.kind, fact.text)
        for fact in _facts(state)
        if fact.metric == "public_move"
    ]
    entries.sort(key=lambda item: (item.day, item.name, item.text))
    return entries


def profiles(state) -> list[RivalProfile]:
    built = []
    for chain_id, facts in _by_chain(state).items():
        profile = _profile(state, chain_id, facts)
        if profile is not None:
            built.append(profile)
    built.sort(key=lambda item: item.name)
    return built


def pressure(state) -> list[Pressure]:
    rows = []
    for chain_id, facts in _by_chain(state).items():
        rows.extend(_pressure_rows(state, chain_id, facts))
    rows.sort(key=lambda item: (item.name, item.city))
    return rows


def _facts(state) -> list[_Fact]:
    public = _snapshot(state)
    if not public or public.get("enabled") is False:
        return []
    names = {
        str(row.get("id") or ""): str(row.get("name") or "")
        for row in (public.get("chains") or [])
    }
    day = max(1, int(getattr(state, "day", 1) or 1))
    found: list[_Fact] = []
    for item in public.get("feed") or []:
        from open_late.living import public_move

        shown = public_move(str(item.get("text") or ""))
        if not shown:
            continue
        chain_id = str(item.get("chain_id") or "")
        slug = str(item.get("city") or "")
        found.append(_Fact(
            chain_id,
            names.get(chain_id) or chain_id,
            int(item.get("day") or day),
            slug,
            _label(slug, shown),
            str(item.get("kind") or ""),
            "public_move",
            shown,
            1,
            70,
        ))
    for store in public.get("stores") or []:
        if str(store.get("status") or "") == "closed":
            continue
        chain_id = str(store.get("chain_id") or "")
        name = names.get(chain_id) or str(store.get("name") or chain_id)
        slug = str(store.get("city") or "")
        label = str(store.get("city_name") or "") or _label(slug, "")
        store_id = str(store.get("id") or "")
        index = int(store.get("price_index") or 100)
        promo = int(store.get("promo") or 0)
        aisle = str(store.get("focus") or "grocery").replace("_", " ") or "grocery"
        if index != 100:
            gap = abs(100 - index)
            unit = "point" if gap == 1 else "points"
            direction = "under" if index < 100 else "over"
            where = f" in {label}" if label else ""
            found.append(_Fact(
                chain_id,
                name,
                day,
                slug,
                label,
                "price",
                "public_price",
                f"The basket{where} is {gap} {unit} {direction} the usual price.",
                index,
                90,
                store_id,
            ))
        if promo > 0:
            where = f" in {label}" if label else ""
            found.append(_Fact(
                chain_id,
                name,
                day,
                slug,
                label,
                "promo",
                "public_promo",
                f"The {aisle} aisle{where} is {promo}% off.",
                promo,
                90,
                store_id,
            ))
    found.sort(key=lambda item: (item.day, item.chain_id, item.metric, item.text))
    return found


def _profile(state, chain_id: str, facts: list[_Fact]) -> RivalProfile | None:
    if not facts:
        return None
    moves: list[str] = []
    evidence: list[str] = []
    goals: list[Objective] = []
    aggressive = premium = expanding = False
    levels: list[str] = []
    price_pressure = False
    for fact in facts:
        evidence.append(fact.text)
        kind = fact.kind
        text = fact.text.lower()
        if fact.metric == "public_price":
            _add(moves, "Staple pricing movement")
            if fact.value < 100:
                aggressive = True
                price_pressure = True
                levels.append("High" if fact.value <= 90 else "Moderate")
                _goal(goals, "Pressure local margins.", fact.text, fact.reliability, measured=True)
            elif fact.value > 100:
                premium = True
        elif fact.metric == "public_promo":
            aggressive = True
            _add(moves, "Visible promotion")
            levels.append("High" if fact.value >= 20 else "Moderate")
            _goal(goals, "Acquire value-seeking households.", fact.text, fact.reliability, measured=True)
        elif _price_war(kind, text):
            aggressive = True
            price_pressure = True
            _add(moves, "Staple pricing movement")
            levels.append("High")
            _goal(goals, "Pressure local margins.", fact.text, fact.reliability, measured=False)
        elif _expansion(kind, text):
            expanding = True
            _add(moves, "New door")
            levels.append("Moderate")
            _goal(goals, "Defend traffic.", fact.text, fact.reliability, measured=False)
        elif _promo_text(text):
            aggressive = True
            _add(moves, "Visible promotion")
            levels.append("Moderate")
            _goal(goals, "Acquire value-seeking households.", fact.text, fact.reliability, measured=False)
        elif _restock(kind, text):
            _add(moves, "Shelf restock")
            levels.append("Low")
    if price_pressure:
        lost = _lost_price(state)
        if lost >= LOST_PRICE_MIN and _shares_a_door(state, facts, price_only=True):
            _add(moves, "Customer switching")
            evidence.append(f"{lost} customers left over price.")
            _goal(goals, "Customers are leaving over price.", f"{lost} customers left over price.", 90, measured=True)
    if not (aggressive or premium or expanding or moves):
        return None
    if aggressive:
        posture = "Aggressive"
    elif expanding:
        posture = "Expanding"
    elif premium:
        posture = "Premium"
    else:
        posture = "Unclear"
    used = [fact.reliability for fact in facts if _supports(fact, posture)]
    confidence = "moderate" if not used or any(score < 90 for score in used) else "high"
    return RivalProfile(
        chain_id,
        facts[0].name,
        posture,
        _highest(levels) if (aggressive or expanding or "Shelf restock" in moves) else "None",
        confidence,
        tuple(moves),
        tuple(goals),
        tuple(evidence),
    )


def _pressure_rows(state, chain_id: str, facts: list[_Fact]) -> list[Pressure]:
    grouped: dict[str, list[_Fact]] = {}
    for fact in facts:
        level, subject = _fact_pressure(fact)
        if not level:
            continue
        grouped.setdefault(fact.city, []).append(fact)
    rows = []
    name = facts[0].name if facts else chain_id
    for city, city_facts in grouped.items():
        ranked = [(fact, *_fact_pressure(fact)) for fact in city_facts]
        fact, level, subject = max(ranked, key=lambda item: _RANK[item[1]])
        slug = fact.city_slug
        rows.append(Pressure(
            chain_id,
            name,
            city,
            subject,
            level,
            fact.text,
            _exposure(state, city, slug),
        ))
    return rows


def _fact_pressure(fact: _Fact) -> tuple[str, str]:
    text = fact.text.lower()
    if fact.metric == "public_price" and fact.value < 100:
        return ("High" if fact.value <= 90 else "Moderate"), "visits"
    if fact.metric == "public_price":
        return "", ""
    if fact.metric == "public_promo":
        return ("High" if fact.value >= 20 else "Moderate"), "visits"
    if _price_war(fact.kind, text):
        return "High", "visits"
    if _expansion(fact.kind, text):
        return "Moderate", "visits"
    if _promo_text(text):
        return "Moderate", "visits"
    if _restock(fact.kind, text):
        return "Low", "the shelf"
    return "", ""


def _supports(fact: _Fact, posture: str) -> bool:
    if posture == "Aggressive":
        return fact.metric != "public_move" or _price_war(fact.kind, fact.text.lower()) or _promo_text(fact.text.lower()) or fact.metric == "public_promo"
    if posture == "Premium":
        return fact.metric == "public_price" and fact.value > 100
    if posture == "Expanding":
        return _expansion(fact.kind, fact.text.lower())
    return fact.metric == "public_move"


def _goal(goals: list[Objective], text: str, evidence: str, reliability: int, *, measured: bool) -> None:
    _score, confidence = rate(reliability, measured=measured)
    for index, goal in enumerate(goals):
        if goal.text == text:
            if _RANK_CONF[confidence] > _RANK_CONF[goal.confidence]:
                goals[index] = Objective(text, evidence, confidence)
            return
    goals.append(Objective(text, evidence, confidence))


def _by_chain(state) -> dict[str, list[_Fact]]:
    grouped: dict[str, list[_Fact]] = {}
    for fact in _facts(state):
        grouped.setdefault(fact.chain_id, []).append(fact)
    return grouped


def _shares_a_door(state, facts: list[_Fact], *, price_only: bool) -> bool:
    for fact in facts:
        if price_only and not (_price_war(fact.kind, fact.text.lower()) or (fact.metric == "public_price" and fact.value < 100)):
            continue
        if _door(state, fact.city, fact.city_slug):
            return True
    return False


def _exposure(state, label: str, slug: str) -> str:
    door = _door(state, label, slug)
    if door:
        return f"Your {door} door shares {label or door}."
    if label:
        return f"None of your doors shares {label}."
    return ""


def _door(state, label: str, slug: str) -> str:
    wanted = {label.lower(), slug.lower()}
    wanted.discard("")
    for door in getattr(state, "doors", []) or []:
        city = str(getattr(door, "city", "") or "")
        if city.lower() in wanted:
            return city
    return ""


def _lost_price(state) -> int:
    report = getattr(state, "last_report", None)
    return int(getattr(report, "lost_price", 0) or 0)


def _label(slug: str, shown: str) -> str:
    from open_late.ai.constants import city_name

    if slug:
        named = city_name(slug)
        if named and named != slug:
            return named
        if slug[:1].isupper():
            return slug
    if " in " in shown:
        tail = shown.split(" in ", 1)[1].split(".", 1)[0].strip()
        if tail:
            return tail
    if slug:
        return slug[:1].upper() + slug[1:]
    return ""


def _snapshot(state) -> dict:
    if state is None:
        return {}
    try:
        from open_late.rival_ai import rival_snapshot

        return rival_snapshot(state) or {}
    except Exception:
        return {}


def _ident(fact: _Fact) -> str:
    if fact.metric == "public_move":
        return f"public_move:{fact.chain_id}:{fact.kind}:{fact.city_slug}:{fact.day}"
    return f"{fact.metric}:{fact.chain_id}:{fact.city_slug}:{fact.store_id}"


def _price_war(kind: str, text: str) -> bool:
    return kind in {"start_price_war", "end_price_war"} or "price war" in text


def _expansion(kind: str, text: str) -> bool:
    return kind in {"open_store", "store_opened", "reenter"} or "supercenter" in text or "new door" in text


def _restock(kind: str, text: str) -> bool:
    return kind == "copy_best_seller" or "restock" in text


def _promo_text(text: str) -> bool:
    return "% off" in text or "promotion" in text


def _add(moves: list[str], label: str) -> None:
    if label not in moves:
        moves.append(label)


def _highest(levels: list[str]) -> str:
    if not levels:
        return "None"
    return max(levels, key=lambda level: _RANK[level])


_RANK = {"High": 3, "Moderate": 2, "Low": 1}
_RANK_CONF = {"high": 3, "moderate": 2, "low": 1}
