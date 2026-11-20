"""Living Market, first slice.

The three signature corporations keep their doctrines on every new rival
game. Redline pushes price, Harbor & Pine protects margin, and Ironwood
holds cash. A weekly briefing is written only from the ledger of moves
the week actually produced. The briefing keeps the part a competitor
could see, and names how sure that read is. Each chain decides from its own
estimate, a week behind on your shelf. A cause keeps the week a household
move or a fight started, and a later week cites that week. A chain spends on
a fight only when its own traffic and the shelf it can check agree. A thin
read is a watch on the ledger. An open household fight orders more staples,
and the supplier is tight for smaller buyers the following week. Harbor
answers that fight with one store-label exclusive and leaves the staple price.
When that shelf runs short, coupon shoppers come halfway back the next week.
"""

from __future__ import annotations

from typing import Any

from open_late.ai.constants import chain_name
from open_late.ai.memory import ensure_memory
from open_late.ai.models import Mandate, RivalChain, RivalStore

# Save ids stay stable. The doctrine is the behavior.
SIGNATURE: tuple[tuple[str, str], ...] = (
    ("valuemax", "aggressive"),
    ("primestop", "premium"),
    ("allinone", "endurance"),
)
FILL: tuple[str, ...] = ("megamart", "everyday", "shopgiant", "bluestar")

PERSONALITY = {
    "aggressive": "price_leader_v1",
    "premium": "premium_v1",
    "endurance": "expander_v1",
}
HOME = {
    "aggressive": "evansville",
    "premium": "seattle",
    "endurance": "naperville",
}
# Weeks before the first big filing, so the three do not open on the same Sunday.
FILING = {"aggressive": 12, "premium": 9, "endurance": 18}
GROWTH = {"aggressive": 55, "premium": 20, "endurance": 15}
CASH_FLOOR = 12_000_000

DOCTRINE_LINE = {
    "aggressive": "aggressive penetration",
    "premium": "premium loyalty",
    "endurance": "cash endurance",
}

LEDGER_KEEP = 40

COHORTS: tuple[str, ...] = ("value_seekers", "premium_shoppers", "habitual_loyalists")
COHORT_LABEL = {
    "value_seekers": "Value seekers",
    "premium_shoppers": "Premium shoppers",
    "habitual_loyalists": "Habitual loyalists",
}
# How much of the gap toward this week's preference actually closes.
COHORT_STEP = {"value_seekers": 40, "premium_shoppers": 25, "habitual_loyalists": 10}
SHARE = 1000
# A cohort line is printed only after a banner gains this many share points.
SWITCH_POINTS = 40
OVERLAP_MIN = 40
FATIGUE_OPEN = 14
FATIGUE_DECAY = 8
FATIGUE_STOP = 70
CONFIDENCE_STOP = 30
BELIEF_SPEND = 70
TRAFFIC_MOVE = 20
PULL_UNITS = 400
HOUSEHOLD_KEEP = 70


def seats_for(player_chain_id: str) -> list[tuple[str, str]]:
    """Three rival seats. A signature chain the player took is filled by the next fascia."""
    player = str(player_chain_id or "")
    seated: list[tuple[str, str]] = []
    displaced: list[str] = []
    for chain_id, kind in SIGNATURE:
        if chain_id == player:
            displaced.append(kind)
        else:
            seated.append((chain_id, kind))
    fillers = [chain_id for chain_id in FILL if chain_id != player]
    for kind in displaced:
        seated.append((fillers.pop(0), kind))
    return seated[:3]


def seat_market(ai_state, snap) -> dict[str, str]:
    """Replace the shuffled roster with the living-market seats."""
    seats = seats_for(snap.player_chain_id)
    people = ai_state.personalities
    chains = {}
    doctrine: dict[str, str] = {}
    week = int(snap.week)
    for chain_id, kind in seats:
        person = people[PERSONALITY[kind]]
        city = HOME[kind]
        store = RivalStore(
            id=f"store:{chain_id}:{city}:1",
            city=city,
            opened_on=int(snap.day),
            status="open",
            distance_band=2,
            weekly_sales=0,
            focus_dept="grocery" if kind != "premium" else "produce",
            price_index=int(person.price_index),
        )
        chains[chain_id] = RivalChain(
            chain_id=chain_id,
            personality_id=person.id,
            price_index=int(person.price_index),
            cash=15_000_000,
            debt=0,
            credit_line=10_000_000,
            stores=[store],
            mandate=Mandate(growth_vs_profit=GROWTH[kind]),
            cooldowns={"opening": week + FILING[kind], "big_call": week + FILING[kind]},
        )
        doctrine[chain_id] = kind
        memory = ensure_memory(ai_state.memories, f"ceo:{chain_id}")
        for city_name, index in (snap.public.get("player_price_index") or {}).items():
            memory.ref_price[str(city_name)] = int(index)
    ai_state.chains = chains
    ai_state.roster = [chain_id for chain_id, _kind in seats]
    return doctrine


def corporate_state(chain, kind: str) -> str:
    if chain is None:
        return "normal"
    if int(getattr(chain, "cash", 0) or 0) < CASH_FLOOR:
        return "defensive"
    net = int(getattr(getattr(chain, "last_pnl", None), "net", 0) or 0)
    if net < 0:
        return "defensive"
    if kind == "aggressive" and int(getattr(chain, "price_index", 100) or 100) < 96:
        return "aggressive"
    return "normal"


def _chain_of(action) -> str:
    ident = str(getattr(getattr(action, "actor", None), "id", "") or "")
    if ":" not in ident:
        return ""
    return ident.split(":", 1)[1]


def gate_actions(actions: list, ai_state, world: dict) -> tuple[list, list[dict]]:
    """Ironwood does not start a price war or a new door while cash is the priority."""
    doctrine = world.get("doctrine") or {}
    kept: list = []
    held: list[dict] = []
    for action in actions:
        chain_id = _chain_of(action)
        kind = doctrine.get(chain_id)
        if kind != "endurance" or getattr(getattr(action, "actor", None), "kind", "") != "ceo":
            kept.append(action)
            continue
        chain = ai_state.chains.get(chain_id) if ai_state is not None else None
        if action.kind == "start_price_war":
            held.append(_held(chain_id, action.kind, "Cash endurance skipped a price war."))
            continue
        if action.kind == "open_store" and (chain is None or int(chain.cash) < 20_000_000):
            held.append(_held(chain_id, action.kind, "Cash endurance delayed a new door."))
            continue
        if action.kind == "set_chain_price_index":
            delta = int(action.args.get("delta") or 0)
            if delta < -1:
                args = dict(action.args)
                args["delta"] = -1
                action = action.model_copy(update={"args": args})
        kept.append(action)
    return kept, held


def _held(chain_id: str, blocked: str, reason: str) -> dict:
    return {"chain_id": chain_id, "decision": "held", "blocked": blocked, "reason": reason}


def note_player_price(world: dict, week: int, city: str, previous: int, index: int) -> None:
    """Kept so older callers still record the week. Shares move in ``observe_shoppers``."""
    del world, week, city, previous, index


# What a competitor can see. Anything else stays on the ledger.
_HIGH = {"promo", "set_chain_price_index", "copy_best_seller", "defend", "set_staffing"}
_MODERATE = {"start_price_war", "end_price_war", "open_store", "close_store", "reenter", "remodel"}
_INTERNAL_MARKS = (
    "margin is under the plan",
    "cash endurance",
    "no rule fired",
    "four weeks of costs",
    "credit line",
    "opening cooldown",
    "board's cooldown",
)


def _evidence(decision: str) -> str:
    if decision in _HIGH:
        return "high"
    if decision in _MODERATE:
        return "moderate"
    return "internal"


def _confidence_word(level: str) -> str:
    return "High confidence." if level == "high" else "Moderate confidence."


def public_move(text: str) -> str:
    """The part of a feed line a competitor could check. Internal clauses drop out."""
    original = " ".join(str(text or "").split())
    if not original:
        return ""
    raw = original
    if " No new door:" in raw:
        raw = raw.split(" No new door:")[0].strip()
    if " because " in raw:
        raw = raw.split(" because ")[0].strip()
    raw = raw.rstrip(".")
    hidden = any(mark in original.lower() for mark in _INTERNAL_MARKS)
    visible = any(word in raw.lower() for word in ("promoting", "% off", "restocked", "basket", "shelf", "promotion"))
    if hidden and not visible:
        return ""
    if not raw or any(mark in raw.lower() for mark in _INTERNAL_MARKS):
        return ""
    return raw + "."


def _brief_action(chain_id: str, doctrine_kind: str, action) -> str | None:
    level = _evidence(action.kind)
    if level == "internal":
        return None
    name = chain_name(chain_id)
    label = DOCTRINE_LINE.get(doctrine_kind, "")
    prefix = f"{name} ({label}). " if label else f"{name}. "
    args = dict(getattr(action, "args", None) or {})
    city = _city_label(str(args.get("city") or ""))
    dept = str(args.get("dept") or "").replace("_", " ")
    place = f" in {city}" if city else ""
    reason = str(getattr(action, "reason", "") or "")
    if action.kind == "promo":
        depth = int(args.get("depth") or 0)
        aisle = dept or "grocery"
        if depth <= 0:
            body = f"The {aisle} promotion{place} ended."
        else:
            body = f"The {aisle} aisle{place} is {depth}% off."
    elif action.kind == "set_chain_price_index":
        delta = int(args.get("delta") or 0)
        if delta == 0:
            return None
        points = abs(delta)
        unit = "point" if points == 1 else "points"
        verb = "came down" if delta < 0 else "came up"
        body = f"The basket {verb} by {points} {unit}."
    elif action.kind == "copy_best_seller":
        if "restock" in reason.lower() and city:
            body = f"The {city} shelf was restocked after it ran short."
        elif dept and city:
            body = f"More of the {dept} set is forward on the {city} shelf."
        elif city:
            body = f"The {city} shelf was reset."
        else:
            body = "A shelf was reset."
    elif action.kind == "start_price_war":
        body = f"A price war opened{place}."
    elif action.kind == "end_price_war":
        body = f"A price war ended{place}."
    elif action.kind == "open_store":
        body = f"A new door was filed{place}."
    elif action.kind == "close_store":
        body = f"A door closed{place}."
    elif action.kind == "reenter":
        body = f"A new door is back{place}."
    elif action.kind == "remodel":
        body = f"The {city} door is being remodeled." if city else "A door is being remodeled."
    elif action.kind == "defend":
        body = f"A public price was matched{place}."
    elif action.kind == "set_staffing":
        body = f"The crew changed{place}."
    else:
        return None
    return f"{prefix}{body} {_confidence_word(level)}"


def write_week(world: dict, week: int, results, held: list[dict], ai_state) -> list[str]:
    """The ledger keeps the real reason. The briefing keeps what you could see."""
    doctrine = world.get("doctrine") or {}
    ledger = world.setdefault("ledger", [])
    lines: list[str] = []
    for result in results or []:
        action = result.action
        if not result.accepted or getattr(action.actor, "kind", "") != "ceo":
            continue
        if action.kind in {"do_nothing", "hold"}:
            continue
        chain_id = _chain_of(action)
        chain = ai_state.chains.get(chain_id) if ai_state is not None else None
        kind = doctrine.get(chain_id, "")
        reason = action.reason or _fallback_reason(action.kind, kind)
        level = _evidence(action.kind)
        ledger.append({
            "week": int(week),
            "chain_id": chain_id,
            "decision": action.kind,
            "reason": reason,
            "state": corporate_state(chain, kind),
            "confidence": level,
        })
        spoken = _brief_action(chain_id, kind, action)
        if spoken:
            lines.append(spoken)
    for item in held:
        chain_id = str(item.get("chain_id") or "")
        chain = ai_state.chains.get(chain_id) if ai_state is not None else None
        kind = doctrine.get(chain_id, "endurance")
        ledger.append({
            "week": int(week),
            "chain_id": chain_id,
            "decision": "held",
            "blocked": item.get("blocked") or "",
            "reason": item.get("reason") or "",
            "state": corporate_state(chain, kind),
            "confidence": "internal",
        })
    for switch in world.get("switches") or []:
        if int(switch.get("week") or 0) == int(week) and switch.get("text"):
            lines.append(f"{switch['text']} Moderate confidence.")
    for note in world.get("rivalry_notes") or []:
        if int(note.get("week") or 0) == int(week) and note.get("text"):
            lines.append(f"{note['text']} Moderate confidence.")
    lines.extend(_short_lines(world, week))
    lines.extend(_exclusive_lines(world, week))
    del ledger[:-LEDGER_KEEP]
    if not lines:
        lines.append("No chain posted a material move this week.")
    # One city can write the same price sentence several times. Keep the first.
    seen: list[str] = []
    for line in lines:
        if line not in seen:
            seen.append(line)
    world["briefing"] = seen
    return seen


def _fallback_reason(decision: str, kind: str) -> str:
    label = DOCTRINE_LINE.get(kind, "its doctrine")
    return f"Moved under {label}: {decision.replace('_', ' ')}."


def roster_sentence(doctrine: dict[str, str]) -> str:
    parts = []
    for chain_id, kind in doctrine.items():
        parts.append(f"{chain_name(chain_id)} on {DOCTRINE_LINE.get(kind, kind)}")
    if not parts:
        return "The living market has no seated chains."
    return "Living market: " + "; ".join(parts) + "."


def shelf_ratio(state, category: str) -> int:
    """Price over cost for one category, scaled so 100 is cost."""
    price = cost = 0
    for product in state.products.values():
        if str(getattr(product, "category", "") or "") != category:
            continue
        price += int(product.price)
        cost += int(product.cost)
    if cost <= 0:
        return 100
    return int(round(1000 * price / cost))


def remember_shelf_base(state, world: dict) -> None:
    world["shelf_base"] = {
        "household": shelf_ratio(state, "household"),
        "grocery": shelf_ratio(state, "grocery"),
    }


def _banner(chain_id: str) -> str:
    if chain_id == "player":
        return "your shelves"
    return chain_name(chain_id)


def _city_label(city: str) -> str:
    from open_late.ai.constants import city_name

    return city_name(city)


def _split(ids: list[str]) -> dict[str, int]:
    if not ids:
        return {}
    base = SHARE // len(ids)
    shares = {ident: base for ident in ids}
    shares[ids[0]] += SHARE - base * len(ids)
    return shares


def _renorm(shares: dict[str, int]) -> dict[str, int]:
    if not shares:
        return {}
    total = sum(int(value) for value in shares.values())
    if total <= 0:
        return _split(list(shares))
    out = {key: int(value) * SHARE // total for key, value in shares.items()}
    drift = SHARE - sum(out.values())
    leader = max(out, key=out.get)
    out[leader] += drift
    return out


def _memory(world: dict) -> dict[str, int]:
    stored = world.setdefault("memory", {})
    return stored


def _decay_memory(world: dict) -> None:
    stored = _memory(world)
    dead = []
    for key, strength in list(stored.items()):
        nxt = int(strength) * 85 // 100
        if nxt <= 0:
            dead.append(key)
        else:
            stored[key] = nxt
    for key in dead:
        del stored[key]


def _add_memory(world: dict, city: str, chain_id: str, cohort: str, event: str, amount: int) -> None:
    key = f"{city}|{chain_id}|{cohort}|{event}"
    stored = _memory(world)
    stored[key] = min(100, int(stored.get(key, 0)) + int(amount))


_HELPS = {"price_cut", "promotion", "visit", "exclusive"}
_HURTS = {"price_rise", "stockout"}


def _open_cause(world: dict, story: str) -> dict | None:
    for row in world.get("causes") or []:
        if row.get("open") and row.get("story") == story:
            return row
    return None


def _start_cause(world: dict, week: int, kind: str, city: str, banners: list[str], aisle: str, story: str, share: int) -> dict:
    existing = _open_cause(world, story)
    if existing is not None:
        return existing
    row = {
        "story": story,
        "kind": kind,
        "city": city,
        "week": int(week),
        "closed_week": None,
        "open": True,
        "banners": list(banners),
        "aisle": aisle,
        "close_reason": "",
        "share": int(share),
    }
    causes = world.setdefault("causes", [])
    causes.append(row)
    del causes[:-40]
    return row


def _close_cause(world: dict, story: str, week: int, reason: str) -> dict | None:
    row = _open_cause(world, story)
    if row is None:
        return None
    row["open"] = False
    row["closed_week"] = int(week)
    row["close_reason"] = reason
    world.setdefault("ledger", []).append({
        "week": int(row["week"]),
        "closed_week": int(week),
        "chain_id": str((row.get("banners") or [""])[0]),
        "decision": "cause",
        "reason": reason,
        "story": story,
        "city": row.get("city") or "",
        "aisle": row.get("aisle") or "",
        "confidence": "moderate",
    })
    return row


def _habit(world: dict, city: str, chain_id: str, cohort: str) -> int:
    stored = _memory(world)
    prefix = f"{city}|{chain_id}|{cohort}|"
    total = 0
    for key, value in stored.items():
        if not key.startswith(prefix):
            continue
        event = key.rsplit("|", 1)[-1]
        if event in _HELPS:
            total += int(value)
        elif event in _HURTS:
            total -= int(value)
    return total


def _score(cohort: str, row: dict, habit: int) -> int:
    price = int(row.get("price_index") or 100)
    promo = int(row.get("promo") or 0)
    stock = int(row.get("stockouts") or 0)
    if cohort == "value_seekers":
        staple = 80 if row.get("household_cut") and stock == 0 else 0
        return (120 - price) * 3 + promo // 4 - stock * 14 + habit + staple
    if cohort == "premium_shoppers":
        premium = 22 if row.get("doctrine") == "premium" else 0
        exclusive = 24 if row.get("exclusive") else 0
        cheap = max(0, 100 - price)
        return premium + price + habit + exclusive - stock * 12 - cheap
    return habit * 3 + promo // 8 - stock * 5


def observe_shoppers(world: dict, week: int, rows: list[dict]) -> list[dict]:
    """Move cohort shares from this week's prices, stockouts, promotions, and visits.

    Returns the switches large enough to brief. A one-point price gap does not
    empty a rival, and a repeated event sticks harder than a new one.
    """
    world["sight"] = [dict(row) for row in rows]
    _decay_memory(world)
    by_city: dict[str, list[dict]] = {}
    household_cut = False
    for row in rows:
        city = str(row.get("city") or "")
        if not city:
            continue
        by_city.setdefault(city, []).append(row)
        if row.get("chain_id") == "player" and row.get("household_cut"):
            household_cut = True
    world["household_cut"] = household_cut
    shoppers = world.setdefault("shoppers", {})
    switches: list[dict] = []
    for city, group in by_city.items():
        ids = []
        for row in group:
            ident = str(row.get("chain_id") or "")
            if ident and ident not in ids:
                ids.append(ident)
        if len(ids) < 2:
            continue
        city_book = shoppers.setdefault(city, {})
        present = {str(row.get("chain_id")): row for row in group}
        for ident, row in present.items():
            if row.get("exclusive") or _has_exclusive(world, city, ident):
                row["exclusive"] = True
        for cohort in COHORTS:
            current = dict(city_book.get(cohort) or _split(ids))
            for ident in ids:
                current.setdefault(ident, 0)
            for ident in list(current):
                if ident not in present:
                    current.pop(ident, None)
            current = _renorm(current)
            for ident, row in present.items():
                prev = int(row.get("prev_price") if row.get("prev_price") is not None else row.get("price_index") or 100)
                price = int(row.get("price_index") or 100)
                if row.get("household_cut") and int(row.get("stockouts") or 0) == 0 and cohort == "value_seekers":
                    _add_memory(world, city, ident, cohort, "price_cut", 20)
                elif price <= prev - 2 and cohort == "value_seekers":
                    _add_memory(world, city, ident, cohort, "price_cut", 16)
                elif price <= prev - 2 and cohort == "habitual_loyalists":
                    _add_memory(world, city, ident, cohort, "price_cut", 4)
                elif price >= prev + 2 and cohort == "premium_shoppers":
                    _add_memory(world, city, ident, cohort, "price_rise", 8)
                elif price >= prev + 2 and cohort == "value_seekers":
                    _add_memory(world, city, ident, cohort, "price_rise", 6)
                if int(row.get("promo") or 0) >= 10 and cohort in {"value_seekers", "habitual_loyalists"}:
                    gain = 8 if cohort == "value_seekers" else 3
                    _add_memory(world, city, ident, cohort, "promotion", gain)
                if int(row.get("stockouts") or 0) >= 1:
                    hit = {"value_seekers": 14, "premium_shoppers": 10, "habitual_loyalists": 5}[cohort]
                    _add_memory(world, city, ident, cohort, "stockout", hit)
                if row.get("exclusive") and cohort == "premium_shoppers":
                    _add_memory(world, city, ident, cohort, "exclusive", 24)
            weights = {}
            for ident, row in present.items():
                weights[ident] = max(1, _score(cohort, row, _habit(world, city, ident, cohort)))
            target = _renorm(weights)
            step = COHORT_STEP[cohort]
            moved = {}
            for ident in ids:
                cur = int(current.get(ident, 0))
                nxt = cur + (int(target.get(ident, 0)) - cur) * step // 100
                moved[ident] = nxt
            moved = _renorm(moved)
            ordered = sorted(ids, key=lambda ident: int(moved.get(ident, 0)), reverse=True)
            if len(ordered) == 1 or int(moved[ordered[0]]) > int(moved[ordered[1]]):
                _add_memory(world, city, ordered[0], cohort, "visit", 6 if cohort == "habitual_loyalists" else 2)
            city_book[cohort] = moved
            gainers = sorted(ids, key=lambda ident: int(moved.get(ident, 0)) - int(current.get(ident, 0)), reverse=True)
            if not gainers:
                continue
            top = gainers[0]
            gain = int(moved.get(top, 0)) - int(current.get(top, 0))
            story = f"household|{city}|value_seekers"
            cause = _open_cause(world, story) if cohort == "value_seekers" else None
            if cause is not None:
                holder = str((cause.get("banners") or ["player"])[0])
                held = int(cause.get("share") or 0)
                now = int(moved.get(holder, 0))
                if held - now >= SWITCH_POINTS:
                    _close_cause(world, story, week, "Value seekers moved on.")
                    cause = None
                else:
                    cause["share"] = max(held, now)
            if gain >= SWITCH_POINTS:
                if cause is not None and holder == top:
                    continue
                text = f"{COHORT_LABEL[cohort]} in {_city_label(city)} moved toward {_banner(top)}."
                if cohort == "value_seekers" and household_cut and top == "player":
                    others = [ident for ident in ids if ident != top]
                    _start_cause(world, week, "household", city, [top, *others[:1]], "household", story, int(moved.get(top, 0)))
                switches.append({"week": int(week), "city": city, "cohort": cohort, "chain_id": top, "gain": gain, "text": text})
    prior = [row for row in world.get("switches") or [] if int(row.get("week") or 0) != int(week)]
    world["switches"] = (prior + switches)[-24:]
    settle_returns(world, week)
    return switches


def _schedule_return(world: dict, week: int, city: str, attacker: str, record: dict) -> None:
    """Coupon traffic walks halfway back next week. Habit is not part of this."""
    before = {ident: int(points) for ident, points in (record.get("value_before") or {}).items()}
    frozen = {ident: int(points) for ident, points in _value_shares(world, city).items()}
    if not before or not frozen:
        return
    if int(frozen.get(attacker, 0)) <= int(before.get(attacker, 0)):
        return
    world.setdefault("returns", []).append({
        "city": city,
        "due_week": int(week) + 1,
        "opened_week": int(record.get("opened_week") or week),
        "attacker": attacker,
        "target": str(record.get("target") or ""),
        "before": before,
        "frozen": frozen,
        "done": False,
    })


def settle_returns(world: dict, week: int) -> None:
    """Move value seekers halfway toward the shares from the week the fight opened."""
    for row in world.get("returns") or []:
        if row.get("done") or int(row.get("due_week") or 0) != int(week):
            continue
        before = {ident: int(points) for ident, points in (row.get("before") or {}).items()}
        frozen = {ident: int(points) for ident, points in (row.get("frozen") or {}).items()}
        row["done"] = True
        if not before or not frozen:
            continue
        nxt = {}
        moved = False
        for ident in list(dict.fromkeys([*frozen, *before])):
            start = int(frozen.get(ident, before.get(ident, 0)))
            goal = int(before.get(ident, start))
            step = start + (goal - start) // 2
            nxt[ident] = step
            if step != start:
                moved = True
        if not moved:
            continue
        city = str(row.get("city") or "")
        book = world.setdefault("shoppers", {}).setdefault(city, {})
        book["value_seekers"] = _renorm(nxt)
        opened = int(row.get("opened_week") or 0)
        text = f"Some household traffic in {_city_label(city)} came back. The fight opened in week {opened}."
        switches = world.setdefault("switches", [])
        switches.append({
            "week": int(week),
            "city": city,
            "cohort": "value_seekers",
            "chain_id": str(row.get("target") or ""),
            "gain": 0,
            "text": text,
        })
        del switches[:-24]


def chain_pull(world: dict, city: str, chain_id: str) -> float:
    """Visit weight from the three cohorts. 1.0 is an even split."""
    book = (world.get("shoppers") or {}).get(city) or {}
    if not book:
        return 1.0
    samples = []
    for cohort in COHORTS:
        shares = book.get(cohort) or {}
        if chain_id not in shares or len(shares) < 2:
            continue
        even = SHARE / len(shares)
        samples.append(int(shares[chain_id]) / even)
    if not samples:
        return 1.0
    pull = sum(samples) / len(samples)
    return max(0.85, min(1.15, pull))


def player_visit_factor(state, store_id: str) -> float:
    rival = getattr(state, "rival_ai", None)
    live = getattr(rival, "_live", None) if rival is not None else None
    if live:
        from open_late.economy import city_of

        base = chain_pull(live["world"], city_of(state, store_id), "player")
    else:
        base = 1.0
    shoppers = getattr(state, "shopperlife", None)
    if shoppers is None or not shoppers.enabled:
        return base
    from open_late.shopperlife.signals import trip_pull

    pull = trip_pull(shoppers, "player")
    if pull is None:
        return base
    return max(0.85, min(1.15, (base + pull) / 2))


def scale_rival_traffic(card, world: dict, ai_state) -> None:
    if card is None or ai_state is None:
        return
    for chain in ai_state.chains.values():
        for store in chain.stores:
            if store.status != "open" or store.id not in card.visit_mult:
                continue
            pull = chain_pull(world, store.city, chain.chain_id)
            card.visit_mult[store.id] = max(0, min(5000, int(round(card.visit_mult[store.id] * pull))))


def pull_supply(ai_state, world: dict, week: int) -> None:
    """An open household fight places one staple order. Smaller buyers feel it next week."""
    book = world.setdefault("supply", {}).setdefault("household", {})
    book.setdefault("pulls", [])
    book.setdefault("shorts", [])
    book.setdefault("tight_week", 0)
    attacker = ""
    for record in (world.get("rivalry") or {}).values():
        if not record.get("open") or record.get("aisle") != "household":
            continue
        ident = str(record.get("attacker") or "")
        if (world.get("doctrine") or {}).get(ident) != "aggressive":
            continue
        if ai_state.chains.get(ident) is None:
            continue
        attacker = ident
        break
    if not attacker:
        return
    if not any(int(row.get("week") or 0) == int(week) and row.get("buyer") == attacker for row in book["pulls"]):
        book["pulls"].append({"week": int(week), "buyer": attacker, "units": PULL_UNITS})
        del book["pulls"][:-12]
        world.setdefault("ledger", []).append({
            "week": int(week),
            "chain_id": attacker,
            "decision": "supply_pull",
            "reason": f"{chain_name(attacker)} ordered {PULL_UNITS} more household units.",
            "state": "normal",
            "confidence": "internal",
        })
    book["tight_week"] = int(week) + 1


def supplier_is_tight(world: dict, week: int) -> bool:
    row = ((world.get("supply") or {}).get("household") or {})
    return int(row.get("tight_week") or 0) == int(week)


def short_delivery(state, order) -> int:
    """Hold back household units on a tight week. The order's lines become what arrived."""
    block = getattr(state, "rival_ai", None)
    live = getattr(block, "_live", None) if block is not None else None
    if not live or not getattr(block, "enabled", False):
        return 0
    world = live.get("world") or {}
    from open_late.ai.constants import week_of

    week = week_of(int(state.day))
    if not supplier_is_tight(world, week):
        return 0
    shorted = 0
    updated: dict[str, int] = {}
    for product_id, qty in order.lines.items():
        amount = int(qty)
        product = state.products.get(product_id)
        if product is None or str(getattr(product, "category", "") or "") != "household" or amount < 2:
            updated[product_id] = amount
            continue
        keep = max(1, amount * HOUSEHOLD_KEEP // 100)
        shorted += amount - keep
        updated[product_id] = keep
    if shorted <= 0:
        return 0
    order.lines = updated
    household = world.setdefault("supply", {}).setdefault("household", {})
    shorts = household.setdefault("shorts", [])
    shorts.append({
        "week": week,
        "supplier_id": str(order.supplier_id),
        "units": shorted,
        "order_id": str(order.id),
    })
    del shorts[:-12]
    return shorted


def _short_lines(world: dict, week: int) -> list[str]:
    from open_late.ai.constants import SUPPLIER_NAMES

    grouped: dict[str, int] = {}
    row = ((world.get("supply") or {}).get("household") or {})
    for short in row.get("shorts") or []:
        if int(short.get("week") or 0) != int(week):
            continue
        units = int(short.get("units") or 0)
        if units <= 0:
            continue
        supplier_id = str(short.get("supplier_id") or "")
        grouped[supplier_id] = grouped.get(supplier_id, 0) + units
    lines = []
    for supplier_id, units in grouped.items():
        name = SUPPLIER_NAMES.get(supplier_id, "The supplier")
        lines.append(f"The household truck from {name} arrived short. {units} units did not come. High confidence.")
    return lines


def _has_exclusive(world: dict, city: str, chain_id: str) -> bool:
    return any(
        row.get("open") and row.get("city") == city and row.get("chain_id") == chain_id
        for row in world.get("exclusives") or []
    )


def _place_exclusive(world: dict, week: int, city: str, chain_id: str) -> None:
    rows = world.setdefault("exclusives", [])
    if _has_exclusive(world, city, chain_id):
        return
    rows.append({"city": city, "chain_id": chain_id, "week": int(week), "open": True})
    del rows[:-12]
    world.setdefault("ledger", []).append({
        "week": int(week),
        "chain_id": chain_id,
        "city": city,
        "decision": "exclusive",
        "reason": "The staple price was left alone. A store-label exclusive went on the premium shelf.",
        "state": "normal",
        "confidence": "high",
    })


def _close_exclusive(world: dict, city: str, chain_id: str) -> None:
    for row in world.get("exclusives") or []:
        if row.get("city") == city and row.get("chain_id") == chain_id:
            row["open"] = False


def _exclusive_lines(world: dict, week: int) -> list[str]:
    lines = []
    seen: set[str] = set()
    for row in world.get("exclusives") or []:
        if int(row.get("week") or 0) != int(week):
            continue
        city = _city_label(str(row.get("city") or ""))
        if not city or city in seen:
            continue
        seen.add(city)
        lines.append(f"A store-label exclusive is on the {city} shelf. High confidence.")
    return lines


def strain_supply(ai_state, world: dict) -> None:
    """A deep staple campaign at a low price leaves the shelf short."""
    doctrine = world.get("doctrine") or {}
    for chain_id, chain in ai_state.chains.items():
        if doctrine.get(chain_id) != "aggressive":
            continue
        if int(chain.price_index) > 94:
            continue
        for store in chain.stores:
            if store.status == "open" and int(store.promo_depth) >= 15:
                store.stockouts = min(3, int(store.stockouts) + 1)


def _pair_key(city: str, left: str, right: str) -> str:
    first, second = sorted((left, right))
    return f"{city}|{first}|{second}"


def _open_cities(ai_state) -> dict[str, set[str]]:
    doors: dict[str, set[str]] = {}
    for chain_id, chain in ai_state.chains.items():
        cities = {store.city for store in chain.stores if store.status == "open"}
        if cities:
            doors[chain_id] = cities
    return doors


def _value_shares(world: dict, city: str) -> dict[str, int]:
    return dict((((world.get("shoppers") or {}).get(city) or {}).get("value_seekers") or {}))


def _banners(ai_state, world: dict, city: str) -> list[str]:
    present = [chain_id for chain_id, cities in _open_cities(ai_state).items() if city in cities]
    if _player_in_city(world, city) and "player" not in present:
        present.append("player")
    return present


def _short_shelf(ai_state, chain_id: str, city: str) -> bool:
    chain = ai_state.chains.get(chain_id)
    if chain is None:
        return False
    return any(store.city == city and store.status == "open" and int(store.stockouts) >= 2 for store in chain.stores)


def _rivalry_note(world: dict, week: int, key: str, kind: str, text: str) -> None:
    notes = world.setdefault("rivalry_notes", [])
    if any(int(row.get("week") or 0) == int(week) and row.get("key") == key and row.get("kind") == kind for row in notes):
        return
    notes.append({"week": int(week), "key": key, "kind": kind, "text": text})
    del notes[:-24]


def _player_in_city(world: dict, city: str) -> bool:
    for row in world.get("sight") or []:
        if row.get("city") == city and row.get("chain_id") == "player":
            return True
    for book in (world.get("estimates") or {}).values():
        est = book.get(city) or {}
        if "player" in (est.get("known") or []):
            return True
    for record in (world.get("rivalry") or {}).values():
        if record.get("city") == city and "player" in (record.get("attacker"), record.get("target")):
            return True
    return False


def _feel_own_share(est: dict, chain_id: str, true_own: int) -> int:
    """Move this chain's own share toward the traffic it felt. Other banners keep its guess."""
    shares = {key: int(value) for key, value in (est.get("share") or {}).items()}
    if chain_id not in shares:
        return 0
    old = shares[chain_id]
    felt = old + (int(true_own) - old) // 2
    delta = felt - old
    others = [ident for ident in shares if ident != chain_id]
    shares[chain_id] = felt
    if others and delta != 0:
        left = abs(delta)
        sign = -1 if delta > 0 else 1
        for index, ident in enumerate(others):
            part = left if index == len(others) - 1 else left // (len(others) - index)
            left -= part
            shares[ident] = max(0, shares[ident] + sign * part)
    est["share"] = _renorm(shares)
    return delta


def revise_estimates(ai_state, world: dict, week: int) -> None:
    """Each chain keeps a private read. Your shelf arrives a week late."""
    estimates = world.setdefault("estimates", {})
    doors = _open_cities(ai_state)
    seen_player: dict[str, dict] = {}
    for row in world.get("sight") or []:
        if row.get("chain_id") == "player" and row.get("city"):
            seen_player[str(row["city"])] = row
    for chain_id, cities in doors.items():
        book = estimates.setdefault(chain_id, {})
        chain = ai_state.chains[chain_id]
        for city in cities:
            est = book.setdefault(city, {})
            if "pending_player_price" in est:
                price = int(est.pop("pending_player_price"))
                cut = bool(est.pop("pending_player_cut", False))
                changed = est.get("player_price") != price or bool(est.get("player_cut")) != cut
                est["player_price"] = price
                est["player_cut"] = cut
                if changed:
                    world.setdefault("ledger", []).append({
                        "week": int(week),
                        "chain_id": chain_id,
                        "decision": "estimate",
                        "reason": f"Read the {_city_label(city)} shelf a week late at {price}.",
                        "state": "normal",
                        "confidence": "internal",
                    })
            else:
                est.setdefault("player_cut", False)
            store = next((item for item in chain.stores if item.city == city and item.status == "open"), None)
            if store is not None:
                est["own_price"] = int(store.price_index)
                est["own_promo"] = int(store.promo_depth)
                est["own_stockouts"] = int(store.stockouts)
            row = seen_player.get(city)
            if row is not None:
                est["pending_player_price"] = int(row.get("price_index") or 100)
                est["pending_player_cut"] = bool(row.get("household_cut"))
            known = [ident for ident, group in doors.items() if city in group]
            if row is not None or est.get("player_price") is not None or "pending_player_price" in est:
                if "player" not in known:
                    known.append("player")
            est["known"] = known
            true = _value_shares(world, city)
            if "share" not in est or set(est["share"]) != set(known):
                est["share"] = _split(known)
            delta = 0
            if chain_id in true:
                delta = _feel_own_share(est, chain_id, int(true[chain_id]))
            est["traffic_delta"] = delta
            est["rival_prices"] = _rival_prices(ai_state, chain_id, city)
            est["belief"] = _belief_score(est, delta)


def _rival_prices(ai_state, chain_id: str, city: str) -> dict[str, int]:
    prices = {}
    for other_id, other in ai_state.chains.items():
        if other_id == chain_id:
            continue
        for store in other.stores:
            if store.city == city and store.status == "open":
                prices[other_id] = int(store.price_index)
    return prices


def _belief_score(est: dict, delta: int) -> int:
    """Traffic and a shelf the chain can check. A quiet week or an unpaid fight lowers it."""
    belief = 40
    moved = abs(int(delta)) >= TRAFFIC_MOVE
    if moved:
        belief += 25
    else:
        belief -= 20
    if moved and int(delta) < 0:
        own = int(est.get("own_price") or 100)
        rich = any(int(price) >= own + 8 for price in (est.get("rival_prices") or {}).values())
        if est.get("player_cut") or rich:
            belief += 25
    if est.get("unpaid"):
        belief -= 25
        est["unpaid"] = False
    return max(0, min(100, belief))


def _watch(world: dict, week: int, chain_id: str, city: str) -> None:
    reason = f"{chain_name(chain_id)} is watching the {_city_label(city)} shelf."
    ledger = world.setdefault("ledger", [])
    if any(
        row.get("decision") == "watch" and int(row.get("week") or 0) == int(week) and row.get("chain_id") == chain_id and row.get("city") == city
        for row in ledger
    ):
        return
    ledger.append({
        "week": int(week),
        "chain_id": chain_id,
        "city": city,
        "decision": "watch",
        "reason": reason,
        "state": "normal",
        "confidence": "internal",
    })


def _decision_overlap(world: dict, city: str, left: str, right: str) -> int:
    """Overlap from a chain's own estimate. The true book is not consulted."""
    for ident, other in ((left, right), (right, left)):
        est = ((world.get("estimates") or {}).get(ident) or {}).get(city) or {}
        shares = est.get("share") or {}
        if ident in shares and other in shares:
            small = min(int(shares[ident]), int(shares[other]))
            if small < 80:
                return 0
            return min(100, small * 100 // 250)
    return 0


def review_rivalry(ai_state, world: dict, week: int) -> None:
    """Update one record per pair that shares a city. Open and ease are the only notes."""
    revise_estimates(ai_state, world, week)
    doctrine = world.get("doctrine") or {}
    book = world.setdefault("rivalry", {})
    doors = _open_cities(ai_state)
    cities: set[str] = set()
    for group in doors.values():
        cities.update(group)
    cities.update((world.get("shoppers") or {}).keys())
    for switch in world.get("switches") or []:
        if switch.get("city"):
            cities.add(str(switch["city"]))
    seen: set[str] = set()
    for city in sorted(cities):
        present = _banners(ai_state, world, city)
        for index, left in enumerate(present):
            for right in present[index + 1:]:
                key = _pair_key(city, left, right)
                seen.add(key)
                overlap = _decision_overlap(world, city, left, right)
                record = book.get(key) or {
                    "city": city,
                    "open": False,
                    "attacker": "",
                    "target": "",
                    "aisle": "",
                    "fatigue": 0,
                    "confidence": 55,
                    "age": 0,
                    "last_gain": 0,
                    "attacks": [],
                    "share": {},
                }
                record["overlap"] = overlap
                shares = _value_shares(world, city)
                attacker = str(record.get("attacker") or "")
                eased_now = False
                if record.get("open") and attacker:
                    previous = int((record.get("share") or {}).get(attacker, shares.get(attacker, 0)))
                    record["last_gain"] = int(shares.get(attacker, previous)) - previous
                    record["age"] = int(record.get("age") or 0) + 1
                    record["fatigue"] = min(100, int(record.get("fatigue") or 0) + FATIGUE_OPEN)
                    if record["last_gain"] > 0:
                        record["confidence"] = min(100, int(record.get("confidence") or 55) + 10)
                    elif int(record.get("age") or 0) >= 2:
                        record["confidence"] = max(0, int(record.get("confidence") or 55) - 15)
                    reason = _ease_reason(ai_state, record, attacker)
                    if reason:
                        record["open"] = False
                        record["eased_week"] = int(week)
                        eased_now = True
                        story = f"fight|{key}"
                        closed = _close_cause(world, story, week, reason)
                        opened = int(closed["week"]) if closed is not None else int(record.get("opened_week") or 0)
                        if opened:
                            text = f"{_banner(attacker)} eased the {_city_label(city)} fight in week {int(week)}. It opened in week {opened}. {reason}"
                        else:
                            text = f"{_banner(attacker)} eased the {_city_label(city)} fight in week {int(week)}. {reason}"
                        _rivalry_note(world, week, key, "eased", text)
                        if reason == "The gain disappeared.":
                            book_est = world.setdefault("estimates", {}).setdefault(attacker, {}).setdefault(city, {})
                            book_est["unpaid"] = True
                        if reason == "The shelf ran short.":
                            _schedule_return(world, week, city, attacker, record)
                elif int(record.get("fatigue") or 0) > 0:
                    record["fatigue"] = max(0, int(record["fatigue"]) - FATIGUE_DECAY)
                tired = eased_now or (int(record.get("eased_week") or 0) > 0 and int(record.get("fatigue") or 0) > 0)
                if not tired and not record.get("open") and overlap >= OVERLAP_MIN:
                    choice = _choose_attack(ai_state, world, city, left, right, record, week)
                    if choice is not None:
                        attacker_id, target_id, aisle = choice
                        record["open"] = True
                        record["attacker"] = attacker_id
                        record["target"] = target_id
                        record["aisle"] = aisle
                        record["age"] = 0
                        record["confidence"] = 60
                        record["opened_week"] = int(week)
                        record["value_before"] = {ident: int(points) for ident, points in shares.items()}
                        attacks = list(record.get("attacks") or [])
                        attacks.append({"week": int(week), "by": attacker_id, "aisle": aisle, "gain": None})
                        record["attacks"] = attacks[-8:]
                        _start_cause(
                            world,
                            week,
                            "fight",
                            city,
                            [attacker_id, target_id],
                            aisle,
                            f"fight|{key}",
                            int(shares.get(attacker_id, 0)),
                        )
                        _rivalry_note(
                            world,
                            week,
                            key,
                            "opened",
                            f"{_banner(attacker_id)} opened a {aisle} fight with {_banner(target_id)} in {_city_label(city)}. Their shoppers overlap, and {_banner(target_id)} looked vulnerable.",
                        )
                felt = str(record.get("attacker") or "")
                if shares and felt:
                    record["share"] = {felt: int(shares.get(felt, 0))}
                guess = ((world.get("estimates") or {}).get(felt or "") or {}).get(city) or {}
                if not guess:
                    for ident in (left, right):
                        guess = ((world.get("estimates") or {}).get(ident) or {}).get(city) or {}
                        if guess:
                            break
                if guess.get("share"):
                    record["estimate_share"] = {key: int(value) for key, value in guess["share"].items()}
                book[key] = record
    for key in list(book):
        if key not in seen and book[key].get("open"):
            book[key]["open"] = False


def _ease_reason(ai_state, record: dict, attacker: str) -> str:
    city = str(record.get("city") or "")
    if attacker != "player" and _short_shelf(ai_state, attacker, city):
        return "The shelf ran short."
    chain = ai_state.chains.get(attacker)
    if chain is not None and int(chain.cash) < CASH_FLOOR:
        return "The cash ran thin."
    if int(record.get("fatigue") or 0) >= FATIGUE_STOP:
        return "The fight wore out."
    if int(record.get("confidence") or 100) < CONFIDENCE_STOP:
        return "They are no longer sure the fight is worth it."
    if int(record.get("age") or 0) >= 2 and int(record.get("last_gain") or 0) <= 0:
        return "The gain disappeared."
    return ""


def _choose_attack(ai_state, world: dict, city: str, left: str, right: str, record: dict, week: int):
    """Aggressive chains open when the read is strong. A thin read is a watch."""
    if int(record.get("fatigue") or 0) >= FATIGUE_STOP:
        return None
    doctrine = world.get("doctrine") or {}
    present = _banners(ai_state, world, city)
    for attacker in (left, right):
        if doctrine.get(attacker) != "aggressive":
            continue
        chain = ai_state.chains.get(attacker)
        if chain is None or int(chain.cash) < CASH_FLOOR or _short_shelf(ai_state, attacker, city):
            continue
        other = right if attacker == left else left
        other_kind = doctrine.get(other, "")
        premium_here = any(doctrine.get(ident) == "premium" for ident in present if ident != attacker)
        player_here = "player" in present and _player_vulnerable(world, city, attacker)
        if other_kind == "endurance" and (premium_here or player_here or not _share_fell(world, city, other, record, attacker)):
            continue
        sure = _belief_of(world, attacker, city) >= BELIEF_SPEND
        if other_kind == "premium" or (other == "player" and _player_vulnerable(world, city, attacker)):
            if not sure:
                _watch(world, week, attacker, city)
                return None
            return attacker, other, "household"
        if other_kind == "endurance" and _share_fell(world, city, other, record, attacker):
            if not sure:
                _watch(world, week, attacker, city)
                return None
            return attacker, other, "household"
    return None


def _belief_of(world: dict, chain_id: str, city: str) -> int:
    est = ((world.get("estimates") or {}).get(chain_id) or {}).get(city) or {}
    return int(est.get("belief") or 0)


def _player_vulnerable(world: dict, city: str, attacker: str) -> bool:
    est = ((world.get("estimates") or {}).get(attacker) or {}).get(city) or {}
    return bool(est.get("player_cut"))


def _share_fell(world: dict, city: str, chain_id: str, record: dict, attacker: str) -> bool:
    est = ((world.get("estimates") or {}).get(attacker) or {}).get(city) or {}
    shares = est.get("share") or {}
    if chain_id not in shares:
        return False
    current = int(shares[chain_id])
    previous = int((record.get("estimate_share") or {}).get(chain_id, current))
    return previous - current >= SWITCH_POINTS


def response_actions(ai_state, world: dict, week: int):
    """Act only on a rivalry record that opened or eased this week."""
    from open_late.ai.models import Action, ActorRef

    review_rivalry(ai_state, world, week)
    actions = []
    doctrine = world.get("doctrine") or {}
    notes = [row for row in world.get("rivalry_notes") or [] if int(row.get("week") or 0) == int(week)]
    book = world.get("rivalry") or {}

    def actor(chain_id: str) -> ActorRef:
        return ActorRef(kind="ceo", id=f"ceo:{chain_id}")

    eased_attackers: set[str] = set()
    for note in notes:
        if note.get("kind") != "eased":
            continue
        record = book.get(note.get("key") or "")
        if not record:
            continue
        attacker = str(record.get("attacker") or "")
        if doctrine.get(attacker) != "aggressive" or attacker in eased_attackers:
            continue
        eased_attackers.add(attacker)
        city = str(record.get("city") or "")
        target = str(record.get("target") or "")
        if doctrine.get(target) == "premium":
            _close_exclusive(world, city, target)
        actions.append(Action(
            actor=actor(attacker),
            kind="set_chain_price_index",
            args={"delta": 1},
            reason="The fight eased, so the staple price came back a point.",
        ))
        actions.append(Action(
            actor=actor(attacker),
            kind="promo",
            args={"city": city, "dept": "household", "depth": 0, "weeks": 1},
            reason="The household push stopped.",
        ))
    for note in notes:
        if note.get("kind") != "opened":
            continue
        record = book.get(note.get("key") or "")
        if not record or not record.get("open"):
            continue
        attacker = str(record.get("attacker") or "")
        target = str(record.get("target") or "")
        city = str(record.get("city") or "")
        if attacker in eased_attackers:
            continue
        if doctrine.get(attacker) == "aggressive":
            actions.append(Action(
                actor=actor(attacker),
                kind="promo",
                args={"city": city, "dept": "household", "depth": 15, "weeks": 3},
                reason="Value seekers left. Household staples are the reply.",
            ))
            actions.append(Action(
                actor=actor(attacker),
                kind="copy_best_seller",
                args={"city": city, "dept": "household"},
                reason="More of the household aisle is at eye level.",
            ))
        if doctrine.get(target) == "premium":
            _place_exclusive(world, week, city, target)
        if doctrine.get(target) == "endurance" and int(record.get("fatigue") or 0) < 40:
            chain = ai_state.chains.get(target)
            if chain is not None and int(chain.cash) >= CASH_FLOOR:
                actions.append(Action(
                    actor=actor(target),
                    kind="set_chain_price_index",
                    args={"delta": -1},
                    reason="Matched the visible staple only.",
                ))
    actions.extend(customer_actions(ai_state, world, week))
    return actions


def customer_actions(ai_state, world: dict, week: int):
    """A doctrine reads household switches. No signals, no extra move."""
    from open_late.ai.models import Action, ActorRef

    signals = world.get("customer_signals") or {}
    if int(signals.get("week") or -1) != int(week):
        return []
    doctrine = world.get("doctrine") or {}
    cities = list((world.get("shoppers") or {}).keys())
    city = str(cities[0]) if cities else "evansville"
    actions = []
    seen: set[str] = set()
    for row in signals.get("switches") or []:
        former = str(row.get("former") or "")
        if not former or former == "player" or former in seen:
            continue
        kind = doctrine.get(former, "")
        if not kind:
            continue
        seen.add(former)
        cause = str(row.get("cause") or "a household move").replace("_", " ")
        who = ActorRef(kind="ceo", id=f"ceo:{former}")
        if kind == "aggressive":
            actions.append(Action(
                actor=who,
                kind="promo",
                args={"city": city, "dept": "household", "depth": 10, "weeks": 2},
                reason=f"Households left after {cause}.",
            ))
        elif kind == "premium":
            _rivalry_note(
                world,
                week,
                f"customers:{former}",
                "customers",
                f"{_banner(former)} held the staple price after households left. The record cites {cause}.",
            )
        elif kind == "endurance":
            chain = ai_state.chains.get(former) if ai_state is not None else None
            if chain is not None and int(chain.cash) >= CASH_FLOOR:
                actions.append(Action(
                    actor=who,
                    kind="set_chain_price_index",
                    args={"delta": -1},
                    reason="Matched one visible point after households left.",
                ))
    return actions


def gather_observations(state, ai_state, world: dict) -> list[dict]:
    """What each banner's shoppers could see this week."""
    from open_late.economy import city_of, store_ids_for

    household = shelf_ratio(state, "household")
    base = int((world.get("shelf_base") or {}).get("household") or household)
    if "shelf_base" not in world:
        remember_shelf_base(state, world)
        base = int(world["shelf_base"]["household"])
        household_cut = False
    else:
        household_cut = household <= base - 30
    price = cost = 0
    for product in state.products.values():
        price += int(product.price)
        cost += int(product.cost)
    ratio = (price / cost) if cost else 1.0
    basket_base = float(world.get("price_base") or 0.0) or ratio
    basket = int(round(100.0 * ratio / basket_base))
    seen = world.setdefault("seen_price", {})
    lost = int(getattr(getattr(state, "last_report", None), "lost_stockout", 0) or 0)
    rows: list[dict] = []
    seen_cities: set[str] = set()
    for store_id in store_ids_for(state):
        city = city_of(state, store_id)
        if city in seen_cities:
            continue
        seen_cities.add(city)
        key = f"player:{city}"
        prev = int(seen.get(key, basket))
        rows.append({
            "city": city,
            "chain_id": "player",
            "price_index": basket,
            "prev_price": prev,
            "promo": 0,
            "stockouts": 1 if lost > 0 else 0,
            "doctrine": "",
            "household_cut": household_cut,
        })
        seen[key] = basket
    doctrine = world.get("doctrine") or {}
    for chain_id, chain in ai_state.chains.items():
        for store in chain.stores:
            if store.status != "open":
                continue
            key = f"{chain_id}:{store.city}"
            price_index = int(store.price_index)
            prev = int(seen.get(key, price_index))
            rows.append({
                "city": store.city,
                "chain_id": chain_id,
                "price_index": price_index,
                "prev_price": prev,
                "promo": int(store.promo_depth),
                "stockouts": int(store.stockouts),
                "doctrine": doctrine.get(chain_id, ""),
                "household_cut": False,
            })
            seen[key] = price_index
    return rows


def cohort_lines(world: dict, cities: list[str]) -> list[str]:
    """One readable share line per city the player actually trades in."""
    lines = []
    shoppers = world.get("shoppers") or {}
    for city in cities:
        book = shoppers.get(city) or {}
        shares = book.get("value_seekers") or {}
        if len(shares) < 2:
            continue
        parts = []
        for chain_id, points in sorted(shares.items(), key=lambda item: -int(item[1])):
            parts.append(f"{_banner(chain_id)} {int(points) // 10}%")
        sentence = f"{_city_label(city)} value seekers: " + ", ".join(parts) + "."
        cause = _open_cause(world, f"household|{city}|value_seekers")
        if cause is not None:
            sentence += f" They moved in week {int(cause['week'])} after the household cut."
        lines.append(sentence)
    return lines
