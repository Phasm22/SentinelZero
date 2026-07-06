from __future__ import annotations

import subprocess
from typing import Any


FIXTURE_SMB_OUTPUT = {
    "ip": "",
    "shares": ["IPC$", "tmp"],
    "smb_signing": False,
    "guest_access": False,
    "notes": "fixture smb enumeration",
}


def run_smb_enum(ip: str, *, fixture: bool = False, timeout: int = 120) -> dict[str, Any]:
    if fixture:
        payload = dict(FIXTURE_SMB_OUTPUT)
        payload["ip"] = ip
        return payload

    # Lightweight share listing via smbclient if available; fall back to nmap script.
    result = subprocess.run(
        ["nmap", "-Pn", "-p445", "--script", "smb-enum-shares", "-oN", "-", ip],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0 and not result.stdout:
        return {"ip": ip, "error": result.stderr.strip() or "smb enum failed", "shares": []}

    shares: list[str] = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("Sharename"):
            continue
        if stripped and not stripped.startswith("-"):
            token = stripped.split()[0]
            if token not in {"Account", "Domain", "Server"}:
                shares.append(token)

    return {
        "ip": ip,
        "shares": sorted(set(shares)),
        "raw_excerpt": result.stdout[:2000],
    }
