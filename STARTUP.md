# SentinelZero Startup Guide

How to start and stop SentinelZero in development and production.

## Quick start

### Development

```bash
./start-dev.sh
# Frontend: http://localhost:3173
# Backend:  http://localhost:5000
```

Or from `frontend/`:

```bash
npm run dev:all    # backend + Vite concurrently
```

Stop with `Ctrl+C` or:

```bash
./stop-dev.sh
./cleanup-sentinelzero.sh cleanup   # if ports are stuck
```

### Production

```bash
./start-prod.sh
sudo systemctl status sentinelzero
```

Stop:

```bash
sudo systemctl stop sentinelzero
```

## Scripts

| Script | Purpose |
|--------|---------|
| `./start-dev.sh` | Backend (5000) + Vite frontend (3173) |
| `./stop-dev.sh` | Stop dev processes |
| `./start-prod.sh` | Build frontend, install/start systemd service |
| `./cleanup-sentinelzero.sh status` | Show running SentinelZero processes |
| `./cleanup-sentinelzero.sh cleanup` | Kill stuck processes / free ports |
| `./cleanup-scans.sh` | Cancel active scans, kill orphaned nmap |

See [SCRIPTS.md](SCRIPTS.md) for details.

## Ports

| Service | Port | URL |
|---------|------|-----|
| Backend API + Socket.IO | 5000 | http://localhost:5000 |
| Frontend (Vite dev) | 3173 | http://localhost:3173 |

In production with a static build, the frontend can be served through Flask on port 5000 alone (`./start-prod.sh` handles the build step).

## Checking status

```bash
# Production
sudo systemctl status sentinelzero
sudo journalctl -u sentinelzero -f

# Dev or stuck processes
./cleanup-sentinelzero.sh status
curl -s http://localhost:5000/api/ping
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3173
```

## Dev logs

During `./start-dev.sh`:

- Backend: `/tmp/sentinelzero-backend.log`
- Frontend: `/tmp/sentinelzero-frontend.log`

## Troubleshooting

**Port already in use**

```bash
lsof -i :5000
lsof -i :3173
./cleanup-sentinelzero.sh cleanup
```

**Service won't start**

```bash
sudo journalctl -u sentinelzero -f
cd backend && uv sync && uv run python -c "from app import create_app; create_app()"
```

**Nuclear reset**

```bash
./cleanup-sentinelzero.sh cleanup
./start-dev.sh
```

## Best practices

1. Use the provided scripts instead of starting processes manually.
2. Check `./cleanup-sentinelzero.sh status` before starting if unsure what's running.
3. Use `sudo systemctl restart sentinelzero` for production restarts after code pulls.
4. Run `cd backend && uv sync` after pulling backend dependency changes.
