"""Three shares of the crowd already drawn. Not a new basket for every person.

Price-sensitive walks are the price walks. Stock-up walks are an empty grocery
or household shelf. Trip-for-one walks are an empty shelf in any other department.
"""

from __future__ import annotations

# Shares of the people who came. The remainder stays with the price-sensitive share.
SHARES = (
    ("Price-sensitive", 40),
    ("Stock-up", 35),
    ("Trip-for-one", 25),
)
STOCK_DEPTS = ("grocery", "household")


def crowd_split(visits: int) -> dict[str, int]:
    visits = max(0, int(visits))
    counts = [visits * share // 100 for _name, share in SHARES]
    counts[0] += visits - sum(counts)
    return {name: counts[index] for index, (name, _share) in enumerate(SHARES)}


def shopper_walks(report) -> dict[str, int]:
    """How many of each type walked, capped by how many of that type came."""
    came = crowd_split(int(getattr(report, "visits", 0) or 0))
    by_category = getattr(report, "lost_stockout_by_category", None) or {}
    stock_empty = sum(int(by_category.get(dept, 0) or 0) for dept in STOCK_DEPTS)
    stock_walk = min(came["Stock-up"], stock_empty)
    trip_walk = min(came["Trip-for-one"], max(0, int(getattr(report, "lost_stockout", 0) or 0) - stock_walk))
    price_walk = min(came["Price-sensitive"], int(getattr(report, "lost_price", 0) or 0))
    return {
        "Price-sensitive": price_walk,
        "Stock-up": stock_walk,
        "Trip-for-one": trip_walk,
    }


def shopper_sentence(report) -> str:
    visits = int(getattr(report, "visits", 0) or 0)
    if visits <= 0:
        return "No crowd on this close."
    came = crowd_split(visits)
    walked = shopper_walks(report)
    return (
        f"Came: price-sensitive {came['Price-sensitive']:,}, "
        f"stock-up {came['Stock-up']:,}, "
        f"trip-for-one {came['Trip-for-one']:,}. "
        f"Walked: price-sensitive {walked['Price-sensitive']:,} because the shelf was above the list, "
        f"stock-up {walked['Stock-up']:,} because grocery or household was empty, "
        f"trip-for-one {walked['Trip-for-one']:,} because the item they came for was gone."
    )
