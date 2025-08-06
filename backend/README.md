# SentinelZero Backend

A lightweight, local network scan dashboard for cybersecurity homelabs - Backend API.

## Features

- **Network Scanning**: Orchestrates nmap scans with real-time progress tracking
- **Flask API**: RESTful API with WebSocket support for real-time updates
- **Modular Architecture**: Clean separation of concerns with services, routes, and models
- **Scheduled Scanning**: APScheduler integration for automated scans
- **Health Monitoring**: What's Up system for network infrastructure monitoring
- **Settings Management**: JSON-based configuration with automatic field normalization

## Architecture

- **Framework**: Flask with SQLAlchemy ORM
- **Database**: SQLite with scan results and alert models
- **Real-time**: Flask-SocketIO for progress updates and notifications
- **Background Jobs**: APScheduler for automated scanning
- **Testing**: pytest with coverage reporting

## Installation

```bash
# Install dependencies with uv
uv sync

# Run the application
uv run python app.py
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

## API Endpoints

- `GET /api/dashboard-stats` - Dashboard statistics
- `POST /api/scan` - Trigger network scan
- `GET /api/scans` - Get scan history
- `GET /api/settings/<section>` - Get settings
- `POST /api/settings/<section>` - Update settings

See the main project README for complete documentation.
