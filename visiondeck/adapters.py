"""Observation adapters. Each one reads company-visible state and writes nothing."""

from __future__ import annotations

from open_late.visiondeck.models import Observation


def all_observations(state) -> list[Observation]:
    rows: list[Observation] = []
    for reader in (
        sales_adapter,
        inventory_adapter,
        pricing_adapter,
        customer_adapter,
        supplier_adapter,
        finance_adapter,
        workforce_adapter,
        rival_adapter,
    ):
        rows.extend(reader(state))
    return rows


def sales_adapter(state) -> list[Observation]:
    report = getattr(state, "last_report", None)
    if report is None:
        return []
    prior = _prior_report(state, report)
    day = int(getattr(report, "day", 0) or 0)
    rows = [
        _row(
            f"revenue:{day}",
            day,
            "company",
            "company",
            "",
            "revenue",
            int(getattr(report, "revenue", 0) or 0),
            _field(prior, "revenue"),
            reliability=85,
        )
    ]
    gross = getattr(report, "gross_profit", None)
    if gross is not None:
        rows.append(_row(
            f"gross_profit:{day}",
            day,
            "company",
            "company",
            "",
            "gross_profit",
            int(gross or 0),
            _field(prior, "gross_profit"),
            reliability=85,
        ))
    current = dict(getattr(report, "by_category", {}) or {})
    for category in sorted(current):
        rows.append(_row(
            f"category_sales:{category}:{day}",
            day,
            "company",
            "company",
            str(category),
            "category_sales",
            int(current[category] or 0),
            _window(state, report, "by_category", str(category)),
            reliability=85,
        ))
    return rows


def inventory_adapter(state) -> list[Observation]:
    from open_late.visiondeck.observations import inventory_observations

    return inventory_observations(state)


def pricing_adapter(state) -> list[Observation]:
    day = _today(state)
    rows = []
    for product in (getattr(state, "products", {}) or {}).values():
        name = str(getattr(product, "name", "") or getattr(product, "id", ""))
        cost = int(getattr(product, "cost", 0) or 0)
        price = int(getattr(product, "price", 0) or 0)
        rows.append(_row(
            f"price:{getattr(product, 'id', name)}:{day}",
            day,
            "catalog",
            str(getattr(product, "id", "") or name),
            str(getattr(product, "category", "") or ""),
            "price",
            price,
            None,
            reliability=95,
            metadata=(("cost", str(cost)), ("name", name)),
        ))
    return rows


def customer_adapter(state) -> list[Observation]:
    report = getattr(state, "last_report", None)
    prior = _prior_report(state, report) if report is not None else None
    day = int(getattr(report, "day", 0) or 0) if report is not None else _today(state)
    rows = []
    if report is not None:
        rows.append(_row(
            f"visits:{day}",
            day,
            "company",
            "company",
            "",
            "visits",
            int(getattr(report, "visits", 0) or 0),
            _window(state, report, "visits"),
            reliability=80,
        ))
        rows.append(_row(
            f"lost_price:{day}",
            day,
            "company",
            "company",
            "",
            "lost_price",
            int(getattr(report, "lost_price", 0) or 0),
            _field(prior, "lost_price"),
            reliability=80,
        ))
    for person in getattr(state, "regulars", []) or []:
        if not getattr(person, "active", True):
            continue
        ident = str(getattr(person, "id", "") or "regular")
        rows.append(_row(
            f"loyalty:{ident}:{day}",
            day,
            "customer",
            ident,
            "",
            "loyalty",
            int(getattr(person, "loyalty", 0) or 0),
            None,
            reliability=70,
        ))
    return rows


def supplier_adapter(state) -> list[Observation]:
    day = _today(state)
    rows = []
    for order in getattr(state, "orders", []) or []:
        arrives = int(getattr(order, "arrives_on", 0) or 0)
        if not arrives or arrives >= day:
            continue
        ident = str(getattr(order, "id", "") or "order")
        supplier = str(getattr(order, "supplier_id", "") or "supplier")
        rows.append(_row(
            f"late_order:{ident}",
            day,
            "supplier",
            ident,
            "",
            "late_order",
            day - arrives,
            None,
            reliability=80,
            metadata=(("supplier", supplier), ("due", str(arrives))),
        ))
    for shipment in getattr(state, "shipments", []) or []:
        arrives = int(getattr(shipment, "arrives_on", 0) or 0)
        if not arrives or arrives >= day:
            continue
        ident = str(getattr(shipment, "id", "") or "truck")
        door = str(getattr(shipment, "door_id", "") or "")
        rows.append(_row(
            f"late_shipment:{ident}",
            day,
            "supplier",
            ident,
            "",
            "late_shipment",
            day - arrives,
            None,
            reliability=80,
            metadata=(("door", door), ("due", str(arrives))),
        ))
    for account in getattr(state, "supplier_accounts", []) or []:
        late = int(getattr(account, "late_payments", 0) or 0)
        ident = str(getattr(account, "supplier_id", "") or "supplier")
        rows.append(_row(
            f"late_payments:{ident}:{day}",
            day,
            "supplier",
            ident,
            "",
            "late_payments",
            late,
            None,
            reliability=75,
        ))
    return rows


def finance_adapter(state) -> list[Observation]:
    if not hasattr(state, "cash"):
        return []
    day = _today(state)
    cash = int(getattr(state, "cash", 0) or 0)
    rows = [_row(f"cash:{day}", day, "company", "company", "", "cash", cash, None, reliability=95)]
    obligations = _obligations(state)
    if obligations is None:
        return rows
    rows.append(_row(
        f"obligations:{day}",
        day,
        "company",
        "company",
        "",
        "obligations",
        obligations,
        None,
        reliability=90,
    ))
    limit = int(getattr(state, "credit_limit", 0) or 0)
    used = int(getattr(state, "credit_used", 0) or 0)
    rows.append(_row(
        f"credit_left:{day}",
        day,
        "company",
        "company",
        "",
        "credit_left",
        max(0, limit - used),
        None,
        reliability=95,
        metadata=(("used", str(used)), ("limit", str(limit))),
    ))
    return rows


def workforce_adapter(state) -> list[Observation]:
    day = _today(state)
    report = getattr(state, "last_report", None)
    report_day = int(getattr(report, "day", 0) or 0) if report is not None else day - 1
    spent: dict[str, int] = {}
    for row in getattr(state, "store_days", []) or []:
        if int(getattr(row, "day", 0) or 0) != report_day and int(getattr(row, "day", 0) or 0) != day - 1:
            continue
        door_id = str(getattr(row, "store_id", "") or "")
        spent[door_id] = spent.get(door_id, 0) + int(getattr(row, "labor", 0) or 0)
    rows = []
    for door in getattr(state, "doors", []) or []:
        door_id = str(getattr(door, "id", "") or "")
        budget = int(getattr(door, "labor_budget", 0) or 0)
        place = str(getattr(door, "city", "") or door_id)
        rows.append(_row(
            f"labor:{door_id}:{report_day}",
            report_day or day,
            "store",
            door_id,
            "",
            "labor",
            int(spent.get(door_id, 0)),
            None,
            store_id=door_id,
            region=str(getattr(door, "region", "") or ""),
            reliability=85,
            metadata=(("budget", str(budget)), ("place", place)),
        ))
    if report is not None:
        rows.append(_row(
            f"lost_staff:{report_day}",
            report_day,
            "company",
            "company",
            "",
            "lost_staff",
            int(getattr(report, "lost_staff", 0) or 0),
            None,
            reliability=85,
        ))
        rows.append(_row(
            f"overtime:{report_day}",
            report_day,
            "company",
            "company",
            "",
            "overtime",
            int(getattr(report, "labor_overtime", 0) or 0),
            None,
            reliability=85,
        ))
        rows.append(_row(
            f"noshow:{report_day}",
            report_day,
            "company",
            "company",
            "",
            "noshow",
            len(getattr(report, "noshow_ids", []) or []),
            None,
            reliability=85,
        ))
    return rows


def rival_adapter(state) -> list[Observation]:
    try:
        from open_late.ai.constants import week_of
        from open_late.living import public_move
        from open_late.rival_ai import rival_snapshot

        public = rival_snapshot(state) or {}
    except Exception:
        return []
    names = {
        str(row.get("id") or ""): str(row.get("name") or "")
        for row in (public.get("chains") or [])
    }
    day = max(1, _today(state))
    current = week_of(day)
    rows = []
    for item in public.get("feed") or []:
        if _feed_week(item, day) != current:
            continue
        shown = public_move(str(item.get("text") or ""))
        if not shown:
            continue
        chain_id = str(item.get("chain_id") or "")
        kind = str(item.get("kind") or "")
        city = str(item.get("city") or "")
        name = names.get(chain_id) or chain_id
        item_day = int(item.get("day") or day)
        rows.append(_row(
            f"public_move:{chain_id}:{kind}:{city}:{item_day}",
            item_day,
            "rival",
            chain_id,
            kind,
            "public_move",
            1,
            None,
            visibility="public",
            reliability=70,
            metadata=(("text", shown), ("chain", name), ("city", city), ("kind", kind)),
        ))
    return rows


def _obligations(state) -> int | None:
    try:
        from open_late.finance import weekly_obligations

        return int(weekly_obligations(state))
    except Exception:
        return None


def _window(state, report, field: str, category: str | None = None) -> int | None:
    """Mean of up to seven earlier readings. One earlier day is that day."""
    if report is None:
        return None
    day = int(getattr(report, "day", 0) or 0)
    values = []
    for row in getattr(state, "history", []) or []:
        if int(getattr(row, "day", 0) or 0) >= day:
            continue
        if category is None:
            if not hasattr(row, field):
                continue
            values.append(int(getattr(row, field) or 0))
            continue
        bucket = getattr(row, field, None) or {}
        if category not in bucket:
            continue
        values.append(int(bucket[category] or 0))
    if not values:
        return None
    window = values[-7:]
    return sum(window) // len(window)


def _prior_report(state, report):
    if report is None:
        return None
    day = int(getattr(report, "day", 0) or 0)
    earlier = [
        row for row in (getattr(state, "history", []) or [])
        if int(getattr(row, "day", 0) or 0) < day
    ]
    return earlier[-1] if earlier else None


def _field(report, name: str) -> int | None:
    if report is None or not hasattr(report, name):
        return None
    return int(getattr(report, name) or 0)


def _feed_week(item, day: int) -> int:
    from open_late.ai.constants import week_of

    week = item.get("week")
    if week:
        return int(week)
    return week_of(int(item.get("day") or day))


def _today(state) -> int:
    return int(getattr(state, "day", 0) or 0)


def _row(
    ident,
    day,
    source_type,
    source_id,
    category,
    metric,
    value,
    previous,
    *,
    region="",
    store_id="",
    visibility="company",
    reliability=80,
    metadata=(),
) -> Observation:
    return Observation(
        ident,
        int(day),
        source_type,
        source_id,
        category,
        metric,
        int(value),
        previous,
        region,
        store_id,
        visibility,
        reliability,
        0,
        tuple(metadata),
    )
