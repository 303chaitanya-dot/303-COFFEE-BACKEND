from datetime import date
from decimal import Decimal

from app.services.sheets import parse_sheet_csv, sheet_export_url


def test_sheet_export_url_from_edit_link():
    url = sheet_export_url("https://docs.google.com/spreadsheets/d/abc123XYZ/edit?usp=sharing#gid=42")
    assert url == "https://docs.google.com/spreadsheets/d/abc123XYZ/export?format=csv&gid=42"


def test_parse_sheet_csv_upserts_pack_fields():
    csv_text = """name,category,unit,qty_per_unit,units_on_hand,price,serving_size,serving_unit,reorder_point,expiry
Soy sauce,dry_goods,ml,250,4,200,15,ml,2,23/08/2028
"""
    rows = parse_sheet_csv(csv_text)
    assert rows[0]["name"] == "Soy sauce"
    assert rows[0]["qty_per_unit"] == Decimal("250")
    assert rows[0]["units_on_hand"] == Decimal("4")
    assert rows[0]["price"] == Decimal("200")
    assert rows[0]["expiry_date"] == date(2028, 8, 23)


def test_parse_menu_csv():
    from app.services.sheets import parse_menu_csv

    rows = parse_menu_csv(
        """dish,category,price,ingredient,qty,unit
Latte,espresso,220,Whole milk,200,ml
Latte,espresso,220,Espresso beans,18,g
"""
    )
    assert len(rows) == 2
    assert rows[0]["dish"] == "Latte"
    assert rows[1]["qty"] == Decimal("18")


def test_menu_sheet_sync_builds_recipe(client, monkeypatch):
    client.post(
        "/api/items",
        json={
            "name": "Whole milk",
            "category": "dairy",
            "unit": "l",
            "qty_per_unit": "1",
            "units_on_hand": "10",
            "price": "800",
            "serving_size": "200",
            "serving_unit": "ml",
        },
    )
    client.post(
        "/api/items",
        json={
            "name": "Espresso beans",
            "category": "coffee",
            "unit": "g",
            "qty_per_unit": "1000",
            "units_on_hand": "2",
            "price": "2000",
            "serving_size": "18",
            "serving_unit": "g",
        },
    )
    monkeypatch.setattr(
        "app.services.sheets.fetch_sheet_csv",
        lambda _url: """dish,category,price,ingredient,qty,unit
Latte,espresso,220,Whole milk,200,ml
Latte,espresso,220,Espresso beans,18,g
""",
    )
    result = client.post(
        "/api/menu-sheet/sync",
        json={"url": "https://docs.google.com/spreadsheets/d/menu123/edit"},
    )
    assert result.status_code == 200, result.text
    menu = {item["name"]: item for item in client.get("/api/menu").json()}
    assert "Latte" in menu
    assert len(menu["Latte"]["recipe"]) == 2
    sale = client.post(
        "/api/sales",
        json={"payment_method": "cash", "lines": [{"menu_item_id": menu["Latte"]["id"], "quantity": 1}]},
    )
    assert sale.status_code == 201, sale.text
    items = {item["name"]: item for item in client.get("/api/items").json()}
    assert float(items["Whole milk"]["quantity_on_hand"]) == 9.8
    assert float(items["Espresso beans"]["quantity_on_hand"]) == 1982


def test_sheet_sync_creates_and_updates(client, monkeypatch):
    csv_text = """name,category,unit,qty_per_unit,units_on_hand,price,serving_size,serving_unit,reorder_point,expiry
Soy sauce,dry_goods,ml,250,4,200,15,ml,2,23/08/2028
"""
    monkeypatch.setattr("app.services.sheets.fetch_sheet_csv", lambda _url: csv_text)
    first = client.post(
        "/api/sheet/sync",
        json={"url": "https://docs.google.com/spreadsheets/d/abc123XYZ/edit"},
    )
    assert first.status_code == 200, first.text
    assert first.json()["created"] == 1
    items = {item["name"]: item for item in client.get("/api/items").json()}
    assert items["Soy sauce"]["quantity_on_hand"] == "1000.0000"
    assert items["Soy sauce"]["price_per_serving"] == "3.00"

    updated_csv = """name,category,unit,qty_per_unit,units_on_hand,price,serving_size,serving_unit,reorder_point,expiry
Soy sauce,dry_goods,ml,250,6,300,15,ml,2,23/08/2028
"""
    monkeypatch.setattr("app.services.sheets.fetch_sheet_csv", lambda _url: updated_csv)
    second = client.post("/api/sheet/sync")
    assert second.status_code == 200, second.text
    assert second.json()["updated"] == 1
    soy = {item["name"]: item for item in client.get("/api/items").json()}["Soy sauce"]
    assert soy["units_on_hand"] == "6.0000"
    assert soy["price"] == "300.00"
