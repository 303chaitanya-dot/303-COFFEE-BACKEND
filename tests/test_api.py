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


def test_cannot_sell_more_than_stock(client):
    menu = client.get("/api/menu").json()
    croissant = next(item for item in menu if item["name"] == "Butter croissant")
    response = client.post(
        "/api/sales",
        json={"payment_method": "cash", "lines": [{"menu_item_id": croissant["id"], "quantity": 500}]},
    )
    assert response.status_code == 400
    assert "Not enough" in response.json()["detail"]
