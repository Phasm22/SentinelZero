import json
from datetime import datetime
from unittest.mock import patch

from app import db
from src.models import SensorAgent, SensorTelemetry
from src.services import lab_status_service


def setup_function():
    lab_status_service.clear_cache()


def test_lab_status_overview_endpoint_returns_aggregate(client, app):
    now = datetime.utcnow()
    snapshot = {
        "overall_status": "healthy",
        "health_percentage": 100.0,
        "total_items": 1,
        "up_items": 1,
        "down_items": 0,
        "timestamp": now.isoformat(),
        "last_update": now.isoformat(),
        "categories": {
            "loopbacks": {"total": 0, "up": 0, "items": []},
            "services": {"total": 0, "up": 0, "items": []},
            "infrastructure": {"total": 1, "up": 1, "items": [{"name": "Gateway", "status": "up"}]},
        },
    }
    with app.app_context():
        db.session.add(SensorAgent(
            agent_id="opnsense-ntopng",
            hostname="ntopng",
            role="network-sensor",
            last_seen_at=now,
        ))
        db.session.add(SensorTelemetry(
            agent_id="opnsense-ntopng",
            collected_at=now,
            collectors_json=json.dumps({
                "active_hosts": {"total_active": 1, "flagged": [{"ip": "172.16.0.9", "score": 60}]},
            }),
        ))
        db.session.commit()

    with patch("src.services.lab_status_service.get_summary_data", return_value=snapshot):
        response = client.get("/api/lab-status/overview?window_minutes=120")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["summary"]["window_minutes"] == 120
    assert payload["reachability"]["overall_status"] == "healthy"
    assert payload["sensor_fleet"]["count"] == 1
    assert payload["flows"]["flagged_hosts"][0]["ip"] == "172.16.0.9"


def test_lab_status_overview_rejects_bad_window(client):
    response = client.get("/api/lab-status/overview?window_minutes=nope")

    assert response.status_code == 400
    assert "window_minutes" in response.get_json()["error"]
