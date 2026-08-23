from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.db import get_db
from app.models import Account, Item, JournalEntry, JournalLine, Sale, SaleLine
from app.presenters import present_account, present_entry, present_item, present_sale
from app.schemas import AccountOut, DashboardOut, InventoryValuationOut, JournalEntryOut, ProfitLossOut, SaleOut
from app.services.inventory import item_value, sale_total
from app.services.ledger import account_balance, get_account, money

router = APIRouter()


def start_of_day(day: date) -> datetime:
    return datetime.combine(day, datetime.min.time())


def sum_money(values) -> Decimal:
    total = Decimal("0.00")
    for value in values:
        total += money(value)
    return total


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(db: Session = Depends(get_db)) -> DashboardOut:
    items = db.scalars(
        select(Item).options(selectinload(Item.lots)).where(Item.active.is_(True)).order_by(Item.name)
    ).all()
    presented = [present_item(item) for item in items]
    low_stock = [item for item in presented if item.below_reorder]
    sales = db.scalars(
        select(Sale).options(selectinload(Sale.lines)).where(Sale.sold_at >= start_of_day(date.today()))
    ).all()
    return DashboardOut(
        currency_code=settings.currency_code,
        currency_symbol=settings.currency_symbol,
        inventory_value=sum_money(item_value(item) for item in items),
        cash_balance=account_balance(db, get_account(db, "cash")),
        accounts_payable=account_balance(db, get_account(db, "accounts_payable")),
        today_sales=sum_money(sale_total(sale) for sale in sales),
        today_tickets=len(sales),
        low_stock_count=len(low_stock),
        low_stock=low_stock,
        expiring=[item for item in presented if item.expiry_status == "expiring"],
        expired=[item for item in presented if item.expired_quantity > 0 or item.expiry_status == "expired"],
    )


@router.get("/accounts", response_model=list[AccountOut])
def list_accounts(db: Session = Depends(get_db)) -> list[AccountOut]:
    rows = db.scalars(select(Account).order_by(Account.code)).all()
    return [present_account(db, row) for row in rows]


@router.get("/ledger", response_model=list[JournalEntryOut])
def list_ledger(limit: int = 80, db: Session = Depends(get_db)) -> list[JournalEntryOut]:
    rows = db.scalars(
        select(JournalEntry)
        .options(selectinload(JournalEntry.lines).selectinload(JournalLine.account))
        .order_by(JournalEntry.created_at.desc())
        .limit(limit)
    ).all()
    return [present_entry(row) for row in rows]


@router.get("/reports/valuation", response_model=InventoryValuationOut)
def inventory_valuation(db: Session = Depends(get_db)) -> InventoryValuationOut:
    items = [
        present_item(item)
        for item in db.scalars(select(Item).options(selectinload(Item.lots)).order_by(Item.name)).all()
    ]
    return InventoryValuationOut(items=items, total_value=sum_money(item.inventory_value for item in items))


@router.get("/reports/profit-loss", response_model=ProfitLossOut)
def profit_loss(
    from_date: date | None = None,
    to_date: date | None = None,
    db: Session = Depends(get_db),
) -> ProfitLossOut:
    start = from_date or date.today().replace(day=1)
    end = to_date or date.today()
    entries = db.scalars(
        select(JournalEntry)
        .options(selectinload(JournalEntry.lines).selectinload(JournalLine.account))
        .where(JournalEntry.occurred_on >= start, JournalEntry.occurred_on <= end)
    ).all()

    revenue = money(0)
    cogs = money(0)
    waste = money(0)
    other = money(0)
    for entry in entries:
        for line in entry.lines:
            key = line.account.system_key
            if key == "sales":
                revenue += money(line.credit) - money(line.debit)
            elif key == "cogs":
                cogs += money(line.debit) - money(line.credit)
            elif key == "waste":
                waste += money(line.debit) - money(line.credit)
            elif key == "adjustments":
                other += money(line.debit) - money(line.credit)

    return ProfitLossOut(
        from_date=start,
        to_date=end,
        revenue=revenue,
        cogs=cogs,
        waste=waste,
        other_expense=other,
        gross_profit=money(revenue - cogs),
        net_income=money(revenue - cogs - waste - other),
    )


@router.get("/reports/today-sales", response_model=list[SaleOut])
def today_sales(db: Session = Depends(get_db)) -> list[SaleOut]:
    rows = db.scalars(
        select(Sale)
        .options(selectinload(Sale.lines).selectinload(SaleLine.menu_item))
        .where(Sale.sold_at >= start_of_day(date.today()))
        .order_by(Sale.sold_at.desc())
    ).all()
    return [present_sale(db, sale) for sale in rows]
