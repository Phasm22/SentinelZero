#!/bin/bash
cd /home/sentinel/SentinelZero/backend
export PATH="/home/sentinel/.local/bin:$PATH"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BACKEND_PORT=5000

# Function to check if port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
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
    
    # Kill any existing Python app.py processes
    pkill -f "python.*app.py" 2>/dev/null || true
    
    # Kill any processes on our target port
    kill_port $BACKEND_PORT
    
    # Wait for processes to actually terminate
    sleep 3
    
    # Double-check and force kill if needed
    pkill -9 -f "python.*app.py" 2>/dev/null || true
    
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

# Run cleanup before starting
cleanup_processes

echo -e "${GREEN}🚀 Starting SentinelZero backend...${NC}"
exec uv run python app.py
