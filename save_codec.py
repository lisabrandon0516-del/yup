"""Save diet: a lossless, deterministic packing of the state JSON before zlib.

Two rewrites, both exactly reversible (key order included):

* a dict keyed only by product ids (8+ keys), e.g. ``units_by_product``, becomes
  ``{"@P": [d0, v0, d1, v1, ...]}``: ``d`` is the signed step in the save's product order
  (``"@order"`` at the top) from the previous key, so the ids are written once per save.
* a list of 4+ dicts that share the same keys in the same order becomes
  ``{"@T": [keys], "r": [[values], ...]}`` (one header instead of a key per row).

A real dict whose keys start with "@" is wrapped as ``{"@E": {...}}`` so it never collides.
The blob is ``MAGIC + zlib(json)``. Only games with shelves on are packed; every other save
stays plain JSON text, byte for byte, and plain rows always load.
"""

from __future__ import annotations

import json
import zlib
from typing import Any

MAGIC = b"RRS1\n"
_MIN_P = 8
_MIN_T = 4


def _enc(o: Any, pos: dict[str, int]) -> Any:
    if isinstance(o, dict):
        if len(o) >= _MIN_P and all(k in pos for k in o):
            out: list[Any] = []
            last = -1
            for k, v in o.items():
                i = pos[k]
                out.append(i - last)
                out.append(_enc(v, pos))
                last = i
            return {"@P": out}
        body = {k: _enc(v, pos) for k, v in o.items()}
        if any(k[:1] == "@" for k in o):
            return {"@E": body}
        return body
    if isinstance(o, list):
        if len(o) >= _MIN_T and all(isinstance(x, dict) for x in o):
            keys = list(o[0])
            if keys and not any(k[:1] == "@" for k in keys) and all(list(x) == keys for x in o):
                return {"@T": keys, "r": [[_enc(x[k], pos) for k in keys] for x in o]}
        return [_enc(x, pos) for x in o]
    return o


def _dec(o: Any, order: list[str]) -> Any:
    if isinstance(o, dict):
        if "@P" in o and len(o) == 1:
            seq = o["@P"]
            out: dict[str, Any] = {}
            last = -1
            for j in range(0, len(seq), 2):
                last += seq[j]
                out[order[last]] = _dec(seq[j + 1], order)
            return out
        if "@T" in o and len(o) == 2 and "r" in o:
            keys = o["@T"]
            return [{k: _dec(v, order) for k, v in zip(keys, row)} for row in o["r"]]
        if "@E" in o and len(o) == 1:
            return {k: _dec(v, order) for k, v in o["@E"].items()}
        return {k: _dec(v, order) for k, v in o.items()}
    if isinstance(o, list):
        return [_dec(x, order) for x in o]
    return o


def pack_json(text: str) -> bytes:
    data = json.loads(text)
    order = list((data.get("products") or {}).keys()) if isinstance(data, dict) else []
    pos = {p: i for i, p in enumerate(order)}
    body = {"@order": order, "s": _enc(data, pos)}
    raw = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return MAGIC + zlib.compress(raw, 6)


def unpack_json(blob: bytes) -> str:
    if not blob.startswith(MAGIC):
        raise ValueError("not a packed save")
    body = json.loads(zlib.decompress(blob[len(MAGIC):]).decode("utf-8"))
    return json.dumps(_dec(body["s"], body["@order"]), separators=(",", ":"), ensure_ascii=False)


def pack_state(state) -> bytes:
    """Packed blob for any state (deterministic for a given state)."""
    return pack_json(state.model_dump_json())


def unpack_state(raw):
    """GameState from pack_state's blob or plain JSON (str or bytes)."""
    from open_late.models import GameState

    if isinstance(raw, (bytes, bytearray, memoryview)):
        data = bytes(raw)
        text = unpack_json(data) if data.startswith(MAGIC) else data.decode("utf-8")
    else:
        text = raw
    return GameState.model_validate_json(text)


def encode_save(state):
    """What SaveStore writes: plain JSON text while shelves are off (byte-identical to p2),
    the packed blob once they are on."""
    if not getattr(state, "shelves", None):
        return state.model_dump_json()
    return pack_state(state)


def decode_save(raw):
    return unpack_state(raw)
