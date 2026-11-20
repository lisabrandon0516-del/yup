"""Store managers on the roster. Wages are already in dollars."""

from __future__ import annotations

from dataclasses import dataclass

from open_late.text import money


@dataclass(frozen=True)
class ManagerCard:
    id: str
    name: str
    area: str
    assignment: str
    available: bool
    wage: str


def managers(state) -> list[ManagerCard]:
    if state is None:
        return []
    doors = {door.id: door.city for door in getattr(state, "doors", []) or []}
    rows = []
    seen = set()
    for person in list(getattr(state, "managers", []) or []):
        seen.add(person.id)
        city = doors.get(person.door_id, "Company")
        rows.append(ManagerCard(
            person.id,
            person.name,
            "store_operations",
            city,
            bool(person.employed),
            money(person.wage),
        ))
    for door in getattr(state, "doors", []) or []:
        manager_id = getattr(door, "manager_id", "") or ""
        if manager_id and manager_id not in seen:
            seen.add(manager_id)
            rows.append(ManagerCard(manager_id, manager_id, "store_operations", door.city, True, "—"))
    return rows
