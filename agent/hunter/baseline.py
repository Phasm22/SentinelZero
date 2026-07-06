from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
STATE_DIR_ENV = "HUNTER_STATE_DIR"
DEFAULT_STATE_DIR = Path(__file__).resolve().parent.parent / "state"
BASELINE_FILENAME = "iot_fingerprints.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def state_dir() -> Path:
    raw = os.environ.get(STATE_DIR_ENV, str(DEFAULT_STATE_DIR))
    return Path(raw)


def baseline_path() -> Path:
    return state_dir() / BASELINE_FILENAME


def empty_baseline() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "fingerprints": {}}


def load_baseline(path: Path | None = None) -> dict[str, Any]:
    target = path or baseline_path()
    if not target.exists():
        return empty_baseline()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return empty_baseline()
    if not isinstance(payload, dict):
        return empty_baseline()
    fps = payload.get("fingerprints")
    if not isinstance(fps, dict):
        fps = {}
    return {
        "schema_version": int(payload.get("schema_version") or SCHEMA_VERSION),
        "fingerprints": fps,
    }


def save_baseline(payload: dict[str, Any], path: Path | None = None) -> Path:
    target = path or baseline_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    normalized = {
        "schema_version": int(payload.get("schema_version") or SCHEMA_VERSION),
        "fingerprints": payload.get("fingerprints") or {},
    }
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(normalized, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, target)
    return target


def get_fingerprint(payload: dict[str, Any], ip: str) -> dict[str, Any] | None:
    fps = payload.get("fingerprints")
    if not isinstance(fps, dict):
        return None
    entry = fps.get(ip)
    return entry if isinstance(entry, dict) else None


def extract_udp_ports(probe_result: dict[str, Any]) -> list[dict[str, Any]]:
    rows = probe_result.get("open_ports") or []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        proto = str(row.get("protocol") or "udp").lower()
        if proto != "udp":
            continue
        try:
            port = int(row.get("port"))
        except Exception:
            continue
        out.append({
            "port": port,
            "protocol": "udp",
            "state": str(row.get("state") or "open"),
            "service": str(row.get("service") or ""),
        })
    out.sort(key=lambda item: item["port"])
    return out


def upsert_fingerprint(
    payload: dict[str, Any],
    *,
    ip: str,
    probe_result: dict[str, Any],
    mission_id: str,
    device_hint: str | None = None,
    observed_at: str | None = None,
) -> dict[str, Any]:
    ts = observed_at or _utc_now_iso()
    fps = payload.setdefault("fingerprints", {})
    if not isinstance(fps, dict):
        fps = {}
        payload["fingerprints"] = fps
    existing = fps.get(ip)
    if not isinstance(existing, dict):
        existing = {
            "ip": ip,
            "first_seen": ts,
            "observation_count": 0,
        }

    entry = dict(existing)
    entry["ip"] = ip
    entry["last_seen"] = ts
    entry["last_mission"] = mission_id
    entry["observation_count"] = int(entry.get("observation_count") or 0) + 1
    if device_hint:
        entry["device_hint"] = device_hint
    entry["udp_ports"] = extract_udp_ports(probe_result)
    fps[ip] = entry
    payload["schema_version"] = SCHEMA_VERSION
    return entry
