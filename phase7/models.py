"""Delegation policy. Dollars are whole numbers. Authority is not execution."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


AREAS = ("pricing", "inventory", "labor", "marketing", "store_operations")
LEVELS = ("manual", "recommend", "guardrails", "delegated")


@dataclass
class DelegationPolicy:
    area: str
    level: str = "recommend"
    objective: str = "balanced"
    min_cash_reserve: int = 0
    max_single_spend: int = 25000
    min_margin_pct: float = 0.0
    max_price_change_pct: float = 8.0
    require_review_if_confidence_below: float = 0.65
    enabled: bool = True


@dataclass
class DelegationBook:
    policies: dict[str, dict] = field(default_factory=dict)
    approvals: list[dict] = field(default_factory=list)
    activity: list[dict] = field(default_factory=list)

    def policy(self, area: str) -> DelegationPolicy:
        raw = self.policies.get(area)
        return DelegationPolicy(**raw) if raw else DelegationPolicy(area=area)

    def save_policy(self, policy: DelegationPolicy) -> None:
        self.policies[policy.area] = asdict(policy)
