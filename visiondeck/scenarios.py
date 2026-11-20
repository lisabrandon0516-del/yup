"""Compare the options on an alert, then commit one through the game."""

from __future__ import annotations

from dataclasses import dataclass

from open_late.visiondeck.forecasts import projection_text, score_text


@dataclass(frozen=True)
class Scenario:
    recommendation_id: str
    action_family: str
    title: str
    financial_cost: int
    execution_delay: int
    risk: str
    expected_benefit: str
    projection: str


def compare(alert) -> tuple[Scenario, ...]:
    """The options side by side. Nothing is sent, ordered, or repriced."""
    forecast = getattr(alert, "forecast", None)
    projection = projection_text(forecast) if forecast is not None else ""
    return tuple(
        Scenario(
            item.id,
            item.action_family,
            item.title,
            int(item.financial_cost),
            int(item.execution_delay),
            item.risk,
            item.expected_benefit,
            projection,
        )
        for item in (getattr(alert, "recommendations", ()) or ())
    )


def commit(state, alert, recommendation_id: str) -> str:
    """Run the chosen option through the simulation. An unknown option is refused."""
    choice = next((item for item in (alert.recommendations or ()) if item.id == recommendation_id), None)
    if choice is None:
        return "That option is not on this alert."
    if choice.action_family == "do_nothing":
        _remember(state, alert, choice.title)
        return choice.title
    if choice.action_family == "allocate":
        from open_late.corporate import allocate

        text = allocate(state, choice.target, {choice.product_id: int(choice.quantity)})
        if text.startswith("Sent "):
            _remember(state, alert, choice.title)
        return text
    if choice.action_family == "place_order":
        from open_late.engine import place_order

        text = place_order(state, choice.target, {choice.product_id: int(choice.quantity)})
        if text.startswith("Order placed"):
            _remember(state, alert, choice.title)
        return text
    if choice.action_family == "set_price":
        from open_late.engine import set_price

        text = set_price(state, choice.product_id, int(choice.price))
        if text == "":
            _remember(state, alert, choice.title)
            return choice.title
        return text
    return "That option is not on this alert."


def capture(state, alerts) -> None:
    """Write yesterday's held or missed line onto the choice that was committed."""
    notes = getattr(state, "decisions", None)
    if not notes:
        return
    today = int(getattr(state, "day", 0) or 0)
    by_id = {getattr(item, "id", ""): item for item in alerts}
    for note in notes:
        if getattr(note, "kind", "") != "decision_lab" or getattr(note, "result", ""):
            continue
        if int(getattr(note, "day", 0) or 0) != today - 1:
            continue
        alert = by_id.get(getattr(note, "ref", ""))
        forecast = getattr(alert, "prior_forecast", None) if alert is not None else None
        if forecast is None or not forecast.verdict:
            continue
        note.result = score_text(forecast)


def _remember(state, alert, title: str) -> None:
    from open_late.books import note_decision

    if getattr(state, "decisions", None) is None:
        state.decisions = []
    forecast = getattr(alert, "forecast", None)
    projection = projection_text(forecast) if forecast is not None else title
    options = ", ".join(item.title for item in (getattr(alert, "recommendations", ()) or ()) if item.title)
    note_decision(
        state,
        "decision_lab",
        f"Chose {title} Options: {options}. {projection}",
        ref=alert.id,
        before_units=int(forecast.expected_case) if forecast is not None else -1,
    )
