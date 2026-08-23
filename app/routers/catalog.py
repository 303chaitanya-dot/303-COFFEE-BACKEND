from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import Item, ItemCategory, Supplier, Unit
from app.presenters import present_item, present_supplier, present_vendor
from app.schemas import (
    ExpiredActionIn,
    ItemDeleteIn,
    ItemIn,
    ItemOut,
    SupplierIn,
    SupplierOut,
    VendorEntryIn,
    VendorOut,
    VendorSettleIn,
)
from app.services.inventory import (
    apply_pack_stock,
    apply_qty_delta_to_lots,
    convert_qty,
    delete_items,
    item_split,
    make_sku,
    mark_expired_good,
    qty,
    record_waste,
)
from app.services.ledger import money
from app.services.vendors import (
    charge_vendor,
    create_vendor,
    delete_vendor,
    record_manual_entry,
    settle_vendor,
    vendor_balances,
)

router = APIRouter()


def _validated_serving(payload: ItemIn) -> str:
    if payload.category not in {item.value for item in ItemCategory}:
        raise HTTPException(status_code=400, detail="Invalid item category")
    if payload.unit not in {item.value for item in Unit}:
        raise HTTPException(status_code=400, detail="Invalid unit")
    serving_unit = payload.serving_unit or payload.unit
    if serving_unit not in {item.value for item in Unit}:
        raise HTTPException(status_code=400, detail="Invalid serving unit")
    if convert_qty(payload.serving_size, serving_unit, payload.unit) is None:
        raise HTTPException(
            status_code=400,
            detail=f"Serving unit {serving_unit} does not match stock unit {payload.unit}. Use g/kg together, ml/l together, or pcs with pcs.",
        )
    return serving_unit


@router.get("/suppliers", response_model=list[SupplierOut])
def list_suppliers(db: Session = Depends(get_db)) -> list[SupplierOut]:
    rows = db.scalars(select(Supplier).order_by(Supplier.name)).all()
    return [present_supplier(row) for row in rows]


@router.post("/suppliers", response_model=SupplierOut, status_code=201)
def create_supplier(payload: SupplierIn, db: Session = Depends(get_db)) -> SupplierOut:
    supplier = create_vendor(db, **payload.model_dump())
    db.commit()
    db.refresh(supplier)
    return present_supplier(supplier)


def _vendor_out(db: Session, vendor_id: int) -> VendorOut:
    vendor = db.scalar(select(Supplier).options(selectinload(Supplier.vendor_entries)).where(Supplier.id == vendor_id))
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return present_vendor(vendor, vendor_balances(db).get(vendor.id, 0))


@router.get("/vendors", response_model=list[VendorOut])
def list_vendors(db: Session = Depends(get_db)) -> list[VendorOut]:
    rows = db.scalars(
        select(Supplier)
        .where(Supplier.active.is_(True))
        .options(selectinload(Supplier.vendor_entries))
        .order_by(Supplier.name)
    ).all()
    balances = vendor_balances(db)
    return [present_vendor(row, balances.get(row.id, 0)) for row in rows]


@router.post("/vendors", response_model=VendorOut, status_code=201)
def add_vendor(payload: SupplierIn, db: Session = Depends(get_db)) -> VendorOut:
    vendor = create_vendor(db, **payload.model_dump())
    db.commit()
    return _vendor_out(db, vendor.id)


@router.post("/vendors/{vendor_id}/settle", response_model=VendorOut)
def settle_vendor_balance(vendor_id: int, payload: VendorSettleIn, db: Session = Depends(get_db)) -> VendorOut:
    settle_vendor(db, vendor_id=vendor_id, amount=payload.amount, note=payload.note)
    db.commit()
    return _vendor_out(db, vendor_id)


@router.post("/vendors/{vendor_id}/entries", response_model=VendorOut)
def add_vendor_entry(vendor_id: int, payload: VendorEntryIn, db: Session = Depends(get_db)) -> VendorOut:
    record_manual_entry(db, vendor_id=vendor_id, amount=payload.amount, kind=payload.kind, note=payload.note)
    db.commit()
    return _vendor_out(db, vendor_id)


@router.delete("/vendors/{vendor_id}")
def remove_vendor(vendor_id: int, db: Session = Depends(get_db)) -> dict[str, int]:
    delete_vendor(db, vendor_id)
    db.commit()
    return {"deleted": 1}


@router.put("/suppliers/{supplier_id}", response_model=SupplierOut)
def update_supplier(supplier_id: int, payload: SupplierIn, db: Session = Depends(get_db)) -> SupplierOut:
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    for key, value in payload.model_dump().items():
        setattr(supplier, key, value)
    db.commit()
    db.refresh(supplier)
    return present_supplier(supplier)


def _item_with_lots(db: Session, item_id: int) -> Item:
    item = db.scalar(select(Item).options(selectinload(Item.lots)).where(Item.id == item_id))
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.get("/items", response_model=list[ItemOut])
def list_items(db: Session = Depends(get_db)) -> list[ItemOut]:
    rows = db.scalars(select(Item).options(selectinload(Item.lots)).order_by(Item.category, Item.name)).all()
    return [present_item(row) for row in rows]


@router.post("/items", response_model=ItemOut, status_code=201)
def create_item(payload: ItemIn, db: Session = Depends(get_db)) -> ItemOut:
    serving_unit = _validated_serving(payload)
    sku = (payload.sku or "").strip() or make_sku(db, payload.name)
    if db.scalar(select(Item).where(Item.sku == sku)):
        raise HTTPException(status_code=409, detail="SKU already exists")
    item = Item(
        sku=sku,
        name=payload.name,
        category=payload.category,
        unit=payload.unit,
        reorder_point=payload.reorder_point,
        par_level=payload.par_level,
        serving_size=payload.serving_size,
        serving_unit=serving_unit,
        expiry_date=payload.expiry_date,
        active=payload.active,
    )
    apply_pack_stock(
        item,
        qty_per_unit=payload.qty_per_unit,
        units_on_hand=payload.units_on_hand,
        total_price=payload.price,
    )
    db.add(item)
    db.flush()
    apply_qty_delta_to_lots(db, item, item.quantity_on_hand, expiry_date=item.expiry_date)
    charge_vendor(db, vendor_id=payload.vendor_id, amount=payload.price, item=item)
    db.commit()
    return present_item(_item_with_lots(db, item.id))


@router.put("/items/{item_id}", response_model=ItemOut)
def update_item(item_id: int, payload: ItemIn, db: Session = Depends(get_db)) -> ItemOut:
    item = _item_with_lots(db, item_id)
    serving_unit = _validated_serving(payload)
    if payload.sku and payload.sku != item.sku:
        if db.scalar(select(Item).where(Item.sku == payload.sku, Item.id != item.id)):
            raise HTTPException(status_code=409, detail="SKU already exists")
        item.sku = payload.sku
    item.name = payload.name
    item.category = payload.category
    item.unit = payload.unit
    item.reorder_point = payload.reorder_point
    item.par_level = payload.par_level
    item.serving_size = payload.serving_size
    item.serving_unit = serving_unit
    item.expiry_date = payload.expiry_date
    item.active = payload.active
    previous = qty(item.quantity_on_hand)
    added = qty(payload.add_units)
    if added:
        apply_pack_stock(
            item,
            qty_per_unit=payload.qty_per_unit,
            units_on_hand=qty(item.units_on_hand) + added,
            total_price=money(getattr(item, "total_price", 0) or 0) + money(payload.add_price),
        )
    elif payload.replace_stock:
        apply_pack_stock(
            item,
            qty_per_unit=payload.qty_per_unit,
            units_on_hand=payload.units_on_hand,
            total_price=payload.price,
        )
    else:
        item.qty_per_unit = qty(payload.qty_per_unit)
        from app.services.inventory import sync_pack_from_quantity

        sync_pack_from_quantity(item)
    apply_qty_delta_to_lots(
        db,
        item,
        qty(item.quantity_on_hand) - previous,
        expiry_date=item.expiry_date,
        prefer_expired=True,
    )
    if added:
        charge_vendor(db, vendor_id=payload.vendor_id, amount=payload.add_price, item=item)
    db.commit()
    return present_item(_item_with_lots(db, item.id))


@router.post("/items/{item_id}/expired", response_model=ItemOut)
def act_on_expired(item_id: int, payload: ExpiredActionIn, db: Session = Depends(get_db)) -> ItemOut:
    item = _item_with_lots(db, item_id)
    _good, expired = item_split(item)
    used = qty(payload.quantity)
    if used > expired:
        raise HTTPException(
            status_code=400,
            detail=f"Only {expired} {item.unit} is expired on {item.name}",
        )
    if payload.action == "discard":
        record_waste(
            db,
            item_id=item.id,
            quantity=used,
            reason="Expired",
            note="Discarded from expired stock",
        )
    else:
        mark_expired_good(db, item, used)
    db.commit()
    return present_item(_item_with_lots(db, item.id))


@router.post("/items/delete")
def remove_items(payload: ItemDeleteIn, db: Session = Depends(get_db)) -> dict[str, int]:
    return {"deleted": delete_items(db, payload.ids)}
