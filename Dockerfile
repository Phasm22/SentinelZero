# Multi-stage Docker build for SentinelZero
FROM node:18-alpine AS frontend-builder

# Build React frontend
WORKDIR /app/frontend
COPY frontend/react-sentinelzero/package*.json ./
ENV NODE_ENV=production
RUN npm install --omit=dev --no-audit --no-fund

COPY frontend/react-sentinelzero/ ./
RUN npm run build

# Production stage
FROM python:3.12-slim

## 1) System dependencies (runtime + build for any wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
        nmap \
        netcat-openbsd \
        curl \
        dnsutils \
        libcap2-bin \
        build-essential \
        python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user & needed dirs
RUN useradd -m -u 1000 sentinelzero && mkdir -p /app/scans /app/instance /app/backend
WORKDIR /app/backend

# Copy backend source
COPY backend/ /app/backend/

# Create requirements (mirrors pyproject dependencies)
RUN set -e; cat > requirements.txt <<'REQ'
apscheduler>=3.10.0
eventlet>=0.40.2
flask>=3.1.1
flask-cors>=6.0.1
flask-migrate>=4.1.0
flask-socketio>=5.5.1
flask-sqlalchemy>=3.1.1
psutil>=7.0.0
python-dotenv>=1.1.1
pytz>=2025.2
requests>=2.32.4
gunicorn>=20.1.0
gevent>=21.0.0
REQ
RUN pip install --no-cache-dir -r requirements.txt && rm requirements.txt && apt-get purge -y build-essential python3-dev && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

# Capabilities for nmap (allow raw sockets without root)
RUN /sbin/setcap cap_net_admin,cap_net_raw=eip /usr/bin/nmap || setcap cap_net_admin,cap_net_raw=eip /usr/bin/nmap || true

# Adjust ownership
RUN chown -R sentinelzero:sentinelzero /app

# Copy built frontend into expected path
RUN mkdir -p /app/frontend/react-sentinelzero/dist
COPY --from=frontend-builder /app/frontend/dist /app/frontend/react-sentinelzero/dist

# Also expose assets via /app/static
RUN mkdir -p /app/static && cp -r /app/frontend/react-sentinelzero/dist/* /app/static/ || true

# Move index.html to templates
RUN mkdir -p /app/templates && cp /app/frontend/react-sentinelzero/dist/index.html /app/templates/

# Create volume mount points
VOLUME ["/app/scans", "/app/instance"]

# Run as non-root; nmap binary has CAP_NET_RAW + CAP_NET_ADMIN so UDP/OS scans work
USER sentinelzero

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/api/dashboard-stats || exit 1

EXPOSE 5000

# Environment variables
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/backend

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--worker-class", "gevent", "--workers", "1", "app:app", "--access-logfile", "-"]
