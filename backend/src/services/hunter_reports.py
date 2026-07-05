"""Normalize Hunter report artifacts for SentinelZero UI consumption."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MISSION_STALE_MINUTES = 15

DEFAULT_REPORT_DIRS = (
    "/home/hunter/agent/reports",
    "/home/sentinel/agent/reports",
)

DEFAULT_BASELINE_PATHS = (
    "/home/hunter/agent/state/iot_fingerprints.json",
    "/home/sentinel/agent/state/iot_fingerprints.json",
)

NOVELTY_WEIGHTS = {
    "new_device": 6,
    "new_udp_port": 4,
    "expected_udp_violation": 4,
    "new_host": 3,
}

DRIFT_WEIGHTS = {
    "lost_udp_port": 3,
    "expected_udp_violation": 2,
    "service_change": 2,
}

NOW_TYPES = {"new_device", "new_udp_port", "expected_udp_violation"}
OBSERVE_TYPES = {"lost_udp_port", "iot_observation"}


def _safe_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _env_list(name: str) -> list[str]:
    raw = os.environ.get(name, "")
    if not raw.strip():
        return []
    return [item.strip() for item in raw.split(":") if item.strip()]


def report_dirs() -> list[Path]:
    configured = _env_list("HUNTER_REPORTS_DIRS")
    single = os.environ.get("HUNTER_REPORTS_DIR")
    if single:
        configured.append(single.strip())
    if not configured:
        configured = list(DEFAULT_REPORT_DIRS)
    return [Path(item) for item in configured]


def baseline_paths() -> list[Path]:
    configured = _env_list("HUNTER_BASELINE_PATHS")
    single = os.environ.get("HUNTER_BASELINE_PATH")
    if single:
        configured.append(single.strip())
    if not configured:
        configured = list(DEFAULT_BASELINE_PATHS)
    return [Path(item) for item in configured]


def _read_json_file(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _load_baseline_state() -> dict[str, Any]:
    for path in baseline_paths():
        if path.exists():
            payload = _read_json_file(path)
            if payload is not None:
                payload["_baseline_path"] = str(path)
                return payload
    return {"schema_version": 1, "fingerprints": {}}


def _iter_report_files(limit: int = 50) -> list[Path]:
    files: list[Path] = []
    for root in report_dirs():
        if not root.exists() or not root.is_dir():
            continue
        files.extend(root.glob("hunt-*.json"))
    files = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)
    return files[: max(limit, 1)]


def _scan_trigger_status(scan_triggered: Any) -> str:
    if not isinstance(scan_triggered, dict):
        return "none"
    if scan_triggered.get("status") == "skipped":
        return "skipped"
    if scan_triggered.get("error"):
        return "failed"
    if scan_triggered.get("scan_id") or scan_triggered.get("status") == "success":
        return "triggered"
    return "none"


def _event_severity(event_type: str) -> str:
    if event_type in {"expected_udp_violation", "new_device"}:
        return "high"
    if event_type in {"new_udp_port", "new_host"}:
        return "medium"
    if event_type in {"lost_udp_port", "iot_observation"}:
        return "low"
    return "info"


def _default_action_for_type(event_type: str) -> str:
    if event_type in NOW_TYPES:
        return "now"
    if event_type in OBSERVE_TYPES:
        return "observe"
    return "next_scan"


def _build_events(raw: dict[str, Any]) -> list[dict[str, Any]]:
    findings = raw.get("findings") or []
    diffs = raw.get("fingerprint_diffs") or []
    events: list[dict[str, Any]] = []
    idx = 0
    for source_field, items in (("findings", findings), ("fingerprint_diffs", diffs)):
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            ip = str(item.get("ip") or "").strip()
            event_type = str(item.get("type") or "unknown").strip() or "unknown"
            events.append({
                "event_id": f"{source_field}:{idx}",
                "ip": ip,
                "type": event_type,
                "severity": _event_severity(event_type),
                "description": str(item.get("description") or "").strip(),
                "recommended_action": str(item.get("recommended_action") or "").strip() or _default_action_for_type(event_type),
                "source_field": source_field,
                "raw_index": idx,
                "open_ports": item.get("open_ports") if isinstance(item.get("open_ports"), list) else [],
                "udp_ports": item.get("udp_ports") if isinstance(item.get("udp_ports"), list) else [],
                "device_hint": str(item.get("device_hint") or "").strip() or None,
                "confidence": str(item.get("confidence") or "").strip() or None,
                "server_header": str(item.get("server_header") or "").strip() or None,
                "title": str(item.get("title") or "").strip() or None,
                "generator": str(item.get("generator") or "").strip() or None,
                "missing_security_headers": item.get("missing_security_headers") if isinstance(item.get("missing_security_headers"), list) else [],
            })
            idx += 1
    return events


def _host_rollups(
    raw: dict[str, Any],
    events: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    recommended = [str(ip).strip() for ip in (raw.get("hosts_recommended_for_scan") or []) if str(ip).strip()]
    recommended_set = set(recommended)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        if event["ip"]:
            grouped[event["ip"]].append(event)

    # Ensure all recommended hosts have rows, even without events.
    for ip in recommended:
        grouped.setdefault(ip, [])

    hosts: list[dict[str, Any]] = []
    recommendations: list[dict[str, Any]] = []
    for ip, host_events in grouped.items():
        novelty = sum(NOVELTY_WEIGHTS.get(ev["type"], 0) for ev in host_events)
        drift = sum(DRIFT_WEIGHTS.get(ev["type"], 0) for ev in host_events)
        evidence = min(10, len(host_events) + (2 if ip in recommended_set else 0))
        action = "observe"
        explicit_actions = {ev["recommended_action"] for ev in host_events if ev.get("recommended_action")}
        if "none_until_online" in explicit_actions:
            action = "none_until_online"
        elif any(ev["type"] in NOW_TYPES for ev in host_events):
            action = "now"
        elif ip in recommended_set:
            action = "next_scan"
        elif any(ev["type"] in OBSERVE_TYPES for ev in host_events):
            action = "observe"
        elif host_events:
            action = "next_scan"

        hosts.append({
            "ip": ip,
            "event_count": len(host_events),
            "noveltyScore": novelty,
            "driftScore": drift,
            "evidenceStrength": evidence,
            "actionPriority": action,
            "recommendedForScan": ip in recommended_set,
            "events": host_events,
            "topEventTypes": dict(Counter(ev["type"] for ev in host_events).most_common(4)),
        })
        recommendations.append({
            "ip": ip,
            "actionPriority": action,
            "noveltyScore": novelty,
            "driftScore": drift,
            "eventCount": len(host_events),
            "recommendedForScan": ip in recommended_set,
        })

    priority_rank = {"now": 0, "next_scan": 1, "observe": 2, "none_until_online": 3}
    hosts.sort(
        key=lambda host: (
            priority_rank.get(host["actionPriority"], 4),
            -host["noveltyScore"],
            -host["driftScore"],
            -host["evidenceStrength"],
            host["ip"],
        )
    )
    recommendations.sort(
        key=lambda row: (
            priority_rank.get(row["actionPriority"], 4),
            -row["noveltyScore"],
            -row["driftScore"],
            -row["eventCount"],
            row["ip"],
        )
    )
    return hosts, recommendations


def _build_histogram(events: list[dict[str, Any]]) -> dict[str, int]:
    histogram = Counter(event["type"] for event in events)
    return {key: histogram[key] for key in sorted(histogram.keys())}


def _build_deterministic_bullets(run: dict[str, Any]) -> list[str]:
    bullets: list[str] = []
    scan_status = run["huntRun"]["scanTriggerStatus"]
    if scan_status == "triggered":
        bullets.append("Hunter triggered a follow-up scan handoff for this run.")
    elif scan_status == "skipped":
        bullets.append("Hunter did not trigger a follow-up scan in this run.")

    events = run["huntEvent"]
    if events:
        histogram = _build_histogram(events)
        top = ", ".join(f"{k}:{v}" for k, v in list(histogram.items())[:4])
        bullets.append(f"Observed {len(events)} evidence events ({top}).")
    else:
        bullets.append("No structured hunt events were recorded in this run.")

    top_hosts = run["huntRecommendation"][:3]
    if top_hosts:
        rendered = ", ".join(f"{item['ip']} ({item['actionPriority']})" for item in top_hosts)
        bullets.append(f"Top action targets: {rendered}.")
    return bullets


def build_llm_context_pack(run: dict[str, Any], top_n_hosts: int = 5, events_per_host: int = 3) -> dict[str, Any]:
    hunt_run = run["huntRun"]
    hosts = run["huntHost"][: max(top_n_hosts, 1)]
    host_snippets: list[dict[str, Any]] = []
    for host in hosts:
        snippets = []
        for event in host["events"][: max(events_per_host, 1)]:
            snippets.append({
                "type": event["type"],
                "description": event["description"],
                "recommended_action": event["recommended_action"],
            })
        host_snippets.append({
            "ip": host["ip"],
            "actionPriority": host["actionPriority"],
            "noveltyScore": host["noveltyScore"],
            "driftScore": host["driftScore"],
            "evidenceStrength": host["evidenceStrength"],
            "evidence": snippets,
        })

    must_mention = [
        f"scan_trigger_status={hunt_run['scanTriggerStatus']}",
        f"event_total={hunt_run['eventCount']}",
    ]
    if host_snippets:
        must_mention.append(f"top_host={host_snippets[0]['ip']}")
    histogram = run["whatChanged"]["eventHistogram"]
    if histogram:
        first_type = next(iter(histogram))
        must_mention.append(f"top_event_type={first_type}")

    return {
        "run_summary": {
            "run_id": hunt_run["runId"],
            "mission_id": hunt_run["missionId"],
            "target_network": hunt_run["targetNetwork"],
            "completed_at": hunt_run["completedAt"],
            "seed_summary": hunt_run["seedSummary"],
            "scan_trigger_status": hunt_run["scanTriggerStatus"],
        },
        "event_histogram": histogram,
        "top_hosts": host_snippets,
        "caveats": {
            "recommendations_capped": hunt_run["hostsRecommendedCapped"],
            "worker_summaries": hunt_run["workerSummaries"][:6],
        },
        "must_mention_facts": must_mention,
        "prompt_contract": {
            "system": (
                "Summarize this hunter run for operators. Do not invent facts. "
                "Use only provided fields and preserve action priorities."
            ),
            "acceptance_checks": [
                "Includes scan trigger status",
                "Includes top prioritized host and action",
                "Includes one key event type with count",
            ],
        },
    }


def _build_pivot_chain(raw: dict[str, Any]) -> dict[str, Any] | None:
    items = raw.get("pivot_events")
    if not isinstance(items, list) or not items:
        return None

    events: list[dict[str, Any]] = []
    parent_ids: set[str] = set()
    child_refs = 0
    max_seq = 0

    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        event_id = str(item.get("event_id") or f"pivot:{idx}")
        parent = item.get("parent_event_id")
        seq = _safe_int(item.get("seq"), idx + 1)
        max_seq = max(max_seq, seq)
        if parent:
            child_refs += 1
        parent_ids.add(event_id)
        events.append({
            "eventId": event_id,
            "seq": seq,
            "ts": item.get("ts"),
            "taskId": str(item.get("task_id") or ""),
            "parentEventId": parent,
            "ip": str(item.get("ip") or ""),
            "type": str(item.get("type") or "unknown"),
            "description": str(item.get("description") or ""),
            "action": str(item.get("action") or ""),
        })

    if not events:
        return None

    depth = 1
    if child_refs:
        by_id = {event["eventId"]: event for event in events}

        def _depth(event_id: str, seen: set[str]) -> int:
            if event_id in seen:
                return 1
            seen.add(event_id)
            event = by_id.get(event_id)
            if not event or not event.get("parentEventId"):
                return 1
            return 1 + _depth(str(event["parentEventId"]), seen)

        depth = max(_depth(event["eventId"], set()) for event in events)

    return {
        "events": events,
        "edgeCount": child_refs,
        "depth": depth,
        "eventTotal": len(events),
        "maxSeq": max_seq,
    }


def _mission_logs_dir() -> Path:
    reports = os.environ.get("HUNTER_REPORTS_DIR", "")
    if reports:
        return Path(reports) / "mission-logs"
    for root in report_dirs():
        candidate = root / "mission-logs"
        if candidate.exists():
            return candidate
    return Path(DEFAULT_REPORT_DIRS[0]) / "mission-logs"


def _mission_seeds_dir() -> Path:
    return _mission_logs_dir() / "seeds"


def _read_mission_seed(mission_id: str) -> dict[str, Any] | None:
    cleaned = str(mission_id or "").strip()
    if not cleaned:
        return None
    seed_path = _mission_seeds_dir() / f"{cleaned}.json"
    if not seed_path.exists():
        return None
    payload = _read_json_file(seed_path)
    return payload if isinstance(payload, dict) else None


def _mission_seed_matches(seed: dict[str, Any], candidate_seed: dict[str, Any] | None) -> bool:
    if not candidate_seed:
        return False
    insight_id = str(seed.get("insight_id") or "").strip()
    if insight_id:
        return str(candidate_seed.get("insight_id") or "").strip() == insight_id
    seed_ip = str(seed.get("ip") or "").strip()
    seed_type = str(seed.get("type") or "").strip()
    if not seed_ip or not seed_type:
        return False
    return (
        str(candidate_seed.get("ip") or "").strip() == seed_ip
        and str(candidate_seed.get("type") or "").strip() == seed_type
    )


_BLOCKING_MISSION_STATES = frozenset({"running", "queued", "done"})


def find_blocking_mission(seed: dict[str, Any]) -> dict[str, Any] | None:
    """Return an existing mission that blocks spawning the same insight again."""
    if not isinstance(seed, dict):
        return None
    for path in _iter_status_files(limit=500):
        payload = _read_json_file(path)
        if payload is None:
            continue
        mission_id = str(payload.get("mission_id") or "").strip()
        if not mission_id:
            continue
        candidate_seed = _read_mission_seed(mission_id)
        if not _mission_seed_matches(seed, candidate_seed):
            continue
        state = _effective_mission_state(payload)
        if state in _BLOCKING_MISSION_STATES:
            normalized = _normalize_mission_status(payload, status_name=path.name)
            normalized["state"] = state
            return normalized
    return None


def read_mission_log(mission_id: str, *, tail_bytes: int = 65536) -> str | None:
    cleaned = str(mission_id or "").strip()
    if not cleaned:
        return None
    log_path = _mission_logs_dir() / f"{cleaned}.log"
    if not log_path.exists() or not log_path.is_file():
        return None
    size = log_path.stat().st_size
    with log_path.open("rb") as handle:
        if size > tail_bytes:
            handle.seek(-tail_bytes, os.SEEK_END)
        data = handle.read()
    return data.decode("utf-8", errors="replace")


def _iter_status_files(limit: int = 50) -> list[Path]:
    files: list[Path] = []
    for root in report_dirs():
        if not root.exists() or not root.is_dir():
            continue
        files.extend(root.glob("hunt-*.status.json"))
    files = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)
    return files[: max(limit, 1)]


def _pid_alive(pid: Any) -> bool:
    try:
        pid_int = int(pid)
    except (TypeError, ValueError):
        return False
    if pid_int <= 0:
        return False
    try:
        os.kill(pid_int, 0)
    except OSError:
        return False
    return True


def _effective_mission_state(payload: dict[str, Any]) -> str:
    state = str(payload.get("state") or "unknown").strip().lower()
    if state in {"done", "failed", "stalled"}:
        return state
    updated_at = _parse_iso(payload.get("updated_at"))
    if updated_at:
        age_min = (datetime.now(timezone.utc) - updated_at).total_seconds() / 60.0
        pid = payload.get("pid")
        if age_min > MISSION_STALE_MINUTES and not _pid_alive(pid):
            return "stalled"
    return state or "unknown"


def _normalize_mission_status(raw: dict[str, Any], *, status_name: str) -> dict[str, Any]:
    mission_id = str(raw.get("mission_id") or "").strip()
    if mission_id.startswith("hunt-"):
        mission_id = mission_id.removeprefix("hunt-").removesuffix(".status.json")
    state = _effective_mission_state(raw)
    report_glob = None
    for root in report_dirs():
        if not root.exists():
            continue
        matches = sorted(root.glob(f"hunt-{mission_id}-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if matches:
            report_glob = matches[0].name
            break
    seed = _read_mission_seed(mission_id) or {}
    return {
        "missionId": mission_id,
        "statusFile": status_name,
        "state": state,
        "startedAt": raw.get("started_at"),
        "updatedAt": raw.get("updated_at"),
        "pid": raw.get("pid"),
        "lastTask": raw.get("last_task"),
        "error": raw.get("error"),
        "reportId": report_glob,
        "insightId": seed.get("insight_id"),
        "host": seed.get("ip"),
        "type": seed.get("type"),
    }


def list_missions(limit: int = 20) -> list[dict[str, Any]]:
    missions: list[dict[str, Any]] = []
    for path in _iter_status_files(limit=limit):
        payload = _read_json_file(path)
        if payload is None:
            continue
        missions.append(_normalize_mission_status(payload, status_name=path.name))
    missions.sort(
        key=lambda item: _parse_iso(item.get("updatedAt")) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return missions


def mission_by_id(mission_id: str) -> dict[str, Any] | None:
    cleaned = str(mission_id or "").strip()
    if not cleaned:
        return None
    target_name = f"hunt-{cleaned}.status.json"
    for path in _iter_status_files(limit=500):
        if path.name != target_name:
            continue
        payload = _read_json_file(path)
        if payload is None:
            return None
        return _normalize_mission_status(payload, status_name=path.name)
    return None


def normalize_report(raw: dict[str, Any], *, report_name: str) -> dict[str, Any]:
    events = _build_events(raw)
    hosts, recommendations = _host_rollups(raw, events)
    histogram = _build_histogram(events)
    hunt_run = {
        "runId": report_name,
        "missionId": str(raw.get("mission_id") or ""),
        "targetNetwork": str(raw.get("target_network") or ""),
        "executor": str(raw.get("executor") or ""),
        "iface": str(raw.get("iface") or ""),
        "completedAt": raw.get("completed_at"),
        "seedSummary": raw.get("seed_summary") if isinstance(raw.get("seed_summary"), dict) else {},
        "scanTriggered": raw.get("scan_triggered"),
        "scanTriggerStatus": _scan_trigger_status(raw.get("scan_triggered")),
        "hostsRecommendedTotal": _safe_int(raw.get("hosts_recommended_total"), len(raw.get("hosts_recommended_for_scan") or [])),
        "hostsRecommendedCapped": bool(raw.get("hosts_recommended_capped")),
        "baselineUpdated": raw.get("baseline_updated") if isinstance(raw.get("baseline_updated"), dict) else None,
        "deviceContextSummary": raw.get("device_context_summary") if isinstance(raw.get("device_context_summary"), dict) else None,
        "workerSummaries": raw.get("worker_summaries") if isinstance(raw.get("worker_summaries"), list) else [],
        "eventCount": len(events),
        "hostCount": len(hosts),
        "missionType": str(raw.get("mission_type") or "inventory"),
    }
    normalized = {
        "huntRun": hunt_run,
        "huntHost": hosts,
        "huntEvent": events,
        "huntRecommendation": recommendations,
        "whatChanged": {
            "eventHistogram": histogram,
            "eventTotal": len(events),
            "hostTotal": len(hosts),
        },
    }
    pivot_chain = _build_pivot_chain(raw)
    if pivot_chain is not None:
        normalized["huntPivotChain"] = pivot_chain
    normalized["deterministicNarrative"] = _build_deterministic_bullets(normalized)
    normalized["llmContextPack"] = build_llm_context_pack(normalized)
    return normalized


def list_normalized_runs(limit: int = 20) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for path in _iter_report_files(limit=limit):
        payload = _read_json_file(path)
        if payload is None:
            continue
        runs.append(normalize_report(payload, report_name=path.name))
    runs.sort(
        key=lambda run: _parse_iso(run["huntRun"].get("completedAt")) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return runs


def latest_normalized_run() -> dict[str, Any] | None:
    runs = list_normalized_runs(limit=1)
    if not runs:
        return None
    return runs[0]


def normalized_run_by_id(run_id: str) -> dict[str, Any] | None:
    cleaned = str(run_id or "").strip()
    if not cleaned:
        return None
    for path in _iter_report_files(limit=500):
        if path.name != cleaned:
            continue
        payload = _read_json_file(path)
        if payload is None:
            return None
        return normalize_report(payload, report_name=path.name)
    return None


def hunter_overview(limit: int = 20) -> dict[str, Any]:
    runs = list_normalized_runs(limit=limit)
    latest = runs[0] if runs else None
    baseline = _load_baseline_state()
    fingerprints = baseline.get("fingerprints") if isinstance(baseline.get("fingerprints"), dict) else {}
    fingerprint_hosts = len(fingerprints)
    overview = {
        "runs": runs,
        "latest": latest,
        "meta": {
            "report_dirs": [str(p) for p in report_dirs()],
            "run_count": len(runs),
            "baseline_path": baseline.get("_baseline_path"),
            "baseline_schema_version": baseline.get("schema_version"),
            "baseline_fingerprint_hosts": fingerprint_hosts,
        },
    }
    return overview


def _baseline_history_dir() -> Path:
    raw = os.environ.get("HUNTER_BASELINE_HISTORY_DIR")
    if raw:
        return Path(raw)
    return Path(os.path.expanduser("~/agent/state/baseline_history"))


def _list_baseline_snapshots(history_dir: Path) -> list[Path]:
    if not history_dir.exists():
        return []
    return sorted(p for p in history_dir.glob("snapshot-*.json") if p.is_file())


def baseline_status() -> dict[str, Any]:
    baseline_path = next((p for p in baseline_paths() if p.exists()), None)
    history_dir = _baseline_history_dir()
    snapshots = _list_baseline_snapshots(history_dir)
    if baseline_path is None:
        return {
            "exists": False,
            "path_used": None,
            "size_bytes": 0,
            "sha256": None,
            "modified_at": None,
            "snapshot_count": len(snapshots),
        }

    content = baseline_path.read_bytes()
    modified = datetime.fromtimestamp(baseline_path.stat().st_mtime, tz=timezone.utc).isoformat()
    return {
        "exists": True,
        "path_used": str(baseline_path),
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "modified_at": modified,
        "snapshot_count": len(snapshots),
    }


def snapshot_baseline(max_snapshots: int = 30) -> dict[str, Any]:
    baseline_path = next((p for p in baseline_paths() if p.exists()), None)
    history_dir = _baseline_history_dir()
    history_dir.mkdir(parents=True, exist_ok=True)
    snapshots = _list_baseline_snapshots(history_dir)

    if baseline_path is None:
        return {"status": "no_baseline", "snapshot_count": len(snapshots)}

    content = baseline_path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if snapshots:
        latest_digest = hashlib.sha256(snapshots[-1].read_bytes()).hexdigest()
        if latest_digest == digest:
            return {"status": "unchanged", "snapshot_count": len(snapshots)}

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination = history_dir / f"snapshot-{timestamp}.json"
    shutil.copy2(baseline_path, destination)
    snapshots = _list_baseline_snapshots(history_dir)

    while len(snapshots) > max_snapshots:
        snapshots[0].unlink(missing_ok=True)
        snapshots = _list_baseline_snapshots(history_dir)

    return {"status": "snapshotted", "snapshot_count": len(snapshots)}

