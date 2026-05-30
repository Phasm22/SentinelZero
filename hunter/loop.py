from __future__ import annotations

import json
import sys
from typing import Any

from agent import _chat_create, _make_client, _model_for

from .tools import HunterRuntime, dispatch_tool, tool_schemas_for_runtime


SYSTEM = """You are SentinelZero Hunter.

Role:
- You are a red-team style network hunter that gathers evidence and proposes scan handoffs.
- You must never output blue-team verdicts (no escalate/explain/dismiss).
- Gather facts, submit findings, and finalize a report.

Workflow:
1. Review mission + seed + ranked candidates.
2. Use discover_hosts and port_scan_light only within scope.
2b. Use port_scan_iot only when assess profile is active and the host is flagged.
3. Add structured finding objects via submit_finding.
4. Call finalize_hunt_report when done.

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
            want_json=True,
        )
        msg = resp.choices[0].message
        finish_reason = resp.choices[0].finish_reason

        if verbose:
            print(
                f"[hunter] turn={idx} finish={finish_reason} tool_calls={len(msg.tool_calls or [])}",
                file=sys.stderr,
            )

        if finish_reason == "stop" or not msg.tool_calls:
            text = (msg.content or "").strip()
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

