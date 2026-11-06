"""Integration tests for sensor routes."""
import pytest


def test_sensor_register_without_api_key(client, app, monkeypatch):
    monkeypatch.setattr("src.routes.sensor_routes.SENSOR_API_KEY", "")
    with app.app_context():
        response = client.post(
            "/api/sensor/register",
            json={"agent_id": "ci-agent", "hostname": "ci-host", "host_ip": "10.0.0.2"},
        )
    assert response.status_code in (200, 201)
    data = response.get_json()
    assert data["agent_id"] == "ci-agent"


def test_sensor_register_rejects_bad_api_key(client, monkeypatch):
    monkeypatch.setattr("src.routes.sensor_routes.SENSOR_API_KEY", "secret-key")
    response = client.post(
        "/api/sensor/register",
        headers={"X-Sensor-Key": "wrong"},
        json={"agent_id": "blocked-agent"},
    )
    assert response.status_code == 401


def test_sensor_register_accepts_valid_api_key(client, monkeypatch):
    monkeypatch.setattr("src.routes.sensor_routes.SENSOR_API_KEY", "secret-key")
    response = client.post(
        "/api/sensor/register",
        headers={"X-Sensor-Key": "secret-key"},
        json={"agent_id": "allowed-agent", "hostname": "sensor"},
    )
    assert response.status_code in (200, 201)


def test_sensor_ingest_requires_payload(client, monkeypatch):
    monkeypatch.setattr("src.routes.sensor_routes.SENSOR_API_KEY", "")
    response = client.post("/api/sensor/ingest", json={})
    assert response.status_code == 400


def test_sensor_ingest_stores_and_exposes_wifi_collector(client, monkeypatch):
    """collectors.wifi must be normalized, stored, and queryable (was previously opaque/ignored)."""
    monkeypatch.setattr("src.routes.sensor_routes.SENSOR_API_KEY", "")

    register = client.post(
        "/api/sensor/register",
        json={
            "agent_id": "t470s-rf",
            "hostname": "phasm-T470s",
            "host_ip": "192.168.68.111",
            "role": "wireless",
            "tags": ["rf", "passive"],
        },
    )
    assert register.status_code in (200, 201)

    wifi = {
        "aps": [{"bssid": "a8:42:a1:00:00:01", "ssid": "deco-home", "channel": "5g-36", "rssi_dbm": -52}],
        "clients_summary": {"associated": 4, "probe_noise_count": 7, "unresolved": 1, "psk": "LEAK"},
        "channels": [{"id": "5g-36", "neighbor_count": 3}],
        "events": [{"event": "new_client", "entity": "wifi_mac:da:11:22:33:44:55@home"}],
        "password": "nope",
    }
    ingest = client.post(
        "/api/sensor/ingest",
        json={
            "agent_id": "t470s-rf",
            "hostname": "phasm-T470s",
            "host_ip": "192.168.68.111",
            "ts": "2026-11-06T12:00:00Z",
            "collectors": {
                "system": {"cpu_pct": 3.5, "mem_pct": 41.0, "load_avg": [0.2, 0.3, 0.4]},
                "wifi": wifi,
            },
        },
    )
    assert ingest.status_code == 202

    latest = client.get("/api/sensor/latest/t470s-rf")
    assert latest.status_code == 200
    body = latest.get_json()
    stored = body["collectors"]["wifi"]
    assert "password" not in stored
    assert "psk" not in stored.get("clients_summary", {})
    assert stored["clients_summary"]["associated"] == 4
    assert stored["aps"][0]["bssid"] == "a8:42:a1:00:00:01"

    by_agent = client.get("/api/sensor/wifi?agent_id=t470s-rf")
    assert by_agent.status_code == 200
    wifi_body = by_agent.get_json()
    assert wifi_body["agent_id"] == "t470s-rf"
    assert wifi_body["wifi"]["channels"][0]["id"] == "5g-36"

    by_ip = client.get("/api/sensor/wifi?ip=192.168.68.111")
    assert by_ip.status_code == 200
    assert by_ip.get_json()["wifi"]["events"][0]["event"] == "new_client"


def test_sensor_wifi_endpoint_404_without_wifi_block(client, monkeypatch):
    monkeypatch.setattr("src.routes.sensor_routes.SENSOR_API_KEY", "")
    client.post(
        "/api/sensor/register",
        json={"agent_id": "plain-agent", "hostname": "plain", "host_ip": "10.0.0.9"},
    )
    client.post(
        "/api/sensor/ingest",
        json={
            "agent_id": "plain-agent",
            "ts": "2026-11-06T12:00:00Z",
            "collectors": {"system": {"cpu_pct": 1.0}},
        },
    )
    resp = client.get("/api/sensor/wifi?agent_id=plain-agent")
    assert resp.status_code == 404
    assert "no wifi" in resp.get_json()["error"]
