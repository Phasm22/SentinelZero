"""CI-safe tests for network interfaces and sync with isolated scans dir."""
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest


@pytest.fixture
def mock_psutil_interfaces():
    fake_addrs = {
        "eth0": [
            SimpleNamespace(family=SimpleNamespace(name="AF_INET"), address="10.0.0.5", netmask="255.255.255.0"),
        ],
        "lo": [
            SimpleNamespace(family=SimpleNamespace(name="AF_INET"), address="127.0.0.1", netmask="255.0.0.0"),
        ],
    }
    fake_stats = {
        "eth0": SimpleNamespace(isup=True, speed=1000),
        "lo": SimpleNamespace(isup=True, speed=None),
    }
    with patch("psutil.net_if_addrs", return_value=fake_addrs), patch(
        "psutil.net_if_stats", return_value=fake_stats
    ):
        yield


def test_network_interfaces_mocked(client, mock_psutil_interfaces):
    response = client.get("/api/network-interfaces")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "interfaces" in data
    assert data["count"] >= 1
    names = {item["name"] for item in data["interfaces"]}
    assert "eth0" in names


def test_sync_scans_reconcile_mode_isolated(client, scans_dir):
    sample = scans_dir / "discovery_scan_2026-01-01_1200.xml"
    sample.write_text(
        """<?xml version="1.0"?><nmaprun><host><status state="up"/>
        <address addr="10.0.0.1" addrtype="ipv4"/></host></nmaprun>""",
        encoding="utf-8",
    )

    response = client.post("/api/sync-scans", json={"mode": "reconcile_db"})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "success"
    assert payload["mode"] == "reconcile_db"
    assert "sync_result" in payload
