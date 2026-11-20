"""Connect workstation signals to the engine, then refresh the desks that the change touches."""

from __future__ import annotations

from .actions import CommandRouter


class WorkstationController:
    def __init__(self, registry, state_provider, on_changed=None):
        self.registry = registry
        self.state_provider = state_provider
        self.on_changed = on_changed
        self.router = CommandRouter(state_provider, self.refresh)
        for page in registry.pages.values():
            signal = getattr(page, "command_requested", None)
            if signal is not None:
                signal.connect(lambda command, page=page: self._execute(page, command))

    def _execute(self, page, command) -> None:
        result = self.router.execute(command)
        if result.ok and self.on_changed is not None:
            self.on_changed()
        page.notify_result(result)

    def refresh(self, page_ids=()) -> None:
        state = self.state_provider()
        targets = page_ids or tuple(self.registry.pages)
        for page_id in targets:
            page = self.registry.pages.get(page_id)
            if page is not None and state is not None:
                page.load(state)
