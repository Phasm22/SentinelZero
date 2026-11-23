# Traefik Configuration for Remote Server

## Overview

These configuration files are for the **remote Traefik server** (auth.ops.prox), NOT for this machine.

This machine (sentinelzero.ops.prox) runs SentinelZero via systemd:
- App (API + static UI + Socket.IO): port **5000** (`sentinelzero.service`)
- Vite on 3173 is **dev-only** and should be disabled in production

The remote Traefik server handles:
- Reverse proxy routing
- SSL/TLS termination
- Authentik forward authentication

## Files in This Directory

### `dynamic/authentik.yml`
Defines Traefik middlewares:
- **auth** - Forward auth to Authentik (`https://auth.ops.prox/outpost.goauthentik.io/auth/traefik`)
- **redirect-to-https** - HTTP to HTTPS redirect
- **websocket-headers** - Headers for Socket.IO support

### `dynamic/sentinelzero.yml`
Defines Traefik routing:
- **sentinelzero-http** - HTTP router (redirects to HTTPS)
- **sentinelzero** - HTTPS router with Authentik auth
- **sentinelzero-app** - Service pointing to `http://172.16.0.198:5000`

## Setup on Remote Traefik Server

### 1. Copy Configuration Files

```bash
# From this machine, copy to remote Traefik server
scp traefik/dynamic/*.yml user@auth.ops.prox:/path/to/traefik/dynamic/
```

Or manually copy the contents of:
- `traefik/dynamic/authentik.yml`
- `traefik/dynamic/sentinelzero.yml`

### 2. Traefik Configuration Requirements

Ensure your Traefik static configuration includes:

```yaml
# traefik.yml or command args
providers:
  file:
    directory: /etc/traefik/dynamic
    watch: true

entryPoints:
  web:
    address: :80
  websecure:
    address: :443

certificatesResolvers:
  letsencrypt:
    acme:
      tlsChallenge: true
      email: your-email@example.com
      storage: /letsencrypt/acme.json
```

### 3. DNS Configuration

Point the domain to your Traefik server:

```
sentinelzero.ops.prox → [Traefik server IP]
```

### 4. Verify Configuration

```bash
# Check Traefik picks up the configs
docker logs traefik  # or check logs

# Test routing
curl -I https://sentinelzero.ops.prox
```

### 5. Authentik Setup

Ensure Authentik is configured with:
- Proxy provider in `forward_single` mode
- External host: `https://sentinelzero.ops.prox`
- Outpost running and accessible at: `https://auth.ops.prox/outpost.goauthentik.io/auth/traefik`

## How It Works

```
User Request
  ↓
https://sentinelzero.ops.prox
  ↓
Traefik (remote server)
  ├─ Matches Host(`sentinelzero.ops.prox`)
  ├─ Applies auth@file middleware
  │   └─ Forward auth to Authentik
  │       └─ If authenticated: continue
  │       └─ If not: redirect to login
  ├─ Applies websocket-headers@file
  └─ Proxies to http://172.16.0.198:5000
      ↓
SentinelZero Flask app (this machine)
  ├─ Serves React dist
  ├─ Handles /api
  └─ Handles /socket.io
```

## Updating Configuration

If you need to change the configuration:

1. Edit files in `traefik/dynamic/` on this machine
2. Copy updated files to remote Traefik server
3. Traefik will auto-reload (if `watch: true` is enabled)

## Troubleshooting

### Check Traefik logs
```bash
# Docker
docker logs traefik -f

# Systemd
journalctl -u traefik -f
```

### Test Authentik forward auth
```bash
curl -v https://auth.ops.prox/outpost.goauthentik.io/auth/traefik
```

### Verify routing
```bash
# Should redirect to HTTPS
curl -I http://sentinelzero.ops.prox

# Should require auth or redirect to login
curl -I https://sentinelzero.ops.prox
```

### Check backend accessibility from Traefik server
```bash
# From the Traefik server
curl http://172.16.0.198:5000/api/dashboard-stats
```

## Notes

- These configs use file provider, not Docker labels
- TLS is terminated by Traefik. In the homelab deployment, `*.ops.prox`
  is covered by the internal self-signed certificate.
- WebSocket support is included for Socket.IO
- No changes needed to SentinelZero backend code
- All authentication is handled at the Traefik layer
