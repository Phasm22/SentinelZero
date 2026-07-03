# SentinelZero Backend Architecture

Modular Flask application with Socket.IO for real-time scan progress, insights, sensors, and Hunter integration.

## Layout

```
backend/
├── app.py                 # Entry point, schema migration, scheduler, Socket.IO
├── run-app.sh             # Production startup (systemd ExecStart)
└── src/
    ├── models/
    │   ├── scan.py        # Scan records, hosts/vulns/insights JSON
    │   ├── alert.py       # Alert notifications
    │   ├── sensor.py      # SensorAgent, SensorTelemetry
    │   └── incident.py    # IncidentEmbedding
    ├── routes/
    │   ├── scan_routes.py       # Trigger/cancel scans, scan status
    │   ├── api_routes.py        # Dashboard, scan history, ping, health
    │   ├── settings_routes.py   # JSON settings CRUD
    │   ├── schedule_routes.py   # Scheduled scans
    │   ├── upload_routes.py     # Manual XML upload
    │   ├── insights_routes.py   # Insights, verdicts, host-context
    │   ├── hunter_routes.py     # Hunter runs, missions, pivot API
    │   ├── sensor_routes.py     # Sensor agent ingest + registry
    │   ├── diff_routes.py       # Scan diff vs previous
    │   ├── incident_routes.py   # Incident memory / embeddings
    │   └── whatsup_routes.py    # Network health ("What's Up")
    ├── services/
    │   ├── scanner.py           # Nmap orchestration
    │   ├── scan_runtime.py      # Scan lifecycle + socket handlers
    │   ├── insights.py          # Insight generation post-scan
    │   ├── scan_analysis.py     # Per-scan AI pipeline metadata
    │   ├── host_context.py      # DHCP/ARP/registry host enrichment
    │   ├── diff.py              # Scan-to-scan diffs
    │   ├── sync.py              # Scan file ↔ DB sync
    │   ├── sensor_service.py    # Telemetry queries + prune/VACUUM
    │   ├── hunter_reports.py    # Hunter report normalization
    │   ├── agent_service.py     # Verdict agent integration
    │   ├── whats_up.py          # Infrastructure health probes
    │   ├── cleanup.py           # Scheduled XML/data cleanup
    │   ├── notifications.py     # Pushover
    │   └── asset_registry.py    # Known asset context
    └── config/
        ├── database.py    # SQLAlchemy + SQLite WAL pragmas
        └── scheduler.py   # APScheduler job store
```

## Database

- SQLite at `backend/instance/sentinelzero.db` (WAL mode)
- Schema is ensured on startup via `_ensure_database_schema()` in `app.py` — columns and indexes are added idempotently; existing data is preserved
- Composite index on `sensor_telemetry (agent_id, collected_at)` for fast latest-telemetry lookups

## Key API surfaces

| Area | Examples |
|------|----------|
| Scans | `POST /api/scan`, `GET /api/scan-history`, `GET /api/active-scans` |
| Insights | `GET /api/insights`, `GET /api/scans/<id>/host-context` |
| Hunter | `GET /api/hunter/runs`, `POST /api/hunter/missions` |
| Sensors | `POST /api/sensor/ingest`, `GET /api/sensor/agents` |
| Health | `GET /api/ping`, `GET /api/health`, `GET /api/whatsup/summary` |

Host-context GET returns cached data only (`status: pending` if not yet enriched). Enrichment runs during scan postprocessing and via a startup backfill timer.

## Scheduled jobs

Registered in `app.py` when `ENABLE_BACKGROUND_SERVICES` is true:

- XML cleanup (03:15 daily)
- Sensor telemetry prune (03:30 daily) + VACUUM when rows deleted
- Weekly VACUUM safety net (Sunday 03:45)
- What's Up snapshot refresh (every 30s)
- Hunter baseline snapshot (every 6h)

## Development

```bash
cd backend
uv sync
uv run python app.py          # http://0.0.0.0:5000
uv run pytest tests/ -v
uv run black app.py src/ tests/
```

Tests use in-memory SQLite; background services are disabled via `TESTING` config.
