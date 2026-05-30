"""Load the shared asset registry used by the analysis agent and insight enrichment."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

_DEFAULT_PATH = Path(os.path.expanduser("~/agent/context/assets.json"))

# Trust zones where missing registry / sensor is actionable on lab scans.
_LAB_STRICT_TRUST_ZONES = frozenset({
    "infrastructure", "management", "lab",
})

# Home hosts we expect endpoint sensors on (explicit registry entries only).
_HOME_SENSOR_TRUST_ZONES = frozenset({
    "home-infrastructure", "management", "user",
})


def assets_path() -> Path:
    return Path(os.environ.get("SENTINEL_ASSETS_PATH", str(_DEFAULT_PATH)))


@lru_cache(maxsize=1)
def _load_registry() -> Dict[str, Any]:
    path = assets_path()
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def ip_matches_network(ip: str, cidr: Optional[str]) -> bool:
    """Rough CIDR membership for lab/home scopes used by SentinelZero."""
    if not cidr or not ip:
        return True
    cidr = str(cidr).strip()
    if "172.16." in cidr or cidr.startswith("172.16"):
        return ip.startswith("172.16.")
    if "192.168.68" in cidr or "192.168.71" in cidr:
        return ip.startswith(("192.168.68.", "192.168.71."))
    return True


def is_lab_network(cidr: Optional[str]) -> bool:
    if not cidr:
        return False
    c = str(cidr).strip()
    return "172.16." in c or c.startswith("172.16")


def is_home_network(cidr: Optional[str]) -> bool:
    if not cidr:
        return False
    c = str(cidr).strip()
    return "192.168.68" in c or "192.168.71" in c


def registry_strict_for_network(cidr: Optional[str]) -> bool:
    """Lab: registry gaps are triage backlog. Home: documentation-only."""
    return is_lab_network(cidr) and not is_home_network(cidr)


def get_asset_context(ip: str, *, network_cidr: Optional[str] = None) -> Dict[str, Any]:
    """Return registry entry for an IP, or a minimal unknown-host stub."""
    assets = _load_registry()
    entry = assets.get(ip)
    if entry:
        ctx = dict(entry)
        ctx["in_registry"] = True
        ctx.setdefault("name", ip)
        return ctx

    home = is_home_network(network_cidr) or ip.startswith(("192.168.68.", "192.168.71."))
    lab = is_lab_network(network_cidr) or ip.startswith("172.16.")

    if home:
        return {
            "name": ip,
            "role": "unknown",
            "trust_zone": "home",
            "expected_ports": [],
            "in_registry": False,
            "note": (
                "Home network host — not individually documented in assets.json. "
                "Consumer/IoT devices are often intentionally unlisted; compare to prior "
                "Home scans, not the lab asset registry."
            ),
        }
    if lab:
        return {
            "name": ip,
            "role": "unknown",
            "trust_zone": "unknown",
            "expected_ports": [],
            "in_registry": False,
            "note": "Unknown host in lab network — not in asset registry",
        }
    return {
        "name": ip,
        "role": "unknown",
        "trust_zone": "unknown",
        "expected_ports": [],
        "in_registry": False,
        "note": "Unknown host — not in asset registry",
    }


def is_in_registry(ip: str) -> bool:
    """True if IP has an explicit entry in assets.json (not a prefix stub)."""
    return ip in _load_registry()


def hosts_for_registry_gap(ips: List[str], network_cidr: Optional[str]) -> List[str]:
    """IPs that should generate a registry_gap insight for this scan scope."""
    if is_home_network(network_cidr):
        return []
    return [ip for ip in ips if ip_matches_network(ip, network_cidr) and not is_in_registry(ip)]


def hosts_for_inventory_gap(
    discovered_ips: List[str], network_cidr: Optional[str],
) -> List[str]:
    """Registered hosts in scope that did not appear in this scan."""
    if is_home_network(network_cidr):
        return []
    seen = set(discovered_ips)
    registry = _load_registry()
    missing = [
        ip for ip in registry
        if ip_matches_network(ip, network_cidr) and ip not in seen
    ]
    return sorted(missing, key=lambda x: tuple(int(p) for p in x.split('.')))


def hosts_for_sensor_gap(ips: List[str], network_cidr: Optional[str]) -> List[str]:
    """
    IPs lacking endpoint sensor coverage that matter for this network.
    Home: only registered infrastructure/user hosts. Lab: all discovered hosts.
    """
    from . import sensor_service
    from ..config.database import db

    gaps: List[str] = []
    for ip in ips:
        if not ip_matches_network(ip, network_cidr):
            continue
        if is_home_network(network_cidr):
            if not is_in_registry(ip):
                continue
            ctx = get_asset_context(ip, network_cidr=network_cidr)
            if ctx.get("trust_zone") not in _HOME_SENSOR_TRUST_ZONES:
                continue
        agent = sensor_service.get_agent_by_ip(db, ip)
        if not agent:
            gaps.append(ip)
            continue
        tags = json.loads(agent.tags or "[]")
        if "category:network" in tags:
            gaps.append(ip)
    return gaps


def is_expected_port(ip: str, port: int, *, network_cidr: Optional[str] = None) -> Optional[bool]:
    """True if port is in expected_ports, False if known host but unexpected, None if unknown host."""
    ctx = get_asset_context(ip, network_cidr=network_cidr)
    expected = ctx.get("expected_ports") or []
    if not expected and ctx.get("trust_zone") in ("unknown", "home"):
        return None
    return port in expected
