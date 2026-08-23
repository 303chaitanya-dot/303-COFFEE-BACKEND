from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

Money = Numeric(14, 2)
Qty = Numeric(16, 4)


class ItemCategory(str, Enum):
    coffee = "coffee"
    dairy = "dairy"
    bakery = "bakery"
    dry_goods = "dry_goods"
    packaging = "packaging"
    beverages = "beverages"
    produce = "produce"
    other = "other"


class Unit(str, Enum):
    g = "g"
    kg = "kg"
    ml = "ml"
    l = "l"
    pcs = "pcs"


class MenuCategory(str, Enum):
    espresso = "espresso"
    coffee = "coffee"
    tea = "tea"
    food = "food"
    retail = "retail"
    other = "other"


class MovementReason(str, Enum):
    purchase = "purchase"
    sale = "sale"
    waste = "waste"
    adjustment = "adjustment"


class PurchaseStatus(str, Enum):
    draft = "draft"
    received = "received"
    void = "void"


class PaymentMethod(str, Enum):
    cash = "cash"
    card = "card"
    upi = "upi"
    other = "other"


class AccountType(str, Enum):
    asset = "asset"
    liability = "liability"
    equity = "equity"
    revenue = "revenue"
    expense = "expense"


class AppFlag(Base):
    __tablename__ = "app_flags"

    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    value: Mapped[str] = mapped_column(String(80), default="1")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(160), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20), default="staff")
    phone: Mapped[str | None] = mapped_column(String(40))
    title: Mapped[str | None] = mapped_column(String(80))
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    contact_name: Mapped[str | None] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(160))
    notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    purchases: Mapped[list["Purchase"]] = relationship(back_populates="supplier")


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(40))
    unit: Mapped[str] = mapped_column(String(8))
    qty_per_unit: Mapped[Decimal] = mapped_column(Qty, default=Decimal("1"))
    units_on_hand: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    quantity_on_hand: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    reorder_point: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    par_level: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    total_price: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    unit_cost: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    serving_size: Mapped[Decimal] = mapped_column(Qty, default=Decimal("1"))
    serving_unit: Mapped[str] = mapped_column(String(8), default="pcs")
    expiry_date: Mapped[date | None] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    movements: Mapped[list["StockMovement"]] = relationship(back_populates="item")
    recipe_lines: Mapped[list["RecipeLine"]] = relationship(back_populates="item")
    lots: Mapped[list["StockLot"]] = relationship(back_populates="item", cascade="all, delete-orphan")


class StockLot(Base):
    __tablename__ = "stock_lots"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"))
    quantity: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    expiry_date: Mapped[date | None] = mapped_column(Date)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    item: Mapped["Item"] = relationship(back_populates="lots")


class MenuItem(Base):
    __tablename__ = "menu_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    category: Mapped[str] = mapped_column(String(40))
    price: Mapped[Decimal] = mapped_column(Money)
    petpooja_item_id: Mapped[str | None] = mapped_column(String(80))
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    recipe_lines: Mapped[list["RecipeLine"]] = relationship(
        back_populates="menu_item", cascade="all, delete-orphan"
    )
    sale_lines: Mapped[list["SaleLine"]] = relationship(back_populates="menu_item")


class Sauce(Base):
    __tablename__ = "sauces"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    lines: Mapped[list["SauceLine"]] = relationship(back_populates="sauce", cascade="all, delete-orphan")


class SauceLine(Base):
    __tablename__ = "sauce_lines"
    __table_args__ = (UniqueConstraint("sauce_id", "item_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sauce_id: Mapped[int] = mapped_column(ForeignKey("sauces.id", ondelete="CASCADE"))
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    quantity: Mapped[Decimal] = mapped_column(Qty)

    sauce: Mapped[Sauce] = relationship(back_populates="lines")
    item: Mapped[Item] = relationship()


class RecipeLine(Base):
    __tablename__ = "recipe_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    menu_item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id", ondelete="CASCADE"))
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"))
    sauce_id: Mapped[int | None] = mapped_column(ForeignKey("sauces.id"))
    quantity: Mapped[Decimal] = mapped_column(Qty)
    unit: Mapped[str | None] = mapped_column(String(8))

    menu_item: Mapped[MenuItem] = relationship(back_populates="recipe_lines")
    item: Mapped[Item] = relationship(back_populates="recipe_lines")
    sauce: Mapped[Sauce] = relationship()


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    quantity_delta: Mapped[Decimal] = mapped_column(Qty)
    unit_cost: Mapped[Decimal] = mapped_column(Money)
    reason: Mapped[str] = mapped_column(String(20))
    ref_type: Mapped[str | None] = mapped_column(String(40))
    ref_id: Mapped[int | None]
    note: Mapped[str | None] = mapped_column(String(240))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    item: Mapped[Item] = relationship(back_populates="movements")


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    invoice_number: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default=PurchaseStatus.received.value)
    purchased_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    paid: Mapped[bool] = mapped_column(default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    supplier: Mapped[Supplier] = relationship(back_populates="purchases")
    lines: Mapped[list["PurchaseLine"]] = relationship(
        back_populates="purchase", cascade="all, delete-orphan"
    )


class PurchaseLine(Base):
    __tablename__ = "purchase_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id", ondelete="CASCADE"))
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    quantity: Mapped[Decimal] = mapped_column(Qty)
    unit_cost: Mapped[Decimal] = mapped_column(Money)

    purchase: Mapped[Purchase] = relationship(back_populates="lines")
    item: Mapped[Item] = relationship()


class Sale(Base):
    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(primary_key=True)
    sold_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    payment_method: Mapped[str] = mapped_column(String(20), default=PaymentMethod.cash.value)
    notes: Mapped[str | None] = mapped_column(String(240))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    lines: Mapped[list["SaleLine"]] = relationship(
        back_populates="sale", cascade="all, delete-orphan"
    )


class SaleLine(Base):
    __tablename__ = "sale_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id", ondelete="CASCADE"))
    menu_item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"))
    quantity: Mapped[int]
    unit_price: Mapped[Decimal] = mapped_column(Money)

    sale: Mapped[Sale] = relationship(back_populates="lines")
    menu_item: Mapped[MenuItem] = relationship(back_populates="sale_lines")


class WasteEvent(Base):
    __tablename__ = "waste_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    quantity: Mapped[Decimal] = mapped_column(Qty)
    reason: Mapped[str] = mapped_column(String(80))
    note: Mapped[str | None] = mapped_column(String(240))
    wasted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    item: Mapped[Item] = relationship()


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(12), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    type: Mapped[str] = mapped_column(String(20))
    system_key: Mapped[str | None] = mapped_column(String(40), unique=True)

    lines: Mapped[list["JournalLine"]] = relationship(back_populates="account")


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    occurred_on: Mapped[date] = mapped_column(Date, default=date.today)
    memo: Mapped[str] = mapped_column(String(240))
    source_type: Mapped[str] = mapped_column(String(40))
    source_id: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    lines: Mapped[list["JournalLine"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan"
    )


class JournalLine(Base):
    __tablename__ = "journal_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("journal_entries.id", ondelete="CASCADE"))
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    debit: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    credit: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))

    entry: Mapped[JournalEntry] = relationship(back_populates="lines")
    account: Mapped[Account] = relationship(back_populates="lines")


class BillUpload(Base):
    __tablename__ = "bill_uploads"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(240))
    content_type: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30), default="pending_review")
    supplier_name: Mapped[str | None] = mapped_column(String(160))
    invoice_number: Mapped[str | None] = mapped_column(String(80))
    extracted_json: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    purchase_id: Mapped[int | None] = mapped_column(ForeignKey("purchases.id"))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    purchase: Mapped[Purchase | None] = relationship()
    created_by: Mapped[User | None] = relationship()


class PetPoojaMapping(Base):
    __tablename__ = "petpooja_mappings"
    __table_args__ = (UniqueConstraint("external_item_id", "external_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    external_item_id: Mapped[str | None] = mapped_column(String(80))
    external_name: Mapped[str] = mapped_column(String(160))
    menu_item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    menu_item: Mapped[MenuItem] = relationship()


class PetPoojaOrder(Base):
    __tablename__ = "petpooja_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    external_order_id: Mapped[str] = mapped_column(String(80), unique=True)
    status: Mapped[str] = mapped_column(String(30), default="received")
    raw_payload: Mapped[str] = mapped_column(Text)
    unmapped_json: Mapped[str | None] = mapped_column(Text)
    sale_id: Mapped[int | None] = mapped_column(ForeignKey("sales.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    sale: Mapped[Sale | None] = relationship()


class InventorySheet(Base):
    __tablename__ = "inventory_sheets"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), default="inventory")
    url: Mapped[str] = mapped_column(Text)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_message: Mapped[str | None] = mapped_column(Text)
