# SentinelZero Backend Architecture

Modular Flask architecture for network scanning with real-time updates.

## Architecture

```
backend/
├── app.py                    # Main Flask application
└── src/
    ├── models/              # Database models
    │   ├── scan.py          # Scan model
    │   └── alert.py         # Alert model
    ├── routes/               # API endpoints
    │   ├── scan_routes.py   # Scan endpoints
    │   ├── settings_routes.py # Settings endpoints
    │   ├── schedule_routes.py # Scheduler endpoints
    │   └── api_routes.py    # General API endpoints
    ├── services/             # Business logic
    │   ├── scanner.py       # Nmap orchestration
    │   ├── notifications.py # Pushover notifications
    │   └── whats_up.py      # Network monitoring
    └── config/               # Configuration
        ├── database.py      # SQLAlchemy setup
        └── scheduler.py     # APScheduler setup
```

## Key Components

### Models
- **`scan.py`** - Scan database model with relationships
- **`alert.py`** - Alert database model for notifications

### Routes
- **`scan_routes.py`** - `/api/scan`, `/api/clear-scan/<id>`
- **`settings_routes.py`** - `/api/settings` (GET/POST)
- **`schedule_routes.py`** - `/api/scheduled-scans` (GET/POST)
- **`api_routes.py`** - `/api/dashboard-stats`, `/api/scans`, `/api/alerts`

### Services
- **`scanner.py`** - Nmap scan orchestration with progress tracking
- **`notifications.py`** - Pushover notification system
- **`whats_up.py`** - Network health monitoring

## Development

```bash
# Run application
uv run python app.py

# Run tests
uv run pytest

# Format code
uv run black .
```

## Benefits

- **Separation of Concerns** - Routes, models, services clearly separated
- **Maintainability** - Smaller, focused files
- **Reusability** - Services can be used across routes
- **Testing** - Unit tests focus on individual components
