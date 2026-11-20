"""One warehouse pool per department.

A pool is the units of that department already on the save. The 200,500-item
catalog is not copied into the warehouse. A door draws from the pool. A thin
pool orders the items that actually sold, from their vendor, at most once a week.
"""

from __future__ import annotations

from dataclasses import dataclass

from open_late.departments import DEPARTMENT_IDS, DEPARTMENT_LABELS
from open_late.models import GameState


@dataclass(frozen=True)
class Pool:
    department: str
    label: str
    on_hand: int
    on_order: int
    week_sales: int
    thin: bool


def pool_rows(state: GameState) -> list[Pool]:
    on_hand = {dept: 0 for dept in DEPARTMENT_IDS}
    on_order = {dept: 0 for dept in DEPARTMENT_IDS}
    sales = {dept: 0 for dept in DEPARTMENT_IDS}
    for product_id, line in state.stock.items():
        product = state.products.get(product_id)
        if product is None:
            continue
        dept = _dept(product)
        if dept not in on_hand:
            continue
        on_hand[dept] += int(line.on_hand or 0)
    for order in state.orders:
        if int(order.arrives_on) < int(state.day):
            continue
        for product_id, qty in order.lines.items():
            product = state.products.get(product_id)
            if product is None:
                continue
            dept = _dept(product)
            if dept in on_order:
                on_order[dept] += int(qty)
    _add_sales(state, sales, None)
    rows = []
    for dept in DEPARTMENT_IDS:
        week = sales[dept]
        rows.append(Pool(
            department=dept,
            label=DEPARTMENT_LABELS.get(dept, dept.replace("_", " ").title()),
            on_hand=on_hand[dept],
            on_order=on_order[dept],
            week_sales=week,
            thin=week > 0 and on_hand[dept] + on_order[dept] < week,
        ))
    return rows


def pool_summary(state: GameState) -> tuple[str, str]:
    rows = pool_rows(state)
    thin = [row for row in rows if row.thin]
    held = sum(row.on_hand for row in rows)
    if thin:
        names = ", ".join(row.label for row in thin[:4])
        extra = len(thin) - 4
        more = f" and {extra} more" if extra > 0 else ""
        face = f"Thin pools: {names}{more}. {held:,} units in the warehouse."
    else:
        face = f"{len(rows)} warehouse pools. {held:,} units on hand."
    tip = "\n".join(
        f"{row.label}: {row.on_hand:,} on hand, {row.on_order:,} on order, "
        f"{row.week_sales:,} sold in the last week."
        for row in rows
    )
    return face, tip


def units_on_road(state: GameState) -> int:
    """Vendor trucks not yet in, and store trucks that have not reached the door."""
    total = 0
    for order in state.orders:
        if int(order.arrives_on) > int(state.day):
            total += sum(int(qty) for qty in order.lines.values())
    for shipment in state.shipments:
        if int(shipment.arrives_on) > int(state.day):
            total += sum(int(qty) for qty in shipment.lines.values())
    return total


def drawn_labels(state: GameState, product_ids) -> str:
    labels = []
    for product_id in product_ids:
        product = state.products.get(product_id)
        if product is None:
            continue
        label = DEPARTMENT_LABELS.get(_dept(product), _dept(product))
        if label not in labels:
            labels.append(label)
    return ", ".join(labels) if labels else "the warehouse"


def fill_thin_pools(state: GameState, only: set[str] | None = None) -> str:
    """Order the sold items for each thin pool. Shop shelves are not a warehouse."""
    if state.mode != "corporate":
        return "The shop shelf is the stock. Pools supply doors from the Evansville warehouse."
    from open_late.content import SUPPLIERS
    from open_late.engine import _add_order

    rows = [row for row in pool_rows(state) if row.thin and (only is None or row.department in only)]
    if not rows:
        return "No pool is thin. The warehouse covers the last week of sales."
    sold = _sku_sales(state)
    placed: list[str] = []
    skipped: list[str] = []
    for row in rows:
        tried = int((state.pool_tried or {}).get(row.department, -99))
        if tried + 7 > int(state.day) and only is None:
            continue
        gap = row.week_sales - row.on_hand - row.on_order
        batches = _batches(state, row.department, gap, sold)
        if not batches:
            skipped.append(f"{row.label} has no sold item to reorder")
            _mark(state, row.department)
            continue
        for supplier_id, lines in batches.items():
            supplier = SUPPLIERS.get(supplier_id)
            ok, message = _add_order(state, supplier_id, lines, ignore_minimum=False)
            name = supplier.name if supplier is not None else supplier_id
            if ok:
                placed.append(f"{row.label} from {name}")
                _tag_order(state, row.label)
                _mark(state, row.department)
            elif "minimum" in message.lower():
                skipped.append(f"{row.label} is under {name}'s minimum")
                _mark(state, row.department)
            else:
                skipped.append(message)
    if placed:
        text = "Ordered for " + "; ".join(placed) + "."
        if skipped:
            text += " Left: " + "; ".join(skipped) + "."
        return text
    if skipped:
        return "Thin pools were not ordered. " + "; ".join(skipped) + "."
    return "Thin pools were already ordered this week."


def _tag_order(state: GameState, label: str) -> None:
    if not state.decisions:
        return
    note = state.decisions[-1]
    if note.kind == "order" and label not in note.text:
        note.text = f"{label} pool. {note.text}"


def _mark(state: GameState, department: str) -> None:
    tried = dict(state.pool_tried or {})
    tried[department] = int(state.day)
    state.pool_tried = tried


def _batches(state: GameState, department: str, gap: int, sold: dict[str, int]) -> dict[str, dict[str, int]]:
    from open_late.engine import order_qty_max

    gap = max(0, int(gap))
    if gap <= 0:
        return {}
    ranked = []
    for product_id, qty in sold.items():
        product = state.products.get(product_id)
        if product is None or _dept(product) != department or qty <= 0:
            continue
        ranked.append((product, int(qty)))
    if not ranked:
        return {}
    total = sum(qty for _product, qty in ranked) or 1
    cap = order_qty_max()
    batches: dict[str, dict[str, int]] = {}
    for product, qty in ranked:
        share = max(1, int(round(gap * qty / total)))
        share = min(share, cap)
        bucket = batches.setdefault(product.supplier_id, {})
        bucket[product.id] = bucket.get(product.id, 0) + share
    return batches


def _sku_sales(state: GameState) -> dict[str, int]:
    sold: dict[str, int] = {}
    _add_sales(state, {}, None, sold)
    return sold


def _add_sales(
    state: GameState,
    by_dept: dict[str, int],
    by_sku: dict[str, dict[str, int]] | None,
    flat: dict[str, int] | None = None,
) -> None:
    def add(product_id: str, qty: int) -> None:
        amount = int(qty)
        if amount <= 0:
            return
        product = state.products.get(product_id)
        if product is None:
            return
        dept = _dept(product)
        if dept in by_dept:
            by_dept[dept] += amount
        if by_sku is not None and dept in by_sku:
            bucket = by_sku[dept]
            bucket[product_id] = bucket.get(product_id, 0) + amount
        if flat is not None:
            flat[product_id] = flat.get(product_id, 0) + amount

    if state.mode == "corporate":
        for door in state.doors:
            for row in door.sales_days:
                if int(state.day) - 7 < int(row.day) <= int(state.day):
                    for product_id, qty in row.units.items():
                        add(product_id, qty)
        return
    reports = list(state.history or [])
    if state.last_report.day and state.last_report not in reports:
        reports.append(state.last_report)
    for report in reports[-7:]:
        for product_id, qty in (getattr(report, "units_by_product", None) or {}).items():
            add(product_id, qty)


def _dept(product) -> str:
    return product.department or product.category or "other"
