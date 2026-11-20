"""Catalog, people, and places for Back Office: Retail supercenters."""

from __future__ import annotations

from open_late import GAME_NAME, STUDIO_NAME
from open_late.finance import SIZE_MULT, size_int
from open_late.models import Product, Regular, Site, Staff, Supplier

SUPPLIERS: dict[str, Supplier] = {
    "meadowgrove": Supplier(
        id="meadowgrove",
        name="Meadowgrove Pantry",
        lead_time_days=2,
        minimum_order=12000,
        exclusive_ok=False,
        categories=["grocery"],
        price_tier="Value",
        brands=["Meadowgrove", "Aisle House"],
        blurb="Dry grocery and bakery. Short lead, thin margins, frequent drops.",
    ),
    "orchard": Supplier(
        id="orchard",
        name="Orchard Lane",
        lead_time_days=1,
        minimum_order=8000,
        exclusive_ok=False,
        categories=["produce"],
        price_tier="Value",
        brands=["Orchard Lane"],
        blurb="Fresh produce. Fast truck, short shelf life, tight margins.",
    ),
    "coldfield": Supplier(
        id="coldfield",
        name="Coldfield Farms",
        lead_time_days=2,
        minimum_order=20000,
        exclusive_ok=False,
        categories=["meat_dairy", "frozen"],
        price_tier="Mid",
        brands=["Coldfield", "Frostbank"],
        blurb="Meat, dairy, and frozen. Cold-chain trucks, net seven, solid quality.",
    ),
    "soapstone": Supplier(
        id="soapstone",
        name="Soapstone Goods",
        lead_time_days=3,
        minimum_order=15000,
        exclusive_ok=False,
        categories=["household"],
        price_tier="Value",
        brands=["Soapstone"],
        blurb="Paper, soap, and the rest of the cleaning aisle.",
    ),
    "riverwell": Supplier(
        id="riverwell",
        name="Riverwell Care",
        lead_time_days=3,
        minimum_order=18000,
        exclusive_ok=False,
        categories=["health_beauty", "pharmacy"],
        price_tier="Mid",
        brands=["Riverwell", "Clearwell"],
        blurb="Health, beauty, and pharmacy-counter staples. Careful paperwork.",
    ),
    "sparklane": Supplier(
        id="sparklane",
        name="Sparklane Tech",
        lead_time_days=5,
        minimum_order=40000,
        exclusive_ok=False,
        categories=["electronics"],
        price_tier="High",
        brands=["Sparklane", "Nimbus"],
        blurb="Consumer electronics. High ticket, mixed margin, slower restock.",
    ),
    "millthread": Supplier(
        id="millthread",
        name="Millthread Apparel",
        lead_time_days=5,
        minimum_order=20000,
        exclusive_ok=False,
        categories=["clothing"],
        price_tier="Mid",
        brands=["Millthread", "Harbor Knit"],
        blurb="Everyday apparel in a size run. Decent margin if the sizes land.",
    ),
    "playnook": Supplier(
        id="playnook",
        name="Playnook",
        lead_time_days=4,
        minimum_order=12000,
        exclusive_ok=False,
        categories=["toys"],
        price_tier="Value",
        brands=["Playnook", "Cedar Hill"],
        blurb="Toys and games. Cheap lines come back if quality is thin.",
    ),
    "yardwell": Supplier(
        id="yardwell",
        name="Yardwell Supply",
        lead_time_days=4,
        minimum_order=16000,
        exclusive_ok=False,
        categories=["home_garden", "sporting"],
        price_tier="Mid",
        brands=["Yardwell", "Trailbench"],
        blurb="Home, garden, and sporting goods from one house.",
    ),
    "festoon": Supplier(
        id="festoon",
        name="Festoon Seasonal",
        lead_time_days=6,
        minimum_order=15000,
        exclusive_ok=False,
        categories=["seasonal"],
        price_tier="Mid",
        brands=["Festoon"],
        blurb="Holiday and patio seasonal. Long lead, margins all over the map.",
    ),
    "labelco": Supplier(
        id="labelco",
        name="Private Label Co",
        lead_time_days=7,
        minimum_order=40000,
        exclusive_ok=True,
        categories=["grocery", "household"],
        price_tier="Value",
        brands=["Aisle House"],
        blurb="Your house brand. Slow, a real minimum, and only after the label is signed.",
    ),
}


def _p(
    pid: str,
    name: str,
    dept: str,
    quality: int,
    cost: int,
    price: int,
    trend: str,
    supplier: str,
    brand: str,
    blurb: str,
    shelf: int = 0,
    intensity: int = 0,
    exclusive: bool = False,
    case_size: int = 1,
) -> Product:
    return Product(
        id=pid,
        name=name,
        category=dept,
        department=dept,
        quality=quality,
        cost=cost,
        price=price,
        trend=trend,  # type: ignore[arg-type]
        supplier_id=supplier,
        brand=brand,
        intensity=intensity,
        exclusive=exclusive,
        blurb=blurb,
        shelf_life_days=shelf,
        case_size=max(1, int(case_size or 1)),
    )


# Authored catalog. This is a list. A live GameState keeps the same records
# as state.products: a dict keyed by product id. Pass either to iter_products().
PRODUCTS: list[Product] = [
    # Grocery (10): thin margins; bakery is perishable.
    _p("groc-flour", "All-purpose flour, 5 lb", "grocery", 4, 3, 4, "steady", "meadowgrove", "Meadowgrove", "A basic bag for the baking aisle.", 0),
    _p("groc-rice", "Long-grain rice, 2 lb", "grocery", 4, 3, 4, "steady", "meadowgrove", "Meadowgrove", "A pantry staple with a thin ticket.", 0),
    _p("groc-pasta", "Dry pasta, 1 lb", "grocery", 4, 3, 4, "steady", "meadowgrove", "Meadowgrove", "Everyday noodles, stacked by the case.", 0),
    _p("groc-cereal", "Morning flake cereal", "grocery", 3, 3, 4, "steady", "meadowgrove", "Meadowgrove", "A family box with ordinary margins.", 0),
    _p("groc-tomatoes", "Canned tomatoes, 28 oz", "grocery", 4, 3, 4, "steady", "meadowgrove", "Aisle House", "House canned tomatoes for the grocery wall.", 0),
    _p("groc-spread", "Peanut spread, 16 oz", "grocery", 4, 3, 4, "steady", "meadowgrove", "Meadowgrove", "A lunchbox jar, priced tight.", 0),
    _p("groc-coffee", "Ground coffee, 12 oz", "grocery", 4, 6, 8, "rising", "meadowgrove", "Meadowgrove", "A mid-aisle bag with a little more room.", 0),
    _p("groc-bread", "Sandwich loaf", "grocery", 3, 3, 4, "steady", "meadowgrove", "Meadowgrove", "Bakery bread. Short shelf, daily turns.", 3),
    _p("groc-muffins", "Bakery muffin 4-pack", "grocery", 3, 3, 4, "steady", "meadowgrove", "Meadowgrove", "In-store bakery pack. Two or three days at most.", 2),
    _p("groc-buns", "Bakery dinner rolls", "grocery", 3, 3, 4, "steady", "meadowgrove", "Meadowgrove", "Soft rolls from the bakery case.", 3),
    # Produce (10)
    _p("prod-bananas", "Bananas, bunch", "produce", 3, 3, 4, "steady", "orchard", "Orchard Lane", "The first thing people look for. Turns fast.", 4),
    _p("prod-apples", "Bagged apples, 3 lb", "produce", 4, 3, 4, "steady", "orchard", "Orchard Lane", "A family bag with a short week on the rack.", 7),
    _p("prod-oranges", "Bagged oranges, 4 lb", "produce", 4, 3, 4, "steady", "orchard", "Orchard Lane", "Citrus with a little more life than greens.", 8),
    _p("prod-lettuce", "Head lettuce", "produce", 3, 3, 4, "steady", "orchard", "Orchard Lane", "Crisp only for a few days.", 4),
    _p("prod-tomatoes", "Tomatoes, 1 lb", "produce", 3, 3, 4, "rising", "orchard", "Orchard Lane", "Ripe fruit that will not wait.", 5),
    _p("prod-onions", "Yellow onions, 3 lb", "produce", 4, 3, 4, "steady", "orchard", "Orchard Lane", "A longer-keeping bag for the rack.", 10),
    _p("prod-potatoes", "Russet potatoes, 5 lb", "produce", 4, 3, 4, "steady", "orchard", "Orchard Lane", "A heavy bag that still turns each week.", 12),
    _p("prod-berries", "Mixed berries, pint", "produce", 4, 5, 7, "rising", "orchard", "Orchard Lane", "High waste if they sit.", 3),
    _p("prod-carrots", "Baby carrots, 1 lb", "produce", 4, 3, 4, "steady", "orchard", "Orchard Lane", "Bagged carrots with a short, honest life.", 8),
    _p("prod-salad", "Bagged salad mix", "produce", 3, 3, 4, "steady", "orchard", "Orchard Lane", "Washed greens. Mark them down before they turn.", 5),
    # Meat and Dairy (10)
    _p("meat-chicken", "Chicken thighs, family pack", "meat_dairy", 4, 6, 8, "steady", "coldfield", "Coldfield", "A weekday pack that cannot sit.", 4),
    _p("meat-turkey", "Ground turkey, 1 lb", "meat_dairy", 4, 6, 8, "steady", "coldfield", "Coldfield", "Lean grind with a short case life.", 3),
    _p("meat-pork", "Pork chops, 2-pack", "meat_dairy", 4, 6, 8, "steady", "coldfield", "Coldfield", "A mid-case cut, tight on days.", 4),
    _p("meat-ham", "Sliced ham, 12 oz", "meat_dairy", 4, 6, 8, "steady", "coldfield", "Coldfield", "Deli pack for the lunch case.", 6),
    _p("meat-steak", "Family steak pack", "meat_dairy", 5, 12, 16, "rising", "coldfield", "Coldfield", "A higher ticket with the same short clock.", 4),
    _p("dairy-milk", "Whole milk, gallon", "meat_dairy", 4, 3, 4, "steady", "coldfield", "Coldfield", "The dairy door. Thin margin, honest date.", 10),
    _p("dairy-yogurt", "Yogurt cups, 6-pack", "meat_dairy", 4, 6, 8, "steady", "coldfield", "Coldfield", "A weekly dairy staple.", 12),
    _p("dairy-cheddar", "Cheddar block, 8 oz", "meat_dairy", 4, 3, 4, "steady", "coldfield", "Coldfield", "A small block with a modest date.", 14),
    _p("dairy-butter", "Salted butter, 1 lb", "meat_dairy", 5, 6, 8, "steady", "coldfield", "Coldfield", "Baking butter, longer than fresh meat.", 16),
    _p("dairy-eggs", "Large eggs, dozen", "meat_dairy", 4, 3, 4, "steady", "coldfield", "Coldfield", "A dozen with a little more life than meat.", 14),
    # Frozen (10): not daily-spoil; the cold case holds them.
    _p("fzn-peas", "Frozen peas, 16 oz", "frozen", 4, 3, 4, "steady", "coldfield", "Frostbank", "A freezer bag that waits for the weeknight.", 0),
    _p("fzn-fries", "Oven fries, 32 oz", "frozen", 3, 3, 4, "steady", "coldfield", "Frostbank", "A family bag from the frozen wall.", 0),
    _p("fzn-pizza", "Frozen pizza", "frozen", 3, 5, 7, "steady", "coldfield", "Frostbank", "A mid-aisle pizza with honest room.", 0),
    _p("fzn-ice", "Vanilla ice cream, 1.5 qt", "frozen", 4, 5, 7, "rising", "coldfield", "Frostbank", "A freezer treat with a little margin.", 0),
    _p("fzn-waffles", "Frozen waffles, 10-pack", "frozen", 3, 3, 4, "steady", "coldfield", "Frostbank", "Breakfast from the freezer door.", 0),
    _p("fzn-meals", "Frozen dinner tray", "frozen", 3, 3, 4, "steady", "coldfield", "Frostbank", "A single tray for a late shift.", 0),
    _p("fzn-berries", "Frozen mixed berries", "frozen", 4, 5, 7, "steady", "coldfield", "Frostbank", "Fruit that will keep if the case stays cold.", 0),
    _p("fzn-fish", "Fish sticks, 20 oz", "frozen", 3, 5, 7, "steady", "coldfield", "Frostbank", "A kids' freezer box.", 0),
    _p("fzn-pie", "Frozen pot pie", "frozen", 3, 3, 4, "steady", "coldfield", "Frostbank", "A small pie, stacked two deep.", 0),
    _p("fzn-juice", "Frozen juice concentrate", "frozen", 4, 3, 4, "steady", "coldfield", "Frostbank", "A can from the freezer door.", 0),
    # Household (10)
    _p("house-towels", "Paper towels, 6-pack", "household", 4, 6, 9, "steady", "soapstone", "Soapstone", "The paper aisle workhorse.", 0),
    _p("house-bags", "Trash bags, 30-ct", "household", 4, 6, 9, "steady", "soapstone", "Soapstone", "Kitchen bags, mid-aisle.", 0),
    _p("house-dish", "Dish soap, 28 oz", "household", 4, 4, 6, "steady", "soapstone", "Soapstone", "A sink bottle with ordinary room.", 0),
    _p("house-laundry", "Laundry soap, 64 oz", "household", 4, 8, 12, "steady", "soapstone", "Soapstone", "A jug that turns every week.", 0),
    _p("house-sponges", "Sponge 4-pack", "household", 3, 2, 3, "steady", "soapstone", "Soapstone", "A small add-on at the end of the aisle.", 0),
    _p("house-foil", "Aluminum foil, 30 ft", "household", 4, 4, 6, "steady", "soapstone", "Soapstone", "A kitchen roll with a fair ticket.", 0),
    _p("house-parchment", "Parchment paper", "household", 4, 4, 6, "steady", "soapstone", "Soapstone", "A baking roll next to the foil.", 0),
    _p("house-bulbs", "LED bulbs, 4-pack", "household", 4, 7, 10, "steady", "soapstone", "Soapstone", "A better margin than paper goods.", 0),
    _p("house-batteries", "AA batteries, 8-pack", "household", 4, 6, 9, "rising", "soapstone", "Soapstone", "A checkout pack with decent room.", 0),
    _p("house-cleaner", "All-purpose cleaner", "household", 4, 4, 6, "steady", "soapstone", "Soapstone", "A spray bottle for the cleaning wall.", 0),
    # Health and Beauty (10)
    _p("beauty-shampoo", "Daily shampoo, 12 oz", "health_beauty", 4, 5, 8, "steady", "riverwell", "Riverwell", "A mid-aisle bottle with honest room.", 0),
    _p("beauty-paste", "Toothpaste, 6 oz", "health_beauty", 4, 4, 6, "steady", "riverwell", "Riverwell", "A tube people pick up without thinking.", 0),
    _p("beauty-lotion", "Hand and body lotion", "health_beauty", 4, 5, 8, "steady", "riverwell", "Riverwell", "A pump bottle with a fair margin.", 0),
    _p("beauty-deodorant", "Daily deodorant", "health_beauty", 4, 4, 6, "steady", "riverwell", "Riverwell", "A stick from the care wall.", 0),
    _p("beauty-soap", "Bar soap, 3-pack", "health_beauty", 3, 4, 6, "steady", "riverwell", "Riverwell", "A simple pack, priced to move.", 0),
    _p("beauty-razors", "Disposable razors, 5-ct", "health_beauty", 3, 5, 8, "steady", "riverwell", "Riverwell", "A pack with more room than soap.", 0),
    _p("beauty-cotton", "Cotton rounds, 80-ct", "health_beauty", 4, 4, 6, "steady", "riverwell", "Riverwell", "A bag from the beauty endcap.", 0),
    _p("beauty-balm", "Lip balm, 2-pack", "health_beauty", 3, 4, 6, "steady", "riverwell", "Riverwell", "A small add-on near the register.", 0),
    _p("beauty-sun", "Daily sunscreen, 6 oz", "health_beauty", 4, 7, 11, "rising", "riverwell", "Riverwell", "A seasonal mover that still sits year-round.", 0),
    _p("beauty-cream", "Hand cream, 3 oz", "health_beauty", 4, 4, 6, "steady", "riverwell", "Riverwell", "A tube with a better margin.", 0),
    # Pharmacy (10): intensity 3 so a lease without a counter cannot sell them.
    _p("pharm-allergy", "Allergy tablets, 24-ct", "pharmacy", 4, 7, 10, "steady", "riverwell", "Clearwell", "A pharmacy-counter box.", 0, 3),
    _p("pharm-pain", "Pain reliever, 50-ct", "pharmacy", 4, 7, 10, "steady", "riverwell", "Clearwell", "A generic pain box from the counter.", 0, 3),
    _p("pharm-fever", "Children's fever reducer", "pharmacy", 5, 7, 10, "steady", "riverwell", "Clearwell", "A liquid for the family counter.", 0, 3),
    _p("pharm-cough", "Cough syrup, 8 oz", "pharmacy", 4, 7, 10, "steady", "riverwell", "Clearwell", "A bottle that turns when a cold goes around.", 0, 3),
    _p("pharm-antacid", "Antacid tablets, 60-ct", "pharmacy", 4, 5, 7, "steady", "riverwell", "Clearwell", "A counter pack with ordinary room.", 0, 3),
    _p("pharm-bandage", "Adhesive bandage pack", "pharmacy", 4, 5, 7, "steady", "riverwell", "Clearwell", "A first-aid box from the counter.", 0, 3),
    _p("pharm-vitamin", "Vitamin C, 60-ct", "pharmacy", 3, 7, 10, "steady", "riverwell", "Clearwell", "A bottle from the vitamin rack.", 0, 3),
    _p("pharm-saline", "Saline spray", "pharmacy", 4, 5, 7, "steady", "riverwell", "Clearwell", "A small bottle next to the colds.", 0, 3),
    _p("pharm-thermo", "Digital thermometer", "pharmacy", 4, 9, 13, "steady", "riverwell", "Clearwell", "A counter device with a better ticket.", 0, 3),
    _p("pharm-kit", "First-aid kit", "pharmacy", 4, 11, 16, "steady", "riverwell", "Clearwell", "A family kit from the pharmacy wall.", 0, 3),
    # Electronics (10): varied tickets and margins.
    _p("elec-earbuds", "Wired earbuds", "electronics", 3, 10, 12, "steady", "sparklane", "Sparklane", "A low ticket with a full markup.", 0),
    _p("elec-speaker", "Bluetooth speaker", "electronics", 4, 31, 36, "rising", "sparklane", "Nimbus", "A mid-aisle speaker with decent room.", 0),
    _p("elec-cable", "Charging cable", "electronics", 3, 10, 12, "steady", "sparklane", "Sparklane", "A cable with a fat accessory margin.", 0),
    _p("elec-hdmi", "HDMI cable, 6 ft", "electronics", 4, 11, 13, "steady", "sparklane", "Sparklane", "Another accessory with room to price.", 0),
    _p("elec-radio", "Clock radio", "electronics", 3, 19, 22, "steady", "sparklane", "Sparklane", "A small set with a mid ticket. Cost 14, used in tests.", 0),
    _p("elec-tablet", "8-inch tablet", "electronics", 4, 101, 119, "steady", "sparklane", "Nimbus", "A mid ticket with a tighter margin.", 0),
    _p("elec-tv", "32-inch display", "electronics", 4, 152, 179, "fading", "sparklane", "Nimbus", "A floor TV. Thin margin, slow turn.", 0),
    _p("elec-webcam", "USB webcam", "electronics", 4, 25, 29, "steady", "sparklane", "Sparklane", "A desk camera with mid-aisle room.", 0),
    _p("elec-mouse", "Wireless mouse", "electronics", 4, 14, 16, "steady", "sparklane", "Sparklane", "A double-up accessory.", 0),
    _p("elec-strip", "Power strip, 6-outlet", "electronics", 4, 12, 14, "steady", "sparklane", "Sparklane", "A strip that sits next to the cables.", 0),
    # Clothing (10): sized.
    _p("cloth-tee", "Crew-neck tee", "clothing", 4, 7, 14, "steady", "millthread", "Millthread", "A basic tee in a size run.", 0),
    _p("cloth-jeans", "Straight jeans", "clothing", 4, 16, 32, "steady", "millthread", "Millthread", "Denim with a full apparel markup.", 0),
    _p("cloth-hoodie", "Fleece hoodie", "clothing", 4, 14, 28, "rising", "millthread", "Harbor Knit", "A mid-weight hoodie, sized.", 0),
    _p("cloth-socks", "Crew socks, 6-pack", "clothing", 3, 5, 10, "steady", "millthread", "Millthread", "A pack that still uses the size run.", 0),
    _p("cloth-cap", "Ball cap", "clothing", 3, 7, 14, "steady", "millthread", "Harbor Knit", "A hat from the apparel wall.", 0),
    _p("cloth-kids", "Kids' graphic tee", "clothing", 3, 6, 12, "steady", "millthread", "Millthread", "A kids' tee, same size system.", 0),
    _p("cloth-sleep", "Sleep pants", "clothing", 4, 9, 18, "steady", "millthread", "Harbor Knit", "Soft pants in a size run.", 0),
    _p("cloth-jacket", "Denim jacket", "clothing", 4, 22, 44, "steady", "millthread", "Millthread", "A heavier piece with a slower turn.", 0),
    _p("cloth-shorts", "Athletic shorts", "clothing", 3, 9, 18, "rising", "millthread", "Harbor Knit", "Shorts that move in warm weeks.", 0),
    _p("cloth-work", "Work shirt", "clothing", 4, 12, 24, "steady", "millthread", "Millthread", "A button shirt from the work end.", 0),
    # Toys (10)
    _p("toy-blocks", "Wooden building blocks", "toys", 2, 7, 11, "steady", "playnook", "Playnook", "A cheap set. Weak quality comes back.", 0),
    _p("toy-game", "Family board game", "toys", 4, 12, 18, "steady", "playnook", "Cedar Hill", "A table game with a fair ticket.", 0),
    _p("toy-puzzle", "1,000-piece puzzle", "toys", 5, 9, 14, "steady", "playnook", "Cedar Hill", "A solid puzzle that rarely comes back.", 0),
    _p("toy-plush", "Plush fox", "toys", 4, 8, 13, "steady", "playnook", "Playnook", "A soft toy from the kids' wall.", 0),
    _p("toy-tiles", "Building tiles, 40-pc", "toys", 3, 10, 16, "rising", "playnook", "Playnook", "A mid-aisle construction set.", 0),
    _p("toy-chalk", "Sidewalk chalk, 12-ct", "toys", 3, 4, 6, "steady", "playnook", "Playnook", "A cheap outdoor pack.", 0),
    _p("toy-rope", "Jump rope", "toys", 3, 4, 6, "steady", "playnook", "Playnook", "A simple rope for the toy endcap.", 0),
    _p("toy-craft", "Craft kit", "toys", 4, 8, 13, "steady", "playnook", "Cedar Hill", "A boxed craft with a mid ticket.", 0),
    _p("toy-truck", "Toy pickup truck", "toys", 3, 8, 12, "steady", "playnook", "Playnook", "A small truck from the vehicle bin.", 0),
    _p("toy-color", "Coloring set", "toys", 4, 5, 8, "steady", "playnook", "Cedar Hill", "Pencils and a pad, packaged together.", 0),
    # Home and Garden (10)
    _p("garden-soil", "Potting mix, 8 qt", "home_garden", 4, 5, 8, "steady", "yardwell", "Yardwell", "A bag for the garden wall.", 0),
    _p("garden-hose", "Garden hose, 50 ft", "home_garden", 4, 14, 20, "steady", "yardwell", "Yardwell", "A mid-ticket hose.", 0),
    _p("garden-trowel", "Hand trowel", "home_garden", 4, 5, 8, "steady", "yardwell", "Yardwell", "A small tool with a full markup.", 0),
    _p("garden-pot", "Indoor planter, 8 in", "home_garden", 3, 7, 11, "steady", "yardwell", "Yardwell", "A pot from the indoor end.", 0),
    _p("garden-seed", "Grass seed, 3 lb", "home_garden", 4, 8, 13, "rising", "yardwell", "Yardwell", "A seasonal bag that still sits year-round.", 0),
    _p("garden-feed", "All-purpose plant food", "home_garden", 4, 7, 11, "steady", "yardwell", "Yardwell", "A bottle for the garden rack.", 0),
    _p("garden-mat", "Coir doormat", "home_garden", 3, 9, 14, "steady", "yardwell", "Yardwell", "A mat for the entry wall.", 0),
    _p("garden-bin", "Storage bin, 18 qt", "home_garden", 4, 7, 11, "steady", "yardwell", "Yardwell", "A bin from the organizing aisle.", 0),
    _p("garden-frame", "Picture frame, 8x10", "home_garden", 3, 7, 11, "steady", "yardwell", "Yardwell", "A frame from the home wall.", 0),
    _p("garden-cord", "Outdoor extension cord", "home_garden", 4, 10, 16, "steady", "yardwell", "Yardwell", "A cord that sits with the tools.", 0),
    # Sporting Goods (10)
    _p("sport-soccer", "Size 5 soccer ball", "sporting", 4, 10, 15, "steady", "yardwell", "Trailbench", "A practice ball with a fair ticket.", 0),
    _p("sport-yoga", "Yoga mat", "sporting", 4, 10, 16, "rising", "yardwell", "Trailbench", "A mat from the fitness wall.", 0),
    _p("sport-weights", "Dumbbell pair, 8 lb", "sporting", 4, 16, 24, "steady", "yardwell", "Trailbench", "A small pair with mid-aisle room.", 0),
    _p("sport-rope", "Speed jump rope", "sporting", 3, 7, 11, "steady", "yardwell", "Trailbench", "A fitness rope, not the toy one.", 0),
    _p("sport-bottle", "Sports water bottle", "sporting", 3, 5, 8, "steady", "yardwell", "Trailbench", "A bottle from the fitness endcap.", 0),
    _p("sport-chair", "Camping chair", "sporting", 4, 19, 28, "steady", "yardwell", "Trailbench", "A folding chair with a mid ticket.", 0),
    _p("sport-fish", "Starter fishing kit", "sporting", 3, 16, 24, "steady", "yardwell", "Trailbench", "A boxed kit for the weekend wall.", 0),
    _p("sport-helmet", "Bike helmet", "sporting", 5, 20, 30, "steady", "yardwell", "Trailbench", "A helmet with a careful quality line.", 0),
    _p("sport-bands", "Resistance bands, 3-pack", "sporting", 3, 8, 12, "steady", "yardwell", "Trailbench", "A pack from the fitness pegs.", 0),
    _p("sport-stool", "Folding camp stool", "sporting", 3, 10, 16, "steady", "yardwell", "Trailbench", "A smaller seat than the chair.", 0),
    # Seasonal (10): mixed margins.
    _p("season-lights", "String lights, 25 ft", "seasonal", 3, 8, 14, "rising", "festoon", "Festoon", "A fat-margin string for the seasonal endcap.", 0),
    _p("season-wreath", "Door wreath", "seasonal", 4, 12, 22, "rising", "festoon", "Festoon", "A wreath that only moves in its window.", 0),
    _p("season-wrap", "Wrapping paper, 3-roll", "seasonal", 3, 5, 9, "steady", "festoon", "Festoon", "A pack with a full seasonal markup.", 0),
    _p("season-cards", "Greeting card 8-pack", "seasonal", 4, 5, 9, "steady", "festoon", "Festoon", "Cards with a high ticket relative to cost.", 0),
    _p("season-flag", "Lawn flag", "seasonal", 3, 6, 11, "steady", "festoon", "Festoon", "A flag that turns with the calendar.", 0),
    _p("season-cocoa", "Seasonal cocoa tin", "seasonal", 4, 4, 7, "rising", "festoon", "Festoon", "A tighter-margin tin for cold weeks.", 0),
    _p("season-lantern", "Patio lantern", "seasonal", 4, 9, 16, "steady", "festoon", "Festoon", "A lantern for the warm-weather wall.", 0),
    _p("season-cape", "Kids' dress-up cape", "seasonal", 3, 7, 13, "steady", "festoon", "Festoon", "A clean costume piece for a short season.", 0),
    _p("season-picnic", "Picnic set", "seasonal", 4, 11, 20, "fading", "festoon", "Festoon", "A mid-ticket set that cools off after summer.", 0),
    _p("season-shovel", "Snow shovel", "seasonal", 4, 9, 16, "steady", "festoon", "Festoon", "A tighter-margin tool for the cold weeks.", 0),
]


from open_late.catalog_e8 import E8_ROWS

for _row in E8_ROWS:
    _pid, _name, _dept, _quality, _cost, _price, _trend, _supplier, _brand, _blurb, _shelf, _intensity, _case = _row
    PRODUCTS.append(
        _p(_pid, _name, _dept, _quality, _cost, _price, _trend, _supplier, _brand, _blurb, _shelf, _intensity, case_size=_case)
    )

_DEFAULT_CASE = {
    "grocery": 12,
    "produce": 8,
    "meat_dairy": 6,
    "frozen": 8,
    "household": 6,
    "health_beauty": 6,
    "pharmacy": 6,
    "electronics": 1,
    "clothing": 6,
    "toys": 4,
    "home_garden": 2,
    "sporting": 2,
    "seasonal": 4,
}
_E8_IDS = {row[0] for row in E8_ROWS}
for _product in PRODUCTS:
    if _product.id in _E8_IDS:
        continue
    case = _DEFAULT_CASE.get(_product.department, 1)
    if "gallon" in _product.name.lower():
        case = 4
    if _product.department == "electronics" and _product.price >= 80:
        case = 1
    _product.case_size = case


LABEL_PRODUCTS: list[Product] = [
    _p("label-flour", "Aisle House flour, 5 lb", "grocery", 4, 3, 4, "steady", "labelco", "Aisle House", "House flour. A little more room than the national bag.", 0, exclusive=True),
    _p("label-towels", "Aisle House paper towels, 6-pack", "household", 4, 6, 9, "steady", "labelco", "Aisle House", "House paper with a cleaner margin.", 0, exclusive=True),
    _p("label-soap", "Aisle House dish soap", "household", 4, 4, 6, "steady", "labelco", "Aisle House", "A house bottle for the cleaning wall.", 0, exclusive=True),
]


SHOP_STOCK = {
    "groc-flour": 396,
    "groc-rice": 396,
    "groc-pasta": 475,
    "groc-cereal": 316,
    "groc-tomatoes": 396,
    "groc-spread": 316,
    "groc-coffee": 237,
    "groc-bread": 129,
    "groc-muffins": 86,
    "groc-buns": 86,
    "prod-bananas": 129,
    "prod-apples": 108,
    "prod-oranges": 108,
    "prod-lettuce": 86,
    "prod-tomatoes": 86,
    "prod-onions": 237,
    "prod-potatoes": 237,
    "prod-berries": 64,
    "prod-carrots": 108,
    "prod-salad": 86,
    "meat-chicken": 86,
    "meat-turkey": 86,
    "meat-pork": 64,
    "meat-ham": 86,
    "meat-steak": 43,
    "dairy-milk": 316,
    "dairy-yogurt": 237,
    "dairy-cheddar": 237,
    "dairy-butter": 237,
    "dairy-eggs": 316,
    "fzn-peas": 316,
    "fzn-fries": 316,
    "fzn-pizza": 237,
    "fzn-ice": 237,
    "fzn-waffles": 237,
    "fzn-meals": 237,
    "fzn-berries": 198,
    "fzn-fish": 198,
    "fzn-pie": 237,
    "fzn-juice": 237,
    "house-towels": 316,
    "house-bags": 237,
    "house-dish": 316,
    "house-laundry": 237,
    "house-sponges": 316,
    "house-foil": 237,
    "house-parchment": 198,
    "house-bulbs": 198,
    "house-batteries": 237,
    "house-cleaner": 237,
    "beauty-shampoo": 198,
    "beauty-paste": 237,
    "beauty-lotion": 198,
    "beauty-deodorant": 198,
    "beauty-soap": 237,
    "beauty-razors": 198,
    "beauty-cotton": 198,
    "beauty-balm": 237,
    "beauty-sun": 158,
    "beauty-cream": 158,
    "pharm-allergy": 158,
    "pharm-pain": 198,
    "pharm-fever": 158,
    "pharm-cough": 158,
    "pharm-antacid": 198,
    "pharm-bandage": 237,
    "pharm-vitamin": 158,
    "pharm-saline": 158,
    "pharm-thermo": 118,
    "pharm-kit": 118,
    "elec-earbuds": 100,
    "elec-speaker": 50,
    "elec-cable": 151,
    "elec-hdmi": 100,
    "elec-radio": 75,
    "elec-webcam": 50,
    "elec-mouse": 75,
    "elec-strip": 100,
    "cloth-tee": 475,
    "cloth-jeans": 316,
    "cloth-hoodie": 237,
    "cloth-socks": 396,
    "cloth-cap": 237,
    "cloth-kids": 316,
    "cloth-sleep": 237,
    "cloth-jacket": 158,
    "cloth-shorts": 237,
    "cloth-work": 198,
    "toy-blocks": 237,
    "toy-game": 158,
    "toy-puzzle": 158,
    "toy-plush": 198,
    "toy-tiles": 158,
    "toy-chalk": 316,
    "toy-rope": 237,
    "toy-craft": 158,
    "toy-truck": 198,
    "toy-color": 237,
    "garden-soil": 198,
    "garden-hose": 118,
    "garden-trowel": 198,
    "garden-pot": 158,
    "garden-seed": 118,
    "garden-feed": 158,
    "garden-mat": 118,
    "garden-bin": 158,
    "garden-frame": 158,
    "garden-cord": 118,
    "sport-soccer": 158,
    "sport-yoga": 158,
    "sport-weights": 79,
    "sport-rope": 198,
    "sport-bottle": 237,
    "sport-chair": 79,
    "sport-fish": 79,
    "sport-helmet": 79,
    "sport-bands": 158,
    "sport-stool": 118,
    "season-lights": 158,
    "season-wreath": 79,
    "season-wrap": 198,
    "season-cards": 237,
    "season-flag": 118,
    "season-cocoa": 198,
    "season-lantern": 118,
    "season-cape": 118,
    "season-picnic": 79,
    "season-shovel": 79,
}


# Shelf / want volumes, scaled with the size pack. Restock tests and the desk use these.
WANT_PERISHABLE = size_int(200)  # produce, meat_dairy, frozen
WANT_STAPLE = size_int(250)  # grocery, household
WANT_GENERAL = size_int(160)


def want_units(department: str) -> int:
    if department in {"produce", "meat_dairy", "frozen"}:
        return WANT_PERISHABLE
    if department in {"grocery", "household"}:
        return WANT_STAPLE
    return WANT_GENERAL



def iter_products(source=None):
    """Yield Product records from the catalog list or a runtime products dict.

    `content.PRODUCTS` and `LABEL_PRODUCTS` are lists. `GameState.products`
    (and door catalogs after merge) are `dict[str, Product]`. This helper
    accepts a list, a dict, a GameState, or None (the main PRODUCTS list).
    It does not change those types.
    """
    if source is None:
        source = PRODUCTS
    elif hasattr(source, "products"):
        source = source.products
    if isinstance(source, dict):
        return iter(source.values())
    return iter(source)


def _sku_counts(source, *, include_exclusive: bool = False) -> dict[str, int]:
    counts: dict[str, int] = {}
    for product in source:
        dept = getattr(product, "department", None) or getattr(product, "category", "")
        if not include_exclusive and getattr(product, "exclusive", False):
            continue
        counts[dept] = counts.get(dept, 0) + 1
    return counts


def department_sku_count(department: str, products=None, *, include_exclusive: bool = False) -> int:
    if products is None and not include_exclusive:
        return max(1, _DEFAULT_SKU_COUNTS.get(department, 0))
    source = products if products is not None else PRODUCTS
    count = 0
    for product in source:
        dept = getattr(product, "department", None) or getattr(product, "category", "")
        if dept != department:
            continue
        if not include_exclusive and getattr(product, "exclusive", False):
            continue
        count += 1
    return max(1, count)


# E7 listed 10 named SKUs in every department; want_units was a per-SKU shelf.
# E8 keeps that department-level shelf and splits it across the larger family.
LEGACY_DEPARTMENT_SKUS = 10


def _family_want_from_counts(counts: dict[str, int]) -> dict[str, int]:
    wants: dict[str, int] = {}
    for department, count in counts.items():
        want = want_units(department) * LEGACY_DEPARTMENT_SKUS
        wants[department] = max(1, (want + max(1, count) - 1) // max(1, count))
    return wants


def family_want_map(products=None) -> dict[str, int]:
    """One-pass family want for every department in the given catalog."""
    if products is None:
        return dict(_DEFAULT_FAMILY_WANT)
    return _family_want_from_counts(_sku_counts(products))


def family_want_units(department: str, products=None) -> int:
    """Per-SKU family share of the historical department shelf.

    Each named SKU stands in for its family. The department still targets about
    LEGACY_DEPARTMENT_SKUS * want_units, split across today's assortment, so a
    larger catalog does not multiply the restock sheet or shrink the wall.
    """
    if products is None:
        if department in _DEFAULT_FAMILY_WANT:
            return _DEFAULT_FAMILY_WANT[department]
        count = 1
    else:
        count = department_sku_count(department, products)
    want = want_units(department) * LEGACY_DEPARTMENT_SKUS
    return max(1, (want + count - 1) // count)


_DEFAULT_SKU_COUNTS = _sku_counts(PRODUCTS)
_DEFAULT_FAMILY_WANT = _family_want_from_counts(_DEFAULT_SKU_COUNTS)


def case_round(quantity: int, case_size: int) -> int:
    """Round a positive need up to the next case pack."""
    if quantity <= 0:
        return 0
    pack = max(1, int(case_size or 1))
    return ((quantity + pack - 1) // pack) * pack


ONLINE_STOCK = {
    "groc-flour": 316,
    "groc-rice": 316,
    "groc-pasta": 396,
    "groc-cereal": 237,
    "groc-coffee": 237,
    "groc-spread": 237,
    "house-towels": 316,
    "house-laundry": 198,
    "house-batteries": 237,
    "beauty-shampoo": 198,
    "beauty-paste": 237,
    "pharm-bandage": 198,
    "pharm-vitamin": 158,
    "elec-earbuds": 126,
    "elec-cable": 201,
    "elec-mouse": 100,
    "elec-strip": 100,
    "cloth-tee": 396,
    "cloth-socks": 316,
    "cloth-hoodie": 198,
    "toy-puzzle": 198,
    "toy-game": 158,
    "toy-color": 237,
    "garden-bin": 158,
    "garden-frame": 158,
    "sport-yoga": 158,
    "sport-bottle": 237,
    "season-lights": 158,
    "season-wrap": 198,
    "season-cards": 237,
}


def _staff(**kwargs) -> Staff:
    return Staff(**kwargs)


STAFF: list[Staff] = [
    _staff(
        id="alyssa",
        name="Alyssa Kane",
        short="Twelve years on a floor. Likes running the endcap photo and says so.",
        product_knowledge=76,
        comfort_modeling=84,
        personality="playful",
        boundaries=[],
        reliability=88,
        aptitude_floor=80,
        aptitude_fulfillment=40,
        aptitude_events=74,
        wage=1520,
        following=12,
    ),
    _staff(
        id="jordan",
        name="Jordan Ellis",
        short="Discreet closer. Will not pose for the weekly ad, host a night event, or work the appointment desk.",
        product_knowledge=82,
        comfort_modeling=10,
        personality="discreet",
        boundaries=["no_modeling", "no_private", "no_events"],
        reliability=92,
        aptitude_floor=90,
        aptitude_fulfillment=55,
        aptitude_events=20,
        wage=1600,
    ),
    _staff(
        id="priya",
        name="Priya Raman",
        short="Warm, specific, and done with appointment-desk work. Fine with a posted photo.",
        product_knowledge=86,
        comfort_modeling=58,
        personality="warm",
        boundaries=["no_private"],
        reliability=90,
        aptitude_floor=88,
        aptitude_fulfillment=50,
        aptitude_events=70,
        wage=1560,
    ),
    _staff(
        id="chris",
        name="Chris Dalton",
        short="Packs clean and tells the truth about shipping. Not a floor person.",
        product_knowledge=64,
        comfort_modeling=8,
        personality="blunt",
        boundaries=["no_modeling", "no_private", "no_events"],
        reliability=94,
        aptitude_floor=36,
        aptitude_fulfillment=92,
        aptitude_events=15,
        wage=1440,
    ),
    _staff(
        id="naomi",
        name="Naomi Brooks",
        short="Good host. Will run a department demo if the rules are posted. Will not work a pharmacy rush alone.",
        product_knowledge=78,
        comfort_modeling=88,
        personality="playful",
        boundaries=["no_intense_demo"],
        reliability=80,
        aptitude_floor=70,
        aptitude_fulfillment=34,
        aptitude_events=93,
        wage=1680,
        following=8,
    ),
    _staff(
        id="evan",
        name="Evan Cho",
        short="New, willing, and still late more often than you want on a payroll.",
        product_knowledge=48,
        comfort_modeling=62,
        personality="warm",
        boundaries=[],
        reliability=54,
        aptitude_floor=60,
        aptitude_fulfillment=66,
        aptitude_events=58,
        wage=1360,
    ),
    _staff(
        id="marisol",
        name="Marisol Vega",
        short="Writes the careful emails. Knows the catalog. Will not be the face of the store.",
        product_knowledge=91,
        comfort_modeling=18,
        personality="discreet",
        boundaries=["no_modeling"],
        reliability=90,
        aptitude_floor=84,
        aptitude_fulfillment=72,
        aptitude_events=40,
        wage=1760,
    ),
    _staff(
        id="dean",
        name="Dean Okonkwo",
        short="Floor lead. Twelve years in retail. He will not host after hours.",
        product_knowledge=88,
        comfort_modeling=46,
        personality="blunt",
        boundaries=["no_events"],
        reliability=96,
        aptitude_floor=94,
        aptitude_fulfillment=40,
        aptitude_events=22,
        wage=1920,
    ),
]

REGULARS: list[Regular] = [
    Regular(id="mark", name="Mark Adelman", blurb="High spend, specific lists, and pushy about a manager override.", preferences=["electronics", "seasonal"], discretion=18, loyalty=52, pushiness=74, spend=860, introduced=True, visits=4),
    Regular(id="ellen", name="Ellen Park", blurb="Wants the grocery wall, a quiet voice, and a plain bag.", preferences=["grocery", "household"], discretion=92, loyalty=58, pushiness=8, spend=410, introduced=True, visits=6),
    Regular(id="vincent", name="Vincent Shaw", blurb="Buys clothing and does not linger.", preferences=["clothing"], discretion=55, loyalty=47, pushiness=12, spend=640, introduced=True, visits=3),
    Regular(id="casey", name="Casey Nguyen", blurb="Grabs household packs, then tells two friends.", preferences=["household", "grocery"], discretion=60, loyalty=50, pushiness=15, spend=220, introduced=True, visits=3),
    Regular(id="ruthie", name="Ruthie Quinn", blurb="Has not come in yet. A first toy aisle visit, if the floor is kind.", preferences=["toys", "household"], discretion=84, loyalty=20, pushiness=4, introduced=False),
    Regular(id="irene", name="Irene Walsh", blurb="Asked a friend where the pharmacy counter is. Still deciding whether to walk in.", preferences=["pharmacy"], discretion=88, loyalty=16, pushiness=6, introduced=False),
    Regular(id="harper", name="Harper Dale", blurb="Knows the electronics wall and leaves if the quality is cheap.", preferences=["electronics", "toys"], discretion=30, loyalty=24, pushiness=28, introduced=False),
    Regular(id="samira", name="Samira & Luis", blurb="A couple shopping together. They want a host who explains the weekly ad, then leaves.", preferences=["grocery", "clothing"], discretion=48, loyalty=22, pushiness=20, introduced=False),
    Regular(id="billie", name="Billie Frost", blurb="Treats staff like friends. Pushes a rule if one isn't posted.", preferences=["toys", "seasonal"], discretion=22, loyalty=30, pushiness=68, introduced=False),
    Regular(id="thea", name="Thea Morgan", blurb="Follows the seasonal endcap and disappears when it doesn't change.", preferences=["seasonal", "clothing"], discretion=40, loyalty=26, pushiness=18, introduced=False),
]


class Offer(Site):
    blurb: str
    opening_cost: int
    min_cash_after: int
    min_respectable: int = 0
    min_nightlife: int = 0
    needs_online: bool = False
    for_online_start: bool = False


OFFERS: dict[str, Offer] = {
    "side_street": Offer(
        id="side_street",
        label="Riverside supercenter",
        blurb="A full floor, a real lot, and neighbors who notice a loud sign or a late truck.",
        rent_weekly=4000,
        foot_traffic=260,
        neighbor_sensitivity=46,
        allows_intense=True,
        opening_cost=28000,
        min_cash_after=18000,
        for_online_start=True,
    ),
    "high_street": Offer(
        id="high_street",
        label="High street",
        blurb="More foot traffic, higher rent, and a block that expects a tidy store.",
        rent_weekly=9300,
        foot_traffic=430,
        neighbor_sensitivity=74,
        allows_intense=True,
        opening_cost=38000,
        min_cash_after=22000,
        min_respectable=55,
    ),
    "nightlife": Offer(
        id="nightlife",
        label="Late boulevard",
        blurb="Late hours, lower neighbor heat, and a rent that assumes you mean the late close.",
        rent_weekly=8000,
        foot_traffic=375,
        neighbor_sensitivity=24,
        allows_intense=True,
        opening_cost=32000,
        min_cash_after=20000,
        min_nightlife=50,
    ),
    "mall": Offer(
        id="mall",
        label="Plaza annex",
        blurb="The most walk-bys. The lease keeps a pharmacy counter off this floor.",
        rent_weekly=11300,
        foot_traffic=520,
        neighbor_sensitivity=86,
        allows_intense=False,
        opening_cost=44000,
        min_cash_after=22000,
        min_respectable=60,
    ),
    "warehouse": Offer(
        id="warehouse",
        label="Warehouse",
        blurb="No customers. More online orders that actually leave the building.",
        rent_weekly=5000,
        foot_traffic=0,
        neighbor_sensitivity=10,
        allows_intense=True,
        is_physical=False,
        is_warehouse=True,
        opening_cost=24000,
        min_cash_after=16000,
        needs_online=True,
    ),
}

SIDE_STREET = Site(
    id="side_street",
    label="Riverside supercenter",
    rent_weekly=4000,
    foot_traffic=260,
    neighbor_sensitivity=46,
    allows_intense=True,
)

def _allocate_opening(legacy: dict[str, int], products: list[Product], *, shippable_only: bool = False) -> dict[str, int]:
    """Spread each department's legacy unit total across the expanded assortment."""
    from collections import defaultdict

    id_to_dept = {product.id: product.department for product in products}
    totals: dict[str, int] = defaultdict(int)
    for product_id, qty in legacy.items():
        dept = id_to_dept.get(product_id)
        if dept:
            totals[dept] += int(qty)
    allocated: dict[str, int] = {}
    for dept, total in totals.items():
        skus = [product for product in products if product.department == dept and not product.exclusive]
        if shippable_only:
            skus = [product for product in skus if int(product.shelf_life_days or 0) == 0]
        if not skus or total <= 0:
            continue
        weights = []
        for product in skus:
            weight = 12.0 / max(1, int(product.price))
            if product.shelf_life_days and product.shelf_life_days <= 5:
                weight *= 0.45
            elif product.shelf_life_days:
                weight *= 0.7
            weights.append(max(0.05, weight))
        mass = sum(weights) or 1.0
        raw = [total * weight / mass for weight in weights]
        floors = [int(value) for value in raw]
        leftover = total - sum(floors)
        order = sorted(range(len(skus)), key=lambda index: raw[index] - floors[index], reverse=True)
        for index in order:
            if leftover <= 0:
                break
            floors[index] += 1
            leftover -= 1
        for product, qty in zip(skus, floors):
            if qty > 0:
                allocated[product.id] = qty
    return allocated


# E8: keep department opening-unit totals, split across the larger family assortment.
SHOP_STOCK = _allocate_opening(SHOP_STOCK, PRODUCTS)
ONLINE_STOCK = _allocate_opening(ONLINE_STOCK, PRODUCTS, shippable_only=True)

# E7a size pack: scale shelf volumes and lease dollars. Foot traffic stays for E7b to hybridize.
SHOP_STOCK = {key: size_int(value) for key, value in SHOP_STOCK.items()}
ONLINE_STOCK = {key: size_int(value) for key, value in ONLINE_STOCK.items()}
SIDE_STREET.rent_weekly = size_int(SIDE_STREET.rent_weekly)
for _offer in OFFERS.values():
    _offer.rent_weekly = size_int(_offer.rent_weekly)
    _offer.opening_cost = size_int(_offer.opening_cost)
    _offer.min_cash_after = size_int(_offer.min_cash_after)

ONLINE_SETUP_COST = size_int(2000)
LABEL_SETUP_COST = size_int(6500)
LABEL_MIN_REP = 48
LABEL_MIN_DAY = 14

HELP = """
Back Office: Retail is a supercenter you run one day at a time. The floor is groceries and everything else: produce, meat and dairy, frozen, household, health and beauty, a pharmacy counter, electronics, clothing, toys, home and garden, sporting goods, and seasonal.

Morning is the inbox. Urgent notes have to be answered before the day can close. The rest can wait.

The desk spends real money. Supplier orders leave the drawer when you place them, and the goods show up after the lead time. Pricing is yours. A bargain toy with poor quality comes back as refunds and reviews. Produce, meat and dairy, and bakery have a shelf life. Near expiry they mark down; at expiry they are written off as shrink.

Each person gets one assignment. Floor, packing, a social post, an appointment desk, an event, training, or off. Limits are on the card. Assigning past a limit is allowed, and you will read the consequence later. A raise sticks. Loyalty slips if a review date passes.

Sunday takes rent, the gross wage, time and a half past eight hours, 7.65% employer tax, insurance, utilities, the sales tax you collected, and 2% on any credit you have drawn. The direct-deposit advice shows what the person actually receives after Social Security, Medicare, federal income tax, state tax, and county tax. That withholding comes out of the gross. It is not a second bill. A quarter with a profit also pays 21% income tax that day. Cards take 2.6% of what the customer was charged. The credit line covers a bad Sunday. It does not pay suppliers, and it does not cover a net-14 bill. Two Sundays in a row that do not clear, and the lease is done.

Clothing is a size run, XS through XL. A customer who does not find their size leaves. Orders also pay freight, and a long lead can arrive with a damaged piece that does not go on the shelf.

Books is the quarter: sales, cost, card fees, tax held, income tax, fixtures, and what you took out. Fixtures depreciate over five years. Operations is hours, coverage, and stock that has sat too long. Market is the other store, the list, and the quarter marks. Eight hours is the base week. Longer hours bring more people, overtime, and more burnout.

Neighborhood trust and destination traffic are separate. They bring different people, different ads, and different neighbors. Expansion is a second rent. Open it when the drawer and the staff can hold it.

The corporate office is a different start. You lease the cities, hire the managers, and they write the shifts inside the labor budget you set. You set the planogram, the ads, the truck out of the Evansville warehouse, and the deals with the houses. A truck takes longer the farther the city is, and a long haul arrives short. A new lease does not sell until the build-out is done. Rent starts when you sign. Co-op accrues on what you buy and comes off an ad when you claim it. Sunday scores each door after cost, shrink, labor, rent, and freight. Stock that sits 28 days is marked down once. Perishables follow their own clock. Seattle, Houston, Las Vegas, and Naperville each have their own wage floor, sales tax, and paycheck withholding. Naperville's lease keeps the pharmacy counter off the floor. Seattle charges extra when you move the schedule after Monday.
""".strip() + f"\n\n{GAME_NAME} is a {STUDIO_NAME} game."


def merge_catalog(state):
    """Add any catalog SKUs missing from a loaded save. Old stock and prices stay.

    New SKUs arrive with on_hand 0 so a mid-game save does not get free inventory.
    Exclusive house-label items are added only after the label is signed.
    """
    from open_late.models import StockLine

    catalog = {product.id: product for product in PRODUCTS}
    if getattr(getattr(state, "flags", None), "private_label", False):
        for product in LABEL_PRODUCTS:
            catalog[product.id] = product
    for product_id, product in catalog.items():
        if product_id not in state.products:
            state.products[product_id] = product.model_copy(deep=True)
        else:
            existing = state.products[product_id]
            if int(getattr(existing, "case_size", 1) or 1) == 1 and int(product.case_size or 1) > 1:
                existing.case_size = product.case_size
        if product_id not in state.stock:
            state.stock[product_id] = StockLine(product_id=product_id, on_hand=0, on_order=0)
    for door in getattr(state, "doors", None) or []:
        stock = getattr(door, "stock", None)
        if not isinstance(stock, dict):
            continue
        for product_id in state.products:
            if product_id not in stock:
                stock[product_id] = StockLine(product_id=product_id, on_hand=0, on_order=0)
    state.save_version = max(int(getattr(state, "save_version", 0) or 0), 4)
    return state
