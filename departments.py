"""Department catalog helpers for Back Office: Retail."""

from __future__ import annotations

from typing import Any

DEPARTMENTS: list[tuple[str, str]] = [
    ("grocery", "Grocery"),
    ("produce", "Produce"),
    ("meat_dairy", "Meat and Dairy"),
    ("frozen", "Frozen"),
    ("household", "Household"),
    ("health_beauty", "Health and Beauty"),
    ("pharmacy", "Pharmacy"),
    ("electronics", "Electronics"),
    ("clothing", "Clothing"),
    ("toys", "Toys"),
    ("home_garden", "Home and Garden"),
    ("sporting", "Sporting Goods"),
    ("seasonal", "Seasonal"),
]

DEPARTMENT_IDS: list[str] = [item[0] for item in DEPARTMENTS]
DEPARTMENT_LABELS: dict[str, str] = dict(DEPARTMENTS)

LEGACY_CATEGORY_TO_DEPARTMENT: dict[str, str] = {
    "everyday": "clothing",
    "statement": "clothing",
    "toys_gentle": "toys",
    "toys_playful": "toys",
    "toys_intense": "toys",
    "accessories": "household",
    "seasonal": "seasonal",
}

MARKDOWN_DAYS = 2
MARKDOWN_PERCENT = 30


def default_department(category: str | None) -> str:
    if not category:
        return "household"
    if category in DEPARTMENT_IDS:
        return category
    return LEGACY_CATEGORY_TO_DEPARTMENT.get(category, "household")


def is_perishable(product: Any) -> bool:
    return int(getattr(product, "shelf_life_days", 0) or 0) > 0


def days_left(product: Any, line: Any) -> int | None:
    life = int(getattr(product, "shelf_life_days", 0) or 0)
    if life <= 0:
        return None
    return life - int(getattr(line, "age_days", 0) or 0)


def in_markdown_window(product: Any, line: Any) -> bool:
    left = days_left(product, line)
    return left is not None and 0 < left <= MARKDOWN_DAYS


def selling_price(product: Any, line: Any) -> int:
    price = int(product.price)
    if in_markdown_window(product, line):
        return max(int(product.cost), price * (100 - MARKDOWN_PERCENT) // 100)
    return price


def _catalog(source: Any | None) -> dict[str, Any]:
    if source is None:
        from open_late.content import PRODUCTS

        return {product.id: product for product in PRODUCTS}
    if hasattr(source, "products"):
        return dict(source.products)
    if isinstance(source, dict):
        return source
    products = {}
    for product in source:
        products[product.id] = product
    return products


def department_of(sku: str, source: Any | None = None) -> str:
    product = _catalog(source).get(sku)
    if product is None:
        return ""
    department = getattr(product, "department", "") or ""
    if department:
        return department
    return default_department(getattr(product, "category", ""))


def products_by_department(source: Any | None = None) -> dict[str, list[Any]]:
    grouped = {dept: [] for dept in DEPARTMENT_IDS}
    for product in _catalog(source).values():
        dept = getattr(product, "department", "") or default_department(getattr(product, "category", ""))
        grouped.setdefault(dept, []).append(product)
    return grouped


def department_sales(state: Any, store_id: str, days: int = 7) -> dict[str, int]:
    """Sum recorded department sales for a store over the last `days` calendar days.

    Figures come from StoreDay.by_department, written at close. Days recorded
    before that field existed, or closes that sold nothing in a department,
    contribute 0.
    """
    totals = {dept: 0 for dept in DEPARTMENT_IDS}
    if state is None or days <= 0:
        return totals
    cutoff = int(state.day) - int(days)
    for record in getattr(state, "store_days", []) or []:
        if record.store_id != store_id or record.day <= cutoff:
            continue
        for dept, amount in (record.by_department or {}).items():
            totals[dept] = totals.get(dept, 0) + int(amount)
    return totals
