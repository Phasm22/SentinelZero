import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.services.agent_service import build_enrichment_digest


def test_build_enrichment_digest_groups_by_host():
    insights = [
        {
            "id": "a",
            "type": "new_port",
            "host": "172.16.0.10",
            "details": {
                "ip": "172.16.0.10",
                "port": 8443,
                "asset_context": {"name": "proxBig", "role": "proxmox-hypervisor"},
                "sensor_context": {
                    "endpoint": {"process_name": "backup-proxy", "pid": 99},
                    "network": {"segment": "lab"},
                },
                "unexpected_port": True,
            },
        },
    ]
    digest = build_enrichment_digest(insights)
    assert "172.16.0.10" in digest["hosts"]
    h = digest["hosts"]["172.16.0.10"]
    assert h["asset"]["role"] == "proxmox-hypervisor"
    assert h["sensor"]["endpoint"]["process_name"] == "backup-proxy"
    assert h["unexpected_port"] is True
    assert h["port"] == 8443
