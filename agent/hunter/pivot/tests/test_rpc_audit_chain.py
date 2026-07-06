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
from hunter.pivot.rpc_audit_parse import parse_rpc_scripts, recommend_rpc_action
from hunter.pivot.runners.rpc_audit_runner import FIXTURE_RPC_AUDIT_XML, parse_rpc_audit_xml
from hunter.pivot.scope import ScopeGuard


RPC_ONLY_FIXTURE_XML = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <status state="up"/>
    <address addr="{ip}" addrtype="ipv4"/>
    <ports>
      <port protocol="tcp" portid="111">
        <state state="open"/>
        <service name="rpcbind"/>
      </port>
    </ports>
  </host>
</nmaprun>
"""


_NFS_RPCINFO = (
    "\n  program version    port/proto  service\n"
    "  100000  2,3,4        111/tcp   rpcbind\n"
    "  100003  3,4         2049/tcp   nfs\n"
    "  100005  1,2,3      56401/tcp   mountd\n"
    "  100024  1          45953/tcp   status\n"
)
_BARE_RPCINFO = (
    "\n  program version    port/proto  service\n"
    "  100000  2,3,4        111/tcp   rpcbind\n"
    "  100024  1          45953/tcp   status\n"
)


def test_parse_rpc_scripts_nfs():
    fields = parse_rpc_scripts({"rpcinfo": _NFS_RPCINFO})
    assert fields["services"] == ["mountd", "nfs", "rpcbind", "status"]
    assert fields["sensitive_services"] == ["mountd", "nfs"]
    assert fields["programs_parsed"] is True
    nfs = next(p for p in fields["programs"] if p["service"] == "nfs")
    assert nfs["program"] == 100003
    assert nfs["versions"] == [3, 4]
    assert nfs["port"] == 2049


def test_parse_rpc_scripts_bare_portmapper():
    fields = parse_rpc_scripts({"rpcinfo": _BARE_RPCINFO})
    assert fields["sensitive_services"] == []
    assert fields["programs_parsed"] is True


def test_recommend_rpc_action_grades_decision():
    # Sensitive RPC service reachable -> escalate.
    assert recommend_rpc_action(sensitive_services=["nfs"], programs_parsed=True) == "escalate"
    # Portmapper answered but nothing parsed -> next_scan.
    assert recommend_rpc_action(sensitive_services=[], programs_parsed=False) == "next_scan"
    # Only portmapper/status -> observe.
    assert recommend_rpc_action(sensitive_services=[], programs_parsed=True) == "observe"


def test_parse_rpc_audit_xml_fixture_shape():
    recon = parse_rpc_audit_xml(
        FIXTURE_RPC_AUDIT_XML.format(ip="10.99.1.90", port=111), "10.99.1.90", 111
    )
    assert "nfs" in recon["sensitive_services"]
    assert "mountd" in recon["sensitive_services"]


def test_fixture_next_action_chooses_rpc_audit_when_111_open():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        event_log = EventLog(tmp_path / "test.sqlite")
        seed = {"ip": "10.99.1.90", "type": "new_port", "scan_id": None, "network_label": "Fixture"}
        board = Blackboard.from_seed(seed, ["10.99.1.0/24"])
        board.open_ports = [{"port": 111, "protocol": "tcp", "service": "rpcbind"}]
        config = PivotMissionConfig(
            mission_id="pivot-rpc-unit",
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
        event_log.append(
            task_id="t1", parent_event_id=None, ip="10.99.1.90",
            type="nmap_scan", description="scan", action="nmap_scan",
        )
        event_log.append(
            task_id="t2", parent_event_id=None, ip="10.99.1.90",
            type="asset_expectation_check", description="drift", action="asset_expectation_check",
        )

        action = _fixture_next_action(runtime, 1)
        event_log.close()

        assert action == {"action": "rpc_audit", "ip": "10.99.1.90"}


def test_fixture_pivot_chain_rpc_audit_end_to_end():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        reports = tmp_path / "reports"
        state = tmp_path / "state"
        config = PivotMissionConfig(
            mission_id="pivot-test-rpc",
            seed={"ip": "10.99.1.90", "type": "new_port", "scan_id": None, "network_label": "Fixture"},
            allowed_cidrs=["10.99.1.0/24"],
            reports_dir=reports,
            state_dir=state,
            target_network="10.99.1.0/24",
            fixture=True,
            allow_active=True,
            max_turns=10,
        )
        with patch("hunter.pivot.runners.nmap_runner.FIXTURE_NMAP_XML", RPC_ONLY_FIXTURE_XML):
            result = run_pivot_mission(config)

        assert result["status"] == "done"
        report = json.loads(list(reports.glob("hunt-pivot-test-rpc-*.json"))[0].read_text())

        event_types = {e["type"] for e in report["pivot_events"]}
        assert "rpc_audit" in event_types

        finding_types = {f["type"] for f in report["findings"]}
        assert "pivot_rpc_exposure" in finding_types
        rpc_finding = next(f for f in report["findings"] if f["type"] == "pivot_rpc_exposure")
        assert rpc_finding["port"] == 111
        # Fixture exposes nfs+mountd -> escalate.
        assert rpc_finding["recommended_action"] == "escalate"
        assert "nfs" in rpc_finding["sensitive_services"]


def test_seed_hydration_rpc_skips_redundant_scan():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        reports = tmp_path / "reports"
        state = tmp_path / "state"
        config = PivotMissionConfig(
            mission_id="pivot-test-rpc-hydration",
            seed={"ip": "10.99.1.95", "type": "correlated", "scan_id": 9, "network_label": "Fixture"},
            allowed_cidrs=["10.99.1.0/24"],
            reports_dir=reports,
            state_dir=state,
            target_network="10.99.1.0/24",
            fixture=True,
            allow_active=True,
            max_turns=10,
            fixture_hydration={
                "open_ports": [
                    {"port": 111, "protocol": "tcp", "service": "rpcbind", "product": "rpcbind", "version": "2-4"},
                ],
                "http_recon": None,
                "tls_recon": None,
                "ssh_audit": None,
                "rpc_audit": parse_rpc_scripts({"rpcinfo": _BARE_RPCINFO}),
                "source_scan_id": 9,
            },
        )
        result = run_pivot_mission(config)

        assert result["status"] == "done"
        report = json.loads(list(reports.glob("hunt-pivot-test-rpc-hydration-*.json"))[0].read_text())

        event_types_in_order = [e["type"] for e in report["pivot_events"]]
        assert event_types_in_order[0] == "seed_hydration"
        assert "nmap_scan" not in event_types_in_order
        assert "rpc_audit" not in event_types_in_order
        assert "rpc_exposure" in event_types_in_order

        finding_types = {f["type"] for f in report["findings"]}
        assert "pivot_rpc_exposure" in finding_types
        assert "pivot_recon" not in finding_types
        rpc_finding = next(f for f in report["findings"] if f["type"] == "pivot_rpc_exposure")
        # Only portmapper/status hydrated -> observe.
        assert rpc_finding["recommended_action"] == "observe"
