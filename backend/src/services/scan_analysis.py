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


def record_host_context(
    scan_id: int,
    *,
    host_count: int = 0,
    error: Optional[str] = None,
) -> None:
    entry: Dict[str, Any] = {
        "at": _now(),
        "host_count": host_count,
        "error": error,
    }
    merge_analysis(scan_id, {"host_context_enrichment": entry})


def record_insights_generation(
    scan_id: int,
    *,
    count: int,
    previous_scan_id: Optional[int] = None,
    target_network: Optional[str] = None,
    error: Optional[str] = None,
    skipped_reason: Optional[str] = None,
) -> None:
    entry: Dict[str, Any] = {
        "at": _now(),
        "count": count,
        "previous_scan_id": previous_scan_id,
        "error": error,
        "skipped_reason": skipped_reason,
    }
    if target_network:
        entry["target_network"] = target_network
    merge_analysis(scan_id, {"insights_generation": entry})


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


def record_synthesis_agent(
    scan_id: int,
    *,
    status: str,
    stories_added: int = 0,
    skipped_reason: Optional[str] = None,
    stdout: Optional[str] = None,
    stderr: Optional[str] = None,
    raw_response: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> None:
    entry: Dict[str, Any] = {
        "at": _now(),
        "status": status,
        "stories_added": stories_added,
        "skipped_reason": skipped_reason,
        "error": error,
        "duration_ms": duration_ms,
    }
    if stdout:
        entry["stdout_preview"] = stdout[:4000]
    if stderr:
        entry["stderr_preview"] = stderr[:2000]
    if raw_response is not None:
        entry["raw_response"] = raw_response
    merge_analysis(scan_id, {"synthesis_agent": entry})


def record_scan_analyst(
    scan_id: int,
    *,
    status: str,
    source: str = "timer",
    verdict: Optional[str] = None,
    summary: Optional[str] = None,
    findings: Optional[List[Dict[str, Any]]] = None,
    reasoning: Optional[str] = None,
    skipped_reason: Optional[str] = None,
    stderr: Optional[str] = None,
    error: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> None:
    entry: Dict[str, Any] = {
        "at": _now(),
        "status": status,
        "source": source,
        "verdict": verdict,
        "summary": summary,
        "skipped_reason": skipped_reason,
        "error": error,
        "duration_ms": duration_ms,
    }
    if findings is not None:
        entry["findings"] = findings
    if reasoning:
        entry["reasoning"] = reasoning[:12000]
    if stderr:
        entry["stderr_preview"] = stderr[:2000]
    merge_analysis(scan_id, {"scan_analyst": entry})


def public_summary(scan: Scan) -> Dict[str, Any]:
    """Lightweight fields for scan history lists."""
    analysis = load_analysis(scan)
    counts = insight_counts(scan)
    ig = analysis.get("insights_generation") or {}
    va = analysis.get("verdict_agent") or {}
    sa = analysis.get("scan_analyst") or {}
    return {
        "insights_count": counts["total"],
        "insights_escalated": counts["escalate"],
        "insights_explain": counts["explain"],
        "insights_dismissed": counts["dismiss"],
        "insights_pending": counts["pending"],
        "insights_generation": ig,
        "verdict_agent_status": va.get("status", "not_run"),
        "verdict_agent_summary": _agent_one_liner(va, ig, counts, sa),
        "scan_analyst_status": sa.get("status", "not_run"),
        "scan_analyst_summary": sa.get("summary"),
    }


AUTO_HANDLED_TYPES = frozenset({
    "port_closed", "scan_performance", "baseline_inventory", "vuln_resolved",
    "registry_gap", "sensor_gap",
})

ACTIONABLE_INSIGHT_TYPES = frozenset({
    "new_port", "new_host", "missing_host", "service_change",
    "new_vuln_critical", "new_vuln_high", "new_vuln_medium", "new_vuln_low",
    "registry_gap", "sensor_gap", "correlated",
})


def verdict_status_for_insight(insight: dict, scan: Scan) -> dict:
    """
    Explain why an insight has no verdict yet (or never will).
    Returned fields: verdict_agent_status, verdict_status_note
    """
    if insight.get("verdict"):
        return {
            "verdict_agent_status": "complete",
            "verdict_status_note": None,
        }

    analysis = load_analysis(scan)
    va = analysis.get("verdict_agent") or {}
    itype = insight.get("type", "")
    status = va.get("status", "not_run")

    if insight.get("synthesized"):
        syn = analysis.get("synthesis_agent") or {}
        return {
            "verdict_agent_status": "complete",
            "verdict_status_note": (
                f"Synthesis story ({syn.get('status', 'unknown')})"
                if syn else "Correlated story from synthesis pass"
            ),
        }

    if itype in AUTO_HANDLED_TYPES or itype not in ACTIONABLE_INSIGHT_TYPES:
        label = {
            "baseline_inventory": "First-scan inventory",
            "vuln_resolved": "Resolved vulnerability",
            "registry_gap": "Asset registry backlog",
            "sensor_gap": "Sensor coverage backlog",
            "port_closed": "Port closed",
            "scan_performance": "Scan performance metric",
        }.get(itype, "Auto-handled insight")
        return {
            "verdict_agent_status": "auto",
            "verdict_status_note": label,
        }

    if status == "not_run":
        return {
            "verdict_agent_status": "pending",
            "verdict_status_note": "Waiting for verdict agent after scan…",
        }
    if status == "skipped":
        reason = va.get("skipped_reason") or "Agent skipped"
        return {"verdict_agent_status": "skipped", "verdict_status_note": reason}
    if status == "timeout":
        return {
            "verdict_agent_status": "timeout",
            "verdict_status_note": va.get("error") or "Verdict agent timed out",
        }
    if status == "failed":
        return {
            "verdict_agent_status": "failed",
            "verdict_status_note": va.get("error") or "Verdict agent failed — see scan AI tab",
        }
    if status == "success":
        return {
            "verdict_agent_status": "success",
            "verdict_status_note": "Agent finished but no verdict for this insight — check scan AI tab",
        }

    return {
        "verdict_agent_status": status,
        "verdict_status_note": "No verdict assigned",
    }


def attach_verdict_status(insight: dict, scan: Scan) -> dict:
    extra = verdict_status_for_insight(insight, scan)
    insight.update(extra)
    return insight


def _agent_one_liner(va: dict, ig: dict, counts: dict, sa: dict | None = None) -> str:
    sa = sa or {}
    if sa.get("status") == "success" and sa.get("summary"):
        base = sa["summary"][:120]
        if va.get("status") == "success":
            return (
                f"{base} — verdicts {va.get('patched_count', 0)}/"
                f"{va.get('actionable_count', 0)}"
            )
        return base
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
