from decimal import Decimal

from app.models import MenuItem, RecipeLine, Sauce, SauceLine
from app.services.inventory import receive_named_purchase, receive_purchase, record_sale
from app.services.ledger import account_balance, get_account
from app.services.petpooja import ingest_order


def test_sauce_recipe_deducts_ingredients(db, cafe):
    sauce = Sauce(name="Mocha sauce")
    db.add(sauce)
    db.flush()
    db.add(SauceLine(sauce_id=sauce.id, item_id=cafe["milk"].id, quantity=Decimal("20")))
    mocha = MenuItem(name="House mocha", category="espresso", price=Decimal("260"), active=True)
    db.add(mocha)
    db.flush()
    db.add_all(
        [
            RecipeLine(menu_item_id=mocha.id, item_id=cafe["beans"].id, quantity=Decimal("18")),
            RecipeLine(menu_item_id=mocha.id, sauce_id=sauce.id, quantity=Decimal("1")),
        ]
    )
    receive_purchase(
        db,
        supplier_id=cafe["supplier"].id,
        invoice_number="S",
        purchased_at=None,
        paid=True,
        notes=None,
        lines=[
            {"item_id": cafe["beans"].id, "quantity": Decimal("180"), "unit_cost": Decimal("1.00")},
            {"item_id": cafe["milk"].id, "quantity": Decimal("200"), "unit_cost": Decimal("0.10")},
        ],
    )
    record_sale(db, payment_method="cash", notes=None, sold_at=None, lines=[{"menu_item_id": mocha.id, "quantity": 1}])
    assert cafe["beans"].quantity_on_hand == Decimal("162.0000")
    assert cafe["milk"].quantity_on_hand == Decimal("180.0000")
    assert account_balance(db, get_account(db, "cogs")) == Decimal("20.00")


def test_named_purchase_creates_item(db):
    from app.services.ledger import ensure_chart_of_accounts

    ensure_chart_of_accounts(db)
    purchase = receive_named_purchase(
        db,
        supplier_name="Market",
        invoice_number="M-1",
        purchased_at=None,
        paid=False,
        notes=None,
        lines=[{"name": "Tomatoes", "quantity": Decimal("5"), "price": Decimal("40"), "unit": "kg", "serving_size": Decimal("0.03")}],
    )
    item = purchase.lines[0].item
    assert item.name == "Tomatoes"
    assert item.serving_size == Decimal("0.0300")
    assert item.quantity_on_hand == Decimal("5.0000")
    assert item.unit_cost == Decimal("40.00")


def test_petpooja_order_deducts_mapped_item(db, cafe):
    receive_purchase(
        db,
        supplier_id=cafe["supplier"].id,
        invoice_number="P",
        purchased_at=None,
        paid=True,
        notes=None,
        lines=[
            {"item_id": cafe["beans"].id, "quantity": Decimal("180"), "unit_cost": Decimal("1")},
            {"item_id": cafe["milk"].id, "quantity": Decimal("2200"), "unit_cost": Decimal("0.1")},
            {"item_id": cafe["cup"].id, "quantity": Decimal("10"), "unit_cost": Decimal("5")},
        ],
    )
    record = ingest_order(
        db,
        {"orderID": "PP-100", "order_items": [{"id": "x", "name": "Latte", "quantity": 1}]},
    )
    assert record.status == "applied"
    assert cafe["beans"].quantity_on_hand == Decimal("162.0000")
