#!/bin/bash

# SentinelZero Docker Deployment Script
set -e

echo "🚀 SentinelZero Docker Deployment"
echo "=================================="

# Create data directories
echo "📁 Creating data directories..."
mkdir -p data/{scans,database,logs}
chmod 755 data/{scans,database,logs}

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is available
if ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not available. Please install Docker Compose first."
    exit 1
fi

# Build and start the services
echo "🔨 Building SentinelZero containers..."
docker compose build

echo "🚀 Starting SentinelZero services..."
docker compose up -d

# Wait for health check
echo "⏳ Waiting for services to be healthy..."
sleep 30

# Check if services are running
if docker compose ps | grep -q "Up"; then
    echo "✅ SentinelZero is running successfully!"
    echo ""
    echo "🌐 Access your application at:"
    echo "   - Direct: http://localhost:5000
    echo "   - Proxy: http://localhost:80 (if nginx enabled)"
    echo ""
    echo "📊 Useful commands:"
    echo "   - View logs: docker compose logs -f"
    echo "   - Stop: docker compose down"
    echo "   - Restart: docker compose restart"
    echo "   - Update: docker compose pull && docker compose up -d"
else
    echo "❌ Failed to start services. Check logs:"
    docker compose logs
    exit 1
fi
