# SentinelZero Startup Guide

This guide explains how to start and manage SentinelZero in both development and production environments.

## 🚀 Quick Start

### Development Mode
```bash
# Start both frontend and backend
./start-dev.sh

# Check status
./status.sh

# Stop all services
./stop-dev.sh
```

### Production Mode
```bash
# Build frontend and start with systemd
./start-prod.sh

# Check status
./status.sh

# Stop production service
sudo systemctl stop sentinelzero
```

## 📋 Available Scripts

| Script | Purpose | Description |
|--------|---------|-------------|
| `./start-dev.sh` | Development | Starts both frontend (3173) and backend (5000) with process management |
| `./stop-dev.sh` | Development | Stops all development processes and cleans up |
| `./start-prod.sh` | Production | Builds frontend and starts backend with systemd |
| `./status.sh` | Status | Shows status of all services and processes |

## 🔧 Port Configuration

- **Backend**: Port 5000 (http://localhost:5000)
- **Frontend**: Port 3173 (http://localhost:3173)
- **Production**: Frontend served through backend on port 5000

## 🛠️ Development Mode Features

### Process Management
- Automatically kills existing processes on target ports
- Prevents port conflicts and zombie processes
- Graceful shutdown with cleanup

### Health Checks
- Backend API connectivity test
- Frontend accessibility test
- Real-time status monitoring

### Logging
- Backend logs: `/tmp/sentinelzero-backend.log`
- Frontend logs: `/tmp/sentinelzero-frontend.log`
- Real-time log following during startup

### Error Handling
- Automatic retry on startup failures
- Clear error messages with troubleshooting hints
- Process cleanup on errors

## 🏭 Production Mode Features

### Systemd Integration
- Service file: `/etc/systemd/system/sentinelzero.service`
- Automatic startup on boot
- Process monitoring and restart
- Centralized logging via journald

### Frontend Build
- Production-optimized build
- Static file serving through Flask
- No separate frontend server needed

### Security
- Restricted file system access
- No new privileges
- Private temporary directories

## 🔍 Troubleshooting

### Port Already in Use
```bash
# Check what's using the port
lsof -i :5000
lsof -i :3173

# Kill processes manually
sudo kill -9 $(lsof -ti:5000)
sudo kill -9 $(lsof -ti:3173)
```

### Service Won't Start
```bash
# Check systemd service status
sudo systemctl status sentinelzero

# View service logs
sudo journalctl -u sentinelzero -f

# Restart service
sudo systemctl restart sentinelzero
```

### Development Issues
```bash
# Check process status
./status.sh

# View logs
tail -f /tmp/sentinelzero-backend.log
tail -f /tmp/sentinelzero-frontend.log

# Clean restart
./stop-dev.sh
./start-dev.sh
```

## 📊 Monitoring

### Development
- Real-time log following during startup
- Process status monitoring
- Health check endpoints

### Production
- Systemd service monitoring
- Journald logging
- Process restart on failure

## 🔄 Service Management

### Development
```bash
# Start
./start-dev.sh

# Stop
./stop-dev.sh

# Status
./status.sh
```

### Production
```bash
# Start
./start-prod.sh

# Stop
sudo systemctl stop sentinelzero

# Restart
sudo systemctl restart sentinelzero

# Status
sudo systemctl status sentinelzero

# Logs
sudo journalctl -u sentinelzero -f
```

## 🎯 Best Practices

1. **Always use the provided scripts** - Don't start services manually
2. **Check status before starting** - Use `./status.sh` to see current state
3. **Clean shutdown** - Always use `./stop-dev.sh` or systemctl stop
4. **Monitor logs** - Check logs if services fail to start
5. **Port management** - Scripts handle port conflicts automatically

## 🚨 Emergency Recovery

If services are completely stuck:

```bash
# Nuclear option - kill everything
sudo pkill -f "python.*app.py"
sudo pkill -f "vite"
sudo pkill -f "node.*vite"
sudo lsof -ti:5000 | xargs -r kill -9
sudo lsof -ti:3173 | xargs -r kill -9

# Clean start
./start-dev.sh
```

## 📝 Notes

- Development mode uses separate frontend and backend servers
- Production mode serves frontend through backend (single port)
- All scripts include comprehensive error handling
- Process cleanup is automatic on script exit
- Logs are automatically rotated and managed
