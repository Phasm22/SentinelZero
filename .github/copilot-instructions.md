## SentinelZero – AI Contributor Quick Reference

Goal: Homelab network security scanner (Flask + React) orchestrating nmap scans with real-time WebSocket streaming, insights/verdicts, sensor telemetry, Hunter integration, and JSON file–driven settings.

### 1. Core Layout

**Backend:** `backend/src/`

| Layer | Key files |
|-------|-----------|
| Routes | `scan_routes.py`, `api_routes.py`, `settings_routes.py`, `insights_routes.py`, `hunter_routes.py`, `sensor_routes.py`, `diff_routes.py`, `whatsup_routes.py`, `upload_routes.py` |
| Services | `scanner.py`, `scan_runtime.py`, `insights.py`, `host_context.py`, `sensor_service.py`, `hunter_reports.py`, `whats_up.py`, `sync.py`, `cleanup.py` |
| Models | `scan.py`, `alert.py`, `sensor.py`, `incident.py` |

**Frontend:** `frontend/react-sentinelzero/src/`

- `pages/Dashboard.jsx`, `pages/HunterRuns.jsx`, `pages/LabStatus.jsx`
- `components/ScanControls.jsx` (must mirror backend nmap command logic)
- `components/hunter/*` — Hunter Runs UI
- `contexts/SocketContext.jsx`, `contexts/ToastContext.jsx`

Settings (snake_case on disk, camelCase via API): `*_settings.json` in `backend/`.

### 2. Run & Dev

```bash
cd backend && uv run python app.py          # port 5000
cd frontend/react-sentinelzero && npm run dev   # port 3173, proxies /api
cd frontend && npm run dev:all            # both
```

Production: `sentinelzero.service` → `backend/run-app.sh`.

**Database:** SQLite at `backend/instance/sentinelzero.db`. Schema is migrated in place on startup via `_ensure_database_schema()` — do **not** assume the DB is dropped/recreated. Add columns/indexes idempotently in that function.

### 3. Scan Types & Status Flow

Types: Full TCP, IoT Scan, Vuln Scripts, Discovery Scan.

- Discovery: host discovery only (`-sn`), no `-Pn`
- Pre-discovery (`pre_discovery_enabled`): fast live-host sweep before heavy scans
- Vuln Scripts: targets open ports from latest Full TCP scan when available; long timeout (`SCAN_TIMEOUT_VULN_SECONDS`)

Active statuses: `running`, `parsing`, `saving`, `postprocessing` (+ legacy `starting`, `in_progress`).

Terminal: `complete`, `failed`, `cancelled`, `error`.

### 4. Command Synchronization (Do Not Drift)

When altering scan flags, update **both**:

- Backend: `scanner.py` (`scan_type_normalized` branches)
- Frontend: `buildNmapCommand()` in `ScanControls.jsx` and confirmation modal in `Dashboard.jsx`

Keep `user_facing_cmd` (logged/shown) separate from `exec_cmd` (may add `--privileged`).

### 5. Threading & Socket Events

Scans run in background threads inside `app.app_context()`. Eventlet worker — blocking DB calls on the main request path stall all API traffic.

Emitters: `scan.log`, `scan.progress`, `scan.snapshot`, `scan.completed`, `scan.failed`, `scan.cancelled`, `insights.verdicts_ready`. Wrap emits in try/except.

**Never** run expensive work synchronously on GET (e.g. `build_host_context()` was removed from the host-context endpoint for this reason).

### 6. Settings Handling

`/api/settings` GET converts snake_case → camelCase. POST expects camelCase groups. Add new fields snake_case in JSON files.

### 7. Insights & Host Context

Postprocessing (`generate_and_store_insights`) builds insights, diffs, and persists host context via `store_host_context()`.

- Insights stored in `Scan.insights_json`
- Host context in `Scan.host_context_json`
- GET `/api/scans/<id>/host-context` returns cache only; `status: pending` if missing

Use `/api/scan-diff/<id>` for on-demand diffs.

### 8. Sensors & Telemetry

`sensor_telemetry` is high-volume. Latest collectors query uses composite index `(agent_id, collected_at)`. Prune + VACUUM scheduled in `app.py`.

### 9. Hunter

Reports normalized in `hunter_reports.py`. Routes under `/api/hunter/*`. Pivot missions via `POST /api/hunter/missions`.

### 10. Cancellation & Concurrency

`/api/cancel-scan/<id>`, `/api/kill-all-scans`. Scan loops re-query DB for cancellation. Respect `concurrent_scans` limit (Discovery excluded).

### 11. Schema Changes

Add columns/indexes in `_ensure_database_schema()` in `app.py`. Use `CREATE INDEX IF NOT EXISTS` for SQLite. Do not drop tables in normal feature work.

### 12. Tests

```bash
cd frontend && npm run test:backend   # pytest, 38% cov minimum
cd backend && uv run pytest tests/unit/test_sensor_telemetry.py -v
```

### 13. Cleanup & Retention

- `cleanup.py` — old scan XML
- `sensor_service.prune_old_telemetry()` — telemetry retention (default 7 days)
- Playwright/test-results dirs are gitignored

### 14. Do / Don't

**DO:** Mirror scan flags frontend↔backend; wrap DB + socket ops; use background threads for long work; respect concurrency rules.

**DON'T:** Block the eventlet worker with slow queries; rebuild host context on GET; commit test artifacts; drop/recreate the production DB.

Use this as the authoritative reference before modifying scan orchestration, settings schema, or socket event surface.
