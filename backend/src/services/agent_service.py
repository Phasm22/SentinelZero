"""
Agent service — verdict batch, synthesis stories, and scan-level analyst narrative.
Runs in a daemon thread after scan completion; never blocks the scan pipeline.
"""
import json
import logging
import os
import subprocess
import time
import uuid
from datetime import datetime, timezone

from ..models.scan import Scan
from ..config.database import db
from . import scan_analysis
from . import config_service
from .diff import compute_scan_diff
from .asset_registry import is_home_network
from .scan_scope import network_short_label

logger = logging.getLogger(__name__)

_AGENT_DIR    = os.environ.get("SENTINEL_AGENT_DIR", os.path.expanduser("~/agent"))
_AGENT_SCRIPT = os.path.join(_AGENT_DIR, "agent.py")
_AGENT_PYTHON = os.path.join(_AGENT_DIR, ".venv", "bin", "python")

ACTIONABLE_TYPES = {
    "new_port", "new_host", "missing_host", "service_change",
    "new_vuln_critical", "new_vuln_high", "new_vuln_medium", "new_vuln_low",
    "registry_gap", "sensor_gap",
}
AUTO_DISMISS_TYPES = {"port_closed", "scan_performance", "baseline_inventory"}
AUTO_EXPLAIN_TYPES = {"vuln_resolved"}
AUTO_ESCALATE_TYPES = {"registry_gap", "sensor_gap"}  # lab only; home gaps auto-explained
SYNTHESIS_SKIP_BASELINE_ONLY = True


def run_ai_pipeline(scan_id: int, app, socketio) -> None:
    """Verdicts → synthesis → scan analyst (daemon thread entry)."""
    with app.app_context():
        try:
            _run_verdicts(scan_id, socketio)
            _run_synthesis(scan_id, socketio)
            _run_scan_analyst(scan_id)
        except Exception as exc:
            logger.exception("agent_service: pipeline error for scan %s", scan_id)


def run_verdicts_for_scan(scan_id: int, app, socketio) -> None:
    """Backward-compatible entry: full pipeline."""
    run_ai_pipeline(scan_id, app, socketio)


def _is_baseline_insight(insight: dict) -> bool:
    if insight.get("type") == "baseline_inventory":
        return True
    details = insight.get("details") or {}
    if details.get("is_baseline") and insight.get("type") in (
        "new_host", "new_vuln_critical", "new_vuln_high",
    ):
        return True
    if details.get("host_count") is not None:
        return True
    if details.get("vuln_count") is not None and "baseline" in (insight.get("message") or "").lower():
        return True
    msg = (insight.get("message") or "").lower()
    if "baseline established" in msg or msg.startswith("security baseline:"):
        return True
    host = insight.get("host") or ""
    return host.endswith(" hosts") and not _is_host_ip(host)


def _insight_network_label(insight: dict) -> str:
    details = insight.get("details") or {}
    label = details.get("network_label")
    if label:
        return label
    net = details.get("target_network")
    return network_short_label(net) if net else ""


def _is_home_scoped_insight(insight: dict) -> bool:
    return _insight_network_label(insight) == "Home" or is_home_network(
        (insight.get("details") or {}).get("target_network"),
    )


def _is_host_ip(value: str) -> bool:
    if not value or " " in value:
        return False
    parts = value.split(".")
    return len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)


def build_enrichment_digest(
    insights: list,
    diff: dict | None = None,
    scan: Scan | None = None,
) -> dict:
    """Summarize pre-enrichment for verdict/synthesis agent payloads."""
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

    digest: dict = {
        "hosts": hosts,
        "notes": (
            "Backend attached asset_context and sensor_context during insight generation. "
            "Use this digest first; only call tools for missing fields."
        ),
    }
    if diff:
        digest["diff_summary"] = diff.get("summary")
        digest["escalate_count"] = sum(
            1 for i in insights if i.get("verdict") == "escalate"
        )
        digest["explain_count"] = sum(
            1 for i in insights if i.get("verdict") == "explain"
        )
    if scan:
        try:
            from .host_context import digest_for_agent

            digest["host_context"] = digest_for_agent(scan)
        except Exception as exc:
            logger.warning("host_context digest failed: %s", exc)
    try:
        from .host_context import institutional_memory_for_hosts

        memory = institutional_memory_for_hosts(hosts.keys())
        if memory:
            digest["institutional_memory"] = memory
    except Exception as exc:
        logger.warning("institutional_memory digest failed: %s", exc)
    return digest


def _load_diff(scan: Scan) -> dict:
    if scan.diff_from_previous:
        try:
            return json.loads(scan.diff_from_previous)
        except (json.JSONDecodeError, TypeError):
            pass
    try:
        return compute_scan_diff(scan.id, require_complete=False)
    except Exception:
        return {}


def _apply_auto_verdicts(insights: list, now: str) -> None:
    for insight in insights:
        itype = insight.get("type")
        if itype in AUTO_DISMISS_TYPES:
            insight["verdict"] = "dismiss"
            insight["verdict_summary"] = "Inventory or noise — no triage required"
            insight["verdict_evidence"] = f"Auto-dismissed: type is {itype}"
            insight["verdict_at"] = now
        elif itype in AUTO_EXPLAIN_TYPES:
            insight["verdict"] = "explain"
            insight["verdict_summary"] = "Positive change — vulnerability no longer reported"
            insight["verdict_evidence"] = "Auto-explained: resolved since previous scan of this type"
            insight["verdict_at"] = now
        elif itype in AUTO_ESCALATE_TYPES:
            if _is_home_scoped_insight(insight):
                insight["verdict"] = "explain"
                if itype == "registry_gap":
                    insight["verdict_summary"] = (
                        "Home scan — lab registry not applicable"
                    )
                    insight["verdict_evidence"] = (
                        "Home consumer/IoT hosts are compared to prior Home baselines, "
                        "not the lab asset registry. Document known devices in assets.json "
                        "when you want named triage."
                    )
                else:
                    ips = (insight.get("details") or {}).get("ips", [])
                    insight["verdict_summary"] = (
                        "Home sensor backlog — only registered infra hosts"
                    )
                    insight["verdict_evidence"] = (
                        f"Endpoint sensors are not expected on every home IoT device. "
                        f"Registered hosts needing sensors: {', '.join(ips[:8])}"
                        + ("…" if len(ips) > 8 else "")
                        if ips
                        else "No registered home infrastructure hosts lack sensors."
                    )
                insight["verdict_at"] = now
            else:
                insight["verdict"] = "escalate"
                if itype == "registry_gap":
                    ips = (insight.get("details") or {}).get("ips", [])
                    insight["verdict_summary"] = (
                        "Add lab hosts to asset registry for accurate triage"
                    )
                    insight["verdict_evidence"] = (
                        f"{len(ips)} lab IP(s) lack registry entries: "
                        + ", ".join(ips[:12])
                        + ("…" if len(ips) > 12 else "")
                    )
                else:
                    ips = (insight.get("details") or {}).get("ips", [])
                    insight["verdict_summary"] = (
                        "Deploy endpoint sensors to correlate ports with processes"
                    )
                    insight["verdict_evidence"] = (
                        f"{len(ips)} IP(s) without endpoint sensor: "
                        + ", ".join(ips[:12])
                        + ("…" if len(ips) > 12 else "")
                    )
                insight["verdict_at"] = now
        elif _is_baseline_insight(insight):
            insight["verdict"] = "explain"
            insight["verdict_summary"] = "First scan inventory — not a per-host threat"
            insight["verdict_evidence"] = "Baseline rollup; per-host diffs apply on subsequent scans"
            insight["verdict_at"] = now


def _agent_env() -> dict:
    env = {**os.environ, "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", "")}
    local = config_service.get_local_mode()
    if local["enabled"]:
        env["OLLAMA_BASE_URL"] = local["base_url"]
        env["OLLAMA_MODEL"] = local["model"]
    else:
        # Ensure a stale local-mode env from the parent process never leaks in.
        env.pop("OLLAMA_BASE_URL", None)
        env.pop("OLLAMA_MODEL", None)
    return env


def _can_call_agent() -> tuple[bool, str | None]:
    if config_service.get_local_mode()["enabled"]:
        # Local mode talks to Ollama; no OpenAI key required.
        if not os.path.exists(_AGENT_PYTHON):
            return False, f"Agent venv not found: {_AGENT_PYTHON}"
        return True, None
    if not os.environ.get("OPENAI_API_KEY"):
        return False, "OPENAI_API_KEY not set"
    if not os.path.exists(_AGENT_PYTHON):
        return False, f"Agent venv not found: {_AGENT_PYTHON}"
    return True, None


def _run_subprocess(args: list, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=_agent_env(),
    )


def _run_verdicts(scan_id: int, socketio) -> None:
    scan = db.session.get(Scan, scan_id)
    if not scan or not scan.insights_json:
        scan_analysis.record_verdict_agent(
            scan_id, status="skipped", skipped_reason="No insights_json on scan",
        )
        return

    try:
        insights = json.loads(scan.insights_json)
    except (json.JSONDecodeError, TypeError):
        scan_analysis.record_verdict_agent(
            scan_id, status="skipped", skipped_reason="Could not parse insights_json",
        )
        return

    if not insights:
        scan_analysis.record_verdict_agent(
            scan_id, status="skipped", skipped_reason="Insights list empty",
        )
        return

    now = datetime.now(timezone.utc).isoformat()
    _apply_auto_verdicts(insights, now)

    actionable = [
        i for i in insights
        if i.get("type") in ACTIONABLE_TYPES
        and not _is_baseline_insight(i)
        and i.get("type") not in AUTO_ESCALATE_TYPES
        and not i.get("verdict")
    ]

    if not actionable:
        scan.insights_json = json.dumps(insights)
        db.session.commit()
        scan_analysis.record_verdict_agent(
            scan_id,
            status="skipped",
            skipped_reason="No LLM-actionable insights after auto-verdicts",
            actionable_count=0,
            patched_count=0,
        )
        _emit(socketio, scan_id, "insights.verdicts_ready")
        return

    ok, reason = _can_call_agent()
    if not ok:
        scan.insights_json = json.dumps(insights)
        db.session.commit()
        scan_analysis.record_verdict_agent(
            scan_id, status="skipped", skipped_reason=reason,
            actionable_count=len(actionable),
        )
        _emit(socketio, scan_id, "insights.verdicts_ready")
        return

    diff = _load_diff(scan)
    payload = json.dumps({
        "scan_id": scan_id,
        "insights": actionable,
        "diff": diff,
        "enrichment": build_enrichment_digest(insights, diff, scan),
    })

    started = time.perf_counter()
    try:
        result = _run_subprocess([_AGENT_PYTHON, _AGENT_SCRIPT, "--insights", payload])
    except subprocess.TimeoutExpired:
        scan_analysis.record_verdict_agent(
            scan_id, status="timeout", actionable_count=len(actionable),
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
        return
    except Exception as exc:
        scan_analysis.record_verdict_agent(
            scan_id, status="failed", actionable_count=len(actionable), error=str(exc),
        )
        return

    duration_ms = int((time.perf_counter() - started) * 1000)
    if result.returncode != 0:
        scan_analysis.record_verdict_agent(
            scan_id, status="failed", actionable_count=len(actionable),
            stderr=result.stderr, stdout=result.stdout,
            error=f"exit code {result.returncode}", duration_ms=duration_ms,
        )
        return

    try:
        output = json.loads(result.stdout)
        verdicts = output.get("verdicts", [])
    except (json.JSONDecodeError, TypeError) as exc:
        scan_analysis.record_verdict_agent(
            scan_id, status="failed", actionable_count=len(actionable),
            stdout=result.stdout, stderr=result.stderr,
            error=f"Invalid JSON stdout: {exc}", duration_ms=duration_ms,
        )
        return

    verdict_map = {str(v["insight_id"]): v for v in verdicts if "insight_id" in v}
    now = datetime.now(timezone.utc).isoformat()
    patched = 0
    for insight in insights:
        iid = str(insight.get("id", ""))
        v = verdict_map.get(iid)
        if v:
            insight["verdict"] = v.get("verdict", "escalate")
            insight["verdict_summary"] = v.get("verdict_summary", "")
            insight["verdict_evidence"] = v.get("verdict_evidence", "")
            insight["verdict_at"] = now
            patched += 1

    scan.insights_json = json.dumps(insights)
    db.session.commit()
    scan_analysis.record_verdict_agent(
        scan_id, status="success", actionable_count=len(actionable),
        patched_count=patched, stdout=result.stdout, stderr=result.stderr,
        raw_response=output, duration_ms=duration_ms,
    )
    _emit(socketio, scan_id, "insights.verdicts_ready")


def _should_run_synthesis(insights: list, diff: dict) -> tuple[bool, str]:
    if len(insights) < 2:
        return False, "Fewer than 2 insights"
    if SYNTHESIS_SKIP_BASELINE_ONLY and diff.get("baseline"):
        non_inv = [i for i in insights if i.get("type") != "baseline_inventory"]
        if len(non_inv) < 2:
            return False, "Baseline scan with insufficient non-inventory insights"
    return True, ""


def _append_synthesis_stories(scan: Scan, insights: list, stories: list) -> int:
    valid_ids = {str(i.get("id")) for i in insights if i.get("id")}
    now = datetime.now(timezone.utc).isoformat()
    added = 0
    for story in stories[:5]:
        related = [
            str(r) for r in (story.get("related_insight_ids") or [])
            if str(r) in valid_ids
        ]
        if not related and not story.get("message"):
            continue
        verdict = story.get("verdict", "escalate")
        if verdict not in ("escalate", "explain", "dismiss"):
            verdict = "escalate"
        host = story.get("host") or "network"
        insights.append({
            "id": str(uuid.uuid4()),
            "scan_id": scan.id,
            "type": "correlated",
            "host": host,
            "message": story.get("message", "Correlated finding cluster"),
            "priority": int(story.get("priority", 85)),
            "timestamp": now,
            "is_read": False,
            "synthesized": True,
            "details": {
                "related_insight_ids": related,
                "pattern": story.get("pattern", "cluster"),
                "hosts": story.get("hosts", []),
                "ports": story.get("ports", []),
            },
            "verdict": verdict,
            "verdict_summary": story.get("verdict_summary", story.get("message", ""))[:200],
            "verdict_evidence": story.get("verdict_evidence", ""),
            "verdict_at": now,
        })
        added += 1
    return added


def _run_synthesis(scan_id: int, socketio) -> None:
    scan = db.session.get(Scan, scan_id)
    if not scan or not scan.insights_json:
        scan_analysis.record_synthesis_agent(
            scan_id, status="skipped", skipped_reason="No insights_json",
        )
        return

    try:
        insights = json.loads(scan.insights_json)
    except (json.JSONDecodeError, TypeError):
        scan_analysis.record_synthesis_agent(
            scan_id, status="skipped", skipped_reason="Could not parse insights_json",
        )
        return

    diff = _load_diff(scan)
    should, skip_reason = _should_run_synthesis(insights, diff)
    if not should:
        scan_analysis.record_synthesis_agent(
            scan_id, status="skipped", skipped_reason=skip_reason,
        )
        return

    ok, reason = _can_call_agent()
    if not ok:
        scan_analysis.record_synthesis_agent(
            scan_id, status="skipped", skipped_reason=reason,
        )
        return

    payload = json.dumps({
        "scan_id": scan_id,
        "scan_type": scan.scan_type,
        "insights": insights,
        "diff": diff,
        "enrichment": build_enrichment_digest(insights, diff, scan),
        "max_stories": 5,
    })

    started = time.perf_counter()
    try:
        result = _run_subprocess(
            [_AGENT_PYTHON, _AGENT_SCRIPT, "--synthesize", payload],
            timeout=90,
        )
    except subprocess.TimeoutExpired:
        scan_analysis.record_synthesis_agent(
            scan_id, status="timeout",
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
        return
    except Exception as exc:
        scan_analysis.record_synthesis_agent(
            scan_id, status="failed", error=str(exc),
        )
        return

    duration_ms = int((time.perf_counter() - started) * 1000)
    if result.returncode != 0:
        scan_analysis.record_synthesis_agent(
            scan_id, status="failed", stderr=result.stderr, stdout=result.stdout,
            error=f"exit code {result.returncode}", duration_ms=duration_ms,
        )
        return

    try:
        output = json.loads(result.stdout)
        stories = output.get("stories", [])
    except (json.JSONDecodeError, TypeError) as exc:
        scan_analysis.record_synthesis_agent(
            scan_id, status="failed", stdout=result.stdout,
            error=f"Invalid JSON: {exc}", duration_ms=duration_ms,
        )
        return

    added = _append_synthesis_stories(scan, insights, stories)
    scan.insights_json = json.dumps(insights)
    db.session.commit()
    scan_analysis.record_synthesis_agent(
        scan_id, status="success", stories_added=added,
        raw_response=output, duration_ms=duration_ms,
    )
    if added:
        _emit(socketio, scan_id, "insights.synthesis_ready")


def _run_scan_analyst(scan_id: int) -> None:
    scan = db.session.get(Scan, scan_id)
    if not scan:
        return

    ok, reason = _can_call_agent()
    if not ok:
        scan_analysis.record_scan_analyst(
            scan_id, status="skipped", skipped_reason=reason, source="post_scan",
        )
        return

    started = time.perf_counter()
    try:
        result = _run_subprocess(
            [_AGENT_PYTHON, _AGENT_SCRIPT, "--scan-id", str(scan_id), "--no-post"],
            timeout=180,
        )
    except subprocess.TimeoutExpired:
        scan_analysis.record_scan_analyst(
            scan_id, status="timeout", source="post_scan",
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
        return
    except Exception as exc:
        scan_analysis.record_scan_analyst(
            scan_id, status="failed", source="post_scan", error=str(exc),
        )
        return

    duration_ms = int((time.perf_counter() - started) * 1000)
    if result.returncode != 0:
        scan_analysis.record_scan_analyst(
            scan_id, status="failed", source="post_scan",
            stderr=result.stderr, error=f"exit code {result.returncode}",
            duration_ms=duration_ms,
        )
        return

    try:
        output = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        scan_analysis.record_scan_analyst(
            scan_id, status="failed", source="post_scan",
            stdout=result.stdout, error=str(exc), duration_ms=duration_ms,
        )
        return

    scan_analysis.record_scan_analyst(
        scan_id,
        status="success",
        source="post_scan",
        verdict=output.get("verdict"),
        summary=output.get("summary"),
        findings=output.get("findings"),
        reasoning=(output.get("reasoning") or "")[:12000],
        duration_ms=duration_ms,
    )


def _emit(socketio, scan_id: int, event: str = "insights.verdicts_ready") -> None:
    try:
        socketio.emit(event, {"scan_id": scan_id})
    except Exception as exc:
        logger.warning("agent_service: socket emit failed: %s", exc)
