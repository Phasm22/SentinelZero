# SentinelZero Deployment Options

## 🐳 Docker (Recommended)

### Advantages:
- ✅ **Isolated Environment**: Complete containerization with all dependencies
- ✅ **Easy Deployment**: Single command setup with `./deploy.sh`
- ✅ **Security**: Proper capability management for network scanning
- ✅ **Portability**: Runs consistently across different systems
- ✅ **Resource Control**: Built-in CPU/memory limits
- ✅ **Auto-scaling**: Easy horizontal scaling with Docker Swarm/Kubernetes
- ✅ **Updates**: Simple container updates without system changes
- ✅ **Rollback**: Easy rollback to previous versions

### Quick Start:
```bash
# Install Docker and Docker Compose first
./deploy.sh
```

### Management:
```bash
# View logs
docker-compose logs -f

# Restart services
docker-compose restart

# Stop everything
docker-compose down

# Update
docker-compose pull && docker-compose up -d
```

### Production Ready Features:
- Health checks
- Automatic restarts
- Resource limits
- Security hardening
- Nginx reverse proxy included
- SSL/TLS ready

---

## ⚙️ SystemD

### Advantages:
- ✅ **Native Integration**: Direct OS service management
- ✅ **Lower Overhead**: No containerization layer
- ✅ **System Logging**: Integrated with journald
- ✅ **Process Management**: Advanced service controls

### Disadvantages:
- ❌ **Dependency Hell**: Manual management of Python, Node.js, nmap versions
- ❌ **System Pollution**: Installs packages globally
- ❌ **Security Concerns**: Runs directly on host system
- ❌ **Platform Dependent**: Tied to specific OS configuration
- ❌ **Update Complexity**: Potential conflicts with system updates

### Quick Start:
```bash
# Run as root
sudo ./systemd/install-systemd.sh
```

### Management:
```bash
# View logs
journalctl -u sentinelzero-backend.service -f

# Restart services
systemctl restart sentinelzero-backend.service

# Stop services
systemctl stop sentinelzero-backend.service

# Check status
systemctl status sentinelzero-backend.service
```

---

## 🏆 Recommendation: Docker

**For production deployment, Docker is strongly recommended because:**

1. **Security**: Network scanning requires elevated privileges - Docker provides better isolation
2. **Reliability**: Consistent environment across development and production
3. **Maintenance**: Easier updates and dependency management
4. **Scalability**: Ready for load balancing and multiple instances
5. **Monitoring**: Better integration with monitoring tools

## 🚀 Production Deployment Commands

### Docker (Recommended):
```bash
# One-time setup
./deploy.sh

# Production with SSL
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### SystemD (Alternative):
```bash
# One-time setup
sudo ./systemd/install-systemd.sh

# Enable auto-start
sudo systemctl enable sentinelzero-backend.service
```

## 📊 Resource Requirements

| Deployment | RAM | CPU | Disk | Network |
|------------|-----|-----|------|---------|
| Docker     | 512MB-1GB | 0.5-1 cores | 2GB | Host network or bridge |
| SystemD    | 256MB-512MB | 0.25-0.5 cores | 1GB | Direct host access |

## 🔧 Configuration

Both methods support environment variables for configuration:
- `SCAN_NETWORK`: Target network range (default: 172.16.0.0/22)
- `MAX_HOSTS`: Maximum hosts to scan (default: 100)
- `FLASK_ENV`: Environment mode (production/development)

Choose Docker for production reliability and SystemD for development simplicity!
