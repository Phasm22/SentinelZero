#!/bin/bash

echo "🔍 SentinelZero Socket Connection Diagnostics"
echo "=============================================="
echo

# Check if backend is running
echo "1. Checking if backend is running on port 5000..."
if netstat -tlnp 2>/dev/null | grep -q :5000; then
    echo "✅ Backend is running on port 5000"
else
    echo "❌ Backend is NOT running on port 5000"
    echo "   To start backend: cd backend && uv run python app.py"
fi
echo

# Check if frontend dev server is running  
echo "2. Checking if frontend dev server is running on port 3173..."
if netstat -tlnp 2>/dev/null | grep -q :3173; then
    echo "✅ Frontend dev server is running on port 3173"
else
    echo "❌ Frontend dev server is NOT running on port 3173"
    echo "   To start frontend: cd frontend/react-sentinelzero && npm run dev"
fi
echo

# Check network connectivity
echo "3. Testing network connectivity..."
if curl -s http://localhost:5000/api/dashboard-stats >/dev/null 2>&1; then
    echo "✅ Backend API is accessible"
else
    echo "❌ Backend API is NOT accessible"
    echo "   Check if backend server is running and listening on all interfaces"
fi
echo

# Check Socket.IO endpoint specifically
echo "4. Testing Socket.IO endpoint..."
if curl -s "http://localhost:5000/socket.io/?EIO=4&transport=polling" >/dev/null 2>&1; then
    echo "✅ Socket.IO endpoint is accessible"
else
    echo "❌ Socket.IO endpoint is NOT accessible"
    echo "   This indicates Socket.IO server is not properly configured"
fi
echo

echo "🚀 Next steps:"
echo "1. If backend is not running: cd backend && uv run python app.py"
echo "2. If frontend is not running: cd frontend/react-sentinelzero && npm run dev"
echo "3. Check browser console for detailed Socket.IO connection logs"
echo "4. Verify no firewall is blocking ports 5000 or 3173"
