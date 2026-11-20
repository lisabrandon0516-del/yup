"""What the player did about an empty shelf, and whether it worked."""

from __future__ import annotations

from dataclasses import dataclass

_KINDS = {"stockout_send", "stockout_order", "stockout_wait"}


def remember_send(state, door_id: str, place: str, category: str, product_id: str, quantity: int) -> None:
    _note(
        state,
        "stockout_send",
        f"Sent {int(quantity)} {category} to {place}.",
        _ref(door_id, category, product_id, place),
        int(quantity),
    )


def remember_order(state, category: str, product_id: str, quantity: int) -> None:
    _note(
        state,
        "stockout_order",
        f"Ordered {int(quantity)} {category}.",
        _ref("", category, product_id, ""),
        int(quantity),
    )


def remember_rival_hold(state, door_id: str, place: str, visits: int) -> None:
    """The player left the rival move alone. Visits are the door's last count."""
    from open_late.books import note_decision

    if getattr(state, "decisions", None) is None:
        state.decisions = []
    note_decision(
        state,
        "rival_hold",
        f"Did nothing about the {place} move.",
        ref=f"{door_id}|{place}",
        before_visits=int(visits),
    )


def rival_outcomes(state) -> list[str]:
    if state is None:
        return []
    today = int(getattr(state, "day", 0) or 0)
    lines: list[str] = []
    for note in list(getattr(state, "decisions", []) or []):
        if int(getattr(note, "day", 0) or 0) != today - 1:
            continue
        kind = str(getattr(note, "kind", "") or "")
        if kind == "rival_hold":
            lines.append(_hold_result(state, note))
        elif kind == "price" and int(getattr(note, "before_units", -1) or -1) >= 0 and getattr(note, "ref", ""):
            lines.append(_price_result(state, note))
    return [line for line in lines if line]


def visits_on(state, door_id: str, day: int) -> int | None:
    found = False
    total = 0
    for row in getattr(state, "store_days", []) or []:
        if str(getattr(row, "store_id", "") or "") != door_id:
            continue
        if int(getattr(row, "day", 0) or 0) != int(day):
            continue
        found = True
        total += int(getattr(row, "visits", 0) or 0)
    if found:
        return total
    report = getattr(state, "last_report", None)
    doors = list(getattr(state, "doors", []) or [])
    if report is not None and int(getattr(report, "day", 0) or 0) == int(day) and len(doors) <= 1:
        return int(getattr(report, "visits", 0) or 0)
    return None


def _hold_result(state, note) -> str:
    ref = str(getattr(note, "ref", "") or "")
    door_id, _, place = ref.partition("|")
    place = place or door_id
    today = int(getattr(state, "day", 0) or 0)
    after = visits_on(state, door_id, today - 1)
    before = int(getattr(note, "before_visits", 0) or 0)
    if after is None:
        return f"Visits at {place} were not on the tape."
    if after > before:
        return f"Visits at {place} rose, {after} from {before}."
    if after < before:
        return f"Visits at {place} fell, {after} from {before}."
    return f"Visits at {place} held at {after}."


def _price_result(state, note) -> str:
    report = getattr(state, "last_report", None)
    units = getattr(report, "units_by_product", None) or {}
    sold = int(units.get(note.ref, 0) or 0)
    before = int(note.before_units)
    product = (getattr(state, "products", {}) or {}).get(note.ref)
    name = str(getattr(product, "name", "") or note.ref)
    if sold > before:
        return f"{name} sold more, {sold} from {before}."
    if sold < before:
        return f"{name} sold less, {sold} from {before}."
    return f"{name} sold the same, {sold}."


def remember_wait(state, door_id: str, place: str, category: str, lost: int) -> None:
    _note(
        state,
        "stockout_wait",
        f"Waited on {place} {category}.",
        _ref(door_id, category, "", place),
        int(lost),
    )


def stockout_outcomes(state) -> list[str]:
    if state is None:
        return []
    today = int(getattr(state, "day", 0) or 0)
    lines: list[str] = []
    for note in list(getattr(state, "decisions", []) or []):
        if str(getattr(note, "kind", "") or "") not in _KINDS:
            continue
        if int(getattr(note, "day", 0) or 0) >= today:
            continue
        fresh = _fresh(state, note)
        if not fresh:
            continue
        shown = int(getattr(note, "before_walked", -1) if getattr(note, "before_walked", -1) is not None else -1)
        note.result = fresh
        if _terminal(fresh):
            if shown < 0:
                note.before_walked = today
                lines.append(fresh)
            elif shown == today:
                lines.append(fresh)
        else:
            lines.append(fresh)
    return lines


def _note(state, kind: str, text: str, ref: str, before_units: int) -> None:
    from open_late.books import note_decision

    if getattr(state, "decisions", None) is None:
        state.decisions = []
    note_decision(state, kind, text, ref=ref, before_units=before_units)


def _ref(door_id: str, category: str, product_id: str, place: str) -> str:
    return "|".join((door_id, category, product_id, place))


def _parts(note) -> tuple[str, str, str, str]:
    bits = str(getattr(note, "ref", "") or "").split("|")
    bits += [""] * (4 - len(bits))
    return bits[0], bits[1], bits[2], bits[3]


def _fresh(state, note) -> str:
    door_id, category, product_id, place = _parts(note)
    kind = str(note.kind)
    if kind == "stockout_send":
        return _send_result(state, door_id, category, product_id, place)
    if kind == "stockout_order":
        return _order_result(state, category, product_id)
    if kind == "stockout_wait":
        return _wait_result(state, door_id, category, place, int(getattr(note, "before_units", 0) or 0))
    return ""


def _send_result(state, door_id: str, category: str, product_id: str, place: str) -> str:
    today = int(getattr(state, "day", 0) or 0)
    future = False
    for shipment in getattr(state, "shipments", []) or []:
        if str(getattr(shipment, "door_id", "") or "") != door_id:
            continue
        lines = getattr(shipment, "lines", {}) or {}
        if product_id and product_id not in lines:
            continue
        if int(getattr(shipment, "arrives_on", 0) or 0) > today:
            future = True
    if _on_hand(state, door_id, category, product_id) > 0:
        return f"The send worked. {place} {category} is on the shelf."
    if future:
        return f"The truck to {place} has not arrived."
    return f"The send did not keep {place} {category} on the shelf."


def _order_result(state, category: str, product_id: str) -> str:
    today = int(getattr(state, "day", 0) or 0)
    pending = False
    for order in getattr(state, "orders", []) or []:
        lines = getattr(order, "lines", {}) or {}
        if product_id and product_id not in lines:
            continue
        if int(getattr(order, "arrives_on", 0) or 0) > today:
            pending = True
    if _on_hand(state, "", category, product_id) > 0:
        return f"The order worked. {category.capitalize()} is on the shelf."
    if pending:
        return f"The {category} order has not arrived."
    return f"The order did not put {category} on the shelf."


def _wait_result(state, door_id: str, category: str, place: str, before: int) -> str:
    report = getattr(state, "last_report", None)
    lost = getattr(report, "lost_stockout_by_category", None) or {}
    actual = int(lost.get(category, 0) or 0)
    if actual <= 0 and _on_hand(state, door_id, category, "") > 0:
        return f"You waited, and {place} {category} is on the shelf."
    return f"You waited on {place} {category}. {actual} turned away, was {before}."


def _on_hand(state, door_id: str, category: str, product_id: str) -> int:
    products = getattr(state, "products", {}) or {}
    stocks = []
    doors = list(getattr(state, "doors", []) or [])
    if door_id:
        stocks = [getattr(door, "stock", {}) or {} for door in doors if str(getattr(door, "id", "")) == door_id]
    elif doors:
        stocks = [getattr(door, "stock", {}) or {} for door in doors]
    else:
        stocks = [getattr(state, "stock", {}) or {}]
    total = 0
    for stock in stocks:
        for line in stock.values():
            pid = str(getattr(line, "product_id", "") or "")
            if product_id and pid != product_id:
                continue
            product = products.get(pid)
            if product is None or str(getattr(product, "category", "") or "") != category:
                continue
            total += int(getattr(line, "on_hand", 0) or 0)
    return total


@dataclass(frozen=True)
class MemoryEntry:
    """One real choice. A lesson is present only after an outcome was written."""

    day: int
    kind: str
    ref: str
    text: str
    expected: int
    outcome: str
    lesson: str


def journal(state) -> list[MemoryEntry]:
    """The choices on the company record. Nothing is added that was not stored."""
    entries = []
    for note in list(getattr(state, "decisions", []) or []):
        kind = str(getattr(note, "kind", "") or "")
        if kind not in _JOURNAL:
            continue
        before = getattr(note, "before_units", -1)
        expected = int(-1 if before is None else before)
        if kind == "price" and expected < 0:
            continue
        outcome = str(getattr(note, "result", "") or "")
        entries.append(MemoryEntry(
            int(getattr(note, "day", 0) or 0),
            kind,
            str(getattr(note, "ref", "") or ""),
            str(getattr(note, "text", "") or ""),
            expected,
            outcome,
            lesson_for(outcome),
        ))
    return entries


def analogs(state, alert) -> list[MemoryEntry]:
    """Earlier choices about this same situation. An empty list means there are none."""
    if state is None or alert is None:
        return []
    today = int(getattr(state, "day", 0) or 0)
    return [entry for entry in journal(state) if entry.day < today and _related(entry, alert)]


def recall(state, alert) -> str:
    found = analogs(state, alert)
    if not found:
        return ""
    latest = found[-1]
    if latest.lesson:
        return f"Last time, day {latest.day}: {latest.lesson}"
    return f"Last time, day {latest.day}: {latest.text}"


def lesson_for(outcome: str) -> str:
    text = (outcome or "").lower()
    if not text:
        return ""
    if "held" in text:
        return "The projection was usable."
    if "missed" in text:
        return "The projection missed."
    if "did not" in text:
        return "The action did not put the goods on the shelf."
    if "worked" in text:
        return "The action put the goods on the shelf."
    return ""


def calibrate(state, kind: str, confidence: str) -> str:
    """Lower confidence after two or more misses. One miss, or a clean record, stays put."""
    prefix = _PREFIX.get(kind, "")
    if not prefix:
        return confidence
    scored = [
        note for note in (getattr(state, "decisions", []) or [])
        if getattr(note, "kind", "") == "decision_lab"
        and str(getattr(note, "ref", "") or "").startswith(prefix)
        and str(getattr(note, "result", "") or "")
    ]
    if len(scored) < 2:
        return confidence
    misses = sum(1 for note in scored if "missed" in str(note.result).lower())
    holds = sum(1 for note in scored if "held" in str(note.result).lower())
    if misses > holds:
        return _down(confidence)
    return confidence


_JOURNAL = {"decision_lab", "stockout_send", "stockout_order", "stockout_wait", "rival_hold", "price"}

_PREFIX = {
    "stockout_pressure": "stockout:",
    "cash_pressure": "cash_pressure:",
    "margin_compression": "margin:",
    "sales_decline": "sales_decline:",
    "traffic_decline": "traffic_decline:",
}


def _related(entry: MemoryEntry, alert) -> bool:
    if entry.ref and entry.ref == getattr(alert, "id", ""):
        return True
    category = str(getattr(alert, "category", "") or "")
    if getattr(alert, "kind", "") != "stockout_pressure" or not category:
        return False
    if entry.ref.startswith("stockout:") and entry.ref.endswith(f":{category}"):
        return True
    return category in [part for part in entry.ref.split("|") if part]


def _down(confidence: str) -> str:
    if confidence == "high":
        return "moderate"
    if confidence == "moderate":
        return "low"
    return confidence


def _terminal(text: str) -> bool:
    return text.startswith("The send worked") or text.startswith("The order worked") or text.startswith("The send did not") or text.startswith("The order did not") or text.startswith("You waited")
