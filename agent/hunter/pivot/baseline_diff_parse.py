from __future__ import annotations

from typing import Any


def recommend_baseline_action(
    *,
    baseline_present: bool,
    new_udp_ports: list[int] | None,
) -> str:
    """Decision-grade triage for a baseline_diff finding.

    - ``escalate``: the host exposes a UDP service it did not have at baseline --
      fingerprint drift worth investigating.
    - ``next_scan``: no prior baseline for this host (first observation; nothing
      to compare against yet).
    - ``observe``: current UDP fingerprint matches the baseline.
    """
    if not baseline_present:
        return "next_scan"
    if new_udp_ports or []:
        return "escalate"
    return "observe"


def diff_udp_ports(
    baseline_ports: list[dict[str, Any]] | None,
    current_ports: list[dict[str, Any]] | None,
) -> dict[str, list[int]]:
    """Compare baseline vs current open UDP port sets."""
    base = {int(p.get("port")) for p in (baseline_ports or []) if p.get("port") is not None
            and str(p.get("state") or "open") == "open"}
    curr = {int(p.get("port")) for p in (current_ports or []) if p.get("port") is not None
            and str(p.get("state") or "open") == "open"}
    return {
        "new_udp_ports": sorted(curr - base),
        "removed_udp_ports": sorted(base - curr),
        "matched_udp_ports": sorted(base & curr),
    }


def build_baseline_fields(
    *,
    baseline_present: bool,
    entry: dict[str, Any] | None,
    diff: dict[str, list[int]],
) -> dict[str, Any]:
    return {
        "baseline_present": baseline_present,
        "new_udp_ports": diff["new_udp_ports"],
        "removed_udp_ports": diff["removed_udp_ports"],
        "matched_udp_ports": diff["matched_udp_ports"],
        "observation_count": (entry or {}).get("observation_count"),
        "first_seen": (entry or {}).get("first_seen"),
        "last_seen": (entry or {}).get("last_seen"),
        "device_hint": (entry or {}).get("device_hint"),
    }
