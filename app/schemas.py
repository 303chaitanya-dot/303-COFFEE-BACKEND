from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SupplierIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    contact_name: str | None = None
    phone: str | None = None
    email: str | None = None
    notes: str | None = None
    active: bool = True


class SupplierOut(ORMModel, SupplierIn):
    id: int
    created_at: datetime


class ItemIn(BaseModel):
    sku: str | None = None
    name: str = Field(min_length=1, max_length=160)
    category: str
    unit: str
    qty_per_unit: Decimal = Decimal("1")
    units_on_hand: Decimal = Decimal("0")
    reorder_point: Decimal = Decimal("0")
    par_level: Decimal = Decimal("0")
    price: Decimal = Decimal("0")
    serving_size: Decimal = Decimal("1")
    serving_unit: str | None = None
    expiry_date: date | None = None
    active: bool = True
    add_units: Decimal = Decimal("0")
    add_price: Decimal = Decimal("0")
    replace_stock: bool = False


class ItemOut(ORMModel):
    id: int
    sku: str
    name: str
    category: str
    unit: str
    qty_per_unit: Decimal
    units_on_hand: Decimal
    quantity_on_hand: Decimal
    good_quantity: Decimal
    expired_quantity: Decimal
    reorder_point: Decimal
    par_level: Decimal
    price: Decimal
    unit_cost: Decimal
    serving_size: Decimal
    serving_unit: str
    price_per_serving: Decimal
    expiry_date: date | None
    expiry_status: str
    inventory_value: Decimal
    below_reorder: bool
    active: bool
    created_at: datetime
    updated_at: datetime


class ExpiredActionIn(BaseModel):
    action: Literal["discard", "mark_good"]
    quantity: Decimal = Field(gt=0)


class ItemDeleteIn(BaseModel):
    ids: list[int] = Field(min_length=1)


class RecipeLineIn(BaseModel):
    item_id: int | None = None
    sauce_id: int | None = None
    quantity: Decimal = Field(gt=0)
    unit: str | None = None

    @model_validator(mode="after")
    def one_component(self):
        if bool(self.item_id) == bool(self.sauce_id):
            raise ValueError("Each recipe line needs either an ingredient or a sauce")
        return self


class RecipeLineOut(ORMModel):
    id: int
    kind: str
    item_id: int | None
    sauce_id: int | None
    name: str
    unit: str
    quantity: Decimal
    price_used: Decimal


class MenuItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    category: str
    price: Decimal = Field(ge=0)
    active: bool = True
    recipe: list[RecipeLineIn] = Field(default_factory=list)


class MenuItemOut(ORMModel):
    id: int
    name: str
    category: str
    price: Decimal
    active: bool
    recipe_cost: Decimal
    recipe: list[RecipeLineOut]
    created_at: datetime


class PurchaseLineIn(BaseModel):
    item_id: int
    quantity: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(ge=0)


class PurchaseIn(BaseModel):
    supplier_id: int
    invoice_number: str | None = None
    purchased_at: datetime | None = None
    paid: bool = False
    notes: str | None = None
    lines: list[PurchaseLineIn] = Field(min_length=1)


class PurchaseLineOut(ORMModel):
    id: int
    item_id: int
    item_name: str
    quantity: Decimal
    unit_cost: Decimal
    line_total: Decimal


class PurchaseOut(ORMModel):
    id: int
    supplier_id: int
    supplier_name: str
    invoice_number: str | None
    status: str
    purchased_at: datetime
    paid: bool
    notes: str | None
    total: Decimal
    lines: list[PurchaseLineOut]
    created_at: datetime


class SaleLineIn(BaseModel):
    menu_item_id: int
    quantity: int = Field(gt=0)


class SaleIn(BaseModel):
    payment_method: str = "cash"
    notes: str | None = None
    sold_at: datetime | None = None
    lines: list[SaleLineIn] = Field(min_length=1)


class SaleLineOut(ORMModel):
    id: int
    menu_item_id: int
    menu_item_name: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal


class SaleOut(ORMModel):
    id: int
    sold_at: datetime
    payment_method: str
    notes: str | None
    total: Decimal
    cogs: Decimal
    lines: list[SaleLineOut]
    created_at: datetime


class WasteIn(BaseModel):
    item_id: int
    quantity: Decimal = Field(gt=0)
    reason: str = Field(min_length=1, max_length=80)
    note: str | None = None


class WasteOut(ORMModel):
    id: int
    item_id: int
    item_name: str
    quantity: Decimal
    unit: str
    reason: str
    note: str | None
    cost: Decimal
    wasted_at: datetime


class AdjustmentIn(BaseModel):
    item_id: int
    quantity_delta: Decimal
    note: str = Field(min_length=1, max_length=240)


class PaymentIn(BaseModel):
    amount: Decimal = Field(gt=0)
    note: str | None = None


class AccountOut(ORMModel):
    id: int
    code: str
    name: str
    type: str
    system_key: str | None
    balance: Decimal


class JournalLineOut(ORMModel):
    account_code: str
    account_name: str
    debit: Decimal
    credit: Decimal


class JournalEntryOut(ORMModel):
    id: int
    occurred_on: date
    memo: str
    source_type: str
    source_id: int | None
    lines: list[JournalLineOut]
    created_at: datetime


class MovementOut(ORMModel):
    id: int
    item_id: int
    item_name: str
    quantity_delta: Decimal
    unit_cost: Decimal
    reason: str
    ref_type: str | None
    ref_id: int | None
    note: str | None
    created_at: datetime


class DashboardOut(BaseModel):
    currency_code: str
    currency_symbol: str
    inventory_value: Decimal
    cash_balance: Decimal
    accounts_payable: Decimal
    today_sales: Decimal
    today_tickets: int
    low_stock_count: int
    low_stock: list[ItemOut]
    expiring: list[ItemOut]
    expired: list[ItemOut]


class ProfitLossOut(BaseModel):
    from_date: date
    to_date: date
    revenue: Decimal
    cogs: Decimal
    waste: Decimal
    other_expense: Decimal
    gross_profit: Decimal
    net_income: Decimal


class InventoryValuationOut(BaseModel):
    items: list[ItemOut]
    total_value: Decimal


class MetaOut(BaseModel):
    app_name: str
    currency_code: str
    currency_symbol: str
    item_categories: list[str]
    menu_categories: list[str]
    units: list[str]
    payment_methods: list[str]
    roles: list[str]


class MessageOut(BaseModel):
    status: Literal["ok"] = "ok"
    detail: str


class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str | None = None
    title: str | None = None


class PasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class UserCreateIn(BaseModel):
    email: str
    password: str = Field(min_length=8)
    name: str = Field(min_length=1, max_length=120)
    role: str = "staff"
    phone: str | None = None
    title: str | None = None


class UserOut(ORMModel):
    id: int
    email: str
    name: str
    role: str
    phone: str | None
    title: str | None
    active: bool
    created_at: datetime


class SauceLineIn(BaseModel):
    item_id: int
    quantity: Decimal = Field(gt=0)


class SauceLineOut(ORMModel):
    id: int
    item_id: int
    item_name: str
    item_unit: str
    quantity: Decimal
    price_used: Decimal


class SauceIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    active: bool = True
    recipe: list[SauceLineIn] = Field(min_length=1)


class SauceOut(ORMModel):
    id: int
    name: str
    active: bool
    recipe_cost: Decimal
    recipe: list[SauceLineOut]
    created_at: datetime


class NamedPurchaseLineIn(BaseModel):
    name: str = Field(min_length=1)
    quantity: Decimal = Field(gt=0)
    price: Decimal = Field(ge=0)
    unit: str = "pcs"
    category: str = "other"
    serving_size: Decimal | None = None


class NamedPurchaseIn(BaseModel):
    supplier_name: str | None = None
    invoice_number: str | None = None
    paid: bool = False
    notes: str | None = None
    lines: list[NamedPurchaseLineIn] = Field(min_length=1)


class BillOut(ORMModel):
    id: int
    filename: str
    status: str
    supplier_name: str | None
    invoice_number: str | None
    notes: str | None
    lines: list[dict]
    purchase_id: int | None
    created_at: datetime


class BillReviewIn(BaseModel):
    supplier_name: str | None = None
    invoice_number: str | None = None
    notes: str | None = None
    lines: list[NamedPurchaseLineIn]


class PetPoojaMapIn(BaseModel):
    external_item_id: str | None = None
    external_name: str = Field(min_length=1)
    menu_item_id: int


class PetPoojaMapOut(ORMModel):
    id: int
    external_item_id: str | None
    external_name: str
    menu_item_id: int
    menu_item_name: str


class SheetLinkIn(BaseModel):
    url: str = Field(min_length=8)


class SheetSyncIn(BaseModel):
    url: str = ""


class SheetLinkOut(BaseModel):
    url: str
    last_synced_at: datetime | None = None
    last_message: str | None = None


class SheetSyncOut(BaseModel):
    created: int
    updated: int
    skipped: int
    errors: list[str]
    last_synced_at: datetime | None
    last_message: str | None
    url: str


class SalesImportOut(BaseModel):
    filename: str
    report_date: str
    applied: list[dict]
    skipped: list[dict]
    sale_id: int | None
    status: str
    message: str


class PetPoojaOrderOut(ORMModel):
    id: int
    external_order_id: str
    status: str
    unmapped: list[dict]
    sale_id: int | None
    created_at: datetime
