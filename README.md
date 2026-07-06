# SentinelZero

**Network security scanner for cybersecurity homelabs**

[![Python](https://img.shields.io/badge/Python-3.9+-blue?style=flat-square&logo=python)](https://python.org)
[![React](https://img.shields.io/badge/React-18+-61DAFB?style=flat-square&logo=react)](https://reactjs.org)
[![Flask](https://img.shields.io/badge/Flask-2.3+-000000?style=flat-square&logo=flask)](https://flask.palletsprojects.com)

## Overview

Browser-based network scanner with real-time nmap orchestration, vulnerability detection, and comprehensive reporting.

### Features

- **Network Scanning** - TCP, IoT discovery, vulnerability scripts
- **Real-time Updates** - WebSocket-powered live progress
- **Insights & Verdicts** - Post-scan diffing with AI verdict pipeline
- **Hunter Runs** - Run history, missions, and pivot integration
- **Sensor Telemetry** - Network and endpoint agent ingest
- **Manual Upload** - Import XML from external scans (macOS WiFi)
- **Scheduled Scans** - Automated scanning with notifications
- **Lab Status** - Infrastructure health monitoring ("What's Up")
- **Modern UI** - Responsive React frontend with system theme
- **Production Ready** - Systemd service with uv package management

## Quick Start

### Production Deployment

```bash
# Start production environment
./start-prod.sh

# Access: http://localhost:5000
# Network: http://[your-ip]:5000
```

### Development

```bash
# Start development environment
./start-dev.sh

# Access: http://localhost:3173 (frontend) + http://localhost:5000 (backend)
```

### Manual Setup

```bash
# Backend
cd backend
uv sync
uv run python app.py

# Frontend (new terminal)
cd frontend/react-sentinelzero
npm install
npm run dev
```

## Project Structure

```
SentinelZero/
├── backend/                    # Flask API server
│   ├── src/                   # Modular architecture
│   │   ├── models/           # Database models
│   │   ├── routes/           # API endpoints
│   │   ├── services/         # Business logic
│   │   └── config/           # Configuration
│   └── app.py                # Main application
├── frontend/react-sentinelzero/ # React frontend
├── agent/                     # Hunter agent + pivot engine (LLM-driven scan analysis)
├── start-prod.sh             # Production deployment
├── start-dev.sh              # Development environment
└── sentinelzero.service      # Systemd service
```

## Configuration

JSON-based settings managed through web interface:

- **Network Settings** - Target networks, scan parameters
- **Security Settings** - Scan types, OS detection
- **Notifications** - Pushover integration
- **Scheduled Scans** - Automated scanning

## Development

```bash
# Backend
cd backend
uv sync
uv run pytest
uv run black .

# Frontend
cd frontend/react-sentinelzero
npm install
npm run dev
npm run lint
```

## Service Management

```bash
# Production
sudo systemctl status sentinelzero
sudo systemctl restart sentinelzero
sudo journalctl -u sentinelzero -f

# Development
./start-dev.sh
./cleanup-sentinelzero.sh cleanup
```

## Authentication & Deployment

### Systemd Services (Production - Current Setup)

This machine runs SentinelZero via systemd services:
- Backend: port 5000
- Frontend: port 3173

Authentication is handled by **remote Traefik + Authentik** (forward auth).

See **[AUTHENTIK_SETUP.md](AUTHENTIK_SETUP.md)** for complete setup instructions.

### Docker (Development/Testing)

For standalone deployment without authentication:

```bash
docker-compose up -d
```

See `docker-compose.yml` for configuration.

## Documentation

- **[Startup Guide](STARTUP.md)** - Dev and production scripts
- **[Deployment](DEPLOYMENT.md)** - Systemd, health checks, DB maintenance
- **[Scripts Guide](SCRIPTS.md)** - All available scripts
- **[Authentik Setup](AUTHENTIK_SETUP.md)** - SSO authentication setup
- **[Traefik Configuration](traefik/README.md)** - Remote Traefik setup
- **[Nginx Alternative](nginx/README.md)** - Alternative reverse proxy
- **[Backend Architecture](backend/src/README.md)** - Routes, services, models
- **[Backend Setup](backend/README.md)** - Installation guide
- **[Tests](backend/tests/README.md)** - Running pytest and Vitest
