from pathlib import Path

from hunter.executors.local import LocalExecutor
from hunter.missions import Mission
from hunter.seed import SeedResult
from hunter.tools import HunterRuntime, tool_schemas_for_runtime


def _seed() -> SeedResult:
    return SeedResult(
        mission_id="home_assess",
        target_network="192.168.68.0/22",
        registry_hosts=[],
        passive_hosts=[],
        last_scan_hosts=[],
        unknown_in_passive=[],
        missing_from_scan=[],
        stale=[],
        last_scan_id=None,
        last_scan_timestamp=None,
    )


def _mission(profile: str) -> Mission:
    return Mission(
        mission_id="home_assess",
        objective="test",
        target_network="192.168.68.0/22",
        profile=profile,
        executor="local",
        iface="enp6s19",
        max_turns=40,
        parallel_workers=1,
        handoff_scan_type="Discovery Scan",
        handoff_trigger_discovery_scan=False,
        handoff_min_new_hosts=1,
        handoff_max_recommended_hosts=10,
        allowed_cidrs=["192.168.68.0/22"],
    )


def _runtime(profile: str) -> HunterRuntime:
    return HunterRuntime(
        mission=_mission(profile),
        executor=LocalExecutor(iface="enp6s19", allowed_cidrs=["192.168.68.0/22"]),
        seed_result=_seed(),
        ranked_candidates=[],
        reports_dir=Path("/tmp"),
    )


def test_iot_tool_hidden_for_white_profile():
    names = {t["function"]["name"] for t in tool_schemas_for_runtime(_runtime("white"))}
    assert "port_scan_iot" not in names


def test_iot_tool_enabled_for_assess_profile():
    names = {t["function"]["name"] for t in tool_schemas_for_runtime(_runtime("assess"))}
    assert "port_scan_iot" in names


def test_iot_scan_rejected_for_white_profile_runtime():
    out = _runtime("white").port_scan_iot("192.168.68.20")
    assert "only available for assess profile" in out["error"]


def test_iot_scan_rejected_when_not_flagged():
    out = _runtime("assess").port_scan_iot("192.168.68.20")
    assert "not a flagged host" in out["error"]

