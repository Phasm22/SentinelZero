from __future__ import annotations

PASSIVE_TOOLS = frozenset({"nmap_scan", "port_scan_light", "http_recon", "triage", "complete"})
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
