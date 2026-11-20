"""Records the company is allowed to keep. These stay off the save."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Observation:
    id: str
    day: int
    source_type: str
    source_id: str
    category: str
    metric: str
    observed_value: int
    previous_value: int | None = None
    region: str = ""
    store_id: str = ""
    visibility: str = "company"
    reliability: int = 80
    freshness: int = 0
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Hypothesis:
    """One possible cause. Support and contradiction are counted apart."""

    id: str
    signal_id: str
    cause_type: str
    cause_entity: str
    explanation: str
    support_score: int
    contradiction_score: int
    confidence: str
    status: str


@dataclass(frozen=True)
class Forecast:
    """A range for one alert. The wording is a projection, not an outcome."""

    id: str
    signal_id: str
    scope: str
    metric: str
    horizon: int
    baseline: int
    low_case: int
    expected_case: int
    high_case: int
    confidence: str
    assumptions: str
    created_at: int
    expires_at: int
    category: str = ""
    source_id: str = ""
    label: str = ""
    style: str = "count"
    actual: int | None = None
    verdict: str = ""


@dataclass(frozen=True)
class Recommendation:
    """One option. It names an action the game can perform and does not perform it."""

    id: str
    title: str
    problem_id: str
    action_family: str
    target: str
    expected_benefit: str
    financial_cost: int
    operational_cost: str
    execution_delay: int
    risk: str
    confidence: str
    reversibility: str
    prerequisites: tuple[str, ...]
    side_effects: str
    product_id: str = ""
    quantity: int = 0
    price: int = 0


@dataclass(frozen=True)
class Alert:
    """One condition worth attention. Severity and confidence are separate."""

    id: str
    kind: str
    day: int
    scope: str
    severity: str
    confidence: str
    observation_ids: tuple[str, ...]
    current_value: int
    baseline_value: int
    delta: int
    trend: str
    first_seen: int
    last_seen: int
    status: str
    evidence: str
    source_id: str = ""
    category: str = ""
    confidence_score: int = 0
    hypotheses: tuple[Hypothesis, ...] = ()
    forecast: Forecast | None = None
    prior_forecast: Forecast | None = None
    recommendations: tuple[Recommendation, ...] = ()
    memory: str = ""


@dataclass(frozen=True)
class Signal:
    id: str
    kind: str
    day: int
    first_seen: int
    last_seen: int
    status: str
    category: str
    source_id: str
    on_hand: int
    lost: int
    confidence: str
    evidence: str
    action: str = ""
    product_id: str = ""
    quantity: int = 0
