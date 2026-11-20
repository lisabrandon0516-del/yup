"""Inbox notes stored on the save."""

from __future__ import annotations

from open_late.models import Choice, GameState, InboxMessage


def add(
    state: GameState,
    *,
    kind: str,
    title: str,
    body: str,
    urgent: bool = False,
    choices: list[Choice] | None = None,
) -> InboxMessage:
    message = InboxMessage(
        id=f"m{state.next_message_id}",
        day=state.day,
        kind=kind,
        title=title,
        body=body,
        urgent=urgent,
        choices=choices or [],
    )
    state.next_message_id += 1
    state.inbox.append(message)
    trim(state)
    return message


def trim(state: GameState, limit: int = 80) -> None:
    """Keep urgent notes and recent choices. Older unread notes do not pile up for a year."""
    inbox = state.inbox
    if len(inbox) <= limit:
        return
    floor = int(state.day) - 14
    important = [
        message
        for message in inbox
        if not message.resolved and (message.urgent or (message.choices and int(message.day) >= floor))
    ]
    important_ids = {message.id for message in important}
    rest = [message for message in inbox if message.id not in important_ids]
    room = max(0, limit - len(important))
    state.inbox = rest[-room:] + important
