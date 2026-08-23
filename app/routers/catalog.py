from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Item, ItemCategory, Supplier, Unit
from app.presenters import present_item, present_supplier
from app.schemas import ItemIn, ItemOut, SupplierIn, SupplierOut

router = APIRouter()


@router.get("/suppliers", response_model=list[SupplierOut])
def list_suppliers(db: Session = Depends(get_db)) -> list[SupplierOut]:
    rows = db.scalars(select(Supplier).order_by(Supplier.name)).all()
    return [present_supplier(row) for row in rows]


@router.post("/suppliers", response_model=SupplierOut, status_code=201)
def create_supplier(payload: SupplierIn, db: Session = Depends(get_db)) -> SupplierOut:
    existing = db.scalar(select(Supplier).where(Supplier.name == payload.name))
    if existing:
        raise HTTPException(status_code=409, detail="Supplier already exists")
    supplier = Supplier(**payload.model_dump())
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return present_supplier(supplier)


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


@router.get("/items", response_model=list[ItemOut])
def list_items(db: Session = Depends(get_db)) -> list[ItemOut]:
    rows = db.scalars(select(Item).order_by(Item.category, Item.name)).all()
    return [present_item(row) for row in rows]


@router.post("/items", response_model=ItemOut, status_code=201)
def create_item(payload: ItemIn, db: Session = Depends(get_db)) -> ItemOut:
    if payload.category not in {item.value for item in ItemCategory}:
        raise HTTPException(status_code=400, detail="Invalid item category")
    if payload.unit not in {item.value for item in Unit}:
        raise HTTPException(status_code=400, detail="Invalid unit")
    if db.scalar(select(Item).where(Item.sku == payload.sku)):
        raise HTTPException(status_code=409, detail="SKU already exists")
    data = payload.model_dump()
    data["quantity_on_hand"] = 0
    data["unit_cost"] = 0
    item = Item(**data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return present_item(item)


@router.put("/items/{item_id}", response_model=ItemOut)
def update_item(item_id: int, payload: ItemIn, db: Session = Depends(get_db)) -> ItemOut:
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    data = payload.model_dump()
    data.pop("quantity_on_hand", None)
    data.pop("unit_cost", None)
    for key, value in data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return present_item(item)


