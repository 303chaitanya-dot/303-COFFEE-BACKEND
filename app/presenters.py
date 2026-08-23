from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import (
    Account,
    Item,
    JournalEntry,
    MenuItem,
    Purchase,
    Sale,
    StockMovement,
    Supplier,
    WasteEvent,
)
from app.schemas import (
    AccountOut,
    ItemOut,
    JournalEntryOut,
    JournalLineOut,
    MenuItemOut,
    MovementOut,
    PurchaseLineOut,
    PurchaseOut,
    RecipeLineOut,
    SaleLineOut,
    SaleOut,
    SupplierOut,
    WasteOut,
)
from app.services.inventory import item_value, purchase_total, qty, recipe_cost, sale_cogs, sale_total
from app.services.ledger import account_balance, money


def present_supplier(supplier: Supplier) -> SupplierOut:
    return SupplierOut.model_validate(supplier)


def present_item(item: Item) -> ItemOut:
    on_hand = qty(item.quantity_on_hand)
    return ItemOut(
        id=item.id,
        sku=item.sku,
        name=item.name,
        category=item.category,
        unit=item.unit,
        quantity_on_hand=on_hand,
        reorder_point=qty(item.reorder_point),
        par_level=qty(item.par_level),
        unit_cost=money(item.unit_cost),
        active=item.active,
        inventory_value=item_value(item),
        below_reorder=on_hand <= qty(item.reorder_point),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def present_menu_item(db: Session, menu_item: MenuItem) -> MenuItemOut:
    recipe = []
    for line in menu_item.recipe_lines:
        item = db.get(Item, line.item_id)
        recipe.append(
            RecipeLineOut(
                id=line.id,
                item_id=line.item_id,
                item_name=item.name if item else "Unknown",
                item_unit=item.unit if item else "",
                quantity=qty(line.quantity),
            )
        )
    return MenuItemOut(
        id=menu_item.id,
        name=menu_item.name,
        category=menu_item.category,
        price=money(menu_item.price),
        active=menu_item.active,
        recipe_cost=recipe_cost(db, menu_item),
        recipe=recipe,
        created_at=menu_item.created_at,
    )


def present_purchase(purchase: Purchase) -> PurchaseOut:
    lines = [
        PurchaseLineOut(
            id=line.id,
            item_id=line.item_id,
            item_name=line.item.name,
            quantity=qty(line.quantity),
            unit_cost=money(line.unit_cost),
            line_total=money(qty(line.quantity) * Decimal(line.unit_cost)),
        )
        for line in purchase.lines
    ]
    return PurchaseOut(
        id=purchase.id,
        supplier_id=purchase.supplier_id,
        supplier_name=purchase.supplier.name,
        invoice_number=purchase.invoice_number,
        status=purchase.status,
        purchased_at=purchase.purchased_at,
        paid=purchase.paid,
        notes=purchase.notes,
        total=purchase_total(purchase),
        lines=lines,
        created_at=purchase.created_at,
    )


def present_sale(db: Session, sale: Sale) -> SaleOut:
    lines = [
        SaleLineOut(
            id=line.id,
            menu_item_id=line.menu_item_id,
            menu_item_name=line.menu_item.name,
            quantity=line.quantity,
            unit_price=money(line.unit_price),
            line_total=money(line.quantity * Decimal(line.unit_price)),
        )
        for line in sale.lines
    ]
    return SaleOut(
        id=sale.id,
        sold_at=sale.sold_at,
        payment_method=sale.payment_method,
        notes=sale.notes,
        total=sale_total(sale),
        cogs=sale_cogs(db, sale),
        lines=lines,
        created_at=sale.created_at,
    )


def present_waste(event: WasteEvent) -> WasteOut:
    cost = money(qty(event.quantity) * Decimal(event.item.unit_cost))
    return WasteOut(
        id=event.id,
        item_id=event.item_id,
        item_name=event.item.name,
        quantity=qty(event.quantity),
        unit=event.item.unit,
        reason=event.reason,
        note=event.note,
        cost=cost,
        wasted_at=event.wasted_at,
    )


def present_account(db: Session, account: Account) -> AccountOut:
    return AccountOut(
        id=account.id,
        code=account.code,
        name=account.name,
        type=account.type,
        system_key=account.system_key,
        balance=account_balance(db, account),
    )


def present_entry(entry: JournalEntry) -> JournalEntryOut:
    return JournalEntryOut(
        id=entry.id,
        occurred_on=entry.occurred_on,
        memo=entry.memo,
        source_type=entry.source_type,
        source_id=entry.source_id,
        created_at=entry.created_at,
        lines=[
            JournalLineOut(
                account_code=line.account.code,
                account_name=line.account.name,
                debit=money(line.debit),
                credit=money(line.credit),
            )
            for line in entry.lines
        ],
    )


def present_movement(movement: StockMovement) -> MovementOut:
    return MovementOut(
        id=movement.id,
        item_id=movement.item_id,
        item_name=movement.item.name,
        quantity_delta=qty(movement.quantity_delta),
        unit_cost=money(movement.unit_cost),
        reason=movement.reason,
        ref_type=movement.ref_type,
        ref_id=movement.ref_id,
        note=movement.note,
        created_at=movement.created_at,
    )
