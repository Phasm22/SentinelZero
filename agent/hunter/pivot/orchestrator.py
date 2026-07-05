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
from .http_recon_parse import HTTP_PORTS, recommend_http_action
from .hydration import hydrate_seed
from .report import write_pivot_report
from .runners.asset_expectation_runner import (
    recommend_asset_action,
    run_asset_expectation_check,
)
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
{"action":"asset_expectation_check","ip":"<target>"}
{"action":"complete","summary":"<short summary>"}

Rules:
- Stay within allowed CIDRs only.
- Prefer nmap_scan first on the seed host, then smb_enum if port 445/tcp is open.
- Run http_recon when an HTTP(S) surface port is open (80,443,8080,8443,3128,8006,8581)
  -- it identifies page content (title, server header, generator, missing security
  headers) via passive nmap NSE scripts. It is content identification, not enumeration:
  never follow it with path brute-forcing tools.
- Run asset_expectation_check once open ports are known -- it compares them against the
  host's registered expectation (assets.json) and never touches the network. It flags
  unexpected ports and unregistered hosts. Prefer it before completing so the finding
  carries drift context.
- If a "seed_hydration" event already reused open ports (and, when present, http_recon
  data) from a prior scan, do NOT re-run nmap_scan/http_recon for evidence you already
  have -- go straight to triage/complete on what's known.
- Call complete when you have enough evidence for a terminal finding.
"""


def _first_json_object(text: str) -> str | None:
    """Return the substring of the first balanced, top-level ``{...}`` object.

    Small local models often emit several action objects on separate lines; the
    naive first-brace..last-brace span then fails to parse and the mission
    dead-ends. Scanning for the first complete object (string-aware) lets us act
    on the model's first choice instead of discarding the whole turn.
    """
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _parse_action(text: str) -> dict[str, Any] | None:
    text = (text or "").strip()
    if not text:
        return None
    candidate = _first_json_object(text)
    if candidate is None:
        return None
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _select_http_port(open_ports: list[dict[str, Any]]) -> int | None:
    """Pick the highest-value open HTTP(S) surface port, in HTTP_PORTS priority
    order, so an 8080-only host targets 8080 rather than defaulting to 80/443."""
    port_nums = {int(p.get("port", 0)) for p in open_ports}
    for candidate in HTTP_PORTS:
        if candidate in port_nums:
            return candidate
    return None


def _build_http_finding(
    ip: str, port: int, recon: dict[str, Any], open_ports: list[dict[str, Any]]
) -> dict[str, Any]:
    """Typed pivot_http_exposure finding, shared by the live http_recon dispatch
    and the hydrated-evidence path so both grade identically."""
    missing = recon.get("missing_security_headers") or []
    return {
        "ip": ip,
        "type": "pivot_http_exposure",
        "description": (
            f"http exposure on {ip}:{port}: title={recon.get('title')!r}"
        ),
        "port": port,
        "open_ports": open_ports,
        "title": recon.get("title"),
        "server_header": recon.get("server_header"),
        "generator": recon.get("generator"),
        "missing_security_headers": missing,
        "recommended_action": recommend_http_action(
            port=port,
            title=recon.get("title"),
            server_header=recon.get("server_header"),
            generator=recon.get("generator"),
            missing_security_headers=missing,
        ),
    }


def _build_asset_finding(
    ip: str, result: dict[str, Any], open_ports: list[dict[str, Any]]
) -> dict[str, Any]:
    """Typed pivot_asset_drift finding from an asset-expectation result."""
    unexpected = result.get("unexpected_ports") or []
    if not result.get("registered", False):
        desc = f"{ip} is not in the asset inventory: {len(unexpected)} open port(s)"
    elif unexpected:
        desc = f"{ip} ({result.get('name')}) has unexpected port(s): {unexpected}"
    else:
        desc = f"{ip} ({result.get('name')}) ports match expectation"
    return {
        "ip": ip,
        "type": "pivot_asset_drift",
        "description": desc,
        "open_ports": open_ports,
        "registered": result.get("registered", False),
        "name": result.get("name"),
        "role": result.get("role"),
        "trust_zone": result.get("trust_zone"),
        "expected_ports": result.get("expected_ports") or [],
        "unexpected_ports": unexpected,
        "missing_ports": result.get("missing_ports") or [],
        "recommended_action": recommend_asset_action(result),
    }


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
        target_port = _select_http_port(runtime.board.open_ports) or 80
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
        finding = _build_http_finding(ip, target_port, result, runtime.board.open_ports)
        runtime.board.findings.append(finding)
        runtime.terminal_findings.append(finding)
        return result

    if action == "asset_expectation_check":
        result = run_asset_expectation_check(
            ip, runtime.board.open_ports, fixture=cfg.fixture
        )
        finding = _build_asset_finding(ip, result, runtime.board.open_ports)
        _append_event(
            runtime,
            task_id=f"task-{uuid.uuid4().hex[:8]}",
            parent_event_id=parent,
            ip=ip,
            type="asset_expectation_check",
            description=finding["description"],
            action="asset_expectation_check",
            result=result,
        )
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
    # Asset drift first: it is port-agnostic and never breaks the chain, so it
    # runs before the service runners (which terminate the mission on first find).
    if "asset_expectation_check" not in types and runtime.board.open_ports:
        return {"action": "asset_expectation_check", "ip": ip}
    if "smb_enum" not in types and any(
        int(p.get("port", 0)) == 445 for p in runtime.board.open_ports
    ):
        return {"action": "smb_enum", "ip": ip}
    if (
        "http_recon" not in types
        and runtime.hydrated_http_recon is None
        and any(int(p.get("port", 0)) in HTTP_PORTS for p in runtime.board.open_ports)
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
        # Drift analysis on the reused ports -- a local-file comparison, no probe.
        asset_result = run_asset_expectation_check(
            board.seed_ip, board.open_ports, fixture=config.fixture
        )
        asset_finding = _build_asset_finding(
            board.seed_ip, asset_result, board.open_ports
        )
        _append_event(
            runtime,
            task_id=f"task-{uuid.uuid4().hex[:8]}",
            parent_event_id=runtime.board.last_event_id,
            ip=board.seed_ip,
            type="asset_expectation_check",
            description=asset_finding["description"],
            action="asset_expectation_check",
            result=asset_result,
        )
        runtime.board.findings.append(asset_finding)
        runtime.terminal_findings.append(asset_finding)
    if hydrated.get("http_recon"):
        runtime.hydrated_http_recon = hydrated["http_recon"]
        # Reused http_recon evidence terminates to a typed finding here rather
        # than dead-ending at the generic pivot_recon fallback. Event type is
        # "http_exposure" (not "http_recon") because no live NSE run occurred.
        http_port = _select_http_port(board.open_ports) or 80
        http_finding = _build_http_finding(
            board.seed_ip, http_port, hydrated["http_recon"], board.open_ports
        )
        _append_event(
            runtime,
            task_id=f"task-{uuid.uuid4().hex[:8]}",
            parent_event_id=runtime.board.last_event_id,
            ip=board.seed_ip,
            type="http_exposure",
            description=http_finding["description"],
            action="http_exposure",
            result=hydrated["http_recon"],
        )
        runtime.board.findings.append(http_finding)
        runtime.terminal_findings.append(http_finding)

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
