from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Item,
    ItemCategory,
    JournalEntry,
    MenuItem,
    MovementReason,
    Purchase,
    PurchaseLine,
    RecipeLine,
    Sale,
    SaleLine,
    Sauce,
    SauceLine,
    StockLot,
    StockMovement,
    Supplier,
    Unit,
    WasteEvent,
    utcnow,
)
from app.services.ledger import money, post_entry


def qty(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.0001"))


UNIT_BASE = {
    "g": ("mass", Decimal("1")),
    "kg": ("mass", Decimal("1000")),
    "ml": ("vol", Decimal("1")),
    "l": ("vol", Decimal("1000")),
    "pcs": ("count", Decimal("1")),
}


def convert_qty(amount: Decimal, from_unit: str, to_unit: str) -> Decimal | None:
    if from_unit == to_unit:
        return qty(amount)
    source = UNIT_BASE.get(from_unit)
    dest = UNIT_BASE.get(to_unit)
    if not source or not dest or source[0] != dest[0]:
        return None
    return qty(Decimal(amount) * source[1] / dest[1])


def price_per_serving(item: Item) -> Decimal:
    serving_in_stock = convert_qty(item.serving_size, item.serving_unit or item.unit, item.unit)
    on_hand = qty(item.quantity_on_hand)
    if serving_in_stock is None or on_hand <= 0:
        return money(0)
    total = Decimal(getattr(item, "total_price", None) or on_hand * Decimal(item.unit_cost))
    return money(total * serving_in_stock / on_hand)


def apply_pack_stock(item: Item, *, qty_per_unit, units_on_hand, total_price) -> None:
    pack = qty(qty_per_unit)
    units = qty(units_on_hand)
    if pack <= 0:
        raise HTTPException(status_code=400, detail="Qty per unit must be greater than zero")
    total = money(total_price)
    stock = qty(pack * units)
    item.qty_per_unit = pack
    item.units_on_hand = units
    item.quantity_on_hand = stock
    item.total_price = total
    item.unit_cost = money(total / stock) if stock > 0 else money(0)


def sync_pack_from_quantity(item: Item) -> None:
    pack = qty(getattr(item, "qty_per_unit", None) or 1)
    if pack <= 0:
        pack = qty(1)
        item.qty_per_unit = pack
    on_hand = qty(item.quantity_on_hand)
    item.units_on_hand = qty(on_hand / pack)
    item.total_price = money(on_hand * Decimal(item.unit_cost))


def delete_items(db: Session, item_ids: list[int]) -> int:
    from app.models import PurchaseLine, RecipeLine, SauceLine, WasteEvent

    deleted = 0
    for item_id in item_ids:
        item = db.get(Item, item_id)
        if item is None:
            continue
        db.execute(delete(StockLot).where(StockLot.item_id == item_id))
        db.execute(delete(StockMovement).where(StockMovement.item_id == item_id))
        db.execute(delete(WasteEvent).where(WasteEvent.item_id == item_id))
        db.execute(delete(PurchaseLine).where(PurchaseLine.item_id == item_id))
        db.execute(delete(RecipeLine).where(RecipeLine.item_id == item_id))
        db.execute(delete(SauceLine).where(SauceLine.item_id == item_id))
        db.delete(item)
        deleted += 1
    db.commit()
    return deleted


def item_split(item: Item, today=None) -> tuple[Decimal, Decimal]:
    from datetime import date

    day = today or date.today()
    on_hand = qty(getattr(item, "quantity_on_hand", None) or 0)
    lots = [lot for lot in (getattr(item, "lots", None) or []) if qty(lot.quantity) > 0]
    if not lots:
        if on_hand <= 0:
            return on_hand, qty(0)
        expiry = getattr(item, "expiry_date", None)
        if expiry is not None and expiry < day:
            return qty(0), on_hand
        return on_hand, qty(0)
    expired = sum(
        (qty(lot.quantity) for lot in lots if lot.expiry_date is not None and lot.expiry_date < day),
        Decimal("0"),
    )
    lot_total = sum((qty(lot.quantity) for lot in lots), Decimal("0"))
    remainder = on_hand - lot_total
    if remainder > 0:
        expiry = getattr(item, "expiry_date", None)
        if expiry is not None and expiry < day:
            expired += remainder
    expired = qty(min(expired, max(on_hand, Decimal("0"))))
    return qty(on_hand - expired), expired


def expiry_status(item: Item, today=None) -> str:
    from datetime import date

    day = today or date.today()
    _good, expired = item_split(item, day)
    if expired > 0:
        return "expired"
    expiry = getattr(item, "expiry_date", None)
    if expiry is not None and expiry < day:
        return "expired"
    for lot in getattr(item, "lots", None) or []:
        if qty(lot.quantity) <= 0 or lot.expiry_date is None:
            continue
        days_left = (lot.expiry_date - day).days
        if 0 <= days_left <= 7:
            return "expiring"
    if expiry is None:
        return "ok"
    if (expiry - day).days <= 7:
        return "expiring"
    return "ok"


def add_stock_lot(db: Session, item: Item, quantity, expiry_date) -> None:
    amount = qty(quantity)
    if amount <= 0 or item.id is None:
        return
    lots = db.scalars(select(StockLot).where(StockLot.item_id == item.id)).all()
    for lot in lots:
        if lot.expiry_date == expiry_date:
            lot.quantity = qty(lot.quantity) + amount
            return
    db.add(StockLot(item_id=item.id, quantity=amount, expiry_date=expiry_date, received_at=utcnow()))
    db.flush()


def consume_stock_lots(db: Session, item: Item, quantity, *, prefer_expired: bool = False) -> None:
    from datetime import date

    remaining = qty(quantity)
    if remaining <= 0 or item.id is None:
        return
    today = date.today()
    lots = [
        lot
        for lot in db.scalars(select(StockLot).where(StockLot.item_id == item.id)).all()
        if qty(lot.quantity) > 0
    ]

    def sort_key(lot: StockLot):
        expired = lot.expiry_date is not None and lot.expiry_date < today
        expiry_ord = lot.expiry_date.toordinal() if lot.expiry_date else 10**9
        received = lot.received_at or utcnow()
        return (not expired if prefer_expired else expired, expiry_ord, received)

    for lot in sorted(lots, key=sort_key):
        if remaining <= 0:
            break
        take = min(qty(lot.quantity), remaining)
        lot.quantity = qty(lot.quantity) - take
        remaining -= take
        if lot.quantity <= 0:
            db.delete(lot)
    db.flush()


def apply_qty_delta_to_lots(
    db: Session,
    item: Item,
    delta,
    *,
    expiry_date,
    prefer_expired: bool = False,
) -> None:
    change = qty(delta)
    if change > 0:
        add_stock_lot(db, item, change, expiry_date)
    elif change < 0:
        consume_stock_lots(db, item, -change, prefer_expired=prefer_expired)


def mark_expired_good(db: Session, item: Item, quantity) -> Decimal:
    from datetime import date

    remaining = qty(quantity)
    if remaining <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be greater than zero")
    today = date.today()
    lots = [
        lot
        for lot in db.scalars(select(StockLot).where(StockLot.item_id == item.id)).all()
        if qty(lot.quantity) > 0 and lot.expiry_date is not None and lot.expiry_date < today
    ]
    lots.sort(key=lambda lot: (lot.expiry_date or today, lot.received_at or utcnow()))
    moved = qty(0)
    for lot in lots:
        if remaining <= 0:
            break
        take = min(qty(lot.quantity), remaining)
        lot.quantity = qty(lot.quantity) - take
        remaining -= take
        moved += take
        if lot.quantity <= 0:
            db.delete(lot)
    if moved <= 0:
        raise HTTPException(status_code=400, detail="No expired quantity to mark as good")
    add_stock_lot(db, item, moved, None)
    db.flush()
    return moved


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
    sync_pack_from_quantity(item)
    apply_qty_delta_to_lots(
        db,
        item,
        delta,
        expiry_date=item.expiry_date,
        prefer_expired=reason == MovementReason.waste.value,
    )
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


def usage_in_stock(item: Item, amount, from_unit: str | None = None) -> Decimal:
    source = from_unit or item.unit
    converted = convert_qty(qty(amount), source, item.unit)
    if converted is None:
        return qty(amount)
    return converted


def sauce_cost(db: Session, sauce: Sauce) -> Decimal:
    total = Decimal("0.00")
    lines = sauce.lines or db.scalars(select(SauceLine).where(SauceLine.sauce_id == sauce.id)).all()
    for line in lines:
        ingredient = db.get(Item, line.item_id)
        if ingredient is None:
            continue
        total += money(usage_in_stock(ingredient, line.quantity) * Decimal(ingredient.unit_cost))
    return total


def line_price_used(db: Session, line: RecipeLine) -> Decimal:
    if line.sauce_id:
        sauce = db.get(Sauce, line.sauce_id)
        if sauce is None:
            return money(0)
        return money(qty(line.quantity) * sauce_cost(db, sauce))
    if line.item_id:
        ingredient = db.get(Item, line.item_id)
        if ingredient is None:
            return money(0)
        return money(usage_in_stock(ingredient, line.quantity, getattr(line, "unit", None)) * Decimal(ingredient.unit_cost))
    return money(0)


def recipe_cost(db: Session, menu_item: MenuItem) -> Decimal:
    total = Decimal("0.00")
    for line in menu_item.recipe_lines:
        total += line_price_used(db, line)
    return total


def _add_usage(needed: dict[int, tuple[Item, Decimal]], item: Item, used: Decimal) -> None:
    current = needed.get(item.id)
    needed[item.id] = (item, (current[1] if current else Decimal("0")) + used)


def explode_recipe(db: Session, menu_item: MenuItem, servings: int) -> list[tuple[Item, Decimal]]:
    if servings <= 0:
        raise HTTPException(status_code=400, detail="Servings must be greater than zero")
    if not menu_item.recipe_lines:
        raise HTTPException(status_code=400, detail=f"{menu_item.name} has no recipe")
    needed: dict[int, tuple[Item, Decimal]] = {}
    for line in menu_item.recipe_lines:
        if line.sauce_id:
            sauce = db.get(Sauce, line.sauce_id)
            if sauce is None:
                raise HTTPException(status_code=400, detail="Sauce is missing from a recipe")
            sauce_lines = db.scalars(select(SauceLine).where(SauceLine.sauce_id == sauce.id)).all()
            if not sauce_lines:
                raise HTTPException(status_code=400, detail=f"{sauce.name} has no ingredients")
            for sauce_line in sauce_lines:
                item = get_item(db, sauce_line.item_id)
                _add_usage(needed, item, usage_in_stock(item, sauce_line.quantity) * qty(line.quantity) * servings)
        elif line.item_id:
            item = get_item(db, line.item_id)
            _add_usage(needed, item, usage_in_stock(item, line.quantity, getattr(line, "unit", None)) * servings)
        else:
            raise HTTPException(status_code=400, detail="Recipe line needs an ingredient or a sauce")
    return list(needed.values())


def make_sku(db: Session, name: str) -> str:
    base = "".join(char for char in name.upper() if char.isalnum())[:8] or "ITEM"
    sku = base
    suffix = 1
    while db.scalar(select(Item).where(Item.sku == sku)):
        suffix += 1
        sku = f"{base}{suffix}"
    return sku


def upsert_named_item(db: Session, payload: dict) -> tuple[Item, str]:
    name = str(payload["name"]).strip()
    category = str(payload.get("category") or "other").strip().lower()
    unit = str(payload["unit"]).strip().lower()
    serving_unit = str(payload.get("serving_unit") or unit).strip().lower()
    if category not in {item.value for item in ItemCategory}:
        raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
    if unit not in {item.value for item in Unit}:
        raise HTTPException(status_code=400, detail=f"Invalid stock unit: {unit}")
    if serving_unit not in {item.value for item in Unit}:
        raise HTTPException(status_code=400, detail=f"Invalid serving unit: {serving_unit}")
    serving_size = qty(payload.get("serving_size") or 1)
    if convert_qty(serving_size, serving_unit, unit) is None:
        raise HTTPException(
            status_code=400,
            detail=f"Serving unit {serving_unit} does not match stock unit {unit}",
        )
    item = db.scalar(select(Item).where(func.lower(Item.name) == name.lower()))
    created = item is None
    if created:
        item = Item(sku=make_sku(db, name), name=name, active=True)
        db.add(item)
    item.name = name
    item.category = category
    item.unit = unit
    item.serving_size = serving_size
    item.serving_unit = serving_unit
    item.reorder_point = qty(payload.get("reorder_point") or 0)
    item.expiry_date = payload.get("expiry_date")
    previous = qty(item.quantity_on_hand) if item.id else qty(0)
    apply_pack_stock(
        item,
        qty_per_unit=payload.get("qty_per_unit") or 1,
        units_on_hand=payload.get("units_on_hand") or 0,
        total_price=payload.get("price") or 0,
    )
    db.flush()
    apply_qty_delta_to_lots(
        db,
        item,
        qty(item.quantity_on_hand) - previous,
        expiry_date=item.expiry_date,
        prefer_expired=True,
    )
    return item, "created" if created else "updated"


def get_or_create_supplier(db: Session, name: str | None) -> Supplier:
    label = (name or "Walk-in purchase").strip() or "Walk-in purchase"
    supplier = db.scalar(select(Supplier).where(func.lower(Supplier.name) == label.lower()))
    if supplier:
        return supplier
    supplier = Supplier(name=label)
    db.add(supplier)
    db.flush()
    return supplier


def get_or_create_item(
    db: Session,
    *,
    name: str,
    unit: str,
    category: str,
    serving_size: Decimal | None,
) -> Item:
    item = db.scalar(select(Item).where(func.lower(Item.name) == name.strip().lower()))
    if item:
        if serving_size is not None:
            item.serving_size = qty(serving_size)
        return item
    item = Item(
        sku=make_sku(db, name),
        name=name.strip(),
        category=category,
        unit=unit,
        serving_size=qty(serving_size or 1),
        qty_per_unit=Decimal("1"),
        units_on_hand=Decimal("0"),
        quantity_on_hand=Decimal("0"),
        total_price=Decimal("0"),
        unit_cost=Decimal("0"),
        active=True,
    )
    db.add(item)
    db.flush()
    return item


def receive_named_purchase(
    db: Session,
    *,
    supplier_name: str | None,
    invoice_number: str | None,
    purchased_at: datetime | None,
    paid: bool,
    notes: str | None,
    lines: list[dict],
) -> Purchase:
    resolved = []
    for raw in lines:
        item = get_or_create_item(
            db,
            name=raw["name"],
            unit=raw.get("unit") or "pcs",
            category=raw.get("category") or "other",
            serving_size=raw.get("serving_size"),
        )
        quantity = qty(raw["quantity"])
        if raw.get("unit_cost") is not None:
            unit_cost = money(raw["unit_cost"])
        elif raw.get("price") is not None:
            unit_cost = money(raw["price"])
        elif raw.get("line_total") is not None:
            unit_cost = money(Decimal(str(raw["line_total"])) / quantity)
        else:
            raise HTTPException(status_code=400, detail=f"Price missing for {item.name}")
        resolved.append({"item_id": item.id, "quantity": quantity, "unit_cost": unit_cost})
    supplier = get_or_create_supplier(db, supplier_name)
    return receive_purchase(
        db,
        supplier_id=supplier.id,
        invoice_number=invoice_number,
        purchased_at=purchased_at,
        paid=paid,
        notes=notes,
        lines=resolved,
    )


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
                allow_negative=True,
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
        allow_negative=True,
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
        allow_negative=True,
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
