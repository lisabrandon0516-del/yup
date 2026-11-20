"""Shoppers + Planograms LITE, phase 1: the static shelf model.

Fixed store sizes with a floor of fixed fixtures (action alley, seasonal, the
fresh perimeter, pharmacy, checkout) plus center and GM aisles the player can
move, add, remove and re-department from lists (no drag-and-drop). The player's
choices (template, eye-level priorities, endcap picks) and the floor are the
only things saved; ``planogram_api.auto_planogram`` compiles them into a full
``Layout`` that is rebuilt deterministically and never saved.

Everything here is pure data or pure functions. No engine state is touched.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent / "data"
CATALOG_VERSION = 1
MAX_PINS_PER_DEPT = 3
MAX_PINS_PER_STORE = 24
MAX_ENDCAP_SKUS = 3
DEFAULT_SIZE = "supercenter_v1"


@lru_cache(maxsize=None)
def formats() -> dict[str, Any]:
    return json.loads((DATA_DIR / "shelf_formats_v1.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def shopper_traits() -> dict[str, Any]:
    return json.loads((DATA_DIR / "shopper_instore_v1.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def pairs() -> tuple[tuple[str, str], ...]:
    rows = json.loads((DATA_DIR / "pairs_v1.json").read_text(encoding="utf-8"))["pairs"]
    return tuple((str(a), str(b)) for a, b in rows)


@lru_cache(maxsize=None)
def sku_index_v1() -> tuple[str, ...]:
    """Frozen, append-only SKU order: the shipped catalog, then the house label."""
    from open_late.content import LABEL_PRODUCTS, PRODUCTS

    out: list[str] = []
    for product in list(PRODUCTS) + list(LABEL_PRODUCTS):
        if product.id not in out:
            out.append(product.id)
    return tuple(out)


@lru_cache(maxsize=None)
def sku_pos() -> dict[str, int]:
    return {sku: i for i, sku in enumerate(sku_index_v1())}


def segment_mix(income_index: int = 100) -> dict[str, float]:
    """Segment shares for a city. Uses the rival AI's own rule (open_late.ai.shoppers.segment_mix)
    when that package is present, so both shopper models split a city the same way; else the
    same formula, copied, so the shelves work on a tree without the AI."""
    try:
        from open_late.ai.shoppers import segment_mix as ai_mix
    except ImportError:
        ai_mix = None
    if ai_mix is not None:
        return dict(ai_mix(income_index))
    tilt = max(-1.0, min(1.0, (income_index - 100) / 40.0))
    raw = {
        "value_stretchers": 0.22 - 0.08 * tilt, "busy_families": 0.24, "fresh_first": 0.14 + 0.06 * tilt,
        "brand_loyal": 0.12 + 0.08 * tilt, "deal_hunters": 0.16 - 0.06 * tilt, "online_leaners": 0.12,
    }
    total = sum(raw.values())
    return {k: v / total for k, v in raw.items()}


@lru_cache(maxsize=None)
def mission_mix() -> tuple[float, float, float]:
    """Default trip mix (stock-up, fill-in, grab-and-go) from the segment table."""
    traits = shopper_traits()
    mix = segment_mix(100)
    total = [0.0, 0.0, 0.0]
    weight = 0.0
    for seg, share in mix.items():
        missions = traits["segments"][seg]["missions"]
        for i in range(3):
            total[i] += share * missions[i]
        weight += share
    return tuple(round(value / weight, 4) for value in total)  # type: ignore[return-value]


@lru_cache(maxsize=None)
def zone_exposure(zone: str) -> float:
    mix = mission_mix()
    row = formats()["zones"][zone]
    return round(sum(m * z for m, z in zip(mix, row)), 4)


_CUSTOM_SIZES: dict[str, dict[str, Any]] = {}


def register_size(size_id: str, spec: dict[str, Any]) -> None:
    """A building designed at the lease. It stays in the size table for this session and is saved on the door."""
    _CUSTOM_SIZES[size_id] = spec
    formats()["sizes"][size_id] = spec


def size_spec(size_id: str) -> dict[str, Any]:
    custom = _CUSTOM_SIZES.get(size_id)
    if custom is not None:
        formats()["sizes"][size_id] = custom
        return custom
    sizes = formats()["sizes"]
    return sizes.get(size_id) or sizes[DEFAULT_SIZE]


def size_ids() -> list[str]:
    return list(formats()["sizes"])


# ---------------------------------------------------------------- floors


@dataclass(frozen=True)
class Aisle:
    uid: str  # stable id, e.g. "C1" or "G8" (never reused inside a door)
    kind: str  # "center" | "gm"
    dept: str


def default_floor(size_id: str) -> tuple[Aisle, ...]:
    spec = size_spec(size_id)
    out = []
    for i, dept in enumerate(spec["center"]["default"]):
        out.append(Aisle(f"C{i + 1}", "center", dept))
    for i, dept in enumerate(spec["gm"]["default"]):
        out.append(Aisle(f"G{i + 1}", "gm", dept))
    return tuple(out)


def pack_floor(floor: tuple[Aisle, ...]) -> str:
    return ",".join(f"{a.uid}:{a.dept}" for a in floor)


def unpack_floor(text: str, size_id: str) -> tuple[Aisle, ...]:
    if not text:
        return default_floor(size_id)
    out = []
    for part in text.split(","):
        uid, _, dept = part.partition(":")
        kind = "center" if uid.startswith("C") else "gm"
        out.append(Aisle(uid, kind, dept))
    return tuple(out)


def aisle_label(floor: tuple[Aisle, ...], aisle: Aisle) -> str:
    """Display number by position: center aisles 1..n, GM aisles G1..Gn."""
    same = [a for a in floor if a.kind == aisle.kind]
    n = same.index(aisle) + 1
    return f"Aisle {n}" if aisle.kind == "center" else f"GM {n}"


def floor_limits(size_id: str, kind: str) -> tuple[int, int]:
    spec = size_spec(size_id)[kind]
    return int(spec["min"]), int(spec["max"])


def next_uid(floor: tuple[Aisle, ...], kind: str, used: tuple[str, ...] = ()) -> str:
    prefix = "C" if kind == "center" else "G"
    taken = {a.uid for a in floor} | set(used)
    n = 1
    while f"{prefix}{n}" in taken:
        n += 1
    return f"{prefix}{n}"


# ---------------------------------------------------------------- choices


@dataclass(frozen=True)
class LiteChoice:
    template_id: str = "balanced"
    priorities: tuple[int, ...] = ()  # SKU_INDEX_V1 positions, <=3/dept, <=24/store
    endcaps: tuple[tuple[str, tuple[int, ...]], ...] = ()  # (endcap_id, skus); missing = auto
    action_alley: tuple[tuple[str, tuple[int, ...]], ...] = ()
    checkout_mix: str = "auto"
    promo_link: tuple[tuple[str, str], ...] = ()  # (campaign category, endcap_id)
    facings: tuple[tuple[int, int], ...] = ()  # (sku index, facing count); empty stays off the save

    def facing_map(self) -> dict[int, int]:
        return {int(sku): int(count) for sku, count in self.facings}

    def endcap_map(self) -> dict[str, tuple[int, ...]]:
        return dict(self.endcaps)

    def alley_map(self) -> dict[str, tuple[int, ...]]:
        return dict(self.action_alley)


def pack_choice(choice: LiteChoice) -> dict[str, Any]:
    """Compact JSON-safe dict (~0.1-0.5 KB). Defaults are omitted."""
    out: dict[str, Any] = {"t": choice.template_id}
    if choice.priorities:
        out["p"] = list(choice.priorities)
    if choice.endcaps:
        out["e"] = {key: list(skus) for key, skus in choice.endcaps}
    if choice.action_alley:
        out["a"] = {key: list(skus) for key, skus in choice.action_alley}
    if choice.checkout_mix != "auto":
        out["k"] = choice.checkout_mix
    if choice.promo_link:
        out["l"] = {key: value for key, value in choice.promo_link}
    if choice.facings:
        out["f"] = {str(sku): int(count) for sku, count in choice.facings}
    return out


def unpack_choice(data: dict[str, Any] | None) -> LiteChoice:
    if not data:
        return LiteChoice()
    return LiteChoice(
        template_id=str(data.get("t", "balanced")),
        priorities=tuple(int(x) for x in data.get("p", ())),
        endcaps=tuple(sorted((str(k), tuple(int(x) for x in v)) for k, v in (data.get("e") or {}).items())),
        action_alley=tuple(sorted((str(k), tuple(int(x) for x in v)) for k, v in (data.get("a") or {}).items())),
        checkout_mix=str(data.get("k", "auto")),
        promo_link=tuple(sorted((str(k), str(v)) for k, v in (data.get("l") or {}).items())),
        facings=tuple(sorted((int(k), max(1, min(8, int(v)))) for k, v in (data.get("f") or {}).items())),
    )


# ---------------------------------------------------------------- layout


@dataclass(frozen=True)
class Bay:
    key: str  # "C3.2" inline bay, "C3.F"/"C3.B" endcaps, "AA.1", "CK.1", "PR.4"
    aisle: str  # aisle uid or fixed id
    kind: str  # center | gm | perimeter | seasonal | pharmacy | action_alley | checkout | endcap
    zone: str
    fixture: str
    dept: str  # "*" for mixed fixtures
    order: int  # walk order, used for pair adjacency (<=2 bays apart)
    exposure: float
    tiers: tuple[tuple[str, tuple[tuple[int, int], ...]], ...]  # (tier, ((sku, facings), ...))

    @property
    def is_feature(self) -> bool:
        return self.kind in ("endcap", "action_alley", "checkout")


@dataclass(frozen=True)
class Layout:
    size_id: str
    floor: tuple[Aisle, ...]
    bays: tuple[Bay, ...]
    left_out: tuple[int, ...] = ()
    notes: tuple[str, ...] = ()
    rotation: int = 0
    _index: dict = field(default_factory=dict, compare=False, hash=False, repr=False)

    def sku_slots(self) -> dict[int, list[tuple[int, str, int]]]:
        """sku -> [(bay_index, tier, facings)], built once per layout."""
        cached = self._index.get("slots")
        if cached is not None:
            return cached
        out: dict[int, list[tuple[int, str, int]]] = {}
        for bi, bay in enumerate(self.bays):
            for tier, items in bay.tiers:
                for sku, facings in items:
                    out.setdefault(sku, []).append((bi, tier, facings))
        self._index["slots"] = out
        return out

    def facing_map(self) -> dict[tuple[str, str, int], int]:
        """(bay key, tier, sku) -> facings; the unit of a reset."""
        cached = self._index.get("facings")
        if cached is not None:
            return cached
        out: dict[tuple[str, str, int], int] = {}
        for bay in self.bays:
            for tier, items in bay.tiers:
                for sku, facings in items:
                    key = (bay.key, tier, sku)
                    out[key] = out.get(key, 0) + facings
        self._index["facings"] = out
        return out

    def to_bytes(self) -> bytes:
        rows = [self.size_id, pack_floor(self.floor), str(self.rotation)]
        for bay in self.bays:
            tiers = ";".join(f"{t}=" + " ".join(f"{s}x{f}" for s, f in items) for t, items in bay.tiers)
            rows.append(f"{bay.key}|{bay.zone}|{bay.fixture}|{bay.dept}|{bay.order}|{bay.exposure:.4f}|{tiers}")
        rows.append("left:" + " ".join(str(s) for s in self.left_out))
        return "\n".join(rows).encode()

    def fingerprint(self) -> str:
        cached = self._index.get("fp")
        if cached is None:
            import hashlib

            cached = hashlib.sha1(self.to_bytes()).hexdigest()[:16]
            self._index["fp"] = cached
        return cached

    def positions(self) -> int:
        return sum(f for bay in self.bays for _t, items in bay.tiers for _s, f in items)
