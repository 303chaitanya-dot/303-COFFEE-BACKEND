from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

from app.services.inventory import (
    convert_qty,
    expiry_status,
    price_per_serving,
    receive_purchase,
    record_sale,
    record_waste,
)
from app.services.ledger import account_balance, get_account


def test_purchase_increases_stock_and_uses_weighted_average(db, cafe):
    receive_purchase(
        db,
        supplier_id=cafe["supplier"].id,
        invoice_number="A-1",
        purchased_at=None,
        paid=False,
        notes=None,
        lines=[{"item_id": cafe["beans"].id, "quantity": Decimal("1000"), "unit_cost": Decimal("1.00")}],
    )
    receive_purchase(
        db,
        supplier_id=cafe["supplier"].id,
        invoice_number="A-2",
        purchased_at=None,
        paid=False,
        notes=None,
        lines=[{"item_id": cafe["beans"].id, "quantity": Decimal("1000"), "unit_cost": Decimal("3.00")}],
    )

    assert cafe["beans"].quantity_on_hand == Decimal("2000.0000")
    assert cafe["beans"].unit_cost == Decimal("2.00")
    assert account_balance(db, get_account(db, "inventory")) == Decimal("4000.00")
    assert account_balance(db, get_account(db, "accounts_payable")) == Decimal("4000.00")


def test_sale_deducts_recipe_and_posts_cogs(db, cafe):
    receive_purchase(
        db,
        supplier_id=cafe["supplier"].id,
        invoice_number="OPEN",
        purchased_at=None,
        paid=True,
        notes=None,
        lines=[
            {"item_id": cafe["beans"].id, "quantity": Decimal("180"), "unit_cost": Decimal("1.00")},
            {"item_id": cafe["milk"].id, "quantity": Decimal("2200"), "unit_cost": Decimal("0.10")},
            {"item_id": cafe["cup"].id, "quantity": Decimal("10"), "unit_cost": Decimal("5.00")},
        ],
    )
    sale = record_sale(
        db,
        payment_method="upi",
        notes=None,
        sold_at=None,
        lines=[{"menu_item_id": cafe["latte"].id, "quantity": 2}],
    )

    assert cafe["beans"].quantity_on_hand == Decimal("144.0000")
    assert cafe["milk"].quantity_on_hand == Decimal("1760.0000")
    assert cafe["cup"].quantity_on_hand == Decimal("8.0000")
    assert account_balance(db, get_account(db, "sales")) == Decimal("440.00")
    assert account_balance(db, get_account(db, "cogs")) == Decimal("90.00")
    assert sale.id


def test_sale_allows_negative_stock(db, cafe):
    record_sale(
        db,
        payment_method="cash",
        notes=None,
        sold_at=None,
        lines=[{"menu_item_id": cafe["latte"].id, "quantity": 1}],
    )
    assert cafe["beans"].quantity_on_hand == Decimal("-18.0000")
    assert cafe["milk"].quantity_on_hand == Decimal("-220.0000")
    assert cafe["cup"].quantity_on_hand == Decimal("-1.0000")


def test_waste_writes_off_inventory(db, cafe):
    receive_purchase(
        db,
        supplier_id=cafe["supplier"].id,
        invoice_number="W",
        purchased_at=None,
        paid=True,
        notes=None,
        lines=[{"item_id": cafe["milk"].id, "quantity": Decimal("1000"), "unit_cost": Decimal("0.10")}],
    )
    record_waste(db, item_id=cafe["milk"].id, quantity=Decimal("100"), reason="Spoilage", note=None)
    assert cafe["milk"].quantity_on_hand == Decimal("900.0000")
    assert account_balance(db, get_account(db, "waste")) == Decimal("10.00")


def test_price_per_serving_from_total_spend():
    item = SimpleNamespace(
        serving_size=Decimal("15"),
        serving_unit="ml",
        unit="ml",
        unit_cost=Decimal("0.20"),
        quantity_on_hand=Decimal("1000"),
        total_price=Decimal("200"),
    )
    assert price_per_serving(item) == Decimal("3.00")
    item.serving_unit = "pcs"
    assert price_per_serving(item) == Decimal("0.00")
    assert convert_qty(Decimal("1"), "kg", "g") == Decimal("1000.0000")


def test_expiry_status_windows():
    today = date(2026, 8, 23)
    assert expiry_status(SimpleNamespace(expiry_date=None), today) == "ok"
    assert expiry_status(SimpleNamespace(expiry_date=today - timedelta(days=1)), today) == "expired"
    assert expiry_status(SimpleNamespace(expiry_date=today + timedelta(days=7)), today) == "expiring"
    assert expiry_status(SimpleNamespace(expiry_date=today + timedelta(days=8)), today) == "ok"
