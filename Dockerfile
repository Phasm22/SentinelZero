# Multi-stage Docker build for SentinelZero
FROM node:18-alpine AS frontend-builder

# Build React frontend
WORKDIR /app/frontend
COPY frontend/react-sentinelzero/package*.json ./
RUN npm ci

COPY frontend/react-sentinelzero/ ./
RUN npm run build

# Production stage
FROM python:3.9-slim

# Install system dependencies including nmap and DNS tools
RUN apt-get update && apt-get install -y \
    nmap \
    netcat-openbsd \
    curl \
    dnsutils \
    && rm -rf /var/lib/apt/lists/*

# Create app user for security
RUN useradd -m -u 1000 sentinelzero && \
    mkdir -p /app/scans /app/instance && \
    chown -R sentinelzero:sentinelzero /app

WORKDIR /app

# Copy Python requirements and install
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application
COPY backend/ ./

# Copy built frontend from previous stage
COPY --from=frontend-builder /app/frontend/dist ./static/

# Move index.html to templates for Flask
RUN mkdir -p templates && \
    cp static/index.html templates/ && \
    chown -R sentinelzero:sentinelzero /app

# Create volume mount points
VOLUME ["/app/scans", "/app/instance"]

# Switch to non-root user (nmap needs to run as root for some features)
# We'll use capabilities instead
USER root

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5001/api/dashboard-stats || exit 1

# Expose ports
EXPOSE 5000

# Environment variables
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# Run the application
CMD ["python", "app.py"]
