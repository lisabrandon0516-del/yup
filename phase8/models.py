"""Board objectives. A scenario is a scorecard, not a change to the company."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Objective:
    id: str
    title: str
    metric: str
    comparison: str
    target: float
    deadline_day: int
    weight: int = 1
    scope: str = "company"
    reward: str = "Board confidence"
    penalty: str = "Board concern"


@dataclass(frozen=True)
class ScenarioBeat:
    day_offset: int
    kind: str
    title: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    description: str
    duration_days: int
    objectives: tuple[Objective, ...]
    beats: tuple[ScenarioBeat, ...] = ()
    starting_notes: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


@dataclass
class ScenarioRun:
    scenario_id: str
    started_day: int
    status: str = "active"
    objective_results: dict[str, dict] = field(default_factory=dict)
    fired_beats: list[str] = field(default_factory=list)
    board_confidence: int = 50
    review_notes: list[str] = field(default_factory=list)
