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
