from __future__ import annotations

import re
from typing import Any

# NSE script ids the pivot engine treats as "web content identification" --
# single-request fingerprinting, never path enumeration.
HTTP_RECON_SCRIPT_IDS = frozenset({
    "http-title",
    "http-headers",
    "http-server-header",
    "http-generator",
})

_SECURITY_HEADERS = ("Strict-Transport-Security", "Content-Security-Policy")

# Ports the pivot engine treats as HTTP(S) management/content surfaces, in the
# priority order http_recon should target when several are open on one host.
HTTP_PORTS: tuple[int, ...] = (443, 8443, 8006, 8581, 80, 8080, 3128)

# Substrings in an http-title that signal an administrative / auth surface --
# a materially higher-value exposure than a static content page.
_ADMIN_TITLE_MARKERS = (
    "login", "sign in", "log in", "admin", "dashboard", "console",
    "proxmox", "pi-hole", "pihole", "opnsense", "pfsense", "portainer",
    "homebridge", "router", "gateway", "management", "control panel",
    "unauthorized", "authentication required",
)


def recommend_http_action(
    *,
    port: int,
    title: str | None,
    server_header: str | None,
    generator: str | None,
    missing_security_headers: list[str] | None,
) -> str:
    """Decision-grade triage for an http_recon finding.

    Returns one of ``escalate`` | ``next_scan`` | ``observe`` (never a blue-team
    verdict). Shared by the live http_recon dispatch and the hydrated-evidence
    finding so both paths grade identically.

    - ``escalate``: an admin/auth surface is exposed (title markers or the
      Proxmox web UI on 8006 / Homebridge on 8581), or a TLS surface (443/8443)
      is missing both HSTS and CSP.
    - ``next_scan``: the port answered HTTP but no content identifies it --
      worth a deeper look before deciding.
    - ``observe``: identified, benign static content.
    """
    title_l = (title or "").lower()
    is_admin_title = any(marker in title_l for marker in _ADMIN_TITLE_MARKERS)
    is_admin_port = port in (8006, 8581)

    tls_port = port in (443, 8443)
    missing = {h.lower() for h in (missing_security_headers or [])}
    tls_no_hardening = tls_port and {
        "strict-transport-security", "content-security-policy",
    } <= missing

    if is_admin_title or is_admin_port or tls_no_hardening:
        return "escalate"

    if not (title or server_header or generator):
        return "next_scan"

    return "observe"


def parse_recon_scripts(scripts: dict[str, str]) -> dict[str, Any]:
    """Turn a {script_id: raw nmap script output} map into structured http_recon fields.

    Shared by hydration.py (reading prior scan's vulns_json) and http_recon_runner.py
    (reading a fresh nmap NSE run) so both sources produce identical finding shapes.
    """
    title = None
    title_output = (scripts.get("http-title") or "").strip()
    if title_output:
        title = title_output.splitlines()[0].strip() or None

    server_header = None
    server_output = (scripts.get("http-server-header") or "").strip()
    headers_text = scripts.get("http-headers") or ""
    if server_output:
        server_header = server_output.splitlines()[0].strip() or None
    elif headers_text:
        match = re.search(r"^Server:\s*(.+)$", headers_text, re.MULTILINE | re.IGNORECASE)
        if match:
            server_header = match.group(1).strip() or None

    generator = None
    generator_output = (scripts.get("http-generator") or "").strip()
    if generator_output:
        generator = generator_output.splitlines()[0].strip() or None

    missing_security_headers = [
        header for header in _SECURITY_HEADERS
        if header.lower() not in headers_text.lower()
    ] if headers_text else []

    return {
        "title": title,
        "server_header": server_header,
        "generator": generator,
        "missing_security_headers": missing_security_headers,
    }
