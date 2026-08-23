def test_health_and_seeded_dashboard(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    dashboard = client.get("/api/dashboard")
    assert dashboard.status_code == 200
    body = dashboard.json()
    assert body["today_tickets"] >= 1
    assert float(body["inventory_value"]) > 0
    assert float(body["today_sales"]) > 0


def test_sale_flow_updates_stock(client):
    menu = client.get("/api/menu").json()
    latte = next(item for item in menu if item["name"] == "Latte")
    before = {item["sku"]: item for item in client.get("/api/items").json()}

    response = client.post(
        "/api/sales",
        json={"payment_method": "cash", "lines": [{"menu_item_id": latte["id"], "quantity": 1}]},
    )
    assert response.status_code == 201
    ticket = response.json()
    assert float(ticket["total"]) == 220

    after = {item["sku"]: item for item in client.get("/api/items").json()}
    assert float(after["ESP-BEAN"]["quantity_on_hand"]) == float(before["ESP-BEAN"]["quantity_on_hand"]) - 18
    assert float(after["MILK"]["quantity_on_hand"]) == float(before["MILK"]["quantity_on_hand"]) - 220


def test_dashboard_requires_login(tmp_path):
    from fastapi.testclient import TestClient

    from app.db import configure_database

    configure_database(f"sqlite:///{tmp_path / 'anon.db'}")
    from app.main import app

    with TestClient(app) as anon:
        assert anon.get("/api/dashboard").status_code == 401


def test_bill_text_upload_and_confirm(client):
    upload = client.post(
        "/api/bills",
        files={"file": ("bill.txt", b"supplier: Market\nTomatoes|2|50|kg|0.03\n", "text/plain")},
    )
    assert upload.status_code == 201, upload.text
    bill = upload.json()
    assert bill["supplier_name"] == "Market"
    assert bill["lines"][0]["name"] == "Tomatoes"
    confirm = client.post(f"/api/bills/{bill['id']}/confirm")
    assert confirm.status_code == 200
    items = {item["name"]: item for item in client.get("/api/items").json()}
    assert items["Tomatoes"]["quantity_on_hand"] == "2.0000"


def test_petpooja_webhook_uses_mapping(client):
    before = {item["sku"]: item for item in client.get("/api/items").json()}
    response = client.post(
        "/api/integrations/petpooja/orders",
        json={"orderID": "PP-UI-1", "order_items": [{"name": "Latte", "quantity": 1}]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "applied"
    after = {item["sku"]: item for item in client.get("/api/items").json()}
    assert float(after["ESP-BEAN"]["quantity_on_hand"]) == float(before["ESP-BEAN"]["quantity_on_hand"]) - 18


def test_cannot_sell_more_than_stock(client):
    menu = client.get("/api/menu").json()
    croissant = next(item for item in menu if item["name"] == "Butter croissant")
    response = client.post(
        "/api/sales",
        json={"payment_method": "cash", "lines": [{"menu_item_id": croissant["id"], "quantity": 500}]},
    )
    assert response.status_code == 400
    assert "Not enough" in response.json()["detail"]
