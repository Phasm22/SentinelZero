#!/bin/bash

# SentinelZero SystemD Installation Script
set -e

echo "⚙️ SentinelZero SystemD Setup"
echo "=============================="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "❌ This script must be run as root"
   exit 1
fi

# Install system dependencies
echo "📦 Installing system dependencies..."
apt-get update
apt-get install -y python3 python3-pip nodejs npm nmap

# Install Python dependencies
echo "🐍 Installing Python dependencies..."
cd /root/sentinelZero/backend
pip3 install -r requirements.txt

# Install Node.js dependencies and build frontend
echo "⚛️ Building React frontend..."
cd /root/sentinelZero/frontend/react-sentinelzero
npm install
npm run build

# Copy systemd service files
echo "📋 Installing systemd services..."
cp /root/sentinelZero/systemd/*.service /etc/systemd/system/

# Reload systemd and enable services
echo "🔄 Enabling services..."
systemctl daemon-reload
systemctl enable sentinelzero-backend.service
systemctl enable sentinelzero-frontend.service

# Start services
echo "🚀 Starting services..."
systemctl start sentinelzero-backend.service
systemctl start sentinelzero-frontend.service

# Check status
echo "📊 Service status:"
systemctl status sentinelzero-backend.service --no-pager
systemctl status sentinelzero-frontend.service --no-pager

echo ""
echo "✅ SentinelZero systemd installation complete!"
echo ""
echo "🌐 Access your application at:"
echo "   - Backend: http://localhost:5000"
echo "   - Frontend: http://localhost:3173"
echo ""
echo "📊 Useful commands:"
echo "   - View logs: journalctl -u sentinelzero-backend.service -f"
echo "   - Restart: systemctl restart sentinelzero-backend.service"
echo "   - Stop: systemctl stop sentinelzero-backend.service"
echo "   - Status: systemctl status sentinelzero-backend.service"
