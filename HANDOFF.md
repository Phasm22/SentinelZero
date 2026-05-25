# SentinelZero — Project Handoff

**Last updated:** 2026-05-25
**Status:** 8 sensors active (incl. OPNsense REST), backend + frontend on 3173/5000, verdict pipeline live.

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

## What's Brewing (Do This Next)

### 1. InsightsGenerator Enrichment — `backend/src/services/insights.py`
This is the critical path. Sensor data is collecting but not yet used in analysis.

**What to do:** When a `new_port` insight is generated from an nmap diff, enrich it:
- For **endpoint agents** (proxmox-nodes, linux-*): call `sensor_service.get_process_events(db, agent_id, minutes=120)` and match the process whose `listening_ports` contains the detected port. Add `sensor_context: {process_name, pid, started_at, minutes_before_scan}`.
- For **network agents**: call `/api/sensor/latest/<agent_id>` and pull `top_blocked` from pihole and `alerted_flows` from ntopng for the same time window. Add as context.

**Result:** "New port 8443 detected" → "proxmox-backup-proxy (PID 9999) started 47 min before scan"

### 2. Asset Registry — `agent/context/assets.json`
A JSON file mapping each known IP to role, expected ports, and trust zone. Without it the LLM can't distinguish "RDP on the Windows VM (expected)" from "RDP on a Proxmox node (alarming)."

Seed from `backend/src/services/whats_up.py` — the infra list is already there. Add `expected_ports` and `trust_zone` fields per host.

### 3. LLM Reasoning Loop — `agent/agent.py` (partially done)
`agent_service.run_verdicts_for_scan` calls `agent.py --insights` with batch payload. Agent tools: asset registry, process timeline, port history, OPNsense ARP/DHCP, network topology. Auto-dismisses `port_closed` / `scan_performance` without LLM.

Remaining: enrich **generation** (step 1) so actionable insights ship sensor context before the agent runs.

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
| palindrome | 192.168.68.202 | Dev PC (Ubuntu 24.04) | `palindrome` |
| pihole-home | 192.168.71.25 | DNS / Pi-hole (home network) | `pihole-home` |
| winvm.prox | 172.16.0.100 | Windows lab VM | not deployed (Windows) |
| Gateway | 172.16.0.1 | Network gateway | — |

Networks: `172.16.0.0/22` (lab), `192.168.68.0/24` and `192.168.71.0/24` (home)

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
| InsightsGenerator (enrich next) | `backend/src/services/insights.py` |
| WhatsUp infra list (asset registry seed) | `backend/src/services/whats_up.py` |

---

## Credentials Reference

| Service | URL | User | Password / Key |
|---------|-----|------|----------------|
| ntopng | https://172.16.0.1:3000 | admin | spacex |
| Pi-hole lab | https://172.16.0.13 | — | spacex |
| Pi-hole home | https://192.168.71.25 | — | spacex |
| SentinelZero sensor API | http://172.16.0.254:5000 | — | `SENSOR_API_KEY` in `backend/.env` |
