def _item_payload(**overrides):
    body = {
        "name": "Soy sauce",
        "category": "dry_goods",
        "unit": "ml",
        "qty_per_unit": "250",
        "units_on_hand": "2",
        "price": "100",
        "serving_size": "15",
        "serving_unit": "ml",
    }
    body.update(overrides)
    return body


def test_add_vendor_and_reject_others(client):
    created = client.post("/api/vendors", json={"name": "Metro", "phone": "999"})
    assert created.status_code == 201, created.text
    vendor = created.json()
    assert vendor["name"] == "Metro"
    assert vendor["balance"] == "0.00"

    listed = client.get("/api/vendors").json()
    assert [row["name"] for row in listed] == ["Metro"]

    reserved = client.post("/api/vendors", json={"name": "Others"})
    assert reserved.status_code == 400
    duplicate = client.post("/api/vendors", json={"name": "metro"})
    assert duplicate.status_code == 409


def test_inventory_from_vendor_accumulates_and_settle_reduces(client):
    vendor_id = client.post("/api/vendors", json={"name": "Local farm"}).json()["id"]

    created = client.post("/api/items", json=_item_payload(vendor_id=vendor_id, price="250"))
    assert created.status_code == 201, created.text
    item_id = created.json()["id"]
    assert client.get("/api/vendors").json()[0]["balance"] == "250.00"

    client.post("/api/items", json=_item_payload(name="Oil", vendor_id=None, price="80"))
    assert client.get("/api/vendors").json()[0]["balance"] == "250.00"

    added = client.put(
        f"/api/items/{item_id}",
        json=_item_payload(
            add_units="1",
            add_price="40",
            units_on_hand="2",
            vendor_id=vendor_id,
        ),
    )
    assert added.status_code == 200, added.text
    assert client.get("/api/vendors").json()[0]["balance"] == "290.00"

    settled = client.post(f"/api/vendors/{vendor_id}/settle", json={"amount": "100"})
    assert settled.status_code == 200, settled.text
    assert settled.json()["balance"] == "190.00"

    zero = client.post(f"/api/vendors/{vendor_id}/settle", json={"amount": "0"})
    assert zero.status_code == 400


def test_unknown_vendor_is_rejected(client):
    response = client.post("/api/items", json=_item_payload(vendor_id=99, price="10"))
    assert response.status_code == 404


def test_manual_entry_and_delete_vendor(client):
    vendor_id = client.post("/api/vendors", json={"name": "Opening books"}).json()["id"]

    added = client.post(
        f"/api/vendors/{vendor_id}/entries",
        json={"amount": "500", "kind": "add", "note": "Opening balance"},
    )
    assert added.status_code == 200, added.text
    assert added.json()["balance"] == "500.00"
    assert added.json()["entries"][0]["note"] == "Opening balance"
    assert added.json()["entries"][0]["kind"] == "charge"

    reduced = client.post(
        f"/api/vendors/{vendor_id}/entries",
        json={"amount": "120", "kind": "reduce", "note": "Cash paid"},
    )
    assert reduced.status_code == 200, reduced.text
    assert reduced.json()["balance"] == "380.00"

    deleted = client.delete(f"/api/vendors/{vendor_id}")
    assert deleted.status_code == 200, deleted.text
    assert client.get("/api/vendors").json() == []
    assert client.delete(f"/api/vendors/{vendor_id}").status_code == 404
