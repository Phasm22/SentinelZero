"""
Build per-scan host context for LLM triage — names, network placement, DHCP/ARP, sensors.

Stored on Scan.host_context_json after postprocessing (one enrichment pass per scan).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config.database import db
from ..models.scan import Scan
from . import asset_registry, sensor_service
from .scan_scope import effective_target_network, network_short_label

_NETWORK_JSON = Path(
    os.environ.get(
        "SENTINEL_NETWORK_CONTEXT_PATH",
        os.path.expanduser("~/agent/context/network.json"),
    )
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_network_topology() -> Dict[str, Any]:
    if not _NETWORK_JSON.is_file():
        return {}
    try:
        with _NETWORK_JSON.open(encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}


def _subnet_context(cidr: Optional[str]) -> Dict[str, Any]:
    """Return network.json subnet block + iot_context hints for this CIDR."""
    if not cidr:
        return {}
    topo = _load_network_topology()
    subnets = topo.get("subnets") or {}
    block = subnets.get(cidr)
    out: Dict[str, Any] = {}
    if block:
        out["subnet"] = {
            "cidr": cidr,
            "name": block.get("name"),
            "description": block.get("description"),
            "gateway": block.get("gateway"),
            "dns": block.get("dns"),
            "trust_zone": block.get("trust_zone"),
            "range": block.get("range"),
        }
    iot = topo.get("iot_context") or {}
    label = network_short_label(cidr)
    if label == "Home":
        out["segment_guidance"] = iot.get("home_network_pattern")
    elif label == "Lab":
        out["segment_guidance"] = iot.get("lab_device_expectations")
    sensors = topo.get("sensors") or {}
    if sensors:
        out["available_sensors"] = sensors
    return out


def institutional_memory_for_hosts(host_ips) -> Dict[str, Any]:
    """network.json known_unknowns + Proxmox cluster/standalone notes that match the
    given host IPs. Injected into agent payloads so the model always sees this context
    instead of having to choose to call get_network_topology."""
    ips = {ip for ip in (host_ips or []) if ip}
    if not ips:
        return {}
    topo = _load_network_topology()
    out: Dict[str, Any] = {}

    known = topo.get("known_unknowns") or {}
    matched_unknowns = {ip: known[ip] for ip in ips if ip in known}
    if matched_unknowns:
        out["known_unknowns"] = matched_unknowns

    proxmox = topo.get("proxmox") or {}
    standalone = proxmox.get("standalone") or {}
    matched_standalone = {
        name: meta for name, meta in standalone.items()
        if isinstance(meta, dict) and meta.get("ip") in ips
    }
    if matched_standalone:
        out["proxmox_standalone"] = matched_standalone

    cluster = proxmox.get("cluster_yin_yang") or {}
    members = set(cluster.get("members") or [])
    if members & ips:
        out["proxmox_cluster"] = {
            "members": cluster.get("members"),
            "note": cluster.get("note"),
            "matched_members": sorted(members & ips),
        }
    return out


def _index_opnsense_by_ip(collectors: dict) -> Dict[str, Dict[str, Any]]:
    """Map IP → latest DHCP / ARP fields from OPNsense sensor telemetry."""
    by_ip: Dict[str, Dict[str, Any]] = {}
    for lease in collectors.get("dhcp_leases") or []:
        if not isinstance(lease, dict):
            continue
        ip = lease.get("ip")
        if not ip:
            continue
        by_ip.setdefault(ip, {})["dhcp"] = {
            "hostname": lease.get("hostname") or "",
            "description": lease.get("description") or "",
            "mac": lease.get("mac"),
            "manufacturer": lease.get("manufacturer") or "",
            "interface": lease.get("network") or "",
            "status": lease.get("status"),
            "type": lease.get("type"),
        }
    for entry in collectors.get("arp_table") or []:
        if not isinstance(entry, dict):
            continue
        ip = entry.get("ip")
        if not ip:
            continue
        slot = by_ip.setdefault(ip, {})
        if "arp" not in slot:
            slot["arp"] = {
                "hostname": entry.get("hostname") or "",
                "mac": entry.get("mac"),
                "manufacturer": entry.get("manufacturer") or "",
                "interface": entry.get("network") or entry.get("interface") or "",
                "expired": entry.get("expired"),
            }
    return by_ip


def _port_summary(ports: List[dict], limit: int = 8) -> str:
    parts = []
    for p in (ports or [])[:limit]:
        port = p.get("port")
        svc = p.get("service") or "?"
        prod = p.get("product")
        ver = p.get("version")
        label = f"{port}/{svc}"
        if prod:
            label += f" ({prod}"
            if ver:
                label += f" {ver}"
            label += ")"
        parts.append(label)
    if len(ports or []) > limit:
        parts.append(f"+{len(ports) - limit} more")
    return ", ".join(parts) if parts else "no open ports in scan"


def _pick_display_name(
    ip: str,
    *,
    asset: dict,
    dhcp: Optional[dict],
    arp: Optional[dict],
    nmap_hostnames: List[str],
    sensor_hostname: Optional[str],
    user_label: Optional[str],
) -> str:
    if user_label and str(user_label).strip():
        return str(user_label).strip()
    if asset.get("name") and asset.get("in_registry"):
        return str(asset["name"])
    for src in (
        (dhcp or {}).get("description"),
        (dhcp or {}).get("hostname"),
        (arp or {}).get("hostname"),
    ):
        if src and str(src).strip():
            return str(src).strip()
    if nmap_hostnames:
        return nmap_hostnames[0]
    if sensor_hostname:
        return sensor_hostname
    return ip


def _build_host_entry(
    host: dict,
    *,
    net: Optional[str],
    net_label: str,
    opn_by_ip: Dict[str, Dict[str, Any]],
    existing_hosts: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    ip = host.get("ip")
    if not ip:
        return {}

    prev = (existing_hosts or {}).get(ip) or {}
    user_label = prev.get("user_label")

    asset = asset_registry.get_asset_context(ip, network_cidr=net)
    opn = opn_by_ip.get(ip, {})
    dhcp = opn.get("dhcp")
    arp = opn.get("arp")

    agent = sensor_service.get_agent_by_ip(db, ip)
    sensor_block = None
    if agent:
        sensor_block = {
            "agent_id": agent.agent_id,
            "hostname": agent.hostname,
            "role": agent.role,
            "tags": json.loads(agent.tags or "[]"),
        }

    nmap_hostnames = host.get("hostnames") or []
    display_name = _pick_display_name(
        ip,
        asset=asset,
        dhcp=dhcp,
        arp=arp,
        nmap_hostnames=nmap_hostnames,
        sensor_hostname=agent.hostname if agent else None,
        user_label=user_label,
    )

    mac = host.get("mac") or (dhcp or {}).get("mac") or (arp or {}).get("mac")
    manufacturer = (
        host.get("vendor")
        or (dhcp or {}).get("manufacturer")
        or (arp or {}).get("manufacturer")
    )

    entry: Dict[str, Any] = {
        "ip": ip,
        "display_name": display_name,
        "network_label": net_label,
        "identification_sources": [],
        "asset": asset,
        "trust_zone": asset.get("trust_zone"),
        "role": asset.get("role"),
        "in_asset_registry": bool(asset.get("in_registry")),
        "open_port_summary": _port_summary(host.get("ports") or []),
        "port_count": len(host.get("ports") or []),
    }

    if user_label:
        entry["user_label"] = user_label
    if dhcp:
        entry["dhcp"] = dhcp
        entry["identification_sources"].append("dhcp")
    if arp:
        entry["arp"] = arp
        if "arp" not in entry["identification_sources"]:
            entry["identification_sources"].append("arp")
    if asset.get("in_registry"):
        entry["identification_sources"].append("asset_registry")
    if nmap_hostnames:
        entry["nmap_hostnames"] = nmap_hostnames
        entry["identification_sources"].append("nmap")
    if host.get("os"):
        entry["os"] = host["os"]
    if mac:
        entry["mac"] = mac
    if manufacturer:
        entry["manufacturer"] = manufacturer
    if sensor_block:
        entry["endpoint_sensor"] = sensor_block
        entry["identification_sources"].append("endpoint_sensor")
    if host.get("uptime"):
        entry["uptime"] = host["uptime"]

    # One-line analyst hint for LLM payloads
    hints = [display_name]
    if entry.get("role") and entry["role"] != "unknown":
        hints.append(entry["role"])
    if manufacturer:
        hints.append(manufacturer)
    if entry.get("os", {}).get("name"):
        hints.append(entry["os"]["name"])
    entry["summary_line"] = " · ".join(hints)

    return entry


def build_host_context(scan: Scan, *, preserve_user_labels: bool = True) -> Dict[str, Any]:
    """Assemble host context dict for a scan (does not persist)."""
    try:
        hosts = json.loads(scan.hosts_json) if scan.hosts_json else []
    except (json.JSONDecodeError, TypeError):
        hosts = []

    net = effective_target_network(scan)
    net_label = network_short_label(net)

    existing: Dict[str, Any] = {}
    if preserve_user_labels and getattr(scan, "host_context_json", None):
        try:
            prior = json.loads(scan.host_context_json)
            existing = (prior.get("hosts") or {}) if isinstance(prior, dict) else {}
        except (json.JSONDecodeError, TypeError):
            existing = {}

    opn = sensor_service.get_latest_collectors(db, "opnsense")
    opn_by_ip = _index_opnsense_by_ip(opn) if opn else {}

    host_map: Dict[str, Any] = {}
    for host in hosts:
        if not host.get("ip"):
            continue
        entry = _build_host_entry(
            host,
            net=net,
            net_label=net_label,
            opn_by_ip=opn_by_ip,
            existing_hosts=existing,
        )
        if entry:
            host_map[entry["ip"]] = entry

    return {
        "enriched_at": _now(),
        "target_network": net,
        "network_label": net_label,
        "network": _subnet_context(net),
        "host_count": len(host_map),
        "hosts": host_map,
    }


def store_host_context(scan_id: int) -> Dict[str, Any]:
    """Build and persist host context on the scan row."""
    scan = db.session.get(Scan, scan_id)
    if not scan:
        return {}
    ctx = build_host_context(scan)
    scan.host_context_json = json.dumps(ctx)
    db.session.commit()
    return ctx


def load_host_context(scan: Scan) -> Dict[str, Any]:
    if not scan or not getattr(scan, "host_context_json", None):
        return {}
    try:
        data = json.loads(scan.host_context_json)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def get_host_entry(scan: Scan, ip: str) -> Dict[str, Any]:
    ctx = load_host_context(scan)
    return (ctx.get("hosts") or {}).get(ip) or {}


def apply_user_labels(scan_id: int, labels: Dict[str, str]) -> Dict[str, Any]:
    """Merge user-provided display names (e.g. room/device labels) into host context."""
    scan = db.session.get(Scan, scan_id)
    if not scan:
        return {}
    ctx = load_host_context(scan)
    if not ctx:
        ctx = build_host_context(scan, preserve_user_labels=False)
    hosts = ctx.setdefault("hosts", {})
    for ip, label in (labels or {}).items():
        if not ip or not str(label).strip():
            continue
        entry = hosts.setdefault(ip, {"ip": ip})
        entry["user_label"] = str(label).strip()
        entry["display_name"] = str(label).strip()
        entry["summary_line"] = str(label).strip()
    ctx["labels_updated_at"] = _now()
    scan.host_context_json = json.dumps(ctx)
    db.session.commit()
    return ctx


def digest_for_agent(scan: Scan, max_hosts: int = 40) -> Dict[str, Any]:
    """Compact host context for LLM payloads."""
    ctx = load_host_context(scan)
    if not ctx:
        ctx = build_host_context(scan)
    hosts = ctx.get("hosts") or {}
    lines = []
    for ip, h in list(hosts.items())[:max_hosts]:
        lines.append(
            f"{ip}: {h.get('summary_line', h.get('display_name', ip))} "
            f"({h.get('open_port_summary', '')})"
        )
    return {
        "network_label": ctx.get("network_label"),
        "target_network": ctx.get("target_network"),
        "network": ctx.get("network"),
        "host_count": ctx.get("host_count", len(hosts)),
        "host_lines": lines,
        "hosts": {
            ip: {
                "display_name": h.get("display_name"),
                "summary_line": h.get("summary_line"),
                "role": h.get("role"),
                "trust_zone": h.get("trust_zone"),
                "dhcp_hostname": (h.get("dhcp") or {}).get("hostname"),
                "manufacturer": h.get("manufacturer"),
                "open_port_summary": h.get("open_port_summary"),
                "user_label": h.get("user_label"),
            }
            for ip, h in list(hosts.items())[:max_hosts]
        },
    }
