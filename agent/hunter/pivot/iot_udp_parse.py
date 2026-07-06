from __future__ import annotations

from typing import Any

# Notable IoT/consumer UDP services -- their exposure is a decision-grade signal
# (UPnP IGD abuse, mDNS info disclosure, RTSP camera streams, SNMP walk).
NOTABLE_UDP_SERVICES = {
    1900: "upnp",
    5353: "mdns",
    554: "rtsp",
    161: "snmp",
}

# UDP ports that unlock a follow-on discovery runner.
UPNP_UDP_PORT = 1900
MDNS_UDP_PORT = 5353


def _open_udp_ports(scan: dict[str, Any]) -> list[dict[str, Any]]:
    return [p for p in (scan.get("open_ports") or []) if p.get("state") == "open"]


def recommend_iot_action(scan: dict[str, Any]) -> str:
    """Decision-grade triage for an iot_udp_probe finding.

    - ``escalate``: a notable IoT UDP service is confirmed open (UPnP/mDNS/RTSP/SNMP).
    - ``next_scan``: only ``open|filtered`` UDP responses (ambiguous -- worth a
      closer look but not confirmed).
    - ``observe``: nothing notable exposed.
    """
    confirmed = _open_udp_ports(scan)
    if any(int(p.get("port", 0)) in NOTABLE_UDP_SERVICES for p in confirmed):
        return "escalate"
    ambiguous = [
        p for p in (scan.get("open_ports") or [])
        if p.get("state") == "open|filtered" and int(p.get("port", 0)) in NOTABLE_UDP_SERVICES
    ]
    if ambiguous:
        return "next_scan"
    return "observe"


def summarize_iot(scan: dict[str, Any]) -> dict[str, Any]:
    """Structured summary fields for the pivot_iot_exposure finding."""
    open_ports = scan.get("open_ports") or []
    confirmed = _open_udp_ports(scan)
    exposed_services = sorted({
        NOTABLE_UDP_SERVICES[int(p.get("port", 0))]
        for p in confirmed
        if int(p.get("port", 0)) in NOTABLE_UDP_SERVICES
    })
    return {
        "udp_ports": open_ports,
        "exposed_services": exposed_services,
        "upnp_open": any(int(p.get("port", 0)) == UPNP_UDP_PORT for p in confirmed),
        "mdns_open": any(int(p.get("port", 0)) == MDNS_UDP_PORT for p in confirmed),
    }
