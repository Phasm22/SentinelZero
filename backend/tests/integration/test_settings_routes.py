"""Integration tests for settings routes."""
import json


def test_get_settings_returns_structure(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "network_settings.json").write_text(
        json.dumps({"default_target_network": "10.0.0.0/24", "local_mode_enabled": False}),
        encoding="utf-8",
    )

    response = client.get("/api/settings")
    assert response.status_code == 200
    data = response.get_json()
    assert "networkSettings" in data
    assert data["networkSettings"]["defaultTargetNetwork"] == "10.0.0.0/24"


def test_post_settings_persists_network_settings(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    payload = {
        "networkSettings": {
            "defaultTargetNetwork": "192.168.1.0/24",
            "concurrentScans": 2,
            "localModeEnabled": True,
            "ollamaBaseUrl": "http://127.0.0.1:11434/v1",
            "ollamaModel": "test-model",
        }
    }
    response = client.post("/api/settings", json=payload)
    assert response.status_code == 200

    saved = json.loads((tmp_path / "network_settings.json").read_text(encoding="utf-8"))
    assert saved["default_target_network"] == "192.168.1.0/24"
    assert saved["local_mode_enabled"] is True
