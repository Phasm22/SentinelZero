# SentinelZero Backend

Flask + Socket.IO API for network scanning, insights, sensors, and Hunter integration.

## Features

- **Network scanning** — nmap orchestration with real-time WebSocket progress
- **Insights & verdicts** — post-scan diffing, AI verdict pipeline, host-context enrichment
- **Hunter integration** — runs, missions, pivot API
- **Sensor telemetry** — agent ingest, timeline queries, retention pruning
- **What's Up** — infrastructure health monitoring with cached snapshots
- **Scheduled scans** — APScheduler jobs
- **Settings** — JSON file–backed configuration via REST API

## Quick start

```bash
uv sync
uv run python app.py
# → http://localhost:5000
```

## Development

```bash
uv run pytest tests/ -v
uv run black app.py src/ tests/
uv run flake8 app.py src/ tests/
```

## Architecture

See [src/README.md](src/README.md) for routes, services, models, and scheduled jobs.

## Key endpoints

- `GET /api/ping` — liveness
- `GET /api/health` — health check
- `GET /api/scan-history` — paginated scan list
- `POST /api/scan` — trigger scan
- `GET /api/insights` — insight feed
- `GET /api/hunter/runs` — Hunter run history
- `POST /api/sensor/ingest` — sensor telemetry
