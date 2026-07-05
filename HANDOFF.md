# Handoff — Pivot tools 1–3, asset registry fix, DB maintenance

**Date:** 2026-07-05
**Branch:** `dev` (all commits below are on `dev`)
**Author:** pairing session (Claude)

---

## TL;DR

- Shipped pivot backlog **tools 1–3** (`seed_context_load`, `asset_expectation_check`, `http_recon` upgrades) — decision-grade typed findings, proven live on `172.16.0.85`.
- Root-caused and fixed the **asset registry not loading** (backend read a non-existent `~/agent/...` path → every host read "unregistered" → false `registry_gap` escalations).
- Root-caused **9.7 GB SQLite WAL** bloat and added a periodic `wal_checkpoint(TRUNCATE)` job.
- Wiped agent-side state; handed off a root script for the backend DB wipe + restart (**still pending — see "Action required"**).

## Commits (on `dev`)

| commit | what |
|---|---|
| `1df0e15` | Pivot tools 1–3: seed-context findings, `pivot_asset_drift`, `http_recon` port/grade upgrades, `_parse_action` multi-object hardening |
| `a84586c` | Asset registry default path fix (repo-relative; `SENTINEL_ASSETS_PATH` still overrides) |
| `66c9c3d` | Periodic WAL checkpoint job (`db_maintenance.checkpoint_wal`, every 10 min) |

## ⚠️ Action required (needs root — not done)

The backend runs as system service `sentinelzero.service` (no passwordless sudo in the session). Run this to wipe the bloated main DB and activate the two backend fixes (registry path + WAL job load on restart). **`jobs.sqlite` / scan schedules are intentionally preserved.**

```bash
sudo systemctl stop sentinelzero.service
rm -f /home/sentinel/SentinelZero/backend/instance/sentinelzero.db \
      /home/sentinel/SentinelZero/backend/instance/sentinelzero.db-wal \
      /home/sentinel/SentinelZero/backend/instance/sentinelzero.db-shm
sudo systemctl start sentinelzero.service
sleep 4 && sudo systemctl is-active sentinelzero.service
```

Then verify:
```bash
curl -s http://172.16.0.254:5000/api/scans           # -> []
# Run a scan of 172.16.0.0/22, then confirm host_context for 172.16.0.11
# shows in_asset_registry=true, trust_zone="infrastructure", and NO registry_gap insight.
```

---

## What was done

### 1. Pivot tools 1–3 (`agent/hunter/pivot/`)
- **Tool 1 `seed_context_load`** — kept existing `hydration.py::hydrate_seed` (no duplication). Closed the gap where hydrated evidence dead-ended at generic `pivot_recon`: hydrated ports now emit typed `pivot_asset_drift`, hydrated http_recon emits typed `pivot_http_exposure` (event type `http_exposure`, since no live NSE ran).
- **Tool 2 `asset_expectation_check`** (new `runners/asset_expectation_runner.py`) — compares open ports vs `context/assets.json`; emits `pivot_asset_drift` with `unexpected_ports`/`missing_ports`/`registered`; grades `escalate | next_scan | observe` by trust zone. Passive.
- **Tool 3 `http_recon`** — surface ports extended to `80,443,8080,8443,3128,8006,8581` with priority-ordered target selection; decision-grade `recommend_http_action` replaces hardcoded `"observe"`.
- **Support:** `triage_ports` recommends `asset_expectation_check` whenever ports are known; removed dead `port_scan_light` from `approval.PASSIVE_TOOLS`; hardened `_parse_action` to take the first balanced JSON object (small models emit multiple objects → was dead-ending).
- **Tests:** `agent/hunter/pivot/tests/` — 18 pass (`.venv/bin/python -m pytest hunter/pivot/tests/ -q` from `agent/`).
- **Live proof:** LLM-driven mission on `172.16.0.85` → typed `pivot_http_exposure` (title "porttest // lab gateway" → `recommended_action: escalate`, nginx/1.24.0), no `pivot_recon`.

### 2. Asset registry path fix (`backend/src/services/asset_registry.py`)
- Default was `~/agent/context/assets.json` → `/home/sentinel/agent/...` which **does not exist** (repo is `~/SentinelZero/agent`). `_load_registry()` returned `{}`, so every host read as unregistered and insight generation raised false `registry_gap` (prio 75) + `correlated` (prio 80) escalations for hosts that ARE registered.
- Default is now repo-relative (`parents[3]/agent/context/assets.json`); loader verified resolving 19 hosts. Also created `~/agent → ~/SentinelZero/agent` symlink as a belt-and-suspenders. Needs backend restart (registry is `@lru_cache`).
- **Sensors were NOT affected and are working** — 7 agents active with fresh heartbeats; `host_context.endpoint_sensor` populated per host; `sensor_gap` correctly excludes hosts with endpoint agents.

### 3. DB maintenance (`backend/src/services/db_maintenance.py`, `backend/app.py`)
- `sentinelzero.db` was **2.2 GB with a 9.7 GB `-wal`** — WAL mode enabled but nothing ran a TRUNCATE checkpoint, so the sidecar grew unbounded under the polling UI + scheduler.
- Added `checkpoint_wal()` (raw `sqlite3`, no Flask app context → jobstore-serializable) scheduled every 10 min. Verified truncating a 41 MB test WAL to 0.

### 4. Data topology (for reference)
Three separate stores — **hunter runs and pivot missions do NOT share a DB**:
- **Backend app DB** `backend/instance/sentinelzero.db` (SQLAlchemy): tables `scan` (insights/host_context/analysis embedded as JSON columns), `sensor_agent`, `sensor_telemetry`, `incident_embedding`, `alert`.
- **Backend scheduler** `backend/instance/jobs.sqlite`: `apscheduler_jobs` (scan schedules; do NOT auto-repopulate).
- **Agent side (file-based):** pivot = one SQLite per mission at `agent/state/pivot-<id>.sqlite` + JSON report in `agent/reports/`; hunter = JSON reports only (`agent/reports/hunt-*.json`) + `agent/state/iot_fingerprints.json` baseline. Convergence only via API (`incident_embedding`, scan hydration).

### 5. Wipe performed (agent side, this session)
Deleted: all `agent/state/pivot-*.sqlite`, all `agent/reports/*.json`, `agent/reports/mission-logs/*`, and `agent/state/iot_fingerprints.json` (per chosen scope: also wipe sensor registrations + baseline; keep scheduler jobs). Directories preserved. Backend DB wipe is the pending root step above.

---

## What's next

1. **Run the restart script** above; confirm registry resolves and `registry_gap` is gone after a fresh scan.
2. **Pivot tool 4 — `tls_recon`** (443/8443 → `pivot_tls_posture`): next backlog item. Can be built + fixture-tested offline without the restart. Add cert/cipher fields not available from `nmap -sV` alone.
3. **Remaining backlog (tools 5–15):** `ssh_audit`, `rpc_audit`, `proxmox_recon`, `rdp_recon`, `dns_recon`, `iot_udp_probe`, `upnp_discover`, `mdns_discover`, `sensor_correlate`, `opnsense_correlate`, `baseline_diff`. Follow the same per-tool checklist (runner + fixture + approval class + orchestrator dispatch/SYSTEM/fixture-driver + triage rule + typed terminal finding + unit test).

## Open items / hypotheses to verify

- **Existing `vacuum_database` / `prune_old_telemetry` scheduler jobs** may be failing on Flask-SQLAlchemy 3.1 app-context (they touch `db` without pushing context, unlike `refresh_whats_up_snapshot`). If confirmed in `journalctl -u sentinelzero.service` ("working outside of application context"), they should be wrapped in an app context — this would compound bloat. The new WAL job is independent and unaffected.
- **`sentinel-agent.service` is failed** ("No completed scans found") — benign at the time (empty DB); should recover once scans exist.
