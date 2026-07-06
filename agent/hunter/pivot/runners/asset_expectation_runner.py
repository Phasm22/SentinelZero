from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# `agent.ASSETS` is the canonical path to context/assets.json (agent.py). Import
# lazily inside the runner so unit tests can pass an explicit assets_path without
# needing the full agent module on sys.path.


FIXTURE_ASSET_OUTPUT: dict[str, Any] = {
    "ip": "",
    "registered": True,
    "name": "fixture-host",
    "role": "linux-server",
    "trust_zone": "lab",
    "expected_ports": [22, 80],
    "open_tcp_ports": [22, 80, 6379],
    "unexpected_ports": [6379],
    "missing_ports": [],
    "notes": "fixture asset expectation check",
}


def _load_assets(assets_path: str | Path | None) -> dict[str, Any]:
    if assets_path is None:
        from agent import ASSETS  # noqa: PLC0415 -- lazy to keep tests decoupled

        assets_path = ASSETS
    try:
        data = json.loads(Path(assets_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _tcp_ports(open_ports: list[dict[str, Any]]) -> list[int]:
    ports: set[int] = set()
    for entry in open_ports or []:
        if str(entry.get("protocol", "tcp")) != "tcp":
            continue
        try:
            ports.add(int(entry.get("port", 0)))
        except (TypeError, ValueError):
            continue
    ports.discard(0)
    return sorted(ports)


def run_asset_expectation_check(
    ip: str,
    open_ports: list[dict[str, Any]] | None = None,
    *,
    assets_path: str | Path | None = None,
    fixture: bool = False,
) -> dict[str, Any]:
    """Compare a host's open ports against its registered expectation in
    context/assets.json.

    Never touches the network -- it reads the already-discovered ``open_ports``
    (from the seed scan or a prior nmap_scan) against the asset inventory. Adds a
    field nmap alone cannot: whether each open port is *expected* for this host.
    """
    if fixture:
        payload = dict(FIXTURE_ASSET_OUTPUT)
        payload["ip"] = ip
        return payload

    open_ports = open_ports or []
    assets = _load_assets(assets_path)
    asset = assets.get(ip) if isinstance(assets.get(ip), dict) else None

    open_tcp = _tcp_ports(open_ports)

    if asset is None:
        return {
            "ip": ip,
            "registered": False,
            "name": None,
            "role": None,
            "trust_zone": None,
            "expected_ports": [],
            "open_tcp_ports": open_tcp,
            "unexpected_ports": open_tcp,
            "missing_ports": [],
            "notes": None,
        }

    expected = sorted({int(p) for p in (asset.get("expected_ports") or [])})
    expected_set = set(expected)
    unexpected = [p for p in open_tcp if p not in expected_set]
    missing = [p for p in expected if p not in set(open_tcp)]

    return {
        "ip": ip,
        "registered": True,
        "name": asset.get("name"),
        "role": asset.get("role"),
        "trust_zone": asset.get("trust_zone"),
        "expected_ports": expected,
        "open_tcp_ports": open_tcp,
        "unexpected_ports": unexpected,
        "missing_ports": missing,
        "notes": asset.get("notes"),
    }


# Trust zones where an unexpected port is high-signal enough to escalate outright.
_HIGH_TRUST_ZONES = frozenset({"management", "infrastructure"})


def recommend_asset_action(result: dict[str, Any]) -> str:
    """Grade an asset-expectation result into escalate | next_scan | observe.

    - ``escalate``: host is unregistered, or an unexpected port appears on a
      management/infrastructure host (a new service where none is sanctioned).
    - ``next_scan``: an unexpected port on a lab/user/home host -- worth
      corroborating before deciding.
    - ``observe``: open ports are a subset of what the host is expected to run.
    """
    unexpected = result.get("unexpected_ports") or []
    if not result.get("registered", False):
        return "escalate"
    if not unexpected:
        return "observe"
    if str(result.get("trust_zone") or "") in _HIGH_TRUST_ZONES:
        return "escalate"
    return "next_scan"
