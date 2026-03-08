# Authentik Setup for SentinelZero

## Architecture Overview

**This machine (sentinelzero.prox):**
- Runs SentinelZero via **systemd services**
  - Backend: `http://172.16.0.198:5000`
  - Frontend: `http://172.16.0.198:3173`
- No authentication code needed (forward auth handles it)
- No local Traefik or Authentik installation

**Remote box (auth.ops.prox):**
- Runs **Traefik** (reverse proxy)
- Runs **Authentik** (SSO provider)
- Handles all authentication via forward auth middleware

## How It Works

```
User → https://sentinelzero.prox
  ↓
Traefik (remote box)
  ↓
Authentik forward auth check (remote box)
  ↓ (if authenticated)
Routes to → http://172.16.0.198:3173 (this machine)
  ↓
Frontend proxies /api & /socket.io → Backend (port 5000)
```

## Configuration Files

The `traefik/dynamic/` folder contains configs for the **remote Traefik server**:

**`traefik/dynamic/authentik.yml`**
- Authentik forward auth middleware
- Points to: `https://auth.ops.prox/outpost.goauthentik.io/auth/traefik`
- Defines redirect and WebSocket headers

**`traefik/dynamic/sentinelzero.yml`**
- Routes `sentinelzero.prox` → `http://172.16.0.198:3173` (frontend)
- Applies `auth@file` middleware (Authentik)
- Frontend proxies `/api` and `/socket.io` to backend (port 5000)

## Setup Instructions

### On This Machine (sentinelzero.prox)

1. **Ensure services are running:**
   ```bash
   sudo systemctl status sentinelzero-backend  # Port 5000
   sudo systemctl status sentinelzero-frontend # Port 3173
   ```

2. **Disable nginx** (if using Traefik):
   ```bash
   sudo systemctl stop nginx && sudo systemctl disable nginx
   ```

3. **Verify services are accessible:**
   ```bash
   curl http://172.16.0.198:5000/api/dashboard-stats
   curl http://172.16.0.198:3173
   ```

### On Remote Traefik Server (auth.ops.prox)

1. **Copy Traefik configs to remote server:**
   ```bash
   scp traefik/dynamic/*.yml user@auth.ops.prox:/path/to/traefik/dynamic/
   ```

2. **Ensure DNS points to Traefik server:**
   ```
   sentinelzero.prox → [Traefik server IP]
   ```

3. **Verify Traefik picks up configs:**
   - Check Traefik dashboard for new routes
   - Test: `https://sentinelzero.prox`

### On Authentik Server (auth.ops.prox)

1. **Create application in Authentik:**
   - Use the Authentik web UI or import a blueprint
   - Configure proxy provider with `forward_single` mode
   - Set external host: `https://sentinelzero.prox`

2. **Verify outpost is running:**
   ```bash
   curl https://auth.ops.prox/outpost.goauthentik.io/auth/traefik
   ```

## Troubleshooting

### Services not accessible
```bash
# Check if services are running
sudo systemctl status sentinelzero-backend
sudo systemctl status sentinelzero-frontend

# Check if ports are listening
sudo netstat -tlnp | grep -E '5000|3173'
```

### Authentication not working
- Verify Authentik outpost is running on remote server
- Check Traefik logs on remote server
- Ensure `traefik/dynamic/authentik.yml` has correct Authentik URL

### Frontend can't reach backend
- Frontend Vite config should proxy `/api` and `/socket.io` to `http://localhost:5000`
- Verify backend is accessible: `curl http://172.16.0.198:5000/api/dashboard-stats`

## Alternative: Nginx Setup

If you prefer nginx over Traefik, see the `nginx/` folder for alternative configurations.
