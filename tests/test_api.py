from datetime import date, timedelta


def test_health_and_empty_dashboard(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    dashboard = client.get("/api/dashboard")
    assert dashboard.status_code == 200
    body = dashboard.json()
    assert body["inventory_value"] == "0.00"
    assert body["low_stock_count"] == 0
    assert body["expiring"] == []
    assert body["expired"] == []
    assert client.get("/api/items").json() == []


def test_create_item_pack_price_and_expiry(client):
    soon = date.today() + timedelta(days=3)
    response = client.post(
        "/api/items",
        json={
            "name": "Soy sauce",
            "category": "dry_goods",
            "unit": "ml",
            "qty_per_unit": "250",
            "units_on_hand": "4",
            "price": "200",
            "serving_size": "15",
            "serving_unit": "ml",
            "reorder_point": "2",
            "par_level": "6",
            "expiry_date": soon.isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    item = response.json()
    assert item["qty_per_unit"] == "250.0000"
    assert item["units_on_hand"] == "4.0000"
    assert item["quantity_on_hand"] == "1000.0000"
    assert item["price"] == "200.00"
    assert item["unit_cost"] == "0.20"
    assert item["price_per_serving"] == "3.00"
    assert item["expiry_status"] == "expiring"
    assert item["below_reorder"] is False

    expired = client.post(
        "/api/items",
        json={
            "name": "Yesterday cream",
            "category": "dairy",
            "unit": "ml",
            "qty_per_unit": "200",
            "units_on_hand": "1",
            "price": "120",
            "serving_size": "30",
            "serving_unit": "ml",
            "expiry_date": (date.today() - timedelta(days=1)).isoformat(),
        },
    )
    assert expired.status_code == 201, expired.text
    assert expired.json()["expiry_status"] == "expired"
    assert expired.json()["expired_quantity"] == "200.0000"
    assert expired.json()["good_quantity"] == "0.0000"
    assert expired.json()["price_per_serving"] == "18.00"

    dashboard = client.get("/api/dashboard").json()
    assert dashboard["low_stock_count"] == 0
    assert len(dashboard["expiring"]) == 1
    assert dashboard["expiring"][0]["name"] == "Soy sauce"
    assert len(dashboard["expired"]) == 1
    assert float(dashboard["inventory_value"]) == 320


def test_serving_unit_must_match_stock_unit(client):
    response = client.post(
        "/api/items",
        json={
            "name": "Chicken",
            "category": "produce",
            "unit": "kg",
            "qty_per_unit": "1",
            "units_on_hand": "3",
            "price": "600",
            "serving_size": "120",
            "serving_unit": "ml",
        },
    )
    assert response.status_code == 400
    assert "does not match" in response.json()["detail"]


def test_delete_selected_items(client):
    created = client.post(
        "/api/items",
        json={
            "name": "Temp oil",
            "category": "other",
            "unit": "ml",
            "qty_per_unit": "500",
            "units_on_hand": "2",
            "price": "80",
            "serving_size": "10",
            "serving_unit": "ml",
        },
    )
    assert created.status_code == 201, created.text
    item_id = created.json()["id"]
    removed = client.post("/api/items/delete", json={"ids": [item_id]})
    assert removed.status_code == 200
    assert removed.json()["deleted"] == 1
    assert client.get("/api/items").json() == []


def test_good_and_expired_split_discard_and_mark_good(client):
    yesterday = date.today() - timedelta(days=1)
    later = date.today() + timedelta(days=10)
    created = client.post(
        "/api/items",
        json={
            "name": "Chicken",
            "category": "produce",
            "unit": "kg",
            "qty_per_unit": "1",
            "units_on_hand": "2",
            "price": "400",
            "serving_size": "0.15",
            "serving_unit": "kg",
            "expiry_date": yesterday.isoformat(),
        },
    )
    assert created.status_code == 201, created.text
    item = created.json()
    assert item["expired_quantity"] == "2.0000"
    assert item["good_quantity"] == "0.0000"

    updated = client.put(
        f"/api/items/{item['id']}",
        json={
            "name": "Chicken",
            "category": "produce",
            "unit": "kg",
            "qty_per_unit": "1",
            "units_on_hand": "2",
            "add_units": "3",
            "add_price": "600",
            "price": "400",
            "serving_size": "0.15",
            "serving_unit": "kg",
            "expiry_date": later.isoformat(),
        },
    )
    assert updated.status_code == 200, updated.text
    split = updated.json()
    assert split["quantity_on_hand"] == "5.0000"
    assert split["expired_quantity"] == "2.0000"
    assert split["good_quantity"] == "3.0000"

    restored = client.post(
        f"/api/items/{item['id']}/expired",
        json={"action": "mark_good", "quantity": "1"},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["expired_quantity"] == "1.0000"
    assert restored.json()["good_quantity"] == "4.0000"
    assert restored.json()["quantity_on_hand"] == "5.0000"

    discarded = client.post(
        f"/api/items/{item['id']}/expired",
        json={"action": "discard", "quantity": "1"},
    )
    assert discarded.status_code == 200, discarded.text
    assert discarded.json()["expired_quantity"] == "0.0000"
    assert discarded.json()["good_quantity"] == "4.0000"
    assert discarded.json()["quantity_on_hand"] == "4.0000"

    waste = client.get("/api/waste").json()
    assert len(waste) == 1
    assert waste[0]["reason"] == "Expired"
    assert waste[0]["quantity"] == "1.0000"


def test_dashboard_requires_login(tmp_path):
    from fastapi.testclient import TestClient

    from app.db import configure_database

    configure_database(f"sqlite:///{tmp_path / 'anon.db'}")
    from app.main import app

    with TestClient(app) as anon:
        assert anon.get("/api/dashboard").status_code == 401
