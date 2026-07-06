from __future__ import annotations

import json
import sys
from typing import Any

from agent import _chat_create, _make_client, _model_for

from .tools import HunterRuntime, dispatch_tool, tool_schemas_for_runtime


def _parse_faux_tool_call(text: str) -> tuple[str, dict[str, Any]] | None:
    """Recover tool intent when the model writes JSON instead of using tool_calls."""
    if not text.startswith("{"):
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    name = payload.get("name") or payload.get("tool")
    args = payload.get("arguments") or payload.get("parameters") or payload.get("args")
    if isinstance(name, str) and isinstance(args, dict):
        return name, args
    return None


SYSTEM = """You are SentinelZero Hunter.

Role:
- You are a red-team style network hunter that gathers evidence and proposes scan handoffs.
- You must never output blue-team verdicts (no escalate/explain/dismiss).
- Gather facts, submit findings, and finalize a report.

Workflow:
1. Review mission + seed + ranked candidates.
2. Use discover_hosts and port_scan_light only within scope.
2b. Use port_scan_iot only when assess profile is active and the host is flagged.
3. After each port_scan_light or port_scan_iot, call submit_finding with ip, description, and open_ports.
4. Call finalize_hunt_report only after at least one submit_finding.

Output:
- Either call tools or return JSON:
  {"status":"complete","summary":"..."}
"""


def run_hunter_loop(
    runtime: HunterRuntime,
    *,
    verbose: bool = False,
    max_turns: int | None = None,
) -> dict[str, Any]:
    client = _make_client()
    user_payload = {
        "mission": {
            "id": runtime.mission.mission_id,
            "objective": runtime.mission.objective,
            "target_network": runtime.mission.target_network,
            "profile": runtime.mission.profile,
            "allowed_cidrs": runtime.mission.allowed_cidrs,
        },
        "seed": runtime.seed_result.to_dict(),
        "ranked_candidates": runtime.ranked_candidates,
        "device_context": runtime.device_context,
        "fingerprints_observed": runtime.fingerprints,
        "instructions": [
            "Gather evidence and submit findings.",
            "Call finalize_hunt_report once you have enough evidence.",
            "Do not issue verdict language.",
        ],
    }
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": json.dumps(user_payload, indent=2)},
    ]
    tool_schemas = tool_schemas_for_runtime(runtime)

    turns = max_turns or runtime.mission.max_turns
    for idx in range(turns):
        resp = _chat_create(
            client,
            model=_model_for(),
            messages=messages,
            tools=tool_schemas,
            tool_choice="auto",
            # JSON mode makes Ollama emit faux tool-call JSON in content instead of
            # real tool_calls; keep plain completions while the tool loop is active.
            want_json=False,
        )
        msg = resp.choices[0].message
        finish_reason = resp.choices[0].finish_reason
        tool_calls = msg.tool_calls or []

        if verbose:
            print(
                f"[hunter] turn={idx} finish={finish_reason} tool_calls={len(tool_calls)}",
                file=sys.stderr,
            )

        if not tool_calls:
            text = (msg.content or "").strip()
            faux = _parse_faux_tool_call(text)
            if faux and idx + 1 < turns:
                name, payload = faux
                if verbose:
                    print(f"[hunter]  -> faux {name}({json.dumps(payload)})", file=sys.stderr)
                if name == "finalize_hunt_report":
                    return {"status": "complete", "finalize_requested": True}
                result = dispatch_tool(runtime, name, payload)
                if verbose:
                    print(f"[hunter]     {json.dumps(result)[:300]}", file=sys.stderr)
                messages.append({"role": "assistant", "content": text})
                messages.append({
                    "role": "user",
                    "content": (
                        f"Tool {name} returned:\n{json.dumps(result, indent=2)}\n\n"
                        "Continue using tools until you have evidence, then call finalize_hunt_report."
                    ),
                })
                continue

            if idx == 0 and not runtime.findings:
                messages.append({"role": "assistant", "content": text or "(no response)"})
                messages.append({
                    "role": "user",
                    "content": (
                        "You must call tools before finishing. Start with discover_hosts on the "
                        f"mission target network ({runtime.mission.target_network}), then "
                        "port_scan_light on top ranked candidates and submit_finding for anything notable."
                    ),
                })
                continue

            try:
                start = text.index("{")
                end = text.rindex("}") + 1
                return json.loads(text[start:end])
            except Exception:
                return {"status": "complete", "summary": text}

        messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ],
        })

        for tc in msg.tool_calls:
            payload = json.loads(tc.function.arguments or "{}")
            if verbose:
                print(f"[hunter]  -> {tc.function.name}({json.dumps(payload)})", file=sys.stderr)
            if tc.function.name == "finalize_hunt_report":
                if not runtime.findings and idx + 1 < turns:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps({
                            "error": "No findings submitted yet. Call submit_finding for probed hosts first.",
                        }),
                    })
                    continue
                return {"status": "complete", "finalize_requested": True}
            result = dispatch_tool(runtime, tc.function.name, payload)
            if verbose:
                print(f"[hunter]     {json.dumps(result)[:300]}", file=sys.stderr)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result),
            })

    return {"status": "error", "error": f"Exceeded max_turns={turns} without finalizing report"}

