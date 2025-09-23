#!/bin/bash

echo "🧹 Cleaning up all SentinelZero processes..."

# Kill all related processes
pkill -9 -f "python.*app.py" 2>/dev/null || true
pkill -9 -f "vite" 2>/dev/null || true
pkill -9 -f "node.*vite" 2>/dev/null || true
pkill -9 -f "npm.*dev" 2>/dev/null || true
pkill -9 -f "start-dev.sh" 2>/dev/null || true

# Wait for processes to die
sleep 3

# Check if ports are free
echo "🔍 Checking ports..."
if lsof -Pi :5000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  Port 5000 still in use, force killing..."
    lsof -ti:5000 | xargs -r kill -9
fi

if lsof -Pi :3173 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  Port 3173 still in use, force killing..."
    lsof -ti:3173 | xargs -r kill -9
fi

sleep 2

echo "✅ Cleanup complete. You can now run ./start-dev.sh"
exit 0
