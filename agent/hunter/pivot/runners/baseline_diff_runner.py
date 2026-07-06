from __future__ import annotations

from typing import Any

from hunter.baseline import get_fingerprint, load_baseline

from ..baseline_diff_parse import build_baseline_fields, diff_udp_ports


# Canned baseline with a new UDP port since last observation -- exercises the
# deterministic ``escalate`` (drift) path without touching the state file.
FIXTURE_BASELINE_RESULT = {
    "baseline_present": True,
    "entry": {"observation_count": 4, "first_seen": "2026-06-01T00:00:00Z",
              "last_seen": "2026-07-01T00:00:00Z", "device_hint": "iot-camera"},
    "diff": {"new_udp_ports": [554], "removed_udp_ports": [], "matched_udp_ports": [1900, 5353]},
}


def run_baseline_diff(
    ip: str,
    current_udp_ports: list[dict[str, Any]] | None,
    *,
    fixture: bool = False,
) -> dict[str, Any]:
    """Compare the host's current UDP fingerprint against the hunter baseline
    (``agent/state/iot_fingerprints.json``). Read-only file access; no probe."""
    if fixture:
        return {"ip": ip, **build_baseline_fields(**FIXTURE_BASELINE_RESULT)}

    payload = load_baseline()
    entry = get_fingerprint(payload, ip)
    baseline_present = entry is not None
    diff = diff_udp_ports(
        (entry or {}).get("udp_ports"),
        current_udp_ports,
    )
    return {"ip": ip, **build_baseline_fields(
        baseline_present=baseline_present, entry=entry, diff=diff,
    )}
