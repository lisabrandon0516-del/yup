"""Player-facing chain brands for Back Office: Retail.

Logo files live in the brand pack; this module stores only the filename.
"""

from __future__ import annotations

from typing import Any

DEFAULT_CHAIN_ID = "megamart"

# Ids stay stable for saves. The names are the seven fascias on the picker.
CHAINS: list[dict[str, str]] = [
    {"id": "megamart", "name": "Northstar Market", "logo": "megamart.png"},
    {"id": "valuemax", "name": "Redline Retail", "logo": "valuemax.png"},
    {"id": "primestop", "name": "Harbor & Pine Market", "logo": "primestop.png"},
    {"id": "everyday", "name": "ValueForge", "logo": "everyday.png"},
    {"id": "shopgiant", "name": "Metrovale Retail", "logo": "shopgiant.png"},
    {"id": "bluestar", "name": "BrightBasket", "logo": "bluestar.png"},
    {"id": "allinone", "name": "Ironwood Mercantile", "logo": "allinone.png"},
]

_CHAIN_BY_ID = {entry["id"]: entry for entry in CHAINS}


def chain_info(state: Any) -> dict[str, str]:
    chain_id = getattr(state, "chain_id", "") or DEFAULT_CHAIN_ID
    entry = _CHAIN_BY_ID.get(chain_id)
    if entry is None:
        return dict(_CHAIN_BY_ID[DEFAULT_CHAIN_ID])
    return dict(entry)


def set_chain(state: Any, chain_id: str) -> str:
    if chain_id not in _CHAIN_BY_ID:
        raise ValueError(f"Unknown chain id: {chain_id}")
    state.chain_id = chain_id
    name = _CHAIN_BY_ID[chain_id]["name"]
    return f"Chain set to {name}."
