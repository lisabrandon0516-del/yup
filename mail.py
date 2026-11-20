"""Letters the player can send from the desk.

A store manager can set the door's hours. A vendor can send the truck when the
minimum is met and the drawer can pay. A note on a lead's file moves mood. A
thank-you moves a regular's loyalty. A letter does not change a price, a wage,
or a vendor's cost.
"""

from __future__ import annotations

from dataclasses import dataclass

from open_late.books import TERMS_RELATIONSHIP, quarter_net
from open_late.content import SUPPLIERS
from open_late.corporate import deal_for
from open_late.departments import DEPARTMENT_LABELS
from open_late.models import GameState, MailLetter, Regular, Staff, SupplierAccount
from open_late.text import money

DAILY_CAP = 12
MAIL_CAP = 80

_LEAD_TITLES = {
    "dean": "Store lead",
    "marisol": "Office lead",
    "chris": "Shipping lead",
    "alyssa": "Front-end lead",
    "jordan": "Closing lead",
    "priya": "Service lead",
    "naomi": "Events lead",
    "evan": "Floor supervisor",
}

_ASSIGN = {
    "floor": "On the floor",
    "fulfillment": "Packing",
    "modeling": "On the photo",
    "private": "Appointment desk",
    "event": "Hosting",
    "training": "Training",
    "off": "Off the schedule",
}


@dataclass(frozen=True)
class MailContact:
    id: str
    name: str
    group: str
    title: str
    detail: str


@dataclass(frozen=True)
class MailTopic:
    id: str
    label: str


_MANAGER_TOPICS = (
    MailTopic("floor", "How is the floor?"),
    MailTopic("hours", "What are the hours?"),
    MailTopic("set_hours", "Set the hours"),
    MailTopic("empty", "Which aisle is empty?"),
    MailTopic("file", "A note for your file"),
)
_VENDOR_TOPICS = (
    MailTopic("terms", "Lead time and the minimum"),
    MailTopic("bill", "The open bill"),
    MailTopic("truck", "Where is my truck?"),
    MailTopic("send", "Send the truck"),
    MailTopic("cost", "Can you come off the sheet?"),
)
_BOOK_TOPICS = (
    MailTopic("cash", "Where does the cash stand?"),
    MailTopic("bills", "Which vendors do we owe?"),
)
_LANDLORD_TOPICS = (
    MailTopic("rent", "What is the rent this week?"),
    MailTopic("lease", "Which doors are open?"),
)
_RIVAL_TOPICS = (
    MailTopic("block", "How are you priced?"),
    MailTopic("move", "What should I be watching?"),
)
_REGULAR_TOPICS = (
    MailTopic("thanks", "Thank you for shopping with us"),
    MailTopic("visit", "When were you last in?"),
)


def contacts(state: GameState) -> list[MailContact]:
    """Store managers, floor leads, merchandise vendors, and the house."""
    people: list[MailContact] = []
    doors = {door.id: door for door in state.doors}
    for manager in state.managers:
        door = doors.get(manager.door_id)
        if not manager.employed:
            detail = "Not on the payroll"
        elif door is None:
            detail = "On the payroll, no store"
        else:
            detail = f"{door.city} · {door.status}"
        people.append(MailContact(
            id=f"mgr:{manager.id}",
            name=manager.name,
            group="Managers",
            title="Store manager",
            detail=detail,
        ))
    for person in state.staff:
        title = _LEAD_TITLES.get(person.id, "Floor lead")
        if not person.employed:
            detail = "Not on the payroll"
        else:
            where = _ASSIGN.get(person.assignment, person.assignment)
            door = doors.get(person.door_id)
            detail = f"{where} · {door.city}" if door is not None else where
        people.append(MailContact(
            id=f"staff:{person.id}",
            name=person.name,
            group="Managers",
            title=title,
            detail=detail,
        ))
    private = bool(getattr(getattr(state, "flags", None), "private_label", False))
    for supplier in SUPPLIERS.values():
        if supplier.id == "labelco" and not private:
            continue
        account = _account(state, supplier.id)
        standing = f"Relationship {account.relationship}" if account is not None else "No account yet"
        people.append(MailContact(
            id=f"vendor:{supplier.id}",
            name=supplier.name,
            group="Vendors",
            title="Merchandise vendor",
            detail=f"{supplier.lead_time_days}-day lead · min {money(supplier.minimum_order)} · {standing}",
        ))
    people.append(MailContact(
        id="house:books",
        name="The bookkeeper",
        group="The house",
        title="Accounting",
        detail="Cash, the quarter, and the open bills",
    ))
    people.append(MailContact(
        id="house:landlord",
        name="The landlord",
        group="The house",
        title="Leases",
        detail="Rent on the sites and the doors",
    ))
    people.append(MailContact(
        id="house:rival",
        name=state.rival.name,
        group="The house",
        title="Down the block",
        detail=state.rival.note,
    ))
    for regular in state.regulars:
        if not regular.introduced:
            continue
        people.append(MailContact(
            id=f"regular:{regular.id}",
            name=regular.name,
            group="The house",
            title="Regular",
            detail=regular.blurb,
        ))
    return people


def topics_for(contact: MailContact) -> list[MailTopic]:
    kind = contact.id.split(":", 1)[0]
    if kind in ("mgr", "staff"):
        return list(_MANAGER_TOPICS)
    if kind == "vendor":
        return list(_VENDOR_TOPICS)
    if contact.id == "house:books":
        return list(_BOOK_TOPICS)
    if contact.id == "house:landlord":
        return list(_LANDLORD_TOPICS)
    if contact.id == "house:rival":
        return list(_RIVAL_TOPICS)
    if kind == "regular":
        return list(_REGULAR_TOPICS)
    return []


def send_letter(state: GameState, to_id: str, topic_id: str, body: str) -> tuple[bool, str]:
    """File a letter and the reply. False means nothing was stored."""
    contact = next((person for person in contacts(state) if person.id == to_id), None)
    if contact is None:
        return False, "That name is not on the desk."
    topic = next((item for item in topics_for(contact) if item.id == topic_id), None)
    if topic is None:
        return False, "Pick what the letter is about."
    today = [letter for letter in state.sent_mail if letter.day == state.day]
    if len(today) >= DAILY_CAP:
        return False, f"{DAILY_CAP} letters is the desk for today."
    if any(letter.to_id == to_id and letter.subject == topic.label for letter in today):
        return False, "You already wrote them about that today. The reply is in Sent."
    note = " ".join((body or "").split())[:400]
    reply = _reply(state, contact, topic.id, note)
    if note:
        reply = f"Your note: {note[:160]}. {reply}"
    _apply(state, contact, topic.id)
    letter = MailLetter(
        id=f"l{state.next_message_id}",
        day=state.day,
        to_id=contact.id,
        to_name=contact.name,
        role=contact.group,
        subject=topic.label,
        body=note,
        reply_from=contact.name,
        reply=reply,
    )
    state.next_message_id += 1
    state.sent_mail.append(letter)
    if len(state.sent_mail) > MAIL_CAP:
        state.sent_mail = state.sent_mail[-MAIL_CAP:]
    state.actions_today.append(f"Wrote {contact.name}.")
    return True, reply


def _apply(state: GameState, contact: MailContact, topic_id: str) -> None:
    if topic_id == "file" and contact.id.startswith("staff:"):
        person = _staff(state, contact.id.split(":", 1)[1])
        if person is not None and person.employed:
            person.mood = min(96, int(person.mood) + 2)
            person.loyalty = min(100, int(person.loyalty) + 1)
    if topic_id == "thanks" and contact.id.startswith("regular:"):
        regular = _regular(state, contact.id.split(":", 1)[1])
        if regular is not None and regular.active:
            regular.loyalty = min(100, int(regular.loyalty) + 1)


def _reply(state: GameState, contact: MailContact, topic_id: str, body: str = "") -> str:
    kind, key = contact.id.split(":", 1)
    if kind == "mgr":
        return _manager_reply(state, key, topic_id, body)
    if kind == "staff":
        return _staff_reply(state, key, topic_id)
    if kind == "vendor":
        return _vendor_reply(state, key, topic_id)
    if contact.id == "house:books":
        return _books_reply(state, topic_id)
    if contact.id == "house:landlord":
        return _landlord_reply(state, topic_id)
    if contact.id == "house:rival":
        return _rival_reply(state, topic_id)
    if kind == "regular":
        return _regular_reply(state, key, topic_id)
    return "The desk has no answer for that."


def _manager_reply(state: GameState, manager_id: str, topic_id: str, body: str = "") -> str:
    manager = next((person for person in state.managers if person.id == manager_id), None)
    if manager is None:
        return "That manager is not on the sheet."
    if not manager.employed:
        return f"{manager.name} is not on the payroll, so the floor will not answer."
    door = next((item for item in state.doors if item.id == manager.door_id), None)
    if door is None:
        return f"{manager.name} is on the payroll and is not assigned to a store."
    if topic_id == "hours":
        return (
            f"{door.city} is posted {door.open_hour}:00 to {door.close_hour}:00. "
            f"The door is {door.status}."
        )
    if topic_id == "set_hours":
        return _set_posted_hours(state, door, body)
    if topic_id == "empty":
        return _empty_line(state, f"the chain, which is what {door.city} is measured against")
    if topic_id == "file":
        return (
            f"Filed. {manager.name} is running {door.city}. "
            f"A letter does not change the wage or the schedule."
        )
    sales = money(door.last_sales) if door.last_sales else "no sales day yet"
    return (
        f"{door.city} last posted {sales}. Planogram compliance is {door.compliance}. "
        f"Hours {door.open_hour}:00 to {door.close_hour}:00."
    )


def _staff_reply(state: GameState, staff_id: str, topic_id: str) -> str:
    person = _staff(state, staff_id)
    if person is None:
        return "That lead is not on the sheet."
    if not person.employed:
        return f"{person.name} is not on the payroll."
    if topic_id == "hours":
        return _hours_line(state, person)
    if topic_id == "empty":
        return _empty_line(state, "the last close")
    if topic_id == "file":
        return (
            f"Filed on {person.name}. Mood is {person.mood} and loyalty is {person.loyalty}. "
            f"The wage stays {money(person.wage)}."
        )
    report = state.last_report
    if not report.day:
        return f"{person.name} is {_ASSIGN.get(person.assignment, person.assignment).lower()}. No day has closed yet."
    return (
        f"Day {report.day}: {report.visits} people, {report.units} units. "
        f"Turned away {report.lost_stockout} empty shelf, {report.lost_price} price, {report.lost_staff} short staff. "
        f"{person.name} is {_ASSIGN.get(person.assignment, person.assignment).lower()}."
    )


def _hours_line(state: GameState, person: Staff) -> str:
    door = next((item for item in state.doors if item.id == person.door_id), None)
    if door is not None:
        span = f"{door.city} is posted {door.open_hour}:00 to {door.close_hour}:00"
    else:
        span = f"The shop is posted {state.open_hour}:00 to {state.close_hour}:00"
    working = [
        member.name
        for member in state.staff
        if member.employed and member.assignment != "off"
    ]
    names = ", ".join(working[:8]) or "no one"
    return (
        f"{span}. {person.name} is {_ASSIGN.get(person.assignment, person.assignment).lower()}. "
        f"On the clock: {names}."
    )


def _empty_line(state: GameState, scope: str) -> str:
    report = state.last_report
    if not report.day:
        return "No day has closed yet, so there is no empty-shelf count."
    lost = report.lost_stockout_by_category or {}
    if not lost:
        return f"No department was empty at {scope}."
    parts = []
    for key, count in sorted(lost.items(), key=lambda item: -int(item[1])):
        if int(count) <= 0:
            continue
        label = DEPARTMENT_LABELS.get(key, key.replace("_", " ").title())
        parts.append(f"{label} {int(count)}")
    if not parts:
        return f"No department was empty at {scope}."
    return f"Empty shelf at {scope}: " + ", ".join(parts) + "."


def _vendor_reply(state: GameState, supplier_id: str, topic_id: str) -> str:
    supplier = SUPPLIERS.get(supplier_id)
    if supplier is None:
        return "That vendor is not on the sheet."
    account = _account(state, supplier_id)
    if topic_id == "terms":
        labels = [DEPARTMENT_LABELS.get(key, key) for key in supplier.categories]
        return (
            f"{supplier.name} leads in {supplier.lead_time_days} days. "
            f"The minimum is {money(supplier.minimum_order)}. "
            f"Lines: {', '.join(labels)}. {supplier.blurb}"
        )
    if topic_id == "bill":
        if account is None or account.payable <= 0:
            terms = account.terms if account is not None else "cash"
            return f"Nothing is open with {supplier.name}. Terms are {terms}."
        return (
            f"{supplier.name} is owed {money(account.payable)}, due day {account.due_day}. "
            f"Late payments: {account.late_payments}. Terms are {account.terms}."
        )
    if topic_id == "truck":
        return _truck_line(state, supplier_id, supplier.name)
    if topic_id == "send":
        return _send_truck(state, supplier_id, supplier.name)
    return _cost_line(state, supplier_id, supplier.name, account)


def _set_posted_hours(state: GameState, door, body: str) -> str:
    import re

    from open_late.corporate import set_door_hours

    numbers = [int(item) for item in re.findall(r"\d{1,2}", body or "")]
    if len(numbers) < 2:
        return (
            f"Write the hours in the letter, like 8 to 21. "
            f"{door.city} stays {door.open_hour}:00 to {door.close_hour}:00."
        )
    before = (door.open_hour, door.close_hour)
    result = set_door_hours(state, door.id, numbers[0], numbers[1])
    if (door.open_hour, door.close_hour) == before and "Posted hours" not in result:
        return f"{result} {door.city} stays {door.open_hour}:00 to {door.close_hour}:00."
    return result


def _send_truck(state: GameState, supplier_id: str, name: str) -> str:
    from open_late.engine import place_order, suggested_restock_quantities

    quantities = suggested_restock_quantities(state, supplier_id)
    if not quantities:
        return f"Nothing from {name} needs a truck. The shelf covers the modest restock."
    before = len(state.orders)
    message = place_order(state, supplier_id, quantities)
    if len(state.orders) == before:
        return message
    due = state.orders[-1].arrives_on
    return f"{message} Due day {due}."


def _truck_line(state: GameState, supplier_id: str, name: str) -> str:
    coming = [
        order for order in state.orders
        if order.supplier_id == supplier_id and order.arrives_on >= state.day
    ]
    if not coming:
        return f"Nothing from {name} is on the road."
    bits = []
    for order in coming[:4]:
        units = sum(int(qty) for qty in order.lines.values())
        wait = order.arrives_on - state.day
        when = "today" if wait <= 0 else f"day {order.arrives_on}"
        bits.append(f"{order.id.upper()} {units} units, arrives {when}, goods {money(order.cost)}")
    return f"On the road from {name}: " + "; ".join(bits) + "."


def _cost_line(state: GameState, supplier_id: str, name: str, account: SupplierAccount | None) -> str:
    deal = deal_for(state, supplier_id)
    if deal is not None and deal.cost_off_percent:
        return (
            f"The {deal.tier} deal with {name} is already {deal.cost_off_percent}% under the sheet. "
            f"This letter does not move it."
        )
    relationship = account.relationship if account is not None else 0
    if relationship >= TERMS_RELATIONSHIP:
        return (
            f"Relationship with {name} is {relationship}. Net 14 is open. "
            f"A house deal is signed on the vendor card. This letter does not change the cost."
        )
    return (
        f"Relationship with {name} is {relationship}. "
        f"The list price holds until relationship reaches {TERMS_RELATIONSHIP}. "
        f"This letter does not change the cost."
    )


def _books_reply(state: GameState, topic_id: str) -> str:
    if topic_id == "bills":
        owed = [account for account in state.supplier_accounts if account.payable > 0]
        if not owed:
            return "No vendor bill is open."
        bits = []
        for account in owed[:6]:
            supplier = SUPPLIERS.get(account.supplier_id)
            label = supplier.name if supplier is not None else account.supplier_id
            bits.append(f"{label} {money(account.payable)} due day {account.due_day}")
        return "Open bills: " + "; ".join(bits) + "."
    net = quarter_net(state)
    return (
        f"Cash is {money(state.cash)}. This quarter's net is {money(net)}. "
        f"Sales tax held is {money(state.tax_held)}."
    )


def _landlord_reply(state: GameState, topic_id: str) -> str:
    rows: list[str] = []
    for site in state.sites:
        kind = "warehouse" if site.is_warehouse else "site"
        rows.append(f"{site.label} ({kind}) {money(site.rent_weekly)} a week")
    for door in state.doors:
        if door.rent_weekly:
            rows.append(f"{door.city} {money(door.rent_weekly)} a week, {door.status}")
    if not rows:
        return "No lease is on the books."
    if topic_id == "lease":
        return "On the books: " + "; ".join(rows) + "."
    return "Rent this week: " + "; ".join(rows) + "."


def _rival_reply(state: GameState, topic_id: str) -> str:
    rival = state.rival
    public = (
        f"{rival.name} prices at {rival.price_index}, against 100 on your shelf. "
        f"They are {rival.blocks_away} blocks away. {rival.note}"
    )
    if topic_id == "block":
        return public
    try:
        from open_late.rival_ai import rival_snapshot
    except Exception:
        return public
    snap = rival_snapshot(state)
    chains = snap.get("chains") or []
    if not snap.get("enabled") or not chains:
        return public + " No other chain has posted a public price index."
    bits = [
        f"{chain['name']} at {chain['price_index']}, {chain['open_stores']} open"
        for chain in chains[:3]
    ]
    return public + " Public chain indexes: " + "; ".join(bits) + "."


def _regular_reply(state: GameState, regular_id: str, topic_id: str) -> str:
    regular = _regular(state, regular_id)
    if regular is None:
        return "That regular is not in the book."
    if topic_id == "thanks":
        return (
            f"{regular.name} has loyalty {regular.loyalty}. "
            f"Spend on the card is {money(regular.spend)}. A thank-you does not change what they buy tomorrow."
        )
    last = f"day {regular.last_visit}" if regular.last_visit else "not yet"
    likes = ", ".join(DEPARTMENT_LABELS.get(key, key) for key in regular.preferences) or "no department named"
    return (
        f"{regular.name} last came in {last}, across {regular.visits} visits. "
        f"They ask for {likes}. {regular.blurb}"
    )


def _account(state: GameState, supplier_id: str) -> SupplierAccount | None:
    return next((item for item in state.supplier_accounts if item.supplier_id == supplier_id), None)


def _staff(state: GameState, staff_id: str) -> Staff | None:
    return next((person for person in state.staff if person.id == staff_id), None)


def _regular(state: GameState, regular_id: str) -> Regular | None:
    return next((person for person in state.regulars if person.id == regular_id), None)
