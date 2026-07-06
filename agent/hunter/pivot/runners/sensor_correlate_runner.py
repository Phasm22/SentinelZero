from __future__ import annotations

import ipaddress
from typing import Any

from agent import BASE_URL, _http

from ..sensor_correlate_parse import build_sensor_fields


# Canned endpoint-sensor correlation with an external peer + auth event --
# exercises the deterministic ``escalate`` path without a backend call.
FIXTURE_SENSOR_RESULT = {
    "has_sensor": True,
    "agent": {"agent_id": "porttest", "role": "endpoint", "status": "active",
              "last_seen_at": "2026-07-06T03:00:00"},
    "listening_ports": [22, 80, 443],
    "established_peers": ["172.16.0.5", "203.0.113.9"],
    "external_peers": ["203.0.113.9"],
    "auth_event_count": 2,
    "process_count": 180,
    "service_count": 60,
}


def _port_of(addr: str | None) -> int | None:
    if not addr or ":" not in addr:
        return None
    try:
        return int(addr.rsplit(":", 1)[1])
    except ValueError:
        return None


def _ip_of(addr: str | None) -> str | None:
    if not addr or ":" not in addr:
        return None
    return addr.rsplit(":", 1)[0]


def _is_external(ip: str | None) -> bool:
    if not ip:
        return False
    try:
        return not ipaddress.ip_address(ip).is_private
    except ValueError:
        return False


def run_sensor_correlate(ip: str, *, fixture: bool = False, timeout: int = 10) -> dict[str, Any]:
    """Correlate the seed host against its endpoint sensor telemetry (read-only
    backend API; no network probe of the target)."""
    if fixture:
        return {"ip": ip, **build_sensor_fields(**FIXTURE_SENSOR_RESULT)}

    agent: dict[str, Any] | None = None
    try:
        resp = _http.get(f"{BASE_URL}/api/sensor/agents", timeout=timeout)
        resp.raise_for_status()
        for candidate in (resp.json().get("agents") or []):
            if str(candidate.get("host_ip") or "") == ip:
                agent = candidate
                break
    except Exception:
        agent = None

    if agent is None:
        return {"ip": ip, **build_sensor_fields(
            has_sensor=False, agent=None, listening_ports=[], established_peers=[],
            external_peers=[], auth_event_count=0, process_count=0, service_count=0,
        )}

    listening: list[int] = []
    established: list[str] = []
    external: list[str] = []
    auth_count = 0
    proc_count = 0
    svc_count = 0
    try:
        resp = _http.get(f"{BASE_URL}/api/sensor/latest/{agent.get('agent_id')}", timeout=timeout)
        resp.raise_for_status()
        collectors = resp.json().get("collectors") or {}
        for conn in collectors.get("connections") or []:
            state = conn.get("state")
            if state == "LISTEN":
                port = _port_of(conn.get("local_addr"))
                if port is not None:
                    listening.append(port)
            elif state == "ESTABLISHED":
                peer = _ip_of(conn.get("remote_addr"))
                if peer:
                    established.append(peer)
                    if _is_external(peer):
                        external.append(peer)
        auth_count = len(collectors.get("auth") or [])
        proc_count = len(collectors.get("processes") or [])
        svc_count = len(collectors.get("services") or [])
    except Exception:
        pass

    return {"ip": ip, **build_sensor_fields(
        has_sensor=True, agent=agent, listening_ports=listening,
        established_peers=established, external_peers=external,
        auth_event_count=auth_count, process_count=proc_count, service_count=svc_count,
    )}
