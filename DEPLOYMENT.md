# SentinelZero Deployment Guide

This guide describes how SentinelZero is deployed on a single homelab host today.

## Current architecture

```
┌──────────────────────┐     ┌─────────────────────────────┐
│  Traefik + Authentik │────▶│  sentinelzero.service :5000 │
│  (optional, remote)  │     │  Flask + Socket.IO          │
└──────────────────────┘     │  serves React dist/         │
                             └─────────────────────────────┘
```

Production on this machine uses **one systemd unit** (`sentinelzero.service`). The React UI is built to `frontend/react-sentinelzero/dist` and served by Flask on port **5000**. Do **not** run the Vite unit (`sentinelzero-frontend`) in production.

Authentication, when enabled, is handled by remote **Traefik + Authentik** forward auth — see [AUTHENTIK_SETUP.md](AUTHENTIK_SETUP.md). Traefik must point at `http://172.16.0.198:5000` (see `traefik/dynamic/sentinelzero.yml`).

## Prerequisites

```bash
sudo apt update
sudo apt install -y nmap curl git

# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Node.js 18+ for the frontend
# (install via nodesource, nvm, or your distro package manager)
```

## Quick deploy

From the repo root:

```bash
./start-prod.sh          # build frontend, install systemd unit, start service
./start-prod.sh --test   # run tests first
```

Manual service install:

```bash
sudo cp sentinelzero.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable sentinelzero
sudo systemctl start sentinelzero
```

## Service management

```bash
sudo systemctl status sentinelzero
sudo systemctl restart sentinelzero
sudo journalctl -u sentinelzero -f
```

## Health checks

```bash
curl http://localhost:5000/api/ping
curl http://localhost:5000/api/health
curl -s http://localhost:5000/ | head   # static UI (production)
```

## Environment variables

Set in `sentinelzero.service` or override with a drop-in:

| Variable | Default | Purpose |
|----------|---------|---------|
| `SENTINEL_BIND_PORT` | `5000` | Backend listen port |
| `SENTINEL_ALLOWED_ORIGINS` | see service file | CORS / Socket.IO origins |
| `SCAN_TIMEOUT_SECONDS` | `1800` | Lab scan watchdog |
| `SCAN_TIMEOUT_VULN_SECONDS` | `10800` | Vuln-script scan watchdog |
| `SENTINEL_TELEMETRY_RETENTION_DAYS` | `3` | Sensor telemetry prune age |
| `SENTINEL_VACUUM_AFTER_PRUNE` | `1` | Run SQLite VACUUM after telemetry delete |

## Database maintenance

SQLite lives at `backend/instance/sentinelzero.db`. Telemetry pruning runs daily at 03:30; VACUUM runs after deletes and weekly on Sundays at 03:45.

To reclaim space manually (brief downtime recommended):

```bash
sudo systemctl stop sentinelzero
cd backend && uv run python -c "
from app import create_app
from src.services import sensor_service
app = create_app({'ENABLE_BACKGROUND_SERVICES': False})
with app.app_context():
    print('deleted', sensor_service.prune_old_telemetry())
"
# VACUUM is triggered automatically when rows are deleted
sudo systemctl start sentinelzero
```

## Troubleshooting

**Service won't start**

```bash
journalctl -u sentinelzero --no-pager -n 50
ls -la backend/instance/ backend/scans/
```

**Port in use**

```bash
./cleanup-sentinelzero.sh cleanup
```

**Dependency updates**

```bash
cd backend && uv sync
cd frontend/react-sentinelzero && npm install
```

## Docker (optional)

For a standalone container without Authentik:

```bash
docker-compose up -d
```

See `docker-compose.yml` for configuration.

## Related docs

- [STARTUP.md](STARTUP.md) — dev vs prod scripts
- [SCRIPTS.md](SCRIPTS.md) — script reference
- [AUTHENTIK_SETUP.md](AUTHENTIK_SETUP.md) — SSO
- [traefik/README.md](traefik/README.md) — reverse proxy
