"""SQLite saves. One row per shop, the whole state as JSON."""

from __future__ import annotations

import json
import lzma
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from open_late.models import GameState


# Rival-AI saves (save_version 5+) are written as an LZMA blob. AI-off saves stay
# plain JSON text, byte-identical to save_version 4, so older builds read them.
ZSAVE_MAGIC = b"RRZ2"
ZSAVE_PRESET = 6


_CATALOG: dict[str, dict] | None = None


def _catalog_baseline() -> dict[str, dict]:
    """Authored products (incl. house label) as saved JSON: the deterministic baseline."""
    global _CATALOG
    if _CATALOG is None:
        from open_late.content import LABEL_PRODUCTS, PRODUCTS

        _CATALOG = {p.id: json.loads(p.model_dump_json()) for p in list(PRODUCTS) + list(LABEL_PRODUCTS)}
    return _CATALOG


def encode_state(state: GameState) -> str | bytes:
    if getattr(state, "rival_ai", None) is None:
        from open_late.save_codec import encode_save  # Lite shelves on: packed blob; off: plain JSON

        return encode_save(state)
    text = state.model_dump_json()
    # Store only the products that differ from the authored catalog.
    data = json.loads(text)
    base = _catalog_baseline()
    products = data.get("products") or {}
    data["products"] = {
        "__order__": list(products),
        "__delta__": {pid: row for pid, row in products.items() if base.get(pid) != row},
    }
    block = data.get("rival_ai")
    if isinstance(block, dict) and isinstance(block.get("packed"), str) and block["packed"]:
        # Compress once: the AI block goes in as plain JSON, not nested base64.
        from open_late.rival_ai import packed_to_payload

        block["packed"] = {"__json__": packed_to_payload(block["packed"])}
    body = json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return ZSAVE_MAGIC + lzma.compress(body, preset=ZSAVE_PRESET)


def decode_state(raw: str | bytes | memoryview) -> GameState:
    if isinstance(raw, memoryview):
        raw = bytes(raw)
    if isinstance(raw, bytes):
        if raw.startswith(ZSAVE_MAGIC):
            data = json.loads(lzma.decompress(raw[len(ZSAVE_MAGIC):]).decode("utf-8"))
            packed = data.get("products") or {}
            if "__order__" in packed:
                base, delta = _catalog_baseline(), packed.get("__delta__") or {}
                data["products"] = {pid: delta.get(pid, base.get(pid)) for pid in packed["__order__"]}
            block = data.get("rival_ai")
            if isinstance(block, dict) and isinstance(block.get("packed"), dict):
                from open_late.rival_ai import payload_to_packed

                block["packed"] = payload_to_packed(block["packed"]["__json__"])
            return GameState.model_validate(data)
        from open_late.save_codec import MAGIC, unpack_state  # Lite shelves blob (AI off)

        if raw.startswith(MAGIC):
            return unpack_state(raw)
        raw = raw.decode("utf-8")
    return GameState.model_validate_json(raw)


def encoded_size(state: GameState) -> int:
    data = encode_state(state)
    return len(data) if isinstance(data, bytes) else len(data.encode("utf-8"))


def default_path() -> Path:
    override = os.environ.get("OPEN_LATE_DB")
    if override:
        return Path(override)
    return Path.home() / ".open_late" / "saves.sqlite"


class SaveStore:
    def __init__(self, path: Path | None = None):
        self.path = path or default_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS saves (
                    slot TEXT PRIMARY KEY,
                    shop_name TEXT NOT NULL,
                    day INTEGER NOT NULL,
                    cash INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    state_json TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def save(self, state: GameState) -> None:
        stamp = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO saves (slot, shop_name, day, cash, updated_at, state_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(slot) DO UPDATE SET
                    shop_name = excluded.shop_name,
                    day = excluded.day,
                    cash = excluded.cash,
                    updated_at = excluded.updated_at,
                    state_json = excluded.state_json
                """,
                (state.slot, state.shop_name, state.day, state.cash, stamp, encode_state(state)),
            )

    def load(self, slot: str) -> GameState:
        with self._connect() as conn:
            row = conn.execute("SELECT state_json FROM saves WHERE slot = ?", (slot,)).fetchone()
        if row is None:
            raise KeyError(slot)
        from open_late.content import merge_catalog

        return merge_catalog(decode_state(row[0]))

    def list_saves(self) -> list[tuple[str, str, int, int, str]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT slot, shop_name, day, cash, updated_at FROM saves ORDER BY updated_at DESC"
            ).fetchall()
        return [(slot, name, day, cash, updated) for slot, name, day, cash, updated in rows]

    def delete(self, slot: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM saves WHERE slot = ?", (slot,))

    def rename(self, slot: str, shop_name: str) -> None:
        state = self.load(slot)
        state.shop_name = shop_name.strip() or state.shop_name
        self.save(state)

    def duplicate(self, slot: str) -> str:
        state = self.load(slot)
        state.slot = uuid.uuid4().hex
        self.save(state)
        return state.slot

    def store_count(self, slot: str) -> int:
        try:
            state = self.load(slot)
        except Exception:
            return 1
        if getattr(state, "mode", "shop") != "corporate":
            return 1
        doors = [door for door in (state.doors or []) if getattr(door, "status", "") != "closed"]
        return max(1, len(doors) or 1)
