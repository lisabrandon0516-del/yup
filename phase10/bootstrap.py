"""Bind the harness to the shell that is already built.

Calling this does not install a second copy of any desk and does not run a
price change, an order, or a scenario.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .audit import run


@dataclass
class FeatureFlags:
    phase2: bool = True
    phase3: bool = True
    phase4_mutations: bool = False
    phase5_connected: bool = True
    phase6_drilldowns: bool = True
    phase7_delegation: bool = False
    phase8_scenarios: bool = False
    phase9_history: bool = True


@dataclass
class IntegratedUI:
    audit: dict
    registry: object | None = None
    workstation_controller: object | None = None
    connected_center: object | None = None
    deep_drill: object | None = None
    extras: dict = field(default_factory=dict)


def bootstrap(stack, state_provider, navigator=None, host=None, flags: FeatureFlags | None = None) -> IntegratedUI:
    flags = flags or FeatureFlags()
    result = IntegratedUI(run())
    if host is None or not result.audit["ready"]:
        return result
    result.registry = getattr(host, "page_registry", None)
    if flags.phase4_mutations:
        result.workstation_controller = getattr(host, "workstation_controller", None)
    if flags.phase5_connected:
        result.connected_center = getattr(host, "connected_center", None)
    if flags.phase6_drilldowns:
        result.deep_drill = getattr(host, "deep_drill", None)
    extras = {}
    if flags.phase7_delegation:
        extras["delegation"] = getattr(host, "delegation", None)
    if flags.phase8_scenarios:
        extras["board"] = getattr(host, "board", None)
    if flags.phase9_history:
        extras["history"] = getattr(host, "archive", None)
    result.extras = {key: value for key, value in extras.items() if value is not None}
    return result
