"""Fifty state capitals, 2020 Census counts, and the desk's lease facts.

Population and race shares are the capital city's 2020 Census profile from the
user's source file (U.S. Census Bureau). Hispanic/Latino is an ethnicity and
overlaps the race shares, so the shares are not a pie.

Coordinates are the capital city's location, WGS84, so the map dot sits on
that city rather than on the state's middle. Sales tax is the state general
rate. Withholding is a flat teaching rate for the paycheck, not a tax return.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Capital:
    abbr: str
    state: str
    city: str
    population: int
    white: float
    black: float
    hispanic: float
    asian: float
    native: float
    multi: float
    lon: float
    lat: float
    sales_tax_bps: int
    withhold_per_ten_thousand: int
    region: str
    economy_city: str
    ident: str


# abbr, state, capital, population, white, black, hispanic, asian, native, multi,
# longitude, latitude, sales-tax bps, withholding per 10,000, census region
_ROWS: tuple[tuple, ...] = (
    ("AL", "Alabama", "Montgomery", 200_603, 29.7, 60.8, 3.9, 3.2, 0.3, 2.3, -86.3077, 32.3792, 400, 500, "South"),
    ("AK", "Alaska", "Juneau", 32_255, 65.1, 1.0, 7.2, 6.6, 12.1, 9.5, -134.4197, 58.3019, 0, 0, "West"),
    ("AZ", "Arizona", "Phoenix", 1_608_139, 49.7, 7.8, 42.6, 3.8, 2.1, 8.2, -112.0740, 33.4484, 560, 250, "West"),
    ("AR", "Arkansas", "Little Rock", 202_591, 43.1, 41.9, 10.6, 3.1, 0.5, 5.4, -92.2896, 34.7465, 650, 440, "South"),
    ("CA", "California", "Sacramento", 524_943, 42.3, 13.2, 28.9, 19.1, 1.8, 9.7, -121.4944, 38.5816, 725, 600, "West"),
    ("CO", "Colorado", "Denver", 715_522, 68.9, 9.2, 29.9, 3.7, 1.7, 8.2, -104.9903, 39.7392, 290, 440, "West"),
    ("CT", "Connecticut", "Hartford", 121_054, 31.3, 37.8, 44.3, 2.8, 0.6, 9.1, -72.6734, 41.7658, 635, 500, "Northeast"),
    ("DE", "Delaware", "Dover", 39_403, 44.8, 43.0, 8.4, 2.7, 0.7, 5.8, -75.5244, 39.1582, 0, 660, "South"),
    ("FL", "Florida", "Tallahassee", 196_169, 54.5, 35.0, 7.3, 4.6, 0.3, 4.8, -84.2807, 30.4383, 600, 0, "South"),
    ("GA", "Georgia", "Atlanta", 498_715, 40.8, 47.6, 6.0, 5.1, 0.3, 5.2, -84.3880, 33.7490, 400, 549, "South"),
    ("HI", "Hawaii", "Honolulu", 350_964, 17.9, 1.5, 7.3, 54.8, 0.2, 22.9, -157.8583, 21.3069, 400, 700, "West"),
    ("ID", "Idaho", "Boise", 235_684, 81.8, 1.6, 9.0, 3.2, 0.9, 7.5, -116.2023, 43.6150, 600, 580, "West"),
    ("IL", "Illinois", "Springfield", 114_394, 69.6, 20.9, 3.4, 3.0, 0.3, 5.8, -89.6501, 39.7817, 625, 495, "Midwest"),
    ("IN", "Indiana", "Indianapolis", 887_642, 58.5, 28.6, 10.5, 3.9, 0.4, 6.6, -86.1581, 39.7684, 700, 295, "Midwest"),
    ("IA", "Iowa", "Des Moines", 214_133, 69.1, 11.4, 14.2, 6.7, 0.6, 7.9, -93.6250, 41.5868, 600, 570, "Midwest"),
    ("KS", "Kansas", "Topeka", 126_587, 72.4, 10.6, 16.5, 1.8, 1.4, 8.4, -95.6752, 39.0473, 650, 570, "Midwest"),
    ("KY", "Kentucky", "Frankfort", 28_602, 72.7, 17.6, 5.4, 2.0, 0.3, 5.6, -84.8733, 38.2009, 600, 400, "South"),
    ("LA", "Louisiana", "Baton Rouge", 227_470, 36.6, 56.1, 4.0, 3.2, 0.3, 3.2, -91.1871, 30.4515, 445, 425, "South"),
    ("ME", "Maine", "Augusta", 18_899, 89.1, 3.3, 2.4, 1.5, 0.8, 6.1, -69.7795, 44.3106, 550, 580, "Northeast"),
    ("MD", "Maryland", "Annapolis", 40_812, 60.1, 21.4, 16.8, 2.4, 0.3, 5.3, -76.4922, 38.9784, 600, 475, "South"),
    ("MA", "Massachusetts", "Boston", 675_647, 52.1, 24.2, 19.5, 11.2, 0.4, 7.0, -71.0589, 42.3601, 625, 500, "Northeast"),
    ("MI", "Michigan", "Lansing", 112_644, 57.4, 22.9, 13.0, 4.1, 0.8, 9.8, -84.5555, 42.7325, 600, 425, "Midwest"),
    ("MN", "Minnesota", "Saint Paul", 311_527, 50.5, 18.5, 9.8, 19.2, 1.1, 8.4, -93.0900, 44.9537, 688, 700, "Midwest"),
    ("MS", "Mississippi", "Jackson", 153_701, 15.7, 82.0, 1.5, 0.5, 0.2, 1.8, -90.1848, 32.2988, 700, 500, "South"),
    ("MO", "Missouri", "Jefferson City", 43_228, 73.5, 18.9, 3.3, 2.3, 0.3, 5.0, -92.1735, 38.5767, 423, 480, "Midwest"),
    ("MT", "Montana", "Helena", 32_091, 88.7, 0.6, 3.5, 1.0, 2.7, 6.7, -112.0391, 46.5891, 0, 500, "West"),
    ("NE", "Nebraska", "Lincoln", 291_082, 78.7, 4.4, 7.7, 4.7, 0.8, 7.3, -96.7026, 40.8136, 550, 580, "Midwest"),
    ("NV", "Nevada", "Carson City", 58_639, 73.4, 2.3, 25.1, 2.6, 2.0, 8.1, -119.7674, 39.1638, 685, 0, "West"),
    ("NH", "New Hampshire", "Concord", 43_976, 87.9, 3.0, 3.1, 4.1, 0.3, 5.0, -71.5376, 43.2081, 0, 0, "Northeast"),
    ("NJ", "New Jersey", "Trenton", 90_871, 33.7, 48.7, 36.4, 1.8, 0.6, 8.5, -74.7597, 40.2206, 663, 550, "Northeast"),
    ("NM", "New Mexico", "Santa Fe", 87_505, 72.3, 1.2, 52.3, 1.6, 2.1, 9.3, -105.9378, 35.6870, 513, 490, "West"),
    ("NY", "New York", "Albany", 99_224, 54.0, 29.0, 9.3, 6.9, 0.4, 7.8, -73.7562, 42.6526, 400, 600, "Northeast"),
    ("NC", "North Carolina", "Raleigh", 467_665, 57.5, 28.9, 11.3, 5.5, 0.4, 5.8, -78.6382, 35.7796, 475, 450, "South"),
    ("ND", "North Dakota", "Bismarck", 73_622, 84.5, 3.6, 2.9, 1.3, 4.3, 6.2, -100.7837, 46.8083, 500, 200, "Midwest"),
    ("OH", "Ohio", "Columbus", 905_748, 57.4, 29.2, 6.3, 5.8, 0.3, 6.4, -82.9988, 39.9612, 575, 350, "Midwest"),
    ("OK", "Oklahoma", "Oklahoma City", 681_054, 58.4, 14.1, 20.0, 4.5, 4.6, 10.4, -97.5164, 35.4676, 450, 475, "South"),
    ("OR", "Oregon", "Salem", 175_535, 75.5, 1.4, 23.3, 3.3, 1.6, 9.3, -123.0351, 44.9429, 0, 800, "West"),
    ("PA", "Pennsylvania", "Harrisburg", 50_099, 29.8, 50.7, 20.4, 5.2, 0.5, 8.6, -76.8867, 40.2732, 600, 307, "Northeast"),
    ("RI", "Rhode Island", "Providence", 190_934, 43.3, 14.4, 43.5, 6.6, 1.2, 13.3, -71.4128, 41.8240, 700, 500, "Northeast"),
    ("SC", "South Carolina", "Columbia", 136_632, 49.2, 40.9, 5.8, 3.1, 0.3, 5.2, -81.0348, 34.0007, 600, 640, "South"),
    ("SD", "South Dakota", "Pierre", 14_091, 80.4, 1.5, 3.4, 1.1, 10.9, 6.3, -100.3510, 44.3683, 450, 0, "Midwest"),
    ("TN", "Tennessee", "Nashville", 689_447, 63.5, 27.1, 10.6, 3.8, 0.4, 5.4, -86.7816, 36.1627, 700, 0, "South"),
    ("TX", "Texas", "Austin", 961_855, 68.4, 7.9, 32.5, 8.9, 0.9, 7.0, -97.7431, 30.2672, 625, 0, "South"),
    ("UT", "Utah", "Salt Lake City", 199_723, 72.8, 2.6, 21.8, 5.4, 1.4, 8.2, -111.8910, 40.7608, 610, 465, "West"),
    ("VT", "Vermont", "Montpelier", 8_074, 89.9, 1.5, 3.1, 2.6, 0.4, 5.5, -72.5754, 44.2601, 600, 600, "Northeast"),
    ("VA", "Virginia", "Richmond", 226_610, 45.2, 45.8, 7.2, 2.1, 0.3, 6.2, -77.4360, 37.5407, 530, 575, "South"),
    ("WA", "Washington", "Olympia", 55_605, 76.1, 3.1, 8.1, 6.7, 1.6, 10.3, -122.9007, 47.0379, 650, 0, "West"),
    ("WV", "West Virginia", "Charleston", 48_864, 78.4, 15.5, 1.8, 2.3, 0.3, 5.1, -81.6326, 38.3498, 600, 500, "South"),
    ("WI", "Wisconsin", "Madison", 269_840, 75.7, 7.1, 8.7, 9.5, 0.5, 6.0, -89.4012, 43.0731, 500, 530, "Midwest"),
    ("WY", "Wyoming", "Cheyenne", 65_132, 84.5, 2.3, 15.1, 1.3, 1.0, 7.0, -104.8202, 41.1400, 400, 0, "West"),
)

_PROXIES = {
    "evansville": (-87.55, 37.97),
    "seattle": (-122.33, 47.61),
    "houston": (-95.37, 29.76),
    "las_vegas": (-115.14, 36.17),
    "naperville": (-88.15, 41.75),
}

_HIGH_WAGE = frozenset({"CA", "NY", "HI", "MA", "WA", "AK", "CT", "NJ", "OR", "MD"})
_MID_WAGE = frozenset({"CO", "IL", "MN", "VA", "NH", "VT", "RI", "DE", "AZ", "NV", "ME"})


def slug(city: str) -> str:
    return city.lower().replace(".", "").replace(" ", "_")


def _miles(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    radius = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * radius * math.asin(min(1.0, math.sqrt(a)))


def _nearest_economy_city(lon: float, lat: float) -> str:
    best = "evansville"
    best_miles = 1e18
    for ident, (elon, elat) in _PROXIES.items():
        miles = _miles(lon, lat, elon, elat)
        if miles < best_miles:
            best = ident
            best_miles = miles
    return best


def _build() -> tuple[Capital, ...]:
    rows = []
    for row in _ROWS:
        abbr, state, city, pop, white, black, hispanic, asian, native, multi, lon, lat, sales, withhold, region = row
        rows.append(Capital(
            abbr=abbr,
            state=state,
            city=city,
            population=int(pop),
            white=float(white),
            black=float(black),
            hispanic=float(hispanic),
            asian=float(asian),
            native=float(native),
            multi=float(multi),
            lon=float(lon),
            lat=float(lat),
            sales_tax_bps=int(sales),
            withhold_per_ten_thousand=int(withhold),
            region=region,
            economy_city=_nearest_economy_city(float(lon), float(lat)),
            ident=slug(city),
        ))
    return tuple(rows)


CAPITALS: tuple[Capital, ...] = _build()
BY_ID: dict[str, Capital] = {item.ident: item for item in CAPITALS}
BY_ABBR: dict[str, Capital] = {item.abbr: item for item in CAPITALS}
STATE_ABBR: dict[str, str] = {item.state: item.abbr for item in CAPITALS}

assert len(CAPITALS) == 50
assert len(BY_ID) == 50


def economy_proxy(store_id: str) -> str:
    item = BY_ID.get(store_id or "")
    return item.economy_city if item is not None else ""


def by_id(store_id: str) -> Capital | None:
    return BY_ID.get(store_id or "")


def by_abbr(abbr: str) -> Capital | None:
    return BY_ABBR.get(abbr or "")


def demographic_line(item: Capital) -> str:
    return (
        f"White {item.white:.1f}% · Black {item.black:.1f}% · "
        f"Hispanic/Latino {item.hispanic:.1f}% · Asian {item.asian:.1f}% · "
        f"Native American {item.native:.1f}% · Two or more {item.multi:.1f}%"
    )


def place_tip(item: Capital) -> str:
    return (
        f"{item.city}, {item.state} · capital · {item.population:,} people (2020 Census). "
        f"{demographic_line(item)}. "
        "Hispanic/Latino is an ethnicity and overlaps the race shares."
    )


def lease_scale(item: Capital) -> dict[str, int]:
    """Weekly rent, opening cost, traffic, freight, and days. Dollars are pre-size."""
    span = math.log(1_608_139) - math.log(8_074)
    weight = (math.log(max(8_074, item.population)) - math.log(8_074)) / span
    weight = max(0.0, min(1.0, weight))
    rent = int(round(3_800 + weight * 7_200))
    opening = int(round(34_000 + weight * 26_000))
    if item.abbr in _HIGH_WAGE:
        wage = 1_400
    elif item.abbr in _MID_WAGE:
        wage = 900
    else:
        wage = 580
    miles = _miles(item.lon, item.lat, -87.55, 37.97)
    freight = max(2, min(9, 2 + int(miles // 400)))
    transit = max(1, min(7, int(round(miles / 450)) or 1))
    if item.population < 100_000:
        build = 8
    elif item.population < 500_000:
        build = 12
    else:
        build = 16
    traffic = max(90, min(780, 70 + item.population // 2_800))
    return {
        "rent_weekly": rent,
        "opening_cost": opening,
        "min_cash_after": int(opening * 0.45),
        "wage_floor": wage,
        "freight_per_unit": freight,
        "transit_days": transit,
        "build_days": build,
        "foot_traffic": traffic,
    }
