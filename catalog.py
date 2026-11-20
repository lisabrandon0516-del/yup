"""Warehouse list of 200,500 items the store can order.

An item stays off the live sheet until a truck is actually placed, so the
day does not walk a quarter-million stock lines every morning.
"""

from __future__ import annotations

import heapq

from open_late.models import Product, StockLine

ITEM_COUNT = 200_500
PAGE_SIZE = 80

# Department, supplier, brand, shelf life in days, low cost, high cost.
_HOUSES = (
    ("grocery", "meadowgrove", "Meadowgrove", 0, 2, 8),
    ("produce", "orchard", "Orchard Lane", 6, 2, 7),
    ("meat_dairy", "coldfield", "Coldfield", 8, 3, 14),
    ("frozen", "coldfield", "Frostbank", 0, 3, 9),
    ("household", "soapstone", "Soapstone", 0, 2, 12),
    ("health_beauty", "riverwell", "Riverwell", 0, 3, 16),
    ("pharmacy", "riverwell", "Clearwell", 0, 4, 18),
    ("electronics", "sparklane", "Sparklane", 0, 12, 80),
    ("clothing", "millthread", "Millthread", 0, 6, 28),
    ("toys", "playnook", "Playnook", 0, 4, 24),
    ("home_garden", "yardwell", "Yardwell", 0, 5, 40),
    ("sporting", "yardwell", "Trailbench", 0, 6, 36),
    ("seasonal", "festoon", "Festoon", 0, 4, 30),
)

_FORMS = (
    "Bagged", "Boxed", "Canned", "Jarred", "Family", "Store", "Value", "Select",
    "Kitchen", "Weeknight", "Travel", "Twin", "Party", "Basic", "House",
)
_GOODS = {
    "grocery": ("rice", "oats", "beans", "pasta", "crackers", "soup", "cereal", "coffee", "flour", "sugar", "oil", "sauce"),
    "produce": ("apples", "bananas", "berries", "lettuce", "carrots", "onions", "potatoes", "oranges", "grapes", "peppers"),
    "meat_dairy": ("chicken", "turkey", "pork", "yogurt", "cheddar", "milk", "butter", "eggs", "ham", "sausage"),
    "frozen": ("peas", "fries", "pizza", "waffles", "ice cream", "burritos", "corn", "meals", "berries", "fish"),
    "household": ("paper towels", "detergent", "trash bags", "dish soap", "sponges", "foil", "tissues", "bleach"),
    "health_beauty": ("shampoo", "soap", "lotion", "toothpaste", "razors", "deodorant", "conditioner", "cotton"),
    "pharmacy": ("pain relief", "cold tablets", "vitamins", "bandages", "antacid", "allergy tablets", "first aid"),
    "electronics": ("headphones", "charger", "batteries", "mouse", "speaker", "cable", "tablet case", "earbuds"),
    "clothing": ("tees", "socks", "jeans", "hoodies", "polos", "shorts", "underwear", "fleece"),
    "toys": ("blocks", "dolls", "cars", "puzzles", "games", "figures", "plush", "craft kits"),
    "home_garden": ("towels", "pillows", "tools", "soil", "pots", "lamps", "rugs", "storage bins"),
    "sporting": ("balls", "gloves", "water bottles", "weights", "bikes locks", "camps chairs", "helmets"),
    "seasonal": ("lights", "decor", "wrap", "candy", "patio chairs", "ornaments", "flags", "wreaths"),
}
_SIZES = ("8 oz", "12 oz", "16 oz", "32 oz", "2 lb", "5 lb", "6-pack", "12-pack", "24-pack", "each", "family pack")
_TRENDS = ("steady", "steady", "steady", "rising", "fading")

# Titles and shelf prices taken from the Great Value page on walmart.com.
# A zero price means the page listed the item and did not show a dollar amount.
_WALMART = (
    ("Great Value Sweet Hawaiian Rolls, 12 oz, 12 Count", "grocery", "Great Value", "meadowgrove", 4, 2),
    ("Great Value Cheddar Broccoli Flavored Pasta & Sauce, 4.3 oz", "grocery", "Great Value", "meadowgrove", 0, 1),
    ("Great Value Ready to Bake Regular Chocolate Chip Cookie Dough, 16.5 oz", "grocery", "Great Value", "meadowgrove", 0, 3),
    ("Great Value Brown Butter Cookie, 12 Count", "grocery", "Great Value", "meadowgrove", 0, 4),
    ("Great Value Butter Flavor Syrup, 24 fl oz", "grocery", "Great Value", "meadowgrove", 0, 2),
    ("Great Value Chocolate Chip Chewy Granola Bars, 24 Count", "grocery", "Great Value", "meadowgrove", 0, 5),
    ("Great Value Chewy Granola Bars Variety Pack, 24 Count", "grocery", "Great Value", "meadowgrove", 0, 0),
    ("Great Value Jellied Cranberry Sauce, 14 oz", "grocery", "Great Value", "meadowgrove", 0, 2),
    ("Great Value Savory Steak Sauce, 10 oz", "grocery", "Great Value", "meadowgrove", 0, 3),
    ("Great Value Premium Original Shells & Cheese, 12 oz", "grocery", "Great Value", "meadowgrove", 0, 1),
    ("Great Value Cheese Crackers, 12.4 oz", "grocery", "Great Value", "meadowgrove", 0, 3),
    ("Great Value Baked Buttery Round Crackers, 13.7 oz", "grocery", "Great Value", "meadowgrove", 0, 0),
    ("Great Value Nonpareil Capers, 3.5 oz", "grocery", "Great Value", "meadowgrove", 0, 2),
    ("Great Value Paprika, 2.5 oz", "grocery", "Great Value", "meadowgrove", 0, 0),
    ("Great Value Chili Powder, 3 oz", "grocery", "Great Value", "meadowgrove", 0, 1),
    ("Great Value Cut Green Beans, 14.5 oz Can", "grocery", "Great Value", "meadowgrove", 0, 0),
    ("Great Value Golden Sweet Whole Kernel Corn, 15.25 oz", "grocery", "Great Value", "meadowgrove", 0, 0),
    ("Great Value Chunk Chicken Breast in Water, 12.5 oz, 4 Pack", "grocery", "Great Value", "meadowgrove", 0, 10),
    ("Great Value Alfredo Pasta Sauce, 16 oz", "grocery", "Great Value", "meadowgrove", 0, 0),
    ("Great Value Flavored with Meat Pasta Sauce, 24 oz", "grocery", "Great Value", "meadowgrove", 0, 2),
    ("Great Value Cheese Ravioli Pasta, 25 oz", "grocery", "Great Value", "meadowgrove", 0, 4),
    ("Great Value Cheddar Broccoli Rice & Sauce, 5.7 oz", "grocery", "Great Value", "meadowgrove", 0, 1),
    ("Great Value White Sandwich Bread, 20 oz", "grocery", "Great Value", "meadowgrove", 4, 2),
    ("Great Value Brown and Serve White Dinner Rolls, 12 oz, 12 Count", "grocery", "Great Value", "meadowgrove", 4, 0),
    ("Great Value Purified Drinking Water, 16.9 fl oz, 24 Count", "grocery", "Great Value", "meadowgrove", 0, 4),
    ("Great Value Naturally Hickory Smoked Sliced Bacon, 16 oz", "meat_dairy", "Great Value", "coldfield", 10, 0),
    ("Great Value Beef & Bean Burritos, 32 oz, 8 Count", "frozen", "Great Value", "coldfield", 0, 4),
    ("Great Value Blueberry Pancakes and Sausage on a Stick, 30 oz, 12 Count", "frozen", "Great Value", "coldfield", 0, 8),
    ("Great Value Chicken Breast Patties, Breaded, 23.8 oz", "frozen", "Great Value", "coldfield", 0, 6),
    ("Great Value Fully Cooked Chicken Nuggets, 32 oz", "frozen", "Great Value", "coldfield", 0, 6),
    ("Great Value Chicken Fries, 27.5 oz", "frozen", "Great Value", "coldfield", 0, 7),
    ("Great Value Flour Chicken Taquitos, 19.2 oz, 16 Count", "frozen", "Great Value", "coldfield", 0, 5),
    ("Great Value Sausage Egg and Cheese Breakfast Burritos, 32 oz, 8 Count", "frozen", "Great Value", "coldfield", 0, 9),
    ("Great Value Cookies & Cream Ice Cream, 48 fl oz", "frozen", "Great Value", "coldfield", 0, 3),
    ("Great Value Frozen Yeast Dinner Rolls, 15 oz, 10 Count", "frozen", "Great Value", "coldfield", 0, 3),
    ("Great Value BR30 LED Floodlight Bulbs, Soft White, 4 Pack", "household", "Great Value", "soapstone", 0, 8),
    ("Great Value BR30 LED Floodlight Bulb, Daylight, 4 Pack", "household", "Great Value", "soapstone", 0, 8),
    ("Great Value BR30 LED Floodlight Bulb, Soft White 8W, 4 Pack", "household", "Great Value", "soapstone", 0, 13),
    ("Great Value BR30 LED Floodlight Bulbs, Adjustable, 8 Pack", "household", "Great Value", "soapstone", 0, 18),
    ("Great Value A19 LED 3-Way Light Bulb, Daylight", "household", "Great Value", "soapstone", 0, 9),
    ("Great Value A19 3-Way LED Light Bulb, Soft White, 4 Pack", "household", "Great Value", "soapstone", 0, 6),
    ("Great Value A21 LED 3-Way Light Bulb, Soft White", "household", "Great Value", "soapstone", 0, 0),
    ("Great Value A19 LED Decorative Green Light Bulbs, 2 Pack", "household", "Great Value", "soapstone", 0, 7),
    ("Great Value A19 Dusk-to-Dawn LED Light Bulb, 9W", "household", "Great Value", "soapstone", 0, 6),
)

# Dog food, cat food, and pet toys. Retail is an integer dollar shelf price.
_PETS = (
    ("Ol' Roy Complete Nutrition dry dog food, 20 lb", "grocery", "Ol' Roy", "meadowgrove", 0, 13),
    ("Pedigree Adult Complete Nutrition dry dog food, 18 lb", "grocery", "Pedigree", "meadowgrove", 0, 18),
    ("Purina Dog Chow Complete Adult dry dog food, 18.5 lb", "grocery", "Purina Dog Chow", "meadowgrove", 0, 16),
    ("Kibbles 'n Bits Original dry dog food, 16 lb", "grocery", "Kibbles 'n Bits", "meadowgrove", 0, 15),
    ("Iams ProActive Health Adult dry dog food, 15 lb", "grocery", "Iams", "meadowgrove", 0, 22),
    ("Beneful Originals dry dog food, 14 lb", "grocery", "Beneful", "meadowgrove", 0, 20),
    ("Purina ONE SmartBlend Chicken dry dog food, 16.5 lb", "grocery", "Purina ONE", "meadowgrove", 0, 24),
    ("Cesar Classics wet dog food, 12 count", "grocery", "Cesar", "meadowgrove", 0, 14),
    ("Blue Buffalo Life Protection dry dog food, 15 lb", "grocery", "Blue Buffalo", "meadowgrove", 0, 42),
    ("Rachael Ray Nutrish dry dog food, 14 lb", "grocery", "Nutrish", "meadowgrove", 0, 28),
    ("Hill's Science Diet Adult dry dog food, 15 lb", "grocery", "Hill's Science Diet", "meadowgrove", 0, 48),
    ("Royal Canin Adult dry dog food, 17 lb", "grocery", "Royal Canin", "meadowgrove", 0, 55),
    ("Taste of the Wild High Prairie dry dog food, 14 lb", "grocery", "Taste of the Wild", "meadowgrove", 0, 46),
    ("Merrick Grain Free dry dog food, 10 lb", "grocery", "Merrick", "meadowgrove", 0, 40),
    ("Nutro Natural Choice dry dog food, 13 lb", "grocery", "Nutro", "meadowgrove", 0, 36),
    ("Diamond Naturals Chicken and Rice dry dog food, 18 lb", "grocery", "Diamond Naturals", "meadowgrove", 0, 32),
    ("Victor Hi-Pro Plus dry dog food, 15 lb", "grocery", "Victor", "meadowgrove", 0, 34),
    ("Fromm Gold Adult dry dog food, 15 lb", "grocery", "Fromm", "meadowgrove", 0, 38),
    ("Wellness CORE dry dog food, 12 lb", "grocery", "Wellness", "meadowgrove", 0, 44),
    ("Canidae All Life Stages dry dog food, 15 lb", "grocery", "Canidae", "meadowgrove", 0, 40),
    ("Acana Regionals dry dog food, 13 lb", "grocery", "Acana", "meadowgrove", 0, 52),
    ("Orijen Original dry dog food, 13 lb", "grocery", "Orijen", "meadowgrove", 0, 58),
    ("Natural Balance Limited Ingredient dry dog food, 12 lb", "grocery", "Natural Balance", "meadowgrove", 0, 36),
    ("Bil-Jac Select dry dog food, 6 lb", "grocery", "Bil-Jac", "meadowgrove", 0, 18),
    ("Eukanuba Adult dry dog food, 15 lb", "grocery", "Eukanuba", "meadowgrove", 0, 30),
    ("Special Kitty dry cat food, 16 lb", "grocery", "Special Kitty", "meadowgrove", 0, 11),
    ("Meow Mix Original dry cat food, 16 lb", "grocery", "Meow Mix", "meadowgrove", 0, 14),
    ("Purina Cat Chow Complete dry cat food, 15 lb", "grocery", "Purina Cat Chow", "meadowgrove", 0, 15),
    ("Friskies Seafood Sensations dry cat food, 16 lb", "grocery", "Friskies", "meadowgrove", 0, 16),
    ("9Lives Plus Care dry cat food, 12 lb", "grocery", "9Lives", "meadowgrove", 0, 13),
    ("Fancy Feast Grilled wet cat food, 24 count", "grocery", "Fancy Feast", "meadowgrove", 0, 18),
    ("Iams ProActive Health Adult dry cat food, 7 lb", "grocery", "Iams", "meadowgrove", 0, 16),
    ("Purina ONE Tender Selects dry cat food, 7 lb", "grocery", "Purina ONE", "meadowgrove", 0, 17),
    ("Sheba Perfect Portions wet cat food, 24 count", "grocery", "Sheba", "meadowgrove", 0, 22),
    ("Blue Buffalo Wilderness dry cat food, 5 lb", "grocery", "Blue Buffalo", "meadowgrove", 0, 24),
    ("Kong Classic dog toy", "toys", "Kong", "playnook", 0, 13),
    ("Nylabone Power Chew dog toy", "toys", "Nylabone", "playnook", 0, 11),
    ("Chuckit Ultra Ball dog toy, 2 pack", "toys", "Chuckit", "playnook", 0, 9),
    ("Benebone Wishbone dog toy", "toys", "Benebone", "playnook", 0, 14),
    ("Outward Hound puzzle dog toy", "toys", "Outward Hound", "playnook", 0, 16),
    ("Petstages Cat Tracks cat toy", "toys", "Petstages", "playnook", 0, 8),
    ("Yeowww Catnip Banana cat toy", "toys", "Yeowww", "playnook", 0, 7),
    ("SmartyKat Hot Pursuit cat toy", "toys", "SmartyKat", "playnook", 0, 10),
    ("Jackson Galaxy Air Prey cat toy", "toys", "Jackson Galaxy", "playnook", 0, 12),
    ("Hartz Just for Cats cat toy assortment", "toys", "Hartz", "playnook", 0, 6),
)
_NAMED = _WALMART + _PETS


def _mix(index: int, salt: int) -> int:
    value = ((index + 1) * 2246822519 + salt * 3266489917) & 0xFFFFFFFF
    value ^= value >> 16
    value = (value * 668265263) & 0xFFFFFFFF
    return value


def item_id(index: int) -> str:
    return f"cat-{index + 1:06d}"


def catalog_record(index: int) -> dict:
    """One warehouse item, numbered from 0. The same number is always the same item."""
    index = int(index) % ITEM_COUNT
    if index < len(_NAMED):
        name, dept, brand, supplier, shelf, retail = _NAMED[index]
        if retail:
            price = int(retail)
            cost = max(1, price * 70 // 100)
        else:
            low = 2
            high = 8
            cost = low + (_mix(index, 5) % max(1, high - low))
            price = max(cost + 1, cost * 14 // 10)
        return {
            "number": index + 1,
            "index": index,
            "id": item_id(index),
            "name": name,
            "department": dept,
            "supplier_id": supplier,
            "brand": brand,
            "cost": int(cost),
            "price": int(price),
            "quality": 4,
            "case_size": 12 if index < len(_WALMART) else (6 if dept == "toys" else 4),
            "shelf_life_days": int(shelf),
            "trend": "steady",
            "source": "walmart",
        }
    house = _HOUSES[_mix(index, 1) % len(_HOUSES)]
    dept, supplier, brand, shelf, low, high = house
    goods = _GOODS[dept]
    good = goods[_mix(index, 2) % len(goods)]
    form = _FORMS[_mix(index, 3) % len(_FORMS)]
    size = _SIZES[_mix(index, 4) % len(_SIZES)]
    span = max(1, high - low)
    cost = low + (_mix(index, 5) % span)
    margin = 30 + (_mix(index, 6) % 50)
    price = max(cost + 1, cost * (100 + margin) // 100)
    if price > cost * 5:
        price = cost * 5
    quality = 2 + (_mix(index, 7) % 4)
    case_size = (6, 12, 24)[_mix(index, 8) % 3]
    trend = _TRENDS[_mix(index, 9) % len(_TRENDS)]
    return {
        "number": index + 1,
        "index": index,
        "id": item_id(index),
        "name": f"{form} {good}, {size}",
        "department": dept,
        "supplier_id": supplier,
        "brand": brand,
        "cost": int(cost),
        "price": int(price),
        "quality": int(quality),
        "case_size": int(case_size),
        "shelf_life_days": int(shelf),
        "trend": trend,
    }


def catalog_product(index: int) -> Product:
    row = catalog_record(index)
    return Product(
        id=row["id"],
        name=row["name"],
        category=row["department"],
        department=row["department"],
        quality=row["quality"],
        cost=row["cost"],
        price=row["price"],
        trend=row["trend"],
        supplier_id=row["supplier_id"],
        brand=row["brand"],
        blurb=f"Warehouse item {row['id']}. Case of {row['case_size']}.",
        shelf_life_days=row["shelf_life_days"],
        case_size=row["case_size"],
    )


def catalog_page(start: int, department: str = "", size: int = PAGE_SIZE) -> list[dict]:
    """A page of items. A department walks the whole list until the page is full."""
    start = max(0, int(start))
    if not department:
        last = min(ITEM_COUNT, start + size)
        return [catalog_record(index) for index in range(start, last)]
    found = []
    index = start
    while index < ITEM_COUNT and len(found) < size:
        row = catalog_record(index)
        if row["department"] == department:
            found.append(row)
        index += 1
    return found


_TOKEN_LISTS: dict[str, list[int]] | None = None
_DEPT_LISTS: dict[str, list[int]] | None = None
_MATCHES: dict[tuple[str, str], list[int]] = {}
_MATCH_KEYS: list[tuple[str, str]] = []


def _words(text: str) -> list[str]:
    words: list[str] = []
    current: list[str] = []
    for char in text.lower():
        if char.isalnum():
            current.append(char)
        elif current:
            words.append("".join(current))
            current = []
    if current:
        words.append("".join(current))
    return words


def _word_lists(choices: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
    return tuple(tuple(dict.fromkeys(_words(choice))) for choice in choices)


_FORM_WORDS = _word_lists(_FORMS)
_SIZE_WORDS = _word_lists(_SIZES)
_GOOD_WORDS = {dept: _word_lists(goods) for dept, goods in _GOODS.items()}
_HOUSE_WORDS = tuple(
    (dept, tuple(dict.fromkeys(_words(f"{brand} {dept.replace('_', ' ')}"))))
    for dept, _supplier, brand, _shelf, _low, _high in _HOUSES
)


def _add_word(tokens: dict[str, list[int]], word: str, index: int) -> None:
    bucket = tokens.get(word)
    if bucket is None:
        tokens[word] = [index]
    elif bucket[-1] != index:
        bucket.append(index)


def _ensure_index() -> None:
    """Word and department lists for every warehouse item, built once."""
    global _TOKEN_LISTS, _DEPT_LISTS
    if _TOKEN_LISTS is not None:
        return
    tokens: dict[str, list[int]] = {}
    depts: dict[str, list[int]] = {}
    houses = _HOUSE_WORDS
    house_count = len(houses)
    form_words = _FORM_WORDS
    form_count = len(form_words)
    size_words = _SIZE_WORDS
    size_count = len(size_words)
    good_words = _GOOD_WORDS
    mix = _mix
    add = _add_word
    for index, item in enumerate(_NAMED):
        name, dept, brand = item[0], item[1], item[2]
        depts.setdefault(dept, []).append(index)
        for word in dict.fromkeys(_words(f"{name} {brand} {dept.replace('_', ' ')}")):
            add(tokens, word, index)
    for index in range(len(_NAMED), ITEM_COUNT):
        dept, label_words = houses[mix(index, 1) % house_count]
        goods = good_words[dept]
        depts.setdefault(dept, []).append(index)
        for word in form_words[mix(index, 3) % form_count]:
            add(tokens, word, index)
        for word in goods[mix(index, 2) % len(goods)]:
            add(tokens, word, index)
        for word in size_words[mix(index, 4) % size_count]:
            add(tokens, word, index)
        for word in label_words:
            add(tokens, word, index)
    _TOKEN_LISTS = tokens
    _DEPT_LISTS = depts


def _union(lists: list[list[int]]) -> list[int]:
    if not lists:
        return []
    if len(lists) == 1:
        return lists[0]
    merged: list[int] = []
    last = -1
    for value in heapq.merge(*lists):
        if value != last:
            merged.append(value)
            last = value
    return merged


def _intersect(left: list[int], right: list[int]) -> list[int]:
    found: list[int] = []
    right_at = 0
    for value in left:
        while right_at < len(right) and right[right_at] < value:
            right_at += 1
        if right_at < len(right) and right[right_at] == value:
            found.append(value)
    return found


def _remember(key: tuple[str, str], ids: list[int]) -> list[int]:
    if key not in _MATCHES:
        _MATCHES[key] = ids
        _MATCH_KEYS.append(key)
        while len(_MATCH_KEYS) > 8:
            _MATCHES.pop(_MATCH_KEYS.pop(0), None)
    return _MATCHES[key]


def match_ids(query: str = "", department: str = "") -> list[int]:
    """Every item number that matches, in catalog order."""
    text = (query or "").strip().lower()
    department = department or ""
    key = (text, department)
    cached = _MATCHES.get(key)
    if cached is not None:
        return cached
    token = text[4:] if text.startswith("cat-") else text
    if token.isdigit():
        number = int(token)
        ids = [number - 1] if 1 <= number <= ITEM_COUNT else []
    elif not text:
        ids = None
    else:
        _ensure_index()
        assert _TOKEN_LISTS is not None
        words = _words(text)
        ids = None
        keys = list(_TOKEN_LISTS)
        for word in words:
            lists = [_TOKEN_LISTS[name] for name in keys if word in name]
            found = _union(lists)
            ids = found if ids is None else _intersect(ids, found)
            if not ids:
                break
        if ids is None:
            ids = []
    if department:
        _ensure_index()
        assert _DEPT_LISTS is not None
        dept_ids = _DEPT_LISTS.get(department, [])
        ids = dept_ids if ids is None else _intersect(ids, dept_ids)
    return _remember(key, ids or [])


def match_count(query: str = "", department: str = "") -> int:
    if not (query or "").strip() and not department:
        return ITEM_COUNT
    return len(match_ids(query, department))


def search_page(
    query: str = "",
    offset: int = 0,
    limit: int = PAGE_SIZE,
    department: str = "",
) -> tuple[list[dict], int]:
    """One page of matches and the count of matches in the whole catalog."""
    offset = max(0, int(offset))
    limit = max(0, int(limit))
    if not (query or "").strip() and not department:
        last = min(ITEM_COUNT, offset + limit)
        return [catalog_record(index) for index in range(offset, last)], ITEM_COUNT
    ids = match_ids(query, department)
    page = ids[offset:offset + limit]
    return [catalog_record(index) for index in page], len(ids)


def find_items(
    query: str,
    limit: int = PAGE_SIZE,
    offset: int = 0,
    department: str = "",
) -> list[dict]:
    if not (query or "").strip() and not department:
        return []
    rows, _total = search_page(query, offset, limit, department)
    return rows


def carry_item(state, product_id: str) -> None:
    """Every store that sells from the sheet needs a stock line, even at zero."""
    if product_id not in state.stock:
        state.stock[product_id] = StockLine(product_id=product_id, on_hand=0, on_order=0)
    for door in getattr(state, "doors", ()) or ():
        if product_id not in door.stock:
            door.stock[product_id] = StockLine(product_id=product_id, on_hand=0, on_order=0)


def adopt_item(state, index: int) -> Product:
    """Copy one warehouse item onto the live sheet and give every store an empty stock line."""
    product = catalog_product(index)
    current = state.products.get(product.id)
    if current is None:
        state.products[product.id] = product
        current = product
    carry_item(state, current.id)
    return current
