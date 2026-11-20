"""Rival AI wiring: three supercenter chains in place of the single Northline rival.

Integration only. Every rival decision comes from Brandon's minds in
``open_late.ai`` (``RetailAI.weekly`` / ``shopper_card`` / ``on_event``); the
moves are applied with the AI repo's own applier (``open_late.standin``
``apply_actions``). This module:

* builds the minds' weekly ``Snapshot`` from the real game (the live factor
  card, which carries the Phase 1 macro layer, the Phase 2 Fed rate and wage
  levels, city markets, the player's doors, prices and sales);
* posts the rivals' Sunday books with debt service charged through
  ``fed.rival_interest_due`` (rival debt pays interest at the policy rate);
* writes the rivals' local pressure back onto the hooks Northline used
  (factors 80/81/84, ``state.rival``, ``state.flags.competitor``) so the
  existing demand and sale-chance code feels them;
* exposes rival stores and moves for the map, news and inbox;
* packs the AI state into the save (delta vs a deterministic baseline, then
  zlib + base64).

AI off (the default for ``new_game``, every economy-off game, and every save
older than version 5) touches nothing: ``state.rival_ai`` stays ``None``, it is
not written to the save, and no RNG is drawn. No network, no outside AI.
"""

from __future__ import annotations

import base64
import json
import zlib
from typing import Any

from open_late.models import GameState, RivalAIBlock

RIVAL_AI_VERSION = 1
SAVE_VERSION_AI = 5
FEED_KEEP = 60
CHAINS_DIR = "retail_rivals_brand/chains"

_DEFAULT_ON = False
_PROVIDER = None


# --- switches -----------------------------------------------------------------

def set_default_enabled(flag: bool) -> None:
    """The playable launcher turns this on; library/test callers keep it off."""
    global _DEFAULT_ON
    _DEFAULT_ON = bool(flag)


def default_enabled(difficulty: str | None) -> bool:
    return _DEFAULT_ON and (difficulty or "off") != "off"


def provider():
    global _PROVIDER
    if _PROVIDER is None:
        from open_late.ai import RetailAI

        _PROVIDER = RetailAI()
    return _PROVIDER


def is_on(state: GameState) -> bool:
    block = getattr(state, "rival_ai", None)
    if block is None or not block.enabled:
        return False
    return str(getattr(state.economy, "difficulty", "off") or "off") != "off"


# --- live state + packing -------------------------------------------------------

def _empty_world() -> dict[str, Any]:
    return {
        "permits": [],
        "war_until": {},
        "wars": {},
        "accounts": {},
        "feed": [],
        "player_cities": [],
        "player_index": {},
        "price_base": 0.0,
        "interest_paid": {},
        "last_week": 0,
        "town_rules": {},
        "town_walk": {},
        "town_applied": {},
    }


def _canonical_snapshot(seed: int, chain_id: str, difficulty: str, day: int):
    from open_late.ai.constants import CITIES, week_of
    from open_late.ai.costs import city_opening_cost, game_factors
    from open_late.ai.snapshot import Snapshot

    factors = game_factors()
    return Snapshot(
        seed=int(seed),
        day=int(day),
        week=week_of(int(day)),
        difficulty=difficulty,
        ai_enabled=True,
        player_chain_id=chain_id,
        opening_cost=city_opening_cost("seattle", factors),
        factors=factors,
        public={
            "player_price_index": {city: 100 for city in CITIES},
            "player_stores": [],
            "permits": [],
            "war_until": {},
            "campaigns": [],
            "news_ids": [],
        },
    )


def _baseline_dump(init: dict[str, Any]) -> dict[str, Any]:
    snap = _canonical_snapshot(init["seed"], init["chain_id"], init["difficulty"], init["day"])
    return provider().init_world(snap).model_dump(mode="json")


def pack_block(block: RivalAIBlock) -> str:
    live = block._live
    ai_dump = live["ai"].model_dump(mode="json")
    base = _baseline_dump(block.init)
    delta = {key: value for key, value in ai_dump.items() if base.get(key) != value}
    return payload_to_packed({"ai": delta, "world": live["world"]})


def payload_to_packed(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.b64encode(zlib.compress(raw, 9)).decode("ascii")


def packed_to_payload(packed: str) -> dict[str, Any]:
    return json.loads(zlib.decompress(base64.b64decode(packed)).decode("utf-8"))


def _unpack(block: RivalAIBlock) -> dict[str, Any]:
    from open_late.ai.models import AIState

    base = _baseline_dump(block.init)
    payload: dict[str, Any] = {"ai": {}, "world": _empty_world()}
    if block.packed:
        payload = packed_to_payload(block.packed)
    merged = dict(base)
    merged.update(payload.get("ai") or {})
    world = _empty_world()
    world.update(payload.get("world") or {})
    return {"ai": AIState.model_validate(merged), "world": world}


def live(state: GameState) -> dict[str, Any] | None:
    block = getattr(state, "rival_ai", None)
    if block is None:
        return None
    if block._live is None:
        block._live = _unpack(block)
    return block._live


def save_size_bytes(state: GameState) -> int:
    """Bytes SaveStore writes for this state (compressed when the AI is on)."""
    from open_late.store import encoded_size

    return encoded_size(state)


def ai_block_bytes(state: GameState) -> int:
    block = getattr(state, "rival_ai", None)
    if block is None:
        return 0
    return len(block.model_dump_json().encode("utf-8"))


# --- enabling -------------------------------------------------------------------

def enable(state: GameState) -> bool:
    """Start the rival minds on this game (new game or an old save, from today)."""
    difficulty = str(getattr(state.economy, "difficulty", "off") or "off")
    if difficulty == "off":
        return False
    if getattr(state, "rival_ai", None) is not None:
        state.rival_ai.enabled = True
        return True
    init = {"seed": int(state.seed), "chain_id": str(state.chain_id or "megamart"), "difficulty": difficulty, "day": int(state.day)}
    block = RivalAIBlock(version=RIVAL_AI_VERSION, enabled=True, init=init)
    snap = _canonical_snapshot(init["seed"], init["chain_id"], difficulty, init["day"])
    ai_state = provider().init_world(snap)
    from open_late.living import remember_shelf_base, roster_sentence, seat_market

    doctrine = seat_market(ai_state, snap)
    world = _empty_world()
    world["doctrine"] = doctrine
    world["ledger"] = []
    world["briefing"] = []
    world["cohort_memory"] = []
    world["shoppers"] = {}
    world["memory"] = {}
    world["switches"] = []
    remember_shelf_base(state, world)
    world["price_base"] = _price_ratio(state)
    world["accounts"] = _accounts(ai_state)
    world["last_week"] = snap.week - 1
    block._live = {"ai": ai_state, "world": world}
    state.rival_ai = block
    state.save_version = max(int(state.save_version or 0), SAVE_VERSION_AI)
    _feed(world, state.day, snap.week, "", "roster", "", roster_sentence(doctrine))
    _overlay(state, ai_state, world)
    return True


def disable(state: GameState) -> None:
    if getattr(state, "rival_ai", None) is not None:
        state.rival_ai.enabled = False


def _accounts(ai_state) -> dict[str, list[dict]]:
    from open_late.ai.constants import SUPPLIERS

    buyers = [{"buyer_id": "player", "relationship": 42, "volume": 200, "terms": "cash"}]
    for chain_id in sorted(ai_state.chains):
        buyers.append({"buyer_id": chain_id, "relationship": 42, "volume": 200, "terms": "cash"})
    return {sid: [dict(row) for row in buyers] for sid, _name, _dept in SUPPLIERS if sid != "labelco"}


# --- reading the game -----------------------------------------------------------

def _price_ratio(state: GameState) -> float:
    price = cost = 0
    for product in state.products.values():
        price += int(product.price)
        cost += int(product.cost)
    return (price / cost) if cost else 1.0


def _player_index(state: GameState, world: dict) -> int:
    base = float(world.get("price_base") or 0.0) or _price_ratio(state)
    return int(round(100.0 * _price_ratio(state) / base))


def _player_doors(state: GameState) -> list[tuple[str, str]]:
    from open_late.economy import city_of, store_ids_for

    return [(store_id, city_of(state, store_id)) for store_id in store_ids_for(state)]


def _player_focus(state: GameState) -> str:
    """'' with Lite shelves on: the shelves already lift departments in-store, so the minds'
    focus-department boost (ai/shoppers._dept_mult) stays neutral for player doors."""
    return "" if (getattr(state, "shelves", None) or {}).get("on") else "grocery"


def _snapshot(state: GameState, ai_state, world: dict, week: int):
    from open_late.ai.constants import CITIES
    from open_late.ai.costs import city_opening_cost
    from open_late.ai.snapshot import Snapshot
    from open_late.hq import store_pnl

    factors = {key: int(round(value)) for key, value in state.economy.values.items()}
    index = _player_index(state, world)
    doors = _player_doors(state)
    stores, sales = [], {}
    for store_id, city in doors:
        stores.append({"id": store_id, "city": city, "opened_on": 1, "distance_band": 1, "trust": int(state.reputation_respectable),
                       "focus": _player_focus(state), "promo": 0, "stockouts": 0})
        try:
            sales[store_id] = int(store_pnl(state, store_id, days=7).get("sales", 0))
        except Exception:  # a door with no trading days yet
            sales[store_id] = 0
    return Snapshot(
        seed=int(state.seed),
        day=int(state.day),
        week=int(week),
        difficulty=str(state.economy.difficulty),
        ai_enabled=True,
        player_chain_id=str(state.chain_id or "megamart"),
        private_label=bool(getattr(state.flags, "private_label", False)),
        opening_cost=city_opening_cost("seattle", factors),
        factors=factors,
        public={
            "player_price_index": {city: index for city in CITIES},
            "player_weekly_sales": sales,
            "player_store_cities": {store_id: city for store_id, city in doors},
            "player_stores": stores,
            "campaigns": [],
            "permits": [dict(row) for row in world["permits"]],
            "news_ids": [],
            "war_until": dict(world["war_until"]),
            "macro": _macro_view(state),
        },
        wars=dict(world["wars"]),
        accounts={key: [dict(row) for row in rows] for key, rows in world["accounts"].items()},
        northline={},
        hidden={"player_cash": int(state.cash), "player_weekly_net": 0, "stockouts": [], "orders": len(state.orders)},
        ai=ai_state,
    )


def _macro_view(state: GameState) -> dict[str, Any]:
    """Phase 1-2 numbers in plain form (the factor card already carries them)."""
    macro = getattr(state.economy, "macro", None) or {}
    fed = macro.get("fed") or {}
    labor = macro.get("labor") or {}
    out: dict[str, Any] = {}
    for key in ("inflation", "unemployment", "output_gap", "gdp_growth", "expected_inflation"):
        if key in macro:
            out[key] = round(float(macro[key]), 5)
    if fed:
        out["policy_rate"] = round(float(fed.get("policy_rate", 0.0)), 5)
    if labor:
        out["wage_level"] = round(float(labor.get("wage_level", 1.0)), 5)
    return out


# --- the Sunday step --------------------------------------------------------------

def sunday(state: GameState, game_week: int) -> None:
    """Called from economy_tick after the week's factors resolve, before the card bakes."""
    if not is_on(state):
        return
    from open_late import ai_bridge
    from open_late.ai.constants import week_of
    from open_late.ai.models import GameEvent
    from open_late.fed import loan_rate_index
    from open_late.standin.sim import apply_actions

    data = live(state)
    ai_state, world = data["ai"], data["world"]
    week = week_of(int(state.day))
    if week <= int(world.get("last_week", 0)):
        return  # one AI week per game week
    snap = _snapshot(state, ai_state, world, week)
    clean = dict(snap.factors)
    snap.factors = _town_view(clean, world)
    shown = dict(snap.factors)
    mind = provider()
    # What the rivals saw the player do since last Sunday.
    index = int(snap.public["player_price_index"].get("evansville", 100))
    cities = sorted({city for _sid, city in _player_doors(state)})
    from open_late.living import note_player_price

    for city in cities:
        previous = int(world["player_index"].get(city, index))
        if previous != index:
            mind.on_event(snap, GameEvent(name="PlayerBasketIndex", day=snap.day, week=week, city=city, payload={"index": index}))
            note_player_price(world, week, city, previous, index)
        world["player_index"][city] = index
    for city in cities:
        if world["player_cities"] and city not in world["player_cities"]:
            mind.on_event(snap, GameEvent(name="PlayerStoreOpened", day=snap.day, week=week, city=city, payload={}))
    world["player_cities"] = cities

    ai_bridge.set_rate_index(loan_rate_index(state))
    try:
        from open_late.living import (
            gather_observations,
            gate_actions,
            observe_shoppers,
            response_actions,
            scale_rival_traffic,
            pull_supply,
            strain_supply,
            write_week,
        )

        observe_shoppers(world, week, gather_observations(state, ai_state, world))
        actions = mind.weekly(snap)
        actions, held = gate_actions(actions, ai_state, world)
        actions.extend(response_actions(ai_state, world, week))
        results = apply_actions(snap, actions)
        strain_supply(ai_state, world)
        pull_supply(ai_state, world, week)
        write_week(world, week, results, held, ai_state)
        from open_late.shopperlife.signals import note_customers

        note_customers(world, getattr(state, "shopperlife", None), week)
        mind.shopper_card(snap)
        scale_rival_traffic(snap.ai.shopper_card if snap.ai is not None else None, world, ai_state)
        opened = _settle(state, snap)
    finally:
        ai_bridge.set_rate_index(1.0)
    _capture_town(world, shown, snap.factors)
    world["permits"] = [dict(row) for row in snap.public.get("permits") or []]
    world["war_until"] = {str(k): int(v) for k, v in (snap.public.get("war_until") or {}).items()}
    world["wars"] = {str(k): int(v) for k, v in snap.wars.items()}
    world["accounts"] = snap.accounts
    world["last_week"] = week
    _report(state, world, week, results, opened)
    _overlay(state, ai_state, world)
    _apply_town_and_suppliers(state, ai_state, world, clean)
    _cap_inbox(state)


def _settle(state: GameState, snap) -> list[tuple[str, str, str]]:
    """Open finished builds and post one week of integer books (the AI repo's settle,
    with debt service through fed.rival_interest_due)."""
    from open_late.ai.books import loan_service
    from open_late.ai.forecast import store_pnl
    from open_late.ai.models import ChainPnL
    from open_late.fed import rival_interest_due
    from open_late.standin.sim import _intensity

    ai_state = snap.ai
    card = ai_state.shopper_card
    world = live(state)["world"]
    opened: list[tuple[str, str, str]] = []
    for chain in ai_state.chains.values():
        for store in chain.stores:
            if store.status == "building" and store.opened_on <= snap.day:
                store.status = "open"
                opened.append((chain.chain_id, store.city, store.id))
        person = ai_state.personalities.get(chain.personality_id)
        if person is None or chain.status == "bankrupt":
            continue
        open_stores = [store for store in chain.stores if store.status == "open"]
        if not open_stores:
            chain.last_pnl = ChainPnL(week=snap.week)
            continue
        sales = cogs = opex = net = 0
        if chain.cost_cut_until_week and snap.week > chain.cost_cut_until_week:
            chain.cost_cut_pct = 0
        cut = chain.cost_cut_pct if snap.week <= chain.cost_cut_until_week else 0
        for store in open_stores:
            if store.promo_until_week and snap.week > store.promo_until_week:
                store.promo_depth = 0
            mult = card.visit_mult.get(store.id, 1000) if card is not None else 1000
            pnl = store_pnl(
                store,
                gross_margin_bps=person.gross_margin_bps,
                opex_bps=person.opex_bps,
                visit_mult=mult,
                war_intensity=_intensity(snap, store.city),
                cost_cut_pct=cut,
                debt_share=0,
                factors=snap.factors,
                shelf_index=person.price_index,
            )
            store.weekly_sales = pnl.sales
            sales += pnl.sales
            cogs += pnl.cogs
            opex += pnl.opex
            net += pnl.net
        chain.cash += net
        chain.ebitda_trail.append(net)
        chain.ebitda_trail = chain.ebitda_trail[-52:]
        # Debt service at the policy rate (Phase 2 Fed hook).
        interest = rival_interest_due(state, max(0, chain.revolver_debt))
        principal_paid = 0
        for loan in chain.build_loans:
            _base_interest, step = loan_service(loan)
            if loan.principal <= 0:
                continue
            interest += rival_interest_due(state, loan.principal, weekly_rate=loan.rate_bps / 10_000 / 52)
            loan.principal -= step
            principal_paid += step
        chain.build_loans = [loan for loan in chain.build_loans if loan.principal > 0]
        service = interest + principal_paid
        chain.cash -= service
        chain.refresh_debt()
        paid = world.setdefault("interest_paid", {})
        paid[chain.chain_id] = int(paid.get(chain.chain_id, 0)) + int(interest)
        chain.last_pnl = ChainPnL(week=snap.week, sales=sales, cogs=cogs, opex=opex + service, net=net - service)
    return opened


# --- writing back to the game ------------------------------------------------------

_BLOCKS = {1: 3, 2: 6, 3: 10}


def _city_rivals(ai_state, city: str) -> list[tuple[str, Any]]:
    rows = []
    for chain_id in sorted(ai_state.chains):
        chain = ai_state.chains[chain_id]
        if chain.status == "bankrupt":
            continue
        for store in chain.stores:
            if store.status == "open" and store.city == city:
                rows.append((chain_id, store))
    return rows


def _heat(rows, player_index: int, week: int) -> int:
    """Local pressure on Northline's 0-100 heat scale (game-side mapping, not a decision)."""
    if not rows:
        return 0
    heat = 34 + 8 * (len(rows) - 1)
    if any(store.promo_depth > 0 and store.promo_until_week >= week for _cid, store in rows):
        heat += 6
    cheapest = min(int(store.price_index) for _cid, store in rows)
    heat += max(0, player_index - cheapest) // 2
    return max(0, min(100, heat))


def _overlay(state: GameState, ai_state, world: dict) -> None:
    from open_late.ai.constants import week_of
    from open_late.economy import _clamp, _key

    eco = state.economy
    week = week_of(int(state.day))
    index = _player_index(state, world)
    home_rows = None
    home_heat = 0
    for n, (store_id, city) in enumerate(_player_doors(state)):
        rows = _city_rivals(ai_state, city)
        heat = _heat(rows, index, week)
        eco.values[_key(81, store_id)] = heat
        war = int(world["wars"].get(city, 0)) if week <= int(world["war_until"].get(city, 0)) else 0
        if rows:
            price = min(int(store.price_index) for _cid, store in rows)
            eco.values[_key(80, store_id)] = _clamp(price - war, 86, 120)
        eco.values[_key(84, city)] = war
        if n == 0:
            home_rows, home_heat = rows, heat
    state.flags.competitor = int(home_heat)
    rival = state.rival
    if home_rows:
        cid, store = max(home_rows, key=lambda item: (int(item[1].weekly_sales), item[0]))
        rival.name = _chain_name(cid)
        rival.price_index = int(_clamp(int(store.price_index), 86, 120))
        rival.focus = str(store.focus_dept or "grocery")
        rival.blocks_away = _BLOCKS.get(int(store.distance_band), 6)
        rival.note = f"{rival.name} runs a supercenter in town."
    else:
        rival.name = "No supercenter rival in town"
        rival.note = "The rival chains have no door in your city yet."


def _chain_name(chain_id: str) -> str:
    from open_late.ai.constants import chain_name

    return chain_name(chain_id)


def _city_name(city: str) -> str:
    from open_late.ai.constants import city_name

    return city_name(city)


def _feed(world: dict, day: int, week: int, chain_id: str, kind: str, city: str, text: str) -> None:
    feed = world.setdefault("feed", [])
    feed.append({"day": int(day), "week": int(week), "chain_id": chain_id, "kind": kind, "city": city, "text": text[:200]})
    del feed[:-FEED_KEEP]


_INBOX_KINDS = {"open_store", "store_opened", "close_store", "bankrupt", "reenter", "start_price_war"}


def _report(state: GameState, world: dict, week: int, results, opened) -> None:
    from open_late.inbox import add

    player_cities = set(world.get("player_cities") or [])
    for result in results:
        action = result.action
        if not result.accepted or action.actor.kind != "ceo":
            continue
        if action.kind in {"do_nothing", "hold"}:
            continue
        cid = action.actor.id.split(":", 1)[1]
        city = str(action.args.get("city", ""))
        name = _chain_name(cid)
        kind = action.kind
        if kind == "open_store":
            text = f"{name} filed for a new supercenter in {_city_name(city)}."
        elif kind == "close_store":
            kind = "bankrupt" if result.note == "bankrupt" else kind
            text = f"{name} closed a store." if kind == "close_store" else f"{name} closed its last door and went bankrupt."
        elif kind == "start_price_war":
            text = f"{name} started a price war in {_city_name(city)}."
        elif kind == "reenter":
            text = f"{name} is back with a new door in {_city_name(city)}."
        else:
            text = f"{name}: {action.reason}" if action.reason else f"{name} made a {kind.replace('_', ' ')} move."
        _feed(world, state.day, week, cid, kind, city, text)
        if kind in _INBOX_KINDS and (kind != "start_price_war" or city in player_cities):
            body = text if not action.reason else f"{text} {action.reason}"
            add(state, kind="rival", title=f"Rival move: {name}", body=body[:400])
    for cid, city, _store_id in opened:
        text = f"{_chain_name(cid)} opened its {_city_name(city)} supercenter."
        _feed(world, state.day, week, cid, "store_opened", city, text)
        add(state, kind="rival", title=f"Rival opening: {_chain_name(cid)}", body=text)


# --- UI-facing snapshots (read only) -------------------------------------------------

def rival_snapshot(state: GameState) -> dict[str, Any]:
    """Public rival view for the map, news and HQ pages. Empty when AI is off.

    Only what a player could see: chain, logo, stores (city, status, opened
    day, price index, focus), weekly sales band, last move. No cash or debt.
    """
    data = live(state) if is_on(state) else None
    if data is None:
        return {"enabled": False, "chains": [], "stores": [], "feed": []}
    from open_late.ai.constants import chain_logo
    from open_late.living import cohort_lines

    ai_state, world = data["ai"], data["world"]
    player_cities: list[str] = []
    for _store_id, city in _player_doors(state):
        if city not in player_cities:
            player_cities.append(city)
    chains, stores = [], []
    for chain_id in ai_state.roster:
        chain = ai_state.chains.get(chain_id)
        if chain is None:
            continue
        open_count = sum(1 for store in chain.stores if store.status == "open")
        building = sum(1 for store in chain.stores if store.status == "building")
        last = next((row for row in reversed(world.get("feed") or []) if row.get("chain_id") == chain_id), None)
        posted = sum(int(store.weekly_sales) for store in chain.stores if store.status == "open")
        low, high = _sales_band(posted)
        chains.append({
            "id": chain_id,
            "name": _chain_name(chain_id),
            "logo": f"{CHAINS_DIR}/{chain_logo(chain_id)}",
            "status": chain.status,
            "doctrine": str((world.get("doctrine") or {}).get(chain_id) or ""),
            "price_index": int(chain.price_index),
            "open_stores": open_count,
            "building": building,
            "sales_low": low,
            "sales_high": high,
            "last_move": (last or {}).get("text", ""),
        })
        for store in chain.stores:
            if store.status == "closed":
                continue
            stores.append({
                "id": store.id,
                "chain_id": chain_id,
                "name": _chain_name(chain_id),
                "logo": f"{CHAINS_DIR}/{chain_logo(chain_id)}",
                "city": store.city,
                "city_name": _city_name(store.city),
                "status": store.status,
                "opens_day": int(store.opened_on),
                "price_index": int(store.price_index),
                "focus": store.focus_dept,
                "promo": int(store.promo_depth),
            })
    return {
        "enabled": True,
        "chains": chains,
        "stores": stores,
        "feed": list(world.get("feed") or [])[-20:],
        "briefing": list(world.get("briefing") or []),
        "cohorts": cohort_lines(world, player_cities),
    }


def _sales_band(sales: int) -> tuple[int, int]:
    """A public range around a week's sales. The exact figure stays off the page."""
    sales = int(sales)
    if sales <= 0:
        return 0, 0
    low = sales * 85 // 100
    high = sales * 115 // 100
    step = 50_000 if sales < 1_000_000 else 100_000
    low = max(step, (low // step) * step)
    high = ((high + step - 1) // step) * step
    if high <= low:
        high = low + step
    return low, high


def market_share(state: GameState, snap: dict[str, Any] | None = None) -> dict[str, Any]:
    """Your last week against the chains' public bands. No cash, no debt."""
    if snap is None:
        snap = rival_snapshot(state)
    player = _player_week_sales(state)
    if not snap.get("enabled"):
        return {"enabled": False, "player": player, "low": 0, "high": 0, "share": None}
    low = high = 0
    for chain in snap.get("chains") or []:
        low += int(chain.get("sales_low") or 0)
        high += int(chain.get("sales_high") or 0)
    middle = (low + high) // 2
    share = (player / middle) if middle else None
    return {"enabled": True, "player": player, "low": low, "high": high, "share": share}


def _player_week_sales(state: GameState) -> int:
    rows = list(state.history or [])
    report = state.last_report
    if report.day and (not rows or rows[-1].day != report.day):
        rows.append(report)
    recent = [row for row in rows if int(row.day) > int(state.day) - 7]
    if not recent and report.day:
        recent = [report]
    return sum(int(getattr(row, "revenue", 0) or 0) for row in recent[-7:])


def rival_news(state: GameState, limit: int = 20) -> list[dict[str, Any]]:
    """Newest-first rival feed rows for a news ticker or headline strip."""
    return list(reversed(rival_snapshot(state)["feed"]))[:limit]


# --- F1: player store cost parity (AI on only) ------------------------------------------

def player_opening_base(state: GameState, market_id: str, default: int) -> int:
    """Base supercenter cost for a player door when the AI is on (same table as rivals).

    The home market (default 0) stays owned. AI off returns the old shop-sized cost.
    """
    if default <= 0 or not is_on(state):
        return default
    from open_late.store_costs import SUPERCENTER_BUILD_COST

    return int(SUPERCENTER_BUILD_COST.get(market_id, default))


def player_opening_cost(state: GameState, market_id: str) -> int:
    """What open_market will charge today (base x factor 95 clamp). For the UI."""
    from open_late.corporate import MARKETS
    from open_late.economy_e3 import opening_cost_mult

    market = MARKETS.get(market_id)
    if market is None:
        return 0
    base = player_opening_base(state, market_id, market.opening_cost)
    return int(round(base * opening_cost_mult(state, market_id)))


# --- F1: the minds' town and supplier moves reach the player's economy ---------------------
#
# The minds' town rules and supplier quotes become small, bounded offsets on the
# game's factor card for one week at a time. Offsets are added after the week's
# walks/links (before the card bakes) and taken back out before next Sunday's
# walks (pre_walk), so they never compound into the walks. No random draws: the
# rules themselves come from the minds' own named streams (ai.town, ai.supplier).

TOWN_FLAG_FIDS = (17, 107, 109, 110)
TOWN_WALK_CAPS = {104: 2, 108: 3}          # sales-tax drift, fair-schedule tightness (points)
ROAD_WORK_TRAFFIC = -2                      # 17 -> factor 11 (city traffic), points
INSPECTION_TRAFFIC = -1                     # 109 -> factor 11
WAGE_FLOOR_CAP = 3                          # 107 intensity -> factor 13 (local wage pressure), points
BAG_RULE_STEP, BAG_RULE_CAP = 1, 2          # 110 -> factor 62 (packaging, national), points
SUPPLIER_CAP = 3                            # quote vs commodity gap -> commodity factor 67-79, points
OFFSET_CAP = 3                              # any one factor key, all sources together
INBOX_KEEP = 200
INBOX_CHOICE_DAYS = 28


def _fid(key: str) -> int:
    return int(str(key).split(":", 1)[0])


def _town_view(clean: dict[str, int], world: dict) -> dict[str, int]:
    """The factor card as the minds should see it: the game plus their own standing rules."""
    view = dict(clean)
    for key, value in (world.get("town_rules") or {}).items():
        view[key] = int(value)
    for key, off in (world.get("town_walk") or {}).items():
        view[key] = int(view.get(key, clean.get(str(_fid(key)), 100))) + int(off)
    return view


def _capture_town(world: dict, shown: dict[str, int], after: dict[str, int]) -> None:
    rules = world.setdefault("town_rules", {})
    walk = world.setdefault("town_walk", {})
    for key in sorted(after):
        new = int(after[key])
        if int(shown.get(key, new)) == new:
            continue
        fid = _fid(key)
        if fid in TOWN_FLAG_FIDS:
            if new:
                rules[key] = new
            else:
                rules.pop(key, None)
        elif fid in TOWN_WALK_CAPS:
            cap = TOWN_WALK_CAPS[fid]
            total = max(-cap, min(cap, int(walk.get(key, 0)) + new - int(shown[key])))
            if total:
                walk[key] = total
            else:
                walk.pop(key, None)


def town_supplier_offsets(ai_state, world: dict, clean: dict[str, int], private_label: bool = False) -> dict[str, int]:
    """Bounded factor offsets from the minds' standing town rules and supplier quotes."""
    from open_late.ai.constants import SUPPLIER_DEPT
    from open_late.economy import DEPT_COMMODITY

    out: dict[str, int] = {}

    def bump(key: str, value: int) -> None:
        out[key] = out.get(key, 0) + int(value)

    for key, off in sorted((world.get("town_walk") or {}).items()):
        bump(key, off)
    bag = 0
    for key, value in sorted((world.get("town_rules") or {}).items()):
        fid = _fid(key)
        city = key.split(":", 1)[1] if ":" in key else ""
        if not city:
            continue
        if fid == 17:
            bump(f"11:{city}", ROAD_WORK_TRAFFIC)
        elif fid == 109:
            bump(f"11:{city}", INSPECTION_TRAFFIC)
        elif fid == 107:
            bump(f"13:{city}", min(WAGE_FLOOR_CAP, max(0, int(value))))
        elif fid == 110:
            bag += BAG_RULE_STEP
    if bag:
        bump("62", min(BAG_RULE_CAP, bag))
    for supplier_id in sorted(ai_state.supplier_quotes):
        if supplier_id == "labelco" and not private_label:
            continue
        dept = SUPPLIER_DEPT.get(supplier_id)
        fid = DEPT_COMMODITY.get(dept or "")
        if fid is None:
            continue
        key = str(fid)
        gap = int(ai_state.supplier_quotes[supplier_id].cost_index) - int(clean.get(key, 100))
        bump(key, max(-SUPPLIER_CAP, min(SUPPLIER_CAP, gap)))
    return {key: max(-OFFSET_CAP, min(OFFSET_CAP, value)) for key, value in out.items() if value}


def _apply_town_and_suppliers(state: GameState, ai_state, world: dict, clean: dict[str, int]) -> None:
    from open_late.economy import FACTORS

    eco = state.economy
    applied: dict[str, int] = {}
    offsets = town_supplier_offsets(ai_state, world, clean, bool(getattr(state.flags, "private_label", False)))
    for key, off in sorted(offsets.items()):
        if key not in eco.values:
            continue
        low, high = FACTORS[_fid(key)]["range"]
        old = int(round(eco.values[key]))
        new = max(int(low), min(int(high), old + off))
        if new != old:
            eco.values[key] = new
            applied[key] = new - old
    world["town_applied"] = applied


def pre_walk(state: GameState) -> None:
    """Remove last Sunday's applied offsets before the walks (exact undo)."""
    block = getattr(state, "rival_ai", None)
    if block is None:
        return
    data = live(state)
    applied = data["world"].get("town_applied") or {}
    eco = state.economy
    for key, delta in applied.items():
        if key in eco.values:
            eco.values[key] = int(round(eco.values[key])) - int(delta)
    data["world"]["town_applied"] = {}


# --- F1: inbox cap (AI on only) -----------------------------------------------------------

def _cap_inbox(state: GameState) -> None:
    """Keep the last INBOX_KEEP messages plus anything still important:
    urgent and unresolved, or an unresolved choice from the last INBOX_CHOICE_DAYS days."""
    inbox = state.inbox
    if len(inbox) <= INBOX_KEEP:
        return
    cut = len(inbox) - INBOX_KEEP
    floor = int(state.day) - INBOX_CHOICE_DAYS
    state.inbox = [
        message
        for index, message in enumerate(inbox)
        if index >= cut
        or (not message.resolved and (message.urgent or (message.choices and int(message.day) >= floor)))
    ]


# --- F2: the player's building loan (AI on only) ------------------------------------------
#
# The player borrows for a supercenter on the rivals' terms. Approval is the AI
# package's own test (``open_late.ai.legal.build_loan_terms``: 70% of cost, the
# four-week cash cushion, the 13-week liquidity rule, the debt/EBITDA cap and the
# payment-cover rule), called with the player's books in a RivalChain-shaped
# probe. Weekly service is the AI's ``books.loan_service`` (level principal over
# BUILD_TERM_WEEKS, interest on the balance at the loan's rate_bps), and the
# interest goes through the player's Sunday interest bill, so factor 1 (policy
# rate) -> factor 96 (credit spread) -> interest_mult reaches it exactly as it
# reaches the rivals' loans in ``_settle`` (fed.rival_interest_due).
# The loans live in the AI block's world, so they ride the compressed save.

LOAN_BOOKS_WEEKS = 4   # one closed 4-week statement is the shortest record a lender reads
LOAN_MAX_STATEMENTS = 3  # trailing EBITDA from up to the last three statements (12 weeks)


def _loan_rows(state: GameState) -> list[dict]:
    data = live(state)
    if data is None:
        return []
    return list(data["world"].get("player_loans") or [])


def player_loans(state: GameState) -> list:
    """The player's building loans as the AI's BuildLoan model (empty when AI is off)."""
    from open_late.ai.models import BuildLoan

    return [BuildLoan.model_validate({k: row[k] for k in ("store_id", "original", "principal", "rate_bps", "term_weeks")})
            for row in _loan_rows(state)]


def player_loan_balance(state: GameState) -> int:
    if getattr(state, "rival_ai", None) is None:
        return 0
    return sum(int(row["principal"]) for row in _loan_rows(state))


def _player_books(state: GameState) -> dict[str, int]:
    """Weekly numbers a lender reads off the player's own statements (integer dollars)."""
    from open_late.hq import store_pnl

    months = list(state.months)[-LOAN_MAX_STATEMENTS:]
    weeks = LOAN_BOOKS_WEEKS * len(months)
    operating = sum(int(m.operating) for m in months)
    ebitda = sum(int(m.gross_profit) - int(m.operating) for m in months)
    doors = []
    for door in state.doors:
        if door.status != "open":
            continue
        row = store_pnl(state, door.id, days=28)
        opex = row["labor"] + row["rent"] + row["freight"] + row["shrink"] + row["card_fees"] + row["pos_fees"]
        doors.append((int(row["contribution"]), int(opex)))
    return {
        "statements": len(months),
        "weekly_cost": operating // weeks if weeks else 0,
        "weekly_net": ebitda // weeks if weeks else 0,
        "ebitda_52": ebitda * 52 // weeks if weeks else 0,
        "door_contribution": (sum(c for c, _o in doors) // len(doors)) // 4 if doors else 0,
        "door_opex": (sum(o for _c, o in doors) // len(doors)) // 4 if doors else 0,
        "doors": len(doors),
    }


def _player_probe(state: GameState, books: dict[str, int]):
    """The player's balance sheet in the AI's RivalChain shape (read only)."""
    from open_late.ai.models import ChainPnL, RivalChain

    return RivalChain(
        chain_id="player",
        personality_id="player",
        price_index=100,
        cash=int(state.cash),
        revolver_debt=int(state.credit_used),
        build_loans=player_loans(state),
        credit_line=int(state.credit_limit),
        last_pnl=ChainPnL(week=0, net=int(books["weekly_net"])),
    )


def _denial_reason(probe, cost: int, weekly_cost: int, incremental: int, ebitda_52: int) -> str:
    """Name the first of the AI's rules that failed (wording only; approval is the AI's call)."""
    from open_late.ai.constants import BUILD_LTV, BUILD_TERM_WEEKS, BUILD_WEEKLY_RATE, MIN_CASH_WEEKS, MIN_LIQUIDITY_WEEKS

    loan = int(cost * BUILD_LTV)
    cash_after = probe.cash - (cost - loan)
    if cash_after < MIN_CASH_WEEKS * weekly_cost:
        return (f"cash after the down payment would be under the {MIN_CASH_WEEKS}-week cushion "
                f"({cash_after:,} vs {MIN_CASH_WEEKS * weekly_cost:,})")
    undrawn = max(0, probe.credit_line - probe.revolver_debt)
    if cash_after + undrawn < MIN_LIQUIDITY_WEEKS * weekly_cost:
        return f"cash plus unused credit would be under {MIN_LIQUIDITY_WEEKS} weeks of costs"
    owed = probe.revolver_debt + loan + sum(item.principal for item in probe.build_loans)
    if ebitda_52 <= 0 or owed > probe.mandate.max_debt_ratio_x100 / 100.0 * ebitda_52:
        return f"debt would be over {probe.mandate.max_debt_ratio_x100 / 100.0:.1f}x a year of operating profit"
    payment = int(round(loan * BUILD_WEEKLY_RATE)) + max(1, loan // BUILD_TERM_WEEKS)
    if incremental <= payment:
        return f"a new door's weekly contribution ({incremental:,}) does not cover the loan payment ({payment:,})"
    return "the building loan does not cover"


def player_store_loan_offer(state: GameState, market_id: str) -> dict[str, Any]:
    """The building loan the player is offered for a new door, on the rivals' terms.

    Keys: market, cost, principal, equity, rate_bps (base), annual_rate (today, Fed-linked),
    policy_rate, spread_over_policy, term_weeks, weekly_payment (first week, today's rate),
    weekly_interest, weekly_principal, approved, reason, inputs.
    """
    from open_late.ai.books import loan_service
    from open_late.ai.constants import BUILD_LTV, BUILD_TERM_WEEKS
    from open_late.ai.legal import build_loan_terms
    from open_late.ai.models import BuildLoan
    from open_late.corporate import MARKETS, door_by_id
    from open_late.fed import loan_rate_index, policy_rate

    rate_bps = int(BuildLoan.model_fields["rate_bps"].default)
    offer: dict[str, Any] = {"market": market_id, "cost": 0, "principal": 0, "equity": 0, "rate_bps": rate_bps,
                             "annual_rate": 0.0, "policy_rate": None, "spread_over_policy": None,
                             "term_weeks": BUILD_TERM_WEEKS, "weekly_payment": 0, "weekly_interest": 0,
                             "weekly_principal": 0, "approved": False, "reason": "", "inputs": {}}
    if not is_on(state):
        offer["reason"] = "building loans come with the rival chains (rival AI is off)"
        return offer
    market = MARKETS.get(market_id)
    if state.mode != "corporate" or market is None or market.opening_cost <= 0:
        offer["reason"] = "that city is not on the list"
        return offer
    if door_by_id(state, market_id) is not None:
        offer["reason"] = f"{market.city} is already on the lease"
        return offer
    cost = player_opening_cost(state, market_id)
    principal = int(cost * BUILD_LTV)
    index = float(loan_rate_index(state))
    base_interest, step = loan_service(BuildLoan(store_id=f"player:{market_id}", original=principal, principal=principal))
    interest = int(round(base_interest * index))
    policy = policy_rate(state)
    annual = rate_bps / 10_000 * index
    offer.update({
        "cost": cost, "principal": principal, "equity": cost - principal,
        "annual_rate": round(annual, 6),
        "policy_rate": None if policy is None else round(float(policy), 6),
        "spread_over_policy": None if policy is None else round(annual - float(policy), 6),
        "weekly_interest": interest, "weekly_principal": step, "weekly_payment": interest + step,
    })
    books = _player_books(state)
    weekly_cost = books["weekly_cost"] + books["door_opex"]
    incremental = books["door_contribution"]
    offer["inputs"] = {**books, "weekly_cost_with_door": weekly_cost, "incremental": incremental,
                       "cash": int(state.cash), "credit_used": int(state.credit_used), "credit_limit": int(state.credit_limit),
                       "loans_outstanding": player_loan_balance(state), "rate_index": round(index, 6)}
    if books["statements"] < 1 or books["doors"] < 1:
        offer["reason"] = "the lender needs one closed 4-week statement first"
        return offer
    probe = _player_probe(state, books)
    allowed, loan = build_loan_terms(probe, cost, weekly_cost, incremental, books["ebitda_52"])
    if not allowed:
        offer["reason"] = _denial_reason(probe, cost, weekly_cost, incremental, books["ebitda_52"])
        return offer
    if state.cash - (cost - loan) < market.min_cash_after:
        offer["reason"] = f"the down payment would leave under {market.min_cash_after:,} in the drawer"
        return offer
    offer["approved"] = True
    offer["reason"] = "approved on the same terms the rival chains get"
    return offer


def take_store_loan(state: GameState, market_id: str, offer: dict[str, Any]) -> None:
    """Book an approved loan (called by corporate.open_market after the door is signed)."""
    from open_late.ai.constants import BUILD_TERM_WEEKS

    data = live(state)
    loans = data["world"].setdefault("player_loans", [])
    loans.append({"store_id": f"player:{market_id}", "market": market_id, "opened_day": int(state.day),
                  "original": int(offer["principal"]), "principal": int(offer["principal"]),
                  "rate_bps": int(offer["rate_bps"]), "term_weeks": int(BUILD_TERM_WEEKS)})


def player_loan_service(state: GameState) -> tuple[int, int]:
    """One Sunday of service on the player's building loans: (base interest, principal).

    Interest is at the loan's base rate; the caller adds it to the Sunday interest
    bill, which applies interest_mult (factors 1 -> 96, 102). Principal shrinks here.
    """
    if getattr(state, "rival_ai", None) is None:
        return 0, 0
    rows = _loan_rows(state)
    if not rows:
        return 0, 0
    from open_late.ai.books import loan_service

    interest = paid = 0
    for row, loan in zip(rows, player_loans(state)):
        base, step = loan_service(loan)
        interest += base
        row["principal"] = int(row["principal"]) - step
        paid += step
    live(state)["world"]["player_loans"] = [row for row in rows if int(row["principal"]) > 0]
    return interest, paid
