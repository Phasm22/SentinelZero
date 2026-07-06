from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from hunter.pivot.blackboard import Blackboard
from hunter.pivot.dns_recon_parse import build_dns_fields, identify_software, recommend_dns_action
from hunter.pivot.event_log import EventLog
from hunter.pivot.orchestrator import (
    PivotMissionConfig,
    PivotRuntime,
    _fixture_next_action,
    run_pivot_mission,
)
from hunter.pivot.runners.dns_recon_runner import _parse_first_txt, _encode_qname
from hunter.pivot.scope import ScopeGuard


DNS_ONLY_FIXTURE_XML = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <status state="up"/>
    <address addr="{ip}" addrtype="ipv4"/>
    <ports>
      <port protocol="tcp" portid="53">
        <state state="open"/>
        <service name="domain"/>
      </port>
    </ports>
  </host>
</nmaprun>
"""


def test_identify_software():
    assert identify_software("dnsmasq-pi-hole-v2.92test21") == "pi-hole"
    assert identify_software("9.18.1-Ubuntu (BIND)") == "bind"
    assert identify_software("unbound 1.17.0") == "unbound"
    assert identify_software(None) is None
    assert identify_software("mystery-resolver") is None


def test_recommend_dns_action_grades_decision():
    # Open recursion -> escalate.
    assert recommend_dns_action(responded=True, recursion_available=True, recursion_tested=True) == "escalate"
    # Answered, recursion refused -> observe.
    assert recommend_dns_action(responded=True, recursion_available=False, recursion_tested=True) == "observe"
    # Answered but recursion untested -> next_scan.
    assert recommend_dns_action(responded=True, recursion_available=False, recursion_tested=False) == "next_scan"
    # No response -> observe.
    assert recommend_dns_action(responded=False, recursion_available=False, recursion_tested=False) == "observe"


def test_parse_first_txt_roundtrip():
    # Build a minimal DNS response for version.bind TXT = "dnsmasq-2.90" and parse it.
    import struct
    header = struct.pack(">HHHHHH", 0x1234, 0x8180, 1, 1, 0, 0)
    question = _encode_qname("version.bind") + struct.pack(">HH", 16, 3)
    answer_name = b"\xc0\x0c"  # pointer to the question name
    txt = b"dnsmasq-2.90"
    rdata = bytes([len(txt)]) + txt
    answer = answer_name + struct.pack(">HHIH", 16, 3, 0, len(rdata)) + rdata
    assert _parse_first_txt(header + question + answer) == "dnsmasq-2.90"


def test_build_dns_fields():
    fields = build_dns_fields(
        responded=True, recursion_available=True, recursion_tested=True,
        version="dnsmasq-pi-hole-v2.92test21",
    )
    assert fields["software"] == "pi-hole"
    assert fields["recursion_available"] is True


def test_fixture_next_action_chooses_dns_recon_when_53_open():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        event_log = EventLog(tmp_path / "test.sqlite")
        seed = {"ip": "10.99.1.13", "type": "new_port", "scan_id": None, "network_label": "Fixture"}
        board = Blackboard.from_seed(seed, ["10.99.1.0/24"])
        board.open_ports = [{"port": 53, "protocol": "tcp", "service": "domain"}]
        config = PivotMissionConfig(
            mission_id="pivot-dns-unit",
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
            task_id="t1", parent_event_id=None, ip="10.99.1.13",
            type="nmap_scan", description="scan", action="nmap_scan",
        )
        event_log.append(
            task_id="t2", parent_event_id=None, ip="10.99.1.13",
            type="asset_expectation_check", description="drift", action="asset_expectation_check",
        )

        action = _fixture_next_action(runtime, 1)
        event_log.close()

        assert action == {"action": "dns_recon", "ip": "10.99.1.13"}


def test_fixture_pivot_chain_dns_recon_end_to_end():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        reports = tmp_path / "reports"
        state = tmp_path / "state"
        config = PivotMissionConfig(
            mission_id="pivot-test-dns",
            seed={"ip": "10.99.1.13", "type": "new_port", "scan_id": None, "network_label": "Fixture"},
            allowed_cidrs=["10.99.1.0/24"],
            reports_dir=reports,
            state_dir=state,
            target_network="10.99.1.0/24",
            fixture=True,
            allow_active=True,
            max_turns=10,
        )
        with patch("hunter.pivot.runners.nmap_runner.FIXTURE_NMAP_XML", DNS_ONLY_FIXTURE_XML):
            result = run_pivot_mission(config)

        assert result["status"] == "done"
        report = json.loads(list(reports.glob("hunt-pivot-test-dns-*.json"))[0].read_text())

        event_types = {e["type"] for e in report["pivot_events"]}
        assert "dns_recon" in event_types

        finding_types = {f["type"] for f in report["findings"]}
        assert "pivot_dns_exposure" in finding_types
        dns = next(f for f in report["findings"] if f["type"] == "pivot_dns_exposure")
        assert dns["port"] == 53
        assert dns["software"] == "pi-hole"
        # Fixture ships an open resolver -> escalate.
        assert dns["recommended_action"] == "escalate"
