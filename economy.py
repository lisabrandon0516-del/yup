"""Weekly economy tick and week-card for Back Office: Retail (patches E1–E2).

E1 is the framework, Sunday tick, week card, and core apply. E2 adds weather
and supply-chain factors, a daily weather overlay, one-disaster-per-city,
and the news feed. Neutral/off is an identity transform, so existing tests
stay bit-identical when difficulty is off. Harvest Card (24) lifts grocery,
meat_dairy, and frozen demand in reload weeks, and is identity when off. E3 finishes all 120 factors. Rent pressure, CAM, fixture
wear, parking fees, and warehouse rent fold into the existing rent line.
E4 is the attribution desk, multi-week card replay, and the 104/106 tax fold. E6 couples difficulty with common random numbers: the same unit shocks and event draws across tiers, then visible levers (sigma, event odds, caps, event duration, walk bias, and downside skew) change only the amplitude.
"""

from __future__ import annotations

import hashlib
import math
import random
from typing import Any

from open_late.departments import DEPARTMENT_IDS, DEPARTMENT_LABELS
from open_late.models import GameState
from open_late.text import is_sunday

DIFFICULTIES = ("off", "calm", "standard", "stern")
DEFAULT_DIFFICULTY = "off"
DIFFICULTY_LABELS = {
    "off": "Off",
    "calm": "Calm",
    "standard": "Standard",
    "stern": "Stern",
}
SIGMA_MULT = {"off": 0.0, "calm": 0.32, "standard": 0.48, "stern": 1.35}
CAP_MULT = {"off": 0.0, "calm": 0.70, "standard": 0.88, "stern": 1.0}  # Stern stays 1.0 (E4 pin). Calm and standard clip a little tighter at supercenter volume.
EVENT_P_MULT = {"off": 0.0, "calm": 0.40, "standard": 0.55, "stern": 1.35}
# Raw event length is drawn once per (week, factor, city); this scales the accepted span.
EVENT_DURATION_MULT = {"off": 1.0, "calm": 1.0, "standard": 1.0, "stern": 1.05}
# Player-signed card bias in index points: + helps the shop (more visits, lower costs).
# Walks themselves stay mean-0; this is applied to baked visits/demand/cost/freight/labor/rent.
# E7e retune after the leftover-constant pack (Harvest Card demand, delayed
# Northline entry). Other lever tables stay at the E7c / E4 pins.
WALK_BIAS = {"off": 0.0, "calm": 2.30, "standard": 1.55, "stern": -0.70}
# Extra stretch on unhelpful card deviations (low visits or high costs). Standard stays symmetric.
DOWN_SKEW = {"off": 0.0, "calm": 0.0, "standard": 0.0, "stern": 0.01}

SALES_CAP = 0.22
COGS_CAP = 0.15
# E8: shrink baked cost deviations from 100 (commodity walks and
# shortage/inspection pulses) so one seed cannot sit several points
# above another for months. Off already bakes 100. Caps and levers
# are unchanged; WALK_BIAS still applies in cost_mult.
COST_VAR_DAMP = 0.50
FREIGHT_CAP = 0.25
DELTA_RANGE_FRAC = 0.40
CITY_RESIDUAL_FRAC = 0.60

CITIES = ("evansville", "seattle", "houston", "las_vegas", "naperville")
CITY_SALT = {
    "evansville": 1,
    "seattle": 2,
    "houston": 3,
    "las_vegas": 4,
    "naperville": 5,
}

# Commodity factor id -> department.
COMMODITY = {
    67: "grocery",
    68: "produce",
    69: "meat_dairy",
    70: "frozen",
    71: "household",
    72: "health_beauty",
    73: "pharmacy",
    74: "electronics",
    75: "clothing",
    76: "toys",
    77: "home_garden",
    78: "sporting",
    79: "seasonal",
}
DEPT_COMMODITY = {dept: fid for fid, dept in COMMODITY.items()}
IMPORT_DEPTS = {"electronics", "toys", "clothing", "seasonal", "sporting"}
PAYDAY_DEPTS = ("grocery", "household", "meat_dairy", "produce")
HARVEST_CARD_DEPTS = ("grocery", "meat_dairy", "frozen")
HARVEST_CARD_LIFT = 1.08  # same amplitude as the payday hook
SCHOOL_DEPTS = ("clothing", "toys", "household", "grocery")
GIFT_DEPTS = ("electronics", "toys", "seasonal", "clothing")
HIGH_INCOME_DEPTS = ("electronics", "clothing", "pharmacy")
LOW_INCOME_DEPTS = ("grocery", "frozen", "household")

# E1 active set: 1-10, 11-14, 21, 23-26, 67-79.
E1_NATIONAL = tuple(range(1, 11)) + (23, 24, 25, 26) + tuple(range(67, 80))
E1_LOCAL = (11, 12, 13, 14, 21)
E1_IDS = frozenset(E1_NATIONAL + E1_LOCAL)
# E2: weather 37-46, supply chain 57-66.
E2_WEATHER = tuple(range(37, 47))
E2_SUPPLY = tuple(range(57, 67))
E2_IDS = frozenset(E2_WEATHER + E2_SUPPLY)
E2_CITY_WALKS = (37, 38, 42)
CITY_WALK_IDS = E1_LOCAL + E2_CITY_WALKS
from open_late.economy_e3 import E3_CITY_WALKS, E3_STORE_WALKS, WALKS_E3, EVENT_SPEC_E3, E3_IDS, E3_DISASTER_RANK

CITY_WALK_IDS = CITY_WALK_IDS + E3_CITY_WALKS
STORE_WALK_IDS = (63,) + E3_STORE_WALKS

# Walk parameters for independent E1 walks: id -> (theta, sigma, mu, low, high)
WALKS = {
    1: (0.12, 0.35, 100, 70, 140),
    2: (0.15, 1.10, 100, 60, 140),
    3: (0.10, 0.50, 100, 70, 140),
    4: (0.08, 0.45, 100, 80, 140),
    6: (0.14, 1.40, 100, 70, 180),
    7: (0.16, 1.20, 100, 70, 160),
    8: (0.12, 0.70, 100, 75, 125),
    9: (0.10, 0.80, 100, 70, 130),
    10: (0.10, 0.90, 100, 80, 150),
    11: (0.18, 0.80, 100, 70, 140),
    12: (0.12, 0.60, 100, 70, 150),
    13: (0.12, 0.70, 100, 80, 150),
    14: (0.06, 0.30, 100, 80, 125),
    21: (0.16, 0.90, 100, 70, 130),
    67: (0.12, 0.80, 100, 80, 145),
    68: (0.20, 1.60, 100, 70, 170),
    69: (0.16, 1.30, 100, 75, 160),
    70: (0.12, 0.70, 100, 80, 140),
    71: (0.12, 0.70, 100, 80, 140),
    72: (0.10, 0.60, 100, 80, 135),
    73: (0.10, 0.60, 100, 80, 145),
    74: (0.10, 1.00, 100, 75, 160),
    75: (0.10, 0.80, 100, 80, 145),
    76: (0.10, 0.80, 100, 80, 145),
    77: (0.12, 1.00, 100, 75, 155),
    78: (0.10, 0.70, 100, 80, 140),
    79: (0.14, 1.20, 100, 75, 160),
    37: (0.25, 2.00, 100, 70, 160),
    38: (0.25, 2.00, 100, 70, 160),
    42: (0.08, 0.80, 100, 80, 160),
    57: (0.10, 0.50, 100, 100, 160),
    58: (0.16, 1.10, 100, 70, 160),
    59: (0.14, 0.80, 100, 70, 130),
    62: (0.12, 0.80, 100, 80, 140),
    63: (0.20, 0.90, 100, 80, 150),
}
WALKS.update(WALKS_E3)

# id, name, category, scope, driver, (low, high)
_FACTOR_ROWS: list[tuple] = [
    (1, "Policy rate", "national_macro", "national", "Walk θ=0.12, σ=0.35, μ=100", (70, 140)),
    (2, "Consumer confidence", "national_macro", "national", "Walk θ=0.15, σ=1.1, μ=100; link 1, 5", (60, 140)),
    (3, "National unemployment", "national_macro", "national", "Walk θ=0.10, σ=0.5, μ=100", (70, 140)),
    (4, "Basket inflation", "national_macro", "national", "Walk θ=0.08, σ=0.45, μ=100; link 67-79", (80, 140)),
    (5, "Real disposable income", "national_macro", "national", "Link 2, 4, 3, residual σ=0.4", (70, 130)),
    (6, "National diesel index", "national_macro", "national", "Walk θ=0.14, σ=1.4, μ=100", (70, 180)),
    (7, "Freight capacity tightness", "national_macro", "national", "Walk θ=0.16, σ=1.2, μ=100; link 6", (70, 160)),
    (8, "National activity", "national_macro", "national", "Walk θ=0.12, σ=0.7, μ=100; link 2", (75, 125)),
    (9, "Housing mood", "national_macro", "national", "Walk θ=0.10, σ=0.8, μ=100; cycle 52 weeks", (70, 130)),
    (10, "Import cost index", "national_macro", "national", "Walk θ=0.10, σ=0.9, μ=100", (80, 150)),
    (11, "City traffic baseline", "local_regional", "city", "Walk θ=0.18, σ=0.8, μ=100", (70, 140)),
    (12, "Local unemployment", "local_regional", "city", "Walk θ=0.12, σ=0.6, μ=100; link 3", (70, 150)),
    (13, "Local wage pressure", "local_regional", "city", "Walk θ=0.12, σ=0.7, μ=100; link 12", (80, 150)),
    (14, "Neighborhood income mix", "local_regional", "city", "Walk θ=0.06, σ=0.3, μ=100", (80, 125)),
    (15, "Tourism pulse", "local_regional", "city", "Cycle 52 weeks, A=18 Las Vegas / 8 Seattle / 2 others; event p=0.05 convention week", (60, 160)),
    (16, "Access and sprawl", "local_regional", "city", "Walk θ=0.08, σ=0.3, μ=100; event p=0.04 road work, 1–3 weeks", (70, 120)),
    (17, "Local road work", "local_regional", "city", "Event p=0.06, duration 1–3 weeks, cooldown 6", (0, 1)),
    (18, "Anchor employer health", "local_regional", "city", "Walk θ=0.08, σ=0.7, μ=100; event p=0.02 layoff or hiring wave, cooldown 20", (60, 140)),
    (19, "Local housing costs", "local_regional", "city", "Walk θ=0.07, σ=0.5, μ=100; link 0.3×9; Seattle and Naperville higher μ", (80, 150)),
    (20, "Regional energy price", "local_regional", "city", "Walk θ=0.14, σ=1.0, μ=100; link 0.45×6", (70, 160)),
    (21, "Local confidence residual", "local_regional", "city", "Walk θ=0.16, σ=0.9, μ=100; link 2", (70, 130)),
    (22, "Late-hour traffic", "local_regional", "city", "Cycle 7 days, A=12 Las Vegas Fri–Sat / 4 others; link nightlife reputation", (70, 140)),
    (23, "Payday cycle", "seasonal_calendar", "national", "Cycle period 14 days, amplitude 8", (92, 112)),
    (24, "Harvest Card reload", "seasonal_calendar", "national", "Reload-week demand lift on grocery, meat_dairy, frozen; identity when off", (100, 118)),
    (25, "Back to school", "seasonal_calendar", "national", "Cycle 52 weeks, peak weeks 32-35", (90, 120)),
    (26, "Year-end gift week", "seasonal_calendar", "national", "Cycle 52 weeks, peak weeks 47-51", (85, 125)),
    (27, "Refund-season lift", "seasonal_calendar", "national", "Cycle 52 weeks, A=10, peak weeks 8–14", (95, 115)),
    (28, "Summer grill peak", "seasonal_calendar", "national", "Cycle 52 weeks, A=12, peak weeks 22–32", (90, 118)),
    (29, "Winter comfort", "seasonal_calendar", "national", "Cycle 52 weeks, A=12, peak weeks 48–8", (90, 118)),
    (30, "Spring garden", "seasonal_calendar", "national", "Cycle 52 weeks, A=16, peak weeks 12–20", (88, 120)),
    (31, "Midyear holiday week", "seasonal_calendar", "national", "Event on a fixed midyear week (26), duration 1 week, every year", (0, 1)),
    (32, "Late-summer travel weekend", "seasonal_calendar", "national", "Event, fixed weekend near week 35, duration 3 days", (0, 1)),
    (33, "New Year reset", "seasonal_calendar", "national", "Cycle, trough week 1–2, A=10", (88, 100)),
    (34, "Sweetheart week", "seasonal_calendar", "national", "Cycle, peak week 7, A=8, 9 days", (100, 112)),
    (35, "Harvest Night week", "seasonal_calendar", "national", "Cycle, peak week 43, A=14, 2 weeks", (100, 118)),
    (36, "Benefit-calendar lag", "seasonal_calendar", "national", "Link to 24; event p=0.08 in reload week to slip 1–2 days", (0, 2)),
    (37, "Heat index", "weather_disasters", "city", "Walk θ=0.25, σ=2.0, μ=seasonal cycle; event p=0.05 heat wave", (70, 160)),
    (38, "Cold snap", "weather_disasters", "city", "Walk θ=0.25, σ=2.0, μ=seasonal; event p=0.05, Houston rarely high", (70, 160)),
    (39, "Heavy rain", "weather_disasters", "city", "Event p=0.08, 1–4 days, cooldown 3 weeks", (0, 1)),
    (40, "Ice or snow", "weather_disasters", "city", "Event p=0.07 Seattle/Naperville/Evansville, p=0.01 Houston/Las Vegas, 1–3 days, cooldown 4", (0, 1)),
    (41, "Severe storm / outage", "weather_disasters", "city", "Event p=0.02, 1–2 days, cooldown 16, severity 1–3", (0, 1)),
    (42, "Drought", "weather_disasters", "city", "Walk θ=0.08, σ=0.8, μ=100; event p=0.02, 4–10 weeks, cooldown 26", (80, 160)),
    (43, "Poor air quality", "weather_disasters", "city", "Event p=0.04, 2–7 days, cooldown 8; Seattle and Houston more often", (0, 1)),
    (44, "Basin storm (freight)", "weather_disasters", "national", "Event p=0.015, 2–3 weeks, cooldown 26; Houston door also takes a local hit", (0, 1)),
    (45, "Midwest wind event", "weather_disasters", "city", "Event p=0.02 Evansville / 0.005 others, 1–3 days, cooldown 20", (0, 1)),
    (46, "Case thaw after outage", "weather_disasters", "store", "Link: fires only if 41 severity ≥2 and frozen/meat_dairy on hand; duration 1 day", (0, 40)),
    (47, "Hire tightness", "labor_market", "city", "Walk θ=0.14, σ=0.8, μ=100; link 0.5× inverted 12 + 0.2×8", (70, 150)),
    (48, "Turnover risk", "labor_market", "store", "Walk θ=0.15, σ=0.7, μ=100; link 0.4×56 + 0.3×47", (70, 150)),
    (49, "Weather no-shows", "labor_market", "store", "Link 0.5×(37 or 38 or 40) + residual event p=0.05", (0, 25)),
    (50, "Overtime pressure", "labor_market", "store", "Link hours over 8 + 31/32/26 peaks + tightness 47", (100, 140)),
    (51, "Schedule rigidity", "labor_market", "city", "Walk θ=0.1, σ=0.4, μ=110 Seattle / 100 others", (90, 130)),
    (52, "Summer youth supply", "labor_market", "city", "Cycle 52 weeks, A=10, peak weeks 22–32", (90, 115)),
    (53, "Pharmacy coverage scarcity", "labor_market", "city", "Walk θ=0.1, σ=0.8, μ=108; event p=0.03, cooldown 12", (80, 150)),
    (54, "Night-shift premium", "labor_market", "city", "Link 22 + local 13; Las Vegas μ higher", (100, 125)),
    (55, "Training quality", "labor_market", "store", "Walk θ=0.2, σ=0.6, μ=100; improves when someone is on training", (80, 120)),
    (56, "Wage gap vs market", "labor_market", "store", "Link (player wage / (floor × 13/100)) vs 100, weekly", (70, 140)),
    (57, "Port delay", "supply_chain", "national", "Event p=0.04, 2–5 weeks, cooldown 10; walk residual σ=0.5", (100, 160)),
    (58, "Truck availability", "supply_chain", "national", "Walk θ=0.16, σ=1.1, μ=100; link 0.4×7 + 0.2×6", (70, 160)),
    (59, "Cold-chain integrity", "supply_chain", "national", "Walk θ=0.14, σ=0.8, μ=100; event p=0.03 equipment failure, 1 week", (70, 130)),
    (60, "Lead-time slip", "supply_chain", "national", "Link 0.5×57 + 0.3×58 + 0.2×7, residual σ=0.4; +0–6 days", (0, 6)),
    (61, "House relationship residual", "supply_chain", "store", "Link existing SupplierAccount.relationship; small walk σ=0.3", (0, 100)),
    (62, "Packaging cost", "supply_chain", "national", "Walk θ=0.12, σ=0.8, μ=100; link 0.25×4", (80, 140)),
    (63, "Warehouse congestion", "supply_chain", "store", "Walk θ=0.2, σ=0.9, μ=100 at Evansville warehouse; event p=0.04", (80, 150)),
    (64, "Inspection hold", "supply_chain", "national", "Event p=0.025, 1–3 weeks, cooldown 14, dept tagged", (0, 1)),
    (65, "Fuel-to-freight pass-through", "supply_chain", "national", "Link 0.7×6 + 0.3×7, lag 1 week", (70, 170)),
    (66, "Shortage allocation", "supply_chain", "department", "Event p=0.03 per dept/year-equivalent, duration 2–4 weeks, cooldown 16", (0, 1)),
    (67, "Grocery staples index", "commodity_prices", "department", "Walk θ=0.12, σ=0.8, μ=100; link 4", (80, 145)),
    (68, "Produce index", "commodity_prices", "department", "Walk θ=0.20, σ=1.6, μ=100", (70, 170)),
    (69, "Meat and dairy index", "commodity_prices", "department", "Walk θ=0.16, σ=1.3, μ=100; link 4", (75, 160)),
    (70, "Frozen index", "commodity_prices", "department", "Walk θ=0.12, σ=0.7, μ=100", (80, 140)),
    (71, "Household paper and chem", "commodity_prices", "department", "Walk θ=0.12, σ=0.7, μ=100; link 4", (80, 140)),
    (72, "Health and beauty inputs", "commodity_prices", "department", "Walk θ=0.10, σ=0.6, μ=100; link 4, 10", (80, 135)),
    (73, "Pharmacy inputs", "commodity_prices", "department", "Walk θ=0.10, σ=0.6, μ=100", (80, 145)),
    (74, "Electronics components", "commodity_prices", "department", "Walk θ=0.10, σ=1.0, μ=100; link 10", (75, 160)),
    (75, "Apparel fibers", "commodity_prices", "department", "Walk θ=0.10, σ=0.8, μ=100; link 10, 4", (80, 145)),
    (76, "Toys inputs", "commodity_prices", "department", "Walk θ=0.10, σ=0.8, μ=100; link 10", (80, 145)),
    (77, "Garden and lumber inputs", "commodity_prices", "department", "Walk θ=0.12, σ=1.0, μ=100; link 9", (75, 155)),
    (78, "Sporting goods inputs", "commodity_prices", "department", "Walk θ=0.10, σ=0.7, μ=100; link 10, 4", (80, 140)),
    (79, "Seasonal goods index", "commodity_prices", "department", "Walk θ=0.14, σ=1.2, μ=100; link 10, 7", (75, 160)),
    (80, "Northline price index", "competition", "store", "Extends Rival.price_index; walk θ=0.15, σ=0.8; war (84) pulls it down", (86, 120)),
    (81, "Northline heat", "competition", "store", "Extends flags.competitor; walk + Sunday trigger after a month at supercenter volume", (0, 100)),
    (82, "Northline focus", "competition", "store", "Slow Markov every 4–8 weeks among departments; grocery-weighted", (0, 1)),
    (83, "New banner entry", "competition", "city", "Event p=0.01, cooldown 40 weeks, duration 12 weeks fade; Westfork Basket or Lane & Barrel", (0, 1)),
    (84, "Price-war intensity", "competition", "city", "Event p=0.03 if 81 high, duration 2–5 weeks, cooldown 12", (0, 30)),
    (85, "Ad clutter", "competition", "city", "Walk θ=0.15, σ=0.7, μ=100; rises after local_ad / influencer", (80, 140)),
    (86, "Online marketplace pressure", "competition", "national", "Walk θ=0.08, σ=0.6, μ=100; cycle mild at 26", (80, 130)),
    (87, "Local specialist", "competition", "city", "Event p=0.02, duration 8–16 weeks, cooldown 24; dept produce or pharmacy", (0, 1)),
    (88, "Lease / rent pressure", "real_estate_costs", "city", "Walk θ=0.06, σ=0.35, μ=100; link 0.3×19; rare event p=0.015; folds into rent", (90, 130)),
    (89, "Common-area recovery", "real_estate_costs", "city", "Walk θ=0.08, σ=0.4, μ=100; CAM add-on folded into rent", (90, 125)),
    (90, "Insurance premium", "real_estate_costs", "store", "Walk θ=0.08, σ=0.4, μ=100; jumps after 41/44/45", (90, 140)),
    (91, "Utility rate", "real_estate_costs", "city", "Walk θ=0.12, σ=0.7, μ=100; link 0.5×20 + heat/cold", (80, 150)),
    (92, "Fixture wear", "real_estate_costs", "store", "Walk θ=0.05, σ=0.3, μ=100; jumps after 45; folds a little into rent", (90, 130)),
    (93, "Parking and access", "real_estate_costs", "store", "Walk θ=0.08, σ=0.3, μ=100; link 17; visits and a mild rent fold", (90, 120)),
    (94, "Warehouse rent pressure", "real_estate_costs", "store", "Walk θ=0.07, σ=0.35, μ=100 at Evansville warehouse; folds into rent", (90, 125)),
    (95, "Build-out cost inflation", "real_estate_costs", "city", "Walk θ=0.08, σ=0.5, μ=100; link 0.3×4 + 0.2×77; multiplies opening_cost", (90, 140)),
    (96, "Credit spread", "finance", "national", "Walk θ=0.12, σ=0.5, μ=100; link 0.6×1", (80, 140)),
    (97, "Card network rate", "finance", "national", "Walk θ=0.08, σ=0.25, μ=100; event p=0.02, +6 pts, cooldown 20", (90, 120)),
    (98, "Credit-limit tightness", "finance", "store", "Link 99 + 96; event p=0.02 freeze, cooldown 16", (80, 130)),
    (99, "Working-capital stress", "finance", "store", "Link (payables + inventory) / cash, weekly", (70, 160)),
    (100, "Inventory carrying", "finance", "store", "Link on-hand cost, especially clothing size runs and electronics", (80, 140)),
    (101, "Import payables FX", "finance", "national", "Link 0.8×10, lag 1 week", (80, 150)),
    (102, "Shortfall climate", "finance", "store", "Link unpaid Sundays (flags.shortfalls) + 96", (100, 160)),
    (103, "Float timing", "finance", "national", "Cycle with 23 and Sunday bills", (95, 110)),
    (104, "Sales-tax drift", "regulation_taxes", "city", "Walk θ=0.04, σ=0.15, μ=100; rare event p=0.01, cooldown 40", (96, 108)),
    (105, "Employer payroll load", "regulation_taxes", "national", "Walk θ=0.05, σ=0.2, μ=100 (100 = today's 7.65%)", (95, 115)),
    (106, "State withholding climate", "regulation_taxes", "city", "Walk θ=0.04, σ=0.2, μ=100; Houston, Seattle, Las Vegas stay at 0 bps", (95, 110)),
    (107, "Wage-floor move", "regulation_taxes", "city", "Event p=0.015, cooldown 26, +0–8% of wage_floor", (0, 8)),
    (108, "Fair-schedule tightness", "regulation_taxes", "city", "Walk θ=0.1, σ=0.4, μ=110 Seattle / 100 others; event p=0.03 extra penalty week", (100, 130)),
    (109, "Safety and pharmacy inspection", "regulation_taxes", "store", "Event p=0.03, cooldown 10; 0–3 days disruption", (0, 1)),
    (110, "Bag and packaging rule", "regulation_taxes", "city", "Event p=0.02, permanent step +4–8 on 62 until repealed", (0, 1)),
    (111, "Ad and labeling rule", "regulation_taxes", "national", "Event p=0.02, 4–8 weeks, cooldown 20; bold campaigns weaker", (0, 1)),
    (112, "Fresh-food tilt", "consumer_trends", "national", "Walk θ=0.12, σ=0.7, μ=100; cycle mild spring", (80, 125)),
    (113, "Value / trade-down", "consumer_trends", "national", "Walk θ=0.14, σ=0.8, μ=100; link 0.4× inverted 5 + 0.3×4", (80, 130)),
    (114, "Home-cooking vs prepared", "consumer_trends", "national", "Walk θ=0.12, σ=0.6, μ=100 (high = cooking)", (80, 125)),
    (115, "Screen and gadget cycle", "consumer_trends", "national", "Walk θ=0.10, σ=0.8, μ=100; event p=0.03 new set week, 3 weeks, cooldown 16", (80, 130)),
    (116, "Outdoor and field mood", "consumer_trends", "national", "Walk θ=0.12, σ=0.7, μ=seasonal; link 30/28", (80, 125)),
    (117, "House-brand willingness", "consumer_trends", "national", "Walk θ=0.10, σ=0.5, μ=100; link 0.4×113", (80, 125)),
    (118, "Self-care wave", "consumer_trends", "national", "Walk θ=0.12, σ=0.7, μ=100; event p=0.04 cold/heat wave link", (80, 130)),
    (119, "Local fad", "consumer_trends", "city", "Event p=0.04, 2–4 weeks, cooldown 8; random dept except pharmacy", (100, 140)),
    (120, "Trust and reviews", "consumer_trends", "store", "Link existing review_score + returns + incidents; walk σ=0.3", (80, 120)),
]


# Categorical flags, counters, and linked book values. Not on the 100-neutral
# index scale. Neutral is the resting value (0 for a clear flag, 50 for house
# relationship). Kendra's movers-strip examples "Northline focus" and
# "House relationship residual" are ids 82 and 61, not 1 and 42.
STATE_NEUTRAL: dict[int, int] = {
    17: 0,
    31: 0,
    32: 0,
    36: 0,
    39: 0,
    40: 0,
    41: 0,
    43: 0,
    44: 0,
    45: 0,
    46: 0,
    49: 0,
    60: 0,
    61: 50,
    64: 0,
    66: 0,
    81: 0,
    82: 0,
    83: 0,
    84: 0,
    87: 0,
    107: 0,
    109: 0,
    110: 0,
    111: 0,
}

FACTORS: dict[int, dict[str, Any]] = {
    row[0]: {
        "id": row[0],
        "name": row[1],
        "category": row[2],
        "scope": row[3],
        "driver": row[4],
        "range": list(row[5]),
        "kind": "state" if row[0] in STATE_NEUTRAL else "index",
        "neutral": STATE_NEUTRAL.get(row[0], 100),
    }
    for row in _FACTOR_ROWS
}

GAUGE_IDS = (1, 2, 4, 6, 7)
# National factors whose level is set by the macro layer when the economy is on.
MACRO_DRIVEN = frozenset((1, 2, 3, 4, 8))  # 1 added in phase 2 (Fed)


def week_id(day: int) -> int:
    return (max(1, int(day)) - 1) // 7


def week_of_year(day: int) -> int:
    return week_id(day) % 52


def is_payday(day: int) -> bool:
    pos = (max(1, int(day)) - 1) % 28
    return pos in (0, 1, 14, 15)


def is_harvest_card_week(day: int) -> bool:
    """Week of the 1st in each 28-day block (reload week)."""
    return (max(1, int(day)) - 1) % 28 < 7


def normalize_difficulty(value: str | None) -> str:
    if value is None or value == "":
        return DEFAULT_DIFFICULTY
    key = str(value).strip().lower()
    if key not in DIFFICULTIES:
        raise ValueError(f"Unknown economy difficulty: {value}")
    return key


def economy_difficulty(state: GameState) -> str:
    eco = getattr(state, "economy", None)
    if eco is None:
        return DEFAULT_DIFFICULTY
    key = eco.difficulty or DEFAULT_DIFFICULTY
    if key in DIFFICULTIES:
        return key
    return normalize_difficulty(key)


def configure_new_game(state: GameState, difficulty: str | None = None) -> None:
    eco = state.economy
    eco.difficulty = normalize_difficulty(difficulty)
    eco.pending_difficulty = ""
    eco.last_week_id = -1
    eco.values = _neutral_values()
    eco.prev_values = dict(eco.values)
    eco.visits = {}
    eco.demand = {}
    eco.cost = {}
    eco.freight = {}
    eco.history = []
    eco.events = []
    eco.deferred_events = []
    eco.event_cooldowns = {}
    eco.news = []
    eco.next_news_id = 1
    eco.catch_up = {}
    eco.daily_news_day = {}
    eco.live_ticks = 0
    if eco.difficulty != "off":
        from open_late.macro import ensure_macro

        eco.macro = {}
        ensure_macro(state)
    _bake_card(state, week_id(state.day))
    from open_late.economy_e4 import enrich_history, trim_history

    row = {"week_id": -1, "values": {k: int(v) for k, v in eco.values.items() if ":" not in k}}
    enrich_history(state, week_id(state.day), row, opening=True)
    eco.history.append(row)
    eco.history = trim_history(eco.history)


def set_economy_difficulty(state: GameState, difficulty: str) -> str:
    """Queue a difficulty change. It takes effect at the next Sunday tick."""
    difficulty = normalize_difficulty(difficulty)
    state.economy.pending_difficulty = difficulty
    label = DIFFICULTY_LABELS[difficulty]
    if is_sunday(state.day) and state.phase in ("morning", "desk"):
        return f"Economy difficulty will switch to {label} when Sunday closes."
    return f"Economy difficulty will switch to {label} this Sunday."


def _key(factor_id: int, city: str | None = None) -> str:
    scope = FACTORS.get(factor_id, {}).get("scope")
    if factor_id in CITY_WALK_IDS or (scope in ("city", "store") and city):
        return f"{factor_id}:{city or 'evansville'}"
    return str(factor_id)


def _neutral_values() -> dict[str, int]:
    values = {str(fid): 100 for fid in range(1, 121)}
    for fid in range(1, 121):
        if FACTORS[fid]["scope"] == "city" or fid in CITY_WALK_IDS:
            for city in CITIES:
                values[f"{fid}:{city}"] = 100
        low, high = FACTORS[fid]["range"]
        if low == 0 and fid != 61:
            values[str(fid)] = 0
            if FACTORS[fid]["scope"] == "city":
                for city in CITIES:
                    values[f"{fid}:{city}"] = 0
        if fid == 61:
            values["61"] = 50
    values["63:evansville"] = 100
    return values


def _starting_values() -> dict[str, int]:
    values = _neutral_values()
    # City priors from the plan for neighborhood income (14). Used once the
    # first live Sunday tick starts; week 1's card stays at 100.
    values["14:naperville"] = 112
    values["14:las_vegas"] = 98
    values["14:evansville"] = 96
    from open_late.economy_e3 import starting_priors

    return starting_priors(values)


def _ensure(state: GameState) -> None:
    eco = state.economy
    if not eco.values:
        eco.values = _neutral_values()
        eco.prev_values = dict(eco.values)
    if eco.difficulty not in DIFFICULTIES:
        eco.difficulty = DEFAULT_DIFFICULTY
    if eco.difficulty != "off" and not getattr(eco, "macro", None):
        # Save migration: an old live-economy save gets a fresh macro block.
        from open_late.macro import ensure_macro

        ensure_macro(state)


def _value(state: GameState, factor_id: int, city: str | None = None, *, previous: bool = False) -> int:
    source = state.economy.prev_values if previous else state.economy.values
    if not source:
        return 100
    key = _key(factor_id, city)
    if key in source:
        return int(source[key])
    return int(source.get(str(factor_id), 100))


def _linear_rng_seed(state: GameState, week: int, salt: int) -> int:
    """Historical linear seed. Salts that differ by a multiple of 9371 alias across weeks."""
    return (int(state.seed) * 1_000_003 + int(week) * 9_371 + int(salt) + 17) % (2**32)


def _linear_rng(state: GameState, week: int, salt: int) -> random.Random:
    return random.Random(_linear_rng_seed(state, week, salt))


def _stream_seed(state: GameState, stream: str, time_index: int, *keys: object) -> int:
    """Stable 64-bit seed from blake2b. Never use Python's built-in hash()."""
    parts = [f"{int(state.seed)}", str(stream), str(int(time_index))]
    for key in keys:
        parts.append("" if key is None else str(key))
    payload = "rr-econ-v1|" + "|".join(parts)
    digest = hashlib.blake2b(payload.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big")


def stream_rng(state: GameState, stream: str, time_index: int, *keys: object) -> random.Random:
    """Named, non-linear CRN stream for economy-on rolls (and for E9 named streams)."""
    return random.Random(_stream_seed(state, stream, time_index, *keys))


def _rng(state: GameState, week: int, salt: int) -> random.Random:
    """Walk and leftover salt streams. Linear when off so that path stays bit-identical."""
    if economy_difficulty(state) == "off":
        return _linear_rng(state, week, salt)
    return stream_rng(state, "walk", int(week), int(salt))


def _demand_salt(state: GameState, store_id: str, department: str) -> int:
    salt = 12_000
    try:
        salt += (DEPARTMENT_IDS.index(department) + 1) * 17
    except ValueError:
        salt += 40
    city = city_of(state, store_id) if store_id else ""
    salt += CITY_SALT.get(city or store_id or "", 0)
    return salt


def demand_rng(state: GameState, day: int, store_id: str, department: str) -> random.Random:
    """Dedicated CRN stream for hybrid aggregate demand.

    This stream is also used when difficulty is off (sigma is 0, but later
    allocation draws still come from it), so off keeps the historical linear
    seed. Economy-on uses a named blake2b stream so day N cannot alias a
    factor 80-84 event roll at week N.
    """
    if economy_difficulty(state) == "off":
        return _linear_rng(state, int(day), _demand_salt(state, store_id, department))
    return stream_rng(state, "demand", int(day), store_id or "", department or "")


def _clamp(value: float, low: int, high: int) -> int:
    return int(round(max(low, min(high, value))))


def _unit_shock(rng: random.Random, down_skew: float = 0.0) -> float:
    """One N(0,1) draw, optionally stretched on the downside. Same draw, scaled later."""
    z = rng.gauss(0.0, 1.0)
    if down_skew and z < 0:
        z = z * (1.0 + down_skew)
    return z


def _step_walk(
    current: int,
    theta: float,
    sigma: float,
    mu: float,
    low: int,
    high: int,
    rng: random.Random,
    sigma_mult: float,
    bias: float = 0.0,
    down_skew: float = 0.0,
) -> int:
    # Draw the unit shock first, then apply visible sigma, bias, and skew so
    # every difficulty shares the same random number and only the amplitude changes.
    z = _unit_shock(rng, down_skew)
    sigma = sigma * sigma_mult
    delta = theta * (mu + bias - current) + sigma * z
    cap = DELTA_RANGE_FRAC * (high - low)
    if delta > cap:
        delta = cap
    elif delta < -cap:
        delta = -cap
    return _clamp(current + delta, low, high)


def city_of(state: GameState, store_id: str) -> str:
    for door in getattr(state, "doors", []) or []:
        if door.id == store_id:
            ident = (door.id or "").replace(" ", "_").lower()
            if ident in CITY_SALT:
                return ident
    if store_id in CITY_SALT:
        return store_id
    from open_late.us_capitals import economy_proxy

    proxy = economy_proxy(store_id)
    if proxy in CITY_SALT:
        return proxy
    return "evansville"


def store_ids_for(state: GameState) -> list[str]:
    from open_late.hq import store_ids

    return list(store_ids(state))


def economy_tick(state: GameState) -> None:
    """Sunday hook. Mutates economy state, the next week's card, and news only."""
    _ensure(state)
    eco = state.economy
    changed = ""
    if eco.pending_difficulty:
        nxt = normalize_difficulty(eco.pending_difficulty)
        if nxt != eco.difficulty:
            changed = nxt
        eco.difficulty = nxt
        eco.pending_difficulty = ""
    week = week_id(state.day)
    if getattr(state, "rival_ai", None) is not None:
        # Rival AI: take last week's bounded town/supplier offsets back out so
        # the walks and links step on clean values.
        from open_late.rival_ai import pre_walk as rival_pre_walk

        rival_pre_walk(state)
    if eco.difficulty == "off":
        eco.prev_values = _neutral_values()
        eco.values = _neutral_values()
        eco.events = []
        eco.deferred_events = []
        eco.catch_up = {}
        eco.live_ticks = 0
        _bake_card(state, week)
        eco.last_week_id = week
        _record_history(state, week)
        return

    if not eco.values or int(getattr(eco, "live_ticks", 0) or 0) == 0:
        eco.values = _starting_values()
    eco.prev_values = dict(eco.values)
    sigma_mult = SIGMA_MULT[eco.difficulty]

    # Mandate port phase 1: the national macro layer steps first; driven
    # national factors are written in _resolve_links.
    from open_late.macro import macro_step

    macro_step(state, week)
    # Walks, cycles, events, links; then bake and emit the week's news.
    _step_all_walks(state, week, sigma_mult)
    _apply_cycles(state, week, state.day)
    _roll_events(state, week)
    _resolve_links(state, week, sigma_mult)
    if getattr(state, "rival_ai", None) is not None:
        # Rival AI: the three chains move on this week's factors, then their
        # local pressure lands on 80/81/84 before the card bakes.
        from open_late.rival_ai import sunday as rival_sunday

        rival_sunday(state, week)
    _bake_card(state, week)
    eco.last_week_id = week
    eco.live_ticks = int(getattr(eco, "live_ticks", 0) or 0) + 1
    _record_history(state, week)
    _sync_flag_values(state)
    from open_late.economy_e3 import apply_wage_floor_event

    apply_wage_floor_event(state)
    _emit_sunday_news(state, week, changed or None)


def _step_all_walks(state: GameState, week: int, sigma_mult: float) -> None:
    eco = state.economy
    national_rng = _rng(state, week, 0)
    year_week = week % 52
    for fid, params in WALKS.items():
        theta, sigma, mu, low, high = params
        if fid in CITY_WALK_IDS or fid in STORE_WALK_IDS:
            continue
        current = _value(state, fid, previous=True)
        if fid in MACRO_DRIVEN:
            # Macro-driven factors walk on their own mean-100 residual.
            from open_late.macro import walk_current

            current = walk_current(state, fid, current)
        eco.values[_key(fid)] = _step_walk(current, theta, sigma, mu, low, high, national_rng, sigma_mult)
    # Evansville warehouse congestion (63).
    if 63 in WALKS:
        theta, sigma, mu, low, high = WALKS[63]
        current = _value(state, 63, "evansville", previous=True)
        eco.values[_key(63, "evansville")] = _step_walk(
            current, theta, sigma, mu, low, high, _rng(state, week, 6), sigma_mult
        )
    for city in CITIES:
        rng = _rng(state, week, CITY_SALT[city])
        for fid in CITY_WALK_IDS:
            theta, sigma, mu, low, high = WALKS[fid]
            if fid == 37:
                mu = _heat_mu(year_week, city)
            elif fid == 38:
                mu = _cold_mu(year_week, city)
            current = _value(state, fid, city, previous=True)
            value = _step_walk(current, theta, sigma, mu, low, high, rng, sigma_mult)
            if fid == 38 and city == "houston":
                value = min(value, 120)
            if fid == 19 and city in ("seattle", "naperville"):
                mu = 108 if city == "seattle" else 110
                value = _step_walk(current, theta, sigma, mu, low, high, rng, sigma_mult)
            if fid in (51, 108) and city == "seattle":
                value = _step_walk(current, theta, sigma, 110, low, high, rng, sigma_mult)
            eco.values[_key(fid, city)] = value
    # Store-scoped E3 walks (home store plus each door).
    for store_id in store_ids_for(state):
        rng = _rng(state, week, 10 + CITY_SALT.get(store_id, 9))
        for fid in STORE_WALK_IDS:
            if fid == 63:
                continue
            if fid not in WALKS:
                continue
            theta, sigma, mu, low, high = WALKS[fid]
            current = _value(state, fid, store_id, previous=True)
            eco.values[_key(fid, store_id)] = _step_walk(current, theta, sigma, mu, low, high, rng, sigma_mult)


def _cycle_boost(week: int, peak_from: int, peak_to: int, amplitude: int, shoulder: int = 1) -> int:
    if peak_from <= week <= peak_to:
        return amplitude
    if shoulder and (week == peak_from - 1 or week == peak_to + 1):
        return amplitude // 2
    return 0


def _apply_cycles(state: GameState, week: int, day: int) -> None:
    eco = state.economy
    year_week = week % 52
    # Housing mood (9) also has a 52-week cycle, amplitude 6, peak week 18.
    if 9 in E1_IDS and economy_difficulty(state) != "off":
        base = _value(state, 9)
        cycle = int(round(6 * __import__("math").cos(2 * 3.1415926535 * (year_week - 18) / 52)))
        eco.values["9"] = _clamp(base + cycle, 70, 130)
    payday = 108 if is_payday(day) else 100
    eco.values["23"] = payday
    # Harvest Card: 108 in a reload week, 100 otherwise. Off stays at 100.
    if economy_difficulty(state) == "off":
        eco.values["24"] = 100
    else:
        eco.values["24"] = 108 if is_harvest_card_week(day) else 100
    school = _cycle_boost(year_week, 32, 35, 16)
    eco.values["25"] = 100 + school
    gift = _cycle_boost(year_week, 47, 51, 22)
    eco.values["26"] = 100 + gift
    from open_late.economy_e3 import apply_e3_cycles

    apply_e3_cycles(state, week, day)


def _resolve_links(state: GameState, week: int, sigma_mult: float) -> None:
    """Use previous week's linked outputs for backward edges."""
    eco = state.economy
    rng = _rng(state, week, 99)
    prev = lambda fid, city=None: _value(state, fid, city, previous=True)
    now = lambda fid, city=None: _value(state, fid, city, previous=False)

    from open_late.macro import apply_macro_factors

    # Mandate port phase 1: when on, 2, 3, 4, and 8 are macro anchor + residual
    # walk, and their national link equations below are skipped (the macro model
    # already links confidence, activity, inflation, and unemployment).
    macro_driven = apply_macro_factors(state)

    # 4 inflation gets a 0.4 pull toward the previous commodity mean.
    if not macro_driven:
        commodities = [prev(fid) for fid in COMMODITY]
        mean_c = sum(commodities) / len(commodities)
        walked = now(4)
        eco.values["4"] = _clamp(0.6 * walked + 0.4 * mean_c, 80, 140)

    # 7 tightness: already walked, blend 0.35 x previous diesel.
    eco.values["7"] = _clamp(0.65 * now(7) + 0.35 * prev(6), 70, 160)

    # 2 confidence: walked, plus previous policy (inverted) and previous income.
    if not macro_driven:
        policy_pull = 100 - (prev(1) - 100)
        income_pull = prev(5)
        eco.values["2"] = _clamp(0.40 * now(2) + 0.35 * policy_pull + 0.25 * income_pull, 60, 140)

        # 8 activity: walked + 0.3 x previous confidence.
        eco.values["8"] = _clamp(0.70 * now(8) + 0.30 * prev(2), 75, 125)

    # 5 is a pure link + residual.
    residual = 0.4 * sigma_mult * rng.gauss(0.0, 1.0)
    income = 0.5 * now(2) + 0.3 * (200 - now(4)) + 0.2 * (200 - now(3)) + residual
    # The weighted parts are around 100 when inputs are 100: 0.5*100+0.3*100+0.2*100=100.
    eco.values["5"] = _clamp(income, 70, 130)

    # Commodities: blend walked with inflation and import cost from the previous week.
    for fid in COMMODITY:
        walked = now(fid)
        blended = 0.70 * walked + 0.30 * prev(4)
        if COMMODITY[fid] in IMPORT_DEPTS:
            blended = 0.75 * blended + 0.25 * prev(10)
        if fid == 77:
            blended = 0.80 * blended + 0.20 * prev(9)
        if fid == 79:
            blended = 0.80 * blended + 0.20 * prev(7)
        low, high = WALKS[fid][3], WALKS[fid][4]
        eco.values[str(fid)] = _clamp(blended, low, high)

    for city in CITIES:
        # 12: 0.5 previous national unemployment + walked residual already in the walk.
        eco.values[_key(12, city)] = _clamp(0.50 * now(12, city) + 0.50 * prev(3), 70, 150)
        # 13: 0.4 inverted local unemployment. Factor 19 is not in E1 (treat as 100).
        eco.values[_key(13, city)] = _clamp(
            0.60 * now(13, city) + 0.40 * (200 - now(12, city)),
            80,
            150,
        )
        # 21: walked + 0.4 previous national confidence; residual capped vs national.
        raw = 0.60 * now(21, city) + 0.40 * prev(2)
        national = now(2)
        residual = raw - national
        cap = CITY_RESIDUAL_FRAC * abs(national - 100)
        if residual > cap:
            raw = national + cap
        elif residual < -cap:
            raw = national - cap
        eco.values[_key(21, city)] = _clamp(raw, 70, 130)

    # E2 supply links, always from previous week's linked outputs where the edge is backward.
    # 65 lag-1 diesel and tightness.
    eco.values["65"] = _clamp(0.70 * prev(6) + 0.30 * prev(7), 70, 170)
    # 58 already walked; blend previous tightness and diesel.
    eco.values["58"] = _clamp(0.40 * now(58) + 0.40 * prev(7) + 0.20 * prev(6), 70, 160)
    # 62 packaging: walked + previous inflation.
    eco.values["62"] = _clamp(0.75 * now(62) + 0.25 * prev(4), 80, 140)
    # 60 lead-time slip in days (0-6).
    residual = 0.4 * sigma_mult * rng.gauss(0.0, 1.0)
    slip = 0.50 * (now(57) - 100) / 10 + 0.30 * (now(58) - 100) / 10 + 0.20 * (prev(7) - 100) / 10 + residual
    eco.values["60"] = max(0, min(6, int(round(max(0.0, slip)))))
    # 61 snapshots average supplier relationship, plus a small walk residual.
    relationships = [int(getattr(account, "relationship", 50) or 50) for account in (state.supplier_accounts or [])]
    base = sum(relationships) / len(relationships) if relationships else 50
    eco.values["61"] = _clamp(base + 0.3 * sigma_mult * rng.gauss(0.0, 1.0), 0, 100)
    # Food commodities pick up lagged freight pass-through (cascade 1).
    for fid in (67, 68, 69, 70):
        low, high = WALKS[fid][3], WALKS[fid][4]
        eco.values[str(fid)] = _clamp(0.80 * now(fid) + 0.20 * prev(65), low, high)
    # Port delay: walked residual, plus the event pulse if one is active next week.
    if active_events(state, day=state.day + 1, factor_id=57) or active_events(state, factor_id=57):
        eco.values["57"] = _clamp(max(now(57), 130), 100, 160)
    if active_events(state, day=state.day + 1, factor_id=59) or active_events(state, factor_id=59):
        eco.values["59"] = _clamp(min(now(59), 80), 70, 130)
    if active_events(state, day=state.day + 1, factor_id=63) or active_events(state, factor_id=63):
        eco.values[_key(63, "evansville")] = _clamp(max(now(63, "evansville"), 130), 80, 150)
    from open_late.economy_e3 import apply_e3_links, sync_rival

    apply_e3_links(state, week, sigma_mult, rng)
    sync_rival(state, week, rng)


def _cap_mult(index: float, cap: float) -> float:
    lo, hi = 1.0 - cap, 1.0 + cap
    mult = index / 100.0
    if mult < lo:
        return lo
    if mult > hi:
        return hi
    return mult


def _bake_card(state: GameState, week: int) -> None:
    eco = state.economy
    cap = CAP_MULT[economy_difficulty(state)]
    sales_cap = SALES_CAP * cap
    cogs_cap = COGS_CAP * cap
    freight_cap = FREIGHT_CAP * cap
    visits: dict[str, int] = {}
    demand: dict[str, dict[str, int]] = {}
    cost: dict[str, dict[str, int]] = {}
    freight: dict[str, int] = {}
    off = economy_difficulty(state) == "off"
    for store_id in store_ids_for(state):
        city = city_of(state, store_id)
        if off:
            visits[store_id] = 100
            demand[store_id] = {dept: 100 for dept in DEPARTMENT_IDS}
            cost[store_id] = {dept: 100 for dept in DEPARTMENT_IDS}
            freight[store_id] = 100
            continue
        v = 100.0
        shoppers = getattr(state, "shopperlife", None)
        shopper_on = shoppers is not None and bool(shoppers.enabled)
        if getattr(state, "rival_ai", None) is not None or shopper_on:
            from open_late.living import player_visit_factor

            v *= player_visit_factor(state, store_id)
        v += (_value(state, 8) - 100) * 0.35
        v += (_value(state, 11, city) - 100) * 1.00
        v += (_value(state, 2) - 100) * 0.25
        v += (_value(state, 21, city) - 100) * 0.20
        v += (_value(state, 5) - 100) * 0.20
        dmap: dict[str, float] = {dept: 100.0 for dept in DEPARTMENT_IDS}
        conf = (_value(state, 2) - 100) * 0.30 + (_value(state, 5) - 100) * 0.25
        for dept in DEPARTMENT_IDS:
            dmap[dept] += conf
        income = _value(state, 14, city)
        shift = (income - 100) * 0.40
        mild = (income - 100) * 0.15
        for dept in HIGH_INCOME_DEPTS:
            dmap[dept] += shift
        for dept in LOW_INCOME_DEPTS:
            dmap[dept] -= mild
        school = _value(state, 25) - 100
        for dept in SCHOOL_DEPTS:
            dmap[dept] += school
        gift = _value(state, 26) - 100
        for dept in GIFT_DEPTS:
            dmap[dept] += gift
        # Cap visits x mean demand to the sales cap by scaling visits.
        avg = sum(dmap.values()) / len(dmap)
        product = (v / 100.0) * (avg / 100.0)
        if sales_cap > 0:
            lo, hi = 1.0 - sales_cap, 1.0 + sales_cap
            if product > hi and product:
                v *= hi / product
            elif product < lo and product:
                v *= lo / product
        visits[store_id] = _clamp(v, int(round((1 - sales_cap) * 100)), int(round((1 + sales_cap) * 100))) if sales_cap else 100
        demand[store_id] = {dept: _clamp(dmap[dept], 80, 130) for dept in DEPARTMENT_IDS}
        cmap: dict[str, int] = {}
        for dept in DEPARTMENT_IDS:
            raw = 0.70 * _value(state, DEPT_COMMODITY[dept]) + 0.15 * _value(state, 4)
            if dept in IMPORT_DEPTS:
                raw += 0.15 * _value(state, 10)
            else:
                raw += 0.15 * 100
            raw += (_value(state, 62) - 100) * 0.20
            if dept == "household":
                raw += (_value(state, 62) - 100) * 0.10
            if dept in ("grocery", "produce", "meat_dairy", "frozen"):
                raw += (_value(state, 65) - 100) * 0.25
            from open_late.economy_e3 import cost_fx_delta

            raw += cost_fx_delta(state, dept)
            if any(event.get("department") == dept for event in active_events(state, factor_id=66)):
                raw += 8
            if any(event.get("department") == dept for event in active_events(state, factor_id=64)):
                raw += 5
            raw = 100.0 + (raw - 100.0) * COST_VAR_DAMP
            cmap[dept] = int(round(_cap_mult(raw, cogs_cap) * 100)) if cogs_cap else 100
        cost[store_id] = cmap
        fr = 0.30 * _value(state, 6) + 0.20 * _value(state, 7) + 0.40 * _value(state, 65) + 0.10 * 100
        fr += (_value(state, 58) - 100) * 0.20
        if _value(state, 61) >= 0:
            fr -= (_value(state, 61) - 50) * 0.10
        basin = active_events(state, factor_id=44)
        if basin:
            fr += int(basin[0].get("intensity") or 30)
        if store_id == "evansville" or city == "evansville":
            fr += (_value(state, 63, "evansville") - 100) * 0.15
        freight[store_id] = int(round(_cap_mult(fr, freight_cap) * 100)) if freight_cap else 100
    eco.visits = visits
    eco.demand = demand
    eco.cost = cost
    eco.freight = freight


def _record_history(state: GameState, week: int) -> None:
    eco = state.economy
    row = {"week_id": week, "values": {k: int(v) for k, v in eco.values.items() if ":" not in k}}
    for city in CITIES:
        row[f"traffic:{city}"] = _value(state, 11, city)
    from open_late.economy_e4 import enrich_history, trim_history

    enrich_history(state, week, row, opening=False)
    eco.history.append(row)
    eco.history = trim_history(eco.history)


def _index(mapping: dict, store_id: str, dept: str | None = None) -> int:
    if dept is None:
        return int(mapping.get(store_id, 100) or 100)
    row = mapping.get(store_id) or {}
    return int(row.get(dept, 100) or 100)


def visits_mult(state: GameState, store_id: str) -> float:
    if economy_difficulty(state) == "off":
        return 1.0
    _ensure(state)
    from open_late.economy_e3 import apply_e3_visits

    base = (_index(state.economy.visits, store_id) / 100.0) * weather_visits_mult(state, store_id)
    base = apply_e3_visits(state, store_id, base)
    cut = weather_visits_mult(state, store_id) < 1.0
    city = city_of(state, store_id)
    if active_events(state, factor_id=16, city_id=city) or active_events(state, factor_id=17, city_id=city):
        cut = True
    cap = SALES_CAP * CAP_MULT[economy_difficulty(state)]
    if cap <= 0:
        return base
    base = apply_player_bias(base, helpful=True, difficulty=economy_difficulty(state))
    # Keep the stacked sales product inside the plan cap unless a visit-cutting
    # weather or road event is already pulling the door below the floor.
    demands = [demand_mult(state, store_id, dept) for dept in DEPARTMENT_IDS]
    avg = sum(demands) / len(demands) if demands else 1.0
    product = base * avg
    lo, hi = 1.0 - cap, 1.0 + cap
    if product > hi and product:
        base *= hi / product
    elif (not cut) and product < lo and product:
        base *= lo / product
    return base


def demand_mult(state: GameState, store_id: str, department: str) -> float:
    if economy_difficulty(state) == "off":
        return 1.0
    _ensure(state)
    base = _index(state.economy.demand, store_id, department) / 100.0
    from open_late.economy_e3 import _payday_day, apply_e3_demand

    if is_payday(_payday_day(state)) and department in PAYDAY_DEPTS:
        base *= 1.08
    if is_harvest_card_week(int(state.day)) and department in HARVEST_CARD_DEPTS:
        base *= HARVEST_CARD_LIFT
    base += weather_demand_delta(state, store_id, department)
    base = apply_e3_demand(state, store_id, department, base)
    return apply_player_bias(max(0.0, base), helpful=True, difficulty=economy_difficulty(state))


def cost_mult(state: GameState, store_id: str, department: str) -> float:
    if economy_difficulty(state) == "off":
        return 1.0
    _ensure(state)
    difficulty = economy_difficulty(state)
    cap = COGS_CAP * CAP_MULT[difficulty]
    return apply_player_bias(_index(state.economy.cost, store_id, department) / 100.0, helpful=False, difficulty=difficulty, cap=cap)


def freight_mult(state: GameState, store_id: str) -> float:
    if economy_difficulty(state) == "off":
        return 1.0
    _ensure(state)
    difficulty = economy_difficulty(state)
    cap = FREIGHT_CAP * CAP_MULT[difficulty]
    return apply_player_bias(_index(state.economy.freight, store_id) / 100.0, helpful=False, difficulty=difficulty, cap=cap)


def _visit_cut(state: GameState, store_id: str) -> bool:
    if weather_visits_mult(state, store_id) < 1.0:
        return True
    city = city_of(state, store_id)
    return bool(
        active_events(state, factor_id=16, city_id=city)
        or active_events(state, factor_id=17, city_id=city)
    )


def adjust_visits(state: GameState, store_id: str, visits: int) -> int:
    if visits <= 0 or economy_difficulty(state) == "off":
        return visits
    scaled = visits * visits_mult(state, store_id)
    from open_late.economy_e4 import apply_sales_grace

    # Difficulty sales grace is a realized-traffic bonus outside the factor
    # cap, so visits_mult (and the E1–E3 cap tests) stay on the card.
    scaled = apply_sales_grace(state, store_id, scaled, cut=_visit_cut(state, store_id))
    return max(0, int(round(scaled)))


def adjust_weight(state: GameState, store_id: str, department: str, weight: float) -> float:
    if economy_difficulty(state) == "off":
        return weight
    return weight * demand_mult(state, store_id, department)


def landed_cost(state: GameState, store_id: str, department: str, base: int) -> int:
    if base <= 0 or economy_difficulty(state) == "off":
        return base
    return max(0, int(round(base * cost_mult(state, store_id, department))))


def adjust_freight(state: GameState, store_id: str, freight: int) -> int:
    if freight <= 0 or economy_difficulty(state) == "off":
        return freight
    return max(0, int(round(freight * freight_mult(state, store_id))))


# --- Patch E2: weather, supply chain, events, daily overlay, news ---

SHRINK_CAP = 0.35
FOOD_DEPTS = ("grocery", "produce", "meat_dairy", "frozen")
THAW_DEPTS = ("frozen", "meat_dairy")
HEAT_DEMAND = ("frozen", "produce", "grocery")
COLD_DEMAND = ("grocery", "frozen", "seasonal", "pharmacy")
AIR_DEMAND = ("pharmacy", "health_beauty")


# Disaster rank (higher wins the one-per-city slot).
DISASTER_RANK = {41: 9, 40: 8, 44: 7, 45: 6, 39: 5, 43: 4, 37: 3, 38: 3, 42: 2}
DISASTER_IDS = frozenset(DISASTER_RANK)

# event_id -> (base_p or city->p, duration (lo,hi) in days, cooldown weeks, default severity)
EVENT_SPEC = {
    37: {"p": 0.05, "days": (7, 14), "cooldown": 8, "severity": 2, "city": True, "kind": "weather"},
    38: {"p": 0.05, "days": (7, 14), "cooldown": 8, "severity": 2, "city": True, "kind": "weather"},
    39: {"p": 0.08, "days": (1, 4), "cooldown": 3, "severity": 2, "city": True, "kind": "disaster"},
    40: {
        "p": {"evansville": 0.07, "seattle": 0.07, "naperville": 0.07, "houston": 0.01, "las_vegas": 0.01},
        "days": (1, 3),
        "cooldown": 4,
        "severity": 3,
        "city": True,
        "kind": "disaster",
    },
    41: {"p": 0.02, "days": (1, 2), "cooldown": 16, "severity": 4, "city": True, "kind": "disaster"},
    42: {"p": 0.02, "days": (28, 70), "cooldown": 26, "severity": 2, "city": True, "kind": "weather"},
    43: {
        "p": {"seattle": 0.06, "houston": 0.06, "evansville": 0.04, "las_vegas": 0.03, "naperville": 0.04},
        "days": (2, 7),
        "cooldown": 8,
        "severity": 2,
        "city": True,
        "kind": "disaster",
    },
    44: {"p": 0.015, "days": (14, 21), "cooldown": 26, "severity": 3, "city": False, "kind": "disaster"},
    45: {
        "p": {"evansville": 0.02, "seattle": 0.005, "houston": 0.005, "las_vegas": 0.005, "naperville": 0.005},
        "days": (1, 3),
        "cooldown": 20,
        "severity": 3,
        "city": True,
        "kind": "disaster",
    },
    57: {"p": 0.04, "days": (14, 35), "cooldown": 10, "severity": 3, "city": False, "kind": "supply"},
    59: {"p": 0.03, "days": (7, 7), "cooldown": 10, "severity": 2, "city": False, "kind": "supply"},
    63: {"p": 0.04, "days": (7, 14), "cooldown": 8, "severity": 2, "city": False, "kind": "supply", "store": "evansville"},
    64: {"p": 0.025, "days": (7, 21), "cooldown": 14, "severity": 3, "city": False, "kind": "supply"},
    66: {"p": 0.03 / 13, "days": (14, 28), "cooldown": 16, "severity": 2, "city": False, "kind": "supply", "per_dept": True},
}


EVENT_SPEC.update(EVENT_SPEC_E3)
DISASTER_RANK.update(E3_DISASTER_RANK)


def _heat_mu(year_week: int, city: str) -> float:
    import math

    base = 100 + 20 * math.cos(2 * math.pi * (year_week - 28) / 52)
    if city == "las_vegas":
        base += 8
    elif city == "houston":
        base += 5
    elif city == "seattle":
        base -= 5
    return base


def _cold_mu(year_week: int, city: str) -> float:
    import math

    amp = 6 if city == "houston" else 18
    if city == "las_vegas":
        amp = 8
    return 100 + amp * math.cos(2 * math.pi * (year_week - 2) / 52)


def event_p_mult(state: GameState) -> float:
    return EVENT_P_MULT.get(economy_difficulty(state), 0.0)


def difficulty_levers(difficulty: str, *, mode: str = "shop") -> dict[str, float | int]:
    """Visible difficulty levers for the desk and for x. Starting cash is included."""
    difficulty = normalize_difficulty(difficulty)
    from open_late.finance import starting_reserve
    from open_late.corporate import corporate_reserve

    reserve = corporate_reserve(difficulty) if mode == "corporate" else starting_reserve(mode, difficulty)
    return {
        "sigma_mult": SIGMA_MULT[difficulty],
        "event_p_mult": EVENT_P_MULT[difficulty],
        "cap_mult": CAP_MULT[difficulty],
        "event_duration_mult": EVENT_DURATION_MULT[difficulty],
        "walk_bias": WALK_BIAS[difficulty],
        "down_skew": DOWN_SKEW[difficulty],
        "starting_reserve": int(reserve),
    }


def apply_player_bias(mult: float, *, helpful: bool, difficulty: str | None = None, cap: float | None = None) -> float:
    """Shift a 1.00-centered multiplier with the visible walk-bias and downside-skew levers.

    helpful=True means a higher value is better for the shop (visits, demand).
    helpful=False means a higher value is worse (cost, freight, labor, rent, fees).
    When cap is set, the result is clamped to the same 1±cap band as the baked index,
    so documented stack caps still hold after the lever is applied.
    """
    if not difficulty or difficulty == "off":
        result = mult
    else:
        bias = float(WALK_BIAS.get(difficulty, 0.0) or 0.0)
        skew = float(DOWN_SKEW.get(difficulty, 0.0) or 0.0)
        if not bias and not skew:
            result = mult
        else:
            index = float(mult) * 100.0
            index = index + (bias if helpful else -bias)
            dev = index - 100.0
            if skew and ((helpful and dev < 0) or ((not helpful) and dev > 0)):
                dev *= 1.0 + skew
                index = 100.0 + dev
            result = index / 100.0
    if cap:
        lo, hi = 1.0 - cap, 1.0 + cap
        if result < lo:
            return lo
        if result > hi:
            return hi
    return result


def active_events(state: GameState, *, day: int | None = None, factor_id: int | None = None, city_id: str | None = None, store_id: str | None = None) -> list[dict]:
    day = int(state.day if day is None else day)
    rows = []
    for event in getattr(state.economy, "events", []) or []:
        if int(event.get("day_start", 0)) <= day <= int(event.get("day_end", 0)):
            if factor_id is not None and int(event.get("factor_id", 0)) != int(factor_id):
                continue
            if city_id is not None and (event.get("city_id") or "") not in ("", city_id):
                # National events (empty city) still count when we ask a city, if they say so
                if event.get("city_id"):
                    continue
            if store_id is not None and event.get("store_ids") and store_id not in event.get("store_ids"):
                if event.get("city_id") and event.get("city_id") != city_of(state, store_id):
                    continue
            rows.append(event)
    return rows


def _event_key(factor_id: int, city_id: str | None = None, department: str | None = None) -> str:
    if department:
        return f"{factor_id}:{department}"
    if city_id:
        return f"{factor_id}:{city_id}"
    return str(factor_id)


def force_event(
    state: GameState,
    factor_id: int,
    *,
    city_id: str | None = None,
    store_id: str | None = None,
    days: int = 2,
    severity: int | None = None,
    intensity: int | None = None,
    department: str | None = None,
    start_day: int | None = None,
    set_cooldown: bool = True,
) -> dict:
    """Test and tick helper. Starts an event on the economy stream, not the sale RNG."""
    _ensure(state)
    spec = EVENT_SPEC.get(int(factor_id), {})
    start = int(state.day if start_day is None else start_day)
    days = max(1, int(days))
    end = start + days - 1
    city_id = city_id or (None if not spec.get("city") else "evansville")
    store_ids = []
    if store_id:
        store_ids = [store_id]
    elif city_id:
        owned = store_ids_for(state)
        if city_id in owned:
            store_ids = [city_id]
        elif not state.doors:
            store_ids = [city_id] if city_id == "evansville" else []
    if int(factor_id) == 63:
        store_ids = ["evansville"]
    event = {
        "id": f"ev{len(state.economy.events) + len(state.economy.deferred_events) + 1}",
        "factor_id": int(factor_id),
        "city_id": city_id or "",
        "store_ids": store_ids,
        "day_start": start,
        "day_end": end,
        "severity": int(severity if severity is not None else spec.get("severity", 1)),
        "intensity": int(intensity if intensity is not None else _default_intensity(int(factor_id))),
        "department": department or "",
        "kind": spec.get("kind", "weather"),
    }
    state.economy.events.append(event)
    _sync_flag_values(state)
    if set_cooldown:
        cool = int(spec.get("cooldown", 0) or 0)
        expire = week_id(state.day) + cool
        state.economy.event_cooldowns[_event_key(int(factor_id), city_id, department)] = expire
    return event


def _default_intensity(factor_id: int) -> int:
    if factor_id == 40:
        return 30
    if factor_id == 39:
        return 12
    if factor_id == 41:
        return 60
    if factor_id == 45:
        return 15
    if factor_id == 43:
        return 10
    if factor_id == 44:
        return 30
    if factor_id == 46:
        return 25
    if factor_id == 57:
        return 20
    if factor_id == 84:
        return 12
    if factor_id == 107:
        return 4
    if factor_id == 119:
        return 20
    if factor_id == 83:
        return 12
    if factor_id == 49:
        return 10
    if factor_id == 36:
        return 1
    return 10


def cooldown_clear(state: GameState, factor_id: int, city_id: str | None = None, department: str | None = None, week: int | None = None) -> bool:
    week = week_id(state.day) if week is None else int(week)
    key = _event_key(factor_id, city_id, department)
    until = int((state.economy.event_cooldowns or {}).get(key, -1))
    return week >= until


def _event_salt(factor_id: int, city_id: str | None = None, department: str | None = None) -> int:
    salt = 8_000 + int(factor_id) * 50
    if city_id:
        salt += CITY_SALT.get(city_id, 0)
    if department:
        try:
            salt += (DEPARTMENT_IDS.index(department) + 1) * 7
        except ValueError:
            salt += 40
    return salt


def _event_rng(state: GameState, week: int, factor_id: int, city_id: str | None = None, department: str | None = None) -> random.Random:
    """A stream per potential event so one fire cannot desync another tier.

    Events only roll when the economy is on. Off keeps the linear formula if
    this helper is called anyway. Economy-on uses a named blake2b stream so
    week N cannot alias demand_rng at day N (factors 80-84 used to overlap
    demand salts 12,000-12,226).
    """
    if economy_difficulty(state) == "off":
        return _linear_rng(state, week, _event_salt(factor_id, city_id, department))
    return stream_rng(state, "event", int(week), int(factor_id), city_id or "", department or "")


def _event_payload(state: GameState, week: int, factor_id: int, *, city_id: str | None = None, department: str | None = None, duration_mult: float = 1.0) -> tuple:
    """Always draw U, duration, and intensity from a dedicated rng, then the caller decides whether to fire."""
    rng = _event_rng(state, week, factor_id, city_id, department)
    u = rng.random()
    spec = EVENT_SPEC[factor_id]
    days = _roll_days(rng, spec["days"], duration_mult)
    sev = spec["severity"]
    if factor_id == 41:
        sev = rng.randint(1, 3)
    intensity = None
    dept = department
    if factor_id == 64:
        dept = rng.choice(["electronics", "toys", "pharmacy"])
    if factor_id == 36:
        intensity = rng.randint(1, 2)
    if factor_id == 87:
        dept = "produce" if city_id == "naperville" else rng.choice(["produce", "pharmacy"])
    if factor_id == 119:
        dept = rng.choice([item for item in DEPARTMENT_IDS if item != "pharmacy"])
        intensity = rng.randint(15, 40)
    if factor_id == 107:
        intensity = rng.randint(0, 8)
    if factor_id == 84:
        intensity = rng.randint(8, 30)
    if factor_id == 109:
        dept = rng.choice(["pharmacy", "grocery", "produce"])
    drafted = _default_intensity(factor_id)
    if factor_id == 40:
        drafted = rng.randint(20, 40)
    elif factor_id == 39:
        drafted = rng.randint(8, 15)
    elif factor_id == 41:
        drafted = rng.randint(50, 70)
    elif factor_id == 44:
        drafted = rng.randint(20, 40)
    elif factor_id == 45:
        drafted = rng.randint(10, 20)
    elif factor_id == 43:
        drafted = rng.randint(8, 14)
    if intensity is None:
        intensity = drafted
    return u, days, sev, intensity, dept


def _roll_events(state: GameState, week: int) -> None:
    """Sunday roll. Common random numbers: one draw per event slot, then visible p and duration."""
    eco = state.economy
    p_mult = event_p_mult(state)
    if p_mult <= 0:
        return
    duration_mult = float(EVENT_DURATION_MULT.get(economy_difficulty(state), 1.0) or 1.0)
    candidates: list[dict] = []
    for pending in list(eco.deferred_events):
        fid = int(pending.get("factor_id", 0))
        city = pending.get("city_id") or None
        dept = pending.get("department") or None
        if cooldown_clear(state, fid, city, dept, week):
            candidates.append(pending)
    eco.deferred_events = [item for item in eco.deferred_events if item not in candidates]

    def _p(spec, city=None):
        raw = spec["p"]
        if isinstance(raw, dict):
            return float(raw.get(city or "evansville", 0.0)) * p_mult
        return float(raw) * p_mult

    def _accept(fid, *, city=None, department=None, extra_ok=True) -> dict | None:
        spec = EVENT_SPEC[fid]
        u, days, sev, intensity, dept = _event_payload(
            state, week, fid, city_id=city, department=department, duration_mult=duration_mult
        )
        if not extra_ok:
            return None
        if not cooldown_clear(state, fid, city, dept, week):
            return None
        if spec.get("fixed_week") is not None and (week % 52) != int(spec["fixed_week"]):
            return None
        if fid == 36 and not is_harvest_card_week(state.day + 1):
            return None
        if fid == 84:
            from open_late.economy_e3 import should_roll_war

            if city and not should_roll_war(state, city):
                return None
        if u >= _p(spec, city):
            return None
        event = _draft_event(state, fid, days=days, city_id=city, department=dept, severity=sev, rng=None, intensity=intensity)
        return event

    for fid in (44, 57, 59, 63, 64, 66, 31, 32, 36, 97, 98, 111, 115, 118):
        if fid == 66:
            for dept in DEPARTMENT_IDS:
                event = _accept(fid, department=dept)
                if event:
                    candidates.append(event)
            continue
        event = _accept(fid)
        if event:
            candidates.append(event)

    for city in CITIES:
        for fid in (37, 38, 39, 40, 41, 42, 43, 45, 15, 16, 17, 18, 49, 53, 83, 84, 87, 88, 107, 108, 109, 110, 119):
            if fid not in EVENT_SPEC:
                continue
            event = _accept(fid, city=city)
            if event:
                candidates.append(event)

    accepted, deferred = _resolve_one_disaster(state, candidates, week)
    start = state.day + 1  # events bake on Sunday for the coming week
    for event in accepted:
        if event.get("day_start") is None or event.get("from_defer"):
            span = int(event["day_end"]) - int(event["day_start"]) if event.get("day_start") is not None else None
            event["day_start"] = start
            if span is not None and span >= 0:
                event["day_end"] = start + span
            else:
                event["day_end"] = start + max(0, int(event.get("days", 1)) - 1)
        event.pop("from_defer", None)
        event.pop("days", None)
        eco.events.append(event)
        spec = EVENT_SPEC.get(int(event["factor_id"]), {})
        cool = int(spec.get("cooldown", 0) or 0)
        eco.event_cooldowns[_event_key(int(event["factor_id"]), event.get("city_id") or None, event.get("department") or None)] = week + cool
    eco.deferred_events.extend(deferred)
    _sync_flag_values(state)


def _roll_days(rng: random.Random, span: tuple[int, int], duration_mult: float) -> int:
    lo, hi = span
    days = rng.randint(int(lo), int(hi))
    if duration_mult > 1:
        days = max(days, int(round(days * duration_mult)))
    return max(1, days)


def _draft_event(state: GameState, factor_id: int, *, days: int, city_id: str | None = None, department: str | None = None, severity: int | None = None, rng: random.Random | None = None, intensity: int | None = None) -> dict:
    spec = EVENT_SPEC[factor_id]
    if intensity is None:
        intensity = _default_intensity(factor_id)
        if rng is not None:
            if factor_id == 40:
                intensity = rng.randint(20, 40)
            elif factor_id == 39:
                intensity = rng.randint(8, 15)
            elif factor_id == 41:
                intensity = rng.randint(50, 70)
            elif factor_id == 44:
                intensity = rng.randint(20, 40)
            elif factor_id == 45:
                intensity = rng.randint(10, 20)
            elif factor_id == 43:
                intensity = rng.randint(8, 14)
    start = state.day + 1
    store_ids = []
    if city_id and city_id in store_ids_for(state):
        store_ids = [city_id]
    elif factor_id == 63:
        store_ids = ["evansville"]
    return {
        "id": f"ev{len(state.economy.events) + len(state.economy.deferred_events) + 1}",
        "factor_id": int(factor_id),
        "city_id": city_id or "",
        "store_ids": store_ids,
        "day_start": start,
        "day_end": start + days - 1,
        "severity": int(severity if severity is not None else spec.get("severity", 1)),
        "intensity": int(intensity),
        "department": department or "",
        "kind": spec.get("kind", "weather"),
        "days": days,
    }


def _resolve_one_disaster(state: GameState, candidates: list[dict], week: int) -> tuple[list[dict], list[dict]]:
    """Two disasters do not land on the same city in the same week; keep the more severe."""
    accepted: list[dict] = []
    deferred: list[dict] = []
    by_city: dict[str, list[dict]] = {}
    others: list[dict] = []
    for event in candidates:
        fid = int(event["factor_id"])
        city = event.get("city_id") or ""
        if fid in DISASTER_IDS and (city or fid == 44):
            # 44 is national; it also contends for Houston's local slot.
            key = city or ("houston" if fid == 44 else "_national")
            by_city.setdefault(key, []).append(event)
            if fid == 44:
                others.append(event)  # national freight still considered with the Houston slot
        else:
            others.append(event)
    # National 44 is in both; handle cities first, drop 44 from others if it loses Houston? National 44 can still fire without Houston visit hit.
    taken_ids = set()
    for city, group in by_city.items():
        disasters = [event for event in group if int(event["factor_id"]) in DISASTER_IDS]
        if not disasters:
            continue
        disasters.sort(key=lambda event: (DISASTER_RANK.get(int(event["factor_id"]), 0), int(event.get("severity", 0))), reverse=True)
        winner = disasters[0]
        accepted.append(winner)
        taken_ids.add(id(winner))
        for event in disasters[1:]:
            event["from_defer"] = True
            deferred.append(event)
            taken_ids.add(id(event))
    for event in others:
        if id(event) in taken_ids:
            continue
        accepted.append(event)
    return accepted, deferred


def _sync_flag_values(state: GameState) -> None:
    eco = state.economy
    for fid in (17, 31, 32, 36, 39, 40, 41, 43, 44, 45, 64, 66, 83, 84, 87, 107, 109, 110, 111, 119):
        info = FACTORS[fid]
        if info["scope"] == "city":
            for city in CITIES:
                eco.values[_key(fid, city)] = 1 if active_events(state, factor_id=fid, city_id=city) else 0
        else:
            eco.values[str(fid)] = 1 if active_events(state, factor_id=fid) else 0
    # 46 is a percent 0-40 when a thaw is staged or firing.
    thaw = active_events(state, factor_id=46)
    eco.values["46"] = max((int(event.get("intensity") or 0) for event in thaw), default=0)
    lag = active_events(state, factor_id=36)
    eco.values["36"] = max((int(event.get("intensity") or 0) for event in lag), default=0)
    for city in CITIES:
        war = active_events(state, factor_id=84, city_id=city)
        eco.values[_key(84, city)] = max((int(event.get("intensity") or 0) for event in war), default=0)
        floor = active_events(state, factor_id=107, city_id=city)
        eco.values[_key(107, city)] = max((int(event.get("intensity") or 0) for event in floor), default=0)
        fad = active_events(state, factor_id=119, city_id=city)
        eco.values[_key(119, city)] = 100 + max((int(event.get("intensity") or 0) for event in fad), default=0)


def weather_label(state: GameState, city_id: str, day: int | None = None) -> str:
    if economy_difficulty(state) == "off":
        return "fair"
    day = int(state.day if day is None else day)
    if active_events(state, day=day, factor_id=41, city_id=city_id):
        return "storm"
    if active_events(state, day=day, factor_id=40, city_id=city_id):
        return "ice"
    if active_events(state, day=day, factor_id=39, city_id=city_id):
        return "rain"
    if active_events(state, day=day, factor_id=45, city_id=city_id):
        return "wind"
    if active_events(state, day=day, factor_id=43, city_id=city_id):
        return "haze"
    if active_events(state, day=day, factor_id=44) and city_id == "houston":
        return "storm"
    heat = _value(state, 37, city_id)
    cold = _value(state, 38, city_id)
    drought = _value(state, 42, city_id)
    if active_events(state, day=day, factor_id=37, city_id=city_id) or heat >= 125:
        return "heat"
    if active_events(state, day=day, factor_id=38, city_id=city_id) or cold >= 125:
        return "cold"
    if active_events(state, day=day, factor_id=42, city_id=city_id) or drought >= 130:
        return "drought"
    return "fair"


def event_rows(state: GameState) -> list[dict]:
    rows = []
    for event in active_events(state):
        fid = int(event["factor_id"])
        info = FACTORS.get(fid, {})
        rows.append(
            {
                "id": event.get("id") or "",
                "factor_id": fid,
                "name": info.get("name", str(fid)),
                "city_id": event.get("city_id") or None,
                "store_ids": list(event.get("store_ids") or []),
                "day_start": int(event.get("day_start") or 0),
                "day_end": int(event.get("day_end") or 0),
                "severity": int(event.get("severity") or 0),
                "department": event.get("department") or None,
            }
        )
    return rows


def weather_visits_mult(state: GameState, store_id: str) -> float:
    if economy_difficulty(state) == "off":
        return 1.0
    city = city_of(state, store_id)
    cut = 0.0
    ice = active_events(state, factor_id=40, city_id=city)
    if ice:
        cut = max(cut, int(ice[0].get("intensity") or 30) / 100.0)
    rain = active_events(state, factor_id=39, city_id=city)
    if rain:
        cut = max(cut, int(rain[0].get("intensity") or 12) / 100.0)
    storm = active_events(state, factor_id=41, city_id=city)
    if storm:
        cut = max(cut, int(storm[0].get("intensity") or 60) / 100.0)
    wind = active_events(state, factor_id=45, city_id=city)
    if wind:
        cut = max(cut, int(wind[0].get("intensity") or 15) / 100.0)
    air = active_events(state, factor_id=43, city_id=city)
    if air:
        cut = max(cut, int(air[0].get("intensity") or 10) / 100.0)
    if city == "houston" and active_events(state, factor_id=44):
        cut = max(cut, 0.12)
    if cut:
        return max(0.0, 1.0 - cut)
    catch = (state.economy.catch_up or {}).get(city) or {}
    if int(catch.get("days") or 0) > 0:
        return 1.0 + float(catch.get("boost") or 0.15)
    return 1.0


def weather_demand_delta(state: GameState, store_id: str, department: str) -> float:
    """Additive multiplier delta (0.0 = no change)."""
    if economy_difficulty(state) == "off":
        return 0.0
    city = city_of(state, store_id)
    delta = 0.0
    heat = _value(state, 37, city)
    if heat >= 115 or active_events(state, factor_id=37, city_id=city):
        bump = 0.08 if heat >= 130 or active_events(state, factor_id=37, city_id=city) else 0.04
        if department in HEAT_DEMAND:
            delta += bump
    cold = _value(state, 38, city)
    if cold >= 115 or active_events(state, factor_id=38, city_id=city):
        bump = 0.08 if cold >= 130 or active_events(state, factor_id=38, city_id=city) else 0.04
        if department in COLD_DEMAND:
            delta += bump
    if active_events(state, factor_id=43, city_id=city) and department in AIR_DEMAND:
        delta += 0.08
    if (active_events(state, factor_id=39, city_id=city) or _value(state, 42, city) >= 125) and department == "home_garden":
        delta -= 0.08
    hold = active_events(state, factor_id=64)
    if hold and (hold[0].get("department") or "") == department:
        delta -= 0.20
    short = [event for event in active_events(state, factor_id=66) if event.get("department") == department]
    if short:
        delta -= 0.15
    return delta


def lead_slip_days(state: GameState, department: str | None = None) -> int:
    if economy_difficulty(state) == "off":
        return 0
    _ensure(state)
    days = int(_value(state, 60) or 0)
    # Allow index-style 100-160 as well as raw 0-6.
    if days >= 70:
        days = max(0, min(6, int(round((days - 100) / 10))))
    days = max(0, min(6, days))
    if department in IMPORT_DEPTS and (_value(state, 57) >= 115 or active_events(state, factor_id=57)):
        days = min(6, days + 1)
    if _value(state, 63, "evansville") >= 125 or active_events(state, factor_id=63):
        days = min(6, days + 1)
    if active_events(state, factor_id=44) or active_events(state, factor_id=58) and _value(state, 58) >= 130:
        days = min(6, max(days, 1))
    return days


def spoilage_rate(state: GameState, store_id: str, department: str) -> float:
    """Daily fraction of perishable units written off, 0 when off / quiet."""
    if economy_difficulty(state) == "off":
        return 0.0
    city = city_of(state, store_id)
    rate = 0.0
    heat = _value(state, 37, city)
    if department in ("meat_dairy", "produce") and (heat >= 120 or active_events(state, factor_id=37, city_id=city)):
        rate += 0.03 if heat >= 135 or active_events(state, factor_id=37, city_id=city) else 0.015
    if department == "produce" and active_events(state, factor_id=39, city_id=city):
        rate += 0.02
    cold_chain = _value(state, 59)
    if department in THAW_DEPTS + ("produce",) and (cold_chain <= 90 or active_events(state, factor_id=59)):
        rate += 0.03 if cold_chain <= 80 or active_events(state, factor_id=59) else 0.015
    if store_id == "evansville" and department in FOOD_DEPTS and (_value(state, 63, "evansville") >= 125 or active_events(state, factor_id=63)):
        rate += 0.02
    if department == "produce" and _value(state, 42, city) >= 130:
        rate += 0.01
    cap = SHRINK_CAP * CAP_MULT[economy_difficulty(state)]
    if cap <= 0:
        return 0.0
    return min(rate, cap)


def apply_daily_spoil(state: GameState, stock: dict, products: dict, store_id: str, report) -> int:
    """Economy spoilage and case thaw. Identity when off. Returns shrink dollars."""
    if economy_difficulty(state) == "off":
        return 0
    _ensure(state)
    _prepare_day(state)
    cost = _write_spoilage(state, stock, products, store_id, report)
    cost += apply_case_thaw(state, stock, products, store_id, report)
    return cost


def _write_spoilage(state: GameState, stock: dict, products: dict, store_id: str, report) -> int:
    from open_late.engine import _take_stock
    from open_late.text import money

    units = 0
    cost = 0
    for product_id, line in list(stock.items()):
        product = products.get(product_id)
        if product is None or int(getattr(product, "shelf_life_days", 0) or 0) <= 0:
            continue
        if line.on_hand <= 0:
            continue
        dept = getattr(product, "department", "") or ""
        rate = spoilage_rate(state, store_id, dept)
        if rate <= 0:
            continue
        take = int(line.on_hand * rate)
        if take <= 0 and rate >= 0.02 and line.on_hand >= 8:
            take = 1
        if take <= 0:
            continue
        taken = _take_stock(line, product, take)
        if taken <= 0:
            continue
        units += taken
        cost += product.cost * taken
    if units:
        report.spoilage_units += units
        report.spoilage_cost += cost
        report.shrink_units += units
        report.shrink_cost += cost
        report.cogs += cost
        report.notes.append(f"Weather and supply spoilage wrote off {units} units ({money(cost)}).")
    return cost


def apply_case_thaw(state: GameState, stock: dict, products: dict, store_id: str, report) -> int:
    """Write frozen and meat_dairy into shrink the same way expiry does."""
    if economy_difficulty(state) == "off":
        return 0
    city = city_of(state, store_id)
    storms = [event for event in active_events(state, factor_id=41, city_id=city) if int(event.get("severity") or 0) >= 2]
    existing = active_events(state, factor_id=46, store_id=store_id)
    if not storms and not existing:
        return 0
    on_hand = 0
    for product_id, line in stock.items():
        product = products.get(product_id)
        if product is None or getattr(product, "department", "") not in THAW_DEPTS:
            continue
        on_hand += int(line.on_hand or 0)
    if on_hand <= 0:
        return 0
    if not existing:
        intensity = 25
        if storms:
            intensity = min(40, 15 + 8 * int(storms[0].get("severity") or 2))
        force_event(state, 46, city_id=city, store_id=store_id, days=1, severity=4, intensity=intensity, start_day=state.day)
        existing = active_events(state, factor_id=46, store_id=store_id)
    event = existing[0]
    pct = max(0, min(40, int(event.get("intensity") or 25))) / 100.0
    from open_late.engine import _take_stock
    from open_late.text import money

    units = 0
    cost = 0
    for product_id, line in list(stock.items()):
        product = products.get(product_id)
        if product is None or getattr(product, "department", "") not in THAW_DEPTS:
            continue
        if line.on_hand <= 0:
            continue
        take = max(1, int(round(line.on_hand * pct))) if line.on_hand * pct >= 0.5 else (1 if pct >= 0.1 and line.on_hand else 0)
        take = min(take, line.on_hand)
        if take <= 0:
            continue
        taken = _take_stock(line, product, take)
        if taken <= 0:
            continue
        units += taken
        cost += product.cost * taken
    if units:
        report.spoilage_units += units
        report.spoilage_cost += cost
        report.shrink_units += units
        report.shrink_cost += cost
        report.cogs += cost
        label = store_id.replace("_", " ").title()
        report.notes.append(f"Case thaw at {label}: frozen and dairy written into shrink after the outage ({units} units, {money(cost)}).")
        _emit_thaw_news(state, store_id, city, event)
    return cost


def _prepare_day(state: GameState) -> None:
    eco = state.economy
    day = int(state.day)
    # Start a two-day catch-up the morning after ice ends.
    for event in list(eco.events):
        if int(event.get("factor_id") or 0) != 40:
            continue
        city = event.get("city_id") or ""
        if not city:
            continue
        if day == int(event.get("day_end") or 0) + 1:
            boost = 0.5 * (int(event.get("intensity") or 30) / 100.0)
            eco.catch_up[city] = {"days": 2, "boost": max(0.10, min(0.20, boost))}
    # Drop expired events from the live list (history stays on the news rail).
    eco.events = [event for event in eco.events if day <= int(event.get("day_end") or 0)]
    _sync_flag_values(state)


def economy_end_day(state: GameState) -> None:
    if economy_difficulty(state) == "off":
        return
    eco = state.economy
    for city, row in list(eco.catch_up.items()):
        if active_events(state, factor_id=40, city_id=city):
            continue
        days = int(row.get("days") or 0) - 1
        if days <= 0:
            eco.catch_up.pop(city, None)
        else:
            row["days"] = days


def _emit_thaw_news(state: GameState, store_id: str, city: str, event: dict) -> None:
    from open_late.economy_news import append_daily_bulletin, headline_for

    headline, body = headline_for(46, city_id=city, department=None, direction="", extra={"store_name": store_id.replace("_", " ").title()})
    append_daily_bulletin(
        state,
        factor_ids=[46, 41],
        headline=headline,
        body=body,
        store_id=store_id,
        city_id=city,
        severity=4,
    )


def economy_daily_news(state: GameState) -> None:
    """Intra-week weather / outage bulletin, at most one per store per day."""
    if economy_difficulty(state) == "off":
        return
    from open_late.economy_news import append_daily_bulletin, headline_for

    for store_id in store_ids_for(state):
        city = city_of(state, store_id)
        for fid in (40, 41, 39, 45, 43, 44):
            rows = active_events(state, factor_id=fid, city_id=city)
            if fid == 44 and city != "houston":
                continue
            if not rows:
                continue
            event = rows[0]
            if int(event.get("day_start") or 0) != int(state.day):
                continue
            headline, body = headline_for(fid, city_id=city, department=event.get("department"), direction="up")
            append_daily_bulletin(
                state,
                factor_ids=[fid],
                headline=headline,
                body=body,
                store_id=store_id,
                city_id=city,
                severity=int(event.get("severity") or 2),
            )
            break


def _emit_sunday_news(state: GameState, week: int, difficulty_changed: str | None) -> None:
    if economy_difficulty(state) == "off":
        return
    from open_late.economy_news import (
        append_news,
        difficulty_story,
        headline_for,
    )

    if difficulty_changed:
        outlet, headline, body = difficulty_story(DIFFICULTY_LABELS.get(difficulty_changed, difficulty_changed))
        append_news(
            state,
            factor_ids=[],
            headline=headline,
            body=body,
            outlet=outlet,
            severity=2,
            prompt="Calm, Standard, and Stern only scale swings and event odds, not long-run means.",
            week=week,
        )
    # Calendar: Harvest Card week ahead (next seven days).
    if is_harvest_card_week(state.day + 1) or is_harvest_card_week(state.day + 7):
        headline, body = headline_for(24, city_id=None, department=None, direction="")
        append_news(state, factor_ids=[24], headline=headline, body=body, severity=2, week=week)
    # Factor moves of at least 6 index points, plus cap hits, plus new events.
    for fid in list(E1_NATIONAL) + list(E2_SUPPLY) + [65]:
        if fid in (23, 24, 25, 26):
            continue
        if FACTORS.get(fid, {}).get("range", [100, 100])[0] == 0 and fid not in (57, 58, 59, 62, 65, 60):
            continue
        now = _value(state, fid)
        prev = _value(state, fid, previous=True)
        if abs(now - prev) >= 6:
            direction = "up" if now > prev else "down"
            headline, body = headline_for(
                fid,
                city_id=None,
                department=None,
                direction=direction,
                extra={"factor_name": FACTORS[fid]["name"], "delta": now - prev},
            )
            append_news(state, factor_ids=[fid], headline=headline, body=body, severity=2 if abs(now - prev) < 12 else 3, week=week)
    # City traffic / weather walks.
    for city in store_ids_for(state):
        loc = city_of(state, city)
        for fid in (11, 37, 38, 42):
            now = _value(state, fid, loc)
            prev = _value(state, fid, loc, previous=True)
            if abs(now - prev) >= 6:
                direction = "up" if now > prev else "down"
                headline, body = headline_for(
                    fid,
                    city_id=loc,
                    department=None,
                    direction=direction,
                    extra={"factor_name": FACTORS[fid]["name"], "delta": now - prev},
                )
                append_news(state, factor_ids=[fid], headline=headline, body=body, city_id=loc, store_ids=[city], severity=2, week=week)
    # Events that start this coming week.
    start = state.day + 1
    end = start + 6
    for event in state.economy.events:
        if not (start <= int(event.get("day_start") or 0) <= end):
            continue
        fid = int(event["factor_id"])
        city = event.get("city_id") or None
        headline, body = headline_for(fid, city_id=city, department=event.get("department"), direction="up")
        stores = list(event.get("store_ids") or [])
        append_news(
            state,
            factor_ids=[fid],
            headline=headline,
            body=body,
            city_id=city,
            store_ids=stores,
            severity=int(event.get("severity") or 2),
            department=event.get("department") or None,
            week=week,
        )



def factor_label(state: GameState, factor_id: int, city_id: str | None = None) -> str | None:
    """Short display string. Index factors show the formatted value; state factors name the state."""
    fid = int(factor_id)
    info = FACTORS.get(fid) or {}
    value = int(_value(state, fid, city_id))
    if info.get("kind") != "state":
        return str(value)
    ev = None
    events = active_events(state, factor_id=fid, city_id=city_id if info.get("scope") == "city" else None)
    if events:
        ev = events[0]
    dept = ""
    if ev is not None:
        dept = str(ev.get("department") or "")
    dept_label = DEPARTMENT_LABELS.get(dept, dept.replace("_", " ").title()) if dept else ""

    if fid == 36:
        if value <= 0:
            return "On time"
        return f"Lag {value} day" if value == 1 else f"Lag {value} days"
    if fid == 46:
        return "None" if value <= 0 else f"Thaw {value}%"
    if fid == 49:
        return "None" if value <= 0 else f"{value} no-shows"
    if fid == 60:
        return "On time" if value <= 0 else (f"{value} day" if value == 1 else f"{value} days")
    if fid == 61:
        if value <= 39:
            return "Strained"
        if value <= 59:
            return "Steady"
        return "Warm"
    if fid == 81:
        if value <= 0:
            return "Quiet"
        if value < 28:
            return f"Heat {value}"
        return f"Hot {value}"
    if fid == 82:
        focus = str(getattr(getattr(state, "rival", None), "focus", "") or "")
        if not focus:
            return "No focus"
        return f"Focus: {DEPARTMENT_LABELS.get(focus, focus.replace('_', ' ').title())}"
    if fid == 83:
        return "None" if value <= 0 else "New banner"
    if fid == 84:
        return "None" if value <= 0 else f"Intensity {value}"
    if fid == 87:
        return "None" if value <= 0 else (f"Specialist: {dept_label}" if dept_label else "Specialist in town")
    if fid == 107:
        return "Unchanged" if value <= 0 else f"+{value}%"
    if fid in (64, 66, 109) and value > 0 and dept_label:
        held = {64: "On hold", 66: "Allocated", 109: "Inspection"}[fid]
        return f"{held}: {dept_label}"
    flags = {
        17: ("Clear", "Road work"),
        31: ("Quiet", "Holiday week"),
        32: ("Quiet", "Travel weekend"),
        39: ("Clear", "Heavy rain"),
        40: ("Clear", "Ice or snow"),
        41: ("Clear", "Outage"),
        43: ("Clear", "Poor air"),
        44: ("Clear", "Basin storm"),
        45: ("Clear", "Wind event"),
        64: ("Clear", "On hold"),
        66: ("Clear", "Allocated"),
        109: ("Clear", "Inspection"),
        110: ("No rule", "In force"),
        111: ("No rule", "In force"),
    }
    off, on = flags.get(fid, ("Clear", "Active"))
    return off if value <= 0 else on


def economy_movers(state: GameState, city_id: str | None = None, limit: int = 5) -> list[dict]:
    """Biggest index movers this week. State factors are excluded from the ranking."""
    rows = [row for row in economy_factors(state, city_id=city_id) if row.get("kind") == "index"]
    rows.sort(key=lambda row: (-abs(int(row["value"]) - int(row["neutral"])), int(row["id"])))
    return rows[: max(0, int(limit))]


# --- Public read API for x (shapes frozen; E2 fills news, weather, and events) ---
def economy_snapshot(state: GameState) -> dict:
    _ensure(state)
    gauges = []
    for fid in GAUGE_IDS:
        info = FACTORS[fid]
        if info.get("kind") == "state":
            continue
        value = _value(state, fid)
        prev = _value(state, fid, previous=True)
        from open_late.economy_e4 import gauge_band

        gauges.append(
            {
                "id": fid,
                "name": info["name"],
                "value": value,
                "delta": value - prev,
                "unit": "index",
                "band": gauge_band(value),
                "kind": "index",
                "neutral": 100,
                "label": str(int(value)),
            }
        )
    cities = []
    for city in CITIES:
        cities.append(
            {
                "city_id": city,
                "traffic": _value(state, 11, city),
                "wage_pressure": _value(state, 13, city),
                "weather": weather_label(state, city),
            }
        )
    from open_late.finance import starting_reserve
    from open_late.corporate import corporate_reserve

    reserve = corporate_reserve(economy_difficulty(state)) if state.mode == "corporate" else starting_reserve(state.mode, economy_difficulty(state))
    difficulty = economy_difficulty(state)
    return {
        "week_id": week_id(state.day),
        "day": int(state.day),
        "difficulty": difficulty,
        "starting_reserve": int(reserve),
        "levers": difficulty_levers(difficulty, mode=("corporate" if state.mode == "corporate" else "shop")),
        "gauges": gauges,
        "cities": cities,
        "events_active": event_rows(state),
    }


def economy_factor(state: GameState, factor_id: int, city_id: str | None = None) -> dict:
    _ensure(state)
    info = FACTORS.get(int(factor_id))
    if info is None:
        raise ValueError(f"Unknown factor id: {factor_id}")
    fid = int(factor_id)
    city = city_id if info["scope"] == "city" or fid in E1_LOCAL else None
    value = _value(state, fid, city)
    prev = _value(state, fid, city, previous=True)
    cities = None
    if info["scope"] == "city" or fid in E1_LOCAL:
        cities = {item: _value(state, fid, item) for item in CITIES}
    kind = str(info.get("kind") or "index")
    neutral = int(info.get("neutral", 100))
    from open_late.economy_e4 import gauge_band

    band = "steady" if kind == "state" else gauge_band(value)
    return {
        "id": fid,
        "name": info["name"],
        "category": info["category"],
        "scope": info["scope"],
        "value": value,
        "delta": value - prev,
        "range": list(info["range"]),
        "driver": info["driver"],
        "cities": cities,
        "kind": kind,
        "neutral": neutral,
        "band": band,
        "label": factor_label(state, fid, city_id=city),
    }


def economy_factors(state: GameState, *, category: str | None = None, city_id: str | None = None) -> list[dict]:
    rows = []
    for fid in range(1, 121):
        info = FACTORS[fid]
        if category and info["category"] != category:
            continue
        rows.append(economy_factor(state, fid, city_id=city_id))
    return rows


def economy_sparklines(state: GameState, factor_ids: list[int], weeks: int = 12, store_id: str | None = None, lines: list[str] | None = None) -> dict:
    """Factor series, optional P&L lines, and a chain overlay when lines are requested."""
    from open_late.economy_e4 import sparkline_payload

    _ensure(state)
    return sparkline_payload(state, list(factor_ids or []), weeks, store_id, lines)


def economy_store_impact(
    state: GameState,
    store_id: str,
    days: int = 7,
    *,
    department: str | None = None,
    category: str | None = None,
    events_only: bool = False,
    min_dollars: int = 0,
) -> dict:
    """Why this P&L moved vs a neutral-card replay of each week in the window."""
    from open_late.hq import store_pnl
    from open_late.economy_e4 import build_store_impact

    _ensure(state)
    pnl = store_pnl(state, store_id, days=days)
    return build_store_impact(
        state,
        store_id,
        days,
        pnl,
        department=department,
        category=category,
        events_only=events_only,
        min_dollars=min_dollars,
    )


def economy_news(state: GameState, *, store_id: str | None = None, limit: int = 10) -> list[dict]:
    """Newest-first news rows. National items appear in a store filter."""
    from open_late.economy_news import public_row

    _ensure(state)
    items = list(reversed(state.economy.news or []))
    if store_id:
        items = [
            item
            for item in items
            if not item.get("store_ids") or store_id in (item.get("store_ids") or [])
        ]
    limit = max(0, int(limit))
    return [public_row(item) for item in items[:limit]]


def economy_calendar(state: GameState, weeks: int = 8) -> list[dict]:
    _ensure(state)
    rows = []
    start_week = week_id(state.day)
    for offset in range(max(1, int(weeks))):
        wid = start_week + offset
        day_from = wid * 7 + 1
        day_to = day_from + 6
        year_week = wid % 52
        labels: list[str] = []
        if any(is_payday(day) for day in range(day_from, day_to + 1)):
            labels.append("Payday")
        if is_harvest_card_week(day_from) or is_harvest_card_week(day_to):
            labels.append("Harvest Card")
        if _cycle_boost(year_week, 32, 35, 16):
            labels.append("Back to school")
        if _cycle_boost(year_week, 47, 51, 22):
            labels.append("Year-end gift week")
        if _cycle_boost(year_week, 8, 14, 10):
            labels.append("Refund season")
        if _cycle_boost(year_week, 22, 32, 12):
            labels.append("Summer grill")
        if year_week >= 48 or year_week <= 8:
            labels.append("Winter comfort")
        if _cycle_boost(year_week, 12, 20, 16):
            labels.append("Spring garden")
        if year_week == 26:
            labels.append("Midyear holiday")
        if year_week == 35:
            labels.append("Travel weekend")
        if _cycle_boost(year_week, 7, 7, 8):
            labels.append("Sweetheart week")
        if _cycle_boost(year_week, 43, 44, 14):
            labels.append("Harvest Night")
        rows.append(
            {
                "week_id": wid,
                "day_from": day_from,
                "day_to": day_to,
                "labels": labels,
                "city_weather": {
                    city: weather_label(state, city, day=day_from if offset else state.day) for city in CITIES
                },
            }
        )
    return rows
