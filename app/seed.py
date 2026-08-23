from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Item, MenuItem, RecipeLine, Supplier
from app.services.inventory import receive_purchase, record_sale
from app.services.ledger import ensure_chart_of_accounts, post_entry


def seed_if_empty(db: Session) -> None:
    ensure_chart_of_accounts(db)
    if db.scalar(select(func.count(Item.id))) > 0:
        db.commit()
        return

    post_entry(
        db,
        memo="Opening cash float",
        source_type="opening",
        source_id=None,
        lines=[
            ("cash", Decimal("50000.00"), Decimal("0")),
            ("equity", Decimal("0"), Decimal("50000.00")),
        ],
    )

    suppliers = [
        Supplier(name="Highland Roastery", contact_name="Asha", phone="9876500011", email="orders@highland.example"),
        Supplier(name="Dairy Cooperative", contact_name="Ravi", phone="9876500022", email="milk@coop.example"),
        Supplier(name="Cafe Pack Co", contact_name="Meera", phone="9876500033", email="hello@cafepack.example"),
        Supplier(name="Bakery Lane", contact_name="Irfan", phone="9876500044", email="bake@lanebakery.example"),
    ]
    db.add_all(suppliers)
    db.flush()
    by_name = {supplier.name: supplier for supplier in suppliers}

    items = {
        "ESP-BEAN": Item(
            sku="ESP-BEAN",
            name="House espresso beans",
            category="coffee",
            unit="g",
            reorder_point=2000,
            par_level=8000,
        ),
        "FILTER-BEAN": Item(
            sku="FILTER-BEAN",
            name="Filter coffee beans",
            category="coffee",
            unit="g",
            reorder_point=1000,
            par_level=4000,
        ),
        "MILK": Item(sku="MILK", name="Whole milk", category="dairy", unit="ml", reorder_point=8000, par_level=20000),
        "OAT": Item(sku="OAT", name="Oat milk", category="dairy", unit="ml", reorder_point=2000, par_level=6000),
        "SYRUP": Item(sku="SYRUP", name="Vanilla syrup", category="dry_goods", unit="ml", reorder_point=400, par_level=1500),
        "CHOCO": Item(sku="CHOCO", name="Chocolate sauce", category="dry_goods", unit="ml", reorder_point=400, par_level=1200),
        "CHAI": Item(sku="CHAI", name="Masala chai concentrate", category="beverages", unit="ml", reorder_point=800, par_level=2500),
        "CUP12": Item(sku="CUP12", name="12oz paper cup", category="packaging", unit="pcs", reorder_point=100, par_level=400),
        "LID12": Item(sku="LID12", name="12oz lid", category="packaging", unit="pcs", reorder_point=100, par_level=400),
        "CROISSANT": Item(
            sku="CROISSANT",
            name="Butter croissant",
            category="bakery",
            unit="pcs",
            reorder_point=6,
            par_level=24,
        ),
    }
    db.add_all(items.values())
    db.flush()

    receive_purchase(
        db,
        supplier_id=by_name["Highland Roastery"].id,
        invoice_number="HR-1042",
        purchased_at=None,
        paid=True,
        notes="Opening coffee stock",
        lines=[
            {"item_id": items["ESP-BEAN"].id, "quantity": Decimal("10000"), "unit_cost": Decimal("1.20")},
            {"item_id": items["FILTER-BEAN"].id, "quantity": Decimal("5000"), "unit_cost": Decimal("1.40")},
        ],
    )
    receive_purchase(
        db,
        supplier_id=by_name["Dairy Cooperative"].id,
        invoice_number="DC-887",
        purchased_at=None,
        paid=False,
        notes="Weekly dairy",
        lines=[
            {"item_id": items["MILK"].id, "quantity": Decimal("20000"), "unit_cost": Decimal("0.08")},
            {"item_id": items["OAT"].id, "quantity": Decimal("6000"), "unit_cost": Decimal("0.14")},
        ],
    )
    receive_purchase(
        db,
        supplier_id=by_name["Cafe Pack Co"].id,
        invoice_number="CP-221",
        purchased_at=None,
        paid=True,
        notes="Cups and lids",
        lines=[
            {"item_id": items["CUP12"].id, "quantity": Decimal("400"), "unit_cost": Decimal("4.50")},
            {"item_id": items["LID12"].id, "quantity": Decimal("400"), "unit_cost": Decimal("2.00")},
            {"item_id": items["SYRUP"].id, "quantity": Decimal("1500"), "unit_cost": Decimal("0.35")},
            {"item_id": items["CHOCO"].id, "quantity": Decimal("1200"), "unit_cost": Decimal("0.40")},
            {"item_id": items["CHAI"].id, "quantity": Decimal("2500"), "unit_cost": Decimal("0.22")},
        ],
    )
    receive_purchase(
        db,
        supplier_id=by_name["Bakery Lane"].id,
        invoice_number="BL-19",
        purchased_at=None,
        paid=True,
        notes="Morning pastry",
        lines=[{"item_id": items["CROISSANT"].id, "quantity": Decimal("24"), "unit_cost": Decimal("55.00")}],
    )

    recipes = [
        (
            "Espresso",
            "espresso",
            Decimal("140.00"),
            [("ESP-BEAN", "18"), ("CUP12", "1")],
        ),
        (
            "Americano",
            "espresso",
            Decimal("160.00"),
            [("ESP-BEAN", "18"), ("CUP12", "1"), ("LID12", "1")],
        ),
        (
            "Cappuccino",
            "espresso",
            Decimal("200.00"),
            [("ESP-BEAN", "18"), ("MILK", "140"), ("CUP12", "1"), ("LID12", "1")],
        ),
        (
            "Latte",
            "espresso",
            Decimal("220.00"),
            [("ESP-BEAN", "18"), ("MILK", "220"), ("CUP12", "1"), ("LID12", "1")],
        ),
        (
            "Oat latte",
            "espresso",
            Decimal("250.00"),
            [("ESP-BEAN", "18"), ("OAT", "220"), ("CUP12", "1"), ("LID12", "1")],
        ),
        (
            "Mocha",
            "espresso",
            Decimal("260.00"),
            [("ESP-BEAN", "18"), ("MILK", "200"), ("CHOCO", "25"), ("CUP12", "1"), ("LID12", "1")],
        ),
        (
            "Vanilla latte",
            "espresso",
            Decimal("240.00"),
            [("ESP-BEAN", "18"), ("MILK", "220"), ("SYRUP", "15"), ("CUP12", "1"), ("LID12", "1")],
        ),
        (
            "Filter coffee",
            "coffee",
            Decimal("180.00"),
            [("FILTER-BEAN", "18"), ("CUP12", "1"), ("LID12", "1")],
        ),
        (
            "Chai latte",
            "tea",
            Decimal("190.00"),
            [("CHAI", "80"), ("MILK", "160"), ("CUP12", "1"), ("LID12", "1")],
        ),
        (
            "Butter croissant",
            "food",
            Decimal("120.00"),
            [("CROISSANT", "1")],
        ),
    ]

    for name, category, price, lines in recipes:
        menu_item = MenuItem(name=name, category=category, price=price, active=True)
        db.add(menu_item)
        db.flush()
        for sku, quantity in lines:
            db.add(RecipeLine(menu_item_id=menu_item.id, item_id=items[sku].id, quantity=Decimal(quantity)))

    db.flush()
    latte = db.scalar(select(MenuItem).where(MenuItem.name == "Latte"))
    croissant = db.scalar(select(MenuItem).where(MenuItem.name == "Butter croissant"))
    filter_coffee = db.scalar(select(MenuItem).where(MenuItem.name == "Filter coffee"))
    record_sale(
        db,
        payment_method="upi",
        notes="Opening sample ticket",
        sold_at=None,
        lines=[
            {"menu_item_id": latte.id, "quantity": 2},
            {"menu_item_id": croissant.id, "quantity": 1},
            {"menu_item_id": filter_coffee.id, "quantity": 1},
        ],
    )
    db.commit()
