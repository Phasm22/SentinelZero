import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.services import asset_registry


def test_get_asset_context_known_ip(tmp_path, monkeypatch):
    registry = {
        "172.16.0.10": {
            "name": "proxBig.prox",
            "role": "proxmox-hypervisor",
            "trust_zone": "infrastructure",
            "expected_ports": [22, 8006],
        }
    }
    path = tmp_path / "assets.json"
    path.write_text(json.dumps(registry))
    monkeypatch.setenv("SENTINEL_ASSETS_PATH", str(path))
    asset_registry._load_registry.cache_clear()

    ctx = asset_registry.get_asset_context("172.16.0.10")
    assert ctx["name"] == "proxBig.prox"
    assert asset_registry.is_expected_port("172.16.0.10", 8006) is True
    assert asset_registry.is_expected_port("172.16.0.10", 8443) is False

    unknown = asset_registry.get_asset_context("172.16.0.199")
    assert unknown["trust_zone"] == "unknown"

    home_unknown = asset_registry.get_asset_context(
        "192.168.68.50", network_cidr="192.168.68.0/22",
    )
    assert home_unknown["trust_zone"] == "home"
    assert "lab asset registry" in home_unknown["note"].lower() or "lab registry" in home_unknown["note"].lower()

    gaps = asset_registry.hosts_for_registry_gap(
        ["192.168.68.1", "192.168.68.99"], "192.168.68.0/22",
    )
    assert gaps == []

    lab_gaps = asset_registry.hosts_for_registry_gap(
        ["172.16.0.10", "172.16.0.199"], "172.16.0.0/22",
    )
    assert "172.16.0.199" in lab_gaps
    assert "172.16.0.10" not in lab_gaps

    inventory = asset_registry.hosts_for_inventory_gap(
        ["172.16.0.10", "172.16.0.13"], "172.16.0.0/22",
    )
    assert "172.16.0.10" not in inventory
    assert inventory == []

    registry["172.16.0.100"] = {
        "name": "winvm.prox",
        "role": "windows-vm",
        "trust_zone": "lab",
        "expected_ports": [3389],
    }
    path.write_text(json.dumps(registry))
    asset_registry._load_registry.cache_clear()
    inventory = asset_registry.hosts_for_inventory_gap(
        ["172.16.0.10", "172.16.0.13"], "172.16.0.0/22",
    )
    assert inventory == ["172.16.0.100"]
