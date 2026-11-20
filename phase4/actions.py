"""Typed workstation commands. Widgets emit these; the router calls the engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class WorkstationCommand:
    kind: str
    payload: dict[str, Any] = field(default_factory=dict)
    title: str = ""
    irreversible: bool = False
    refresh_pages: tuple[str, ...] = ()


@dataclass
class CommandResult:
    ok: bool
    message: str
    changed: bool = False
    data: dict[str, Any] = field(default_factory=dict)


class CommandRouter:
    """Approved engine and corporate calls. A refusal does not refresh the desks."""

    def __init__(self, state_provider: Callable[[], Any], refresh: Callable[[tuple[str, ...]], None] | None = None):
        self.state_provider = state_provider
        self.refresh = refresh or (lambda _pages: None)

    def execute(self, command: WorkstationCommand) -> CommandResult:
        state = self.state_provider()
        if state is None:
            return CommandResult(False, "No company is open.")
        handlers = {
            "place_order": self._place_order,
            "launch_campaign": self._launch_campaign,
            "set_assignment": self._set_assignment,
            "set_door_hours": self._set_door_hours,
            "set_hours": self._set_hours,
        }
        func = handlers.get(command.kind)
        if func is None:
            return CommandResult(False, f"Unsupported workstation command: {command.kind}")
        try:
            ok, message = func(state, **command.payload)
        except Exception as exc:
            return CommandResult(False, str(exc), False)
        if ok:
            self.refresh(command.refresh_pages)
        return CommandResult(bool(ok), message or command.title or command.kind, bool(ok))

    def _place_order(self, state, supplier_id: str, items: dict[str, int]):
        from open_late.engine import _add_order

        ok, message = _add_order(state, supplier_id, {key: int(value) for key, value in items.items() if int(value) > 0}, False)
        return ok, message

    def _launch_campaign(self, state, kind: str, tone: str, category: str, staff_id: str | None = None, door_id: str | None = None):
        from open_late.engine import launch_campaign

        before = state.campaign.days_left if state.campaign is not None else 0
        message = launch_campaign(state, kind, tone, category, staff_id, door_id)
        after = state.campaign.days_left if state.campaign is not None else 0
        ok = after > before or message.startswith("The platform rejected")
        return ok, message

    def _set_assignment(self, state, person_id: str, assignment: str):
        from open_late.engine import set_assignment

        message = set_assignment(state, person_id, assignment)
        return message.startswith("Shift set."), message

    def _set_door_hours(self, state, door_id: str, open_hour: int, close_hour: int):
        from open_late.corporate import set_door_hours

        message = set_door_hours(state, door_id, int(open_hour), int(close_hour))
        return message.startswith("Posted hours"), message

    def _set_hours(self, state, open_hour: int, close_hour: int):
        from open_late.engine import set_hours

        message = set_hours(state, int(open_hour), int(close_hour))
        return message.startswith("Open "), message
