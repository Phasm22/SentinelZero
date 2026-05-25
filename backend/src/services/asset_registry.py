"""Load the shared asset registry used by the analysis agent and insight enrichment."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

_DEFAULT_PATH = Path(os.path.expanduser("~/agent/context/assets.json"))


def assets_path() -> Path:
    return Path(os.environ.get("SENTINEL_ASSETS_PATH", str(_DEFAULT_PATH)))


@lru_cache(maxsize=1)
def _load_registry() -> Dict[str, Any]:
    path = assets_path()
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def get_asset_context(ip: str) -> Dict[str, Any]:
    """Return registry entry for an IP, or a minimal unknown-host stub."""
    assets = _load_registry()
    entry = assets.get(ip)
    if entry:
        return dict(entry)
    for prefix, label in (
        ("172.16.0.", "lab network"),
        ("192.168.68.", "home network"),
        ("192.168.71.", "home network"),
    ):
        if ip.startswith(prefix):
            return {
                "name": ip,
                "role": "unknown",
                "trust_zone": "unknown",
                "expected_ports": [],
                "note": f"Unknown host in {label} — not in asset registry",
            }
    return {
        "name": ip,
        "role": "unknown",
        "trust_zone": "unknown",
        "expected_ports": [],
        "note": "Unknown host — not in asset registry",
    }


def is_expected_port(ip: str, port: int) -> Optional[bool]:
    """True if port is in expected_ports, False if known host but unexpected, None if unknown host."""
    ctx = get_asset_context(ip)
    expected = ctx.get("expected_ports") or []
    if not expected and ctx.get("trust_zone") == "unknown":
        return None
    return port in expected
