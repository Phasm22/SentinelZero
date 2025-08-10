## SentinelZero – AI Contributor Quick Reference

Goal: Homelab network security scanner (Flask + React) orchestrating nmap scans with real‑time WebSocket streaming, insights generation, and JSON file–driven settings.

### 1. Core Layout
Backend: `backend/src/`
- `services/scanner.py` (critical scan engine & progress events)
- `routes/` Blueprints: `scan_routes.py`, `settings_routes.py`, `api_routes.py`, `upload_routes.py`
- `models/scan.py`, `models/alert.py`
- `services/whats_up.py`, `services/cleanup.py`
Frontend: `frontend/react-sentinelzero/src/`
- `components/ScanControls.jsx` (must mirror backend command logic)
- `pages/Dashboard.jsx` (modal preview command)
- `contexts/SocketContext.jsx`, `ToastContext.jsx`
Settings (snake_case on disk, camelCase via API): root JSON files `*_settings.json`.

### 2. Run & Dev
Backend: `cd backend && uv run python app.py` (DB is DROPPED & recreated each start; avoid seeding destructive data inside agent changes). 
Frontend: `cd frontend/react-sentinelzero && npm run dev`.
Full stack helper: `npm run dev:all` (from `frontend/`).

### 3. Scan Types & Status Flow
Types: Full TCP, IoT Scan, Vuln Scripts, Discovery Scan.
Discovery Scan: host discovery only (no ports), omits `-Pn`, uses `-sn -PE -PP -PM -PR -n`.
Pre‑Discovery Optimization (setting: `pre_discovery_enabled` / `preDiscoveryEnabled`): For heavy scans, runs a fast discovery first and replaces CIDR with live IP list.
Statuses used for active logic: `running`, `parsing`, `saving`, `postprocessing`; terminal: `complete`, `error`, `cancelled`.
Concurrency: Heavy scans counted against limit (`concurrent_scans`); Discovery Scan is excluded and always allowed.

### 4. Command Synchronization (Do Not Drift)
When altering scan flags update BOTH:
- Backend: logic blocks in `scanner.py` (scan_type_normalized branches)
- Frontend: `buildNmapCommand()` in `ScanControls.jsx` and confirmation modal in `Dashboard.jsx`.
User-facing vs exec command: backend may inject `--privileged` and absolute nmap path; keep user-facing string unmodified for transparency.

### 5. Threading & Emissions
All scan work happens in a background thread spawned in `scan_routes.py` using `run_nmap_scan()` inside an `app.app_context()` block.
Emitters: `scan_log`, `scan_progress`, `scan_complete`. Always wrap socket emits in try/except; never let a socket failure abort a scan.

### 6. Settings Handling
`/api/settings` GET: converts snake_case→camelCase. POST expects camelCase groups (`networkSettings`, etc.), converts back. Add new fields snake_case in JSON; consume camelCase on frontend.
New per-scan behavior flag pattern: add to relevant `*_settings.json`, read in route, pass via kwargs into service.

### 7. Discovery & Pre-Discovery Nuances
Discovery Scan: skip OS/service/vuln logic & insights (explicit branch). Filters network/broadcast addresses. Host counts (`total_hosts`, `hosts_up`) set after XML parse.
Pre-Discovery: only for heavy scans; generates live host list → enumerated as direct targets (reduces false positives & time, but skips offline hosts for insights).

### 8. Insights Generation
Runs post save unless scan is Discovery or explicitly skipped. Stored JSON in `Scan.insights_json`. If you broaden insight logic, keep it fast (runs at ~99% phase) and resilient (wrap in try/except, never fail scan completion). Use the on-demand diff endpoint `/api/scan-diff/<scan_id>` for structured host/port/vuln changes instead of expanding stored insights when only comparative deltas are needed.

### 9. Cancellation & Concurrency
Endpoints: `/api/cancel-scan/<id>`, `/api/kill-all-scans`. Scan loop periodically re-queries its Scan record to honor cancellation. When adding new long loops, insert cancellation checks.

### 10. Common Pitfalls / Guardrails
- Do not add `-Pn` to discovery path (causes every host to appear up).
- Always create `scans/` directory before writing XML.
- Keep vulnerability script usage limited (explicit `Vuln Scripts` scan vs selective scripts for regular scans).
- Preserve alias handling for scan types (lowercasing + accepted synonyms) when adding new ones.
- Avoid modifying `app.py` drop/create logic unless performing a schema migration task.

### 11. Extending Features Safely
Add new scan type: update enum logic (backend + frontend), tooltips, and optionally insights exclusion rules.
Add new setting: snake_case key in JSON + camelCase surfaced; include in settings page state defaults.
Add socket channel: define emission site + frontend listener in `SocketContext` or relevant component; clean up listeners on unmount.

### 12. Minimal Test & Verification Steps
Backend quick check: `uv run python - <<'PY'` snippet to import and list models.
Run backend tests (once expanded): `npm run test:backend`.
Manual scan sanity: trigger Discovery then Full TCP; confirm command parity and progress events.

### 13. Security / Privilege Handling
`scanner.py` inserts `--privileged` automatically for raw socket flags when not root. Keep split between `user_facing_cmd` (logged/showed) and `exec_cmd` (adjusted). Any privilege fallback variant (e.g., degraded IoT) must recurse with `_priv_fallback=True`.

### 14. Cleanup & Retention
`services/cleanup.py` scheduled job purges old XML & orphaned data (registered in `app.py`). When adding file outputs, register them for cleanup.

### 15. Do / Don’t Summary
DO: Mirror scan flags frontend↔backend; wrap DB + socket ops; maintain status transitions; respect concurrency rules.
DON’T: Introduce blocking operations in main thread; emit unsanitized user input; remove discovery exclusion from concurrency; silently change command semantics.

Use this as the authoritative reference before modifying scan orchestration, settings schema, or socket event surface.
