"""Morning notes. Hard flags always land. Color notes are capped so the desk stays readable."""

from __future__ import annotations

from open_late.content import LABEL_SETUP_COST, SUPPLIERS
from open_late.finance import STABLE_MONTH_CASH, weekly_obligations
from open_late.inbox import add, trim
from open_late.models import Choice, DayReport, GameState, InboxMessage
from open_late.text import money

Builder = tuple[str, int, int, object]


def collect(state: GameState, report: DayReport, rng) -> None:
    _hard(state, report)
    pool: list[tuple[int, str, InboxMessage]] = []
    for key, weight, cooldown, builder in BUILDERS:
        last = state.cooldowns.get(key, -999)
        if state.day - last < cooldown:
            continue
        message = builder(state, report, rng)
        if message is None:
            continue
        pool.append((weight, key, message))
    pool.sort(key=lambda item: -item[0])
    forced = [item for item in pool if item[0] >= 8]
    color = [item for item in pool if item[0] < 8]
    # Stable shuffle from the sim rng.
    for index in range(len(color) - 1, 0, -1):
        swap = rng.randint(0, index)
        color[index], color[swap] = color[swap], color[index]
    picked = forced[:3] + color[:2]
    for _weight, key, message in picked:
        state.cooldowns[key] = state.day
        add(
            state,
            kind=message.kind,
            title=message.title,
            body=message.body,
            urgent=message.urgent,
            choices=message.choices,
        )
    trim(state)


def _hard(state: GameState, report: DayReport) -> None:
    for staff_id in report.quit_ids:
        person = next(member for member in state.staff if member.id == staff_id)
        add(
            state,
            kind="quit",
            title=f"{person.name} quit",
            body=(
                f"Staff note: {person.name} is done. The last assignment crossed a limit they had already named. "
                "Their wage leaves the sheet. The shift does not cover itself."
            ),
        )
    if report.incident:
        add(
            state,
            kind="incident",
            title="Event flag",
            urgent=True,
            body=report.event_blurb or "A guest ignored the rules.",
            choices=[
                Choice(
                    id="back",
                    label="Back the staff and keep that guest out of the next night",
                    effect="back_staff",
                    args={"host_id": report.event_host_id},
                ),
                Choice(
                    id="smooth",
                    label="Comp the guest $60 and smooth it over",
                    effect="smooth_incident",
                    args={"host_id": report.event_host_id},
                ),
            ],
        )
    if report.shortfall:
        add(
            state,
            kind="bills",
            title="Sunday short",
            body=(
                f"The bills missed {money(report.shortfall)}. Credit is {money(state.credit_used)} "
                f"of {money(state.credit_limit)}. A second Sunday like this ends the lease."
            ),
        )


def _msg(title: str, body: str, kind: str, urgent: bool = False, choices: list[Choice] | None = None) -> InboxMessage:
    return InboxMessage(id="", day=0, kind=kind, title=title, body=body, urgent=urgent, choices=choices or [])


def _employed(state: GameState, staff_id: str) -> bool:
    return any(person.id == staff_id and person.employed for person in state.staff)


def _regular(state: GameState, regular_id: str):
    return next((person for person in state.regulars if person.id == regular_id), None)


def red_set(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    sold = report.units_by_product.get("season-lights", 0)
    if sold < 2 or report.assigned.get("alyssa") != "modeling" or not _employed(state, "alyssa"):
        return None
    return _msg(
        "Alyssa on the endcap",
        (
            f"Staff note: Alyssa said the seasonal lights sold {sold} times after she posted the endcap shot. "
            "She's fine doing more, but only during her shifts."
        ),
        "staff",
        choices=[
            Choice(id="shifts", label="Keep posts to her shifts", effect="respect_boundary", args={"staff_id": "alyssa"}),
            Choice(id="offdays", label="Ask her to post on days off too", effect="push_offshift", args={"staff_id": "alyssa"}),
        ],
    )


def mark_fitting(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    mark = _regular(state, "mark")
    if mark is None or not mark.active or mark.banned_private or state.flags.mark_private_open:
        return None
    if state.day < 4 or mark.loyalty < 40:
        return None
    if mark.id not in report.buyer_ids and state.day < 6:
        return None
    return _msg(
        "Customer flag: Mark",
        "Customer flag: Regular (Mark) asked if anyone can do a manager price-check override. He's spent a lot but got pushy last visit.",
        "customer",
        urgent=True,
        choices=[
            Choice(id="floor", label="A short appointment on the open floor, no closed door", effect="discreet_floor", args={"customer_id": "mark"}),
            Choice(id="book", label="Book an appointment-desk price check with someone who accepts them", effect="private_booking", args={"customer_id": "mark"}),
            Choice(id="no", label="Tell him manager overrides are not something you offer", effect="decline_private", args={"customer_id": "mark"}),
            Choice(id="cut", label="Cut him off from appointments", effect="ban_private", args={"customer_id": "mark"}),
        ],
    )


def ellen_thanks(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    if "ellen" not in report.buyer_ids or report.assigned.get("jordan") != "floor":
        return None
    return _msg(
        "Ellen Park",
        "Customer note: Ellen left with a plain bag and told Jordan the room was easy to be in. She will be back on a weekday.",
        "customer",
    )


def ruthie(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    person = _regular(state, "ruthie")
    if person is None or person.introduced or not (2 <= state.day <= 10):
        return None
    if state.stock.get("toy-puzzle") is None or state.stock["toy-puzzle"].on_hand <= 0:
        return None
    return _msg(
        "A first visit, maybe",
        "Customer note: Ruthie wrote in. She wants a first toy-aisle visit and a person who will not make a show of it. She has not decided to walk in.",
        "customer",
        choices=[
            Choice(
                id="invite",
                label="Invite her when a discreet closer is on the floor",
                effect="introduce",
                args={"customer_id": "ruthie", "loyalty": 10, "text": "Ruthie has a weekday appointment with whoever is quietest on the floor."},
            ),
            Choice(
                id="table",
                label="Put a starter puzzle on the front table and let her browse",
                effect="introduce",
                args={"customer_id": "ruthie", "loyalty": 4, "text": "A starter puzzle is on the front table with a plain card. Ruthie can come in without a speech."},
            ),
            Choice(id="later", label="Leave it. She can come in when she is ready.", effect="story", args={"text": "You left the note in the drawer."}),
        ],
    )


def irene(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    person = _regular(state, "irene")
    if person is None or person.introduced or not (5 <= state.day <= 14):
        return None
    return _msg(
        "Irene Walsh",
        "Customer note: Irene asked a friend where to start. She will come in if the first answer is a gentle one and the bag is plain.",
        "customer",
        choices=[
            Choice(
                id="yes",
                label="Tell her to ask for the pharmacy counter",
                effect="introduce",
                args={"customer_id": "irene", "loyalty": 8, "text": "Irene knows to ask for the pharmacy counter. Jordan's kind of sale, if Jordan is in."},
            ),
            Choice(id="no", label="You are too busy for a long first sale", effect="story", args={"text": "You let it pass. She may not write again."}),
        ],
    )


def harper(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    person = _regular(state, "harper")
    if person is None or person.introduced or state.flags.policy == "keep_light":
        return None
    intense = sum(line.on_hand for pid, line in state.stock.items() if state.products[pid].category == "electronics")
    if intense <= 0 or state.day < 6:
        return None
    return _msg(
        "Harper Dale",
        "Customer note: Harper knows the electronics wall and leaves if the goods are cheap. They asked what you actually stand behind.",
        "customer",
        choices=[
            Choice(
                id="quality",
                label="Show the well-made pieces and skip the bargain kit",
                effect="introduce",
                args={"customer_id": "harper", "loyalty": 8, "text": "Harper will shop the pieces you will put your name next to."},
            ),
            Choice(
                id="margin",
                label="Point them at whatever has the best margin",
                effect="introduce",
                args={"customer_id": "harper", "loyalty": 1, "text": "Harper took the pitch. They also looked at the reviews on the way out."},
            ),
        ],
    )


def couples(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    person = _regular(state, "samira")
    if person is None or person.introduced or state.day < 7:
        return None
    if not any(site.is_physical for site in state.sites):
        return None
    return _msg(
        "A couple asks",
        "Customer note: Samira and Luis want a family night where someone explains the weekly ad and the grocery endcap, then leaves them alone. They asked if the rules are real.",
        "customer",
        choices=[
            Choice(id="book", label="Host them tonight, rules posted", effect="book_couples"),
            Choice(id="floor", label="Invite them on a quiet afternoon instead", effect="introduce", args={"customer_id": "samira", "loyalty": 5, "text": "They will come on a weekday afternoon. No closed door."}),
            Choice(id="no", label="Decline", effect="story", args={"text": "You told them the store is not booking nights for two."}),
        ],
    )


def weighted_offer(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    if state.day < 5 or state.cash < 2500 or state.flags.policy == "keep_light":
        return None
    return _msg(
        "Supplier offer: camping weights",
        "Supplier offer: Yardwell can send a short run of the dumbbell pairs. Higher margin, longer lead, mixed reviews on the grips.",
        "supplier",
        choices=[
            Choice(id="pass", label="Pass", effect="story", args={"text": "You left the extra weights on their sheet, not yours."}),
            Choice(id="take", label="Order four", effect="special_order", args={"product_id": "sport-weights", "qty": 4}),
        ],
    )


def cheap_lot(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    if state.day < 3 or state.cash < 800:
        return None
    return _msg(
        "Supplier offer: bargain blocks",
        "Supplier offer: Playnook can push a case of the bargain building blocks. The margin looks friendly. The durability notes are not.",
        "supplier",
        choices=[
            Choice(id="pass", label="Pass", effect="story", args={"text": "You left the case. The shelf stays cleaner."}),
            Choice(id="take", label="Take eight kits", effect="special_order", args={"product_id": "toy-blocks", "qty": 8}),
        ],
    )


def exclusive(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    if state.reputation_respectable < 46 or state.cash < 2800 or state.day < 8:
        return None
    return _msg(
        "Millthread exclusive",
        "Supplier offer: Millthread will cut the denim jacket as an exclusive if you take four now. The lead time does not get shorter.",
        "supplier",
        choices=[
            Choice(id="pass", label="Not this month", effect="story", args={"text": "You thanked Millthread and kept the cash."}),
            Choice(id="take", label="Take the exclusive four", effect="exclusive_run", args={"product_id": "cloth-jacket", "qty": 4}),
        ],
    )


def neighbor(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    sites = [site for site in state.sites if site.is_physical]
    if not sites:
        return None
    limit = max(site.neighbor_sensitivity for site in sites)
    if state.flags.neighbor_heat < limit:
        return None
    return _msg(
        "Neighbor note",
        (
            f"A neighbor left a message about the sign and the later crowd. Heat is {state.flags.neighbor_heat}. "
            f"This block starts to complain around {limit}."
        ),
        "neighbor",
        urgent=True,
        choices=[
            Choice(id="tone", label="Pull the tone back", effect="cool_down"),
            Choice(id="ignore", label="Thank them and change nothing", effect="ignore_neighbor"),
        ],
    )


def competitor(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    if state.flags.competitor < 20:
        return None
    return _msg(
        "Competitor",
        "Northline Market opened two blocks over. Foot traffic will feel it until your name is the one people repeat. A campaign or a better shelf is the reply.",
        "world",
    )


def burnout(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    tired = [
        person
        for person in state.staff
        if person.employed and person.burnout >= 64 and person.id not in report.quit_ids
    ]
    if not tired:
        return None
    person = max(tired, key=lambda member: member.burnout)
    return _msg(
        f"{person.name} is stretched",
        (
            f"Staff note: {person.name} is at burnout {person.burnout}. "
            "They will keep a shift. They will not keep many like the last one."
        ),
        "staff",
        choices=[
            Choice(id="off", label="Give them today off", effect="staff_rest", args={"staff_id": person.id}),
            Choice(id="work", label="Keep them on the sheet", effect="story", args={"text": f"{person.name} stays on. The number does not go down by itself."}),
        ],
    )


def following(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    faces = [person for person in state.staff if person.employed and person.following >= 28]
    if not faces:
        return None
    person = max(faces, key=lambda member: member.following)
    return _msg(
        f"{person.name}'s following",
        (
            f"Staff note: {person.name} is becoming a small local draw. Following is {person.following}. "
            "It helps the posts. It also means the camera is part of the job now, if they still want that."
        ),
        "staff",
    )


def stockout(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    if not report.stockout_ids:
        return None
    name = next(person.name for person in state.regulars if person.id == report.stockout_ids[0])
    return _msg(
        "Empty shelf",
        f"Customer flag: {name} left because the thing they came for was not in. Regulars do not argue. They just stop coming.",
        "customer",
    )


def praise(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    if state.review_score < 4.45 or report.units < 8 or report.returns:
        return None
    return _msg(
        "Reviews",
        f"Reviews are sitting at {state.review_score:.1f}. The notes mention being left alone when they wanted that, and helped when they asked.",
        "review",
    )


def slump(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    if state.review_score > 3.55 or report.returns < 1:
        return None
    return _msg(
        "Reviews slipped",
        (
            f"Reviews are {state.review_score:.1f} after {report.returns} returns. "
            "Cheap pieces that fail are louder than the good ones."
        ),
        "review",
    )


def payroll_watch(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    if is_late_week(state.day) and state.cash < _bills(state):
        return _msg(
            "Drawer check",
            (
                f"You have {money(state.cash)}. Sunday needs about {money(_bills(state))} for rent, wages, employer tax, insurance, and utilities. "
                "Supplier orders will not borrow from the credit line. Sunday will."
            ),
            "cash",
        )
    return None


def online_stuck(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    if report.missed_online < 4:
        return None
    return _msg(
        "Orders sat",
        f"Online note: {report.missed_online} orders never left. Packing was the bottleneck, not demand.",
        "online",
    )


def seasonal(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    rising = [
        product
        for product in state.products.values()
        if product.category == "seasonal" and product.trend == "rising" and state.stock[product.id].on_hand < 2
    ]
    if not rising:
        return None
    name = rising[0].name
    return _msg(
        "Seasonal window",
        f"The {name} is moving and the shelf is almost bare. Seasonal stock does not forgive a late reorder.",
        "stock",
    )


def label_pitch(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    if state.flags.private_label or state.day < 14:
        return None
    if state.cash < STABLE_MONTH_CASH:
        return None
    if max(state.reputation_respectable, state.reputation_nightlife) < 48:
        return None
    return _msg(
        "Private Label Co",
        f"Supplier offer: Private Label Co will run Aisle House flour, paper towels, and dish soap. Setup is {money(LABEL_SETUP_COST)}. The minimums after that are real.",
        "supplier",
        choices=[
            Choice(id="wait", label="Not yet", effect="story", args={"text": "You kept the setup money in the drawer."}),
            Choice(id="pay", label="Pay the setup", effect="unlock_label"),
        ],
    )


def influencer(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    if state.reputation_nightlife < 55 or state.cash < 1200 or state.campaign is not None:
        return None
    return _msg(
        "A collab ask",
        "Someone with a local following wants a paid post. Bold will travel. It may also get the ad rejected, and the fee does not come back.",
        "marketing",
    )


def platform(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    if state.flags.platform_trust >= 52:
        return None
    return _msg(
        "Platform rules",
        f"The ad account is on a shorter leash. Trust is {state.flags.platform_trust}. Discreet and playful still run. Bold is a coin toss you pay for either way.",
        "marketing",
    )


def jordan_cabinet(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    if report.assigned.get("jordan") != "floor":
        return None
    return _msg(
        "Frozen wall",
        "Staff note: Jordan restocked the frozen wall and moved the cold-chain delivery into the case before it could thaw.",
        "staff",
    )


def naomi_night(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    if not _employed(state, "naomi") or state.reputation_nightlife < 42 or report.event_blurb:
        return None
    if not any(site.is_physical for site in state.sites):
        return None
    return _msg(
        "Naomi",
        "Staff note: Naomi says a small department demo would move the electronics wall. She will host if the rules are posted. She will not work a pharmacy rush alone.",
        "staff",
    )


def casey_talk(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    casey = _regular(state, "casey")
    if casey is None or not casey.introduced or casey.loyalty < 62 or "casey" not in report.buyer_ids:
        return None
    return _msg(
        "Casey Nguyen",
        "Customer note: Casey bought a household pack and said two friends asked where it came from. Word of mouth is doing a shift you did not schedule.",
        "customer",
    )


def vincent_gap(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    if "vincent" not in report.stockout_ids:
        return None
    return _msg(
        "Vincent Shaw",
        "Customer flag: Vincent came for a work shirt, found the rack thin, and left without a conversation.",
        "customer",
    )


def thea(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    person = _regular(state, "thea")
    if person is None or person.introduced or state.day < 4:
        return None
    seasonal_units = report.by_category.get("seasonal", 0)
    if seasonal_units < 40:
        return None
    return _msg(
        "Thea Morgan",
        "Customer note: Thea follows the seasonal window. She noticed this one. She will not notice the next one if it looks the same.",
        "customer",
        choices=[
            Choice(
                id="yes",
                label="Treat her like a regular",
                effect="introduce",
                args={"customer_id": "thea", "loyalty": 7, "text": "Thea is on the list. She buys what the window changes to."},
            ),
            Choice(id="no", label="Let the window do the work", effect="story", args={"text": "You left Thea as foot traffic."}),
        ],
    )


def billie(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    if not report.incident:
        return None
    person = _regular(state, "billie")
    if person is None or person.introduced:
        return None
    return _msg(
        "Billie Frost",
        "Customer flag: Billie treats staff like friends and treats a missing rule like a suggestion. They were in the room tonight.",
        "customer",
        choices=[
            Choice(
                id="limits",
                label="They can shop. Events are closed to them.",
                effect="introduce",
                args={"customer_id": "billie", "loyalty": 2, "text": "Billie can buy on the floor. The next night list does not have their name."},
            ),
            Choice(id="out", label="Do not encourage the friendship", effect="story", args={"text": "You left Billie off the list."}),
        ],
    )


def chris_bench(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    if report.assigned.get("chris") != "fulfillment" or report.online_orders < 3:
        return None
    return _msg(
        "Packing table",
        f"Staff note: Chris shipped {report.online_orders} orders and wrote the blunt ones himself. He asked that the site not promise same-day.",
        "staff",
    )


def marisol_mail(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    if report.assigned.get("marisol") not in ("floor", "fulfillment"):
        return None
    if report.online_orders < 2 and state.mode != "online":
        return None
    return _msg(
        "Marisol",
        "Staff note: Marisol answered the careful emails and flagged one that was pushing for a manager override without a receipt. She told them the store does not do that.",
        "staff",
    )


def velvet_sit(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    product = state.products.get("season-picnic")
    if product is None or product.trend != "fading":
        return None
    line = state.stock["season-picnic"]
    if line.on_hand < 3 or report.units_by_product.get("season-picnic", 0) > 0:
        return None
    return _msg(
        "Picnic set",
        f"The picnic set is fading and {line.on_hand} are still on the rack at {money(product.price)}. A markdown is a decision. So is letting it sit.",
        "stock",
    )


def alyssa_shift(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    if report.assigned.get("alyssa") != "floor" or not _employed(state, "alyssa"):
        return None
    if report.units < 4:
        return None
    return _msg(
        "Alyssa on the floor",
        "Staff note: Alyssa sold the floor without a weekly-ad photo today. She said the seasonal endcap still gets touched every hour, posted or not.",
        "staff",
    )


def dean_offer(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    dean = next((person for person in state.staff if person.id == "dean"), None)
    if dean is None or dean.employed or state.day < 10 or state.cash < 4000:
        return None
    return _msg(
        "Dean Okonkwo",
        f"A floor lead with twelve years in retail will come in for {money(dean.wage)} a week. He will not host after hours. He will notice a sloppy sheet.",
        "staff",
    )


def return_spike(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    if report.returns < 2:
        return None
    return _msg(
        "Returns",
        (
            f"Customer flag: {report.returns} returns today, {money(report.refunds)} back out of the drawer. "
            "Check the quality on what you reordered. The bargain kit is the usual suspect."
        ),
        "review",
    )


def priya_floor(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    if report.assigned.get("priya") != "floor":
        return None
    return _msg(
        "Priya",
        "Staff note: Priya walked a couple through the playful wall without rushing them. She still will not take a private booking. She was clear, and they stayed.",
        "staff",
    )


def evan_late(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    if "evan" not in report.noshow_ids:
        return None
    return _msg(
        "Evan",
        "Staff note: Evan missed the shift. He is willing when he is in the building. Willingness does not open the door.",
        "staff",
    )


def is_late_week(day: int) -> bool:
    return (day - 1) % 7 in (3, 4, 5)


def _bills(state: GameState) -> int:
    return weekly_obligations(state)


def dead_stock(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    stale = []
    for product in state.products.values():
        line = state.stock[product.id]
        if line.on_hand >= 4 and line.age_days > 24:
            stale.append((product, line))
    if not stale:
        return None
    product, line = max(stale, key=lambda item: item[1].age_days)
    return _msg(
        f"{product.name} is sitting",
        (
            f"Inventory note: {product.name} has been on the shelf {line.age_days} days, "
            f"{line.on_hand} still here, {money(product.cost * line.on_hand)} at cost. "
            "Past three weeks, people start walking past it."
        ),
        "inventory",
        choices=[
            Choice(
                id="watch",
                label="Leave the price and watch it",
                effect="story",
                args={"text": f"You left {product.name} at {money(product.price)}. It still has to move."},
            ),
            Choice(
                id="mark",
                label="Mark it down about ten percent",
                effect="markdown",
                args={"product_id": product.id},
            ),
        ],
    )


def payable_due(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    soon = [
        account
        for account in state.supplier_accounts
        if account.payable > 0 and 0 <= account.due_day - state.day <= 4
    ]
    if not soon:
        return None
    account = min(soon, key=lambda item: item.due_day)
    supplier = SUPPLIERS.get(account.supplier_id)
    name = supplier.name if supplier else account.supplier_id
    return _msg(
        f"{name} is due",
        (
            f"Books note: {money(account.payable)} to {name} is due day {account.due_day}. "
            "Terms are cash on that day. The credit line does not cover a supplier."
        ),
        "cash",
        choices=[
            Choice(
                id="noted",
                label="Leave it on the books",
                effect="story",
                args={"text": f"{name} stays on the payable list. Pay it from the drawer when it comes due."},
            ),
        ],
    )


def quarter_result(state: GameState, report: DayReport, rng) -> InboxMessage | None:
    if not state.months or state.months[-1].day != state.day:
        return None
    statement = state.months[-1]
    return _msg(
        "Quarter close",
        (
            f"Books note: sales {money(statement.sales)}, refunds {money(statement.refunds)}, "
            f"cost of goods {money(statement.cogs)}, operating {money(statement.operating)}, "
            f"depreciation {money(statement.depreciation)}. Net {money(statement.net)}. "
            f"Drawer {money(statement.cash)}. Inventory {money(statement.inventory)}."
        ),
        "cash",
        choices=[
            Choice(
                id="file",
                label="File it and start the next quarter",
                effect="story",
                args={"text": "The quarter is on the books. The next one starts with an empty tape."},
            ),
        ],
    )


# weight, cooldown days, builder. Weight >= 8 is forced onto the morning sheet.
BUILDERS: list[tuple[str, int, int, object]] = [
    ("red_set", 8, 6, red_set),
    ("mark_fitting", 10, 18, mark_fitting),
    ("ellen_thanks", 3, 8, ellen_thanks),
    ("ruthie", 7, 30, ruthie),
    ("irene", 6, 30, irene),
    ("harper", 6, 20, harper),
    ("couples", 7, 16, couples),
    ("weighted_offer", 5, 12, weighted_offer),
    ("cheap_lot", 5, 14, cheap_lot),
    ("exclusive", 6, 16, exclusive),
    ("neighbor", 10, 8, neighbor),
    ("competitor", 9, 40, competitor),
    ("burnout", 8, 5, burnout),
    ("following", 4, 10, following),
    ("stockout", 8, 4, stockout),
    ("praise", 3, 8, praise),
    ("slump", 8, 6, slump),
    ("payroll_watch", 9, 6, payroll_watch),
    ("online_stuck", 8, 4, online_stuck),
    ("seasonal", 5, 7, seasonal),
    ("label_pitch", 6, 12, label_pitch),
    ("influencer", 4, 12, influencer),
    ("platform", 7, 8, platform),
    ("jordan_cabinet", 2, 7, jordan_cabinet),
    ("naomi_night", 3, 10, naomi_night),
    ("casey_talk", 3, 10, casey_talk),
    ("vincent_gap", 6, 8, vincent_gap),
    ("thea", 4, 20, thea),
    ("billie", 7, 20, billie),
    ("chris_bench", 2, 6, chris_bench),
    ("marisol_mail", 2, 6, marisol_mail),
    ("velvet_sit", 4, 8, velvet_sit),
    ("alyssa_shift", 2, 6, alyssa_shift),
    ("dean_offer", 3, 14, dean_offer),
    ("return_spike", 8, 5, return_spike),
    ("priya_floor", 2, 8, priya_floor),
    ("evan_late", 5, 6, evan_late),
    ("dead_stock", 5, 8, dead_stock),
    ("payable_due", 6, 5, payable_due),
    ("quarter_result", 6, 20, quarter_result),
]
