"""The four board scenarios. Targets are dollars where the metric is money."""

from __future__ import annotations

from .models import Objective, Scenario, ScenarioBeat

SCENARIOS = {
    "first_expansion": Scenario(
        "first_expansion",
        "The First Expansion",
        "Open a second location without destabilizing the original operation.",
        56,
        (
            Objective("cash_floor", "Protect liquidity", "cash", ">=", 750000, 56, 3, penalty="Financing restrictions"),
            Objective("second_store", "Open the second store", "open_stores", ">=", 2, 42, 3),
            Objective("profitability", "Return the chain to profit", "weekly_profit", ">=", 0, 56, 2),
        ),
        (
            ScenarioBeat(7, "board", "Expansion review"),
            ScenarioBeat(28, "market", "Competitor notices the project"),
        ),
        ("The board expects disciplined growth.", "Do not sacrifice the first store."),
        ("expansion", "finance"),
    ),
    "price_war": Scenario(
        "price_war",
        "The Price War",
        "Defend customer traffic while a rival applies sustained price pressure.",
        42,
        (
            Objective("share", "Protect customer traffic", "weekly_visits", ">=", 3500, 42, 3),
            Objective("margin", "Preserve profitability", "weekly_profit", ">=", 0, 42, 3),
            Objective("availability", "Avoid product holes", "stockouts", "<=", 4, 42, 2),
        ),
        (
            ScenarioBeat(0, "rival", "Rival price cut begins"),
            ScenarioBeat(14, "supplier", "Supplier capacity tightens"),
        ),
        ("Matching every price may destroy the economics.", "Differentiation remains available."),
        ("competition", "pricing"),
    ),
    "supply_shock": Scenario(
        "supply_shock",
        "Supply Shock",
        "Operate through a regional availability disruption.",
        35,
        (
            Objective("stockouts", "Contain stockouts", "stockouts", "<=", 8, 35, 3),
            Objective("cash", "Keep emergency liquidity", "cash", ">=", 400000, 35, 2),
            Objective("customers", "Maintain weekly visits", "weekly_visits", ">=", 2500, 35, 2),
        ),
        (
            ScenarioBeat(0, "supplier", "Regional disruption begins"),
            ScenarioBeat(10, "supplier", "Alternative supply offer"),
        ),
        ("Lead times are unstable.", "Emergency purchases may carry poor terms."),
        ("supply", "inventory"),
    ),
    "turnaround": Scenario(
        "turnaround",
        "Corporate Turnaround",
        "Restore an overextended chain without losing the remaining customer base.",
        84,
        (
            Objective("profit", "Achieve weekly profit", "weekly_profit", ">=", 0, 84, 4),
            Objective("cash", "Rebuild cash reserves", "cash", ">=", 1000000, 84, 3),
            Objective("closures", "Limit store closures", "open_stores", ">=", 2, 84, 2),
        ),
        (
            ScenarioBeat(0, "board", "Turnaround mandate"),
            ScenarioBeat(21, "lender", "Credit review"),
            ScenarioBeat(56, "board", "Midpoint review"),
        ),
        ("The board has limited patience.", "Short-term cuts can create long-term damage."),
        ("turnaround", "finance"),
    ),
}
