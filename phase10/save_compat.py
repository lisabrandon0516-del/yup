"""Optional save fields for delegation and the board scenario.

An older save has neither key. An empty book stays off the file.
"""

from __future__ import annotations

PHASE_KEYS = ("ui_phase7_delegation", "ui_phase8_scenario")


def extension_payload(state) -> dict:
    payload = {}
    for key in PHASE_KEYS:
        if not hasattr(state, key):
            continue
        value = getattr(state, key)
        if value:
            payload[key] = value
    return payload


def restore_extensions(state, payload: dict | None) -> None:
    for key, value in (payload or {}).items():
        if key in PHASE_KEYS:
            setattr(state, key, value)


def strip_extensions(payload: dict) -> dict:
    out = dict(payload or {})
    for key in PHASE_KEYS:
        out.pop(key, None)
    return out
