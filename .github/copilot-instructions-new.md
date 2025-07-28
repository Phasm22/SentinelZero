# SentinelZero Development Guide

## Architecture Overview

SentinelZero is a homelab network security scanner with modular Flask/SQLAlchemy backend and React/Vite frontend. The app orchestrates nmap scans, parses XML results, and provides real-time progress via WebSockets.

**Key Components:**
- **Backend**: Modular Flask application in `backend/src/` with Blueprint architecture
- **Frontend**: React SPA in `frontend/react-sentinelzero/` with Vite, Tailwind CSS, and custom components  
- **Database**: SQLite with models: `Scan` (results + metadata) and `Alert` (notifications)
- **Real-time**: Flask-SocketIO for scan progress, logs, and completion events
- **Scheduling**: APScheduler with SQLite job persistence for automated scans
- **Monitoring**: What's Up system for network health monitoring

## Modular Backend Structure

**Current Architecture (Post-Migration):**
```
backend/
├── app.py                    # Application factory entry point
├── src/
│   ├── models/
│   │   ├── scan.py          # Scan database model with created_at, completed_at, total_hosts
│   │   └── alert.py         # Alert model with title, severity, read status
│   ├── routes/              # Blueprint-based API routes
│   │   ├── scan_routes.py   # /api/scan, /api/clear-scan/<id>
│   │   ├── settings_routes.py # /api/settings with field normalization
│   │   ├── schedule_routes.py # /api/scheduled-scans
│   │   └── api_routes.py    # /api/dashboard-stats, /api/network-interfaces, /api/whatsup/summary
│   ├── services/
│   │   ├── scanner.py       # Nmap scan orchestration with progress tracking
│   │   ├── notifications.py # Pushover notification system
│   │   └── whats_up.py      # Network health monitoring service
│   └── config/
│       ├── database.py      # SQLAlchemy initialization with absolute paths
│       └── scheduler.py     # APScheduler background service setup
```

**Migration Note**: The monolithic `app.py` (~2000 lines) was refactored into this modular structure. Use `python migrate.py modular|monolithic` to switch between architectures.

## Frontend Architecture

**React + Vite Structure:**
```
frontend/react-sentinelzero/
├── src/
│   ├── components/          # Reusable UI components (Layout, Modal, etc.)
│   ├── pages/              # Page components (Dashboard, Settings, ScanHistory)
│   ├── contexts/           # React contexts (SocketContext, ToastContext, UserPreferences)
│   ├── utils/              # API service layer and helpers
│   └── App.jsx             # Main router with BackgroundCrossfade component
├── vite.config.js          # Proxy config: /api → localhost:5001
└── tailwind.config.js      # Custom theme with Sentient fonts
```

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
All API routes follow `/api/*` pattern with Blueprint organization:
```python
# In routes/api_routes.py
@bp.route('/dashboard-stats', methods=['GET'])
def dashboard_stats():
    # Route logic only - calls service layer
```

### Settings Architecture
Settings stored in JSON files (not database) with field normalization:
- `network_settings.json`: Target networks, scan limits
- `security_settings.json`: nmap flags, vulnerability scanning  
- `notification_settings.json`: Pushover configuration
- `scheduled_scans_settings.json`: Cron schedules

**Pattern**: Backend normalizes camelCase ↔ snake_case field names for frontend compatibility.

## Development Workflows

### Running Development Environment
```bash
# Backend only (modular)
cd backend && python app.py

# Frontend only
cd frontend/react-sentinelzero && npm run dev

# Full stack (from frontend/)
npm run dev:all

# Switch architecture
cd backend && python migrate.py modular|monolithic
```

### Key Ports & URLs
- **Backend**: `http://localhost:5001` (changed from 5000)
- **Frontend Dev**: `http://localhost:3173/3174` (Vite dev server)  
- **API Base**: `/api/*` routes proxied through Vite
- **WebSocket**: `/socket.io` proxied for real-time updates

### Testing Strategy
- **Backend**: pytest with coverage reports (`npm run test:backend`)
- **Frontend**: Playwright for E2E testing (`npm run test:playwright`)
- **Integration**: Mixed pytest + Playwright tests in `backend/tests/`

## What's Up Monitoring System

Three-layer health monitoring architecture:
1. **Loopbacks**: Basic network connectivity (`LOOPBACKS` array)
2. **Services**: DNS + application health (`SERVICES` array)
3. **Infrastructure**: Critical components (`INFRASTRUCTURE` array)

**Pattern**: Each layer builds on the previous - services check DNS resolution before connectivity, infrastructure checks include specialized probes.

## Common Gotchas

### Database Context
SQLAlchemy operations in background threads need `with app.app_context():` wrapper. Database uses absolute paths for Docker compatibility.

### Field Normalization
Frontend uses camelCase, backend uses snake_case. Settings routes handle automatic conversion:
```python
# Backend converts maxHosts → max_hosts automatically
```

### Import Paths
Modular structure requires careful import management:
```python
# Correct import pattern
from src.models import Scan, Alert
from src.services.scanner import run_nmap_scan
```

### XML Parsing
nmap XML output can contain invalid UTF-8. Always handle encoding errors and validate file size before parsing.

### React State Management
Uses Context pattern (no Redux). Custom hooks in `src/hooks/` for API state. WebSocket connections managed in SocketContext.

## File Conventions

- **Settings files**: JSON in backend root, loaded/saved via dedicated functions
- **Scan results**: XML files in `scans/` directory with timestamp naming
- **Database**: SQLite in `instance/` directory for dev, `/app/instance` in Docker
- **React builds**: Served directly by Flask in production via catch-all route
- **Component naming**: PascalCase for React components, kebab-case for CSS classes

When adding new scan types, update both the nmap command logic in `src/services/scanner.py` and the frontend dropdown options in scan components.

## Docker & Deployment

- Production uses single Dockerfile with multi-stage build
- Requires `NET_ADMIN` and `NET_RAW` capabilities for nmap
- Health checks via `/api/dashboard-stats` endpoint
- Frontend build output served by Flask catch-all route
