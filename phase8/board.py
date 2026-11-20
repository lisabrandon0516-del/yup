"""The board report for the open scenario."""

from __future__ import annotations

from dataclasses import dataclass

from .catalog import SCENARIOS
from .engine import update


@dataclass(frozen=True)
class BoardReport:
    scenario: str
    status: str
    confidence: int
    objectives: tuple[dict, ...]
    notes: tuple[str, ...]


def report(state) -> BoardReport | None:
    run = update(state)
    if run is None:
        return None
    scenario = SCENARIOS[run.scenario_id]
    rows = []
    for objective in scenario.objectives:
        result = run.objective_results.get(objective.id, {})
        rows.append({
            "id": objective.id,
            "title": objective.title,
            "metric": objective.metric,
            "value": result.get("value", 0),
            "target": objective.target,
            "comparison": objective.comparison,
            "achieved": result.get("achieved", False),
            "deadline": objective.deadline_day,
            "weight": objective.weight,
        })
    return BoardReport(scenario.title, run.status, run.board_confidence, tuple(rows), tuple(run.review_notes))
