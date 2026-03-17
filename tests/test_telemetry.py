from datetime import datetime, timedelta, timezone


def test_receive_telemetry(client):
    response = client.post(
        "/api/telemetry",
        json={
            "vehicle_id": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "latitude": -23.55052,
            "longitude": -46.633308,
            "speed_kmh": 72,
            "fuel_level": 60,
            "cargo_occupancy": 55,
            "route_id": 1,
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["vehicle_id"] == 1


def test_generate_alert_from_telemetry(client):
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
    client.patch(f"/api/orders/{order_id}/status", json={"status": "EM_ROTA"})

    response = client.post(
        "/api/telemetry",
        json={
            "vehicle_id": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "latitude": -23.1000,
            "longitude": -46.2000,
            "speed_kmh": 105,
            "fuel_level": 10,
            "cargo_occupancy": 48,
            "route_id": 1,
        },
    )
    assert response.status_code == 201

    alerts_response = client.get("/api/alerts")
    assert alerts_response.status_code == 200
    alerts = alerts_response.json()
    assert len(alerts) >= 3
