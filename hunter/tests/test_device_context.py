from hunter.device_context import build_device_context
from hunter.seed import SeedResult


def _seed() -> SeedResult:
    return SeedResult(
        mission_id="home_assess",
        target_network="192.168.68.0/22",
        registry_hosts=["192.168.68.79"],
        passive_hosts=["192.168.68.79", "192.168.68.90"],
        last_scan_hosts=["192.168.68.79"],
        unknown_in_passive=["192.168.68.90"],
        missing_from_scan=[],
        stale=[],
        last_scan_id=3,
        last_scan_timestamp="2026-05-30T00:00:00Z",
    )


def test_device_context_merges_assets_pihole_and_baseline():
    ctx = build_device_context(
        _seed(),
        assets={
            "192.168.68.79": {
                "name": "homebridge",
                "role": "iot-gateway",
                "expected_udp_ports": [5353],
            }
        },
        pihole_latest={"collectors": {"top_clients": {"entries": [{"client": "192.168.68.79"}]}}},
        baseline={
            "schema_version": 1,
            "fingerprints": {
                "192.168.68.79": {"udp_ports": [{"port": 5353, "protocol": "udp"}], "last_seen": "2026-05-30T00:00:00Z"}
            },
        },
    )
    hb = ctx["192.168.68.79"]
    assert hb["pihole_seen"] is True
    assert hb["expected_udp_ports"] == [5353]
    assert hb["baseline_udp_ports"] == [5353]
    assert hb["device_hint"] == "homebridge (iot-gateway)"
