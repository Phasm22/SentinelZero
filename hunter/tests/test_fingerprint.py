from hunter.fingerprint import build_fingerprint_findings


def test_new_device_and_new_udp_port_findings():
    findings = build_fingerprint_findings(
        ip="192.168.68.79",
        probe_result={"open_ports": [{"port": 5353, "protocol": "udp", "state": "open|filtered"}]},
        baseline_entry=None,
        device_context={"device_hint": "homebridge"},
    )
    kinds = {item["type"] for item in findings}
    assert "new_device" in kinds
    assert "new_udp_port" in kinds


def test_expected_udp_violation_finding():
    findings = build_fingerprint_findings(
        ip="192.168.68.79",
        probe_result={"open_ports": [{"port": 9999, "protocol": "udp", "state": "open"}]},
        baseline_entry={"udp_ports": [{"port": 5353, "protocol": "udp"}]},
        device_context={"device_hint": "homebridge", "expected_udp_ports": [5353]},
    )
    kinds = {item["type"] for item in findings}
    assert "expected_udp_violation" in kinds
    assert "new_udp_port" in kinds
