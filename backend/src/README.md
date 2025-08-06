# SentinelZero Modular Architecture

This document explains the new modular structure for SentinelZero, designed to improve maintainability and code organization.

## 🏗️ Architecture Overview

The monolithic `app.py` (~2000 lines) has been refactored into a clean modular structure:

```
backend/
├── app.py                    # New modular entry point
├── app_modular.py           # Modular application factory
├── app_monolithic_backup.py # Original monolithic backup
├── migrate.py               # Migration helper script
└── src/
    ├── models/
    │   ├── __init__.py
    │   ├── scan.py          # Scan database model
    │   └── alert.py         # Alert database model
    ├── routes/
    │   ├── __init__.py
    │   ├── scan_routes.py   # Scan-related API endpoints
    │   ├── settings_routes.py # Settings API endpoints
    │   ├── schedule_routes.py # Scheduler API endpoints
    │   └── api_routes.py    # General API endpoints
    ├── services/
    │   ├── __init__.py
    │   ├── scanner.py       # Nmap scan orchestration
    │   ├── notifications.py # Pushover notifications
    │   └── whats_up.py      # Network health monitoring
    ├── utils/
    │   └── __init__.py
    └── config/
        ├── __init__.py
        ├── database.py      # Database configuration
        └── scheduler.py     # APScheduler configuration
```

## 🔄 Migration Process

### Quick Migration

```bash
# Switch to modular structure
cd backend
python migrate.py modular

# Test the new structure
python app.py

# If issues arise, revert
python migrate.py monolithic
```

### Manual Migration Steps

1. **Backup Original**
   ```bash
   cp app.py app_monolithic_backup.py
   ```

2. **Switch to Modular**
   ```bash
   cp app_modular.py app.py
   ```

3. **Test Application**
   ```bash
   python app.py
   ```

4. **Verify Functionality**
   - Test scan triggers
   - Verify settings save/load
   - Check WebSocket connections
   - Validate scheduled scans

## 📋 Key Components

### Models (`src/models/`)
- **`scan.py`**: Scan database model with all fields and relationships
- **`alert.py`**: Alert database model for notifications

### Routes (`src/routes/`)
- **`scan_routes.py`**: `/api/scan`, `/api/clear-scan/<id>`
- **`settings_routes.py`**: `/api/settings` (GET/POST with field normalization)
- **`schedule_routes.py`**: `/api/scheduled-scans` (GET/POST)
- **`api_routes.py`**: `/api/dashboard-stats`, `/api/scans`, `/api/alerts`, `/api/health`

### Services (`src/services/`)
- **`scanner.py`**: Nmap scan orchestration with progress tracking
- **`notifications.py`**: Pushover notification system
- **`whats_up.py`**: Network health monitoring service

### Configuration (`src/config/`)
- **`database.py`**: SQLAlchemy initialization
- **`scheduler.py`**: APScheduler background service setup

## 🔧 Development Workflow

### Running the Application

```bash
# Development mode
cd backend
export FLASK_ENV=development
python app.py

# Production mode
python app.py
```

### Adding New Features

1. **New Route**: Add to appropriate routes file or create new blueprint
2. **New Model**: Add to `src/models/` and update `__init__.py`
3. **New Service**: Add to `src/services/` for business logic
4. **New Configuration**: Add to `src/config/` for settings

### Testing

```bash
# Backend tests
cd backend
python -m pytest tests/

# Frontend tests (from frontend/)
npm run test:playwright
```

## 🚀 Benefits

### Code Organization
- **Separation of Concerns**: Routes, models, and services are clearly separated
- **Maintainability**: Smaller, focused files instead of monolithic structure
- **Reusability**: Services can be imported and used across different routes

### Development Experience
- **Easier Navigation**: Find code quickly in organized structure
- **Reduced Conflicts**: Multiple developers can work on different modules
- **Testing**: Unit tests can focus on individual components

### Scalability
- **Blueprint Pattern**: Easy to add new API sections
- **Service Layer**: Business logic separated from request handling
- **Configuration**: Settings managed in dedicated configuration layer

## 🔍 Key Differences from Monolithic

### Before (Monolithic)
```python
# Everything in app.py (~2000 lines)
@app.route('/api/scan', methods=['POST'])
def trigger_scan():
    # Scan logic mixed with route logic
    # Direct database access
    # Settings loading inline
```

### After (Modular)
```python
# Clean separation
# routes/scan_routes.py
@bp.route('/scan', methods=['POST'])
def trigger_scan():
    # Route logic only
    # Calls service layer
    
# services/scanner.py
def run_nmap_scan(...):
    # Pure business logic
    # Focused responsibility
```

## 📝 Migration Checklist

- [ ] Run migration script: `python migrate.py modular`
- [ ] Test application startup: `python app.py`
- [ ] Verify scan functionality
- [ ] Test settings save/load
- [ ] Check WebSocket connections
- [ ] Validate scheduled scans
- [ ] Test alert system
- [ ] Verify What's Up monitoring
- [ ] Update deployment scripts if needed
- [ ] Update documentation

## 🔄 Rollback Plan

If issues arise, rollback is simple:

```bash
python migrate.py monolithic
```

This restores the original monolithic structure while preserving the modular files for future use.

## 🎯 Next Steps

1. **Complete Migration**: Use the modular structure as the new default
2. **Enhanced Testing**: Add unit tests for individual services
3. **Documentation**: Update API documentation for new structure
4. **Deployment**: Update Docker and systemd configurations
5. **Monitoring**: Add health checks for individual services

## 💡 Tips

- **Import Errors**: Normal during development - install dependencies with `uv sync`
- **Database**: Uses same SQLite database, no migration needed
- **Settings**: All JSON settings files remain unchanged
- **Frontend**: No changes needed - API endpoints remain the same

The modular structure maintains 100% API compatibility while dramatically improving code organization and maintainability.
