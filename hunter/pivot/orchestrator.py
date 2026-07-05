from __future__ import annotations

import json
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from agent import _chat_create, _make_client, _model_for, _store_incident

from .approval import requires_approval
from .blackboard import Blackboard
from .event_log import EventLog
from .hydration import hydrate_seed
from .report import write_pivot_report
from .runners.http_recon_runner import run_http_recon
from .runners.nmap_runner import run_nmap_scan, triage_ports
from .runners.smb_enum_runner import run_smb_enum
from .scope import ScopeGuard
from .status import write_status

SYSTEM = """You are SentinelZero Hunter Pivot Engine.

Role:
- Execute a bounded pivot chain starting from a seed insight (host + finding type).
- Choose the next passive or approved active action based on scan evidence.
- Never output blue-team verdicts (escalate/explain/dismiss).

Available actions (respond with JSON only):
{"action":"nmap_scan","ip":"<target>"}
{"action":"smb_enum","ip":"<target>"}
{"action":"http_recon","ip":"<target>"}
{"action":"complete","summary":"<short summary>"}

Rules:
- Stay within allowed CIDRs only.
- Prefer nmap_scan first on the seed host, then smb_enum if port 445/tcp is open.
- Run http_recon when 80/tcp or 443/tcp is open -- it identifies page content (title,
  server header, generator, missing security headers) via passive nmap NSE scripts.
  It is content identification, not enumeration: never follow it with path brute-forcing
  tools.
- If a "seed_hydration" event already reused open ports (and, when present, http_recon
  data) from a prior scan, do NOT re-run nmap_scan/http_recon for evidence you already
  have -- go straight to triage/complete on what's known.
- Call complete when you have enough evidence for a terminal finding.
"""


def _parse_action(text: str) -> dict[str, Any] | None:
    text = (text or "").strip()
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}") + 1
    if start < 0 or end <= start:
        return None
    try:
        payload = json.loads(text[start:end])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


@dataclass
class PivotMissionConfig:
    mission_id: str
    seed: dict[str, Any]
    allowed_cidrs: list[str]
    reports_dir: Path
    state_dir: Path
    target_network: str
    iface: str = "enp6s18"
    max_turns: int = 15
    fixture: bool = False
    allow_active: bool = False
    verbose: bool = False
    fixture_hydration: dict[str, Any] | None = None


@dataclass
class PivotRuntime:
    config: PivotMissionConfig
    event_log: EventLog
    board: Blackboard
    scope: ScopeGuard
    pending_approval: str | None = None
    terminal_findings: list[dict[str, Any]] = field(default_factory=list)
    hydrated_http_recon: dict[str, Any] | None = None


def _log(runtime: PivotRuntime, msg: str) -> None:
    if runtime.config.verbose:
        print(f"[pivot] {msg}", file=sys.stderr)


def _append_event(
    runtime: PivotRuntime,
    *,
    task_id: str,
    parent_event_id: str | None,
    ip: str,
    type: str,
    description: str,
    action: str,
    result: dict[str, Any] | None = None,
) -> None:
    event = runtime.event_log.append(
        task_id=task_id,
        parent_event_id=parent_event_id,
        ip=ip,
        type=type,
        description=description,
        action=action,
    )
    runtime.board.apply_event(event, result)


def _execute_action(runtime: PivotRuntime, action: str, ip: str) -> dict[str, Any]:
    cfg = runtime.config
    scope_err = runtime.scope.check_ip(ip) or runtime.scope.check_budget(ip)
    if scope_err:
        return {"error": scope_err}

    if requires_approval(action, allow_active=cfg.allow_active):
        runtime.pending_approval = action
        write_status(
            cfg.reports_dir,
            cfg.mission_id,
            state="stalled",
            last_task="awaiting approval",
        )
        return {"error": "awaiting approval", "action": action, "ip": ip}

    runtime.scope.record_task(ip)
    parent = runtime.board.last_event_id

    if action == "nmap_scan":
        result = run_nmap_scan(ip, fixture=cfg.fixture)
        if result.get("error"):
            _append_event(
                runtime,
                task_id=f"task-{uuid.uuid4().hex[:8]}",
                parent_event_id=parent,
                ip=ip,
                type="nmap_scan",
                description=f"nmap failed: {result['error']}",
                action="nmap_scan",
                result=result,
            )
            return result
        triage = triage_ports(result)
        desc = f"nmap found {result.get('count', 0)} open ports on {ip}"
        _append_event(
            runtime,
            task_id=f"task-{uuid.uuid4().hex[:8]}",
            parent_event_id=parent,
            ip=ip,
            type="nmap_scan",
            description=desc,
            action="nmap_scan",
            result=result,
        )
        _append_event(
            runtime,
            task_id=f"task-{uuid.uuid4().hex[:8]}",
            parent_event_id=runtime.board.last_event_id,
            ip=ip,
            type="triage",
            description=f"triage recommendations: {triage.get('recommendations')}",
            action="triage",
            result=triage,
        )
        runtime.board.open_ports = result.get("open_ports") or []
        return {"scan": result, "triage": triage}

    if action == "smb_enum":
        result = run_smb_enum(ip, fixture=cfg.fixture)
        shares = result.get("shares") or []
        desc = f"smb enum on {ip}: {len(shares)} shares"
        _append_event(
            runtime,
            task_id=f"task-{uuid.uuid4().hex[:8]}",
            parent_event_id=parent,
            ip=ip,
            type="smb_enum",
            description=desc,
            action="smb_enum",
            result=result,
        )
        finding = {
            "ip": ip,
            "type": "pivot_smb_exposure",
            "description": desc,
            "open_ports": runtime.board.open_ports,
            "shares": shares,
            "recommended_action": "observe",
        }
        runtime.board.findings.append(finding)
        runtime.terminal_findings.append(finding)
        return result

    if action == "http_recon":
        port_nums = {int(p.get("port", 0)) for p in runtime.board.open_ports}
        target_port = 80 if 80 in port_nums else 443
        result = run_http_recon(ip, port=target_port, fixture=cfg.fixture)
        desc = f"http_recon on {ip}:{target_port}: title={result.get('title')!r}"
        _append_event(
            runtime,
            task_id=f"task-{uuid.uuid4().hex[:8]}",
            parent_event_id=parent,
            ip=ip,
            type="http_recon",
            description=desc,
            action="http_recon",
            result=result,
        )
        finding = {
            "ip": ip,
            "type": "pivot_http_exposure",
            "description": desc,
            "open_ports": runtime.board.open_ports,
            "title": result.get("title"),
            "server_header": result.get("server_header"),
            "generator": result.get("generator"),
            "missing_security_headers": result.get("missing_security_headers") or [],
            "recommended_action": "observe",
        }
        runtime.board.findings.append(finding)
        runtime.terminal_findings.append(finding)
        return result

    return {"error": f"unknown action {action}"}


def _fixture_next_action(runtime: PivotRuntime, turn: int) -> dict[str, Any]:
    ip = runtime.board.seed_ip
    events = runtime.event_log.all_events()
    types = {e.type for e in events}
    if "nmap_scan" not in types and "seed_hydration" not in types:
        return {"action": "nmap_scan", "ip": ip}
    if "smb_enum" not in types and any(
        int(p.get("port", 0)) == 445 for p in runtime.board.open_ports
    ):
        return {"action": "smb_enum", "ip": ip}
    if (
        "http_recon" not in types
        and runtime.hydrated_http_recon is None
        and any(int(p.get("port", 0)) in (80, 443) for p in runtime.board.open_ports)
    ):
        return {"action": "http_recon", "ip": ip}
    return {"action": "complete", "summary": f"Fixture pivot chain complete for {ip}"}


def _llm_next_action(runtime: PivotRuntime, messages: list[dict[str, Any]]) -> dict[str, Any]:
    client = _make_client()
    resp = _chat_create(
        client,
        model=_model_for(),
        messages=messages,
        want_json=False,
    )
    text = (resp.choices[0].message.content or "").strip()
    parsed = _parse_action(text)
    if parsed and parsed.get("action"):
        return parsed
    return {"action": "complete", "summary": text or "LLM returned no actionable JSON"}


def run_pivot_mission(config: PivotMissionConfig) -> dict[str, Any]:
    db_path = config.state_dir / f"{config.mission_id}.sqlite"
    event_log = EventLog(db_path)
    board = Blackboard.from_seed(config.seed, config.allowed_cidrs)
    runtime = PivotRuntime(
        config=config,
        event_log=event_log,
        board=board,
        scope=ScopeGuard(allowed_cidrs=config.allowed_cidrs),
    )

    if config.fixture:
        hydrated = config.fixture_hydration or {
            "open_ports": [], "http_recon": None, "source_scan_id": board.scan_id,
        }
    else:
        hydrated = hydrate_seed(board.seed_ip, board.scan_id)

    if hydrated.get("open_ports"):
        board.open_ports = hydrated["open_ports"]
        _append_event(
            runtime,
            task_id=f"task-{uuid.uuid4().hex[:8]}",
            parent_event_id=None,
            ip=board.seed_ip,
            type="seed_hydration",
            description=(
                f"reused {len(hydrated['open_ports'])} open port(s) from "
                f"scan #{hydrated.get('source_scan_id')}"
            ),
            action="seed_hydration",
            result={"open_ports": hydrated["open_ports"]},
        )
        triage = triage_ports({"ip": board.seed_ip, "open_ports": board.open_ports})
        _append_event(
            runtime,
            task_id=f"task-{uuid.uuid4().hex[:8]}",
            parent_event_id=runtime.board.last_event_id,
            ip=board.seed_ip,
            type="triage",
            description=f"triage recommendations: {triage.get('recommendations')}",
            action="triage",
            result=triage,
        )
    if hydrated.get("http_recon"):
        runtime.hydrated_http_recon = hydrated["http_recon"]

    write_status(
        config.reports_dir,
        config.mission_id,
        state="running",
        last_task="starting",
    )

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM},
        {
            "role": "user",
            "content": json.dumps({
                "seed": config.seed,
                "allowed_cidrs": config.allowed_cidrs,
                "target_network": config.target_network,
                "hydrated_open_ports": board.open_ports,
                "hydrated_http_recon": runtime.hydrated_http_recon,
                "instructions": "Begin pivot chain from seed host.",
            }, indent=2),
        },
    ]

    result_summary = ""
    try:
        for turn in range(config.max_turns):
            write_status(
                config.reports_dir,
                config.mission_id,
                state="running",
                last_task=f"turn {turn}",
            )

            if config.fixture:
                action_payload = _fixture_next_action(runtime, turn)
            else:
                action_payload = _llm_next_action(runtime, messages)

            action = str(action_payload.get("action") or "").strip()
            ip = str(action_payload.get("ip") or runtime.board.current_ip or runtime.board.seed_ip).strip()
            _log(runtime, f"turn={turn} action={action} ip={ip}")

            if action == "complete":
                result_summary = str(action_payload.get("summary") or "mission complete")
                _append_event(
                    runtime,
                    task_id=f"task-{uuid.uuid4().hex[:8]}",
                    parent_event_id=runtime.board.last_event_id,
                    ip=ip,
                    type="mission_complete",
                    description=result_summary,
                    action="complete",
                )
                break

            exec_result = _execute_action(runtime, action, ip)
            if exec_result.get("error") == "awaiting approval":
                return {
                    "status": "stalled",
                    "mission_id": config.mission_id,
                    "reason": "awaiting approval",
                    "pending_action": runtime.pending_approval,
                }

            messages.append({"role": "assistant", "content": json.dumps(action_payload)})
            messages.append({"role": "user", "content": json.dumps(exec_result, indent=2)})

            if runtime.terminal_findings and action == "smb_enum":
                result_summary = f"SMB pivot complete for {ip}"
                break
            if runtime.terminal_findings and action == "http_recon":
                result_summary = f"HTTP recon pivot complete for {ip}"
                break
        else:
            result_summary = f"Exceeded max_turns={config.max_turns}"

        if not runtime.terminal_findings and runtime.board.open_ports:
            ip = runtime.board.seed_ip
            runtime.terminal_findings.append({
                "ip": ip,
                "type": "pivot_recon",
                "description": f"Recon pivot on {ip}: {len(runtime.board.open_ports)} open ports",
                "open_ports": runtime.board.open_ports,
                "recommended_action": "observe",
            })

        runtime.board.worker_summaries.append(result_summary)
        pivot_events = event_log.export_dicts()
        report_result = write_pivot_report(
            reports_dir=config.reports_dir,
            mission_id=config.mission_id,
            seed=config.seed,
            pivot_events=pivot_events,
            findings=runtime.terminal_findings,
            worker_summaries=runtime.board.worker_summaries,
            target_network=config.target_network,
            iface=config.iface,
        )

        for finding in runtime.terminal_findings:
            summary = finding.get("description") or ""
            if summary:
                _store_incident(
                    finding.get("ip"),
                    None,
                    config.seed.get("scan_id"),
                    summary,
                    source="mission",
                )

        write_status(
            config.reports_dir,
            config.mission_id,
            state="done",
            last_task="complete",
        )

        return {
            "status": "done",
            "mission_id": config.mission_id,
            "summary": result_summary,
            "report_path": report_result.get("path"),
            "event_count": len(pivot_events),
            "findings_count": len(runtime.terminal_findings),
        }
    except Exception as exc:
        write_status(
            config.reports_dir,
            config.mission_id,
            state="failed",
            last_task="error",
            error=str(exc),
        )
        raise
    finally:
        event_log.close()
