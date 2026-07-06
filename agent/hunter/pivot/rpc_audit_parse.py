from __future__ import annotations

import re
from typing import Any

# NSE script ids the pivot engine treats as passive RPC enumeration -- portmapper
# program listing, never mount/exploitation.
RPC_AUDIT_SCRIPT_IDS = frozenset({"rpcinfo"})

# Port the pivot engine treats as an RPC portmapper surface.
RPC_PORTS: tuple[int, ...] = (111,)

# RPC services whose reachability is a real data/attack-surface exposure (NFS
# export access, NIS maps, quota) -- as opposed to bare portmapper/status.
_SENSITIVE_SERVICES = frozenset({
    "nfs", "nfs_acl", "mountd", "nlockmgr", "ypserv", "ypbind", "yppasswdd",
    "rquotad", "sgi_fam",
})

# rpcinfo output row: "  100003  3,4         2049/tcp   nfs"
_ROW = re.compile(
    r"^\s*(\d{5,})\s+([\d,]+)\s+(\d+)/(\w+)\s+(\S+)\s*$"
)


def recommend_rpc_action(
    *,
    sensitive_services: list[str] | None,
    programs_parsed: bool,
) -> str:
    """Decision-grade triage for an rpc_audit finding.

    Returns one of ``escalate`` | ``next_scan`` | ``observe`` (never a blue-team
    verdict). Shared by the live rpc_audit dispatch and the hydrated-evidence
    finding so both paths grade identically.

    - ``escalate``: a data/attack-surface RPC service is reachable (NFS/mountd/
      NIS/quota) -- e.g. an exported filesystem may be mountable.
    - ``next_scan``: portmapper answered but no program list could be parsed.
    - ``observe``: only portmapper/status is registered.
    """
    if not programs_parsed:
        return "next_scan"
    if sensitive_services or []:
        return "escalate"
    return "observe"


def parse_rpc_scripts(scripts: dict[str, str]) -> dict[str, Any]:
    """Turn a {script_id: raw nmap script output} map into structured rpc_audit fields.

    Shared by hydration.py (reading a prior scan's vulns_json) and rpc_audit_runner.py
    (reading a fresh nmap NSE run) so both sources produce identical finding shapes.
    """
    programs: list[dict[str, Any]] = []
    seen: set[tuple[int, str]] = set()
    for raw in (scripts.get("rpcinfo") or "").splitlines():
        match = _ROW.match(raw)
        if not match:
            continue
        program = int(match.group(1))
        versions = [int(v) for v in match.group(2).split(",") if v.strip().isdigit()]
        proto = match.group(4)
        service = match.group(5)
        # Collapse the ipv4/ipv6/udp rows into one program+service entry.
        key = (program, service)
        if key in seen:
            continue
        seen.add(key)
        programs.append({
            "program": program,
            "versions": versions,
            "port": int(match.group(3)),
            "proto": proto,
            "service": service,
        })

    services = sorted({p["service"] for p in programs})
    sensitive_services = [s for s in services if s in _SENSITIVE_SERVICES]

    return {
        "programs": programs,
        "services": services,
        "sensitive_services": sensitive_services,
        "programs_parsed": bool(programs),
    }
