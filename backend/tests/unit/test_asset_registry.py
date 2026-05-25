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
