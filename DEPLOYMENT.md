# SentinelZero Deployment Guide

This guide covers different deployment strategies for SentinelZero, from simple systemd services to automated CI/CD pipelines.

## 🚀 Deployment Options

### 1. Simple SystemD Deployment (Current)
**Best for**: Single server, manual deployments
- Uses development mode (`npm run dev`)
- Manual restarts required
- No build optimization

### 2. Production SystemD Deployment (Recommended)
**Best for**: Single server, production use
- Uses production builds
- Optimized performance
- Better security
- Automated deployment scripts

### 3. GitHub Actions + Webhook Deployment
**Best for**: Automated deployments, multiple environments
- Automated testing
- Production builds
- Webhook-triggered deployments
- Rollback capabilities

## 📋 Production SystemD Setup

### Prerequisites
```bash
# Install dependencies
sudo apt update
sudo apt install -y python3 python3-pip nodejs npm nginx nmap hping3 dig curl jq git

# Install uv for Python package management
pip3 install uv

# Install serve for static file serving
npm install -g serve
```

### Installation
```bash
# Run the improved installation script
sudo ./systemd/install-systemd-improved.sh
```

### Manual Deployment
```bash
# Deploy latest changes
sudo -u sentinel ./scripts/deploy-production.sh
```

## 🔄 Automated Deployment Setup

### 1. GitHub Actions Setup

#### Required Secrets
Add these secrets to your GitHub repository:
- `HOST`: Your server IP/hostname
- `USERNAME`: SSH username (usually `sentinel`)
- `SSH_KEY`: Private SSH key for deployment

#### Workflow Features
- ✅ Automated testing on PRs
- ✅ Production builds
- ✅ Deploy only on successful builds
- ✅ Artifact caching
- ✅ Rollback on failure

### 2. Webhook Deployment

#### Setup Webhook Server
```bash
# Install webhook service
sudo cp systemd/sentinelzero-webhook.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable sentinelzero-webhook.service
sudo systemctl start sentinelzero-webhook.service
```

#### Configure GitHub Webhook
1. Go to your repository settings
2. Navigate to "Webhooks"
3. Add webhook with:
   - **Payload URL**: `http://your-server:9000`
   - **Content type**: `application/json`
   - **Secret**: Set a secure webhook secret
   - **Events**: Select "Workflow runs" and "Pushes"

#### Update Webhook Secret
```bash
# Edit the webhook service file
sudo nano /etc/systemd/system/sentinelzero-webhook.service

# Update the GITHUB_WEBHOOK_SECRET environment variable
# Restart the service
sudo systemctl restart sentinelzero-webhook.service
```

## 🏗️ Architecture Comparison

### Current Setup (Development Mode)
```
┌─────────────────┐    ┌─────────────────┐
│   Nginx (80)    │    │   Frontend      │
│   (Optional)    │────│   (npm run dev) │
└─────────────────┘    └─────────────────┘
                                │
                       ┌─────────────────┐
                       │   Backend       │
                       │   (Python)      │
                       └─────────────────┘
```

### Recommended Production Setup
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Nginx (80)    │────│   Frontend      │    │   Backend       │
│   (Reverse      │    │   (Production   │    │   (Python)      │
│    Proxy)       │    │    Build)       │    │   (Port 5000)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🔧 Service Management

### View Logs
```bash
# Backend logs
journalctl -u sentinelzero-backend.service -f

# Frontend logs
journalctl -u sentinelzero-frontend.service -f

# Webhook logs
journalctl -u sentinelzero-webhook.service -f
```

### Restart Services
```bash
# Restart all services
sudo systemctl restart sentinelzero-backend.service
sudo systemctl restart sentinelzero-frontend.service

# Or restart individually
sudo systemctl restart sentinelzero-backend.service
```

### Health Checks
```bash
# Check service status
systemctl status sentinelzero-backend.service
systemctl status sentinelzero-frontend.service

# Test endpoints
curl http://localhost:5000/api/health
curl http://localhost:3173
```

## 🚨 Troubleshooting

### Common Issues

#### 1. Services Not Starting
```bash
# Check logs
journalctl -u sentinelzero-backend.service --no-pager

# Check permissions
ls -la /home/sentinel/SentinelZero/
```

#### 2. Frontend Build Issues
```bash
# Rebuild frontend
cd /home/sentinel/SentinelZero/frontend/react-sentinelzero
npm ci
npm run build
```

#### 3. Backend Dependencies
```bash
# Update Python dependencies
cd /home/sentinel/SentinelZero/backend
uv sync
```

### Performance Optimization

#### 1. Nginx Configuration
```nginx
# Add to nginx config for better performance
location / {
    # Enable gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript;
    
    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

#### 2. SystemD Resource Limits
```ini
# Add to service files
MemoryMax=512M
LimitNOFILE=65536
```

## 🔐 Security Considerations

### 1. Firewall Rules
```bash
# Allow only necessary ports
sudo ufw allow 22    # SSH
sudo ufw allow 80    # HTTP
sudo ufw allow 443   # HTTPS
sudo ufw enable
```

### 2. SSL/TLS Setup
```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d your-domain.com
```

### 3. Service Security
- Services run as non-root user (`sentinel`)
- Restricted file system access
- No new privileges
- Private temporary directories

## 📊 Monitoring

### 1. Health Endpoints
- Backend: `http://localhost:5000/api/health`
- Frontend: `http://localhost:3173`
- Webhook: `http://localhost:9000/health`

### 2. Log Monitoring
```bash
# Set up log rotation
sudo nano /etc/logrotate.d/sentinelzero
```

### 3. Performance Monitoring
```bash
# Monitor resource usage
htop
systemctl status sentinelzero-backend.service
```

## 🎯 Recommended Approach

For your use case, I recommend:

1. **Start with Production SystemD**: Use the improved systemd setup for better performance
2. **Add GitHub Actions**: For automated testing and builds
3. **Implement Webhook Deployment**: For automated deployments on successful builds
4. **Add Monitoring**: Set up health checks and alerting

This gives you the best of both worlds: reliable production deployment with automated CI/CD when you're ready for it.