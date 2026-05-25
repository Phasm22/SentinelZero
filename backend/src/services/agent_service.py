"""
Agent service — calls the analysis agent subprocess and patches verdicts onto insights.
Runs in a daemon thread after scan completion; never blocks the scan pipeline.
"""
import json
import logging
import os
import subprocess
from datetime import datetime, timezone

from ..models.scan import Scan
from ..config.database import db

logger = logging.getLogger(__name__)

_AGENT_DIR    = os.environ.get("SENTINEL_AGENT_DIR", os.path.expanduser("~/agent"))
_AGENT_SCRIPT = os.path.join(_AGENT_DIR, "agent.py")
_AGENT_PYTHON = os.path.join(_AGENT_DIR, ".venv", "bin", "python")

ACTIONABLE_TYPES = {
    "new_port", "new_host", "missing_host", "service_change",
    "new_vuln_critical", "new_vuln_high", "new_vuln_medium", "new_vuln_low",
}
AUTO_DISMISS_TYPES = {"port_closed", "scan_performance"}


def _is_host_ip(value: str) -> bool:
    if not value or " " in value:
        return False
    parts = value.split(".")
    return len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)


def build_enrichment_digest(insights: list) -> dict:
    """
    Summarize backend pre-enrichment so the verdict agent can skip redundant tool calls.
    Mirrors details.asset_context / details.sensor_context already on each insight.
    """
    hosts: dict = {}
    for ins in insights:
        details = ins.get("details") or {}
        ip = details.get("ip") or ins.get("host", "")
        if not _is_host_ip(ip):
            continue
        entry = hosts.setdefault(ip, {"insight_types": [], "asset": None, "sensor": None})
        entry["insight_types"].append(ins.get("type"))
        if details.get("asset_context"):
            entry["asset"] = details["asset_context"]
        if details.get("sensor_context"):
            entry["sensor"] = details["sensor_context"]
        if details.get("unexpected_port"):
            entry["unexpected_port"] = True
        if details.get("port") is not None:
            entry["port"] = details["port"]

    return {
        "hosts": hosts,
        "notes": (
            "Backend attached asset_context and sensor_context during insight generation. "
            "Use this digest first; only call tools for missing fields."
        ),
    }


def run_verdicts_for_scan(scan_id: int, app, socketio) -> None:
    """
    Daemon thread entry point. Never raises — failures are logged and swallowed
    so the scan pipeline is never blocked.
    """
    with app.app_context():
        try:
            _run(scan_id, socketio)
        except Exception:
            logger.exception("agent_service: unhandled error for scan %s", scan_id)


def _run(scan_id: int, socketio) -> None:
    scan = db.session.get(Scan, scan_id)
    if not scan or not scan.insights_json:
        logger.info("agent_service: scan %s has no insights, skipping", scan_id)
        return

    try:
        insights = json.loads(scan.insights_json)
    except (json.JSONDecodeError, TypeError):
        logger.warning("agent_service: could not parse insights_json for scan %s", scan_id)
        return

    if not insights:
        return

    now = datetime.now(timezone.utc).isoformat()

    # Auto-dismiss noise types without calling the LLM
    for insight in insights:
        if insight.get("type") in AUTO_DISMISS_TYPES:
            insight["verdict"]          = "dismiss"
            insight["verdict_summary"]  = "Expected noise — port closed or scan performance metric"
            insight["verdict_evidence"] = "Auto-dismissed: type is port_closed or scan_performance"
            insight["verdict_at"]       = now

    actionable = [i for i in insights if i.get("type") in ACTIONABLE_TYPES]

    if not actionable:
        scan.insights_json = json.dumps(insights)
        db.session.commit()
        logger.info("agent_service: scan %s — only noise, no LLM call needed", scan_id)
        _emit(socketio, scan_id)
        return

    # Check prerequisites before subprocess call
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if not openai_key:
        logger.warning("agent_service: OPENAI_API_KEY not set — skipping verdicts for scan %s", scan_id)
        return

    if not os.path.exists(_AGENT_PYTHON):
        logger.warning(
            "agent_service: agent venv not found at %s — skipping verdicts for scan %s",
            _AGENT_PYTHON, scan_id,
        )
        return

    diff = {}
    if scan.diff_from_previous:
        try:
            diff = json.loads(scan.diff_from_previous)
        except (json.JSONDecodeError, TypeError):
            pass

    enrichment = build_enrichment_digest(actionable)
    payload = json.dumps({
        "scan_id": scan_id,
        "insights": actionable,
        "diff": diff,
        "enrichment": enrichment,
    })

    logger.info(
        "agent_service: calling agent for scan %s with %d actionable insights",
        scan_id, len(actionable),
    )

    try:
        result = subprocess.run(
            [_AGENT_PYTHON, _AGENT_SCRIPT, "--insights", payload],
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "OPENAI_API_KEY": openai_key},
        )
    except subprocess.TimeoutExpired:
        logger.error("agent_service: agent timed out for scan %s", scan_id)
        return
    except Exception as exc:
        logger.error("agent_service: failed to launch agent for scan %s: %s", scan_id, exc)
        return

    if result.returncode != 0:
        logger.error(
            "agent_service: agent exited %d for scan %s:\n%s",
            result.returncode, scan_id, result.stderr[:500],
        )
        return

    try:
        output   = json.loads(result.stdout)
        verdicts = output.get("verdicts", [])
    except (json.JSONDecodeError, TypeError) as exc:
        logger.error(
            "agent_service: could not parse agent stdout for scan %s: %s\n%.500s",
            scan_id, exc, result.stdout,
        )
        return

    verdict_map = {str(v["insight_id"]): v for v in verdicts if "insight_id" in v}

    now     = datetime.now(timezone.utc).isoformat()
    patched = 0
    for insight in insights:
        iid = str(insight.get("id", ""))
        v   = verdict_map.get(iid)
        if v:
            insight["verdict"]          = v.get("verdict", "escalate")
            insight["verdict_summary"]  = v.get("verdict_summary", "")
            insight["verdict_evidence"] = v.get("verdict_evidence", "")
            insight["verdict_at"]       = now
            patched += 1

    scan.insights_json = json.dumps(insights)
    db.session.commit()
    logger.info("agent_service: patched %d/%d verdicts for scan %s", patched, len(actionable), scan_id)

    _emit(socketio, scan_id)


def _emit(socketio, scan_id: int) -> None:
    try:
        socketio.emit("insights.verdicts_ready", {"scan_id": scan_id})
    except Exception as exc:
        logger.warning("agent_service: socket emit failed: %s", exc)
