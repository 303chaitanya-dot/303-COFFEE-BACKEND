from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import PaymentMethod, Purchase, PurchaseLine, Sale, SaleLine, StockMovement, WasteEvent
from app.presenters import present_movement, present_purchase, present_sale, present_waste
from app.schemas import (
    AdjustmentIn,
    MessageOut,
    MovementOut,
    NamedPurchaseIn,
    PurchaseIn,
    PurchaseOut,
    SaleIn,
    SaleOut,
    SalesImportOut,
    WasteIn,
    WasteOut,
)
from app.services.inventory import (
    adjust_stock,
    mark_purchase_paid,
    receive_named_purchase,
    receive_purchase,
    record_sale,
    record_waste,
)
from app.services.sales_import import apply_item_wise_report

router = APIRouter()

PURCHASE_LOAD = (selectinload(Purchase.supplier), selectinload(Purchase.lines).selectinload(PurchaseLine.item))
SALE_LOAD = selectinload(Sale.lines).selectinload(SaleLine.menu_item)


@router.get("/purchases", response_model=list[PurchaseOut])
def list_purchases(db: Session = Depends(get_db)) -> list[PurchaseOut]:
    rows = db.scalars(select(Purchase).options(*PURCHASE_LOAD).order_by(Purchase.purchased_at.desc())).all()
    return [present_purchase(row) for row in rows]


@router.post("/purchases", response_model=PurchaseOut, status_code=201)
def create_purchase(payload: PurchaseIn, db: Session = Depends(get_db)) -> PurchaseOut:
    purchase = receive_purchase(
        db,
        supplier_id=payload.supplier_id,
        invoice_number=payload.invoice_number,
        purchased_at=payload.purchased_at,
        paid=payload.paid,
        notes=payload.notes,
        lines=[line.model_dump() for line in payload.lines],
    )
    db.commit()
    purchase = db.scalar(select(Purchase).options(*PURCHASE_LOAD).where(Purchase.id == purchase.id))
    return present_purchase(purchase)


@router.post("/purchases/quick", response_model=PurchaseOut, status_code=201)
def create_named_purchase(payload: NamedPurchaseIn, db: Session = Depends(get_db)) -> PurchaseOut:
    purchase = receive_named_purchase(
        db,
        supplier_name=payload.supplier_name,
        invoice_number=payload.invoice_number,
        purchased_at=None,
        paid=payload.paid,
        notes=payload.notes,
        lines=[line.model_dump() for line in payload.lines],
    )
    db.commit()
    purchase = db.scalar(select(Purchase).options(*PURCHASE_LOAD).where(Purchase.id == purchase.id))
    return present_purchase(purchase)


@router.post("/purchases/{purchase_id}/pay", response_model=MessageOut)
def pay_purchase(purchase_id: int, db: Session = Depends(get_db)) -> MessageOut:
    purchase = db.scalar(select(Purchase).options(selectinload(Purchase.lines)).where(Purchase.id == purchase_id))
    if purchase is None:
        raise HTTPException(status_code=404, detail="Purchase not found")
    mark_purchase_paid(db, purchase)
    db.commit()
    return MessageOut(detail=f"Purchase #{purchase.id} marked paid")


@router.post("/sales/import", response_model=SalesImportOut)
def import_petpooja_sales(file: UploadFile = File(...), db: Session = Depends(get_db)) -> SalesImportOut:
    content = file.file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    result = apply_item_wise_report(db, file.filename or "sales.xlsx", content)
    db.commit()
    return SalesImportOut(**result)


@router.get("/sales", response_model=list[SaleOut])
def list_sales(db: Session = Depends(get_db)) -> list[SaleOut]:
    rows = db.scalars(select(Sale).options(SALE_LOAD).order_by(Sale.sold_at.desc())).all()
    return [present_sale(db, row) for row in rows]


@router.post("/sales", response_model=SaleOut, status_code=201)
def create_sale(payload: SaleIn, db: Session = Depends(get_db)) -> SaleOut:
    if payload.payment_method not in {item.value for item in PaymentMethod}:
        raise HTTPException(status_code=400, detail="Invalid payment method")
    sale = record_sale(
        db,
        payment_method=payload.payment_method,
        notes=payload.notes,
        sold_at=payload.sold_at,
        lines=[line.model_dump() for line in payload.lines],
    )
    db.commit()
    sale = db.scalar(select(Sale).options(SALE_LOAD).where(Sale.id == sale.id))
    return present_sale(db, sale)


@router.get("/waste", response_model=list[WasteOut])
def list_waste(db: Session = Depends(get_db)) -> list[WasteOut]:
    rows = db.scalars(select(WasteEvent).options(selectinload(WasteEvent.item)).order_by(WasteEvent.wasted_at.desc())).all()
    return [present_waste(row) for row in rows]


@router.post("/waste", response_model=WasteOut, status_code=201)
def create_waste(payload: WasteIn, db: Session = Depends(get_db)) -> WasteOut:
    event = record_waste(
        db,
        item_id=payload.item_id,
        quantity=payload.quantity,
        reason=payload.reason,
        note=payload.note,
    )
    db.commit()
    event = db.scalar(select(WasteEvent).options(selectinload(WasteEvent.item)).where(WasteEvent.id == event.id))
    return present_waste(event)


@router.post("/adjustments", response_model=MovementOut, status_code=201)
def create_adjustment(payload: AdjustmentIn, db: Session = Depends(get_db)) -> MovementOut:
    movement = adjust_stock(
        db,
        item_id=payload.item_id,
        quantity_delta=payload.quantity_delta,
        note=payload.note,
    )
    db.commit()
    movement = db.scalar(
        select(StockMovement).options(selectinload(StockMovement.item)).where(StockMovement.id == movement.id)
    )
    return present_movement(movement)


@router.get("/movements", response_model=list[MovementOut])
def list_movements(limit: int = 100, db: Session = Depends(get_db)) -> list[MovementOut]:
    rows = db.scalars(
        select(StockMovement)
        .options(selectinload(StockMovement.item))
        .order_by(StockMovement.created_at.desc())
        .limit(limit)
    ).all()
    return [present_movement(row) for row in rows]
