from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Item, Supplier, VendorEntry
from app.services.ledger import money

RESERVED_VENDOR_NAMES = {"others", "other"}


def _clean_name(name: str) -> str:
    return (name or "").strip()


def assert_vendor_name(name: str) -> str:
    label = _clean_name(name)
    if not label:
        raise HTTPException(status_code=400, detail="Vendor name is required")
    if label.lower() in RESERVED_VENDOR_NAMES:
        raise HTTPException(status_code=400, detail="Others is reserved. Add a named vendor instead.")
    return label


def get_vendor(db: Session, vendor_id: int) -> Supplier:
    vendor = db.get(Supplier, vendor_id)
    if vendor is None or not vendor.active:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return vendor


def create_vendor(
    db: Session,
    *,
    name: str,
    contact_name: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    notes: str | None = None,
    active: bool = True,
) -> Supplier:
    label = assert_vendor_name(name)
    existing = db.scalar(select(Supplier).where(func.lower(Supplier.name) == label.lower()))
    if existing:
        raise HTTPException(status_code=409, detail="Vendor already exists")
    vendor = Supplier(
        name=label,
        contact_name=contact_name,
        phone=phone,
        email=email,
        notes=notes,
        active=active,
    )
    db.add(vendor)
    db.flush()
    return vendor


def vendor_balances(db: Session) -> dict[int, Decimal]:
    rows = db.execute(
        select(VendorEntry.supplier_id, VendorEntry.kind, func.coalesce(func.sum(VendorEntry.amount), 0)).group_by(
            VendorEntry.supplier_id, VendorEntry.kind
        )
    ).all()
    totals: dict[int, Decimal] = {}
    for supplier_id, kind, amount in rows:
        current = totals.get(supplier_id, Decimal("0.00"))
        value = money(amount or 0)
        totals[supplier_id] = money(current + value) if kind == "charge" else money(current - value)
    return totals


def vendor_balance(db: Session, supplier_id: int) -> Decimal:
    return vendor_balances(db).get(supplier_id, Decimal("0.00"))


def charge_vendor(
    db: Session,
    *,
    vendor_id: int | None,
    amount: Decimal | int | float | str,
    item: Item | None = None,
    note: str | None = None,
) -> VendorEntry | None:
    if vendor_id is None:
        return None
    charged = money(amount)
    if charged <= 0:
        return None
    vendor = get_vendor(db, vendor_id)
    item_name = item.name if item is not None else None
    entry = VendorEntry(
        supplier_id=vendor.id,
        kind="charge",
        amount=charged,
        item_id=item.id if item is not None else None,
        note=note or (f"Inventory: {item_name}" if item_name else "Inventory purchase"),
    )
    db.add(entry)
    db.flush()
    return entry


def settle_vendor(
    db: Session,
    *,
    vendor_id: int,
    amount: Decimal | int | float | str,
    note: str | None = None,
) -> VendorEntry:
    paid = money(amount)
    if paid <= 0:
        raise HTTPException(status_code=400, detail="Settle amount must be more than 0")
    vendor = get_vendor(db, vendor_id)
    entry = VendorEntry(
        supplier_id=vendor.id,
        kind="settle",
        amount=paid,
        note=note or f"Settled {paid} for {vendor.name}",
    )
    db.add(entry)
    db.flush()
    return entry


def record_manual_entry(
    db: Session,
    *,
    vendor_id: int,
    amount: Decimal | int | float | str,
    kind: str,
    note: str | None = None,
) -> VendorEntry:
    label = (note or "").strip() or "Manual entry"
    if kind == "add":
        entry = charge_vendor(db, vendor_id=vendor_id, amount=amount, note=label)
        if entry is None:
            raise HTTPException(status_code=400, detail="Entry amount must be more than 0")
        return entry
    if kind == "reduce":
        return settle_vendor(db, vendor_id=vendor_id, amount=amount, note=label)
    raise HTTPException(status_code=400, detail="Entry must add to the balance or reduce it")


def delete_vendor(db: Session, vendor_id: int) -> None:
    vendor = get_vendor(db, vendor_id)
    for purchase in list(vendor.purchases):
        db.delete(purchase)
    db.delete(vendor)
