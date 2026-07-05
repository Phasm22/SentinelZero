from __future__ import annotations

import ipaddress
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


@dataclass
class SeedResult:
    mission_id: str
    target_network: str
    registry_hosts: list[str]
    passive_hosts: list[str]
    last_scan_hosts: list[str]
    unknown_in_passive: list[str]
    missing_from_scan: list[str]
    stale: list[str]
    last_scan_id: int | None
    last_scan_timestamp: str | None
    device_context: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "target_network": self.target_network,
            "registry_hosts": self.registry_hosts,
            "passive_hosts": self.passive_hosts,
            "last_scan_hosts": self.last_scan_hosts,
            "unknown_in_passive": self.unknown_in_passive,
            "missing_from_scan": self.missing_from_scan,
            "stale": self.stale,
            "last_scan_id": self.last_scan_id,
            "last_scan_timestamp": self.last_scan_timestamp,
            "device_context": self.device_context,
        }


def _ip_key(value: str) -> tuple[int, int, int, int]:
    return tuple(int(p) for p in value.split("."))


def _in_cidr(ip: str, cidr: str) -> bool:
    try:
        return ipaddress.ip_address(ip) in ipaddress.ip_network(cidr, strict=False)
    except Exception:
        return False


def _in_any_cidr(ip: str, cidrs: list[str]) -> bool:
    return any(_in_cidr(ip, c) for c in cidrs)


def _load_registry(assets_path: Path, allowed_cidrs: list[str]) -> set[str]:
    try:
        assets = json.loads(assets_path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    return {ip for ip in assets.keys() if _in_any_cidr(ip, allowed_cidrs)}


def _collect_opnsense_ips(payload: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    collectors = payload.get("collectors") or {}
    arp_block = collectors.get("arp_table") or []
    if isinstance(arp_block, dict):
        arp = arp_block.get("entries") or []
    elif isinstance(arp_block, list):
        arp = arp_block
    else:
        arp = []
    for row in arp:
        ip = str((row or {}).get("ip") or "").strip()
        if ip:
            out.add(ip)
    dhcp_block = collectors.get("dhcp_leases") or []
    if isinstance(dhcp_block, dict):
        dhcp = dhcp_block.get("entries") or []
    elif isinstance(dhcp_block, list):
        dhcp = dhcp_block
    else:
        dhcp = []
    for row in dhcp:
        ip = str((row or {}).get("ip") or "").strip()
        if ip:
            out.add(ip)
    return out


def _collect_pihole_ips(payload: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    collectors = payload.get("collectors") or {}
    for key in ("top_clients", "summary"):
        block = collectors.get(key) or []
        if isinstance(block, dict):
            rows = block.get("entries") or []
        elif isinstance(block, list):
            rows = block
        else:
            rows = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            ip = str((row.get("client") or row.get("ip") or row.get("name") or "")).strip()
            if ip and " " in ip:
                ip = ip.split(" ")[0]
            if ip and ip.count(".") == 3:
                out.add(ip)
    return out


def _parse_scan_timestamp(scan: dict[str, Any]) -> datetime | None:
    raw = (
        scan.get("completed_at")
        or scan.get("timestamp")
        or scan.get("created_at")
        or scan.get("updated_at")
    )
    if not raw:
        return None
    text = str(raw).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _pick_latest_scan(scans: list[dict[str, Any]], target_network: str) -> dict[str, Any] | None:
    same_net = [
        s for s in scans
        if str(s.get("target_network") or "").strip() == target_network
        and str(s.get("status") or "").lower() == "complete"
    ]
    if not same_net:
        return None
    same_net.sort(key=lambda s: _parse_scan_timestamp(s) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return same_net[0]


def _extract_scan_hosts(scan: dict[str, Any], target_network: str) -> set[str]:
    hosts = scan.get("hosts") or []
    out: set[str] = set()
    for host in hosts:
        ip = str((host or {}).get("ip") or "").strip()
        if ip and _in_cidr(ip, target_network):
            out.add(ip)
    return out


def build_seed_result(
    *,
    mission_id: str,
    target_network: str,
    allowed_cidrs: list[str],
    assets_path: Path,
    opnsense_latest: dict[str, Any],
    pihole_latest: dict[str, Any],
    scans_payload: dict[str, Any] | list[dict[str, Any]],
    stale_days: int = 7,
    device_context: dict[str, dict[str, Any]] | None = None,
) -> SeedResult:
    registry_hosts = _load_registry(assets_path, allowed_cidrs)

    passive = _collect_opnsense_ips(opnsense_latest) | _collect_pihole_ips(pihole_latest)
    passive = {ip for ip in passive if _in_any_cidr(ip, allowed_cidrs)}

    scans = scans_payload if isinstance(scans_payload, list) else (scans_payload.get("scans") or [])
    latest = _pick_latest_scan(scans, target_network) if isinstance(scans, list) else None
    latest_hosts = _extract_scan_hosts(latest or {}, target_network)

    unknown_in_passive = sorted(passive - registry_hosts, key=_ip_key)
    missing_from_scan = sorted(registry_hosts - latest_hosts, key=_ip_key)

    stale: list[str] = []
    latest_dt = _parse_scan_timestamp(latest or {})
    if latest_dt and latest_dt < datetime.now(timezone.utc) - timedelta(days=stale_days):
        stale = sorted(registry_hosts, key=_ip_key)

    return SeedResult(
        mission_id=mission_id,
        target_network=target_network,
        registry_hosts=sorted(registry_hosts, key=_ip_key),
        passive_hosts=sorted(passive, key=_ip_key),
        last_scan_hosts=sorted(latest_hosts, key=_ip_key),
        unknown_in_passive=unknown_in_passive,
        missing_from_scan=missing_from_scan,
        stale=stale,
        last_scan_id=(latest or {}).get("id"),
        last_scan_timestamp=((latest or {}).get("completed_at") or (latest or {}).get("timestamp")),
        device_context=device_context or {},
    )

