from __future__ import annotations

from typing import Any

from agent import BASE_URL, _http

from .http_recon_parse import HTTP_RECON_SCRIPT_IDS, parse_recon_scripts
from .tls_recon_parse import TLS_RECON_SCRIPT_IDS, parse_tls_scripts


def hydrate_seed(ip: str, scan_id: int | None) -> dict[str, Any]:
    """Look up prior scan evidence for `ip` from scan `scan_id` so the pivot mission can
    skip re-discovering ports/versions/http-recon/tls-recon it already has evidence for.

    Always returns the same shape, even on lookup failure, so callers never branch on
    exceptions -- an empty result just means "nothing to hydrate, scan fresh".
    """
    empty: dict[str, Any] = {
        "open_ports": [], "http_recon": None, "tls_recon": None, "source_scan_id": scan_id,
    }
    if not scan_id:
        return empty

    try:
        resp = _http.get(f"{BASE_URL}/api/scan/{scan_id}", timeout=10)
        resp.raise_for_status()
        payload = resp.json()
    except Exception:
        return empty

    host = next(
        (h for h in (payload.get("hosts") or []) if str(h.get("ip") or "") == ip),
        None,
    )
    if host is None:
        return empty

    open_ports = host.get("ports") or []

    host_vulns = [v for v in (payload.get("vulns") or []) if str(v.get("host") or "") == ip]

    http_scripts = {
        v.get("id"): v.get("output", "")
        for v in host_vulns
        if v.get("id") in HTTP_RECON_SCRIPT_IDS
    }
    http_recon = parse_recon_scripts(http_scripts) if http_scripts else None

    tls_scripts = {
        v.get("id"): v.get("output", "")
        for v in host_vulns
        if v.get("id") in TLS_RECON_SCRIPT_IDS
    }
    tls_recon = parse_tls_scripts(tls_scripts) if tls_scripts else None

    return {
        "open_ports": open_ports,
        "http_recon": http_recon,
        "tls_recon": tls_recon,
        "source_scan_id": scan_id,
    }
