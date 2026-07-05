#!/usr/bin/env python3
"""
SentinelZero Analysis Agent — an LLM reasoning loop that acts as an embedded
security analyst, triaging scan findings with sensor context.

Usage:
  python agent.py --scan-id 42
  python agent.py --latest
  python agent.py --insight '{"type":"new_port","host":"172.16.0.10","details":{"port":8443}}'

Requires:
  OPENAI_API_KEY in environment (set in /etc/sentinel-agent/agent.env)

Optional env overrides:
  SENTINELZERO_URL   (default: http://172.16.0.254:5000)
  SENSOR_API_KEY     (default: hardcoded fallback from .env)
  OPENAI_MODEL       (default: gpt-4o-mini)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import requests
from openai import OpenAI

# ── Config ────────────────────────────────────────────────────────────────────

BASE_URL  = os.environ.get("SENTINELZERO_URL", "http://172.16.0.254:5000")
API_KEY   = os.environ.get(
    "SENSOR_API_KEY",
    "cddf70446cb633a16156a4ad746eb4473bfa8730507c933b4b5a507e17f62697",
)
MODEL     = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
ASSETS           = Path(__file__).parent / "context" / "assets.json"
NETWORK_TOPOLOGY = Path(__file__).parent / "context" / "network.json"

_http = requests.Session()
_http.headers["X-Sensor-Key"] = API_KEY


# ── LLM provider seam ──────────────────────────────────────────────────────────
# Single place to choose provider (OpenAI vs local Ollama) and model per role.
# Local mode is on whenever OLLAMA_BASE_URL is set (injected by the backend when
# the "Local AI" UI toggle is enabled). Ollama exposes an OpenAI-compatible API.

def _local_mode() -> bool:
    return bool(os.environ.get("OLLAMA_BASE_URL"))


def _make_client() -> OpenAI:
    if _local_mode():
        return OpenAI(
            base_url=os.environ["OLLAMA_BASE_URL"],
            api_key=os.environ.get("OLLAMA_API_KEY", "ollama"),
        )
    return OpenAI()  # reads OPENAI_API_KEY from environment


def _model_for(role: str = "default") -> str:
    """Resolve a model name by role. Roles: default, strong, embed.

    The 'strong' tier is used for escalations/synthesis (Phase 6); 'embed' for the
    incident memory store (Phase 7). Local mode reads OLLAMA_* overrides.
    """
    local = _local_mode()
    if role == "embed":
        return (
            os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")
            if local else
            os.environ.get("OPENAI_EMBED_MODEL", "text-embedding-3-small")
        )
    if role == "strong":
        return (
            os.environ.get("OLLAMA_MODEL_STRONG") or os.environ.get("OLLAMA_MODEL", "qwen2.5:14b")
            if local else
            os.environ.get("OPENAI_MODEL_STRONG", "gpt-4o")
        )
    # default
    return os.environ.get("OLLAMA_MODEL", "qwen2.5:14b") if local else MODEL


def _chat_create(client: OpenAI, *, model: str, messages: list, tools=None,
                 tool_choice=None, want_json: bool = False):
    """Wrap chat.completions.create with optional JSON-object structured output.

    When want_json is set we ask the provider for a guaranteed JSON object. Some
    local Ollama models reject response_format, so we transparently retry without
    it — the brace-slice parser at the call site still recovers the JSON.
    """
    kwargs: dict = {"model": model, "messages": messages}
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = tool_choice or "auto"
    if want_json:
        try:
            return client.chat.completions.create(
                response_format={"type": "json_object"}, **kwargs
            )
        except Exception as exc:  # provider doesn't support structured output
            print(f"[agent] response_format unsupported ({exc}); retrying plain",
                  file=sys.stderr)
    return client.chat.completions.create(**kwargs)

# ── Tool implementations ───────────────────────────────────────────────────────

def _get_scan_diff(scan_id: int) -> dict:
    r = _http.get(f"{BASE_URL}/api/scan-diff/{scan_id}", timeout=10)
    r.raise_for_status()
    return r.json()


def _get_process_timeline(ip: str, minutes: int = 120) -> dict:
    r = _http.get(
        f"{BASE_URL}/api/sensor/timeline/process-events",
        params={"ip": ip, "minutes": minutes},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def _get_network_context(source: str) -> dict:
    r = _http.get(f"{BASE_URL}/api/sensor/latest/{source}", timeout=10)
    r.raise_for_status()
    return r.json()


def _get_asset_context(ip: str) -> dict:
    try:
        assets = json.loads(ASSETS.read_text())
        entry = assets.get(ip)
        if entry:
            return entry
        for prefix, label in [
            ("172.16.0.", "lab network"),
            ("192.168.68.", "home network"),
            ("192.168.71.", "home network"),
        ]:
            if ip.startswith(prefix):
                if label == "home network":
                    return {
                        "note": (
                            "Home network host — often intentionally undocumented. "
                            "Compare to prior Home scan baselines, not the lab registry."
                        ),
                        "trust_zone": "home",
                    }
                return {
                    "note": f"Unknown host in {label} — not in asset registry",
                    "trust_zone": "unknown",
                }
        return {"note": "Unknown host — not in asset registry", "trust_zone": "unknown"}
    except FileNotFoundError:
        return {"note": "Asset registry not found", "trust_zone": "unknown"}


def _run_targeted_scan(ip: str) -> dict:
    try:
        result = subprocess.run(
            ["nmap", "-sV", "--open", "-T4", "-oX", "-", ip],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            return {"error": result.stderr.strip() or "nmap failed"}

        root = ET.fromstring(result.stdout)
        ports = []
        for port_el in root.findall(".//port"):
            state_el = port_el.find("state")
            if state_el is not None and state_el.get("state") == "open":
                svc = port_el.find("service")
                ports.append({
                    "port":     port_el.get("portid"),
                    "protocol": port_el.get("protocol"),
                    "service":  svc.get("name") if svc is not None else "unknown",
                    "version":  svc.get("version", "") if svc is not None else "",
                })
        host_el = root.find(".//host")
        status = "up" if host_el is not None and host_el.find("status") is not None else "unknown"
        return {"ip": ip, "status": status, "open_ports": ports}
    except subprocess.TimeoutExpired:
        return {"error": "nmap timed out after 120s"}
    except FileNotFoundError:
        return {"error": "nmap not found in PATH"}
    except ET.ParseError as e:
        return {"error": f"nmap XML parse error: {e}"}


def _get_sensor_agents() -> dict:
    r = _http.get(f"{BASE_URL}/api/sensor/agents", timeout=10)
    r.raise_for_status()
    return r.json()


def _get_network_topology() -> dict:
    try:
        return json.loads(NETWORK_TOPOLOGY.read_text())
    except FileNotFoundError:
        return {"error": "network.json not found"}
    except json.JSONDecodeError as e:
        return {"error": f"network.json parse error: {e}"}


def _get_port_history(ip: str, port: int, limit: int = 10) -> dict:
    r = _http.get(
        f"{BASE_URL}/api/port-history/{ip}/{port}",
        params={"limit": limit},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def _get_auth_events(ip: str, minutes: int = 120) -> dict:
    r = _http.get(
        f"{BASE_URL}/api/sensor/auth-events",
        params={"ip": ip, "minutes": minutes},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def _get_failed_services(ip: str, minutes: int = 120) -> dict:
    r = _http.get(
        f"{BASE_URL}/api/sensor/failed-services",
        params={"ip": ip, "minutes": minutes},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def _get_connections(ip: str, minutes: int = 120) -> dict:
    r = _http.get(
        f"{BASE_URL}/api/sensor/connections",
        params={"ip": ip, "minutes": minutes},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def _get_proxmox_context(ip: str) -> dict:
    r = _http.get(
        f"{BASE_URL}/api/sensor/proxmox",
        params={"ip": ip},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


# ── Incident memory (Phase 7) ───────────────────────────────────────────────────
# Embeddings are produced here (the agent owns the LLM client) and shipped to the
# backend store as plain vectors. The backend ranks; we never ask it to embed.

def _embed(text: str) -> list:
    """Embed text with the role-appropriate model (cloud or local). Returns [] on failure."""
    if not text:
        return []
    try:
        resp = _make_client().embeddings.create(model=_model_for("embed"), input=text)
        return resp.data[0].embedding
    except Exception as exc:
        print(f"[agent] embedding failed ({exc})", file=sys.stderr)
        return []


def _store_incident(ip, port, scan_id, summary, source="verdict") -> None:
    """Embed an incident narrative and persist it to the backend memory store."""
    vector = _embed(summary)
    if not vector:
        return
    try:
        _http.post(
            f"{BASE_URL}/api/incidents",
            json={
                "ip": ip, "port": port, "scan_id": scan_id,
                "summary": summary, "source": source,
                "vector": vector, "embedding_model": _model_for("embed"),
            },
            timeout=15,
        )
    except Exception as exc:
        print(f"[agent] store_incident failed ({exc})", file=sys.stderr)


def _find_similar_incidents(ip: str, port=None, days: int = 90) -> dict:
    """Recall prior incidents semantically similar to this host/port from the memory store."""
    query = f"host {ip}" + (f" port {port}" if port else "") + " security incident escalate"
    vector = _embed(query)
    if not vector:
        return {"matches": [], "error": "embedding unavailable"}
    r = _http.post(
        f"{BASE_URL}/api/incidents/search",
        json={"vector": vector, "days": days, "top_k": 5},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def _backfill_incidents(verbose: bool = False) -> dict:
    """One-off: embed already-escalated insights from history into the memory store."""
    try:
        r = _http.get(f"{BASE_URL}/api/insights/escalated", timeout=30)
        r.raise_for_status()
        items = r.json().get("insights") or r.json().get("escalated") or []
    except Exception as exc:
        return {"error": f"could not fetch escalated insights: {exc}"}

    stored = 0
    for it in items:
        details = it.get("details") or {}
        ip = it.get("host") or it.get("ip")
        port = details.get("port") or it.get("port")
        if not ip:
            continue
        narrative = " | ".join(filter(None, [
            it.get("type"), it.get("message"),
            it.get("verdict_summary"), it.get("verdict_evidence"),
        ]))
        summary = f"host {ip}" + (f" port {port}" if port else "") + f": {narrative}"
        if verbose:
            print(f"[agent:backfill] {ip}:{port}", file=sys.stderr)
        _store_incident(ip, port, it.get("scan_id"), summary, source="verdict")
        stored += 1
    return {"backfilled": stored, "seen": len(items)}


# ── Tool dispatch ──────────────────────────────────────────────────────────────

_TOOLS = {
    "get_scan_diff":        lambda i: _get_scan_diff(i["scan_id"]),
    "get_process_timeline": lambda i: _get_process_timeline(i["ip"], i.get("minutes", 120)),
    "get_network_context":  lambda i: _get_network_context(i["source"]),
    "get_asset_context":    lambda i: _get_asset_context(i["ip"]),
    "run_targeted_scan":    lambda i: _run_targeted_scan(i["ip"]),
    "get_sensor_agents":    lambda i: _get_sensor_agents(),
    "get_network_topology": lambda i: _get_network_topology(),
    "get_port_history":     lambda i: _get_port_history(i["ip"], i["port"], i.get("limit", 10)),
    "get_auth_events":      lambda i: _get_auth_events(i["ip"], i.get("minutes", 120)),
    "get_failed_services":  lambda i: _get_failed_services(i["ip"], i.get("minutes", 120)),
    "get_connections":      lambda i: _get_connections(i["ip"], i.get("minutes", 120)),
    "get_proxmox_context":  lambda i: _get_proxmox_context(i["ip"]),
    "find_similar_incidents": lambda i: _find_similar_incidents(i["ip"], i.get("port"), i.get("days", 90)),
}


def _dispatch_tool(name: str, inputs: dict) -> Any:
    fn = _TOOLS.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        return fn(inputs)
    except requests.HTTPError as e:
        return {"error": str(e), "status_code": e.response.status_code if e.response is not None else None}
    except Exception as e:
        return {"error": str(e)}


# ── Tool schemas (OpenAI function format) ──────────────────────────────────────

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_scan_diff",
            "description": (
                "Fetch the structured diff for a completed nmap scan vs. the previous scan "
                "of the same type. Returns new/removed hosts, new/closed ports, and "
                "new/resolved vulnerabilities with full service detail."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "scan_id": {"type": "integer", "description": "The scan ID to diff."}
                },
                "required": ["scan_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_process_timeline",
            "description": (
                "Get process start/stop events for a host over a time window, with the ports "
                "each process was listening on. Use this to correlate a new_port finding with "
                "the process that opened it. Only works for hosts with an endpoint sensor deployed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ip":      {"type": "string",  "description": "Host IP address."},
                    "minutes": {"type": "integer", "description": "Look-back window in minutes. Default 120."},
                },
                "required": ["ip"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_network_context",
            "description": (
                "Fetch the latest network telemetry from a specific sensor. "
                "Use 'pihole-lab' or 'pihole-home' for DNS context (top queries, top blocked, top clients). "
                "Use 'opnsense-ntopng' for flow/alert context (throughput, L7 protocols, engaged alerts)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "enum": ["pihole-lab", "pihole-home", "opnsense-ntopng", "opnsense"],
                        "description": (
                            "Sensor agent ID. Use 'pihole-lab'/'pihole-home' for DNS context. "
                            "Use 'opnsense-ntopng' for flow/L7/alert context. "
                            "Use 'opnsense' for ARP table, DHCP leases, gateway status, and IDS alerts."
                        ),
                    }
                },
                "required": ["source"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_asset_context",
            "description": (
                "Look up a host IP in the asset registry to get its role, expected ports, and "
                "trust zone. Always check this before concluding a finding is unexpected — "
                "RDP on a Windows VM is expected, RDP on a Proxmox node is alarming."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ip": {"type": "string", "description": "Host IP address."}
                },
                "required": ["ip"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_targeted_scan",
            "description": (
                "Run a focused nmap -sV scan on a single IP for real-time confirmation. "
                "Use only when you need to verify whether a suspicious port is still open "
                "right now, or need service version details not present in the diff."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ip": {"type": "string", "description": "IP address to scan."}
                },
                "required": ["ip"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sensor_agents",
            "description": (
                "List all registered sensor agents and their status (active/stale/offline). "
                "Use this to understand coverage gaps before deciding that missing process "
                "correlation is meaningful."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_network_topology",
            "description": (
                "Get static network topology context for this lab: subnets, trust zones, "
                "OPNsense interfaces, Proxmox cluster layout, routing, and known unknowns. "
                "Call once at the start of any investigation to understand the architecture."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_port_history",
            "description": (
                "Check how many of the last N scans included a specific port open on a host. "
                "Use this to distinguish a truly new port from a recurring one. A port seen "
                "in 8 of 10 past scans is probably expected even if absent from the asset registry."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ip":    {"type": "string",  "description": "Host IP address."},
                    "port":  {"type": "integer", "description": "Port number."},
                    "limit": {"type": "integer", "description": "Number of past scans to check. Default 10."},
                },
                "required": ["ip", "port"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_auth_events",
            "description": (
                "Get authentication events for a host: failed SSH logins (with source IP), "
                "sudo commands, and user add/delete changes, around the scan time. Use this to "
                "correlate a new port or new host with auth activity — e.g. a new listening port "
                "plus failed sshd logins from the same source is far more suspicious than a port alone."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ip":      {"type": "string",  "description": "Host IP address."},
                    "minutes": {"type": "integer", "description": "Look-back window in minutes. Default 120."},
                },
                "required": ["ip"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_failed_services",
            "description": (
                "List failed systemd units on a host around the scan time. Use this to explain "
                "a service_change or missing port — a unit that failed may have closed a port, "
                "and a newly failed security service is itself worth escalating."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ip":      {"type": "string",  "description": "Host IP address."},
                    "minutes": {"type": "integer", "description": "Look-back window in minutes. Default 120."},
                },
                "required": ["ip"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_connections",
            "description": (
                "Get ESTABLISHED and LISTEN socket connections for a host around the scan time, "
                "including remote peer addresses and owning process. Use this to check whether a "
                "new port has active sessions, or whether a host has unexpected outbound "
                "connections to foreign IPs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ip":      {"type": "string",  "description": "Host IP address."},
                    "minutes": {"type": "integer", "description": "Look-back window in minutes. Default 120."},
                },
                "required": ["ip"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_proxmox_context",
            "description": (
                "Get Proxmox node and guest VM context for a Proxmox host: node status, running "
                "guests, and per-VM state. Use this to judge whether a change on a Proxmox node "
                "reflects a VM migration (e.g. a guest moved yin→yang) rather than a new threat."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ip": {"type": "string", "description": "Proxmox host IP address."}
                },
                "required": ["ip"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_similar_incidents",
            "description": (
                "Search historical memory for past incidents (prior escalate verdicts, IDS "
                "alerts, analyst narratives) similar to a host/port finding. Use this to answer "
                "'have we seen this before?' — if the same host+port was escalated and later "
                "explained as benign, prefer that prior outcome over re-escalating."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ip": {"type": "string", "description": "Host IP of the current finding."},
                    "port": {"type": "integer", "description": "Port of the finding, if any."},
                    "days": {"type": "integer", "description": "Look-back window in days (default 90)."},
                },
                "required": ["ip"],
            },
        },
    },
]

# ── System prompt ──────────────────────────────────────────────────────────────

SYSTEM = """You are SentinelZero's embedded security analyst. You receive network scan findings \
and use sensor telemetry, process timelines, network flow data, and an asset registry to \
investigate and triage each finding.

## Investigation process
1. Call get_asset_context first for every host involved — understand what is expected.
2. For new_port findings on hosts with endpoint sensors, call get_process_timeline to correlate \
the port with the process that opened it.
3. For network-level context or when no endpoint sensor exists, call get_network_context \
(pihole-lab for lab DNS, opnsense-ntopng for flows).
4. If still uncertain, call run_targeted_scan to confirm current state.
5. Call get_sensor_agents when you need to know which hosts have coverage.

## Verdicts
- escalate: Something unexpected is happening. Port not in expected list, process unknown or \
suspicious, no benign explanation. Human should investigate now.
- explain: Finding is real but fully explained by sensor data. State the evidence.
- dismiss: Known expected artifact — expected port on expected host, or a transient port \
that has already closed.

## Network scope
- Payload includes target_network / network_label when present. Respect it: Home ≠ Lab registry rules.
- Home: many hosts are undocumented consumer/IoT devices — explain/dismiss "unknown in registry" findings.
- Lab: asset registry and endpoint sensors are expected for infrastructure VMs.

## Trust zones
- infrastructure: Proxmox nodes, firewall, DNS — new ports must match expected list or have clear process explanation
- management: SentinelZero itself — any unexpected port = escalate immediately
- lab: Controlled VMs — investigate but lower urgency
- user: Dev PC — SSH only expected; anything else needs explanation
- home / home-infrastructure: IoT and consumer devices normal; escalate only clear anomalies vs prior Home scans

## Output format
Respond ONLY with valid JSON — no prose before or after:
{
  "verdict": "escalate|explain|dismiss",
  "summary": "One-line summary for the alert feed (under 100 chars)",
  "findings": [
    {"finding": "...", "verdict": "escalate|explain|dismiss", "evidence": "..."}
  ],
  "reasoning": "Full analyst narrative — what you checked, what you found, why you concluded this"
}"""

INSIGHTS_SYSTEM = """\
You are SentinelZero's embedded security analyst operating in batch triage mode.

This is a one-shot automated job. Results are shown on a dashboard — there is no human in the
loop and you cannot ask questions. Write closed triage decisions only.

Your job: evaluate each insight from a completed network scan and assign exactly one verdict.

## Verdicts — three options, no others
- escalate  Port not in expected list with no process match, unregistered host, no benign explanation,
            or you are uncertain. When in doubt, escalate.
- explain   Finding is real but benign. Fully justified by asset context, sensor data, or port history.
- dismiss   Known noise — expected port on expected host, transient state already resolved, or a
            recurring pattern with no anomaly.

## Your output contract (mandatory)
Return ONLY a JSON object — no prose, no markdown fences, only JSON:
{
  "verdicts": [
    {
      "insight_id": "<exact ID from input — string>",
      "verdict": "escalate | explain | dismiss",
      "verdict_summary": "<one line, under 100 chars>",
      "verdict_evidence": "<what data drove this: role, expected ports, process name, port history, sensor gap>"
    }
  ]
}

## Rules
1. Return a verdict for EVERY insight_id in the input. Missing entries are treated as escalate.
2. verdict_evidence is mandatory — a verdict with no evidence will be rejected.
3. When uncertain about a specific host/port finding, choose escalate. Never omit a verdict or
   return "unknown" or "investigate".
4. No-sensor stance: you may still explain if the asset registry and expected ports justify it.
   Note "no endpoint sensor to corroborate" explicitly in verdict_evidence in that case.
5. Cross-correlate: if the same IP has multiple findings, reason about them together before
   finalising each individual verdict.
6. Tone: verdict_summary and verdict_evidence must be factual analyst notes. Never use phrasing
   that implies a reply is expected (e.g. "need clarification", "please confirm", "awaiting",
   "let me know", "unclear if legitimate").

## Baseline / aggregate insights (first scan of this type on this CIDR)
- details.is_baseline, details.host_count, or message containing "Network baseline established"
  means this is an inventory rollup, NOT sixteen separate unknown hosts.
- host field like "16 hosts" (not a dotted IPv4) with no per-IP diff → verdict explain.
- Summarise as establishing scan inventory; future scans will raise per-host new_host if needed.
- Do not escalate baseline rollups solely because asset registry lacks every IP yet.
- On **Home** (details.network_label == "Home"): registry_gap should be dismiss/explain — lab registry does not apply.
- On **Home**: sensor_gap for IoT is expected; only escalate registered home-infrastructure without coverage.

## Pre-enriched context (use first)
The payload may include `enrichment.host_context` (per-IP display names, DHCP/ARP hostnames,
manufacturer, open_port_summary, network segment) and `enrichment.hosts` (insight-linked stubs).
Each insight may have `details.host_context` and `details.asset_context` /
`details.sensor_context`. Use these before any tool calls — they are the scan's one-time
identity pass (registry + OPNsense DHCP/ARP + nmap OS/service + user labels).

## Investigation strategy (tools only for gaps)
1. Read `enrichment` and each insight's `details` before any tool call.
2. get_network_topology: optional once if you need subnet/trust-zone layout not in asset entries.
3. get_asset_context: ONLY for host IPs with no `details.asset_context`.
4. new_port: get_process_timeline ONLY if no `details.sensor_context.endpoint`; get_port_history
   if you need recurrence across past scans (not in pre-enrichment).
5. new_host: get_network_context(source="opnsense") ONLY if ARP/DHCP not in sensor_context.network.
6. get_sensor_agents: only if coverage is unclear after reading enrichment.

## Network scope (critical)
- Each scan targets ONE CIDR (Lab 172.16.0.0/22 or Home 192.168.68.0/22). Baselines and diffs are per network.
- **Home scans:** Consumer/IoT hosts are usually NOT in assets.json. Do NOT escalate solely because a home IP is
  "not in asset registry". Use prior Home scan inventory and OPNsense/ntopng for new devices.
- **Lab scans:** The asset registry is authoritative — unregistered lab hosts are higher concern.
- registry_gap / sensor_gap on Home are documentation/coverage backlogs, not lab-style incidents.

## Trust zones
- infrastructure (Proxmox, firewall, DNS): ports must match expected list exactly.
- management (SentinelZero): any unexpected port = immediate escalate.
- lab (VMs): lower urgency, but investigate unexpected ports.
- user (dev PC): SSH only expected; anything else needs a process explanation.
- home / home-infrastructure: admin and IoT ports are common; unknown home hosts → explain unless lab-like exposure.
- unknown on **lab** network: escalate unless ARP/DHCP clearly places it.\
"""

SYNTHESIS_SYSTEM = """\
You are SentinelZero's scan synthesis analyst. One-shot batch job — no questions to the operator.

Given ALL insights (with verdicts), scan diff, and enrichment, produce up to max_stories correlated \
"story" findings that group related atoms into actionable narratives.

Return ONLY JSON:
{
  "stories": [
    {
      "message": "One-line headline under 120 chars",
      "host": "primary IP or 'network'",
      "pattern": "multi_unexpected_port | new_host_no_coverage | vuln_plus_exposure | mgmt_anomaly | backlog | other",
      "priority": 85,
      "related_insight_ids": ["exact uuid strings from input"],
      "hosts": ["172.16.0.10"],
      "ports": [8006],
      "verdict": "escalate | explain | dismiss",
      "verdict_summary": "under 100 chars",
      "verdict_evidence": "what ties the related insights together"
    }
  ]
}

Rules:
1. 0 stories is valid if nothing meaningful to correlate.
2. Every related_insight_id MUST exist in the input insights list.
3. Do not duplicate a single atom — only create stories when 2+ insights relate OR one insight is critical context.
4. baseline_inventory is informational — on Home, do not build escalate stories from registry_gap alone.
5. Prefer lab registry_gap / multi-port clusters on Lab scans; Home stories should cite scan diff or new_port/new_host.
5. Never use conversational phrasing (no "need clarification", "please confirm").
6. verdict + verdict_summary + verdict_evidence are mandatory per story.\
"""

# ── Agent loop ─────────────────────────────────────────────────────────────────

def analyze(context: dict, verbose: bool = False) -> dict:
    """
    Run the analysis agent on a finding context dict.
    Returns a structured verdict dict: verdict, summary, findings, reasoning.
    """
    client = _make_client()

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM},
        {
            "role": "user",
            "content": (
                f"Analyze this security finding and produce a verdict:\n\n"
                f"```json\n{json.dumps(context, indent=2)}\n```"
            ),
        },
    ]

    max_turns = 10
    for turn in range(max_turns):
        resp = _chat_create(
            client,
            model=_model_for(),
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
            want_json=True,
        )

        msg = resp.choices[0].message
        finish_reason = resp.choices[0].finish_reason

        if verbose:
            print(
                f"[agent] turn={turn} finish_reason={finish_reason} "
                f"tool_calls={len(msg.tool_calls or [])}",
                file=sys.stderr,
            )

        if finish_reason == "stop" or not msg.tool_calls:
            text = (msg.content or "").strip()
            try:
                start = text.index("{")
                end   = text.rindex("}") + 1
                return json.loads(text[start:end])
            except (ValueError, json.JSONDecodeError) as exc:
                print(f"[agent] JSON parse failed ({exc}); raw={text[:300]!r}", file=sys.stderr)
            return {
                "verdict":  "unknown",
                "summary":  "Agent response could not be parsed as JSON",
                "findings": [],
                "reasoning": text,
            }

        # Append assistant turn (must include tool_calls for the API to accept it)
        messages.append({
            "role":    "assistant",
            "content": msg.content,
            "tool_calls": [
                {
                    "id":   tc.id,
                    "type": "function",
                    "function": {
                        "name":      tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ],
        })

        # Execute every tool call and append results
        for tc in msg.tool_calls:
            inputs = json.loads(tc.function.arguments)
            if verbose:
                print(f"[agent]  → {tc.function.name}({json.dumps(inputs)})", file=sys.stderr)
            result = _dispatch_tool(tc.function.name, inputs)
            if verbose:
                print(f"[agent]     {json.dumps(result)[:300]}", file=sys.stderr)
            messages.append({
                "role":         "tool",
                "tool_call_id": tc.id,
                "content":      json.dumps(result),
            })

    return {
        "verdict":   "unknown",
        "summary":   "Agent hit maximum tool-use rounds without concluding",
        "findings":  [],
        "reasoning": f"Exceeded {max_turns} tool-use rounds.",
    }


def _is_host_ip(value: str) -> bool:
    if not value or " " in value:
        return False
    parts = value.split(".")
    return len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)


def _host_has_asset(ip: str, insights: list, enrichment_hosts: dict) -> bool:
    if (enrichment_hosts.get(ip) or {}).get("asset"):
        return True
    for ins in insights:
        details = ins.get("details") or {}
        if (details.get("ip") or ins.get("host")) == ip and details.get("asset_context"):
            return True
    return False


def _select_insight_tools(insights: list, enrichment: dict) -> list:
    """Drop tools whose data is already in pre-enrichment."""
    skip: set[str] = set()
    enrichment_hosts = enrichment.get("hosts") or {}

    host_ips = set()
    for ins in insights:
        details = ins.get("details") or {}
        ip = details.get("ip") or ins.get("host", "")
        if _is_host_ip(ip):
            host_ips.add(ip)

    if host_ips and all(_host_has_asset(ip, insights, enrichment_hosts) for ip in host_ips):
        skip.add("get_asset_context")

    new_ports = [i for i in insights if i.get("type") == "new_port"]
    if new_ports and all(
        ((i.get("details") or {}).get("sensor_context") or {}).get("endpoint")
        for i in new_ports
    ):
        skip.add("get_process_timeline")

    if new_ports and all(
        ((i.get("details") or {}).get("sensor_context") or {}).get("network")
        for i in new_ports
    ):
        skip.add("get_network_context")

    # Endpoint security signals (auth failures, failed services, proxmox) are attached
    # as sensor_context.endpoint_security during enrichment. When every new_port insight
    # carries it, the auth/services/proxmox tools are redundant for this batch.
    if new_ports and all(
        ((i.get("details") or {}).get("sensor_context") or {}).get("endpoint_security")
        for i in new_ports
    ):
        skip.update({"get_auth_events", "get_failed_services", "get_proxmox_context"})

    if not skip:
        return TOOL_SCHEMAS
    return [t for t in TOOL_SCHEMAS if t["function"]["name"] not in skip]


def _run_insight_triage(client: OpenAI, insights: list, scan_id, diff: dict,
                        enrichment: dict, model: str, *, verbose: bool = False) -> dict:
    """Single triage pass over `insights` on a specific model. Returns {verdicts: [...]}."""
    tools = _select_insight_tools(insights, enrichment)
    skipped = {t["function"]["name"] for t in TOOL_SCHEMAS} - {t["function"]["name"] for t in tools}

    user_parts = [
        f"Triage {len(insights)} insight(s) from scan {scan_id}.",
        "One-shot batch — assign final verdicts only; do not ask the operator questions.",
    ]
    if enrichment.get("hosts"):
        user_parts.append(
            "Pre-enriched host context (use first — tools for these hosts were omitted: "
            + ", ".join(sorted(skipped)) + "):\n"
            f"```json\n{json.dumps(enrichment, indent=2)}\n```"
        )
    user_parts.extend([
        f"Insights:\n```json\n{json.dumps(insights, indent=2)}\n```",
        f"Scan diff context:\n```json\n{json.dumps(diff, indent=2)}\n```",
    ])

    messages: list[dict] = [
        {"role": "system", "content": INSIGHTS_SYSTEM},
        {"role": "user", "content": "\n\n".join(user_parts)},
    ]

    max_turns = 12
    for turn in range(max_turns):
        resp = _chat_create(
            client,
            model=model,
            messages=messages,
            tools=tools if tools else None,
            tool_choice="auto" if tools else None,
            want_json=True,
        )

        msg           = resp.choices[0].message
        finish_reason = resp.choices[0].finish_reason

        if verbose:
            print(
                f"[agent:insights] model={model} turn={turn} finish={finish_reason} "
                f"tool_calls={len(msg.tool_calls or [])}",
                file=sys.stderr,
            )

        if finish_reason == "stop" or not msg.tool_calls:
            text = (msg.content or "").strip()
            try:
                start  = text.index("{")
                end    = text.rindex("}") + 1
                result = json.loads(text[start:end])
                if "verdicts" in result:
                    return result
            except (ValueError, json.JSONDecodeError) as exc:
                print(f"[agent:insights] JSON parse failed ({exc}); raw={text[:300]!r}",
                      file=sys.stderr)
            return {
                "verdicts": [],
                "error": "Agent response could not be parsed as JSON",
                "raw": text[:500],
            }

        messages.append({
            "role":    "assistant",
            "content": msg.content,
            "tool_calls": [
                {
                    "id":   tc.id,
                    "type": "function",
                    "function": {
                        "name":      tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ],
        })

        for tc in msg.tool_calls:
            inputs = json.loads(tc.function.arguments)
            if verbose:
                print(f"[agent:insights]  → {tc.function.name}({json.dumps(inputs)})", file=sys.stderr)
            result = _dispatch_tool(tc.function.name, inputs)
            if verbose:
                print(f"[agent:insights]     {json.dumps(result)[:300]}", file=sys.stderr)
            messages.append({
                "role":         "tool",
                "tool_call_id": tc.id,
                "content":      json.dumps(result),
            })

    return {
        "verdicts": [],
        "error": f"Exceeded {max_turns} tool-use rounds without concluding",
    }


def analyze_insights(payload: dict, verbose: bool = False) -> dict:
    """
    Batch verdict mode. payload = {scan_id, insights: [...], diff: {...}, enrichment?: {...}}
    Returns {verdicts: [{insight_id, verdict, verdict_summary, verdict_evidence}]}

    Two-tier triage (Phase 6): the full batch runs on the cheap default model; any
    insight the cheap pass escalates is re-triaged on the stronger model for a second
    opinion, and the stronger verdict wins.
    """
    client = _make_client()
    insights   = payload.get("insights", [])
    scan_id    = payload.get("scan_id")
    diff       = payload.get("diff", {})
    enrichment = payload.get("enrichment") or {}

    result = _run_insight_triage(client, insights, scan_id, diff, enrichment,
                                 _model_for(), verbose=verbose)
    verdicts = result.get("verdicts") or []

    strong = _model_for("strong")
    if verdicts and strong != _model_for():
        escalated = {str(v.get("insight_id")) for v in verdicts if v.get("verdict") == "escalate"}
        sub = [i for i in insights if str(i.get("id")) in escalated]
        if sub:
            if verbose:
                print(f"[agent:insights] re-triaging {len(sub)} escalation(s) on {strong}",
                      file=sys.stderr)
            strong_result = _run_insight_triage(client, sub, scan_id, diff, enrichment,
                                                strong, verbose=verbose)
            override = {str(v.get("insight_id")): v for v in (strong_result.get("verdicts") or [])}
            if override:
                result["verdicts"] = [override.get(str(v.get("insight_id")), v) for v in verdicts]

    _remember_escalations(insights, result.get("verdicts") or [], scan_id, verbose=verbose)
    return result


def _remember_escalations(insights: list, verdicts: list, scan_id, *, verbose=False) -> None:
    """Persist each final escalate verdict to the incident memory store for future recall."""
    by_id = {str(i.get("id")): i for i in insights}
    for v in verdicts:
        if v.get("verdict") != "escalate":
            continue
        insight = by_id.get(str(v.get("insight_id"))) or {}
        details = insight.get("details") or {}
        ip = insight.get("host")
        port = details.get("port")
        if not ip:
            continue
        narrative = " | ".join(filter(None, [
            insight.get("type"), insight.get("message"),
            v.get("verdict_summary"), v.get("verdict_evidence"),
        ]))
        summary = f"host {ip}" + (f" port {port}" if port else "") + f": {narrative}"
        if verbose:
            print(f"[agent:insights] remembering escalation {ip}:{port}", file=sys.stderr)
        _store_incident(ip, port, scan_id, summary, source="verdict")


# Read-only correlation tools synthesis may use. run_targeted_scan is excluded —
# synthesis must not have side effects.
_SYNTHESIS_TOOL_NAMES = {
    "get_scan_diff",
    "get_port_history",
    "get_network_topology",
    "get_process_timeline",
    "get_asset_context",
    "get_auth_events",
    "get_failed_services",
    "get_connections",
    "get_proxmox_context",
    "find_similar_incidents",
}


def _synthesis_tools() -> list:
    return [t for t in TOOL_SCHEMAS if t["function"]["name"] in _SYNTHESIS_TOOL_NAMES]


def analyze_synthesis(payload: dict, verbose: bool = False) -> dict:
    """
    Correlated story mode. payload = {scan_id, insights, diff, enrichment, max_stories}
    Returns {stories: [...]}

    Runs a bounded tool loop so synthesis can verify cross-insight correlations
    (port history, topology, host timelines) rather than guessing from the digest alone.
    """
    client = _make_client()
    scan_id = payload.get("scan_id")
    insights = payload.get("insights", [])
    diff = payload.get("diff", {})
    enrichment = payload.get("enrichment") or {}
    max_stories = payload.get("max_stories", 5)

    user_content = "\n\n".join([
        f"Synthesize up to {max_stories} correlated stories for scan {scan_id}.",
        "One-shot batch — final stories only; do not ask questions.",
        "You may call read-only tools to verify correlations (e.g. get_port_history to "
        "confirm a port is genuinely new, get_network_topology for cluster/migration context). "
        "Use the enrichment digest first; only reach for tools to confirm a cross-insight story.",
        f"Insights ({len(insights)}):\n```json\n{json.dumps(insights, indent=2)}\n```",
        f"Diff:\n```json\n{json.dumps(diff, indent=2)}\n```",
        f"Enrichment:\n```json\n{json.dumps(enrichment, indent=2)}\n```",
    ])

    tools = _synthesis_tools()
    messages: list[dict] = [
        {"role": "system", "content": SYNTHESIS_SYSTEM},
        {"role": "user", "content": user_content},
    ]

    model = _model_for("strong")
    max_turns = 4
    for turn in range(max_turns):
        resp = _chat_create(
            client,
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            want_json=True,
        )
        msg = resp.choices[0].message
        finish_reason = resp.choices[0].finish_reason

        if verbose:
            print(
                f"[agent:synthesis] model={model} turn={turn} finish={finish_reason} "
                f"tool_calls={len(msg.tool_calls or [])}",
                file=sys.stderr,
            )

        if finish_reason == "stop" or not msg.tool_calls:
            text = (msg.content or "").strip()
            try:
                start = text.index("{")
                end = text.rindex("}") + 1
                result = json.loads(text[start:end])
                if "stories" in result:
                    return result
            except (ValueError, json.JSONDecodeError) as exc:
                print(f"[agent:synthesis] JSON parse failed ({exc}); raw={text[:300]!r}",
                      file=sys.stderr)
            return {"stories": [], "error": "Could not parse synthesis JSON", "raw": text[:500]}

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
            inputs = json.loads(tc.function.arguments)
            if verbose:
                print(f"[agent:synthesis]  → {tc.function.name}({json.dumps(inputs)})", file=sys.stderr)
            result = _dispatch_tool(tc.function.name, inputs)
            if verbose:
                print(f"[agent:synthesis]     {json.dumps(result)[:300]}", file=sys.stderr)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result),
            })

    return {"stories": [], "error": f"Exceeded {max_turns} tool-use rounds without concluding"}


def _post_scan_analyst(scan_id: int, result: dict, source: str = "timer") -> None:
    """Persist scan-level narrative to SentinelZero backend."""
    body = {
        "source": source,
        "verdict": result.get("verdict"),
        "summary": result.get("summary"),
        "findings": result.get("findings"),
        "reasoning": result.get("reasoning"),
    }
    try:
        r = _http.post(
            f"{BASE_URL}/api/scans/{scan_id}/analysis/scan-analyst",
            json=body,
            timeout=30,
        )
        r.raise_for_status()
    except Exception as exc:
        print(f"[agent] scan-analyst POST failed for scan {scan_id}: {exc}", file=sys.stderr)


# ── CLI ────────────────────────────────────────────────────────────────────────

def _fetch_scan_analysis_context(scan_id: int) -> dict:
    """Load scan scope, diff, and insight summary for scan-level analyst."""
    scan_r = _http.get(f"{BASE_URL}/api/scan/{scan_id}", timeout=15)
    scan_r.raise_for_status()
    scan = scan_r.json()
    diff = _get_scan_diff(scan_id)
    insights: list = []
    try:
        ins_r = _http.get(f"{BASE_URL}/api/insights/scan/{scan_id}", timeout=15)
        if ins_r.status_code == 200:
            body = ins_r.json()
            insights = body if isinstance(body, list) else body.get("insights", [])
    except Exception:
        pass
    net = scan.get("target_network")
    label = scan.get("network_label") or ""
    hosts = scan.get("hosts") or []
    scope_note = (
        "Home network scan — compare hosts to prior Home baselines; lab asset registry "
        "is not the coverage standard for consumer/IoT devices."
        if label == "Home" or (net and "192.168" in str(net))
        else "Lab network scan — asset registry and endpoint sensors are authoritative for triage."
    )
    host_context = scan.get("host_context") or {}
    host_lines = []
    for ip, h in (host_context.get("hosts") or {}).items():
        host_lines.append(f"{ip}: {h.get('summary_line', h.get('display_name', ip))}")

    return {
        "type": "scan_analysis",
        "scan_id": scan_id,
        "scan_type": scan.get("scan_type"),
        "target_network": net,
        "network_label": label,
        "scope_display": scan.get("scope_display"),
        "host_count": len(hosts),
        "scope_note": scope_note,
        "network": host_context.get("network"),
        "host_context_lines": host_lines[:50],
        "host_context": {
            ip: {
                "display_name": h.get("display_name"),
                "summary_line": h.get("summary_line"),
                "role": h.get("role"),
                "dhcp_hostname": (h.get("dhcp") or {}).get("hostname"),
                "manufacturer": h.get("manufacturer"),
                "open_port_summary": h.get("open_port_summary"),
                "user_label": h.get("user_label"),
            }
            for ip, h in list((host_context.get("hosts") or {}).items())[:50]
        },
        "diff": diff,
        "insights_summary": [
            {
                "type": i.get("type"),
                "message": i.get("message"),
                "verdict": i.get("verdict"),
                "host": i.get("host"),
                "network_label": (i.get("details") or {}).get("network_label"),
            }
            for i in insights[:40]
        ],
    }


def _get_latest_scan_id() -> int:
    r = _http.get(f"{BASE_URL}/api/scans", timeout=10)
    r.raise_for_status()
    data  = r.json()
    scans = data if isinstance(data, list) else data.get("scans", [])
    for s in scans:
        if s.get("status") == "complete":
            return s["id"]
    raise SystemExit("No completed scans found.")


def main() -> None:
    p = argparse.ArgumentParser(description="SentinelZero Analysis Agent")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--scan-id",  type=int, metavar="ID",  help="Analyze a specific scan ID")
    g.add_argument("--latest",   action="store_true",     help="Analyze the most recent completed scan")
    g.add_argument("--insight",  metavar="JSON",          help="Analyze a specific insight as a JSON string")
    g.add_argument("--insights", metavar="JSON",          help="Batch verdict mode: JSON payload {scan_id, insights, diff}")
    g.add_argument("--synthesize", metavar="JSON",       help="Synthesis mode: JSON payload {scan_id, insights, diff, enrichment}")
    g.add_argument("--backfill-incidents", action="store_true", help="Embed past escalated insights into the incident memory store")
    p.add_argument("--verbose", "-v", action="store_true", help="Print tool calls to stderr")
    p.add_argument(
        "--no-post",
        action="store_true",
        help="Do not POST scan analyst result to backend (stdout only)",
    )
    args = p.parse_args()

    if not _local_mode() and not os.environ.get("OPENAI_API_KEY"):
        print("error: OPENAI_API_KEY is not set (check /etc/sentinel-agent/agent.env)", file=sys.stderr)
        sys.exit(1)

    if args.backfill_incidents:
        print(json.dumps(_backfill_incidents(verbose=args.verbose), indent=2))
        return

    if args.insights:
        payload = json.loads(args.insights)
        print(json.dumps(analyze_insights(payload, verbose=args.verbose), indent=2))
        return

    if args.synthesize:
        payload = json.loads(args.synthesize)
        print(json.dumps(analyze_synthesis(payload, verbose=args.verbose), indent=2))
        return

    if args.insight:
        context = json.loads(args.insight)
        scan_id = context.get("scan_id")
        result = analyze(context, verbose=args.verbose)
        print(json.dumps(result, indent=2))
        if scan_id and not args.no_post:
            _post_scan_analyst(int(scan_id), result, source="cli")
        return

    if args.latest:
        scan_id = _get_latest_scan_id()
        source = "timer"
    else:
        scan_id = args.scan_id
        source = "cli"

    context = _fetch_scan_analysis_context(scan_id)
    result = analyze(context, verbose=args.verbose)
    print(json.dumps(result, indent=2))
    if not args.no_post:
        _post_scan_analyst(scan_id, result, source=source)


if __name__ == "__main__":
    main()
