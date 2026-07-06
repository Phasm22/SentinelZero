from __future__ import annotations

from typing import Any

from agent import BASE_URL, _http

from ..opnsense_correlate_parse import build_opnsense_fields


# Canned OPNsense correlation with an IDS alert -- exercises the deterministic
# ``escalate`` path without a backend call.
FIXTURE_OPNSENSE_RESULT = {
    "has_data": True,
    "mac": "bc:24:11:14:87:46",
    "manufacturer": "Proxmox Server Solutions GmbH",
    "arp_hostname": "porttest",
    "dhcp_hostname": "porttest",
    "lease_type": "dynamic",
    "lease_status": "online",
    "ids_alert_count": 1,
    "ids_signatures": ["ET SCAN Potential SSH Scan OUTBOUND"],
}


def _find_opnsense_agent_id(timeout: int) -> str | None:
    try:
        resp = _http.get(f"{BASE_URL}/api/sensor/agents", timeout=timeout)
        resp.raise_for_status()
        for agent in (resp.json().get("agents") or []):
            tags = agent.get("tags") or []
            if agent.get("role") == "network-sensor" and "source:opnsense" in tags:
                return agent.get("agent_id")
    except Exception:
        return None
    return None


def run_opnsense_correlate(ip: str, *, fixture: bool = False, timeout: int = 10) -> dict[str, Any]:
    """Correlate the seed host against the OPNsense network sensor (ARP / DHCP /
    Suricata IDS). Read-only backend API; never probes the target."""
    if fixture:
        return {"ip": ip, **build_opnsense_fields(**FIXTURE_OPNSENSE_RESULT)}

    agent_id = _find_opnsense_agent_id(timeout)
    if not agent_id:
        return {"ip": ip, **build_opnsense_fields(
            has_data=False, mac=None, manufacturer=None, arp_hostname=None,
            dhcp_hostname=None, lease_type=None, lease_status=None,
            ids_alert_count=0, ids_signatures=[],
        )}

    mac = manufacturer = arp_hostname = None
    dhcp_hostname = lease_type = lease_status = None
    ids_signatures: list[str] = []
    try:
        resp = _http.get(f"{BASE_URL}/api/sensor/latest/{agent_id}", timeout=timeout)
        resp.raise_for_status()
        collectors = resp.json().get("collectors") or {}
        for entry in collectors.get("arp_table") or []:
            if str(entry.get("ip") or "") == ip:
                mac = entry.get("mac")
                manufacturer = entry.get("manufacturer")
                arp_hostname = entry.get("hostname")
                break
        for lease in collectors.get("dhcp_leases") or []:
            if str(lease.get("ip") or "") == ip:
                dhcp_hostname = lease.get("hostname")
                lease_type = lease.get("type")
                lease_status = lease.get("status")
                if not mac:
                    mac = lease.get("mac")
                if not manufacturer:
                    manufacturer = lease.get("manufacturer")
                break
        for alert in collectors.get("ids_alerts") or []:
            if str(alert.get("src_ip") or "") == ip or str(alert.get("dest_ip") or "") == ip:
                sig = alert.get("alert")
                if sig:
                    ids_signatures.append(sig)
    except Exception:
        pass

    has_data = bool(mac or arp_hostname or dhcp_hostname or ids_signatures)
    return {"ip": ip, **build_opnsense_fields(
        has_data=has_data, mac=mac, manufacturer=manufacturer, arp_hostname=arp_hostname,
        dhcp_hostname=dhcp_hostname, lease_type=lease_type, lease_status=lease_status,
        ids_alert_count=len(ids_signatures), ids_signatures=ids_signatures,
    )}
