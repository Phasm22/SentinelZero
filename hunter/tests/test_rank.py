from hunter.rank import rank_candidates_with_context
from hunter.seed import SeedResult


def test_rank_candidates_prioritizes_unknown_passive():
    seed = SeedResult(
        mission_id="lab_inventory",
        target_network="172.16.0.0/22",
        registry_hosts=["172.16.0.10"],
        passive_hosts=["172.16.0.10", "172.16.0.184"],
        last_scan_hosts=["172.16.0.10"],
        unknown_in_passive=["172.16.0.184"],
        missing_from_scan=[],
        stale=[],
        last_scan_id=1,
        last_scan_timestamp="2026-05-30T00:00:00Z",
    )
    ranked = rank_candidates_with_context(seed)
    assert ranked[0].ip == "172.16.0.184"
    assert ranked[0].score == 5


def test_rank_candidates_prioritizes_home_iot_role():
    seed = SeedResult(
        mission_id="home_assess",
        target_network="192.168.68.0/22",
        registry_hosts=["192.168.68.79"],
        passive_hosts=["192.168.68.79"],
        last_scan_hosts=["192.168.68.79"],
        unknown_in_passive=[],
        missing_from_scan=[],
        stale=[],
        last_scan_id=1,
        last_scan_timestamp="2026-05-30T00:00:00Z",
    )
    ranked = rank_candidates_with_context(
        seed,
        device_context={"192.168.68.79": {"role": "iot-gateway", "baseline_entry": {"last_seen": "2026-05-30T00:00:00Z"}}},
    )
    assert ranked[0].ip == "192.168.68.79"
    assert ranked[0].score == 5

