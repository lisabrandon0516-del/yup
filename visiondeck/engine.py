"""Signal engine. One id per condition, with a lifecycle and evidence."""

from __future__ import annotations

from dataclasses import replace

from open_late.text import money
from open_late.visiondeck.confidence import rate
from open_late.visiondeck.balance import bars_for, limit_alerts, widen_forecast
from open_late.visiondeck.models import Alert, Observation
from open_late.visiondeck.observations import collect_observations
from open_late.visiondeck.priorities import rank

_SEVERITY_ORDER = {
    "critical": 0,
    "high": 1,
    "moderate": 2,
    "watch": 3,
    "opportunity": 4,
    "information": 5,
}


def detect(state, prior=None) -> list[Alert]:
    if state is None:
        return []
    day = int(getattr(state, "day", 0) or 0)
    rows = collect_observations(state)
    bars = bars_for(state)
    drafts = _drafts(rows, day, bars)
    from open_late.visiondeck.diagnosis import hypotheses_for
    from open_late.visiondeck.forecasts import project, settle
    from open_late.visiondeck.recommendations import recommend

    known = {getattr(item, "id", ""): item for item in (prior or [])}
    found: set[str] = set()
    alerts: list[Alert] = []
    for draft in drafts:
        earlier = known.get(draft.id)
        from open_late.visiondeck.memory import calibrate, recall

        forecast = project(draft, state, rows, day)
        if forecast is not None:
            forecast = replace(forecast, confidence=calibrate(state, draft.kind, forecast.confidence))
            forecast = widen_forecast(forecast, state, draft.kind)
        draft = replace(
            draft,
            hypotheses=hypotheses_for(draft, rows),
            forecast=forecast,
            prior_forecast=settle(earlier, rows, day),
            memory=recall(state, draft),
        )
        draft = replace(draft, recommendations=recommend(draft, state))
        found.add(draft.id)
        alerts.append(_continue(draft, earlier))
    for ident, earlier in known.items():
        if ident in found or getattr(earlier, "status", "") == "resolved":
            continue
        alerts.append(replace(
            earlier,
            day=day,
            last_seen=day,
            status="resolved",
            evidence=f"Resolved. {getattr(earlier, 'evidence', '')}",
            forecast=None,
            prior_forecast=settle(earlier, rows, day) or getattr(earlier, "prior_forecast", None),
        ))
    alerts.sort(key=lambda item: (_SEVERITY_ORDER.get(item.severity, 9), item.kind, item.id))
    alerts = limit_alerts(alerts, bars.per_kind)
    from open_late.visiondeck.scenarios import capture

    capture(state, alerts)
    return alerts


def _drafts(rows: list[Observation], day: int, bars) -> list[Alert]:
    drafts = []
    drafts.extend(_stockouts(rows, day, bars))
    drafts.extend(_category_moves(rows, day, bars))
    drafts.extend(_traffic(rows, day, bars))
    drafts.extend(_cash(rows, day))
    drafts.extend(_debt(rows, day))
    drafts.extend(_labor(rows, day))
    drafts.extend(_suppliers(rows, day))
    drafts.extend(_walkers(rows, day, bars))
    drafts.extend(_margins(rows, day))
    drafts.extend(_rivals(rows, day))
    return drafts


def _stockouts(rows: list[Observation], day: int, bars) -> list[Alert]:
    lost = {row.category: row for row in rows if row.metric == "lost_stockout" and row.observed_value > 0}
    alerts = []
    for row in rows:
        if row.metric != "on_hand" or row.observed_value != 0:
            continue
        turned = lost.get(row.category)
        if turned is None:
            continue
        count = int(turned.observed_value)
        if count < bars.stockout_floor:
            continue
        place = _meta(row, "place") or row.source_id
        score, confidence = rate(row.reliability, measured=True)
        severity = rank(
            customer=3 if count >= bars.stockout_critical else 2 if count >= bars.stockout_high else 1
        )
        alerts.append(_alert(
            f"stockout:{row.source_id}:{row.category}",
            "stockout_pressure",
            day,
            "store" if row.source_type == "store" else "company",
            severity,
            confidence,
            score,
            (row.id, turned.id),
            count,
            int(turned.previous_value or 0),
            row.source_id,
            row.category,
            f"{place} {row.category} is empty, 0 on hand. {count} turned away for an empty {row.category} shelf.",
        ))
    return alerts


def _category_moves(rows: list[Observation], day: int, bars) -> list[Alert]:
    alerts = []
    for row in rows:
        if row.metric != "category_sales" or row.previous_value is None or row.previous_value <= 0:
            continue
        previous = int(row.previous_value)
        current = int(row.observed_value)
        if not _material(previous, current, bars.material):
            continue
        score, confidence = rate(row.reliability, measured=True)
        if current < previous:
            drop = previous - current
            share = drop * 100 // previous
            alerts.append(_alert(
                f"sales_decline:company:{row.category}",
                "sales_decline",
                day,
                "company",
                rank(financial=2 if share >= 25 else 1),
                confidence,
                score,
                (row.id,),
                drop,
                previous,
                "company",
                row.category,
                f"{row.category} sales fell from {money(previous)} to {money(current)}.",
            ))
        else:
            gain = current - previous
            alerts.append(_alert(
                f"category_opportunity:company:{row.category}",
                "category_opportunity",
                day,
                "company",
                rank(opportunity=True),
                confidence,
                score,
                (row.id,),
                gain,
                previous,
                "company",
                row.category,
                f"{row.category} sales rose from {money(previous)} to {money(current)}.",
            ))
    return alerts


def _traffic(rows: list[Observation], day: int, bars) -> list[Alert]:
    alerts = []
    for row in rows:
        if row.metric != "visits" or row.previous_value is None or row.previous_value <= 0:
            continue
        previous = int(row.previous_value)
        current = int(row.observed_value)
        if current >= previous or not _material(previous, current, bars.material):
            continue
        score, confidence = rate(row.reliability, measured=True)
        alerts.append(_alert(
            "traffic_decline:company",
            "traffic_decline",
            day,
            "company",
            rank(customer=1),
            confidence,
            score,
            (row.id,),
            previous - current,
            previous,
            "company",
            "",
            f"Visits fell from {previous} to {current}.",
        ))
    return alerts


def _cash(rows: list[Observation], day: int) -> list[Alert]:
    cash = _one(rows, "cash")
    bill = _one(rows, "obligations")
    if cash is None or bill is None or cash.observed_value >= bill.observed_value:
        return []
    gap = int(bill.observed_value) - int(cash.observed_value)
    score, confidence = rate(cash.reliability, measured=True)
    severity = rank(financial=3 if cash.observed_value <= 0 else 2 if gap * 2 >= bill.observed_value else 1)
    return [_alert(
        "cash_pressure:company",
        "cash_pressure",
        day,
        "company",
        severity,
        confidence,
        score,
        (cash.id, bill.id),
        gap,
        int(bill.observed_value),
        "company",
        "",
        f"Cash is {money(cash.observed_value)}. The week needs {money(bill.observed_value)}. The gap is {money(gap)}.",
    )]


def _debt(rows: list[Observation], day: int) -> list[Alert]:
    credit = _one(rows, "credit_left")
    bill = _one(rows, "obligations")
    if credit is None or bill is None:
        return []
    used = int(_meta(credit, "used") or 0)
    left = int(credit.observed_value)
    if used <= 0 or left >= bill.observed_value:
        return []
    score, confidence = rate(credit.reliability, measured=True)
    return [_alert(
        "debt_pressure:company",
        "debt_pressure",
        day,
        "company",
        rank(financial=2),
        confidence,
        score,
        (credit.id, bill.id),
        int(bill.observed_value) - left,
        int(bill.observed_value),
        "company",
        "",
        f"Credit left is {money(left)}. The week needs {money(bill.observed_value)}.",
    )]


def _labor(rows: list[Observation], day: int) -> list[Alert]:
    alerts = []
    for row in rows:
        if row.metric != "labor":
            continue
        budget = int(_meta(row, "budget") or 0)
        if budget <= 0 or row.observed_value <= budget:
            continue
        place = _meta(row, "place") or row.source_id
        score, confidence = rate(row.reliability, measured=True)
        over = int(row.observed_value) - budget
        share = over * 100 // budget
        alerts.append(_alert(
            f"labor_stress:{row.source_id}",
            "labor_stress",
            day,
            "store",
            rank(urgency=2 if share >= 20 else 1),
            confidence,
            score,
            (row.id,),
            over,
            budget,
            row.source_id,
            "",
            f"{place} labor was {row.observed_value} against a budget of {budget}.",
        ))
    for metric, label in (("lost_staff", "walked off the job"), ("overtime", "overtime hours"), ("noshow", "no-shows")):
        row = _one(rows, metric)
        if row is None or row.observed_value <= 0:
            continue
        score, confidence = rate(row.reliability, measured=True)
        alerts.append(_alert(
            f"labor_stress:{metric}",
            "labor_stress",
            day,
            "company",
            rank(urgency=2),
            confidence,
            score,
            (row.id,),
            int(row.observed_value),
            0,
            "company",
            "",
            f"{row.observed_value} {label}.",
        ))
    return alerts


def _suppliers(rows: list[Observation], day: int) -> list[Alert]:
    alerts = []
    for row in rows:
        if row.metric == "late_order":
            supplier = _meta(row, "supplier") or row.source_id
            due = _meta(row, "due") or ""
            score, confidence = rate(row.reliability, measured=True)
            alerts.append(_alert(
                f"supplier_delay:{row.source_id}",
                "supplier_delay",
                day,
                "company",
                rank(urgency=2),
                confidence,
                score,
                (row.id,),
                int(row.observed_value),
                0,
                row.source_id,
                "",
                f"Order {row.source_id} from {supplier} was due day {due} and has not arrived.",
            ))
        elif row.metric == "late_shipment":
            door = _meta(row, "door") or row.source_id
            score, confidence = rate(row.reliability, measured=True)
            alerts.append(_alert(
                f"supplier_delay:{row.source_id}",
                "supplier_delay",
                day,
                "store",
                rank(urgency=2),
                confidence,
                score,
                (row.id,),
                int(row.observed_value),
                0,
                row.source_id,
                "",
                f"The truck {row.source_id} to {door} is late.",
            ))
        elif row.metric == "late_payments" and row.observed_value > 0:
            score, confidence = rate(row.reliability, measured=True)
            alerts.append(_alert(
                f"supplier_delay:account:{row.source_id}",
                "supplier_delay",
                day,
                "company",
                rank(financial=1, urgency=1),
                confidence,
                score,
                (row.id,),
                int(row.observed_value),
                0,
                row.source_id,
                "",
                f"{row.source_id} has {row.observed_value} late payments.",
            ))
    return alerts


def _walkers(rows: list[Observation], day: int, bars) -> list[Alert]:
    row = _one(rows, "lost_price")
    if row is None or row.observed_value < bars.lost_price:
        return []
    score, confidence = rate(row.reliability, measured=True)
    return [_alert(
        "customer_switching:company",
        "customer_switching",
        day,
        "company",
        rank(customer=2 if row.observed_value >= 8 else 1),
        confidence,
        score,
        (row.id,),
        int(row.observed_value),
        int(row.previous_value or 0),
        "company",
        "",
        f"{row.observed_value} customers walked on price.",
    )]


def _margins(rows: list[Observation], day: int) -> list[Alert]:
    alerts = []
    for row in rows:
        if row.metric != "price":
            continue
        cost = int(_meta(row, "cost") or 0)
        if cost <= 0 or row.observed_value >= cost:
            continue
        name = _meta(row, "name") or row.source_id
        score, confidence = rate(row.reliability, measured=True)
        severity = rank(financial=2 if row.observed_value * 2 <= cost else 1)
        alerts.append(_alert(
            f"margin:{row.source_id}",
            "margin_compression",
            day,
            "company",
            severity,
            confidence,
            score,
            (row.id,),
            cost - int(row.observed_value),
            cost,
            row.source_id,
            row.category,
            f"{name} is priced at {money(row.observed_value)} against a cost of {money(cost)}.",
        ))
    gross = _one(rows, "gross_profit")
    if gross is not None and gross.observed_value < 0:
        score, confidence = rate(gross.reliability, measured=True)
        alerts.append(_alert(
            "margin:company",
            "margin_compression",
            day,
            "company",
            rank(financial=2),
            confidence,
            score,
            (gross.id,),
            abs(int(gross.observed_value)),
            0,
            "company",
            "",
            f"Yesterday's gross profit was {money(gross.observed_value)}.",
        ))
    return alerts


def _rivals(rows: list[Observation], day: int) -> list[Alert]:
    alerts = []
    seen: set[str] = set()
    for row in rows:
        if row.metric != "public_move":
            continue
        kind = _meta(row, "kind") or row.category
        text = _meta(row, "text")
        family = _rival_family(kind, text)
        if not family:
            continue
        chain = row.source_id or "rival"
        city = _meta(row, "city")
        ident = f"{family}:{chain}:{city}"
        if ident in seen:
            continue
        seen.add(ident)
        score, confidence = rate(row.reliability, measured=False)
        shown = text
        name = _meta(row, "chain") or chain
        if name and name not in shown:
            shown = f"{name}. {shown}"
        alerts.append(_alert(
            ident,
            family,
            day,
            "market",
            rank(competitive=2),
            confidence,
            score,
            (row.id,),
            1,
            0,
            chain,
            city,
            f"{shown} This is only what the company can see.",
        ))
    return alerts


def _rival_family(kind: str, text: str) -> str:
    blob = f"{kind} {text}".lower()
    if "price war" in blob or kind in {"start_price_war", "end_price_war"}:
        return "competitor_price_pressure"
    if kind in {"open_store", "store_opened", "reenter"} or "supercenter" in blob or "new door" in blob:
        return "competitor_expansion"
    return ""


def _continue(draft: Alert, earlier) -> Alert:
    if earlier is None:
        return draft
    if int(getattr(earlier, "last_seen", -1)) == draft.day:
        return replace(draft, status=earlier.status, first_seen=earlier.first_seen)
    if earlier.status == "resolved":
        status = "active"
    elif draft.current_value > int(getattr(earlier, "current_value", 0) or 0):
        status = "escalating"
    elif earlier.status == "new":
        status = "active"
    else:
        status = "stable"
    return replace(draft, status=status, first_seen=earlier.first_seen)


def _alert(
    ident,
    kind,
    day,
    scope,
    severity,
    confidence,
    score,
    observation_ids,
    current,
    baseline,
    source_id,
    category,
    evidence,
) -> Alert:
    delta = int(current) - int(baseline)
    if delta > 0:
        trend = "up"
    elif delta < 0:
        trend = "down"
    else:
        trend = "flat"
    return Alert(
        ident,
        kind,
        day,
        scope,
        severity,
        confidence,
        tuple(observation_ids),
        int(current),
        int(baseline),
        delta,
        trend,
        day,
        day,
        "new",
        evidence,
        source_id,
        category,
        score,
    )


def _material(previous: int, current: int, percent: int) -> bool:
    return abs(previous - current) * 100 >= previous * percent


def _one(rows: list[Observation], metric: str) -> Observation | None:
    found = [row for row in rows if row.metric == metric]
    return found[-1] if found else None


def _meta(row: Observation, key: str) -> str:
    for name, value in row.metadata:
        if name == key:
            return value
    return ""
