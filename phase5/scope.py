"""Company, region, and store scope for the connected desks."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Scope:
    kind: str = "company"
    ident: str | None = None


def visible_store_ids(state, scope: Scope) -> list[str]:
    try:
        from open_late.ui.hq_adapter import scoped_store_ids

        kind = "all" if scope.kind == "company" else scope.kind
        return scoped_store_ids(state, kind, scope.ident)
    except Exception:
        return [getattr(door, "id", "") for door in getattr(state, "doors", []) or []]


def keep_row(row: dict, scope: Scope) -> bool:
    if scope.kind in ("company", "all") or not scope.ident:
        return True
    if scope.kind == "store":
        return row.get("store") == scope.ident or row.get("store_id") == scope.ident or row.get("id") == scope.ident
    if scope.kind == "region":
        return row.get("region") == scope.ident
    return True
