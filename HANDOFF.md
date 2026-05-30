# SentinelZero — Project Handoff

**Last updated:** 2026-05-30
**Status:** 8 sensors active (incl. OPNsense REST), backend + frontend on 3173/5000, verdict pipeline live.
LLM pipeline upgraded to full-telemetry analyst (Phases 1–7) with working local Ollama mode.
Scan/sensor discrepancy fixes committed (`f1d339e`). **Next initiative:** Hunter agent — see
`docs/HUNTER-PREPLAN.md`.

### Live stack (2026-05-25)

| Layer | Detail |
|-------|--------|
| Network sensors (60s, on SentinelZero) | `sentinel-ntopng`, `sentinel-pihole@lab`, `sentinel-pihole@home`, `sentinel-opnsense` |
| Endpoint sensors (60s, remote hosts) | proxBig, yin, yang, palindrome, pihole-home (192.168.71.25) |
| Analysis agent | `sentinel-agent.timer` — first run 5 min after boot, then every 30 min (`--latest`) |
| Verdicts | Post-scan daemon → `agent.py --insights`; patches `insights_json`; emits `insights.verdicts_ready` |
| Context | `~/agent/context/assets.json` (17 hosts), `network.json` |
| Frontend | Vite on **3173** (proxies `/api`, `/socket.io` → 5000); InsightsCard shows verdict badges + evidence |

**Note:** `sentinelzero-frontend.service` in `/etc/systemd` may still pass `--port 5173` — use repo unit `sentinelzero-frontend.service` (3173) after `sudo cp` + `daemon-reload`.

---

## 2026-05-30 Session — LLM pipeline overhaul + local mode + scanner/UI fixes

Two repos touched: **`/home/sentinel/SentinelZero`** (this git repo, commits pushed) and the **analysis
agent** `/home/sentinel/agent/agent.py` (separate codebase, venv at `/home/sentinel/agent/.venv` — sensor
reporter changes on disk, not yet versioned in git).

### LLM pipeline: Phases 1–7 (plan: `~/.claude/plans/you-ve-built-a-strong-agile-zebra.md`)

| Phase | What | Key locations |
|-------|------|---------------|
| 1 | Provider seam + local-mode toggle | `agent.py` `_make_client()`/`_model_for(role)`; `config_service.py` (new); `agent_service._agent_env()`; `Settings.jsx` "Local AI" card |
| 2 | Time-windowed sensor queries (anchored to `scan.completed_at` ±15 min) | `sensor_service.get_telemetry_window()`; `insights.py` |
| 3 | Endpoint sensor tools (auth/services/connections/proxmox) exposed to LLM | `sensor_service.py`, `sensor_routes.py`, `agent.py` tools + schemas |
| 4 | Inject `network.json` known_unknowns + cluster notes into every payload | `host_context.institutional_memory_for_hosts()`; `agent_service.build_enrichment_digest` |
| 5 | Synthesis given read-only tools (was zero-tool) | `agent.py` `analyze_synthesis` bounded tool loop (`max_turns=4`) |
| 6 | Structured JSON outputs + model tiering | `agent.py` `_chat_create()` (response_format + fallback), `_run_insight_triage()` (cheap pass → strong re-triage of escalations) |
| 7 | Historical memory (embeddings + `find_similar_incidents`) | new `incident.py`, `incident_memory.py`, `incident_routes.py`; agent `_embed`/`_store_incident`/`_find_similar_incidents`, `--backfill-incidents` |

**New files:** `backend/src/models/incident.py`, `backend/src/services/incident_memory.py`,
`backend/src/routes/incident_routes.py`, `backend/src/services/config_service.py`,
`backend/tests/unit/test_incident_memory.py`.

### Local Ollama mode — VALIDATED
`192.168.68.202:11434` reachable (earlier block was a **ufw** rule). Verified end-to-end via the
agent's own code: embeddings (`nomic-embed-text`, 768-dim), JSON-mode chat and tool-calling
(`qwen2.5:14b`). **Use `qwen2.5:14b` for all tool passes + `nomic-embed-text` for embeddings; leave
`OLLAMA_MODEL_STRONG` unset** (phi4/llama3.1 tool-calling is unreliable; the strong-tier rerun then
no-ops harmlessly). Toggle: Settings → Local AI → `network_settings.json`
(`local_mode_enabled`/`ollama_base_url`/`ollama_model`).

### Scanner adapter fix — `backend/src/services/scanner.py`
Host-discovery probes adapt to on-link vs routed targets. `_target_is_on_link(cidr)` inspects local
interface CIDRs (ignores `/32` VIPs like `dummy0 192.168.68.254/32`). On-link (Lab) keeps ARP
(`-PR`)/netmask (`-PM`); routed (Home) drops them (can't cross the gateway) and leans on TCP
SYN/ACK + routable ICMP. Frees ~1000 wasted ARP rounds per Home /22 sweep. Each scan logs its mode.

### Frontend network selector — `Settings.jsx`
"Default Target Network" dropdown now lists only **Lab — 172.16.0.0/22**, **Home —
192.168.68.0/22**, and **Custom Network…**. Removed auto-detected interface rows (the `/32
(-1 hosts)` junk) + generic "Common Networks" presets and the dead `networkInterfaces` fetch.
Off-list saved values open pre-filled in the manual field.

### Host / systemd
Installed `/etc/sudoers.d/sentinel-systemctl` (NOPASSWD, scoped to `sentinelzero*.service` +
`sentinel-agent`) → the `sentinel` account can restart units unattended. Backend restarted onto new
code; `incident_embedding` table auto-created on boot via `db.create_all()`.

### Test status
Backend **31 unit + 53 integration pass** (incl. new `test_incident_memory.py`). Agent validated via
mocks + live Ollama. **Pre-existing flaky:** `test_scan_runtime.py::test_run_nmap_scan_retries_in_degraded_mode_without_new_scan`
(fixture state-bleed under suite ordering; fails identically on untouched baseline). Run focused
tests with `-o addopts=""` to bypass the 38% coverage gate.

### Open items (LLM session)
1. `network_settings.json` `default_target_network` may still be generic `192.168.1.0/24` — set to
   `172.16.0.0/22` (Lab). Pending user confirm.
2. Box is **single-homed** (only `enp6s18` on Lab). Home is scanned routed via OPNsense; Home scan
   depth + Ollama both ride the same inter-VLAN rules. Real fix = a Home-side NIC/VLAN.
3. Dead but harmless: backend `GET /api/network-interfaces` + `api.js getNetworkInterfaces` now have
   no callers.
4. Version the **agent repo** (`/home/sentinel/agent/`) — sensor reporter + wait-for-backend changes
   live on disk only.

---

## 2026-05-30 Session — Scan/sensor discrepancy + Hunter planning

### Host count investigation (Lab)

| Source | Count | Notes |
|--------|-------|-------|
| Scan #1 (Full TCP, pre-discovery ON) | **9** | Pre-discovery XML at 00:47 also had 9 |
| Live `nmap -sn` on lab /22 | **10** | Included `172.16.0.100` (winvm) |
| Asset registry | **12** lab IPs | `.106`, `.107` often offline by design |
| Discovery Scan #2 (after fixes) | **10** | winvm present |

**Root cause:** With `pre_discovery_enabled: true`, Full TCP only scanned the pre-discovered host list.
winvm was likely **down during pre-discovery** (~00:47); several hosts rebooted ~00:49. Not an ARP bug
on lab (on-link ARP is correct there).

**Shipped in `f1d339e`:**

- `pre_discovery_enabled: false` in `network_settings.json`
- RDP **3389** added to host-discovery probes (`scanner.py`)
- **`inventory_gap`** insight + `hosts_for_inventory_gap()` in `asset_registry.py` / `insights.py`
- Sensor **auto-register on ingest** (`_upsert_sensor_agent` in `sensor_routes.py`)

**Agent-side (not in SentinelZero git):** shared `sensor_reporter.py` (retry register on 404,
periodic re-register), `wait-for-backend.sh`, systemd `ExecStartPre` on network sensor units.

### Sensor gap (ingest 404)

After DB reset, `sensor_agent` was empty while sensors still ran → ingest **404 "agent not registered"**
and dropped telemetry. Backend auto-register + reporter fixes restored **8 sensors up** after restarts.

### Home / IoT scan notes

- **No ARP on Home scans is intentional** — lab is not L2-adjacent to `192.168.68.0/22`.
- IoT pain points: `-Pn` full /22 sweeps, discovery probes missing IoT UDP ports, XML parser keeps
  `open` not `open|filtered`, OPNsense LAN→WAN rules for routed scans from `172.16.0.198` / `.254`.

### OPNsense logging cheat sheet (during scans)

| Traffic | What to watch |
|---------|-----------------|
| Lab east-west | Often **no firewall log** (L2); IDS on `vtnet0` for SYN sweeps to `.1` |
| Home (routed from lab) | LAN **in** + WAN **out** from scanner IPs to `192.168.68.0/22` |
| SSH scan noise | Suricata SID **2003068** — whitelist scanner IPs (`172.16.0.198`) |

### Scan #1 LLM pipeline note

2 insights (`baseline_inventory`, `sensor_gap` escalate); verdict agent skipped auto-verdicts;
**scan_analyst timeout** (180s) on that run.

---

## What's Next — Hunter Agent

**Pre-plan (full context):** [`docs/HUNTER-PREPLAN.md`](docs/HUNTER-PREPLAN.md)

Red-team-style **hunter** feeds blue SentinelZero — does **not** replace `agent.py` verdicts.

| Component | Host | Role |
|-----------|------|------|
| Ollama | **palindrome** `192.168.68.202:11434` | LLM only (GPU, ufw open to lab) |
| Hunter controller + lab nmap | **sentinelzero** | Mission loop, local probes on `172.16.0.0/22` |
| Home probes | **SSH → ubuntu-server** `192.168.71.30` | Wired home executor **from day one** — not palindrome Wi‑Fi |

**Why:** palindrome Wi‑Fi is fine for Ollama but bad for authoritative discovery (flapping hosts, double-hop).
Mythos-inspired scaffold: mission YAML → seed (ARP/DHCP/DNS/assets/scan diff) → rank → parallel workers
→ verifier → JSON report + optional `POST /api/scan` → existing blue pipeline on scan complete.

**Not built yet.** Phase 1 = seed + tools + loop + handoff file + SSH home executor.

---

## What's Brewing (Completed / Reference)

### 1. InsightsGenerator Enrichment — **done** (`insights.py`, `sensor_service.py`, `asset_registry.py`)
- `new_port` / `new_host`: `details.asset_context` from `~/agent/context/assets.json` (`SENTINEL_ASSETS_PATH`)
- `new_port`: `details.sensor_context.endpoint` via process timeline + latest snapshot; `sensor_context.network` from pihole + ntopng + OPNsense IDS for the host's segment
- Message rewritten when a process match is found (e.g. `proxmox-backup-proxy (PID 9999) started 47 min before scan`)
- Frontend InsightsCard expand row shows Asset + Sensor context blocks

### 2. Asset Registry — **done** (`~/agent/context/assets.json`, 17 hosts)
Backend reads the same file as `agent/agent.py`. Keep both in sync when adding hosts.

### 3. LLM Reasoning Loop — **done** (verdicts + pre-enriched batch)
`agent_service` sends `enrichment` digest with each `--insights` payload; `agent.py` uses it first and omits redundant tools (`get_asset_context`, `get_process_timeline`, `get_network_context`) when data is already present.

---

## Infrastructure Inventory

| Host | IP | Role | Sensor Agent |
|------|----|------|-------------|
| sentinelzero | 172.16.0.254 | SentinelZero host | — (runs the app) |
| proxBig.prox | 172.16.0.10 | Proxmox hypervisor (primary) | `proxbig` |
| yin.prox | 172.16.0.11 | Proxmox node | `yin` |
| yang.prox | 172.16.0.12 | Proxmox node | `yang` |
| piholelab | 172.16.0.13 | DNS / Pi-hole (lab network) | `pihole-lab` |
| OPNsense | 172.16.0.1 | Firewall / gateway + ntopng | `opnsense-ntopng` |
| code-server.prox | 172.16.0.106 | Code server VM | not yet deployed |
| palindrome | 192.168.68.202 | Dev PC (Ubuntu 24.04, Wi‑Fi) | `palindrome` |
| pihole-home | 192.168.71.25 | DNS / Pi-hole (home network) | `pihole-home` |
| ubuntu-server | 192.168.71.30 | Wired home Linux (hunter SSH executor) | — |
| winvm.prox | 172.16.0.100 | Windows lab VM | not deployed (Windows) |
| Gateway | 172.16.0.1 | Network gateway | — |

Networks: `172.16.0.0/22` (lab), `192.168.68.0/22` (home, incl. `192.168.71.0/24` segment)

Scanner sources: `172.16.0.198` (DHCP), `172.16.0.254` (dummy0 VIP on sentinelzero)

---

## Sensor Architecture

Two sensor categories — use tags to route context in the LLM loop.

### Endpoint Sensors (`category:endpoint`)
Run **on** the target host. Collect process→port correlation, auth events, connections, services, systemd state. Deployed via `agent/sensor/deploy.sh`.

| Agent | Role | Tags |
|-------|------|------|
| proxbig | proxmox-node | `[]` ← add `category:endpoint` when touching configs |
| yin | proxmox-node | `[]` |
| yang | proxmox-node | `[]` |
| palindrome | linux-pc | `["pc"]` |

> Note: endpoint sensors are missing `category:endpoint` tag — add it when next editing configs on those hosts.

### Network Sensors (`category:network`)
Run **on sentinelzero**, poll external APIs. Ship network-layer context.

| Agent | Source | Tags | What it collects |
|-------|--------|------|-----------------|
| opnsense-ntopng | ntopng at 172.16.0.1:3000 | `category:network, source:ntopng` | throughput, flows, TCP health, L7 protocol breakdown, host scores, engaged alerts |
| pihole-lab | Pi-hole at 172.16.0.13 | `category:network, source:pihole, network:lab` | DNS summary, top queried/blocked domains, top clients |
| pihole-home | Pi-hole at 192.168.71.25 | `category:network, source:pihole, network:home` | same, home network segment |

**LLM routing logic (future):** `category:endpoint` → process/auth context for a specific host. `category:network` → what was happening on the wire/DNS at that time. `network:lab` vs `network:home` → keep segments distinct.

---

## What Was Built (This Session)

### Endpoint Sensor Daemon — `/home/sentinel/agent/sensor/`
Push-based daemon that runs on each Linux host. Collectors: system (psutil), processes (with pid→port map), connections, auth.log, systemd services. Role modules loaded by config: `proxmox.py` uses `pvesh` CLI.

`deploy.sh` rsync + venv + systemd installs to remote hosts as root. Strips `user@` prefix automatically so both `192.168.68.202` and `root@192.168.68.202` work.

### ntopng Sensor — `/home/sentinel/agent/network/ntopng_sensor.py`
Polls ntopng REST v2 API on OPNsense. Session-based auth (POSTs to `/authorize.html`, maintains cookie — same flow as browser). Auto re-authenticates on session expiry.

**Auth:** `admin` / `spacex` (stored in `config.yaml`). ntopng is on HTTPS with self-signed cert (`verify_ssl: false`).

Collectors: `interface_stats`, `l7_stats` (top protocols by flow count), `l4_counters`, `alerts` (engaged), `active_hosts` (flagged by score).

### Pi-hole Sensors — `/home/sentinel/agent/network/pihole_sensor.py`
Polls Pi-hole v6 REST API. Auth: POST `{"password": ...}` to `/api/auth`, get SID, send as `X-FTL-SID` header. Session validity 1800s, auto-renewed by polling cadence.

**Auth:** `spacex` on both. HTTPS with self-signed cert.

Collectors: `summary` (query counts, % blocked, type breakdown), `top_domains`, `top_blocked`, `top_clients`.

One script, two configs (`config-pihole-lab.yaml`, `config-pihole-home.yaml`), systemd template `sentinel-pihole@.service`.

### Backend Sensor API — unchanged from last session
All 8 endpoints live. DB tables `sensor_agent` + `sensor_telemetry` in production SQLite.

---

## Sensor API Reference

All prefixed `/api/sensor/` on the backend at `http://172.16.0.254:5000`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/agents` | All agents with computed status |
| GET | `/agents/<id>` | Single agent + last 10 telemetry summaries |
| GET | `/latest/<id>` | Full last telemetry payload (all collectors) |
| GET | `/timeline?ip=X&minutes=N` | History window, optional `collectors=c1,c2` filter |
| GET | `/timeline/process-events?ip=X&minutes=N` | Process start/stop events with port correlation |
| POST | `/register` | Enroll agent (idempotent) |
| POST | `/ingest` | Receive telemetry |
| DELETE | `/agents/<id>` | Remove agent + all telemetry |

---

## Service Management

```bash
# SentinelZero backend
sudo systemctl status sentinelzero
sudo systemctl restart sentinelzero
sudo journalctl -u sentinelzero -f

# Network sensors (on sentinelzero)
sudo systemctl status sentinel-ntopng
sudo systemctl status sentinel-pihole@lab
sudo systemctl status sentinel-pihole@home
sudo journalctl -u sentinel-ntopng -f
sudo journalctl -u sentinel-pihole@lab -f

# Endpoint sensors (SSH to each host)
ssh root@proxBig.prox 'systemctl status sentinel-sensor'
ssh root@yin.prox     'systemctl status sentinel-sensor'
ssh root@yang.prox    'systemctl status sentinel-sensor'
ssh root@192.168.68.202 'systemctl status sentinel-sensor'

# Quick agent health check from sentinelzero
curl -s http://localhost:5000/api/sensor/agents | python3 -m json.tool
```

---

## Key File Locations

| Purpose | Path |
|---------|------|
| Endpoint sensor daemon | `/home/sentinel/agent/sensor/` |
| ntopng sensor | `/home/sentinel/agent/network/ntopng_sensor.py` |
| Pi-hole sensor | `/home/sentinel/agent/network/pihole_sensor.py` |
| ntopng config | `/home/sentinel/agent/network/config.yaml` |
| Pi-hole configs | `/home/sentinel/agent/network/config-pihole-lab.yaml` / `config-pihole-home.yaml` |
| Systemd units (network) | `/etc/systemd/system/sentinel-ntopng.service`, `sentinel-pihole@.service` |
| Endpoint sensor config (remote) | `/etc/sentinel-sensor/config.yaml` on each host |
| Backend .env (API keys) | `/home/sentinel/SentinelZero/backend/.env` |
| Sensor models | `backend/src/models/sensor.py` |
| Sensor query helpers | `backend/src/services/sensor_service.py` |
| Sensor API routes | `backend/src/routes/sensor_routes.py` |
| InsightsGenerator | `backend/src/services/insights.py` |
| Asset registry / inventory gap | `backend/src/services/asset_registry.py` |
| Scanner (on-link vs routed probes) | `backend/src/services/scanner.py` |
| Hunter pre-plan | `docs/HUNTER-PREPLAN.md` |
| Blue analysis agent | `/home/sentinel/agent/agent.py` |
| Agent context | `/home/sentinel/agent/context/assets.json`, `network.json` |
| WhatsUp infra list (asset registry seed) | `backend/src/services/whats_up.py` |

---

## Credentials Reference

| Service | URL | User | Password / Key |
|---------|-----|------|----------------|
| ntopng | https://172.16.0.1:3000 | admin | spacex |
| Pi-hole lab | https://172.16.0.13 | — | spacex |
| Pi-hole home | https://192.168.71.25 | — | spacex |
| SentinelZero sensor API | http://172.16.0.254:5000 | — | `SENSOR_API_KEY` in `backend/.env` |
