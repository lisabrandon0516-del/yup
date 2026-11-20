"""Phase 11. A versioned intelligence record on the save.

An empty record is left off the file, so an older save still loads and still
writes the same bytes. Choice notes stay on the decisions list. This record
keeps the trend, the open and resolved signals, the forecast, the calibration
counts, the briefing lines, and the alerts the player pinned.
"""

from __future__ import annotations

from open_late.visiondeck.models import Alert

SCHEMA = 1
KEY = "visiondeck_save"

_TREND = {"revenue", "visits", "category_sales", "cash", "lost_price", "obligations", "credit_left"}
_LISTS = ("observations", "signals", "resolved", "forecasts", "briefings", "pinned")


def stored_alerts(state) -> list[Alert]:
    """Yesterday's open signals, rebuilt so today's reading can continue them."""
    book = read(state)
    return _alerts(book.get("signals") or [])


def read(state) -> dict:
    """The stored record, migrated. Missing and empty both come back as {}."""
    if state is None:
        return {}
    raw = getattr(state, KEY, None)
    if not raw:
        return {}
    return migrate(raw)


def migrate(raw) -> dict:
    """Bring an older shape up to the current schema. Unknown extras are dropped."""
    if isinstance(raw, list):
        body = _shell()
        body["pinned"] = [str(item) for item in raw if str(item)]
        return body if _kept(body) else {}
    if not isinstance(raw, dict) or not raw:
        return {}
    schema = int(raw.get("schema") or 0)
    body = _shell()
    body["schema"] = schema if schema > SCHEMA else SCHEMA
    for key in _LISTS:
        value = raw.get(key)
        if isinstance(value, list):
            body[key] = [item for item in value]
    calibration = raw.get("calibration")
    if isinstance(calibration, dict):
        body["calibration"] = dict(calibration)
    return body if _kept(body) else {}


def snapshot(state) -> dict:
    """Write today's record from what the company can already see. Nothing is ordered."""
    if state is None:
        return {}
    prior = read(state)
    observations = _observations(state, prior.get("observations") or [])
    from open_late.visiondeck.signals import detect

    current = detect(state, prior=_alerts(prior.get("signals") or []))
    active = [item for item in current if getattr(item, "status", "") != "resolved"]
    done = [item for item in current if getattr(item, "status", "") == "resolved"]
    day = int(getattr(state, "day", 0) or 0)
    book = {
        "schema": SCHEMA,
        "observations": observations,
        "signals": [_signal(item) for item in active],
        "resolved": _resolved(prior.get("resolved") or [], done),
        "forecasts": [row for row in (_forecast(item) for item in active) if row],
        "calibration": _calibration(state),
        "briefings": _briefings(prior.get("briefings") or [], active, day),
        "pinned": [str(item) for item in (prior.get("pinned") or [])],
    }
    stored = migrate(book)
    _write(state, stored)
    return stored


def pin(state, alert_id: str) -> dict:
    """Remember one alert id across a save. Pinning does not carry the action out."""
    book = snapshot(state)
    ident = str(alert_id or "").strip()
    if not ident:
        return book
    pinned = [item for item in book.get("pinned") or [] if item != ident]
    pinned.append(ident)
    book = {
        "schema": int(book.get("schema") or SCHEMA),
        "observations": list(book.get("observations") or []),
        "signals": list(book.get("signals") or []),
        "resolved": list(book.get("resolved") or []),
        "forecasts": list(book.get("forecasts") or []),
        "calibration": dict(book.get("calibration") or {}),
        "briefings": list(book.get("briefings") or []),
        "pinned": pinned,
    }
    stored = migrate(book)
    _write(state, stored)
    return stored


def _shell() -> dict:
    return {
        "schema": SCHEMA,
        "observations": [],
        "signals": [],
        "resolved": [],
        "forecasts": [],
        "calibration": {},
        "briefings": [],
        "pinned": [],
    }


def _kept(body: dict) -> bool:
    if body.get("calibration"):
        return True
    return any(body.get(key) for key in _LISTS)


def _write(state, book: dict) -> None:
    if state is None:
        return
    setattr(state, KEY, book if book else {})


def _observations(state, prior: list) -> list:
    from open_late.visiondeck.observations import collect_observations

    merged = {}
    for item in prior:
        if isinstance(item, dict) and item.get("id"):
            merged[str(item["id"])] = dict(item)
    for row in collect_observations(state):
        if not _worth(row):
            continue
        previous = getattr(row, "previous_value", None)
        merged[row.id] = {
            "id": row.id,
            "day": int(row.day),
            "metric": row.metric,
            "category": row.category,
            "source_id": row.source_id,
            "observed_value": int(row.observed_value),
            "previous_value": None if previous is None else int(previous),
        }
    kept = sorted(merged.values(), key=lambda item: (int(item.get("day") or 0), str(item.get("id") or "")))
    if not kept:
        return []
    newest = max(int(item.get("day") or 0) for item in kept)
    kept = [item for item in kept if newest - int(item.get("day") or 0) <= 14]
    return kept[-80:]


def _alerts(rows: list) -> list[Alert]:
    alerts = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        alerts.append(Alert(
            str(row.get("id")),
            str(row.get("kind") or ""),
            int(row.get("day") or 0),
            str(row.get("scope") or "company"),
            str(row.get("severity") or "watch"),
            str(row.get("confidence") or "low"),
            (),
            int(row.get("current_value") or 0),
            int(row.get("baseline_value") or 0),
            int(row.get("delta") or 0),
            str(row.get("trend") or "flat"),
            int(row.get("first_seen") or row.get("day") or 0),
            int(row.get("last_seen") or row.get("day") or 0),
            str(row.get("status") or "active"),
            str(row.get("evidence") or ""),
            str(row.get("source_id") or ""),
            str(row.get("category") or ""),
        ))
    return alerts


def _signal(alert) -> dict:
    return {
        "id": alert.id,
        "kind": alert.kind,
        "day": int(alert.day),
        "scope": alert.scope,
        "severity": alert.severity,
        "confidence": alert.confidence,
        "category": alert.category,
        "source_id": alert.source_id,
        "current_value": int(alert.current_value),
        "baseline_value": int(alert.baseline_value),
        "delta": int(alert.delta),
        "trend": alert.trend,
        "first_seen": int(alert.first_seen),
        "last_seen": int(alert.last_seen),
        "status": alert.status,
        "evidence": alert.evidence,
    }


def _forecast(alert) -> dict | None:
    forecast = getattr(alert, "forecast", None)
    if forecast is None:
        return None
    return {
        "id": forecast.id,
        "signal_id": forecast.signal_id or alert.id,
        "metric": forecast.metric,
        "low_case": int(forecast.low_case),
        "expected_case": int(forecast.expected_case),
        "high_case": int(forecast.high_case),
        "baseline": int(forecast.baseline),
        "confidence": forecast.confidence,
        "created_at": int(forecast.created_at),
        "actual": forecast.actual,
        "verdict": forecast.verdict or "",
    }


def _resolved(prior: list, fresh: list) -> list:
    merged = {}
    for item in prior:
        if isinstance(item, dict) and item.get("id"):
            merged[str(item["id"])] = dict(item)
    for alert in fresh:
        merged[alert.id] = _signal(alert)
    return list(merged.values())[-40:]


def _briefings(prior: list, active: list, day: int) -> list:
    lines = [str(getattr(item, "evidence", "") or "") for item in active if getattr(item, "evidence", "")]
    kept = [item for item in prior if isinstance(item, dict) and int(item.get("day") or 0) != day]
    if lines:
        kept.append({"day": day, "lines": lines[:6]})
    return kept[-14:]


def _calibration(state) -> dict:
    counts: dict[str, dict[str, int]] = {}
    for note in list(getattr(state, "decisions", []) or []):
        if str(getattr(note, "kind", "") or "") != "decision_lab":
            continue
        result = str(getattr(note, "result", "") or "").lower()
        if not result:
            continue
        kind = _kind(str(getattr(note, "ref", "") or ""))
        if not kind:
            continue
        row = counts.setdefault(kind, {"misses": 0, "holds": 0})
        if "missed" in result:
            row["misses"] += 1
        elif "held" in result:
            row["holds"] += 1
    return {kind: row for kind, row in counts.items() if row["misses"] or row["holds"]}


def _kind(ref: str) -> str:
    if ref.startswith("stockout:"):
        return "stockout_pressure"
    if ref.startswith("margin:"):
        return "margin_compression"
    head = ref.split(":", 1)[0]
    if head in {"cash_pressure", "sales_decline", "traffic_decline", "margin_compression"}:
        return head
    return ""


def _worth(row) -> bool:
    metric = str(getattr(row, "metric", "") or "")
    value = int(getattr(row, "observed_value", 0) or 0)
    if metric in _TREND:
        return True
    if metric == "lost_stockout" and value > 0:
        return True
    return metric == "on_hand" and value == 0
