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
from hunter.pivot.rdp_recon_parse import parse_rdp_scripts, recommend_rdp_action
from hunter.pivot.runners.rdp_recon_runner import FIXTURE_RDP_RECON_XML, parse_rdp_recon_xml
from hunter.pivot.scope import ScopeGuard


RDP_ONLY_FIXTURE_XML = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <status state="up"/>
    <address addr="{ip}" addrtype="ipv4"/>
    <ports>
      <port protocol="tcp" portid="3389">
        <state state="open"/>
        <service name="ms-wbt-server"/>
      </port>
    </ports>
  </host>
</nmaprun>
"""


_NLA_NTLM = (
    "\n  Target_Name: DESKTOP-LAB\n  NetBIOS_Computer_Name: DESKTOP-LAB\n"
    "  DNS_Domain_Name: corp.lab\n  DNS_Computer_Name: WS01.corp.lab\n"
    "  Product_Version: 10.0.19041\n"
)
_NLA_ENC = "\n  Security layer\n    CredSSP (NLA): SUCCESS\n    RDSTLS: SUCCESS\n"
_NONLA_ENC = "\n  Security layer\n    Native RDP: SUCCESS\n    SSL: SUCCESS\n"


def test_parse_rdp_scripts_identity_and_nla():
    fields = parse_rdp_scripts({"rdp-ntlm-info": _NLA_NTLM, "rdp-enum-encryption": _NLA_ENC})
    assert fields["hostname"] == "WS01.corp.lab"
    assert fields["domain"] == "corp.lab"
    assert fields["os_build"] == "10.0.19041"
    assert fields["nla_enabled"] is True
    assert "CredSSP (NLA)" in fields["security_layers"]
    assert fields["parsed"] is True


def test_parse_rdp_scripts_no_nla():
    fields = parse_rdp_scripts({"rdp-ntlm-info": _NLA_NTLM, "rdp-enum-encryption": _NONLA_ENC})
    assert fields["nla_enabled"] is False
    assert "Native RDP" in fields["security_layers"]


def test_recommend_rdp_action_grades_decision():
    # NLA not enforced -> escalate.
    assert recommend_rdp_action(responded=True, nla_enabled=False, parsed=True) == "escalate"
    # NLA enforced -> observe.
    assert recommend_rdp_action(responded=True, nla_enabled=True, parsed=True) == "observe"
    # Answered but nothing parsed -> next_scan.
    assert recommend_rdp_action(responded=True, nla_enabled=False, parsed=False) == "next_scan"


def test_parse_rdp_recon_xml_fixture_shape():
    recon = parse_rdp_recon_xml(
        FIXTURE_RDP_RECON_XML.format(ip="10.99.1.100", port=3389), "10.99.1.100", 3389
    )
    # Fixture ships NLA disabled.
    assert recon["nla_enabled"] is False
    assert recon["hostname"] == "DESKTOP-LAB"
    assert recon["responded"] is True


def test_fixture_next_action_chooses_rdp_recon_when_3389_open():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        event_log = EventLog(tmp_path / "test.sqlite")
        seed = {"ip": "10.99.1.100", "type": "new_port", "scan_id": None, "network_label": "Fixture"}
        board = Blackboard.from_seed(seed, ["10.99.1.0/24"])
        board.open_ports = [{"port": 3389, "protocol": "tcp", "service": "ms-wbt-server"}]
        config = PivotMissionConfig(
            mission_id="pivot-rdp-unit",
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
            task_id="t1", parent_event_id=None, ip="10.99.1.100",
            type="nmap_scan", description="scan", action="nmap_scan",
        )
        event_log.append(
            task_id="t2", parent_event_id=None, ip="10.99.1.100",
            type="asset_expectation_check", description="drift", action="asset_expectation_check",
        )

        action = _fixture_next_action(runtime, 1)
        event_log.close()

        assert action == {"action": "rdp_recon", "ip": "10.99.1.100"}


def test_fixture_pivot_chain_rdp_recon_end_to_end():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        reports = tmp_path / "reports"
        state = tmp_path / "state"
        config = PivotMissionConfig(
            mission_id="pivot-test-rdp",
            seed={"ip": "10.99.1.100", "type": "new_port", "scan_id": None, "network_label": "Fixture"},
            allowed_cidrs=["10.99.1.0/24"],
            reports_dir=reports,
            state_dir=state,
            target_network="10.99.1.0/24",
            fixture=True,
            allow_active=True,
            max_turns=10,
        )
        with patch("hunter.pivot.runners.nmap_runner.FIXTURE_NMAP_XML", RDP_ONLY_FIXTURE_XML):
            result = run_pivot_mission(config)

        assert result["status"] == "done"
        report = json.loads(list(reports.glob("hunt-pivot-test-rdp-*.json"))[0].read_text())

        event_types = {e["type"] for e in report["pivot_events"]}
        assert "rdp_recon" in event_types

        finding_types = {f["type"] for f in report["findings"]}
        assert "pivot_rdp_exposure" in finding_types
        rdp = next(f for f in report["findings"] if f["type"] == "pivot_rdp_exposure")
        assert rdp["port"] == 3389
        assert rdp["hostname"] == "DESKTOP-LAB"
        # Fixture ships NLA disabled -> escalate.
        assert rdp["recommended_action"] == "escalate"


def test_seed_hydration_rdp_skips_redundant_scan():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        reports = tmp_path / "reports"
        state = tmp_path / "state"
        config = PivotMissionConfig(
            mission_id="pivot-test-rdp-hydration",
            seed={"ip": "10.99.1.105", "type": "correlated", "scan_id": 11, "network_label": "Fixture"},
            allowed_cidrs=["10.99.1.0/24"],
            reports_dir=reports,
            state_dir=state,
            target_network="10.99.1.0/24",
            fixture=True,
            allow_active=True,
            max_turns=10,
            fixture_hydration={
                "open_ports": [
                    {"port": 3389, "protocol": "tcp", "service": "ms-wbt-server"},
                ],
                "http_recon": None,
                "tls_recon": None,
                "ssh_audit": None,
                "rpc_audit": None,
                "rdp_recon": parse_rdp_scripts({"rdp-ntlm-info": _NLA_NTLM, "rdp-enum-encryption": _NLA_ENC}),
                "source_scan_id": 11,
            },
        )
        result = run_pivot_mission(config)

        assert result["status"] == "done"
        report = json.loads(list(reports.glob("hunt-pivot-test-rdp-hydration-*.json"))[0].read_text())

        event_types_in_order = [e["type"] for e in report["pivot_events"]]
        assert event_types_in_order[0] == "seed_hydration"
        assert "nmap_scan" not in event_types_in_order
        assert "rdp_recon" not in event_types_in_order
        assert "rdp_exposure" in event_types_in_order

        finding_types = {f["type"] for f in report["findings"]}
        assert "pivot_rdp_exposure" in finding_types
        assert "pivot_recon" not in finding_types
        rdp = next(f for f in report["findings"] if f["type"] == "pivot_rdp_exposure")
        # NLA enforced in hydrated evidence -> observe.
        assert rdp["recommended_action"] == "observe"
