"""Up and down headline templates for every economy factor (1–120).

Fictional outlets only. Each template uses the factor's plain name,
the city or department where it applies, and a size word (a percent,
'sharply', or 'slightly'). Consumed by economy_news.headline_for.
"""

from __future__ import annotations

# factor_id -> (up_template, down_template)
# Placeholders: {name}, {city}, {dept}, {store}, {size}
HEADLINES: dict[int, tuple[str, str]] = {
    1: (
        '{name} climbs {size} on the national desk, and big-ticket aisles tighten.',
        '{name} eases {size}, loosening electronics and seasonal tickets for a few weeks.',
    ),
    2: (
        'Harbor Ledger: {name} rises {size}, and baskets should fatten if the wall is full.',
        'Harbor Ledger: {name} slips {size}, and shoppers look like they will trade down.',
    ),
    3: (
        '{name} ticks {size} higher; Prairie Wire expects a softer door and a leaner ticket.',
        '{name} eases {size}, and the desk looks for a modest lift in trips.',
    ),
    4: (
        '{name} jumps {size}. Everyday tickets will feel tight unless you reticket a department.',
        '{name} cools {size}, giving grocery and household a little more room on the sticker.',
    ),
    5: (
        '{name} firms {size}. Value aisles may quiet if staples stay in stock.',
        '{name} weakens {size}, and trade-down into house brands is the first tell.',
    ),
    6: (
        '{name} climbs {size} on Amberline racks; freight on Coldfield and Orchard Lane drops should follow.',
        '{name} eases {size} on Amberline racks, and inbound freight should loosen a week behind.',
    ),
    7: (
        '{name} tightens {size}. Corporate drops and replenishment are running late.',
        '{name} loosens {size}, and Basin Review says trucks are starting to clear.',
    ),
    8: (
        '{name} rises {size} on the national activity desk.',
        '{name} softens {size}, a quieter week for traffic and reorders.',
    ),
    9: (
        '{name} lifts {size}; home, garden, and seasonal fixtures should see the first look.',
        '{name} fades {size}, and garden and lumber demand is the first to dip.',
    ),
    10: (
        '{name} climbs {size}. Imported electronics, toys, and apparel will cost more to land.',
        '{name} eases {size}, taking a little pressure off imported landed cost.',
    ),
    11: (
        '{name} rises {size} in {city}, and the door should feel busier if coverage holds.',
        '{name} slips {size} in {city}, with a quieter lot until the walk-ins return.',
    ),
    12: (
        '{name} ticks {size} higher in {city}; Prairie Wire flags a softer local ticket.',
        '{name} eases {size} in {city}, and local trips look a little more willing.',
    ),
    13: (
        '{name} climbs {size} in {city}. Sunday wages will feel it if you match the street.',
        '{name} cools {size} in {city}, easing the Sunday wage ask for a while.',
    ),
    14: (
        '{name} shifts {size} toward higher-ticket shoppers in {city}.',
        '{name} shifts {size} toward a leaner mix in {city}, so value aisles matter more.',
    ),
    15: (
        '{name} jumps {size} in {city}. Nightcourt Dispatch would staff the late side of the week.',
        '{name} fades {size} in {city}, and the tourist door looks quieter than last week.',
    ),
    16: (
        '{name} tightens {size} in {city}; trips from the edge of town are taking longer.',
        '{name} eases {size} in {city}, and the sprawl drive-in is a little smoother.',
    ),
    17: (
        '{name} is on in {city}, cutting trips {size} until the cones come up.',
        '{name} clears in {city}; the drag on local trips should lift {size}.',
    ),
    18: (
        '{name} firms {size} in {city}, a hiring wave the desk can feel in the lot.',
        '{name} wobbles {size} in {city} after a layoff scare; expect a shorter ticket for a bit.',
    ),
    19: (
        '{name} climbs {size} in {city}, squeezing Sunday rent talks and local spend.',
        '{name} eases {size} in {city}, taking a little heat off the lease and the basket.',
    ),
    20: (
        '{name} jumps {size} in {city}. Utility bills and diesel into the dock will follow.',
        '{name} eases {size} in {city}, a softer week for utilities and local freight.',
    ),
    21: (
        '{name} rises {size} in {city}, ahead of the national mood.',
        '{name} slips {size} in {city}, lagging the national confidence desk.',
    ),
    22: (
        '{name} lifts {size} in {city}; late close and Friday-Saturday should carry more of the week.',
        '{name} cools {size} in {city}, and the late-hour door looks thinner.',
    ),
    23: (
        '{name} is on, lifting staple and household trips {size} this payday window.',
        '{name} fades, and the payday lift drops {size} off the week.',
    ),
    24: (
        '{name} window opens this week, lifting staples and produce {size} if the wall is full.',
        '{name} week fades, and the reload lift eases {size} off the calendar.',
    ),
    25: (
        '{name} peaks {size}. Clothing, toys, and backpacks should be faced.',
        '{name} eases {size} as the first-week rush passes.',
    ),
    26: (
        '{name} is on, with gifts, electronics, and seasonal up {size}.',
        '{name} cools {size} after the peak; leftover seasonal will need a plan.',
    ),
    27: (
        '{name} is here, lifting discretionary aisles {size} as refunds land.',
        '{name} tails off {size}, and the refund bump leaves the floor.',
    ),
    28: (
        '{name} is on, lifting meat, frozen, and outdoor {size}.',
        '{name} fades {size} as the grill weeks pass.',
    ),
    29: (
        '{name} builds {size}; staples, frozen, and pharmacy get the first look.',
        '{name} eases {size} as the cold stretch lets up.',
    ),
    30: (
        '{name} is in season, lifting garden and outdoor {size}.',
        '{name} fades {size}, and the garden wall can run leaner.',
    ),
    31: (
        '{name} lands this week, bumping midyear endcaps {size} if they are dressed.',
        '{name} has passed, and the midyear bump drops {size} off.',
    ),
    32: (
        '{name} is on; expect travel and convenience food to tilt {size}.',
        '{name} ends, and the travel-weekend lift eases {size}.',
    ),
    33: (
        '{name} index rises {size}; the post-holiday quiet is not as deep as last year.',
        '{name} index dips {size}, a quieter first week back on the floor.',
    ),
    34: (
        '{name} is on, lifting gifts, grocery treats, and cards {size}.',
        '{name} passes, and the short seasonal lift eases {size}.',
    ),
    35: (
        '{name} is on, a two-week run for costumes, candy, and seasonal, up {size}.',
        '{name} wraps, and seasonal demand falls {size} off the peak.',
    ),
    36: (
        '{name} slips the reload {size}; some households will shop a day or two late.',
        '{name} clears, and the reload lands closer to the posted day, {size} less lag.',
    ),
    37: (
        '{name} builds {size} in {city}. Frozen and produce should move; dairy cases work harder.',
        '{name} eases {size} in {city}, taking pressure off frozen cases and produce shrink.',
    ),
    38: (
        '{name} in {city} is lifting staples, frozen, and pharmacy {size}.',
        '{name} in {city} eases {size}, and winter staples can run a little leaner.',
    ),
    39: (
        '{name} in {city} is cutting trips {size} and slowing inbound produce.',
        '{name} lets up in {city}; the drag on trips and produce trucks should lift {size}.',
    ),
    40: (
        '{name} desk for {city}: trips fall {size} today, then a two-day catch-up if the trucks make it.',
        '{name} clears in {city}, and the cut to trips should start to reverse {size}.',
    ),
    41: (
        '{name} desk for {city}: trips collapse {size} today, and cases may not hold.',
        'The {name} in {city} is easing; the hit to trips and cases should start to recover {size}.',
    ),
    42: (
        '{name} builds {size} around {city}. Produce cost is the first to move.',
        '{name} eases {size} around {city}, taking a little heat off produce cost.',
    ),
    43: (
        '{name} in {city} is keeping some trips home {size} and lifting pharmacy and health aisles.',
        '{name} improves in {city}, and the stay-home drag on the door should lift {size}.',
    ),
    44: (
        '{name} is holding containers and produce {size}. Houston doors feel it first.',
        '{name} eases {size}; freight and the Houston door should start to clear.',
    ),
    45: (
        '{name} is on the {city} lot {size}. Inbound delays and a quieter door are likely.',
        '{name} lets up in {city}, and the delay on inbound and the lot should fade {size}.',
    ),
    46: (
        'Case thaw at {store}: {name} writes frozen and dairy into shrink after the outage, hitting the line {size}.',
        'Cases are cold again at {store}; {name} eases {size} off the shrink line.',
    ),
    47: (
        '{name} rises {size} in {city}. Open shifts will take longer to fill.',
        '{name} eases {size} in {city}, and the next hire should come easier.',
    ),
    48: (
        '{name} climbs {size} on this door; Riverbend Desk would watch reviews and off-days.',
        '{name} eases {size} on this door as the crew steadies.',
    ),
    49: (
        '{name} jump {size} on this door after the weather desk. Coverage will be thin if you do not swap a shift.',
        '{name} ease {size} as the weather desk quiets and people make it in.',
    ),
    50: (
        '{name} builds {size} on this door; Sunday overtime will show if the close stays long.',
        '{name} eases {size} on this door as hours and peaks cool off.',
    ),
    51: (
        '{name} tightens {size} in {city}. Posted-schedule changes will cost more.',
        '{name} loosens {size} in {city}, giving the posted sheet a little more slack.',
    ),
    52: (
        '{name} rises {size} in {city}; seasonal floor help should be easier to book.',
        '{name} fades {size} in {city} as the summer help window closes.',
    ),
    53: (
        '{name} tightens {size} in {city}. The pharmacy counter is the first to feel it.',
        '{name} eases {size} in {city}, and pharmacy coverage should be easier to hold.',
    ),
    54: (
        '{name} climbs {size} in {city} for the late close.',
        '{name} eases {size} in {city}, taking a little off the late-close wage bill.',
    ),
    55: (
        '{name} improves {size} on this door after time on the training slot.',
        '{name} slips {size} on this door; a training shift would earn itself back.',
    ),
    56: (
        '{name} widens {size} on this door versus the local floor.',
        '{name} narrows {size} on this door as the posted wage catches the street.',
    ),
    57: (
        '{name} stretches {size}. Imported electronics, toys, clothing, and seasonal leads are slipping.',
        '{name} eases {size}, and import leads should start to catch up.',
    ),
    58: (
        '{name} tightens {size}. Corporate drops and replenishment are running late.',
        '{name} loosens {size}, and Basin Review says the trucks are moving again.',
    ),
    59: (
        '{name} softens {size}. Produce, meat, and frozen take the shrink risk.',
        '{name} firms {size}, a safer week for cold-chain produce and frozen.',
    ),
    60: (
        '{name} adds {size} to inbound calendars. Order earlier or expect a dark wall.',
        '{name} shortens {size}, and drops should land closer to the posted day.',
    ),
    61: (
        '{name} improves {size} with the house; substitutions and shorts should ease.',
        '{name} cools {size} with the house, so shorts and substitutions may creep back.',
    ),
    62: (
        '{name} climbs {size}. Bags, mailers, and pack-out will show it on the invoice.',
        '{name} eases {size}, taking a little off packaging on the next drop.',
    ),
    63: (
        '{name} builds {size} at the Evansville warehouse. Outbound perishable pallets are delayed.',
        '{name} eases {size} at the Evansville warehouse, and outbound trucks should clear.',
    ),
    64: (
        '{name} is sitting on {dept}, slipping inbound {size}. Expect a stockout and demurrage until it clears.',
        '{name} lifts off {dept} {size}; that aisle can be trusted again.',
    ),
    65: (
        '{name} climbs {size}. Diesel is showing up in freight a week behind the rack.',
        '{name} eases {size}, and freight should follow the softer diesel print.',
    ),
    66: (
        '{name} tightens {size} on {dept}. What arrives will cost more, and Northline will take the rest if you go bare.',
        '{name} eases {size} on {dept}, and allocations start to fill in.',
    ),
    67: (
        '{name} climbs {size}. Thin grocery tickets will need a reticket or a tighter buy.',
        '{name} eases {size}, giving the grocery wall a little more margin room.',
    ),
    68: (
        '{name} jumps {size}. Orchard Lane drops will land dear until the rack cools.',
        '{name} cools {size}, and produce cost should follow the softer print.',
    ),
    69: (
        '{name} climbs {size}; Coldfield cases will show it on the next invoice.',
        '{name} eases {size}, a softer week for meat and dairy cost.',
    ),
    70: (
        '{name} rises {size}, a slower but real lift in frozen landed cost.',
        "{name} eases {size}, taking pressure off the frozen wall's cost line.",
    ),
    71: (
        '{name} firms {size}. Paper, soap, and cleaners will feel it first.',
        '{name} softens {size}, a little relief on household paper and chemicals.',
    ),
    72: (
        '{name} climbs {size}, feeding through into health and beauty cost.',
        '{name} eases {size}, a milder week for health and beauty inputs.',
    ),
    73: (
        '{name} rises {size}; pharmacy-counter replenishment will cost more to land.',
        '{name} eases {size}, taking a little off pharmacy input cost.',
    ),
    74: (
        '{name} jumps {size}. Tablets, TVs, and accessories will land dearer.',
        '{name} eases {size}, a softer import print for electronics.',
    ),
    75: (
        '{name} climbs {size}, and the apparel run will feel it on the next mill drop.',
        '{name} eases {size}, loosening apparel fiber cost a step.',
    ),
    76: (
        '{name} rises {size}; Playnook and gift-week toys will cost more to replace.',
        '{name} eases {size}, a milder week for toy inputs.',
    ),
    77: (
        '{name} climbs {size}. Yardwell lumber and garden goods follow the housing mood.',
        '{name} eases {size}, taking heat off garden and lumber inputs.',
    ),
    78: (
        '{name} firms {size} on sporting goods inputs.',
        '{name} softens {size}, a little relief for sporting goods cost.',
    ),
    79: (
        '{name} jumps {size}. Festoon seasonal leads will arrive dearer if you wait.',
        '{name} cools {size}, a softer print for seasonal goods.',
    ),
    80: (
        '{name} rises {size} on this door; Northline is posting firmer tickets.',
        '{name} falls {size} on this door as Northline cuts into the ticket.',
    ),
    81: (
        '{name} builds {size} on this door. Watch the endcap and the Sunday trigger.',
        "{name} eases {size} on this door as Northline's heat backs off.",
    ),
    82: (
        '{name} shifts {size} toward {dept} on this door. Face that wall or lose the trip.',
        '{name} rotates {size} off {dept} on this door; their next push is elsewhere.',
    ),
    83: (
        '{name} is on in {city}, up {size}. Westfork Basket or Lane & Barrel will test the lot.',
        '{name} fades {size} in {city} as the opening heat cools.',
    ),
    84: (
        '{name} heats up {size} in {city}. Expect a messy week of matching tickets.',
        '{name} cools {size} in {city}, and the matching-ticket week should ease.',
    ),
    85: (
        '{name} rises {size} in {city}. Local ads will have to work harder to be heard.',
        '{name} eases {size} in {city}, giving a local ad a cleaner shot.',
    ),
    86: (
        '{name} builds {size} nationally; some trips will compare the ticket before they come in.',
        '{name} eases {size} nationally, a little less heat from the comparison shops.',
    ),
    87: (
        'A {name} is drawing {dept} trips in {city}, up {size}.',
        'The {name} in {city} eases {size} off {dept}, and those trips should start to return.',
    ),
    88: (
        '{name} climbs {size} in {city}. Sunday rent will feel the fold.',
        '{name} eases {size} in {city}, taking a little off the rent fold.',
    ),
    89: (
        '{name} rises {size} in {city}; the common-area add-on folds into rent.',
        '{name} eases {size} in {city}, a milder common-area recovery on the lease.',
    ),
    90: (
        '{name} jumps {size} on this door, often after a storm or outage week.',
        '{name} eases {size} on this door as the insurance desk quiets.',
    ),
    91: (
        '{name} climbs {size} in {city}. Sunday utilities will show it.',
        '{name} eases {size} in {city}, a softer utility print for the week.',
    ),
    92: (
        '{name} ticks {size} higher on this door; a little more folds into rent until you repair.',
        '{name} eases {size} on this door after wear is caught up.',
    ),
    93: (
        '{name} tightens {size} on this door, cutting visits and folding a little into rent.',
        '{name} eases {size} on this door; the lot and the rent fold should both improve.',
    ),
    94: (
        '{name} climbs {size} on the Evansville warehouse lease.',
        '{name} eases {size} on the Evansville warehouse lease.',
    ),
    95: (
        '{name} rises {size} in {city}. A new door will cost more to open.',
        '{name} eases {size} in {city}, a milder print for a build-out.',
    ),
    96: (
        '{name} widens {size} on the national desk, following the policy rate.',
        '{name} narrows {size}, a little cheaper to carry a drawn line.',
    ),
    97: (
        '{name} ticks {size} higher; card fees on the ticket will show it.',
        '{name} eases {size}, taking a little off the card-fee line.',
    ),
    98: (
        '{name} tightens {size} on this door. Do not count on the line for a supplier drop.',
        '{name} loosens {size} on this door, and the line has a little more room.',
    ),
    99: (
        '{name} builds {size} on this door as payables and inventory lean on the drawer.',
        '{name} eases {size} on this door as cash catches up to the book.',
    ),
    100: (
        '{name} rises {size} on this door, especially on clothing size runs and electronics.',
        '{name} eases {size} on this door as the stock turns down.',
    ),
    101: (
        '{name} moves {size} against the book, following the import cost index.',
        '{name} eases {size}, a softer FX print on import payables.',
    ),
    102: (
        '{name} worsens {size} on this door after a short Sunday.',
        '{name} eases {size} on this door as Sundays start to clear again.',
    ),
    103: (
        '{name} stretches {size}; payday and Sunday bills are further apart this week.',
        '{name} tightens {size}, and the float between payday and Sunday bills shortens.',
    ),
    104: (
        '{name} ticks {size} higher in {city}. The sales-tax line on a ticket will follow.',
        '{name} eases {size} in {city}, a slightly lighter sales-tax take.',
    ),
    105: (
        '{name} climbs {size} nationally; the employer payroll bill will feel it.',
        '{name} eases {size} nationally, a milder employer payroll load.',
    ),
    106: (
        '{name} tightens {size} in {city} for paycheck withholding (zero-tax cities stay at zero).',
        '{name} eases {size} in {city} for paycheck withholding (zero-tax cities stay at zero).',
    ),
    107: (
        '{name} is on in {city}, lifting the posted floor {size}.',
        '{name} talk cools {size} in {city}, and the posted floor holds.',
    ),
    108: (
        '{name} tightens {size} in {city}. A late schedule change will cost more.',
        '{name} loosens {size} in {city}, a little more slack on the posted sheet.',
    ),
    109: (
        '{name} lands on this door, disrupting the floor or the counter {size}.',
        '{name} clears on this door, and the disruption should lift {size}.',
    ),
    110: (
        '{name} steps up {size} in {city}, feeding into packaging cost until it is repealed.',
        '{name} eases {size} in {city}, taking a step off the packaging add-on.',
    ),
    111: (
        '{name} tightens {size} nationally; bold campaigns will have to work quieter.',
        '{name} eases {size} nationally, giving a bolder campaign a cleaner run.',
    ),
    112: (
        '{name} rises {size}. Produce and fresh cases should be faced first.',
        '{name} eases {size}, and the fresh tilt is a little less sharp.',
    ),
    113: (
        '{name} builds {size}. House brands and value packs will do more of the work.',
        '{name} eases {size} as shoppers look a little less like they are trading down.',
    ),
    114: (
        '{name} tilts {size} toward home cooking; grocery staples and meat should move.',
        '{name} tilts {size} toward prepared; frozen meals and convenience get the look.',
    ),
    115: (
        '{name} heats up {size}. Electronics endcaps should be ready for a new-set week.',
        '{name} cools {size}, a quieter stretch for screens and gadgets.',
    ),
    116: (
        '{name} lifts {size} with the outdoor season; sporting and garden should be faced.',
        '{name} fades {size}, and outdoor demand can run a little leaner.',
    ),
    117: (
        '{name} rises {size}; the house brand can take more of the grocery and household wall.',
        '{name} eases {size}, and national brands get a little of that space back.',
    ),
    118: (
        '{name} builds {size}. Health, beauty, and pharmacy should be full before the wave peaks.',
        '{name} eases {size}, taking some heat off the self-care aisles.',
    ),
    119: (
        'A {name} is on in {city} for {dept}, running two to four weeks and lifting demand {size}.',
        'The {name} in {city} fades {size} off {dept}.',
    ),
    120: (
        '{name} improves {size} on this door after kinder reviews and fewer returns.',
        '{name} slips {size} on this door; returns and a rough review will show.',
    ),
}

