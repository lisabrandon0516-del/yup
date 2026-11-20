"""Two hundred thousand shoppers for the trade area.

Each person is built from their number, so the book stays the same every
time it is opened and does not have to be written into the save.

The book is also the population. A campaign or a price cut can draw a
slice of a city's shoppers into that store. The day still rings them as
visits. It does not walk all 200,000 people one by one.
"""

from __future__ import annotations

CUSTOMER_COUNT = 200_000
PAGE_SIZE = 100

_FIRST = (
    "Alicia", "Marcus", "Priya", "Jonah", "Elena", "Chris", "Naomi", "Owen",
    "Sofia", "Andre", "Hannah", "Luis", "Grace", "Noah", "Amina", "Peter",
    "Claire", "Jamal", "Ruth", "Diego", "Megan", "Aaron", "Leah", "Victor",
    "Iris", "Cole", "Fatima", "Henry", "Jade", "Simon", "Nora", "Felix",
    "Bianca", "Troy", "Yara", "Glenn", "Paula", "Micah", "Denise", "Karl",
    "Willa", "Omar", "Stacy", "Brett", "Lana", "Hugh", "Celia", "Dante",
    "Marisol", "Edwin", "Tasha", "Roland", "Gia", "Nolan", "Esther", "Ibrahim",
    "Penny", "Calvin", "June", "Hector", "Ada", "Warren", "Lila", "Seth",
    "Camille", "Roy", "Nadia", "Ellis", "Brooke", "Malik", "Fern", "Oscar",
    "Helen", "Quincy", "Tara", "Vince", "Opal", "Shane", "Keisha", "Boyd",
    "Mina", "Clark", "Rosa", "Dean", "Anita", "Floyd", "Sasha", "Wayne",
)
_LAST = (
    "Adler", "Brooks", "Cho", "Dalton", "Ellis", "Foster", "Garcia", "Hahn",
    "Iverson", "Jones", "Keller", "Lopez", "Meyer", "Nguyen", "Ortiz", "Patel",
    "Quinn", "Reyes", "Shah", "Turner", "Underwood", "Vasquez", "Walker", "Xu",
    "Young", "Zimmer", "Abbott", "Blake", "Carter", "Diaz", "Edwards", "Flynn",
    "Gupta", "Harris", "Ingram", "Jensen", "Knox", "Lambert", "Morales", "Nash",
    "Owens", "Price", "Rowe", "Santos", "Tran", "Upton", "Vega", "Walsh",
    "York", "Zuniga", "Bennett", "Cross", "Doyle", "Farmer", "Gibbs", "Holt",
    "Irwin", "Kane", "Lang", "Moss", "Norris", "Phelps", "Roth", "Stone",
)
_CITIES = (
    "Evansville", "Seattle", "Houston", "Las Vegas", "Naperville",
)
_TEMPER = (
    "plans the list", "buys on impulse", "sticks with one brand", "hunts the ad",
    "is in a hurry", "browses the whole aisle", "checks the label twice", "talks to whoever is stocking",
)
_TONE = ("warm", "blunt", "playful", "quiet", "chatty", "formal")
_HOUSE = (
    "lives alone", "shops for a couple", "shops for a family with kids",
    "shops for teenagers", "is an empty nester", "shares a house with roommates",
    "cares for a parent", "shops for a household of one and a dog",
)
_WORK = (
    "works days", "works nights", "is retired", "is in school",
    "works from home", "works weekends", "is between jobs", "keeps the house",
)
_NEED = (
    "a full pantry restock", "school lunches", "pet food", "a prescription refill",
    "work clothes", "cleaning supplies", "baby supplies", "a week of dinners",
    "sports snacks", "garden basics", "a phone charger", "paper goods",
    "breakfast for the week", "laundry soap", "a cooler of drinks", "pain relief",
)
_WANT = (
    "the better coffee", "a newer television", "name-brand detergent",
    "the ripe produce", "a toy that will last", "store-brand prices on the basics",
    "something new in the seasonal aisle", "a quiet pharmacy counter",
    "clothes that are already on sale", "a treat that was not on the list",
)
_LIKE = (
    "grocery", "produce", "meat and dairy", "frozen food", "household",
    "health and beauty", "pharmacy", "electronics", "clothing", "toys",
    "home and garden", "sporting goods", "seasonal",
)
_DISLIKE = (
    "long lines", "loud music", "a swapped item", "a crowded front end",
    "empty endcaps", "a pushy suggestion", "rain on the walk in",
    "a price that changed since the ad", "self-checkout when the belt is full",
    "a clerk who will not look up",
)
_TRIP = ("a stock-up", "a fill-in", "one errand", "the weekly ad run", "a payday trip")
_WHEN = (
    "weekday mornings", "after work", "Saturday late morning", "Sunday afternoon",
    "Friday evening", "a weeknight", "the first of the month",
)
_CHANNEL = ("the store", "pickup", "delivery", "the store, and pickup when it rains")
_PAY = ("cash", "a debit card", "a credit card", "the store card")
_BRAND = ("national brands", "the store brand", "a mix, and the store brand on paper goods")
_PARK = ("parks in the lot", "takes the bus", "walks", "gets dropped at the door")


def _mix(index: int, salt: int) -> int:
    value = ((index + 1) * 2654435761 + salt * 40503) & 0xFFFFFFFF
    value ^= value >> 16
    value = (value * 2246822519) & 0xFFFFFFFF
    value ^= value >> 13
    return value


def _pick(index: int, salt: int, options: tuple[str, ...]) -> str:
    return options[_mix(index, salt) % len(options)]


def trip_afford_share(price: int) -> float:
    """Share of households whose weekly budget covers this price.

    Budgets run from $40 to $310 in $10 steps, the same steps as ``shopper``.
    A price almost nobody can reach still keeps a thin 8% tail.
    """
    price = max(0, int(price))
    able = sum(1 for step in range(28) if (40 + step * 10) >= price)
    return max(0.08, able / 28.0)


def shopper_name(index: int) -> str:
    """The display name, cheap enough to scan the whole book."""
    first = _FIRST[_mix(index, 1) % len(_FIRST)]
    last = _LAST[_mix(index, 2) % len(_LAST)]
    middle = chr(65 + (_mix(index, 3) % 26))
    return f"{first} {middle}. {last}"


def shopper(index: int) -> dict:
    """One shopper, numbered from 0. The same number always returns the same person."""
    index = int(index) % CUSTOMER_COUNT
    age = 18 + (_mix(index, 4) % 67)
    kids = _mix(index, 5) % 4
    budget = 40 + (_mix(index, 6) % 28) * 10
    likes = []
    for salt in (7, 8, 9):
        item = _pick(index, salt, _LIKE)
        if item not in likes:
            likes.append(item)
    dislikes = []
    for salt in (10, 11):
        item = _pick(index, salt, _DISLIKE)
        if item not in dislikes:
            dislikes.append(item)
    needs = _pick(index, 12, _NEED)
    extra_need = _pick(index, 13, _NEED)
    if extra_need != needs:
        needs = f"{needs}; {extra_need}"
    personality = f"{_pick(index, 14, _TONE).capitalize()}, and {_pick(index, 15, _TEMPER)}"
    person = {
        "number": index + 1,
        "id": f"C{index + 1:06d}",
        "name": shopper_name(index),
        "age": age,
        "city": _pick(index, 16, _CITIES),
        "household": _pick(index, 17, _HOUSE),
        "kids": kids,
        "work": _pick(index, 18, _WORK),
        "personality": personality,
        "needs": needs,
        "wants": _pick(index, 19, _WANT),
        "likes": likes,
        "dislikes": dislikes,
        "budget": budget,
        "trip": _pick(index, 20, _TRIP),
        "when": _pick(index, 21, _WHEN),
        "channel": _pick(index, 22, _CHANNEL),
        "pay": _pick(index, 23, _PAY),
        "brand": _pick(index, 24, _BRAND),
        "arrival": _pick(index, 25, _PARK),
        "patience": 20 + (_mix(index, 26) % 81),
        "discretion": _mix(index, 27) % 101,
        "pushiness": _mix(index, 28) % 101,
        "loyalty": 15 + (_mix(index, 29) % 80),
        "pets": "a pet" if _mix(index, 30) % 3 == 0 else "no pet",
    }
    person["blurb"] = (
        f"{person['name']} is {person['age']}, {person['household']}, and {person['work']}. "
        f"{person['personality']}. Needs {person['needs']}. Wants {person['wants']}. "
        f"Likes {', '.join(person['likes'])}. Dislikes {', '.join(person['dislikes'])}. "
        f"Shops {person['when']} for {person['trip']} at {person['channel']}, "
        f"about ${person['budget']} a week, and pays with {person['pay']}."
    )
    return person


def shopper_page(start: int, size: int = PAGE_SIZE) -> list[dict]:
    start = max(0, min(int(start), CUSTOMER_COUNT - 1))
    last = min(CUSTOMER_COUNT, start + max(1, int(size)))
    return [shopper(index) for index in range(start, last)]


_LIKE_DEPT = {
    "grocery": "grocery",
    "produce": "produce",
    "meat and dairy": "meat_dairy",
    "frozen food": "frozen",
    "household": "household",
    "health and beauty": "health_beauty",
    "pharmacy": "pharmacy",
    "electronics": "electronics",
    "clothing": "clothing",
    "toys": "toys",
    "home and garden": "home_garden",
    "sporting goods": "sporting",
    "seasonal": "seasonal",
}
# Share of the responsive crowd who make the trip on one day.
_AD_REACH = {"social": 0.012, "email": 0.020, "local_ad": 0.018, "influencer": 0.022}
_CAMPAIGN_TONE = {"discreet": 0.85, "playful": 1.0, "bold": 1.15}
_SALE_REACH = 0.02
_CENSUS: dict[str, dict] | None = None


def _census() -> dict[str, dict]:
    """How many store shoppers in each city hunt ads, run the weekly ad, or like an aisle."""
    global _CENSUS
    if _CENSUS is not None:
        return _CENSUS
    blank_likes = {dept: 0 for dept in _LIKE_DEPT.values()}
    cities: dict[str, dict] = {
        city: {"store": 0, "ad": 0, "adrun": 0, "likes": dict(blank_likes)} for city in _CITIES
    }
    temper_ad = _TEMPER.index("hunts the ad")
    trip_ad = _TRIP.index("the weekly ad run")
    for index in range(CUSTOMER_COUNT):
        channel = _CHANNEL[_mix(index, 22) % len(_CHANNEL)]
        if not channel.startswith("the store"):
            continue
        city = _CITIES[_mix(index, 16) % len(_CITIES)]
        bucket = cities[city]
        bucket["store"] += 1
        if _mix(index, 15) % len(_TEMPER) == temper_ad:
            bucket["ad"] += 1
        if _mix(index, 20) % len(_TRIP) == trip_ad:
            bucket["adrun"] += 1
        liked: set[str] = set()
        for salt in (7, 8, 9):
            liked.add(_LIKE_DEPT[_LIKE[_mix(index, salt) % len(_LIKE)]])
        for dept in liked:
            bucket["likes"][dept] += 1
    _CENSUS = cities
    return cities


def _nudge(day: int, city: str, salt: int) -> float:
    value = ((int(day) + 1) * 2246822519 + salt * 3266489917 + sum(ord(char) for char in city)) & 0xFFFFFFFF
    value ^= value >> 16
    return 0.9 + (value % 200) / 1000.0


def census_city(city: str) -> str:
    """The book city for a store. A capital uses its nearest real city, not Evansville every time."""
    name = (city or "").strip()
    if name in _CITIES:
        return name
    names = {
        "evansville": "Evansville",
        "seattle": "Seattle",
        "houston": "Houston",
        "las_vegas": "Las Vegas",
        "naperville": "Naperville",
    }
    key = name.lower().replace(".", "").replace(" ", "_")
    if key in names:
        return names[key]
    try:
        from open_late.us_capitals import CAPITALS, by_id

        row = by_id(key)
        if row is None:
            row = next((item for item in CAPITALS if item.city.lower() == name.lower()), None)
        if row is not None:
            return names.get(row.economy_city, "Evansville")
    except Exception:
        pass
    return "Evansville"


def aisle_tilt(city: str) -> dict[str, float]:
    """How much this city's shoppers lean toward each aisle. 1.0 is an even lean."""
    city = census_city(city)
    bucket = _census().get(city or "")
    if not bucket or int(bucket["store"]) <= 0:
        return {}
    store = int(bucket["store"])
    shares = {dept: int(count) / store for dept, count in bucket["likes"].items()}
    positive = [share for share in shares.values() if share > 0]
    mean = sum(positive) / len(positive) if positive else 1.0
    return {
        dept: 0.8 + 0.2 * (share / mean if mean else 1.0)
        for dept, share in shares.items()
    }


def scale_draw(state, store_id: str, people: int) -> int:
    """The same visit factor that shrinks a storm day also shrinks an ad crowd."""
    if people <= 0:
        return 0
    from open_late.economy import economy_difficulty, visits_mult

    if economy_difficulty(state) == "off":
        return int(people)
    return max(0, int(round(people * visits_mult(state, store_id))))


def population_draw(city: str, campaign, sale_departments, day: int = 1) -> tuple[int, str]:
    """People from this city's book who come in because of an ad or a price cut.

    ``campaign`` is None or an object with kind, tone, and category.
    ``sale_departments`` is the set of departments with an item priced under its list price.
    Returns the extra visits and a sentence for the day note. No campaign and no sale draws nobody.
    """
    city = census_city(city)
    bucket = _census().get(city or "")
    if not bucket or bucket["store"] <= 0:
        return 0, ""
    parts: list[str] = []
    drawn = 0
    if campaign is not None:
        kind = str(getattr(campaign, "kind", "") or "")
        tone = str(getattr(campaign, "tone", "") or "")
        reach = _AD_REACH.get(kind, 0.0) * _CAMPAIGN_TONE.get(tone, 1.0)
        if reach > 0:
            likes = int(bucket["likes"].get(str(getattr(campaign, "category", "") or ""), 0))
            if kind == "email":
                pool = int(bucket["ad"])
            else:
                rest = max(0, int(bucket["store"]) - int(bucket["ad"]))
                pool = int(bucket["ad"]) + int(likes * rest / int(bucket["store"]))
            arrived = int(round(pool * reach * _nudge(day, city, 1)))
            if arrived > 0:
                drawn += arrived
                label = kind.replace("_", " ")
                parts.append(f"{arrived:,} answered the {label}")
    departments = [str(dept) for dept in (sale_departments or ()) if str(dept)]
    if departments:
        counts = sorted((int(bucket["likes"].get(dept, 0)) for dept in set(departments)), reverse=True)
        interested = counts[0] + int(0.4 * sum(counts[1:])) if counts else 0
        interested = min(int(bucket["store"]), interested)
        pool = int(interested * int(bucket["adrun"]) / int(bucket["store"]))
        arrived = int(round(pool * _SALE_REACH * _nudge(day, city, 2)))
        if arrived > 0:
            drawn += arrived
            parts.append(f"{arrived:,} came in for a sale")
    if drawn <= 0:
        return 0, ""
    return drawn, f"{drawn:,} people from the {city} trade area came in. " + ". ".join(parts) + "."


_SHOPPER_HITS: dict[str, list[int]] = {}
_SHOPPER_HIT_KEYS: list[str] = []


def shopper_hits(query: str) -> list[int]:
    """Every shopper number whose name or id matches, in book order."""
    text = (query or "").strip().lower()
    if not text:
        return []
    cached = _SHOPPER_HITS.get(text)
    if cached is not None:
        return cached
    token = text[1:] if text.startswith("c") else text
    if token.isdigit():
        number = int(token)
        found = [number - 1] if 1 <= number <= CUSTOMER_COUNT else []
    else:
        found = [index for index in range(CUSTOMER_COUNT) if text in shopper_name(index).lower()]
    if text not in _SHOPPER_HITS:
        _SHOPPER_HITS[text] = found
        _SHOPPER_HIT_KEYS.append(text)
        while len(_SHOPPER_HIT_KEYS) > 4:
            _SHOPPER_HITS.pop(_SHOPPER_HIT_KEYS.pop(0), None)
    return found


def shopper_search_page(query: str, offset: int = 0, size: int = PAGE_SIZE) -> tuple[list[dict], int]:
    hits = shopper_hits(query)
    offset = max(0, int(offset))
    page = hits[offset:offset + max(0, int(size))]
    return [shopper(index) for index in page], len(hits)


def find_shoppers(query: str, limit: int = PAGE_SIZE) -> list[dict]:
    """Match a shopper number or a piece of a name. Stops after ``limit`` hits."""
    text = (query or "").strip().lower()
    if not text:
        return []
    token = text[1:] if text.startswith("c") else text
    if token.isdigit():
        number = int(token)
        if 1 <= number <= CUSTOMER_COUNT:
            return [shopper(number - 1)]
        return []
    found = []
    for index in range(CUSTOMER_COUNT):
        if text in shopper_name(index).lower():
            found.append(shopper(index))
            if len(found) >= limit:
                break
    return found
