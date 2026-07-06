from __future__ import annotations

import json
import struct
import tempfile
from pathlib import Path
from unittest.mock import patch

from hunter.pivot.iot_udp_parse import recommend_iot_action, summarize_iot
from hunter.pivot.mdns_discover_parse import recommend_mdns_action
from hunter.pivot.orchestrator import PivotMissionConfig, run_pivot_mission
from hunter.pivot.runners.mdns_discover_runner import _encode_qname, _parse_mdns, _read_name
from hunter.pivot.runners.upnp_discover_runner import _msearch_packet
from hunter.pivot.upnp_discover_parse import parse_ssdp_response, recommend_upnp_action


# A bare IoT-style host: one non-primary TCP port so the fixture driver falls
# through to the UDP discovery chain (iot_udp_probe -> upnp -> mdns).
BARE_IOT_FIXTURE_XML = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <status state="up"/>
    <address addr="{ip}" addrtype="ipv4"/>
    <ports>
      <port protocol="tcp" portid="9100">
        <state state="open"/>
        <service name="jetdirect"/>
      </port>
    </ports>
  </host>
</nmaprun>
"""


def test_recommend_iot_action():
    escalate = {"open_ports": [{"port": 1900, "state": "open"}]}
    assert recommend_iot_action(escalate) == "escalate"
    ambiguous = {"open_ports": [{"port": 5353, "state": "open|filtered"}]}
    assert recommend_iot_action(ambiguous) == "next_scan"
    benign = {"open_ports": [{"port": 53, "state": "open"}]}
    assert recommend_iot_action(benign) == "observe"


def test_summarize_iot_flags_followons():
    scan = {"open_ports": [
        {"port": 1900, "state": "open"},
        {"port": 5353, "state": "open"},
        {"port": 161, "state": "open|filtered"},
    ]}
    summary = summarize_iot(scan)
    assert summary["upnp_open"] is True
    assert summary["mdns_open"] is True
    assert summary["exposed_services"] == ["mdns", "upnp"]


def test_parse_ssdp_response():
    raw = (
        b"HTTP/1.1 200 OK\r\n"
        b"SERVER: Linux UPnP/1.0 MiniUPnPd/2.1\r\n"
        b"ST: urn:schemas-upnp-org:device:InternetGatewayDevice:1\r\n"
        b"LOCATION: http://10.0.0.1:5000/rootDesc.xml\r\n"
        b"USN: uuid:abcd\r\n\r\n"
    )
    fields = parse_ssdp_response(raw)
    assert "MiniUPnPd" in fields["server"]
    assert fields["location"].endswith("rootDesc.xml")


def test_recommend_upnp_and_mdns_action():
    assert recommend_upnp_action(responded=True) == "escalate"
    assert recommend_upnp_action(responded=False) == "observe"
    assert recommend_mdns_action(responded=True) == "escalate"
    assert recommend_mdns_action(responded=False) == "observe"


def test_msearch_packet_shape():
    pkt = _msearch_packet("192.0.2.5", 1900)
    assert pkt.startswith(b"M-SEARCH * HTTP/1.1\r\n")
    assert b"HOST: 192.0.2.5:1900" in pkt
    assert b'MAN: "ssdp:discover"' in pkt


def test_mdns_parse_ptr_answer():
    # Build a minimal mDNS response with one PTR answer -> _http._tcp.local.
    header = struct.pack(">HHHHHH", 0x0000, 0x8400, 1, 1, 0, 0)
    question = _encode_qname("_services._dns-sd._udp.local") + struct.pack(">HH", 12, 1)
    ans_name = b"\xc0\x0c"
    ptr_target = _encode_qname("_http._tcp.local")
    answer = ans_name + struct.pack(">HHIH", 12, 1, 120, len(ptr_target)) + ptr_target
    parsed = _parse_mdns(header + question + answer)
    assert "_http._tcp.local" in parsed["services"]


def test_udp_discovery_chain_end_to_end():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        reports = tmp_path / "reports"
        state = tmp_path / "state"
        config = PivotMissionConfig(
            mission_id="pivot-test-udp",
            seed={"ip": "10.99.1.50", "type": "new_port", "scan_id": None, "network_label": "Fixture"},
            allowed_cidrs=["10.99.1.0/24"],
            reports_dir=reports,
            state_dir=state,
            target_network="10.99.1.0/24",
            fixture=True,
            allow_active=True,
            max_turns=12,
        )
        with patch("hunter.pivot.runners.nmap_runner.FIXTURE_NMAP_XML", BARE_IOT_FIXTURE_XML):
            result = run_pivot_mission(config)

        assert result["status"] == "done"
        report = json.loads(list(reports.glob("hunt-pivot-test-udp-*.json"))[0].read_text())

        event_types = {e["type"] for e in report["pivot_events"]}
        assert {"iot_udp_probe", "upnp_discover", "mdns_discover"} <= event_types

        findings = {f["type"]: f for f in report["findings"]}
        assert findings["pivot_iot_exposure"]["recommended_action"] == "escalate"
        assert findings["pivot_iot_exposure"]["upnp_open"] is True
        assert findings["pivot_upnp_exposure"]["recommended_action"] == "escalate"
        assert findings["pivot_mdns_exposure"]["recommended_action"] == "escalate"
        assert "_http._tcp.local" in findings["pivot_mdns_exposure"]["services"]
