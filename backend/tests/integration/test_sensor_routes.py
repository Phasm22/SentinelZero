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
