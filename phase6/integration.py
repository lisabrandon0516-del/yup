"""Install the deep drill on the desks that are already on the shell."""

from __future__ import annotations


def attach(registry, state_provider, host=None):
    from .controller import DeepDrillController

    return DeepDrillController(registry, state_provider, host)
