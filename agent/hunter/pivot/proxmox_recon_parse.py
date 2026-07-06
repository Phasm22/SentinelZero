from __future__ import annotations

import re
from typing import Any

# Port the pivot engine treats as a Proxmox VE web/API surface.
PROXMOX_PORTS: tuple[int, ...] = (8006,)

# Markers that definitively identify a Proxmox Virtual Environment management
# plane -- the pve-api-daemon Server header and the product string in the title.
_SERVER_MARKER = "pve-api-daemon"
_TITLE_MARKER = "proxmox virtual environment"


def recommend_proxmox_action(*, is_proxmox: bool, responded: bool) -> str:
    """Decision-grade triage for a proxmox_recon finding.

    Returns one of ``escalate`` | ``next_scan`` | ``observe`` (never a blue-team
    verdict). Shared by the live proxmox_recon dispatch and any hydrated finding
    so both paths grade identically.

    - ``escalate``: the host is a confirmed Proxmox VE management plane -- a
      hypervisor control surface reachable on the network is a high-value target
      (VM lifecycle control, console, storage).
    - ``next_scan``: 8006 answered but did not identify as Proxmox.
    - ``observe``: the port did not respond.
    """
    if not responded:
        return "observe"
    if is_proxmox:
        return "escalate"
    return "next_scan"


def parse_proxmox_response(
    *, status: int | None, server_header: str | None, title: str | None
) -> dict[str, Any]:
    """Turn a single HTTPS GET response (status + Server header + <title>) into
    structured proxmox_recon fields. Shared by the live runner and its fixture."""
    responded = status is not None
    server_l = (server_header or "").lower()
    title_l = (title or "").lower()

    is_proxmox = _SERVER_MARKER in server_l or _TITLE_MARKER in title_l

    # Proxmox titles look like "<node> - Proxmox Virtual Environment".
    node_name = None
    if title and _TITLE_MARKER in title_l:
        match = re.match(r"\s*(.+?)\s*-\s*Proxmox Virtual Environment", title, re.IGNORECASE)
        if match:
            node_name = match.group(1).strip() or None

    api_daemon = None
    match = re.search(r"(pve-api-daemon/[\w.]+)", server_header or "", re.IGNORECASE)
    if match:
        api_daemon = match.group(1)

    return {
        "responded": responded,
        "status": status,
        "server_header": server_header,
        "title": title,
        "is_proxmox": is_proxmox,
        "node_name": node_name,
        "api_daemon": api_daemon,
    }
