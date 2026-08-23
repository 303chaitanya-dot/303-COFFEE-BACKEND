from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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
    sku: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=160)
    category: str
    unit: str
    quantity_on_hand: Decimal = Decimal("0")
    reorder_point: Decimal = Decimal("0")
    par_level: Decimal = Decimal("0")
    unit_cost: Decimal = Decimal("0")
    active: bool = True


class ItemOut(ORMModel, ItemIn):
    id: int
    inventory_value: Decimal
    below_reorder: bool
    created_at: datetime
    updated_at: datetime


class RecipeLineIn(BaseModel):
    item_id: int
    quantity: Decimal = Field(gt=0)


class RecipeLineOut(ORMModel):
    id: int
    item_id: int
    item_name: str
    item_unit: str
    quantity: Decimal


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


class MessageOut(BaseModel):
    status: Literal["ok"] = "ok"
    detail: str
