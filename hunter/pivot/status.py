from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def status_path(reports_dir: Path, mission_id: str) -> Path:
    return reports_dir / f"hunt-{mission_id}.status.json"


def write_status(
    reports_dir: Path,
    mission_id: str,
    *,
    state: str,
    pid: int | None = None,
    started_at: str | None = None,
    last_task: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = status_path(reports_dir, mission_id)
    existing: dict[str, Any] = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}

    payload: dict[str, Any] = {
        "mission_id": mission_id,
        "state": state,
        "started_at": started_at or existing.get("started_at") or _utc_now_iso(),
        "updated_at": _utc_now_iso(),
        "pid": pid if pid is not None else existing.get("pid") or os.getpid(),
        "last_task": last_task,
        "error": error,
    }
    tmp = path.with_suffix(".status.json.tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return payload


def read_status(reports_dir: Path, mission_id: str) -> dict[str, Any] | None:
    path = status_path(reports_dir, mission_id)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None
