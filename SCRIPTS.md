# SentinelZero Scripts

## Essential Scripts

### Production
- **`start-prod.sh`** - Complete production deployment
  - Builds frontend
  - Syncs backend dependencies with uv
  - Installs systemd service
  - Starts and tests the application
  - Usage: `./start-prod.sh`

### Development  
- **`start-dev.sh`** - Development environment
  - Starts backend on port 5000
  - Starts frontend dev server on port 3173
  - Handles process cleanup
  - Usage: `./start-dev.sh`

### Service Management
- **`sentinelzero.service`** - Systemd service file
  - Runs with uv in production
  - Uses eventlet async mode for Socket.IO
  - Auto-restart on failure
  - Graceful shutdown with process cleanup

### Cleanup
- **`cleanup-scans.sh`** - Manual scan cleanup
  - Kills orphaned nmap processes
  - Cancels active scans via API
  - Usage: `./cleanup-scans.sh`

- **`cleanup-sentinelzero.sh`** - Complete process cleanup
  - Kills all SentinelZero processes (Python, Vite, nmap)
  - Frees up ports 5000 and 3173
  - Handles process conflicts and port conflicts
  - Usage: `./cleanup-sentinelzero.sh [status|cleanup]`

## Service Commands

```bash
# Production service management
sudo systemctl status sentinelzero
sudo systemctl restart sentinelzero
sudo journalctl -u sentinelzero -f

# Development
./start-dev.sh          # Start development environment
Ctrl+C                  # Stop development environment

# Cleanup (when having issues)
./cleanup-sentinelzero.sh status    # Check what's running
./cleanup-sentinelzero.sh cleanup   # Clean up all processes
```

## Access URLs

- **Production**: http://localhost:5000
- **Development**: http://localhost:3173 (frontend) + http://localhost:5000 (backend)

## Removed Scripts

The following redundant scripts have been removed:
- `debug-*.sh` - Debug scripts
- `clean-restart.sh` - Redundant cleanup
- `status.sh` - Use systemctl status instead
- `deploy.sh` - Replaced by start-prod.sh
- `scripts/` directory - Redundant deploy scripts
- `systemd/` directory - Service file moved to root
- Backend cleanup scripts and old app files
