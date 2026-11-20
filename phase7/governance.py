"""Guardrails. A pass still does not change the company."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import DelegationPolicy


@dataclass(frozen=True)
class DelegatedProposal:
    id: str
    area: str
    title: str
    command_kind: str
    payload: dict[str, Any]
    confidence: float
    expected_spend: int = 0
    expected_margin_pct: float | None = None
    reason: str = ""


@dataclass(frozen=True)
class GovernanceDecision:
    status: str
    reason: str
    needs_human: bool


def evaluate(state, policy: DelegationPolicy, proposal: DelegatedProposal) -> GovernanceDecision:
    if not policy.enabled or policy.level == "manual":
        return GovernanceDecision("manual", "Delegation is off for this area.", True)
    if proposal.confidence < policy.require_review_if_confidence_below:
        return GovernanceDecision("review", "Confidence is below the review threshold.", True)
    cash = int(getattr(state, "cash", 0) or 0)
    if proposal.expected_spend > policy.max_single_spend:
        return GovernanceDecision("review", "The proposal is over the single-decision limit.", True)
    if cash - proposal.expected_spend < policy.min_cash_reserve:
        return GovernanceDecision("blocked", "The cash-reserve guardrail would be breached.", True)
    if proposal.expected_margin_pct is not None and proposal.expected_margin_pct < policy.min_margin_pct:
        return GovernanceDecision("blocked", "The minimum margin guardrail would be breached.", True)
    if policy.level == "recommend":
        return GovernanceDecision("review", "A recommendation waits for approval.", True)
    if policy.level == "guardrails":
        return GovernanceDecision("review", "Inside the guardrails, and still waiting for approval.", True)
    return GovernanceDecision("delegated", "Inside delegated authority. Nothing has been executed.", False)
