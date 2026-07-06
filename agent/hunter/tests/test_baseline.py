import json
from pathlib import Path

from hunter.baseline import (
    empty_baseline,
    extract_udp_ports,
    get_fingerprint,
    load_baseline,
    save_baseline,
    upsert_fingerprint,
)


def test_load_baseline_bootstraps_missing_file(tmp_path: Path):
    path = tmp_path / "iot_fingerprints.json"
    baseline = load_baseline(path)
    assert baseline == empty_baseline()


def test_save_and_load_baseline_roundtrip(tmp_path: Path):
    path = tmp_path / "iot_fingerprints.json"
    payload = {"schema_version": 1, "fingerprints": {"192.168.68.79": {"ip": "192.168.68.79"}}}
    save_baseline(payload, path)
    loaded = load_baseline(path)
    assert loaded["fingerprints"]["192.168.68.79"]["ip"] == "192.168.68.79"


def test_upsert_fingerprint_tracks_observation_count():
    payload = empty_baseline()
    upsert_fingerprint(
        payload,
        ip="192.168.68.79",
        probe_result={"open_ports": [{"port": 5353, "protocol": "udp", "state": "open|filtered"}]},
        mission_id="home_assess",
        device_hint="homebridge",
        observed_at="2026-05-30T20:00:00Z",
    )
    entry = get_fingerprint(payload, "192.168.68.79")
    assert entry is not None
    assert entry["observation_count"] == 1
    assert entry["udp_ports"][0]["port"] == 5353


def test_extract_udp_ports_filters_non_udp():
    result = extract_udp_ports({
        "open_ports": [
            {"port": 53, "protocol": "udp", "state": "open"},
            {"port": 80, "protocol": "tcp", "state": "open"},
        ]
    })
    assert [row["port"] for row in result] == [53]
