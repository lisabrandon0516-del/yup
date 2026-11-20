"""Score the active scenario. Beats are notes. Nothing here changes the company."""

from __future__ import annotations

from dataclasses import asdict

from .catalog import SCENARIOS
from .metrics import achieved, read
from .models import ScenarioRun

KEY = "ui_phase8_scenario"


def start(state, scenario_id: str) -> ScenarioRun:
    if scenario_id not in SCENARIOS:
        raise ValueError("Unknown scenario")
    run = ScenarioRun(scenario_id, int(getattr(state, "day", 1) or 1))
    for note in SCENARIOS[scenario_id].starting_notes:
        run.review_notes.append(note)
    _save(state, run)
    return run


def current(state) -> ScenarioRun | None:
    raw = getattr(state, KEY, None) if state is not None else None
    if not isinstance(raw, dict) or not raw.get("scenario_id"):
        return None
    return ScenarioRun(
        scenario_id=raw["scenario_id"],
        started_day=int(raw.get("started_day") or 1),
        status=str(raw.get("status") or "active"),
        objective_results=dict(raw.get("objective_results") or {}),
        fired_beats=list(raw.get("fired_beats") or []),
        board_confidence=int(raw.get("board_confidence") or 0),
        review_notes=list(raw.get("review_notes") or []),
    )


def update(state) -> ScenarioRun | None:
    run = current(state)
    if run is None or run.status != "active":
        return run
    scenario = SCENARIOS[run.scenario_id]
    elapsed = int(getattr(state, "day", 0) or 0) - run.started_day
    score = 0
    total = 0
    for objective in scenario.objectives:
        value = read(state, objective.metric)
        ok = achieved(value, objective.comparison, objective.target)
        expired = elapsed >= objective.deadline_day
        run.objective_results[objective.id] = {
            "value": value,
            "achieved": ok,
            "expired": expired,
            "target": objective.target,
            "comparison": objective.comparison,
        }
        total += objective.weight
        if ok:
            score += objective.weight
    for index, beat in enumerate(scenario.beats):
        token = f"{index}:{beat.title}"
        if elapsed >= beat.day_offset and token not in run.fired_beats:
            run.fired_beats.append(token)
            run.review_notes.append(beat.title)
    run.board_confidence = max(0, min(100, 30 + round(70 * score / max(1, total))))
    if elapsed >= scenario.duration_days:
        run.status = "completed" if score >= max(1, total * 0.6) else "failed"
        run.review_notes.append("Scenario closed with a structured performance review.")
    _save(state, run)
    return run


def _save(state, run: ScenarioRun) -> None:
    if state is None:
        return
    setattr(state, KEY, asdict(run))
