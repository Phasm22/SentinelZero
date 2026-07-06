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
    _select_tls_port,
    run_pivot_mission,
)
from hunter.pivot.runners.tls_recon_runner import parse_tls_recon_xml
from hunter.pivot.scope import ScopeGuard
from hunter.pivot.tls_recon_parse import parse_tls_scripts, recommend_tls_action


# A 443-only host so the fixture driver unambiguously selects tls_recon (443 is
# also an HTTP port, so tls_recon is deliberately checked before http_recon).
TLS_ONLY_FIXTURE_XML = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <status state="up"/>
    <address addr="{ip}" addrtype="ipv4"/>
    <ports>
      <port protocol="tcp" portid="443">
        <state state="open"/>
        <service name="https"/>
      </port>
      <port protocol="tcp" portid="22">
        <state state="open"/>
        <service name="ssh"/>
      </port>
    </ports>
  </host>
</nmaprun>
"""


_SELF_SIGNED_CERT = (
    "Subject: commonName=porttest.lab\n"
    "Subject Alternative Name: DNS:porttest.lab, DNS:www.porttest.lab\n"
    "Issuer: commonName=porttest.lab\n"
    "Not valid before: 2026-07-06T01:19:02\n"
    "Not valid after:  2099-07-06T01:19:02\n"
)
_CA_SIGNED_CERT = (
    "Subject: commonName=shop.example.com\n"
    "Issuer: commonName=R3\n"
    "Not valid before: 2026-01-01T00:00:00\n"
    "Not valid after:  2099-01-01T00:00:00\n"
)
_EXPIRED_CERT = (
    "Subject: commonName=old.example.com\n"
    "Issuer: commonName=R3\n"
    "Not valid before: 2000-01-01T00:00:00\n"
    "Not valid after:  2001-01-01T00:00:00\n"
)
_MODERN_CIPHERS = "\n  TLSv1.2: \n  TLSv1.3: \n  least strength: A"
_WEAK_CIPHERS = "\n  TLSv1.0: \n  TLSv1.2: \n  least strength: C"


def test_parse_tls_scripts_self_signed_modern():
    fields = parse_tls_scripts({"ssl-cert": _SELF_SIGNED_CERT, "ssl-enum-ciphers": _MODERN_CIPHERS})
    assert fields["subject_cn"] == "porttest.lab"
    assert fields["issuer_cn"] == "porttest.lab"
    assert fields["sans"] == ["DNS:porttest.lab", "DNS:www.porttest.lab"]
    assert fields["self_signed"] is True
    assert fields["expired"] is False
    assert fields["tls_versions"] == ["TLSv1.2", "TLSv1.3"]
    assert fields["weak_protocols"] == []
    assert fields["cipher_grade"] == "A"
    assert fields["cert_parsed"] is True


def test_parse_tls_scripts_ca_signed():
    fields = parse_tls_scripts({"ssl-cert": _CA_SIGNED_CERT, "ssl-enum-ciphers": _MODERN_CIPHERS})
    assert fields["self_signed"] is False
    assert fields["expired"] is False


def test_parse_tls_scripts_expired():
    fields = parse_tls_scripts({"ssl-cert": _EXPIRED_CERT})
    assert fields["expired"] is True
    assert fields["days_to_expiry"] < 0


def test_parse_tls_scripts_weak_protocols():
    fields = parse_tls_scripts({"ssl-cert": _CA_SIGNED_CERT, "ssl-enum-ciphers": _WEAK_CIPHERS})
    assert fields["weak_protocols"] == ["TLSv1.0"]
    assert fields["cipher_grade"] == "C"


def test_recommend_tls_action_grades_decision():
    # Self-signed (untrusted chain) -> escalate.
    assert recommend_tls_action(
        expired=False, self_signed=True, weak_protocols=[], cipher_grade="A", cert_parsed=True,
    ) == "escalate"
    # Expired cert -> escalate.
    assert recommend_tls_action(
        expired=True, self_signed=False, weak_protocols=[], cipher_grade="A", cert_parsed=True,
    ) == "escalate"
    # Deprecated protocol offered -> escalate.
    assert recommend_tls_action(
        expired=False, self_signed=False, weak_protocols=["TLSv1.0"], cipher_grade="A", cert_parsed=True,
    ) == "escalate"
    # Weak cipher grade -> escalate.
    assert recommend_tls_action(
        expired=False, self_signed=False, weak_protocols=[], cipher_grade="C", cert_parsed=True,
    ) == "escalate"
    # Port answered but no cert parsed -> next_scan.
    assert recommend_tls_action(
        expired=False, self_signed=False, weak_protocols=[], cipher_grade=None, cert_parsed=False,
    ) == "next_scan"
    # CA-signed, modern TLS, grade A -> observe.
    assert recommend_tls_action(
        expired=False, self_signed=False, weak_protocols=[], cipher_grade="A", cert_parsed=True,
    ) == "observe"


def test_parse_tls_recon_xml_uses_fixture_shape():
    from hunter.pivot.runners.tls_recon_runner import FIXTURE_TLS_RECON_XML

    recon = parse_tls_recon_xml(
        FIXTURE_TLS_RECON_XML.format(ip="10.99.1.50", port=443), "10.99.1.50", 443
    )
    assert recon["subject_cn"] == "porttest.lab"
    assert recon["self_signed"] is True
    assert recon["cipher_grade"] == "A"


def test_select_tls_port_prefers_443():
    assert _select_tls_port([{"port": 8443}, {"port": 443}]) == 443
    assert _select_tls_port([{"port": 22}, {"port": 8443}]) == 8443
    assert _select_tls_port([{"port": 80}]) is None


def test_fixture_next_action_chooses_tls_recon_when_443_open():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        event_log = EventLog(tmp_path / "test.sqlite")
        seed = {"ip": "10.99.1.50", "type": "new_port", "scan_id": None, "network_label": "Fixture"}
        board = Blackboard.from_seed(seed, ["10.99.1.0/24"])
        board.open_ports = [{"port": 443, "protocol": "tcp", "service": "https"}]
        config = PivotMissionConfig(
            mission_id="pivot-tls-unit",
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
        # nmap + port-agnostic asset drift already ran; next pick is tls_recon.
        event_log.append(
            task_id="t1", parent_event_id=None, ip="10.99.1.50",
            type="nmap_scan", description="scan", action="nmap_scan",
        )
        event_log.append(
            task_id="t2", parent_event_id=None, ip="10.99.1.50",
            type="asset_expectation_check", description="drift", action="asset_expectation_check",
        )

        action = _fixture_next_action(runtime, 1)
        event_log.close()

        assert action == {"action": "tls_recon", "ip": "10.99.1.50"}


def test_fixture_pivot_chain_tls_recon_end_to_end():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        reports = tmp_path / "reports"
        state = tmp_path / "state"
        config = PivotMissionConfig(
            mission_id="pivot-test-tls",
            seed={"ip": "10.99.1.50", "type": "new_port", "scan_id": None, "network_label": "Fixture"},
            allowed_cidrs=["10.99.1.0/24"],
            reports_dir=reports,
            state_dir=state,
            target_network="10.99.1.0/24",
            fixture=True,
            allow_active=True,
            max_turns=10,
        )
        with patch("hunter.pivot.runners.nmap_runner.FIXTURE_NMAP_XML", TLS_ONLY_FIXTURE_XML):
            result = run_pivot_mission(config)

        assert result["status"] == "done"

        report = json.loads(list(reports.glob("hunt-pivot-test-tls-*.json"))[0].read_text())

        event_types = {e["type"] for e in report["pivot_events"]}
        assert "tls_recon" in event_types
        assert "smb_enum" not in event_types

        finding_types = {f["type"] for f in report["findings"]}
        assert "pivot_tls_posture" in finding_types
        tls_finding = next(f for f in report["findings"] if f["type"] == "pivot_tls_posture")
        assert tls_finding["port"] == 443
        assert tls_finding["subject_cn"] == "porttest.lab"
        assert tls_finding["self_signed"] is True
        # Self-signed cert -> escalate (decision-grade, not a bare pivot_recon).
        assert tls_finding["recommended_action"] == "escalate"


def test_seed_hydration_tls_skips_redundant_scan():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        reports = tmp_path / "reports"
        state = tmp_path / "state"
        config = PivotMissionConfig(
            mission_id="pivot-test-tls-hydration",
            seed={"ip": "10.99.1.60", "type": "correlated", "scan_id": 5, "network_label": "Fixture"},
            allowed_cidrs=["10.99.1.0/24"],
            reports_dir=reports,
            state_dir=state,
            target_network="10.99.1.0/24",
            fixture=True,
            allow_active=True,
            max_turns=10,
            fixture_hydration={
                "open_ports": [
                    {"port": 443, "protocol": "tcp", "service": "https", "product": "nginx", "version": "1.24.0"},
                ],
                "http_recon": None,
                "tls_recon": {
                    "subject_cn": "porttest.lab",
                    "issuer_cn": "porttest.lab",
                    "sans": ["DNS:porttest.lab"],
                    "not_before": "2026-07-06T01:19:02",
                    "not_after": "2099-07-06T01:19:02",
                    "self_signed": True,
                    "expired": False,
                    "days_to_expiry": 26000,
                    "tls_versions": ["TLSv1.2", "TLSv1.3"],
                    "weak_protocols": [],
                    "cipher_grade": "A",
                    "cert_parsed": True,
                },
                "source_scan_id": 5,
            },
        )
        result = run_pivot_mission(config)

        assert result["status"] == "done"

        report = json.loads(list(reports.glob("hunt-pivot-test-tls-hydration-*.json"))[0].read_text())

        event_types_in_order = [e["type"] for e in report["pivot_events"]]
        assert event_types_in_order[0] == "seed_hydration"
        assert "nmap_scan" not in event_types_in_order
        # No live tls_recon NSE run occurred -- evidence came from the seed scan.
        assert "tls_recon" not in event_types_in_order
        assert "tls_posture" in event_types_in_order

        finding_types = {f["type"] for f in report["findings"]}
        assert "pivot_tls_posture" in finding_types
        assert "pivot_recon" not in finding_types
        tls_finding = next(f for f in report["findings"] if f["type"] == "pivot_tls_posture")
        assert tls_finding["self_signed"] is True
        assert tls_finding["recommended_action"] == "escalate"
