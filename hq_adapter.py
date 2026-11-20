"""UI adapter for optional open_late.hq engine APIs.

Yupper owns open_late/hq.py. This module imports it lazily and falls back to
existing GameState fields (or clearly marked placeholders) when the module is
absent, so the HQ shell works on the current base.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from open_late.models import GameState

HOME_STORE_ID = "evansville"
DEFAULT_POS = "counter_ledger"
# Documented install fees, in integer dollars. Used for labels when hq.py is absent.
# When hq.py is present, install_fee() reads open_late.hq.INSTALL_FEE instead.
FALLBACK_INSTALL_FEE = {
    "open_drawer": 200,
    "counter_ledger": 350,
    "chain_link": 800,
}


def _hq():
    try:
        from open_late import hq as module
    except Exception:
        return None
    return module


def hq_available() -> bool:
    return _hq() is not None


def _call(name: str, *args, **kwargs):
    module = _hq()
    func = getattr(module, name, None) if module is not None else None
    if func is None:
        return None
    return func(*args, **kwargs)


def pos_options() -> list[dict[str, Any]]:
    rows = _call("pos_options")
    if rows is not None:
        return [dict(row) for row in rows]
    # Placeholder catalog — same ids Yupper named, not written into game state.
    return [
        {
            "id": "open_drawer",
            "name": "Open Drawer",
            "blurb": "Placeholder. The engine POS list is not present yet.",
            "weekly_license": 0,
            "card_fee_rate": 0.032,
            "shrink_mult": 1.35,
            "walked_sales_mult": 1.20,
            "placeholder": True,
        },
        {
            "id": "counter_ledger",
            "name": "Counter Ledger",
            "blurb": "Placeholder. The engine POS list is not present yet.",
            "weekly_license": 0,
            "card_fee_rate": 0.026,
            "shrink_mult": 1.0,
            "walked_sales_mult": 1.0,
            "placeholder": True,
        },
        {
            "id": "chain_link",
            "name": "Chain Link",
            "blurb": "Placeholder. The engine POS list is not present yet.",
            "weekly_license": 110,
            "card_fee_rate": 0.021,
            "shrink_mult": 0.65,
            "walked_sales_mult": 0.80,
            "placeholder": True,
        },
    ]


def store_ids(state: GameState) -> list[str]:
    rows = _call("store_ids", state)
    if rows is not None:
        return list(rows)
    if state.doors:
        ids = []
        if any(door.id == HOME_STORE_ID for door in state.doors):
            ids.append(HOME_STORE_ID)
        ids.extend(door.id for door in state.doors if door.id != HOME_STORE_ID)
        return ids
    return [HOME_STORE_ID]


def _door(state: GameState, store_id: str):
    return next((door for door in state.doors if door.id == store_id), None)


def _pos_name(pos_id: str | None) -> str:
    if not pos_id:
        return "Counter Ledger"
    for row in pos_options():
        if row.get("id") == pos_id:
            return str(row.get("name") or pos_id)
    return str(pos_id)


def _pending_info(pending) -> tuple[str | None, str | None]:
    if not pending:
        return None, None
    if isinstance(pending, dict):
        pos_id = pending.get("id") or pending.get("pos_id")
        return pos_id, pending.get("name") or _pos_name(pos_id)
    return str(pending), _pos_name(str(pending))


def store_pos(state: GameState, store_id: str) -> dict[str, Any]:
    row = _call("store_pos", state, store_id)
    if row is not None:
        data = dict(row)
        pending = data.get("pending")
        pending_id, pending_name = _pending_info(pending)
        data.setdefault("name", _pos_name(data.get("id") or data.get("pos_id")))
        data["pending"] = pending
        data["pending_id"] = pending_id
        data["pending_name"] = pending_name
        data["placeholder"] = False
        return data
    return {
        "id": DEFAULT_POS,
        "name": "Counter Ledger",
        "pending": None,
        "pending_id": None,
        "pending_name": None,
        "placeholder": True,
    }


def set_store_pos(state: GameState, store_id: str, pos_id: str) -> str:
    result = _call("set_store_pos", state, store_id, pos_id)
    if result is not None:
        return str(result)
    return (
        "POS changes will apply once the engine API is present. "
        "A switch charges the install fee today and the new till takes over at the next Sunday close."
    )


def store_pnl(state: GameState, store_id: str, days: int = 7) -> dict[str, Any]:
    row = _call("store_pnl", state, store_id, days=days)
    if row is not None:
        data = dict(row)
        data["placeholder"] = False
        return data
    door = _door(state, store_id)
    report = state.last_report
    if door is None:
        sales = report.revenue if report.day else 0
        return {
            "store_id": store_id,
            "name": state.shop_name,
            "days": days,
            "sales": sales,
            "cogs": report.cogs if report.day else 0,
            "labor": report.payroll_paid if report.day else 0,
            "rent": report.rent_paid if report.day else 0,
            "freight": report.shipping if report.day else 0,
            "shrink": report.shrink_cost if report.day else 0,
            "card_fees": report.card_fees if report.day else 0,
            "pos_fees": 0,
            "contribution": 0,
            "placeholder": True,
        }
    return {
        "store_id": door.id,
        "name": door.city,
        "days": days,
        "sales": 0,
        "cogs": 0,
        "labor": 0,
        "rent": 0,
        "freight": 0,
        "shrink": 0,
        "card_fees": 0,
        "pos_fees": 0,
        "contribution": 0,
        "placeholder": True,
    }


_MONEY_KEYS = ("sales", "cogs", "labor", "rent", "freight", "shrink", "card_fees", "pos_fees", "contribution")


def chain_board(state: GameState, days: int = 7) -> list[dict[str, Any]]:
    rows = _call("chain_board", state, days=days)
    if rows is not None:
        return [dict(row) for row in rows]
    board = [store_pnl(state, store_id, days=days) for store_id in store_ids(state)]
    total = {key: sum(int(row.get(key, 0) or 0) for row in board) for key in _MONEY_KEYS}
    total.update({
        "store_id": "chain",
        "name": "Chain",
        "days": days,
        "placeholder": True,
    })
    board.append(total)
    return board


def scoped_store_ids(state: GameState, kind: str, scope_id: str | None) -> list[str]:
    ids = store_ids(state)
    if kind == "store" and scope_id:
        return [scope_id] if scope_id in ids else ids
    if kind == "region" and scope_id:
        matched = []
        for store_id in ids:
            door = _door(state, store_id)
            if door is not None and door.region == scope_id:
                matched.append(store_id)
        return matched
    return ids


def regions_for(state: GameState) -> list[str]:
    seen: list[str] = []
    for door in state.doors:
        if door.region not in seen:
            seen.append(door.region)
    return seen


def warehouse_units(state: GameState) -> int:
    return sum(line.on_hand for line in state.stock.values())


def install_fee(pos_id: str) -> int:
    module = _hq()
    fees = getattr(module, "INSTALL_FEE", None) if module is not None else None
    if isinstance(fees, dict) and pos_id in fees:
        return int(fees[pos_id])
    return int(FALLBACK_INSTALL_FEE.get(pos_id, 0))



# --- Chain catalog (Yupper owns open_late.chains; this is a guarded fallback) ---

ASSETS = Path(__file__).resolve().parent.parent / "assets"
CHAINS_DIR = ASSETS / "chains"

FALLBACK_CHAINS = [
    {"id": "megamart", "name": "Northstar Market", "logo": "megamart.png"},
    {"id": "valuemax", "name": "Redline Retail", "logo": "valuemax.png"},
    {"id": "primestop", "name": "Harbor & Pine Market", "logo": "primestop.png"},
    {"id": "everyday", "name": "ValueForge", "logo": "everyday.png"},
    {"id": "shopgiant", "name": "Metrovale Retail", "logo": "shopgiant.png"},
    {"id": "bluestar", "name": "BrightBasket", "logo": "bluestar.png"},
    {"id": "allinone", "name": "Ironwood Mercantile", "logo": "allinone.png"},
]
FALLBACK_DEFAULT_CHAIN_ID = "megamart"
_SESSION_CHAIN: dict[str, str] = {}

# Chain fascia colors for painted storefronts (sampled from official logos).
CHAIN_COLORS = {
    "megamart": {"fascia": "#1A4E9C", "accent": "#7EB6FF", "wall": "#E8EEF4", "trim": "#0E2E66"},
    "valuemax": {"fascia": "#111111", "accent": "#E10600", "wall": "#F4F4F4", "trim": "#8B0000"},
    "primestop": {"fascia": "#1B4D32", "accent": "#C5D7A4", "wall": "#F3F6EF", "trim": "#0E3320"},
    "everyday": {"fascia": "#E85D04", "accent": "#F4A261", "wall": "#F7F7F7", "trim": "#3A3A3A"},
    "shopgiant": {"fascia": "#1B4F9C", "accent": "#D6E4F0", "wall": "#F7F9FC", "trim": "#0E2F66"},
    "bluestar": {"fascia": "#2E8B3A", "accent": "#F5A524", "wall": "#FFF8EE", "trim": "#1F6B2C"},
    "allinone": {"fascia": "#3A2A1E", "accent": "#C4A574", "wall": "#F3EDE4", "trim": "#8C6A3D"},
}


def _chains_mod():
    try:
        from open_late import chains as module
    except Exception:
        return None
    return module


def chains_available() -> bool:
    return _chains_mod() is not None


def default_chain_id() -> str:
    module = _chains_mod()
    value = getattr(module, "DEFAULT_CHAIN_ID", None) if module is not None else None
    return str(value or FALLBACK_DEFAULT_CHAIN_ID)


def chain_catalog() -> list[dict[str, Any]]:
    module = _chains_mod()
    rows = getattr(module, "CHAINS", None) if module is not None else None
    if rows:
        out = []
        for row in rows:
            data = dict(row)
            ident = str(data.get("id") or "")
            logo = data.get("logo") or data.get("logo_filename") or data.get("logo_file") or f"{ident}.png"
            data["logo"] = logo
            data.setdefault("name", ident.title())
            data["placeholder"] = False
            out.append(data)
        return out
    return [dict(row, placeholder=True) for row in FALLBACK_CHAINS]


def chain_by_id(chain_id: str | None) -> dict[str, Any]:
    wanted = chain_id or default_chain_id()
    for row in chain_catalog():
        if row.get("id") == wanted:
            return row
    return dict(chain_catalog()[0])


def _logo_filename(row: dict[str, Any]) -> str:
    return str(row.get("logo") or row.get("logo_filename") or row.get("logo_file") or f"{row.get('id')}.png")


def chain_logo_path(chain_id_or_row) -> Path:
    if isinstance(chain_id_or_row, dict):
        row = chain_id_or_row
    else:
        row = chain_by_id(str(chain_id_or_row or default_chain_id()))
    name = _logo_filename(row)
    path = CHAINS_DIR / name
    if not path.exists():
        path = CHAINS_DIR / f"{row.get('id')}.png"
    return path


def resolved_chain_id(state: GameState | None) -> str:
    if state is None:
        return default_chain_id()
    value = getattr(state, "chain_id", None)
    if value:
        return str(value)
    return _SESSION_CHAIN.get(getattr(state, "slot", ""), default_chain_id())


def chain_info(state: GameState | None) -> dict[str, Any]:
    if state is not None:
        module = _chains_mod()
        func = getattr(module, "chain_info", None) if module is not None else None
        if func is not None:
            try:
                data = dict(func(state))
                data.setdefault("id", resolved_chain_id(state))
                data.setdefault("name", chain_by_id(data.get("id"))["name"])
                data.setdefault("logo", _logo_filename(data if "logo" in data else chain_by_id(data.get("id"))))
                data["placeholder"] = False
                return data
            except Exception:
                pass
    row = chain_by_id(resolved_chain_id(state))
    colors = CHAIN_COLORS.get(row["id"], CHAIN_COLORS["megamart"])
    return {
        "id": row["id"],
        "name": row["name"],
        "logo": _logo_filename(row),
        "colors": colors,
        "placeholder": not chains_available(),
    }


def set_chain(state: GameState, chain_id: str) -> str:
    if not any(row["id"] == chain_id for row in chain_catalog()):
        raise ValueError(f"Unknown chain: {chain_id}")
    module = _chains_mod()
    func = getattr(module, "set_chain", None) if module is not None else None
    if func is not None:
        result = func(state, chain_id)
        _SESSION_CHAIN[state.slot] = chain_id
        return str(result)
    _SESSION_CHAIN[state.slot] = chain_id
    if hasattr(state, "chain_id"):
        try:
            state.chain_id = chain_id
        except Exception:
            pass
    name = chain_by_id(chain_id)["name"]
    return f"{name} is the chain on this shop."


def chain_colors(state: GameState | None = None, chain_id: str | None = None) -> dict[str, str]:
    ident = chain_id or resolved_chain_id(state)
    return dict(CHAIN_COLORS.get(ident, CHAIN_COLORS["megamart"]))


_STATE_ABBREV = {
    "Indiana": "IN", "Illinois": "IL", "Texas": "TX", "Nevada": "NV",
    "Washington": "WA", "Tennessee": "TN", "Kentucky": "KY",
}

# Fictional streets, used only in the desk. Numbers and ZIP tails come from the store id.
_STREETS = {
    "evansville": ("Harbor Mill Rd", "Oakridge Crossing", "Westfield Blvd", "Copper Creek Dr"),
    "naperville": ("Millbrook Ln", "Prairie Station Rd", "Linden Grove Ave", "Fox River Pkwy"),
    "houston": ("Bayou Bend Blvd", "Cinder Lake Dr", "Mesquite Ridge Rd", "Cypress Trail"),
    "las_vegas": ("Sundown Mesa Rd", "Quartz Valley Ave", "Redcliff Pkwy", "Ironwood Spur"),
    "seattle": ("Cedar Beacon Way", "Soundview Terrace", "Rainier Crossing", "Puget Mill Rd"),
}
_ZIP_STEM = {
    "evansville": "4771",
    "naperville": "6054",
    "houston": "7706",
    "las_vegas": "8912",
    "seattle": "9810",
}


def state_abbrev(state_name: str) -> str:
    from open_late.us_capitals import STATE_ABBR

    name = state_name or ""
    return STATE_ABBR.get(name) or _STATE_ABBREV.get(name) or name


def display_address(door) -> str:
    """City and short state. Use street_address() when a full line is needed."""
    if door is None:
        return ""
    short = state_abbrev(getattr(door, "state_name", "") or "")
    city = getattr(door, "city", "")
    if city and short:
        return f"{city}, {short}"
    return city or short


def street_address(door) -> str:
    """Deterministic fictional street line for a door or market. UI only."""
    if door is None:
        return ""
    ident = str(getattr(door, "id", "") or getattr(door, "city", "") or "store")
    city = getattr(door, "city", "") or ident.replace("_", " ").title()
    short = state_abbrev(getattr(door, "state_name", "") or "")
    import hashlib
    digest = hashlib.sha256(ident.encode()).digest()
    number = 100 + (digest[0] * 256 + digest[1]) % 8900
    streets = _STREETS.get(ident, ("Market Plaza", "Commerce Way", "Depot Hill Rd", "Harvest Lane"))
    street = streets[digest[2] % len(streets)]
    stem = _ZIP_STEM.get(ident, "4000")
    zipc = f"{stem}{digest[3] % 10}"
    if city and short:
        return f"{number} {street}, {city}, {short} {zipc}"
    return f"{number} {street}"


def recorded_sales(state: GameState, door) -> int:
    """Best available sales total for a door — the last 56 recorded days, not a calendar YTD."""
    if door is None:
        return 0
    try:
        row = store_pnl(state, door.id, days=56)
        if row and not row.get("placeholder"):
            return int(row.get("sales") or 0)
    except Exception:
        pass
    return int(getattr(door, "last_sales", 0) or getattr(door, "week_sales", 0) or 0)


def contribution_share(state: GameState, door) -> tuple[int, float]:
    """Return (contribution dollars, share of chain 0-1). Store P&L, not last-week contribution."""
    if door is None:
        return 0, 0.0
    try:
        board = chain_board(state, days=56)
    except Exception:
        board = []
    rows = [row for row in board if row.get("store_id") not in ("chain", None)]
    total = 0
    mine = 0
    for row in rows:
        value = int(row.get("contribution") or 0)
        if row.get("store_id") == door.id:
            mine = value
        total += value
    if not rows:
        mine = int(store_pnl(state, door.id).get("contribution") or 0)
        total = mine
    share = (mine / total) if total else 0.0
    return mine, share


# Department colors are UI-only; ids and labels come from open_late.departments.
DEPARTMENT_COLORS = {
    "grocery": "#C9843A",
    "produce": "#5B8F3A",
    "meat_dairy": "#E8D56A",
    "frozen": "#6BA6D4",
    "household": "#8A7E6A",
    "health_beauty": "#3AA6A0",
    "pharmacy": "#2E8B7A",
    "electronics": "#3D8BDB",
    "clothing": "#7A5CAF",
    "toys": "#E07A3D",
    "home_garden": "#C45B6A",
    "sporting": "#3A7A5C",
    "seasonal": "#D4A373",
}
FALLBACK_DEPARTMENTS = [
    ("grocery", "Grocery"),
    ("produce", "Produce"),
    ("meat_dairy", "Meat and Dairy"),
    ("frozen", "Frozen"),
    ("household", "Household"),
    ("health_beauty", "Health and Beauty"),
    ("pharmacy", "Pharmacy"),
    ("electronics", "Electronics"),
    ("clothing", "Clothing"),
    ("toys", "Toys"),
    ("home_garden", "Home and Garden"),
    ("sporting", "Sporting Goods"),
    ("seasonal", "Seasonal"),
]


def _departments_mod():
    try:
        from open_late import departments as module
    except Exception:
        return None
    return module


def planogram_departments() -> list[tuple[str, str, str]]:
    module = _departments_mod()
    rows = getattr(module, "DEPARTMENTS", None) if module is not None else None
    source = list(rows) if rows else FALLBACK_DEPARTMENTS
    return [(ident, label, DEPARTMENT_COLORS.get(ident, "#6B7380")) for ident, label in source]


def products_by_department(state=None):
    module = _departments_mod()
    func = getattr(module, "products_by_department", None) if module is not None else None
    if func is not None:
        return func(state)
    grouped = {ident: [] for ident, _label, _color in planogram_departments()}
    products = getattr(state, "products", {}) if state is not None else {}
    for product in products.values():
        dept = getattr(product, "department", "") or "household"
        grouped.setdefault(dept, []).append(product)
    return grouped


def department_of(sku: str, state=None) -> str:
    module = _departments_mod()
    func = getattr(module, "department_of", None) if module is not None else None
    if func is not None:
        return str(func(sku, state) or "")
    products = getattr(state, "products", {}) if state is not None else {}
    product = products.get(sku)
    return str(getattr(product, "department", "") or "") if product is not None else ""


def department_sales(state, store_id: str, days: int = 7) -> dict[str, int]:
    module = _departments_mod()
    func = getattr(module, "department_sales", None) if module is not None else None
    if func is not None:
        try:
            return dict(func(state, store_id, days=days))
        except Exception:
            pass
    return {ident: 0 for ident, _label, _color in planogram_departments()}


def _closed_sales_day(state) -> int:
    """Last closed ledger day, matching hq.store_pnl's window."""
    try:
        day = int(getattr(state, "day", 0) or 0)
    except (TypeError, ValueError):
        return 0
    phase = str(getattr(state, "phase", "") or "")
    if phase in ("evening", "gameover"):
        return day
    return max(0, day - 1)


def _empty_dept_totals() -> dict[str, int]:
    return {ident: 0 for ident, _label, _color in planogram_departments()}


def department_sales_in_window(state, store_id: str, low: int, high: int) -> tuple[dict[str, int], bool]:
    """Sum StoreDay.by_department for low..high inclusive. Guarded; missing rows are 0."""
    totals = _empty_dept_totals()
    found = False
    if state is None or not store_id or high < 1 or high < low:
        return totals, False
    try:
        records = list(getattr(state, "store_days", []) or [])
    except Exception:
        return totals, False
    for record in records:
        try:
            if str(getattr(record, "store_id", "") or "") != str(store_id):
                continue
            day = int(getattr(record, "day", 0) or 0)
            if day < low or day > high:
                continue
            found = True
            payload = getattr(record, "by_department", None) or {}
            if not isinstance(payload, dict):
                continue
            for dept, amount in payload.items():
                try:
                    totals[str(dept)] = totals.get(str(dept), 0) + int(amount or 0)
                except (TypeError, ValueError):
                    continue
        except Exception:
            continue
    return totals, found


def department_week_compare(state, store_id: str, days: int = 7) -> dict[str, dict]:
    """Last week vs the prior week, per department, from recorded ledger sales.

    Returns a dict keyed by department id with sales, share, prior, delta_pct,
    and has_prior. delta_pct is None when there is no prior week or prior sales
    are 0 — callers should show an em dash and must not invent a rate.
    """
    try:
        days = max(1, int(days))
    except (TypeError, ValueError):
        days = 7
    last = _closed_sales_day(state)
    current, found_current = department_sales_in_window(state, store_id, last - days + 1, last)
    prior, has_prior = department_sales_in_window(state, store_id, last - 2 * days + 1, last - days)
    # If store_days cannot be read at all, fall back to department_sales for the
    # current window only; prior stays empty so we never invent a prior week.
    if last >= 1 and not found_current:
        fallback = department_sales(state, store_id, days=days)
        if fallback:
            current = {**_empty_dept_totals(), **{str(k): int(v or 0) for k, v in fallback.items()}}
    store_total = sum(int(v or 0) for v in current.values())
    out: dict[str, dict] = {}
    for ident, _label, _color in planogram_departments():
        sales = int(current.get(ident, 0) or 0)
        prev = int(prior.get(ident, 0) or 0)
        share = (sales / store_total) if store_total > 0 else None
        delta = None
        if has_prior and prev > 0:
            delta = (sales - prev) / prev
        out[ident] = {
            "sales": sales,
            "prior": prev,
            "share": share,
            "delta_pct": delta,
            "has_prior": bool(has_prior),
            "store_total": store_total,
        }
    return out

# --- Economy (E1 / E2 / E3), guarded. E4-only calls stay behind getattr. ---

def _economy():
    try:
        from open_late import economy as module
    except Exception:
        return None
    return module


def economy_available() -> bool:
    return _economy() is not None


def _eco_call(name: str, *args, default=None, **kwargs):
    module = _economy()
    func = getattr(module, name, None) if module is not None else None
    if func is None:
        return default
    try:
        return func(*args, **kwargs)
    except Exception:
        return default


def economy_cities() -> list[str]:
    module = _economy()
    cities = getattr(module, "CITIES", None) if module is not None else None
    if cities:
        return [str(item) for item in cities]
    return []


def city_display_name(city_id: str | None) -> str:
    if not city_id:
        return "National"
    return str(city_id).replace("_", " ").title()


def economy_difficulty_of(state) -> str:
    value = _eco_call("economy_difficulty", state, default="off")
    return str(value or "off")


# E5 state-factor ids. Used only when a row is missing kind= so the UI can
# still hide them from the movers strip and render them as chips.
STATE_FACTOR_IDS = frozenset({
    17, 31, 32, 36, 39, 40, 41, 43, 44, 45, 46, 49, 60, 61, 64, 66,
    81, 82, 83, 84, 87, 107, 109, 110, 111,
})


def factor_kind(row: dict | None) -> str:
    """'index' or 'state'. Falls back to the known E5 state ids when kind is absent."""
    row = row or {}
    kind = row.get("kind")
    if kind in ("index", "state"):
        return str(kind)
    try:
        ident = int(row.get("id"))
    except (TypeError, ValueError):
        return "index"
    return "state" if ident in STATE_FACTOR_IDS else "index"


def factor_neutral(row: dict | None):
    row = row or {}
    if row.get("neutral") is not None:
        try:
            return float(row.get("neutral"))
        except (TypeError, ValueError):
            pass
    return 100.0 if factor_kind(row) == "index" else None


def economy_factors(state, *, category: str | None = None, city_id: str | None = None) -> list[dict[str, Any]]:
    rows = _eco_call("economy_factors", state, category=category, city_id=city_id, default=None)
    if rows is None:
        return []
    return [dict(row) for row in rows]


def economy_movers(state, city_id: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
    """Biggest index movers. Prefers E5 economy_movers; otherwise filters kind=='index'."""
    extras = {}
    if city_id:
        extras["city_id"] = city_id
    try:
        extras["limit"] = int(limit)
    except (TypeError, ValueError):
        extras["limit"] = 5
    rows = _eco_call("economy_movers", state, **extras, default=None)
    if rows is None and extras:
        # Older signatures may not take city_id / limit.
        rows = _eco_call("economy_movers", state, default=None)
        if rows is not None and city_id:
            rows = None  # Don't use an unfiltered payload when a city was requested.
    if rows is not None:
        return [dict(row) for row in list(rows)[: max(0, int(limit))]]
    fallback = [row for row in economy_factors(state, city_id=city_id) if factor_kind(row) == "index"]

    def _rank(row: dict) -> tuple:
        try:
            value = float(row.get("value") or 0)
        except (TypeError, ValueError):
            value = 0.0
        neutral = factor_neutral(row)
        base = 100.0 if neutral is None else float(neutral)
        try:
            ident = int(row.get("id") or 0)
        except (TypeError, ValueError):
            ident = 0
        return (-abs(value - base), ident)

    fallback.sort(key=_rank)
    return fallback[: max(0, int(limit))]


def economy_sparklines(
    state,
    factor_ids: list[int],
    weeks: int = 12,
    store_id: str | None = None,
    lines: list[str] | None = None,
) -> dict[str, Any]:
    """Guarded sparkline read. The E4 `lines=` kwarg is retried without if absent."""
    empty: dict[str, Any] = {"weeks": [], "series": {}}
    module = _economy()
    func = getattr(module, "economy_sparklines", None) if module is not None else None
    if func is None:
        return empty
    try:
        if lines:
            try:
                payload = func(state, list(factor_ids), weeks=weeks, store_id=store_id, lines=list(lines))
            except TypeError:
                payload = func(state, list(factor_ids), weeks=weeks, store_id=store_id)
        else:
            payload = func(state, list(factor_ids), weeks=weeks, store_id=store_id)
    except Exception:
        return empty
    if not isinstance(payload, dict):
        return empty
    series = payload.get("series") or {}
    return {
        "weeks": list(payload.get("weeks") or []),
        "series": {str(key): [float(v) for v in (values or [])] for key, values in series.items()},
    }


def impact_filter_kwargs_supported() -> bool:
    """True when economy_store_impact accepts E4 filter kwargs."""
    import inspect

    module = _economy()
    func = getattr(module, "economy_store_impact", None) if module is not None else None
    if func is None:
        return False
    try:
        params = inspect.signature(func).parameters
    except (TypeError, ValueError):
        return False
    return "department" in params or "events_only" in params or "category" in params


def factor_band(value, band: str | None = None, *, kind: str | None = None, neutral=None) -> str:
    """Prefer an explicit band, then E4/E5 gauge_band (kind-aware), then ±10 / ±20 from neutral."""
    if kind == "state":
        return "steady"
    if band in ("steady", "watch", "alert"):
        return str(band)
    try:
        from open_late.economy_e4 import gauge_band

        try:
            return str(gauge_band(int(round(float(value))), kind=kind))
        except TypeError:
            return str(gauge_band(int(round(float(value)))))
    except Exception:
        try:
            base = 100.0 if neutral is None else float(neutral)
            gap = abs(float(value) - base)
        except (TypeError, ValueError):
            return "steady"
        if gap >= 20:
            return "alert"
        if gap >= 10:
            return "watch"
        return "steady"


def economy_store_impact(
    state,
    store_id: str,
    days: int = 7,
    *,
    department: str | None = None,
    category: str | None = None,
    events_only: bool = False,
    min_dollars: int = 0,
) -> dict[str, Any]:
    empty = {
        "store_id": store_id,
        "days": int(days),
        "pnl": {},
        "neutral_pnl": {},
        "delta": {},
        "reasons": [],
    }
    module = _economy()
    func = getattr(module, "economy_store_impact", None) if module is not None else None
    if func is None:
        return empty
    extras = {}
    if department:
        extras["department"] = department
    if category:
        extras["category"] = category
    if events_only:
        extras["events_only"] = True
    if min_dollars:
        extras["min_dollars"] = int(min_dollars)
    try:
        try:
            payload = func(state, store_id, days=days, **extras)
        except TypeError:
            payload = func(state, store_id, days=days)
    except Exception:
        return empty
    if not isinstance(payload, dict):
        return empty
    return {
        "store_id": payload.get("store_id") or store_id,
        "days": int(payload.get("days") or days),
        "pnl": dict(payload.get("pnl") or {}),
        "neutral_pnl": dict(payload.get("neutral_pnl") or {}),
        "delta": dict(payload.get("delta") or {}),
        "reasons": [dict(row) for row in (payload.get("reasons") or [])],
    }


def economy_news(state, *, store_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    rows = _eco_call("economy_news", state, store_id=store_id, limit=limit, default=None)
    if rows is None:
        return []
    return [dict(row) for row in rows]


def economy_snapshot(state) -> dict[str, Any]:
    empty = {
        "week_id": 0,
        "day": 0,
        "difficulty": "off",
        "gauges": [],
        "cities": [],
        "events_active": [],
    }
    payload = _eco_call("economy_snapshot", state, default=empty)
    if not isinstance(payload, dict):
        return empty
    return {
        "week_id": int(payload.get("week_id") or 0),
        "day": int(payload.get("day") or 0),
        "difficulty": str(payload.get("difficulty") or "off"),
        "gauges": [dict(row) for row in (payload.get("gauges") or [])],
        "cities": [dict(row) for row in (payload.get("cities") or [])],
        "events_active": [dict(row) for row in (payload.get("events_active") or [])],
    }


def economy_calendar(state, weeks: int = 8) -> list[dict[str, Any]]:
    rows = _eco_call("economy_calendar", state, weeks=weeks, default=None)
    if rows is None:
        return []
    out = []
    for row in rows:
        item = dict(row)
        item["labels"] = list(item.get("labels") or [])
        item["city_weather"] = dict(item.get("city_weather") or {})
        out.append(item)
    return out
