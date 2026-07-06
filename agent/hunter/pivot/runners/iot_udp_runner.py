from __future__ import annotations

from typing import Any

from hunter.executors.local import LocalExecutor


# Canned port_scan_iot result with UPnP + mDNS confirmed open -- exercises the
# deterministic ``escalate`` path and the upnp/mdns follow-on chain offline.
FIXTURE_IOT_RESULT = {
    "open_ports": [
        {"port": 1900, "protocol": "udp", "state": "open", "service": "upnp"},
        {"port": 5353, "protocol": "udp", "state": "open", "service": "mdns"},
        {"port": 53, "protocol": "udp", "state": "open", "service": "domain"},
    ],
    "count": 3,
    "profile": "iot",
}


def run_iot_udp_probe(
    ip: str,
    *,
    fixture: bool = False,
    iface: str = "enp6s18",
    allowed_cidrs: list[str] | None = None,
    timeout: int = 300,
) -> dict[str, Any]:
    """Wrap LocalExecutor.port_scan_iot (nmap -sU over IoT UDP ports).

    Runs unprivileged via nmap's file capabilities (see LocalExecutor._run --
    ``--privileged`` trusts cap_net_raw/cap_net_admin, no sudo needed).
    """
    if fixture:
        return {"ip": ip, **FIXTURE_IOT_RESULT}

    executor = LocalExecutor(
        iface=iface,
        allowed_cidrs=allowed_cidrs or [],
        timeout_seconds=timeout,
    )
    return executor.port_scan_iot(ip)
