# SentinelZero Backend

Flask API server for network scanning with real-time updates.

## Features

- **Network Scanning** - nmap orchestration with real-time progress
- **WebSocket Updates** - Live scan progress and notifications
- **Modular Architecture** - Clean separation with services, routes, models
- **Scheduled Scans** - APScheduler integration
- **Health Monitoring** - Network infrastructure monitoring
- **Settings Management** - JSON-based configuration

## Quick Start

```bash
# Install dependencies
uv sync

# Run application
uv run python app.py

# Access: http://localhost:5000
```

## Development

```bash
# Run tests
uv run pytest

# Format code
uv run black .

# Lint code
uv run flake8 .
```

## Architecture

```
backend/
├── app.py                    # Main Flask application
└── src/
    ├── models/              # Database models
    ├── routes/               # API endpoints
    ├── services/             # Business logic
    └── config/               # Configuration
```

## API Endpoints

- `GET /api/dashboard-stats` - Dashboard statistics
- `POST /api/scan` - Trigger network scan
- `GET /api/scans` - Scan history
- `GET /api/settings/<section>` - Get settings
- `POST /api/settings/<section>` - Update settings
