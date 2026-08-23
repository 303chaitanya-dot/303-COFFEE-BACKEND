from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.services.inventory import receive_purchase, record_sale, record_waste
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


def test_sale_rejects_insufficient_stock(db, cafe):
    with pytest.raises(HTTPException) as error:
        record_sale(
            db,
            payment_method="cash",
            notes=None,
            sold_at=None,
            lines=[{"menu_item_id": cafe["latte"].id, "quantity": 1}],
        )
    assert error.value.status_code == 400
    assert "Not enough" in error.value.detail


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
