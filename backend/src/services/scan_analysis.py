"""Persist and read per-scan AI / insights pipeline metadata."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..config.database import db
from ..models.scan import Scan


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_analysis(scan: Scan) -> Dict[str, Any]:
    if not scan or not scan.analysis_json:
        return {}
    try:
        data = json.loads(scan.analysis_json)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def save_analysis(scan_id: int, data: Dict[str, Any]) -> None:
    scan = db.session.get(Scan, scan_id)
    if not scan:
        return
    scan.analysis_json = json.dumps(data)
    db.session.commit()


def merge_analysis(scan_id: int, patch: Dict[str, Any]) -> Dict[str, Any]:
    scan = db.session.get(Scan, scan_id)
    if not scan:
        return {}
    data = load_analysis(scan)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(data.get(key), dict):
            merged = {**data[key], **value}
            data[key] = merged
        else:
            data[key] = value
    scan.analysis_json = json.dumps(data)
    db.session.commit()
    return data


def insight_counts(scan: Scan) -> Dict[str, int]:
    if not scan.insights_json:
        return {
            "total": 0,
            "escalate": 0,
            "explain": 0,
            "dismiss": 0,
            "pending": 0,
        }
    try:
        items = json.loads(scan.insights_json)
    except (json.JSONDecodeError, TypeError):
        return {"total": 0, "escalate": 0, "explain": 0, "dismiss": 0, "pending": 0}

    counts = {"total": len(items), "escalate": 0, "explain": 0, "dismiss": 0, "pending": 0}
    for item in items:
        v = item.get("verdict")
        if v in counts:
            counts[v] += 1
        else:
            counts["pending"] += 1
    return counts


def record_insights_generation(
    scan_id: int,
    *,
    count: int,
    previous_scan_id: Optional[int] = None,
    error: Optional[str] = None,
    skipped_reason: Optional[str] = None,
) -> None:
    merge_analysis(scan_id, {
        "insights_generation": {
            "at": _now(),
            "count": count,
            "previous_scan_id": previous_scan_id,
            "error": error,
            "skipped_reason": skipped_reason,
        }
    })


def record_verdict_agent(
    scan_id: int,
    *,
    status: str,
    actionable_count: int = 0,
    patched_count: int = 0,
    skipped_reason: Optional[str] = None,
    tools_omitted: Optional[List[str]] = None,
    stdout: Optional[str] = None,
    stderr: Optional[str] = None,
    raw_response: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> None:
    entry: Dict[str, Any] = {
        "at": _now(),
        "status": status,
        "actionable_count": actionable_count,
        "patched_count": patched_count,
        "skipped_reason": skipped_reason,
        "tools_omitted": tools_omitted or [],
        "error": error,
        "duration_ms": duration_ms,
    }
    if stdout:
        entry["stdout_preview"] = stdout[:4000]
    if stderr:
        entry["stderr_preview"] = stderr[:2000]
    if raw_response is not None:
        entry["raw_response"] = raw_response
    merge_analysis(scan_id, {"verdict_agent": entry})


def public_summary(scan: Scan) -> Dict[str, Any]:
    """Lightweight fields for scan history lists."""
    analysis = load_analysis(scan)
    counts = insight_counts(scan)
    ig = analysis.get("insights_generation") or {}
    va = analysis.get("verdict_agent") or {}
    return {
        "insights_count": counts["total"],
        "insights_escalated": counts["escalate"],
        "insights_explain": counts["explain"],
        "insights_dismissed": counts["dismiss"],
        "insights_pending": counts["pending"],
        "insights_generation": ig,
        "verdict_agent_status": va.get("status", "not_run"),
        "verdict_agent_summary": _agent_one_liner(va, ig, counts),
    }


def _agent_one_liner(va: dict, ig: dict, counts: dict) -> str:
    if va.get("status") == "success":
        return f"Verdicts: {va.get('patched_count', 0)}/{va.get('actionable_count', 0)} patched"
    if va.get("status") == "skipped":
        return va.get("skipped_reason") or "Agent skipped"
    if va.get("status") == "failed":
        return va.get("error") or "Agent failed"
    if va.get("status") == "timeout":
        return "Agent timed out"
    if ig.get("skipped_reason"):
        return ig["skipped_reason"]
    if ig.get("error"):
        return f"Insights error: {ig['error']}"
    if counts["total"] == 0 and ig.get("count", 0) == 0:
        return "No insights generated"
    if counts["pending"] and not va:
        return "Verdict agent pending"
    return "Verdict agent not run"
