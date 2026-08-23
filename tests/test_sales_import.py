from pathlib import Path

from app.services.sales_import import parse_item_wise_rows, parse_report_date, read_rows

FIXTURE = Path(__file__).parent / "fixtures" / "item_wise_sales.csv"


def test_parse_petpooja_item_wise_report():
    rows = read_rows("item_wise_sales.csv", FIXTURE.read_bytes())
    assert parse_report_date(rows).isoformat() == "2026-08-22"
    items = {item["name"]: item for item in parse_item_wise_rows(rows)}
    assert items["Iced Latte"]["quantity"] == 5
    assert items["Cold Fashion"]["quantity"] == 13
    assert items["Katha Stickers"]["quantity"] == 5
    assert items["Orange Esp Tonic"]["quantity"] == 8
    assert "Sub Total" not in items
    assert "Total" not in items


def test_import_applies_recipe_and_skips_unknown(client):
    milk = client.post(
        "/api/items",
        json={
            "name": "Whole milk",
            "category": "dairy",
            "unit": "l",
            "qty_per_unit": "1",
            "units_on_hand": "20",
            "price": "1600",
            "serving_size": "200",
            "serving_unit": "ml",
        },
    ).json()
    dish = client.post(
        "/api/menu",
        json={
            "name": "Iced Latte",
            "category": "coffee",
            "price": "185",
            "recipe": [{"item_id": milk["id"], "quantity": "200", "unit": "ml"}],
        },
    )
    assert dish.status_code == 201, dish.text

    uploaded = client.post(
        "/api/sales/import",
        files={"file": ("item_wise_sales.csv", FIXTURE.read_bytes(), "text/csv")},
    )
    assert uploaded.status_code == 200, uploaded.text
    body = uploaded.json()
    assert body["status"] in {"partial", "applied"}
    assert any(row["name"] == "Iced Latte" for row in body["applied"])
    assert any(row["name"] == "Cold Fashion" for row in body["skipped"])

    after = {item["name"]: item for item in client.get("/api/items").json()}
    assert float(after["Whole milk"]["quantity_on_hand"]) == 19.0

    again = client.post(
        "/api/sales/import",
        files={"file": ("item_wise_sales.csv", FIXTURE.read_bytes(), "text/csv")},
    )
    assert again.status_code == 409
