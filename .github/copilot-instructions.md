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
- **Backend**: `http://localhost:5000`
- **Frontend Dev**: `http://localhost:3173` (Vite dev server)  
- **API Base**: `/api/*` routes proxied through Vite
- **WebSocket**: `/socket.io` proxied for real-time updates

### Testing Strategy
```bash
# Run all tests (backend + frontend)
npm run test

# Backend tests with coverage
npm run test:backend

# Playwright E2E tests
npm run test:playwright
```

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
├── vite.config.js          # Proxy config: /api → localhost:5000
└── tailwind.config.js      # Custom theme with Sentient fonts
```

## Critical Development Patterns

### Scan Orchestration & Threading
Scans run in background threads with real-time progress updates:
```python
def emit_progress(status, percent, message):
    scan.status = status
    scan.percent = percent
    db.session.commit()
    socketio.emit('scan_progress', {...})
```

**Key insights**:
- All scan operations must handle database rollback and socketio emission errors gracefully since scans run in separate threads
- Use `with app.app_context():` wrapper for SQLAlchemy operations in background threads
- nmap assertion errors (return code -6) are handled gracefully - continue processing if valid XML exists

### SocketIO Communication  
Three main event types for real-time updates:
- `scan_progress`: Status updates with percentage completion  
- `scan_log`: Real-time nmap output and debug messages
- `scan_complete`: Final completion notification

**Pattern**: Always wrap socketio.emit in try/except blocks since WebSocket connections can drop during long-running scans:
```python
try:
    socketio.emit('scan_log', {'msg': msg})
except Exception as e:
    print(f'[DEBUG] Could not emit to socketio: {e}')
```

### Nmap Command Architecture
Scan types are hardcoded strings that must match exactly between frontend and backend:
- Backend: `scan_type_normalized = scan_type.strip().lower()`
- Frontend: `const scanTypeNormalized = String(scanType).toLowerCase()`
- Valid types: "full tcp", "iot scan", "vuln scripts"

**Critical Pattern**: Frontend `buildNmapCommand()` in `ScanControls.jsx` must exactly match backend execution in `src/services/scanner.py`. Test by comparing modal preview with backend logs.

### Settings Architecture & Field Normalization
Settings stored in JSON files (not database) with camelCase ↔ snake_case conversion:
```
backend/
├── network_settings.json      # Target networks, scan timeouts
├── security_settings.json     # nmap flags, vulnerability scanning  
├── notification_settings.json # Pushover configuration
└── scheduled_scans_settings.json # Cron schedules
```

**Pattern**: Backend automatically converts field names for frontend compatibility in settings routes.

### Large Network Handling
For networks >256 hosts, the system:
1. Uses conservative timing (T3 instead of T4)
2. Reduces max retries (1 instead of 2) 
3. Implements fallback to individual host scanning when nmap fails
4. Adds comprehensive timeout settings for stability

**Function**: `get_network_size()` calculates hosts in CIDR ranges to trigger adaptive behavior.

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
- **Backend**: `http://localhost:5000` (changed from 5000)
- **Frontend Dev**: `http://localhost:3173/3174` (Vite dev server)  
- **API Base**: `/api/*` routes proxied through Vite
- **WebSocket**: `/socket.io` proxied for real-time updates

### Testing Strategy
- **Backend**: pytest with coverage reports (`npm run test:backend`)
- **Frontend**: Playwright for E2E testing (`npm run test:playwright`)
- **Integration**: Mixed pytest + Playwright tests in `backend/tests/`

**Critical Test Pattern**: When fixing scan command mismatches, test both frontend modal display AND backend execution logs to ensure they match.

## What's Up Monitoring System

Three-layer health monitoring architecture:
1. **Loopbacks**: Basic network connectivity (`LOOPBACKS` array)
2. **Services**: DNS + application health (`SERVICES` array)
3. **Infrastructure**: Critical components (`INFRASTRUCTURE` array)

**Pattern**: Each layer builds on the previous - services check DNS resolution before connectivity, infrastructure checks include specialized probes.

## Common Gotchas & Critical Patterns

### Null Safety in React Components
**Most Critical**: Always validate function parameters and use optional chaining:
```jsx
// Correct - safe parameter handling
const buildNmapCommand = (scanType, security, targetNetwork = '172.16.0.0/22') => {
  if (!scanType) return 'nmap -v -T4 -sS -p- --open 172.16.0.0/22 -oX scan_output.xml'
  const scanTypeNormalized = String(scanType).toLowerCase()
  // ... rest of function
}

// Correct - safe settings access
const enabled = settings.scheduledScans?.enabled || false
```

### Frontend/Backend Command Synchronization
**Major Issue**: Users expect scan modal commands to match actual execution. Backend `run_nmap_scan()` and frontend `buildNmapCommand()` must generate identical commands:

```javascript
// Frontend buildNmapCommand must match these backend patterns:
// Full TCP: nmap -v -T4 -Pn -sS -p- --open -O -sV target -oX file
// IoT Scan: nmap -v -T4 -Pn -sU -p 53,67,68,... target -oX file  
// Vuln Scripts: nmap -v -T4 -Pn -sS -p- --open --script=vuln target -oX file
```

### WebSocket Context Management
Avoid duplicate event listeners between SocketContext and page components. The SocketContext should only handle connection events:
```jsx
// SocketContext - connection only
socket.on('connect', () => console.log('Connected'))
socket.on('disconnect', () => console.log('Disconnected'))

// Dashboard component - scan events
socket.on('scan_progress', handleProgress)
socket.on('scan_log', handleLog)
```

### XML Parsing & Unicode Handling
nmap XML output can contain invalid UTF-8. Always handle encoding errors and validate file size before parsing:
```python
if not os.path.exists(xml_path) or os.path.getsize(xml_path) < 100:
    emit_progress('error', percent, 'XML file not found or too small')
    return
```

### React State Management
Uses Context pattern (no Redux). Custom hooks in `src/hooks/` for API state. Always provide fallbacks when accessing nested objects from API responses.

## File Conventions & Critical Patterns

### File Structure & Naming
- **Settings files**: JSON in backend root, loaded/saved via dedicated functions
- **Scan results**: XML files in `scans/` directory with timestamp naming
- **Database**: SQLite in `instance/` directory for dev, `/app/instance` in Docker
- **React builds**: Served directly by Flask in production via catch-all route
- **Component naming**: PascalCase for React components, kebab-case for CSS classes

### Scan Type String Matching
**Critical**: Scan types are hardcoded strings that must match exactly between frontend and backend:
```python
# Backend normalization
scan_type_normalized = scan_type.strip().lower()

# Frontend normalization  
const scanTypeNormalized = String(scanType).toLowerCase()

# Valid types: "full tcp", "iot scan", "vuln scripts"
```

### What's Up Monitoring System
Three-layer health monitoring architecture:
1. **Loopbacks**: Basic network connectivity (`LOOPBACKS` array)
2. **Services**: DNS + application health (`SERVICES` array)
3. **Infrastructure**: Critical components (`INFRASTRUCTURE` array)

Each layer builds on the previous - services check DNS resolution before connectivity.

## Docker & Deployment

- Production uses single Dockerfile with multi-stage build
- Requires `NET_ADMIN` and `NET_RAW` capabilities for nmap
- Health checks via `/api/dashboard-stats` endpoint
- Frontend build output served by Flask catch-all route

## Performance Optimizations

### Large Network Scanning
For networks >256 hosts:
- Conservative timing (T3 instead of T4)
- Reduced max retries (1 instead of 2)
- Individual host scanning fallback
- Comprehensive timeout settings

### Memory Management
- Scan results cached in SQLite, not memory
- XML files stored on disk, referenced by path
- Lazy loading for large scan result sets
