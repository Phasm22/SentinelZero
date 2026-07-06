from __future__ import annotations

from typing import Any


def recommend_opnsense_action(
    *,
    has_data: bool,
    ids_alert_count: int,
) -> str:
    """Decision-grade triage for an opnsense_correlate finding.

    - ``escalate``: the OPNsense IDS (Suricata) has alerts referencing this host
      -- it is a party to flagged traffic.
    - ``next_scan``: no OPNsense sensor data covers this host.
    - ``observe``: known on the segment (ARP/DHCP), no IDS alerts.
    """
    if not has_data:
        return "next_scan"
    if ids_alert_count > 0:
        return "escalate"
    return "observe"


def build_opnsense_fields(
    *,
    has_data: bool,
    mac: str | None,
    manufacturer: str | None,
    arp_hostname: str | None,
    dhcp_hostname: str | None,
    lease_type: str | None,
    lease_status: str | None,
    ids_alert_count: int,
    ids_signatures: list[str] | None,
) -> dict[str, Any]:
    return {
        "has_data": has_data,
        "mac": mac,
        "manufacturer": manufacturer,
        "arp_hostname": arp_hostname or None,
        "dhcp_hostname": dhcp_hostname or None,
        "lease_type": lease_type,
        "lease_status": lease_status,
        "ids_alert_count": ids_alert_count,
        "ids_signatures": sorted(set(ids_signatures or [])),
    }
