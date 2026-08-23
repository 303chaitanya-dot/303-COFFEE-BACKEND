from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Item,
    JournalEntry,
    MenuItem,
    MovementReason,
    Purchase,
    PurchaseLine,
    RecipeLine,
    Sale,
    SaleLine,
    StockMovement,
    WasteEvent,
    utcnow,
)
from app.services.ledger import money, post_entry


def qty(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.0001"))


def get_item(db: Session, item_id: int) -> Item:
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


def get_menu_item(db: Session, menu_item_id: int) -> MenuItem:
    menu_item = db.scalar(
        select(MenuItem).options(selectinload(MenuItem.recipe_lines)).where(MenuItem.id == menu_item_id)
    )
    if menu_item is None:
        raise HTTPException(status_code=404, detail="Menu item not found")
    return menu_item


def item_value(item: Item) -> Decimal:
    return money(qty(item.quantity_on_hand) * Decimal(item.unit_cost))


def apply_weighted_average(item: Item, incoming_qty: Decimal, incoming_cost: Decimal) -> None:
    on_hand = qty(item.quantity_on_hand)
    incoming = qty(incoming_qty)
    if incoming <= 0:
        return
    if on_hand <= 0:
        item.unit_cost = money(incoming_cost)
        return
    total_value = (on_hand * Decimal(item.unit_cost)) + (incoming * Decimal(incoming_cost))
    item.unit_cost = money(total_value / (on_hand + incoming))


def record_movement(
    db: Session,
    item: Item,
    quantity_delta: Decimal,
    *,
    reason: str,
    unit_cost: Decimal | None = None,
    ref_type: str | None = None,
    ref_id: int | None = None,
    note: str | None = None,
    allow_negative: bool = False,
) -> StockMovement:
    delta = qty(quantity_delta)
    if delta == 0:
        raise HTTPException(status_code=400, detail="Quantity change cannot be zero")
    next_qty = qty(item.quantity_on_hand) + delta
    if next_qty < 0 and not allow_negative:
        raise HTTPException(
            status_code=400,
            detail=f"Not enough {item.name}: need {abs(delta)} {item.unit}, have {item.quantity_on_hand}",
        )
    item.quantity_on_hand = next_qty
    item.updated_at = utcnow()
    movement = StockMovement(
        item_id=item.id,
        quantity_delta=delta,
        unit_cost=money(unit_cost if unit_cost is not None else item.unit_cost),
        reason=reason,
        ref_type=ref_type,
        ref_id=ref_id,
        note=note,
    )
    db.add(movement)
    db.flush()
    return movement


def recipe_cost(db: Session, menu_item: MenuItem) -> Decimal:
    total = Decimal("0.00")
    for line in menu_item.recipe_lines:
        ingredient = db.get(Item, line.item_id)
        if ingredient is None:
            continue
        total += money(qty(line.quantity) * Decimal(ingredient.unit_cost))
    return total


def explode_recipe(db: Session, menu_item: MenuItem, servings: int) -> list[tuple[Item, Decimal]]:
    if servings <= 0:
        raise HTTPException(status_code=400, detail="Servings must be greater than zero")
    if not menu_item.recipe_lines:
        raise HTTPException(status_code=400, detail=f"{menu_item.name} has no recipe")
    usage: list[tuple[Item, Decimal]] = []
    for line in menu_item.recipe_lines:
        item = get_item(db, line.item_id)
        usage.append((item, qty(line.quantity) * servings))
    return usage


def receive_purchase(
    db: Session,
    *,
    supplier_id: int,
    invoice_number: str | None,
    purchased_at: datetime | None,
    paid: bool,
    notes: str | None,
    lines: list[dict],
) -> Purchase:
    if not lines:
        raise HTTPException(status_code=400, detail="Purchase needs at least one line")

    purchase = Purchase(
        supplier_id=supplier_id,
        invoice_number=invoice_number,
        status="received",
        purchased_at=purchased_at or utcnow(),
        paid=paid,
        notes=notes,
    )
    db.add(purchase)
    db.flush()

    inventory_total = Decimal("0.00")
    for raw in lines:
        item = get_item(db, raw["item_id"])
        quantity = qty(raw["quantity"])
        unit_cost = money(raw["unit_cost"])
        apply_weighted_average(item, quantity, unit_cost)
        record_movement(
            db,
            item,
            quantity,
            reason=MovementReason.purchase.value,
            unit_cost=unit_cost,
            ref_type="purchase",
            ref_id=purchase.id,
        )
        db.add(
            PurchaseLine(
                purchase_id=purchase.id,
                item_id=item.id,
                quantity=quantity,
                unit_cost=unit_cost,
            )
        )
        inventory_total += money(quantity * unit_cost)

    post_entry(
        db,
        memo=f"Purchase #{purchase.id}" + (f" / {invoice_number}" if invoice_number else ""),
        source_type="purchase",
        source_id=purchase.id,
        occurred_on=purchase.purchased_at.date(),
        lines=[
            ("inventory", inventory_total, Decimal("0")),
            ("accounts_payable", Decimal("0"), inventory_total),
        ],
    )
    if paid:
        mark_purchase_paid(db, purchase, inventory_total)
    return purchase


def mark_purchase_paid(db: Session, purchase: Purchase, amount: Decimal | None = None) -> JournalEntry:
    if purchase.paid and amount is None:
        raise HTTPException(status_code=400, detail="Purchase is already marked paid")
    if amount is None:
        amount = purchase_total(purchase)
    purchase.paid = True
    return post_entry(
        db,
        memo=f"Payment for purchase #{purchase.id}",
        source_type="purchase_payment",
        source_id=purchase.id,
        occurred_on=purchase.purchased_at.date(),
        lines=[
            ("accounts_payable", amount, Decimal("0")),
            ("cash", Decimal("0"), amount),
        ],
    )


def purchase_total(purchase: Purchase) -> Decimal:
    return money(sum((qty(line.quantity) * Decimal(line.unit_cost) for line in purchase.lines), Decimal("0")))


def record_sale(
    db: Session,
    *,
    payment_method: str,
    notes: str | None,
    sold_at: datetime | None,
    lines: list[dict],
) -> Sale:
    sale = Sale(
        payment_method=payment_method,
        notes=notes,
        sold_at=sold_at or utcnow(),
    )
    db.add(sale)
    db.flush()

    revenue = Decimal("0.00")
    cogs = Decimal("0.00")
    needed: dict[int, tuple[Item, Decimal]] = {}

    prepared: list[tuple[MenuItem, int, Decimal]] = []
    for raw in lines:
        menu_item = get_menu_item(db, raw["menu_item_id"])
        if not menu_item.active:
            raise HTTPException(status_code=400, detail=f"{menu_item.name} is not on the menu")
        servings = int(raw["quantity"])
        prepared.append((menu_item, servings, Decimal(menu_item.price)))
        for item, used in explode_recipe(db, menu_item, servings):
            current = needed.get(item.id)
            if current:
                needed[item.id] = (item, current[1] + used)
            else:
                needed[item.id] = (item, used)

    for item, used in needed.values():
        if qty(item.quantity_on_hand) < used:
            raise HTTPException(
                status_code=400,
                detail=f"Not enough {item.name}: need {used} {item.unit}, have {item.quantity_on_hand}",
            )

    for menu_item, servings, unit_price in prepared:
        db.add(
            SaleLine(
                sale_id=sale.id,
                menu_item_id=menu_item.id,
                quantity=servings,
                unit_price=money(unit_price),
            )
        )
        revenue += money(unit_price * servings)
        for item, used in explode_recipe(db, menu_item, servings):
            line_cogs = money(used * Decimal(item.unit_cost))
            cogs += line_cogs
            record_movement(
                db,
                item,
                -used,
                reason=MovementReason.sale.value,
                unit_cost=item.unit_cost,
                ref_type="sale",
                ref_id=sale.id,
            )

    post_entry(
        db,
        memo=f"Sale #{sale.id}",
        source_type="sale",
        source_id=sale.id,
        occurred_on=sale.sold_at.date(),
        lines=[
            ("cash", revenue, Decimal("0")),
            ("sales", Decimal("0"), revenue),
            ("cogs", cogs, Decimal("0")),
            ("inventory", Decimal("0"), cogs),
        ],
    )
    return sale


def record_waste(
    db: Session,
    *,
    item_id: int,
    quantity: Decimal,
    reason: str,
    note: str | None,
) -> WasteEvent:
    item = get_item(db, item_id)
    used = qty(quantity)
    cost = money(used * Decimal(item.unit_cost))
    event = WasteEvent(item_id=item.id, quantity=used, reason=reason, note=note)
    db.add(event)
    db.flush()
    record_movement(
        db,
        item,
        -used,
        reason=MovementReason.waste.value,
        unit_cost=item.unit_cost,
        ref_type="waste",
        ref_id=event.id,
        note=reason,
    )
    post_entry(
        db,
        memo=f"Waste: {item.name} ({reason})",
        source_type="waste",
        source_id=event.id,
        lines=[
            ("waste", cost, Decimal("0")),
            ("inventory", Decimal("0"), cost),
        ],
    )
    return event


def adjust_stock(db: Session, *, item_id: int, quantity_delta: Decimal, note: str) -> StockMovement:
    item = get_item(db, item_id)
    delta = qty(quantity_delta)
    cost = money(abs(delta) * Decimal(item.unit_cost))
    movement = record_movement(
        db,
        item,
        delta,
        reason=MovementReason.adjustment.value,
        unit_cost=item.unit_cost,
        ref_type="adjustment",
        note=note,
        allow_negative=False,
    )
    if delta > 0:
        lines = [
            ("inventory", cost, Decimal("0")),
            ("adjustments", Decimal("0"), cost),
        ]
    else:
        lines = [
            ("adjustments", cost, Decimal("0")),
            ("inventory", Decimal("0"), cost),
        ]
    post_entry(
        db,
        memo=f"Stock adjustment: {item.name}",
        source_type="adjustment",
        source_id=movement.id,
        lines=lines,
    )
    return movement


def sale_total(sale: Sale) -> Decimal:
    return money(sum((line.quantity * Decimal(line.unit_price) for line in sale.lines), Decimal("0")))


def sale_cogs(db: Session, sale: Sale) -> Decimal:
    total = Decimal("0.00")
    movements = db.scalars(
        select(StockMovement).where(
            StockMovement.ref_type == "sale",
            StockMovement.ref_id == sale.id,
        )
    ).all()
    for movement in movements:
        total += money(abs(qty(movement.quantity_delta)) * Decimal(movement.unit_cost))
    return total
