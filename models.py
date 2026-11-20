"""Saveable game state. Dollars are whole numbers."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, PrivateAttr, model_serializer, model_validator

from open_late.shopperlife.models import ShopperLifeBlock

Assignment = Literal["floor", "fulfillment", "modeling", "private", "event", "training", "off"]
Tone = Literal["discreet", "playful", "bold"]
Policy = Literal["keep_light", "balanced", "lean_in"]
Mode = Literal["shop", "online", "corporate"]


class Product(BaseModel):
    id: str
    name: str
    category: str
    quality: int = Field(ge=1, le=5)
    cost: int = Field(ge=1)
    price: int = Field(ge=1)
    trend: Literal["rising", "steady", "fading"] = "steady"
    supplier_id: str
    brand: str = ""
    intensity: int = Field(default=0, ge=0, le=3)
    exclusive: bool = False
    blurb: str = ""
    department: str = ""
    shelf_life_days: int = 0
    case_size: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def _default_department(self):
        if not self.department:
            from open_late.departments import default_department

            self.department = default_department(self.category)
        return self


class StockLine(BaseModel):
    product_id: str
    on_hand: int = 0
    on_order: int = 0
    age_days: int = 0
    sizes: dict[str, int] = Field(default_factory=dict)


class Supplier(BaseModel):
    id: str
    name: str
    lead_time_days: int
    minimum_order: int
    exclusive_ok: bool
    categories: list[str]
    blurb: str
    price_tier: str = ""
    brands: list[str] = Field(default_factory=list)


class Staff(BaseModel):
    id: str
    name: str
    short: str
    product_knowledge: int
    comfort_modeling: int
    personality: Literal["warm", "blunt", "playful", "discreet"]
    boundaries: list[str] = Field(default_factory=list)
    reliability: int
    aptitude_floor: int
    aptitude_fulfillment: int
    aptitude_events: int
    wage: int
    wage_ask: int = 0
    ytd_gross: int = 0
    ytd_federal: int = 0
    ytd_social: int = 0
    ytd_medicare: int = 0
    ytd_state: int = 0
    ytd_county: int = 0
    ytd_net: int = 0
    mood: int = 72
    burnout: int = 8
    loyalty: int = 60
    following: int = 0
    sales_attributed: int = 0
    review_due: int = 28
    employed: bool = False
    assignment: Assignment = "off"
    door_id: str = ""


class Regular(BaseModel):
    id: str
    name: str
    blurb: str
    preferences: list[str]
    discretion: int
    loyalty: int
    pushiness: int
    spend: int = 0
    active: bool = True
    introduced: bool = False
    visits: int = 0
    last_visit: int = 0
    banned_private: bool = False


class SupplierAccount(BaseModel):
    supplier_id: str
    relationship: int = 42
    terms: Literal["cash", "net14", "net30"] = "cash"
    volume: int = 0
    payable: int = 0
    due_day: int = 0
    late_payments: int = 0


class Rival(BaseModel):
    name: str = "Northline Market"
    price_index: int = 102
    reputation: int = 38
    blocks_away: int = 8
    focus: str = "grocery"
    note: str = "A polite shop several blocks off. Not in your traffic yet."


class Target(BaseModel):
    id: str
    label: str
    metric: str
    goal: int
    due_day: int
    met: bool = False
    closed: bool = False


class MonthClose(BaseModel):
    day: int
    sales: int
    cogs: int
    refunds: int
    gross_profit: int
    operating: int
    tax: int
    depreciation: int
    income_tax: int = 0
    net: int
    cash: int
    inventory: int
    note: str


class LedgerLine(BaseModel):
    day: int
    kind: str
    amount: int
    note: str


class Site(BaseModel):
    id: str
    label: str
    rent_weekly: int
    foot_traffic: int
    neighbor_sensitivity: int
    allows_intense: bool = True
    is_physical: bool = True
    is_warehouse: bool = False


class PurchaseOrder(BaseModel):
    id: str
    supplier_id: str
    lines: dict[str, int]
    arrives_on: int
    cost: int
    placed_on: int
    freight: int = 0


class Campaign(BaseModel):
    kind: Literal["social", "email", "local_ad", "influencer"]
    tone: Tone
    days_left: int
    category: str
    staff_id: str | None = None
    traffic_mult: float = 1.1
    respect: int = 0
    night: int = 0
    door_id: str = ""


class EventPlan(BaseModel):
    kind: Literal["try_on", "demo", "couples"]
    host_id: str
    strict_rules: bool
    category: str


class Choice(BaseModel):
    id: str
    label: str
    effect: str
    args: dict[str, int | str | bool] = Field(default_factory=dict)


class InboxMessage(BaseModel):
    id: str
    day: int
    kind: str
    title: str
    body: str
    urgent: bool = False
    choices: list[Choice] = Field(default_factory=list)
    resolved: bool = False
    resolution: str = ""


class DayReport(BaseModel):
    day: int = 0
    weekday: str = ""
    revenue: int = 0
    refunds: int = 0
    cogs: int = 0
    units: int = 0
    visits: int = 0
    online_orders: int = 0
    missed_online: int = 0
    returns: int = 0
    by_category: dict[str, int] = Field(default_factory=dict)
    units_by_product: dict[str, int] = Field(default_factory=dict)
    top_sellers: list[str] = Field(default_factory=list)
    staff_lines: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    rent_paid: int = 0
    payroll_paid: int = 0
    interest_paid: int = 0
    shortfall: int = 0
    shipping: int = 0
    event_revenue: int = 0
    event_blurb: str = ""
    event_host_id: str = ""
    purchases: int = 0
    incident: bool = False
    quit_ids: list[str] = Field(default_factory=list)
    noshow_ids: list[str] = Field(default_factory=list)
    assigned: dict[str, str] = Field(default_factory=dict)
    stockout_ids: list[str] = Field(default_factory=list)
    buyer_ids: list[str] = Field(default_factory=list)
    milestone_notes: list[str] = Field(default_factory=list)
    lost_stockout: int = 0
    lost_stockout_by_category: dict[str, int] = Field(default_factory=dict)
    lost_price: int = 0
    lost_price_by_product: dict[str, int] = Field(default_factory=dict)
    lost_staff: int = 0
    lost_walk: int = 0
    lost_size: int = 0
    spoilage_units: int = 0
    spoilage_cost: int = 0
    expiry_markdown: int = 0
    shrink_units: int = 0
    shrink_cost: int = 0
    damage_units: int = 0
    damage_cost: int = 0
    tax_collected: int = 0
    tax_remitted: int = 0
    card_fees: int = 0
    insurance_paid: int = 0
    utilities_paid: int = 0
    payroll_tax_paid: int = 0
    income_tax_paid: int = 0
    depreciation: int = 0
    capacity: int = 0
    cash_end: int = 0
    cash_open: int = 0
    trade_visits: int = 0
    payables_paid: int = 0
    tax_refunded: int = 0
    credit_open: int = 0
    credit_drawn: int = 0
    gross_profit: int = 0
    license_paid: int = 0
    loan_principal_paid: int = 0
    merchandise_paid: int = 0
    freight_paid: int = 0
    variance_paid: int = 0
    advertising_paid: int = 0
    severance_paid: int = 0
    draws_paid: int = 0
    debt_paid: int = 0
    fixtures_paid: int = 0
    period_paid: int = 0
    planogram_labor: int = 0
    labor_hours: int = 0
    labor_overtime: int = 0
    on_road: int = 0


class StoreManager(BaseModel):
    id: str
    name: str
    short: str
    operations: int = Field(ge=1, le=100)
    merchandising: int = Field(ge=1, le=100)
    leadership: int = Field(ge=1, le=100)
    local_sense: int = Field(ge=1, le=100)
    wage: int
    employed: bool = False
    door_id: str = ""


class VendorDeal(BaseModel):
    supplier_id: str
    tier: Literal["volume", "partner"]
    cost_off_percent: int = 0
    terms: Literal["cash", "net14", "net30"] = "cash"
    coop_percent: int = 0
    coop_accrued: int = 0


class SalesDay(BaseModel):
    day: int
    units: dict[str, int] = Field(default_factory=dict)


class Shipment(BaseModel):
    id: str
    door_id: str
    lines: dict[str, int]
    departs_on: int
    arrives_on: int
    freight: int
    transit_days: int


class Door(BaseModel):
    id: str
    city: str
    state_name: str
    region: str
    blurb: str = ""
    manager_id: str = ""
    stock: dict[str, StockLine] = Field(default_factory=dict)
    open_hour: int = 11
    close_hour: int = 19
    posted_open: int = 11
    posted_close: int = 19
    planogram: dict[str, int] = Field(default_factory=dict)
    planogram_days: int = 0
    compliance: int = 40
    sales_tax_bps: int = 700
    state_tax_per_ten_thousand: int = 295
    county_tax_per_ten_thousand: int = 125
    wage_floor: int = 290
    freight_per_unit: int = 2
    fair_workweek: bool = False
    allows_intense: bool = True
    foot_traffic: int = 18
    neighbor_sensitivity: int = 40
    demand: dict[str, int] = Field(default_factory=dict)
    rent_weekly: int = 0
    last_sales: int = 0
    predictability_due: int = 0
    status: Literal["buildout", "open"] = "open"
    opens_on: int = 1
    transit_days: int = 1
    labor_budget: int = 2400
    weeks_of_supply: int = 3
    roster_set: bool = False
    sales_days: list[SalesDay] = Field(default_factory=list)
    week_sales: int = 0
    week_cogs: int = 0
    week_shrink: int = 0
    week_freight: int = 0
    last_week_sales: int = 0
    last_contribution: int = 0



class StoreDay(BaseModel):
    day: int
    store_id: str
    sales: int = 0
    cogs: int = 0
    labor: int = 0
    rent: int = 0
    freight: int = 0
    shrink: int = 0
    card_fees: int = 0
    pos_fees: int = 0
    by_department: dict[str, int] = Field(default_factory=dict)
    # Door traffic for that day. Zero stays off the save.
    visits: int = Field(default=0, exclude_if=lambda value: not value)


class Flags(BaseModel):
    neighbor_heat: int = 12
    competitor: int = 0
    competitor_announced: bool = False
    shortfalls: int = 0
    online_open: bool = False
    private_label: bool = False
    policy: Policy = "balanced"
    campaign_this_week: bool = False
    platform_trust: int = 76
    mark_private_open: bool = False
    incidents: int = 0
    ad_rejected: bool = False


class Totals(BaseModel):
    revenue: int = 0
    refunds: int = 0
    units: int = 0
    returns: int = 0
    events: int = 0
    quits: int = 0



class EconomyState(BaseModel):
    """Weekly economy card and factor indexes. Defaults keep old saves neutral."""

    difficulty: str = "off"
    pending_difficulty: str = ""
    last_week_id: int = -1
    values: dict[str, int] = Field(default_factory=dict)
    prev_values: dict[str, int] = Field(default_factory=dict)
    visits: dict[str, int] = Field(default_factory=dict)
    demand: dict[str, dict[str, int]] = Field(default_factory=dict)
    cost: dict[str, dict[str, int]] = Field(default_factory=dict)
    freight: dict[str, int] = Field(default_factory=dict)
    history: list[dict] = Field(default_factory=list)
    events: list[dict] = Field(default_factory=list)
    deferred_events: list[dict] = Field(default_factory=list)
    event_cooldowns: dict[str, int] = Field(default_factory=dict)
    news: list[dict] = Field(default_factory=list)
    next_news_id: int = 1
    catch_up: dict[str, dict] = Field(default_factory=dict)
    daily_news_day: dict[str, int] = Field(default_factory=dict)
    live_ticks: int = 0
    rent_index: dict[str, int] = Field(default_factory=dict)
    rent_week: dict[str, int] = Field(default_factory=dict)
    # Mandate port phase 1: weekly national macro layer. Empty when off and on
    # old saves; economy.macro.ensure_macro fills it on the first live use.
    macro: dict[str, Any] = Field(default_factory=dict)


class RivalAIBlock(BaseModel):
    """Rival AI save block (open_late.rival_ai). Absent on AI-off games and old saves.

    ``packed`` is base64(zlib(JSON)) of the AI state minus every top-level part
    that still equals the deterministic baseline rebuilt from ``init``. The
    live, unpacked state sits on a private attribute and is packed on save.
    """

    version: int = 1
    enabled: bool = True
    init: dict[str, Any] = Field(default_factory=dict)
    packed: str = ""
    _live: Any = PrivateAttr(default=None)

    @model_serializer(mode="wrap")
    def _pack_live(self, handler):
        data = handler(self)
        if self._live is not None:
            from open_late.rival_ai import pack_block

            data["packed"] = pack_block(self)
        return data


class DecisionNote(BaseModel):
    day: int = 0
    kind: str = ""
    text: str = ""
    ref: str = ""
    result: str = ""
    before_units: int = -1
    before_walked: int = -1
    before_visits: int = -1


class MailLetter(BaseModel):
    id: str
    day: int = 0
    to_id: str = ""
    to_name: str = ""
    role: str = ""
    subject: str = ""
    body: str = ""
    reply_from: str = ""
    reply: str = ""


class GameState(BaseModel):
    save_version: int = 2
    slot: str
    shop_name: str
    mode: Mode
    seed: int
    rng_counter: int = 0
    day: int = 1
    phase: Literal["morning", "desk", "evening", "gameover"] = "morning"
    cash: int
    credit_limit: int = 8000
    credit_used: int = 0
    reputation_respectable: int = 48
    reputation_nightlife: int = 32
    review_score: float = 4.2
    review_count: int = 8
    products: dict[str, Product]  # runtime catalog; content.PRODUCTS is the authored list
    stock: dict[str, StockLine]
    staff: list[Staff]
    regulars: list[Regular]
    sites: list[Site]
    orders: list[PurchaseOrder] = Field(default_factory=list)
    campaign: Campaign | None = None
    scheduled_event: EventPlan | None = None
    inbox: list[InboxMessage] = Field(default_factory=list)
    last_report: DayReport = Field(default_factory=DayReport)
    history: list[DayReport] = Field(default_factory=list)
    journal: list[str] = Field(default_factory=list)
    cooldowns: dict[str, int] = Field(default_factory=dict)
    flags: Flags = Field(default_factory=Flags)
    totals: Totals = Field(default_factory=Totals)
    spent_today: int = 0
    spent_merchandise: int = 0
    spent_freight: int = 0
    spent_variance: int = 0
    spent_advertising: int = 0
    spent_severance: int = 0
    spent_draws: int = 0
    spent_debt: int = 0
    spent_fixtures: int = 0
    spent_period: int = 0
    spent_planogram: int = 0
    actions_today: list[str] = Field(default_factory=list)
    milestones: list[str] = Field(default_factory=list)
    failed: bool = False
    fail_reason: str = ""
    next_order_id: int = 1
    next_message_id: int = 1
    tax_held: int = 0
    tax_lifetime: int = 0
    fixtures: int = 2400
    accumulated_depreciation: int = 0
    owner_draws: int = 0
    list_size: int = 60
    open_hour: int = 11
    close_hour: int = 19
    quarter_sales: int = 0
    quarter_cogs: int = 0
    quarter_refunds: int = 0
    quarter_opex: int = 0
    quarter_tax: int = 0
    quarter_depreciation: int = 0
    quarter_rent: int = 0
    quarter_wages: int = 0
    quarter_payroll_tax: int = 0
    quarter_insurance: int = 0
    quarter_utilities: int = 0
    quarter_interest: int = 0
    quarter_shipping: int = 0
    quarter_card_fees: int = 0
    quarter_licenses: int = 0
    quarter_freight: int = 0
    quarter_variance: int = 0
    quarter_ads: int = 0
    quarter_severance: int = 0
    quarter_period: int = 0
    quarter_planogram: int = 0
    quarter_shrink: int = 0
    price_was: dict[str, int] = Field(default_factory=dict)
    decisions: list[DecisionNote] = Field(default_factory=list)
    sent_mail: list[MailLetter] = Field(default_factory=list)
    cost_asked: dict[str, int] = Field(default_factory=dict)
    cost_pending: dict[str, int] = Field(default_factory=dict)
    pool_tried: dict[str, int] = Field(default_factory=dict)
    owner_capital: int = 0
    owner_capital_set: bool = False
    retained_earnings: int = 0
    supplier_accounts: list[SupplierAccount] = Field(default_factory=list)
    rival: Rival = Field(default_factory=Rival)
    targets: list[Target] = Field(default_factory=list)
    months: list[MonthClose] = Field(default_factory=list)
    ledger: list[LedgerLine] = Field(default_factory=list)
    doors: list[Door] = Field(default_factory=list)
    managers: list[StoreManager] = Field(default_factory=list)
    deals: list[VendorDeal] = Field(default_factory=list)
    shipments: list[Shipment] = Field(default_factory=list)
    next_shipment_id: int = 1
    markdown_after_days: int = 28
    markdown_percent: int = 20
    cleared_ids: list[str] = Field(default_factory=list)
    store_pos_by_id: dict[str, str] = Field(default_factory=dict)
    pending_store_pos: dict[str, str] = Field(default_factory=dict)
    store_days: list[StoreDay] = Field(default_factory=list)
    chain_id: str = "megamart"
    economy: EconomyState = Field(default_factory=EconomyState)
    # Rival AI (three supercenter chains). None keeps Northline and is not written
    # to the save, so AI-off saves stay byte-identical to save_version 4.
    rival_ai: RivalAIBlock | None = Field(default=None, exclude_if=lambda value: value is None)
    # ShopperLife households. None stays off the save, so a current game is unchanged.
    shopperlife: ShopperLifeBlock | None = Field(default=None, exclude_if=lambda value: value is None)
    # Delegation policies and the approval queue. Empty stays off the save.
    ui_phase7_delegation: dict[str, Any] = Field(default_factory=dict, exclude_if=lambda value: not value)
    # Board scenario. Empty stays off the save.
    ui_phase8_scenario: dict[str, Any] = Field(default_factory=dict, exclude_if=lambda value: not value)
    shelves: dict[str, Any] = Field(default_factory=dict, exclude_if=lambda value: not value)  # Lite shelves; {} = off, not saved
    # VISIONDECK archive. Empty stays off the save, so an older file is unchanged.
    visiondeck_save: dict[str, Any] = Field(default_factory=dict, exclude_if=lambda value: not value)
