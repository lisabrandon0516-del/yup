"""A cause is stated only when yesterday's numbers support it."""

from __future__ import annotations

from open_late.text import money
from open_late.visiondeck.models import Hypothesis


def stockout_cause(state, category: str) -> tuple[str, str]:
    yesterday, prior = _category_sales(state, category)
    if prior is None or yesterday >= prior:
        return "The evidence is not enough to call it a sales drop.", "low"
    return f"{category} sales fell from {money(prior)} to {money(yesterday)}.", "high"


def _category_sales(state, category: str) -> tuple[int, int | None]:
    report = getattr(state, "last_report", None)
    if report is None:
        return 0, None
    yesterday = _amount(report, category)
    report_day = int(getattr(report, "day", 0) or 0)
    for item in reversed(list(getattr(state, "history", []) or [])):
        day = item.get("day", 0) if isinstance(item, dict) else getattr(item, "day", 0)
        if int(day or 0) < report_day:
            return yesterday, _amount(item, category)
    return yesterday, None


def _amount(report, category: str) -> int:
    by = report.get("by_category") if isinstance(report, dict) else getattr(report, "by_category", None)
    return int((by or {}).get(category, 0) or 0)


_INSUFFICIENT = {
    "stockout_pressure": "The evidence is not enough to call it a sales drop.",
    "cash_pressure": "The evidence is not enough to say why cash is short.",
    "labor_stress": "The evidence is not enough to say why labor is over the budget.",
    "supplier_delay": "The evidence is not enough to say why the order is late.",
    "competitor_price_pressure": "The evidence is not enough to say why. This is only what the company can see.",
    "competitor_expansion": "The evidence is not enough to say why. This is only what the company can see.",
    "margin_compression": "The evidence is not enough to say why the price sits under cost.",
    "debt_pressure": "The evidence is not enough to say why credit is tight.",
    "category_opportunity": "The evidence is not enough to say why sales rose.",
}


def diagnose(state, alerts=None) -> list[Hypothesis]:
    """Causes for the open alerts. Reading the company does not change it."""
    if state is None:
        return []
    if alerts is None:
        from open_late.visiondeck.signals import remembered

        alerts = remembered(state)
    found: list[Hypothesis] = []
    for alert in alerts:
        if getattr(alert, "status", "") == "resolved":
            continue
        carried = tuple(getattr(alert, "hypotheses", ()) or ())
        if carried:
            found.extend(carried)
            continue
        from open_late.visiondeck.observations import collect_observations

        found.extend(hypotheses_for(alert, collect_observations(state)))
    return found


def hypotheses_for(alert, rows) -> tuple[Hypothesis, ...]:
    found = [item for rule in RULES.get(alert.kind, ()) if (item := rule(alert, rows)) is not None]
    if any(item.status == "supported" for item in found):
        return tuple(found)
    if any(item.status == "insufficient" for item in found):
        return tuple(found)
    return tuple(found + [_insufficient(alert)])


def _sales_drop(alert, rows) -> Hypothesis:
    row = _metric(rows, "category_sales", alert.category)
    entity = str(alert.category or "")
    if row is None or row.previous_value is None:
        return _make(alert, "sales_drop", entity, _INSUFFICIENT["stockout_pressure"], "insufficient")
    previous = int(row.previous_value)
    current = int(row.observed_value)
    if current < previous:
        return _make(
            alert,
            "sales_drop",
            entity,
            f"{entity} sales fell from {money(previous)} to {money(current)}.",
            "supported",
        )
    if current > previous:
        return _make(
            alert,
            "sales_drop",
            entity,
            f"{entity} sales rose from {money(previous)} to {money(current)}.",
            "contradicted",
        )
    return _make(alert, "sales_drop", entity, _INSUFFICIENT["stockout_pressure"], "insufficient")


def _empty_shelf(alert, rows) -> Hypothesis | None:
    shelves = _on_hand(rows, alert.category)
    if not shelves:
        return None
    lost = {row.category: row.observed_value for row in rows if row.metric == "lost_stockout"}
    empty = [row for row in shelves if row.observed_value == 0 and int(lost.get(row.category, 0) or 0) > 0]
    if empty:
        row = empty[0]
        place = _meta(row, "place") or row.source_id
        return _make(
            alert,
            "stockout",
            row.category,
            f"{place} {row.category} is empty, 0 on hand.",
            "supported",
        )
    stocked = [row for row in shelves if row.observed_value > 0]
    if not stocked:
        return None
    row = stocked[0]
    place = _meta(row, "place") or row.source_id
    return _make(
        alert,
        "stockout",
        row.category,
        f"{place} {row.category} has {row.observed_value} on hand.",
        "contradicted",
    )


def _price_gap(alert, rows) -> Hypothesis | None:
    prices = [
        row for row in rows
        if row.metric == "price" and (not alert.category or row.category == alert.category)
    ]
    if not prices:
        return None
    under = [row for row in prices if int(_meta(row, "cost") or 0) > row.observed_value]
    if under:
        row = under[0]
        cost = int(_meta(row, "cost") or 0)
        name = _meta(row, "name") or row.source_id
        return _make(
            alert,
            "price_gap",
            row.source_id,
            f"{name} is priced at {money(row.observed_value)} against a cost of {money(cost)}.",
            "supported",
        )
    category = alert.category or prices[0].category
    return _make(alert, "price_gap", category, f"Prices in {category} cover cost.", "contradicted")


def _rival_price(alert, rows) -> Hypothesis | None:
    move = next((row for row in rows if row.metric == "public_move" and _price_war(row)), None)
    if move is None:
        return None
    text = _meta(move, "text")
    return _make(
        alert,
        "rival_price",
        move.source_id,
        f"{text} This is only what the company can see.",
        "supported",
        public=True,
    )


def _labor_over(alert, rows) -> Hypothesis | None:
    labor = [row for row in rows if row.metric == "labor" and int(_meta(row, "budget") or 0) > 0]
    if not labor:
        return None
    over = [row for row in labor if row.observed_value > int(_meta(row, "budget") or 0)]
    row = over[0] if over else labor[0]
    budget = int(_meta(row, "budget") or 0)
    place = _meta(row, "place") or row.source_id
    status = "supported" if row.observed_value > budget else "contradicted"
    return _make(
        alert,
        "labor",
        row.source_id,
        f"{place} labor was {row.observed_value} against a budget of {budget}.",
        status,
    )


def _payables(alert, rows) -> Hypothesis | None:
    late = [row for row in rows if row.metric == "late_order" or (row.metric == "late_payments" and row.observed_value > 0)]
    if late:
        row = late[0]
        name = _meta(row, "supplier") or row.source_id
        return _make(alert, "supplier", name, f"{name} is late.", "supported")
    payments = [row for row in rows if row.metric == "late_payments"]
    if payments and all(row.observed_value <= 0 for row in payments):
        return _make(alert, "supplier", payments[0].source_id, "Supplier payments are current.", "contradicted")
    return None


def _hours(alert, rows, metric: str, cause: str, label: str) -> Hypothesis | None:
    row = _metric(rows, metric, "")
    if row is None:
        return None
    status = "supported" if row.observed_value > 0 else "contradicted"
    amount = row.observed_value
    if status == "supported":
        text = f"{amount} {label}."
    else:
        text = f"{label} are not on the tape."
    return _make(alert, cause, "company", text, status)


def _overtime(alert, rows) -> Hypothesis | None:
    row = _metric(rows, "overtime", "")
    if row is None:
        return None
    if row.observed_value > 0:
        return _make(alert, "overtime", "company", f"{row.observed_value} overtime hours are on the tape.", "supported")
    return _make(alert, "overtime", "company", "Overtime hours are not on the tape.", "contradicted")


def _noshow(alert, rows) -> Hypothesis | None:
    return _hours(alert, rows, "noshow", "noshow", "no-shows")


def _lost_staff(alert, rows) -> Hypothesis | None:
    return _hours(alert, rows, "lost_staff", "lost_staff", "walked off the job")


def _late_account(alert, rows) -> Hypothesis:
    order = next((row for row in rows if row.metric == "late_order" and row.source_id == alert.source_id), None)
    if order is None:
        order = next((row for row in rows if row.metric == "late_order"), None)
    supplier = _meta(order, "supplier") if order is not None else alert.source_id
    account = next((row for row in rows if row.metric == "late_payments" and row.source_id == supplier), None)
    if account is not None and account.observed_value > 0:
        return _make(
            alert,
            "late_payments",
            supplier,
            f"{supplier} has {account.observed_value} late payments.",
            "supported",
        )
    if account is not None:
        return _make(alert, "late_payments", supplier, f"{supplier} payments are current.", "contradicted")
    return _make(
        alert,
        "late_payments",
        supplier,
        f"The evidence is not enough to say why {supplier} is late.",
        "insufficient",
    )


def _cash_short(alert, rows) -> Hypothesis | None:
    cash = _metric(rows, "cash", "")
    bill = _metric(rows, "obligations", "")
    if cash is None or bill is None:
        return None
    if cash.observed_value < bill.observed_value:
        return _make(
            alert,
            "cash_short",
            "company",
            f"Cash is {money(cash.observed_value)}. The week needs {money(bill.observed_value)}.",
            "supported",
        )
    return _make(alert, "cash_short", "company", "Cash covers the week's bills.", "contradicted")


def _player_empty(alert, rows) -> Hypothesis | None:
    lost = {row.category: row.observed_value for row in rows if row.metric == "lost_stockout"}
    for row in rows:
        if row.metric != "on_hand" or row.observed_value != 0:
            continue
        if int(lost.get(row.category, 0) or 0) <= 0:
            continue
        place = _meta(row, "place") or row.source_id
        return _make(
            alert,
            "player_stockout",
            row.category,
            f"{place} {row.category} is empty, 0 on hand.",
            "supported",
        )
    return None


def _rival_motive(alert, rows) -> Hypothesis:
    return _make(
        alert,
        "rival_motive",
        alert.source_id,
        "The evidence is not enough to say why. This is only what the company can see.",
        "insufficient",
    )


def _named_gap(alert, rows) -> Hypothesis:
    return _make(alert, "unexplained", alert.category or alert.source_id, _line(alert), "insufficient")


def _insufficient(alert) -> Hypothesis:
    return _make(alert, "unexplained", alert.category or alert.source_id, _line(alert), "insufficient")


def _line(alert) -> str:
    return _INSUFFICIENT.get(alert.kind, "The evidence is not enough to call a cause.")


def _make(alert, cause, entity, explanation, status, *, public=False) -> Hypothesis:
    if status == "supported":
        support, contradiction, confidence = (55, 0, "moderate") if public else (80, 0, "high")
    elif status == "contradicted":
        support, contradiction, confidence = 0, 80, "low"
    else:
        support, contradiction, confidence = 0, 0, "low"
    return Hypothesis(
        f"{alert.id}:{cause}",
        alert.id,
        cause,
        str(entity or ""),
        explanation,
        support,
        contradiction,
        confidence,
        status,
    )


def _on_hand(rows, category: str) -> list:
    return [
        row for row in rows
        if row.metric == "on_hand" and (not category or row.category == category)
    ]


def _metric(rows, metric: str, category: str):
    found = [
        row for row in rows
        if row.metric == metric and (not category or row.category == category)
    ]
    return found[-1] if found else None


def _price_war(row) -> bool:
    kind = _meta(row, "kind") or row.category
    text = _meta(row, "text")
    blob = f"{kind} {text}".lower()
    return "price war" in blob or kind in {"start_price_war", "end_price_war"}


def _meta(row, key: str) -> str:
    if row is None:
        return ""
    for name, value in row.metadata:
        if name == key:
            return value
    return ""


RULES = {
    "stockout_pressure": (_sales_drop,),
    "sales_decline": (_empty_shelf, _price_gap, _rival_price),
    "traffic_decline": (_empty_shelf, _price_gap, _rival_price),
    "category_opportunity": (_named_gap,),
    "cash_pressure": (_labor_over, _payables),
    "debt_pressure": (_cash_short,),
    "labor_stress": (_overtime, _noshow, _lost_staff),
    "supplier_delay": (_late_account,),
    "customer_switching": (_rival_price,),
    "margin_compression": (_named_gap,),
    "competitor_price_pressure": (_rival_motive, _player_empty),
    "competitor_expansion": (_rival_motive, _player_empty),
}
