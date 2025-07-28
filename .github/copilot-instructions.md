# SentinelZero Development Guide

## Architecture Overview

SentinelZero is a homelab network security scanner with Flask/SQLAlchemy backend and React/Vite frontend. The app orchestrates nmap scans, parses XML results, and provides real-time progress via WebSockets.

**Key Components:**
- **Backend**: Single `backend/app.py` file (~1800 lines) handling all API routes, scan orchestration, and database models
- **Frontend**: React SPA in `frontend/react-sentinelzero/` with Vite build system and Tailwind CSS
- **Database**: SQLite with two main models: `Scan` (results + metadata) and `Alert` (notifications)
- **Real-time**: Flask-SocketIO for scan progress, logs, and completion events
- **Scheduling**: APScheduler for automated scans with cron-like configuration

## Critical Development Patterns

### Scan Orchestration
Scans run in background threads with real-time progress updates:
```python
def emit_progress(status, percent, message):
    scan.status = status
    scan.percent = percent
    db.session.commit()
    socketio.emit('scan_progress', {...})
```
**Key insight**: All scan operations must handle database rollback and socketio emission errors gracefully since scans run in separate threads.

### SocketIO Communication
Three main event types:
- `scan_progress`: Status updates with percentage completion
- `scan_log`: Real-time nmap output and debug messages  
- `scan_complete`: Final completion notification

**Pattern**: Always wrap socketio.emit in try/except blocks since WebSocket connections can drop during long-running scans.

### API Route Structure
All API routes follow `/api/*` pattern. Non-API routes serve React SPA via catch-all:
```python
@app.route('/<path:path>')
def catch_all(path):
    # Serve React app for non-API routes
```

### Settings Architecture
Settings are stored in JSON files (not database):
- `network_settings.json`: Target networks, scan limits
- `security_settings.json`: nmap flags, vulnerability scanning
- `notification_settings.json`: Pushover configuration
- `scheduled_scans_settings.json`: Cron schedules

**Why**: Allows configuration changes without database migrations and enables easy Docker volume mounting.

## What's Up Monitoring System

Three-layer health monitoring architecture:
1. **Loopbacks**: Basic network connectivity (`LOOPBACKS` array)
2. **Services**: DNS + application health (`SERVICES` array) 
3. **Infrastructure**: Critical components (`INFRASTRUCTURE` array)

**Pattern**: Each layer builds on the previous - services check DNS resolution before connectivity, infrastructure checks include specialized probes (HTTP, DNS queries).

## Key Development Workflows

### Running Development Environment
```bash
# Backend only
cd backend && python3 app.py

# Frontend only  
cd frontend/react-sentinelzero && npm run dev

# Full stack (from frontend/)
npm run dev:all
```

### Testing Strategy
- **Backend**: pytest with coverage reports (`npm run test:backend`)
- **Frontend**: Playwright for E2E testing (`npm run test:playwright`)
- **Integration**: Mixed pytest + Playwright tests in `backend/tests/`

### Docker Development
- Production uses single Dockerfile with multi-stage build
- Requires `NET_ADMIN` and `NET_RAW` capabilities for nmap
- Health checks via `/api/dashboard-stats` endpoint

## Common Gotchas

### Database Context
SQLAlchemy operations in background threads need `with app.app_context():` wrapper.

### XML Parsing
nmap XML output can contain invalid UTF-8. Always handle encoding errors and validate file size before parsing.

### Security Settings
The `run_nmap_scan()` function applies security settings dynamically - vulnerability scripts are only enabled for explicit "Vuln Scripts" scan type or when `vuln_scanning_enabled` is true.

### Frontend State Management
React components use custom hooks in `src/hooks/` for API state. No global state library - uses React Context for theme/settings only.

## File Conventions

- **Settings files**: Always JSON in backend root, loaded/saved via dedicated functions
- **Scan results**: XML files in `scans/` directory with timestamp naming
- **Database**: SQLite in `instance/` directory for dev, `/app/instance` in Docker
- **Static files**: React build output served directly by Flask in production

When adding new scan types, update both the nmap command logic in `run_nmap_scan()` and the frontend dropdown options in the scan components.
