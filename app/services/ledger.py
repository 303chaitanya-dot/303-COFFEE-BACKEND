from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, JournalEntry, JournalLine, utcnow

SYSTEM_ACCOUNTS = [
    ("1000", "Cash", "asset", "cash"),
    ("1100", "Inventory", "asset", "inventory"),
    ("2000", "Accounts Payable", "liability", "accounts_payable"),
    ("3000", "Owner Equity", "equity", "equity"),
    ("4000", "Sales Revenue", "revenue", "sales"),
    ("5000", "Cost of Goods Sold", "expense", "cogs"),
    ("5100", "Waste Expense", "expense", "waste"),
    ("5200", "Inventory Adjustments", "expense", "adjustments"),
]


def money(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def ensure_chart_of_accounts(db: Session) -> None:
    existing = {row.system_key for row in db.scalars(select(Account)).all()}
    for code, name, acct_type, key in SYSTEM_ACCOUNTS:
        if key in existing:
            continue
        db.add(Account(code=code, name=name, type=acct_type, system_key=key))
    db.flush()


def get_account(db: Session, system_key: str) -> Account:
    account = db.scalar(select(Account).where(Account.system_key == system_key))
    if account is None:
        raise HTTPException(status_code=500, detail=f"Missing system account: {system_key}")
    return account


def account_balance(db: Session, account: Account) -> Decimal:
    debit = db.scalar(
        select(func.coalesce(func.sum(JournalLine.debit), 0)).where(JournalLine.account_id == account.id)
    )
    credit = db.scalar(
        select(func.coalesce(func.sum(JournalLine.credit), 0)).where(JournalLine.account_id == account.id)
    )
    debit_amt = money(debit or 0)
    credit_amt = money(credit or 0)
    if account.type in ("asset", "expense"):
        return debit_amt - credit_amt
    return credit_amt - debit_amt


def post_entry(
    db: Session,
    *,
    memo: str,
    source_type: str,
    source_id: int | None,
    lines: list[tuple[str, Decimal, Decimal]],
    occurred_on: date | None = None,
) -> JournalEntry:
    balanced_lines: list[tuple[Account, Decimal, Decimal]] = []
    total_debit = Decimal("0.00")
    total_credit = Decimal("0.00")

    for system_key, debit, credit in lines:
        debit_amt = money(debit)
        credit_amt = money(credit)
        if debit_amt < 0 or credit_amt < 0:
            raise HTTPException(status_code=400, detail="Journal amounts cannot be negative")
        if debit_amt == 0 and credit_amt == 0:
            continue
        if debit_amt > 0 and credit_amt > 0:
            raise HTTPException(status_code=400, detail="A journal line cannot be both debit and credit")
        balanced_lines.append((get_account(db, system_key), debit_amt, credit_amt))
        total_debit += debit_amt
        total_credit += credit_amt

    if not balanced_lines:
        raise HTTPException(status_code=400, detail="Journal entry has no lines")
    if total_debit != total_credit:
        raise HTTPException(
            status_code=500,
            detail=f"Unbalanced journal entry: debit {total_debit} credit {total_credit}",
        )

    entry = JournalEntry(
        occurred_on=occurred_on or date.today(),
        memo=memo,
        source_type=source_type,
        source_id=source_id,
        created_at=utcnow(),
    )
    db.add(entry)
    db.flush()
    for account, debit_amt, credit_amt in balanced_lines:
        db.add(
            JournalLine(
                entry_id=entry.id,
                account_id=account.id,
                debit=debit_amt,
                credit=credit_amt,
            )
        )
    db.flush()
    return entry
