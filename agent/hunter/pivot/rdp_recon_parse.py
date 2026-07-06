from __future__ import annotations

import re
from typing import Any

# NSE script ids the pivot engine treats as passive RDP fingerprinting -- the
# NTLM identity blob and security-layer enumeration from the RDP handshake,
# never a credential/CredSSP authentication attempt.
RDP_RECON_SCRIPT_IDS = frozenset({
    "rdp-ntlm-info",
    "rdp-enum-encryption",
})

# Port the pivot engine treats as an RDP surface.
RDP_PORTS: tuple[int, ...] = (3389,)


def recommend_rdp_action(
    *,
    responded: bool,
    nla_enabled: bool,
    parsed: bool,
) -> str:
    """Decision-grade triage for an rdp_recon finding.

    Returns one of ``escalate`` | ``next_scan`` | ``observe`` (never a blue-team
    verdict). Shared by the live rdp_recon dispatch and any hydrated finding so
    both paths grade identically.

    - ``escalate``: RDP is reachable but Network Level Authentication (CredSSP)
      is NOT enforced -- the pre-auth surface is exposed (BlueKeep/DejaBlue
      class), and the RDP identity is disclosed to unauthenticated clients.
    - ``next_scan``: 3389 answered but neither identity nor encryption parsed.
    - ``observe``: NLA is enforced.
    """
    if not parsed:
        return "next_scan" if responded else "observe"
    if not nla_enabled:
        return "escalate"
    return "observe"


def _parse_ntlm(output: str) -> dict[str, Any]:
    fields: dict[str, str] = {}
    for key in (
        "Target_Name", "NetBIOS_Domain_Name", "NetBIOS_Computer_Name",
        "DNS_Domain_Name", "DNS_Computer_Name", "Product_Version",
    ):
        match = re.search(rf"^\s*{key}:\s*(.+)$", output, re.MULTILINE)
        if match:
            fields[key] = match.group(1).strip()
    return fields


def _parse_encryption(output: str) -> dict[str, Any]:
    # Lines look like "    CredSSP (NLA): SUCCESS" under "Security layer".
    layers: list[str] = []
    for match in re.finditer(r"^\s{2,}([A-Za-z0-9 ()/_-]+?):\s*(SUCCESS|FAILED)\s*$", output, re.MULTILINE):
        name, status = match.group(1).strip(), match.group(2)
        if name.lower() == "security layer":
            continue
        if status == "SUCCESS":
            layers.append(name)
    nla_enabled = any("credssp" in layer.lower() for layer in layers)
    return {"security_layers": layers, "nla_enabled": nla_enabled}


def parse_rdp_scripts(scripts: dict[str, str]) -> dict[str, Any]:
    """Turn a {script_id: raw nmap script output} map into structured rdp_recon fields.

    Shared by hydration.py (reading a prior scan's vulns_json) and rdp_recon_runner.py
    (reading a fresh nmap NSE run) so both sources produce identical finding shapes.
    """
    ntlm = _parse_ntlm(scripts.get("rdp-ntlm-info") or "")
    enc = _parse_encryption(scripts.get("rdp-enum-encryption") or "")

    hostname = ntlm.get("DNS_Computer_Name") or ntlm.get("NetBIOS_Computer_Name") or ntlm.get("Target_Name")
    domain = ntlm.get("DNS_Domain_Name") or ntlm.get("NetBIOS_Domain_Name")
    os_build = ntlm.get("Product_Version")

    parsed = bool(ntlm or enc.get("security_layers"))

    return {
        "hostname": hostname,
        "domain": domain,
        "os_build": os_build,
        "nla_enabled": enc.get("nla_enabled", False),
        "security_layers": enc.get("security_layers", []),
        "parsed": parsed,
    }
