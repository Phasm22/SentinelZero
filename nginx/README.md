# Nginx Configuration for SentinelZero (Systemd Setup)

This directory contains nginx configuration for adding Authentik authentication to SentinelZero when running via systemd.

## Files

- `nginx-sentinelzero.conf` - Main nginx configuration with Authentik forward auth

## Setup Instructions

1. **Install Nginx** (if not already installed):
   ```bash
   sudo apt install nginx
   ```

2. **Copy configuration**:
   ```bash
   sudo cp nginx/nginx-sentinelzero.conf /etc/nginx/sites-available/sentinelzero
   ```

3. **Edit configuration**:
   ```bash
   sudo nano /etc/nginx/sites-available/sentinelzero
   ```
   
   Update:
   - `server_name` with your domain (e.g., `sentinelzero.prox`)
   - `upstream authentik` with your Authentik server address
   - SSL certificate paths (if using Let's Encrypt, paths are usually correct)

4. **Enable site**:
   ```bash
   sudo ln -s /etc/nginx/sites-available/sentinelzero /etc/nginx/sites-enabled/
   ```

5. **Test configuration**:
   ```bash
   sudo nginx -t
   ```

6. **Get SSL certificate** (if needed):
   ```bash
   sudo apt install certbot python3-certbot-nginx
   sudo certbot --nginx -d sentinelzero.prox
   ```

7. **Reload nginx**:
   ```bash
   sudo systemctl reload nginx
   ```

## How It Works

1. User accesses `https://sentinelzero.prox`
2. Nginx checks authentication via Authentik forward auth (`/auth` location)
3. If authenticated, request is proxied to backend on port 5000
4. Backend (systemd service) handles the request normally
5. Network scanning capabilities are preserved via systemd capabilities

## Troubleshooting

### Check nginx status:
```bash
sudo systemctl status nginx
```

### Check nginx logs:
```bash
sudo tail -f /var/log/nginx/sentinelzero-error.log
sudo tail -f /var/log/nginx/sentinelzero-access.log
```

### Test backend directly (bypass nginx):
```bash
curl http://127.0.0.1:5000/api/dashboard-stats
```

### Verify Authentik connection:
```bash
curl -v http://your-authentik-host:9000/outpost.goauthentik.io/auth/traefik
```

## Notes

- Backend continues running on port 5000 (internal)
- Nginx listens on ports 80/443 (external)
- Systemd service capabilities (NET_RAW, NET_ADMIN) are preserved
- No changes needed to backend code

