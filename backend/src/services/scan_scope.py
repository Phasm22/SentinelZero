"""Target network scope for scans — baseline and diff are per (scan_type, CIDR)."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from ..models.scan import Scan

DEFAULT_LAB_CIDR = "172.16.0.0/22"
DEFAULT_HOME_CIDR = "192.168.68.0/22"


def normalize_cidr(cidr: Optional[str]) -> Optional[str]:
    if not cidr or not str(cidr).strip():
        return None
    return str(cidr).strip()


def infer_target_network_from_hosts(hosts: List[Dict[str, Any]]) -> Optional[str]:
    """Guess CIDR from host IPs when target_network was not stored (legacy scans)."""
    lab = home = other = 0
    for host in hosts or []:
        ip = (host.get("ip") or "").strip()
        if ip.startswith("172.16."):
            lab += 1
        elif ip.startswith(("192.168.68.", "192.168.71.")):
            home += 1
        elif ip:
            other += 1
    if lab > home and lab >= 1:
        return DEFAULT_LAB_CIDR
    if home >= 1 and home >= lab:
        return DEFAULT_HOME_CIDR
    if lab >= 1:
        return DEFAULT_LAB_CIDR
    return None


def effective_target_network(scan: Scan) -> Optional[str]:
    stored = normalize_cidr(getattr(scan, "target_network", None))
    if stored:
        return stored
    try:
        hosts = json.loads(scan.hosts_json) if scan.hosts_json else []
    except (json.JSONDecodeError, TypeError):
        hosts = []
    return infer_target_network_from_hosts(hosts)


def is_home_network(cidr: Optional[str]) -> bool:
    cidr = normalize_cidr(cidr) or ""
    return "192.168.68" in cidr or "192.168.71" in cidr


def is_lab_network(cidr: Optional[str]) -> bool:
    cidr = normalize_cidr(cidr) or ""
    return "172.16." in cidr or cidr.startswith("172.16")


def network_short_label(cidr: Optional[str]) -> str:
    cidr = normalize_cidr(cidr) or ""
    if "172.16." in cidr or cidr.startswith("172.16"):
        return "Lab"
    if "192.168.68" in cidr or "192.168.71" in cidr:
        return "Home"
    if cidr:
        return cidr
    return "Unknown"


def scope_display(scan: Scan) -> str:
    """Human label for UI: 'Full TCP · Home (192.168.68.0/22)'."""
    net = effective_target_network(scan)
    label = network_short_label(net)
    if net:
        return f"{label} ({net})"
    return label


def find_previous_scan(current: Scan) -> Optional[Scan]:
    """Most recent completed scan of same type on the same target network."""
    current_net = effective_target_network(current)
    candidates = (
        Scan.query.filter(
            Scan.scan_type == current.scan_type,
            Scan.id != current.id,
            Scan.status == "complete",
        )
        .order_by(Scan.created_at.desc())
        .all()
    )
    for scan in candidates:
        if effective_target_network(scan) == current_net:
            return scan
    return None


def scan_scope_dict(scan: Scan) -> Dict[str, Optional[str]]:
    net = effective_target_network(scan)
    return {
        "target_network": net,
        "network_label": network_short_label(net),
        "scope_display": scope_display(scan),
    }
