import os
from pathlib import Path

import pytest

from hunter.baseline import empty_baseline, get_fingerprint, upsert_fingerprint
from hunter.executors.local import LocalExecutor
from hunter.fingerprint import build_fingerprint_findings


pytestmark = pytest.mark.live_home


def _require_live_home() -> None:
    if os.environ.get("HUNTER_LIVE_HOME") != "1":
        pytest.skip("set HUNTER_LIVE_HOME=1 to run live home tests")


def test_live_home_anchor_iot_probe_has_udp_signal():
    _require_live_home()
    iface = os.environ.get("HUNTER_HOME_IFACE", "enp6s19")
    ex = LocalExecutor(iface=iface, allowed_cidrs=["192.168.68.0/22", "192.168.71.0/24"])
    result = ex.port_scan_iot("192.168.71.25")
    assert "error" not in result
    ports = {int(p["port"]) for p in (result.get("open_ports") or []) if str(p.get("protocol", "udp")) == "udp"}
    assert 53 in ports


def test_live_home_continuity_diff_cycle():
    _require_live_home()
    sample = {"open_ports": [{"port": 5353, "protocol": "udp", "state": "open|filtered"}]}
    baseline = empty_baseline()
    upsert_fingerprint(
        baseline,
        ip="192.168.68.79",
        probe_result=sample,
        mission_id="home_assess",
        device_hint="homebridge",
    )
    entry = get_fingerprint(baseline, "192.168.68.79")
    assert entry is not None
    no_drift = build_fingerprint_findings(
        ip="192.168.68.79",
        probe_result=sample,
        baseline_entry=entry,
        device_context={"device_hint": "homebridge", "expected_udp_ports": [5353]},
    )
    assert not [x for x in no_drift if x["type"] in {"new_device", "new_udp_port"}]

    with_new_port = {"open_ports": sample["open_ports"] + [{"port": 1900, "protocol": "udp", "state": "open|filtered"}]}
    drift = build_fingerprint_findings(
        ip="192.168.68.79",
        probe_result=with_new_port,
        baseline_entry=entry,
        device_context={"device_hint": "homebridge", "expected_udp_ports": [5353]},
    )
    assert any(item["type"] == "new_udp_port" for item in drift)
