"""The delegation book lives on the company and stays off the save until it has something in it."""

from __future__ import annotations

from .models import AREAS, DelegationBook, DelegationPolicy

KEY = "ui_phase7_delegation"


def book(state) -> DelegationBook:
    raw = getattr(state, KEY, None) if state is not None else None
    if isinstance(raw, dict) and raw.get("policies"):
        return DelegationBook(
            policies=dict(raw.get("policies") or {}),
            approvals=list(raw.get("approvals") or []),
            activity=list(raw.get("activity") or []),
        )
    result = DelegationBook()
    for area in AREAS:
        result.save_policy(DelegationPolicy(area=area))
    return result


def serialize(value: DelegationBook) -> dict:
    return {"policies": dict(value.policies), "approvals": list(value.approvals), "activity": list(value.activity)}


def store(state, value: DelegationBook) -> None:
    if state is None:
        return
    setattr(state, KEY, serialize(value))
