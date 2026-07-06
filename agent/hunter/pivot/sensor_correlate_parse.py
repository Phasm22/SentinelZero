from __future__ import annotations

from typing import Any


def recommend_sensor_action(
    *,
    has_sensor: bool,
    auth_event_count: int,
    external_peers: list[str] | None,
) -> str:
    """Decision-grade triage for a sensor_correlate finding.

    - ``escalate``: the endpoint sensor reports authentication events or an
      established connection to a non-RFC1918 (external) peer -- ground truth a
      network scan cannot see.
    - ``next_scan``: no endpoint sensor covers this host (a coverage gap; deeper
      scanning is the only visibility).
    - ``observe``: sensor present, nothing anomalous.
    """
    if not has_sensor:
        return "next_scan"
    if auth_event_count > 0 or (external_peers or []):
        return "escalate"
    return "observe"


def build_sensor_fields(
    *,
    has_sensor: bool,
    agent: dict[str, Any] | None,
    listening_ports: list[int],
    established_peers: list[str],
    external_peers: list[str],
    auth_event_count: int,
    process_count: int,
    service_count: int,
) -> dict[str, Any]:
    return {
        "has_sensor": has_sensor,
        "agent_id": (agent or {}).get("agent_id"),
        "role": (agent or {}).get("role"),
        "status": (agent or {}).get("status"),
        "last_seen_at": (agent or {}).get("last_seen_at"),
        "listening_ports": sorted(set(listening_ports)),
        "established_peers": sorted(set(established_peers)),
        "external_peers": sorted(set(external_peers)),
        "auth_event_count": auth_event_count,
        "process_count": process_count,
        "service_count": service_count,
    }
