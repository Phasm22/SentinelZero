#!/bin/bash
set -euo pipefail

cd /home/sentinel/SentinelZero/backend
export PATH="/home/sentinel/.local/bin:$PATH"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration (can be overridden by systemd Environment=)
BACKEND_PORT="${SENTINEL_BIND_PORT:-5000}"
BACKEND_HOST="${SENTINEL_BIND_HOST:-0.0.0.0}"
SCAN_TIMEOUT_SECONDS="${SCAN_TIMEOUT_SECONDS:-1800}"

# Function to check if port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

require_command() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo -e "${RED}❌ Missing required command: ${cmd}${NC}"
        exit 1
    fi
}

require_writable_dir() {
    local dir="$1"
    mkdir -p "$dir"
    if [ ! -w "$dir" ]; then
        echo -e "${RED}❌ Directory is not writable: ${dir}${NC}"
        exit 1
    fi
}

validate_port() {
    if ! [[ "$BACKEND_PORT" =~ ^[0-9]+$ ]] || [ "$BACKEND_PORT" -lt 1 ] || [ "$BACKEND_PORT" -gt 65535 ]; then
        echo -e "${RED}❌ Invalid SENTINEL_BIND_PORT: ${BACKEND_PORT}${NC}"
        exit 1
    fi
}

preflight_checks() {
    echo -e "${YELLOW}🧪 Running startup preflight checks...${NC}"
    require_command uv
    require_command nmap
    require_command lsof
    require_command pkill
    require_command pgrep
    validate_port

    require_writable_dir "/home/sentinel/SentinelZero/backend/scans"
    require_writable_dir "/home/sentinel/SentinelZero/backend/instance"
    require_writable_dir "/home/sentinel/SentinelZero/backend/logs"

    if [ ! -f "/home/sentinel/SentinelZero/backend/network_settings.json" ]; then
        echo -e "${YELLOW}⚠️  network_settings.json not found, using defaults${NC}"
    fi

    echo -e "${GREEN}✅ Preflight checks passed${NC}"
    echo -e "${GREEN}ℹ️  Bind: ${BACKEND_HOST}:${BACKEND_PORT} | Scan timeout: ${SCAN_TIMEOUT_SECONDS}s${NC}"
}

# Function to kill processes on specific ports
kill_port() {
    local port=$1
    echo -e "${YELLOW}🔍 Checking port $port...${NC}"
    if check_port $port; then
        echo -e "${YELLOW}⚠️  Port $port is in use, cleaning up...${NC}"
        lsof -ti:$port | xargs -r kill -9
        sleep 2
        if check_port $port; then
            echo -e "${RED}❌ Failed to free port $port${NC}"
            exit 1
        else
            echo -e "${GREEN}✅ Port $port is now free${NC}"
        fi
    else
        echo -e "${GREEN}✅ Port $port is free${NC}"
    fi
}

# Function to cleanup existing processes
cleanup_processes() {
    echo -e "${YELLOW}🧹 Cleaning up existing processes...${NC}"
    
    # Kill any existing app processes (legacy dev server and gunicorn workers)
    pkill -f "python.*app.py" 2>/dev/null || true
    pkill -f "gunicorn.*app:app" 2>/dev/null || true

    # Kill any processes on our target port
    kill_port $BACKEND_PORT

    # Wait for processes to actually terminate
    sleep 3

    # Double-check and force kill if needed
    pkill -9 -f "python.*app.py" 2>/dev/null || true
    pkill -9 -f "gunicorn.*app:app" 2>/dev/null || true
    
    # Wait a bit more
    sleep 2
    
    echo -e "${GREEN}✅ Process cleanup complete${NC}"
}

# Cleanup function for graceful shutdown
cleanup() {
    echo -e "${YELLOW}🛑 Shutting down SentinelZero...${NC}"
    # Kill any nmap processes
    pkill -f nmap 2>/dev/null || true
    # Kill any Python processes from this app
    pkill -f "python.*app.py" 2>/dev/null || true
    echo -e "${GREEN}✅ Shutdown complete${NC}"
    exit 0
}

# Set up signal handlers for graceful shutdown
trap cleanup SIGTERM SIGINT

preflight_checks

# Run cleanup before starting
cleanup_processes

echo -e "${GREEN}🚀 Starting SentinelZero backend...${NC}"
exec uv run python app.py
