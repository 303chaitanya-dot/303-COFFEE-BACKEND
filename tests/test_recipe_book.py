from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook

from app.services.recipe_book import import_recipe_book, is_prep_recipe, parse_recipe_workbook


def test_prep_names_go_to_sauces():
    assert is_prep_recipe("Pasta sauce")
    assert is_prep_recipe("Chicken marination")
    assert is_prep_recipe("Garlic aoli")
    assert is_prep_recipe("kheema")
    assert is_prep_recipe("Veg Burger prep")
    assert not is_prep_recipe("kheema pav")
    assert not is_prep_recipe("Mac N Cheese")
    assert not is_prep_recipe("Banana bread & esp cream")
    assert not is_prep_recipe("Crispy Falafel & hummus")
    assert not is_prep_recipe("shroom hummus")
    assert is_prep_recipe("hummus")


def _workbook_bytes() -> bytes:
    book = Workbook()
    ingri = book.active
    ingri.title = "Ingri"
    ingri.append(["Items", "", ""])
    ingri.append(["Chicken", "0.44/g", ""])
    ingri.append(["Onions", "0.025/g", ""])
    ingri.append(["Salt", "0.025/g", ""])
    dish = book.create_sheet("kheema pav")
    dish["A1"] = "kheema pav"
    dish["B3"] = "Yield"
    dish.append([])
    dish["A6"] = "S.No."
    dish["B6"] = "Ingredient"
    dish["C6"] = "Quantity"
    dish["D6"] = "Unit"
    dish["A8"] = 1
    dish["B8"] = "Chicken"
    dish["C8"] = 1200
    dish["D8"] = "gms"
    dish["A9"] = 2
    dish["B9"] = "onion"
    dish["C9"] = 50
    dish["D9"] = "g"
    dish["D13"] = "Selling price"
    dish["E13"] = 180
    buffer = BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def test_parse_ingri_and_recipe_tabs():
    ingredients, recipes = parse_recipe_workbook(_workbook_bytes())
    names = {row["name"] for row in ingredients}
    assert "Chicken" in names
    assert "Onions" in names
    assert recipes
    kheema = next(row for row in recipes if "kheema" in row["name"].lower())
    assert kheema["lines"][0]["name"] == "Chicken"
    assert kheema["lines"][0]["qty"] == Decimal("1200")
    assert kheema["lines"][0]["unit"] == "g"


def test_import_lists_items_at_zero_and_keeps_stock(client, monkeypatch):
    created = client.post(
        "/api/items",
        json={
            "name": "Chicken",
            "category": "produce",
            "unit": "g",
            "qty_per_unit": "1",
            "units_on_hand": "5",
            "price": "100",
            "serving_size": "1",
            "serving_unit": "g",
        },
    )
    assert created.status_code == 201, created.text
    monkeypatch.setattr("app.services.recipe_book.fetch_workbook", lambda _url: _workbook_bytes())
    result = client.post(
        "/api/recipe-book/sync",
        json={"url": "https://docs.google.com/spreadsheets/d/recipebook/edit"},
    )
    assert result.status_code == 200, result.text
    items = {item["name"]: item for item in client.get("/api/items").json()}
    assert items["Chicken"]["quantity_on_hand"] == "5.0000"
    assert items["Onions"]["quantity_on_hand"] == "0.0000"
    assert items["Salt"]["quantity_on_hand"] == "0.0000"
    menu = {item["name"].lower(): item for item in client.get("/api/menu").json()}
    assert any("kheema" in name for name in menu)
    recipe = next(item for name, item in menu.items() if "kheema" in name)
    assert len(recipe["recipe"]) >= 2


def test_add_units_adjusts_existing_stock(client):
    created = client.post(
        "/api/items",
        json={
            "name": "Tomato",
            "category": "produce",
            "unit": "kg",
            "qty_per_unit": "1",
            "units_on_hand": "2",
            "price": "80",
            "serving_size": "0.1",
            "serving_unit": "kg",
        },
    )
    assert created.status_code == 201, created.text
    item = created.json()
    updated = client.put(
        f"/api/items/{item['id']}",
        json={
            "name": "Tomato",
            "category": "produce",
            "unit": "kg",
            "qty_per_unit": "1",
            "units_on_hand": "2",
            "add_units": "3",
            "add_price": "120",
            "price": "80",
            "serving_size": "0.1",
            "serving_unit": "kg",
            "replace_stock": False,
        },
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["units_on_hand"] == "5.0000"
    assert body["quantity_on_hand"] == "5.0000"
    assert body["price"] == "200.00"
