from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from hunter.pivot.blackboard import Blackboard
from hunter.pivot.event_log import EventLog
from hunter.pivot.orchestrator import (
    PivotMissionConfig,
    PivotRuntime,
    _fixture_next_action,
    run_pivot_mission,
)
from hunter.pivot.proxmox_recon_parse import parse_proxmox_response, recommend_proxmox_action
from hunter.pivot.scope import ScopeGuard


PROXMOX_FIXTURE_XML = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <status state="up"/>
    <address addr="{ip}" addrtype="ipv4"/>
    <ports>
      <port protocol="tcp" portid="8006">
        <state state="open"/>
        <service name="wpl-analytics"/>
      </port>
    </ports>
  </host>
</nmaprun>
"""


def test_parse_proxmox_response_identifies_node():
    fields = parse_proxmox_response(
        status=200, server_header="pve-api-daemon/3.0",
        title="proxBig - Proxmox Virtual Environment",
    )
    assert fields["is_proxmox"] is True
    assert fields["node_name"] == "proxBig"
    assert fields["api_daemon"] == "pve-api-daemon/3.0"


def test_parse_proxmox_response_non_proxmox():
    fields = parse_proxmox_response(
        status=200, server_header="nginx/1.24.0", title="Some App",
    )
    assert fields["is_proxmox"] is False
    assert fields["node_name"] is None


def test_recommend_proxmox_action_grades_decision():
    assert recommend_proxmox_action(is_proxmox=True, responded=True) == "escalate"
    assert recommend_proxmox_action(is_proxmox=False, responded=True) == "next_scan"
    assert recommend_proxmox_action(is_proxmox=False, responded=False) == "observe"


def test_fixture_next_action_chooses_proxmox_recon_when_8006_open():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        event_log = EventLog(tmp_path / "test.sqlite")
        seed = {"ip": "10.99.1.10", "type": "new_port", "scan_id": None, "network_label": "Fixture"}
        board = Blackboard.from_seed(seed, ["10.99.1.0/24"])
        board.open_ports = [{"port": 8006, "protocol": "tcp", "service": "wpl-analytics"}]
        config = PivotMissionConfig(
            mission_id="pivot-prox-unit",
            seed=seed,
            allowed_cidrs=["10.99.1.0/24"],
            reports_dir=tmp_path / "reports",
            state_dir=tmp_path / "state",
            target_network="10.99.1.0/24",
            fixture=True,
        )
        runtime = PivotRuntime(
            config=config,
            event_log=event_log,
            board=board,
            scope=ScopeGuard(allowed_cidrs=["10.99.1.0/24"]),
        )
        # nmap, asset drift, and http_recon (8006 is also an HTTP port) already ran;
        # the remaining pick is proxmox_recon.
        for t, typ in (("t1", "nmap_scan"), ("t2", "asset_expectation_check"), ("t3", "http_recon")):
            event_log.append(
                task_id=t, parent_event_id=None, ip="10.99.1.10",
                type=typ, description=typ, action=typ,
            )

        action = _fixture_next_action(runtime, 1)
        event_log.close()

        assert action == {"action": "proxmox_recon", "ip": "10.99.1.10"}


def test_fixture_pivot_chain_proxmox_recon_end_to_end():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        reports = tmp_path / "reports"
        state = tmp_path / "state"
        config = PivotMissionConfig(
            mission_id="pivot-test-prox",
            seed={"ip": "10.99.1.10", "type": "new_port", "scan_id": None, "network_label": "Fixture"},
            allowed_cidrs=["10.99.1.0/24"],
            reports_dir=reports,
            state_dir=state,
            target_network="10.99.1.0/24",
            fixture=True,
            allow_active=True,
            max_turns=10,
        )
        with patch("hunter.pivot.runners.nmap_runner.FIXTURE_NMAP_XML", PROXMOX_FIXTURE_XML):
            result = run_pivot_mission(config)

        assert result["status"] == "done"
        report = json.loads(list(reports.glob("hunt-pivot-test-prox-*.json"))[0].read_text())

        event_types = {e["type"] for e in report["pivot_events"]}
        assert "proxmox_recon" in event_types

        finding_types = {f["type"] for f in report["findings"]}
        assert "pivot_hypervisor_exposure" in finding_types
        prox = next(f for f in report["findings"] if f["type"] == "pivot_hypervisor_exposure")
        assert prox["port"] == 8006
        assert prox["is_proxmox"] is True
        assert prox["node_name"] == "porttest"
        assert prox["recommended_action"] == "escalate"
