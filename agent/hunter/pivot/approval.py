from __future__ import annotations

PASSIVE_TOOLS = frozenset({
    "nmap_scan", "http_recon", "tls_recon", "ssh_audit", "rpc_audit", "proxmox_recon",
    "rdp_recon", "asset_expectation_check", "triage", "complete",
})
ACTIVE_TOOLS = frozenset({"smb_enum", "nuclei_active", "credential_spray"})


def tool_classification(tool_name: str) -> str:
    if tool_name in ACTIVE_TOOLS:
        return "active"
    if tool_name in PASSIVE_TOOLS:
        return "passive"
    return "active"


def requires_approval(tool_name: str, *, allow_active: bool) -> bool:
    if allow_active:
        return False
    return tool_classification(tool_name) == "active"
