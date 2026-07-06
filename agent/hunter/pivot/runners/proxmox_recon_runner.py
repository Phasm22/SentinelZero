from __future__ import annotations

import re
import ssl
import urllib.error
import urllib.request
from typing import Any

from ..proxmox_recon_parse import parse_proxmox_response


# Canned single-GET response for a Proxmox VE node -- exercises the deterministic
# ``escalate`` path (confirmed hypervisor) without a live probe.
FIXTURE_PROXMOX_RESPONSE = {
    "status": 200,
    "server_header": "pve-api-daemon/3.0",
    "title": "porttest - Proxmox Virtual Environment",
}


def _extract_title(body: str) -> str | None:
    match = re.search(r"<title>([^<]*)</title>", body, re.IGNORECASE)
    return match.group(1).strip() if match else None


def run_proxmox_recon(ip: str, port: int = 8006, *, fixture: bool = False, timeout: int = 15) -> dict[str, Any]:
    if fixture:
        fields = parse_proxmox_response(
            status=FIXTURE_PROXMOX_RESPONSE["status"],
            server_header=FIXTURE_PROXMOX_RESPONSE["server_header"],
            title=FIXTURE_PROXMOX_RESPONSE["title"],
        )
        return {"ip": ip, "port": port, **fields}

    # Single unauthenticated HTTPS GET -- Proxmox serves a self-signed cert, so
    # verification is disabled (identification, not a trust decision). This is a
    # content GET, never an API call with credentials.
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    url = f"https://{ip}:{port}/"
    status: int | None = None
    server_header: str | None = None
    title: str | None = None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "sentinel-pivot"})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            status = resp.status
            server_header = resp.headers.get("Server")
            body = resp.read(65536).decode("utf-8", "replace")
            title = _extract_title(body)
    except urllib.error.HTTPError as exc:
        # An auth-gated 401 still identifies the daemon via its Server header.
        status = exc.code
        server_header = exc.headers.get("Server") if exc.headers else None
        try:
            title = _extract_title(exc.read(65536).decode("utf-8", "replace"))
        except Exception:
            title = None
    except Exception as exc:
        return {"ip": ip, "port": port, "error": str(exc), "responded": False,
                "is_proxmox": False, "node_name": None}

    fields = parse_proxmox_response(status=status, server_header=server_header, title=title)
    return {"ip": ip, "port": port, **fields}
