# SentinelZero Copilot Instructions

## Architecture Overview

SentinelZero is a homelab network security scanner with a modular Flask/SQLAlchemy backend and React/Vite frontend. It orchestrates nmap scans, parses XML results, and provides real-time progress via WebSockets.

**Key Components:**
- **Backend**: Modular Flask app (`backend/src/`) using Blueprints, APScheduler, and Flask-SocketIO, managed with `uv`
- **Frontend**: React SPA (`frontend/react-sentinelzero/`) with Vite, Tailwind CSS, and custom contexts
- **Database**: SQLite models for `Scan` and `Alert` in `backend/src/models/`
- **Settings**: JSON files in backend root, auto-converted between camelCase and snake_case
- **Scanning**: Background thread-based nmap execution with real-time progress tracking

## Essential Development Commands

```bash
# Full stack development (from frontend/)
npm run dev:all  # Starts both backend and frontend with concurrently

# Backend only (modular architecture)
cd backend && uv run python app.py

# Frontend only
cd frontend/react-sentinelzero && npm run dev

# Switch architectures (modular/monolithic)
cd backend && uv run python migrate.py modular|monolithic

# Testing
npm run test                  # All tests (backend + frontend)
npm run test:backend         # pytest with coverage
npm run test:playwright      # E2E tests

# Dependencies
cd backend && uv sync        # Install backend deps
cd backend && uv add pkg     # Add backend package
cd frontend/react-sentinelzero && npm install  # Frontend deps
```
## Modular Backend Architecture

```
backend/src/
├── models/              # SQLAlchemy models
│   ├── scan.py         # Scan model with progress tracking, XML storage
│   └── alert.py        # Alert model with severity levels
├── routes/             # Flask Blueprints for API endpoints
│   ├── scan_routes.py  # /api/scan, /api/clear-scan/<id>, scan triggers
│   ├── settings_routes.py # /api/settings with camelCase↔snake_case conversion
│   ├── api_routes.py   # /api/dashboard-stats, /api/network-interfaces
│   └── upload_routes.py # XML file upload handling
├── services/           # Business logic layer
│   ├── scanner.py      # Nmap orchestration with threading & progress
│   ├── notifications.py # Pushover integration for alerts
│   └── whats_up.py     # Network health monitoring (loopbacks/services)
└── config/             # Configuration management
    ├── database.py     # SQLAlchemy setup with absolute paths
    └── scheduler.py    # APScheduler background service
```

**Migration Pattern**: The system supports both modular and monolithic architectures. Use `python migrate.py modular|monolithic` to switch. The modular version separates concerns into services/routes/models for better maintainability.

## Critical Real-Time Communication Patterns

### Threading & Progress Tracking
Scans run in background threads with real-time WebSocket updates:
```python
def emit_progress(status, percent, message):
    scan.status = status
    scan.percent = percent  
    db.session.commit()
    if socketio:
        socketio.emit('scan_progress', {
            'scan_id': scan_id, 'status': status, 
            'percent': percent, 'message': message
        })
```

**Critical**: Always wrap SocketIO emissions in try/except blocks and use `with app.app_context()` for database operations in threads.

### SocketIO Event Architecture
Three primary event channels for frontend communication:
- `scan_progress`: Status updates with percentage and scan_id
- `scan_log`: Real-time nmap output streaming
- `scan_complete`: Final completion with results summary

Frontend components must handle disconnections gracefully since scans can run for extended periods.

## Nmap Command Synchronization (Critical)

**Major Integration Point**: Frontend and backend must generate identical nmap commands for user confirmation modals:

```javascript
// Frontend: ScanControls.jsx buildNmapCommand()
const buildNmapCommand = (scanType, security, targetNetwork) => {
  let cmd = ['nmap', '-v', '-T4', '-Pn']
  const scanTypeNormalized = String(scanType).toLowerCase()
  if (scanTypeNormalized === 'full tcp') {
    cmd.push('-sS', '-p-', '--open')
  }
  // Security settings application must match backend exactly
  if (security.osDetectionEnabled) cmd.push('-O')
  if (security.serviceDetectionEnabled) cmd.push('-sV')
  // ... rest must mirror backend scanner.py
}
```

```python  
# Backend: src/services/scanner.py run_nmap_scan()
scan_type_normalized = scan_type.strip().lower()
cmd = ['nmap', '-v', '-T4', '-Pn']
if scan_type_normalized == 'full tcp':
    cmd += ['-sS', '-p-', '--open']
# Security settings must match frontend exactly
```

**Testing Pattern**: When modifying scan commands, test both the frontend modal preview AND backend execution logs to ensure synchronization.

## Large Network Handling & Adaptive Scanning

The system implements intelligent network size detection and adaptive scanning strategies:

```python
def get_network_size(network):
    """Calculate number of hosts in CIDR range"""
    
# For networks >256 hosts:
network_size = get_network_size(target_network)  
if network_size > 256:
    timing_level = 'T3'  # Conservative timing
    max_retries = '1'    # Reduced retries
    # Individual host scanning fallback for nmap assertion errors
```

**Fallback Pattern**: When nmap fails with error -6 on large networks, the system automatically switches to scanning individual hosts (up to 50) spread across the network range for better coverage.

## React Context Architecture & State Management

**No Redux** - Uses React Context pattern exclusively:

```jsx
// Socket connection with automatic reconnection
export const SocketProvider = ({ children }) => {
  const [socket, setSocket] = useState(null)
  const [isConnected, setIsConnected] = useState(false)
  // Auto-detection of development vs production socket URLs
  const backendUrl = isDevelopment ? window.location.origin : 'http://${hostname}:5000'
}

// User preferences with localStorage persistence  
export const UserPreferencesProvider = ({ children }) => {
  const [preferences, setPreferences] = useState({
    use24Hour: false,
    // ... other UI preferences
  })
}
```

**Critical Pattern**: Always validate context availability and provide fallbacks when accessing nested API response objects.

## Settings & Configuration Patterns

Settings stored as JSON files (not database) with automatic field name conversion:

```
backend/
├── network_settings.json      # Target networks, max_hosts, scan timeouts
├── security_settings.json     # nmap flags, vulnerability scanning options
├── notification_settings.json # Pushover API configuration
└── scheduled_scans_settings.json # Cron schedules, target networks
```

**Field Normalization**: Backend `/api/settings` routes automatically convert between camelCase (frontend) and snake_case (backend):
```python
# Backend uses: vuln_scanning_enabled, os_detection_enabled
# Frontend receives: vulnScanningEnabled, osDetectionEnabled
```

## Vulnerability Detection & False Positive Filtering

The system implements intelligent vulnerability filtering to reduce noise:

```python
def should_include_vulnerability(vuln_id, score, has_exploit):
    # Skip very low scores unless they have active exploits
    if score < 4.0 and not has_exploit:
        return False
    # Skip known false positives
    false_positive_patterns = ['PACKETSTORM:140261', 'CVE-2025-*']
```

**Vulnerability Sources**: 
- NSE vulnerability scripts (`--script=vuln`)
- Custom vulnerability patterns from nmap XML parsing
- Vulners.com integration for CVE scoring

## Key Development Ports & URLs

- **Backend**: `http://localhost:5000`
- **Frontend Dev**: `http://localhost:3173` (Vite with HMR)
- **API Proxy**: All `/api/*` and `/socket.io/*` routes proxied through Vite
- **Production**: Single-container deployment with Flask serving React build

## Essential File Patterns & Conventions

### Database & Storage
- **SQLite**: `backend/instance/sentinelzero.db` (dev), `/app/instance/` (Docker)
- **Scan Results**: XML files in `backend/scans/` with timestamp naming
- **Logs**: Structured logging in `backend/logs/` with daily rotation

### Component Architecture
```
frontend/src/
├── components/
│   ├── ScanControls.jsx    # Critical: buildNmapCommand() must match backend
│   ├── ScanDetailsModal.jsx # Handles large scan results with performance optimization
│   └── Layout.jsx          # App shell with navigation and theme handling
├── contexts/
│   ├── SocketContext.jsx   # WebSocket connection with auto-reconnection
│   └── ToastContext.jsx    # Global notification system
└── utils/
    └── api.js              # Centralized API client with error handling
```

## Testing & Quality Assurance

```bash
# Backend testing with coverage
npm run test:backend        # pytest with coverage reports
npm run test:unit          # Unit tests only
npm run test:integration   # API endpoint tests

# Frontend E2E testing  
npm run test:playwright    # Full browser automation tests
npm run test:playwright:ui # Interactive test debugging

# Code quality
npm run lint               # ESLint + flake8
npm run format             # Prettier + black
```

**Test Organization**:
- `backend/tests/unit/` - Database models, utility functions
- `backend/tests/integration/` - API endpoints, scan execution
- Frontend E2E tests cover critical user flows (scan execution, results viewing)

## Critical Error Handling Patterns

### WebSocket Connection Resilience
```jsx
// Always provide fallbacks for socket state
const { socket, isConnected, isInitialized } = useSocket()
if (!socket || !isConnected) {
  return <LoadingSpinner message="Connecting to server..." />
}

// Backend: Graceful socket emission failures
try:
    socketio.emit('scan_progress', data)
except Exception as e:
    print(f'[DEBUG] Could not emit to socketio: {e}')
    # Continue scan execution regardless
```

### Database Operations in Threads
```python
# Always use app context for SQLAlchemy in background threads
with app.app_context():
    try:
        scan.status = 'complete'
        db.session.commit()
    except Exception:
        db.session.rollback()
        # Log error but don't crash the scan
```

### Large Scan Result Handling
```python
# XML size validation before parsing
if not os.path.exists(xml_path) or os.path.getsize(xml_path) < 100:
    emit_progress('error', percent, 'XML file not found or too small')
    return

# Unicode error handling for nmap output
try:
    tree = ET.parse(xml_path)
except ET.ParseError as e:
    # nmap XML can contain invalid UTF-8 from network probes
    emit_progress('error', 95, f'XML parse error: {str(e)}')
```

## Performance & Scalability Considerations

### Large Network Scanning Strategy
```python
def get_network_size(network):
    # Calculate hosts in CIDR notation
    return ipaddress.ip_network(network, strict=False).num_addresses

# Adaptive timing based on network size
network_size = get_network_size(target_network)
if network_size > 256:
    timing_level = 'T3'  # Conservative timing
    max_retries = '1'    # Reduced retries
    # Use individual host fallback if nmap fails
```

### Memory Management
- Scan results stored as JSON in database, not held in memory
- XML files referenced by path, loaded on-demand for viewing
- Background cleanup of old scan files based on retention settings
- Progressive loading for large scan result tables

## Docker & Production Deployment

**Multi-stage Build Pattern**:
```dockerfile
# Frontend build stage
FROM node:18 AS frontend-build
COPY frontend/react-sentinelzero/ .
RUN npm install && npm run build

# Runtime stage
FROM python:3.12
COPY --from=frontend-build /app/dist ./frontend/dist/
# Flask serves React build via catch-all route
```

**Required Capabilities**: `NET_ADMIN` and `NET_RAW` for nmap execution

## Common Development Gotchas

### Scan Command Synchronization
**Critical**: Users see scan commands in confirmation modals that must match actual execution:
```jsx
// Frontend ScanControls.jsx must exactly mirror backend scanner.py
// Test: Compare modal preview with backend execution logs
```

### React Context Patterns
```jsx
// Safe context access with fallbacks
const preferences = useUserPreferences()
const enabled = preferences?.scheduledScans?.enabled || false

// Avoid duplicate SocketIO listeners
// SocketContext handles connection events only
// Component handles scan-specific events
```

### Settings Field Naming
Backend JSON files use snake_case, but API automatically converts to camelCase for frontend consumption.

When modifying settings, always verify both the JSON structure and the API transformation layer.
