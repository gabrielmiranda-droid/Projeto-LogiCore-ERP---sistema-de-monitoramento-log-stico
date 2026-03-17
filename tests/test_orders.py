from datetime import datetime, timedelta, timezone
from pathlib import Path


def test_create_order(client):
    response = client.post(
        "/api/orders",
        json={
            "customer_id": 1,
            "vehicle_id": 1,
            "route_id": 1,
            "expected_delivery_at": (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat(),
            "items": [{"product_id": 1, "quantity": 2}, {"product_id": 2, "quantity": 3}],
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["customer"]["id"] == 1
    assert payload["status"] == "PENDENTE"
    assert len(payload["items"]) == 2


def test_generate_invoice_pdf_and_xml(client):
    order_response = client.post(
        "/api/orders",
        json={
            "customer_id": 1,
            "vehicle_id": 1,
            "route_id": 1,
            "expected_delivery_at": (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat(),
            "items": [{"product_id": 1, "quantity": 1}],
        },
    )
    order_id = order_response.json()["id"]

    response = client.patch(f"/api/orders/{order_id}/status", json={"status": "EM_ROTA"})
    assert response.status_code == 200

    invoice_response = client.get(f"/api/orders/{order_id}/invoice")
    assert invoice_response.status_code == 200
    invoice = invoice_response.json()
    assert invoice["status"] == "EMITIDA"
    assert invoice["customer_name"]
    assert invoice["pdf_download_url"]
    assert invoice["xml_download_url"]
    assert Path(invoice["pdf_path"]).exists()
    assert Path(invoice["xml_path"]).exists()

    listing_response = client.get("/api/invoices")
    assert listing_response.status_code == 200
    assert len(listing_response.json()) >= 1

    invoice_id = invoice["id"]
    detail_response = client.get(f"/api/invoices/{invoice_id}")
    assert detail_response.status_code == 200

    pdf_response = client.get(f"/api/invoices/{invoice_id}/pdf")
    assert pdf_response.status_code == 200

    xml_response = client.get(f"/api/invoices/{invoice_id}/xml")
    assert xml_response.status_code == 200
