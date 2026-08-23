import json
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import MenuItem, PetPoojaMapping, PetPoojaOrder
from app.services.inventory import record_sale


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def parse_order_payload(payload: dict) -> tuple[str, list[dict]]:
    body = payload.get("orderinfo") or payload.get("order") or payload
    order_id = (
        body.get("OrderID")
        or body.get("orderID")
        or body.get("order_id")
        or payload.get("orderID")
        or payload.get("order_id")
    )
    if not order_id:
        raise HTTPException(status_code=400, detail="Pet Pooja payload is missing an order id")

    raw_items = (
        body.get("OrderItem")
        or body.get("order_items")
        or body.get("items")
        or payload.get("OrderItem")
        or payload.get("order_items")
        or payload.get("items")
        or []
    )
    items = []
    for raw in _as_list(raw_items):
        name = raw.get("name") or raw.get("itemname") or raw.get("item_name") or raw.get("title")
        quantity = raw.get("quantity") or raw.get("qty") or raw.get("item_quantity") or 1
        external_id = raw.get("id") or raw.get("item_id") or raw.get("itemid")
        price = raw.get("price") or raw.get("item_price") or raw.get("final_price")
        if not name and not external_id:
            continue
        items.append(
            {
                "external_id": str(external_id) if external_id is not None else None,
                "name": (name or "").strip(),
                "quantity": int(Decimal(str(quantity))),
                "price": price,
            }
        )
    if not items:
        raise HTTPException(status_code=400, detail="Pet Pooja payload has no order items")
    return str(order_id), items


def resolve_menu_item(db: Session, external_id: str | None, name: str) -> MenuItem | None:
    if external_id:
        mapped = db.scalar(
            select(PetPoojaMapping).where(PetPoojaMapping.external_item_id == external_id)
        )
        if mapped:
            return db.get(MenuItem, mapped.menu_item_id)
        by_id = db.scalar(select(MenuItem).where(MenuItem.petpooja_item_id == external_id))
        if by_id:
            return by_id
    if name:
        mapped = db.scalar(
            select(PetPoojaMapping).where(func.lower(PetPoojaMapping.external_name) == name.lower())
        )
        if mapped:
            return db.get(MenuItem, mapped.menu_item_id)
        return db.scalar(select(MenuItem).where(func.lower(MenuItem.name) == name.lower()))
    return None


def ingest_order(db: Session, payload: dict) -> PetPoojaOrder:
    order_id, items = parse_order_payload(payload)
    existing = db.scalar(select(PetPoojaOrder).where(PetPoojaOrder.external_order_id == order_id))
    if existing:
        return existing

    sale_lines = []
    unmapped = []
    for item in items:
        menu_item = resolve_menu_item(db, item["external_id"], item["name"])
        if menu_item is None:
            unmapped.append(item)
            continue
        sale_lines.append({"menu_item_id": menu_item.id, "quantity": item["quantity"]})

    record = PetPoojaOrder(
        external_order_id=order_id,
        raw_payload=json.dumps(payload),
        unmapped_json=json.dumps(unmapped) if unmapped else None,
        status="unmapped" if unmapped else "applied",
    )
    db.add(record)
    db.flush()

    if unmapped:
        return record

    sale = record_sale(
        db,
        payment_method="other",
        notes=f"Pet Pooja order {order_id}",
        sold_at=None,
        lines=sale_lines,
    )
    record.sale_id = sale.id
    record.status = "applied"
    return record
