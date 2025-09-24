#!/bin/bash

# SentinelZero Cleanup Script
# Kills all SentinelZero processes and frees up ports

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧹 SentinelZero Cleanup Script${NC}"
echo -e "${BLUE}==============================${NC}"

# Configuration
BACKEND_PORT=5000
FRONTEND_PORT=3173

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
    local service_name=$2
    echo -e "${YELLOW}🔍 Checking port $port ($service_name)...${NC}"
    if check_port $port; then
        echo -e "${YELLOW}⚠️  Port $port is in use, cleaning up...${NC}"
        lsof -ti:$port | xargs -r kill -9
        sleep 2
        if check_port $port; then
            echo -e "${RED}❌ Failed to free port $port${NC}"
            return 1
        else
            echo -e "${GREEN}✅ Port $port is now free${NC}"
        fi
    else
        echo -e "${GREEN}✅ Port $port is free${NC}"
    fi
}

# Function to cleanup all SentinelZero processes
cleanup_all() {
    echo -e "${YELLOW}🧹 Cleaning up all SentinelZero processes...${NC}"
    
    # Kill any existing Python app.py processes
    echo -e "${YELLOW}🔍 Killing Python app.py processes...${NC}"
    pkill -f "python.*app.py" 2>/dev/null || true
    
    # Kill any existing Vite processes
    echo -e "${YELLOW}🔍 Killing Vite processes...${NC}"
    pkill -f "vite" 2>/dev/null || true
    pkill -f "node.*vite" 2>/dev/null || true
    pkill -f "npm.*dev" 2>/dev/null || true
    
    # Kill any nmap processes
    echo -e "${YELLOW}🔍 Killing nmap processes...${NC}"
    pkill -f nmap 2>/dev/null || true
    
    # Kill processes on our target ports
    kill_port $BACKEND_PORT "Backend"
    kill_port $FRONTEND_PORT "Frontend"
    
    # Wait for processes to actually terminate
    sleep 3
    
    # Double-check and force kill if needed
    echo -e "${YELLOW}🔍 Force killing remaining processes...${NC}"
    pkill -9 -f "python.*app.py" 2>/dev/null || true
    pkill -9 -f "vite" 2>/dev/null || true
    pkill -9 -f "node.*vite" 2>/dev/null || true
    pkill -9 -f "npm.*dev" 2>/dev/null || true
    pkill -9 -f nmap 2>/dev/null || true
    
    # Wait a bit more
    sleep 2
    
    echo -e "${GREEN}✅ Process cleanup complete${NC}"
}

# Function to show what's running
show_status() {
    echo -e "${YELLOW}📊 Current status:${NC}"
    
    # Check backend port
    if check_port $BACKEND_PORT; then
        echo -e "${RED}❌ Backend port $BACKEND_PORT is in use${NC}"
        lsof -Pi :$BACKEND_PORT -sTCP:LISTEN
    else
        echo -e "${GREEN}✅ Backend port $BACKEND_PORT is free${NC}"
    fi
    
    # Check frontend port
    if check_port $FRONTEND_PORT; then
        echo -e "${RED}❌ Frontend port $FRONTEND_PORT is in use${NC}"
        lsof -Pi :$FRONTEND_PORT -sTCP:LISTEN
    else
        echo -e "${GREEN}✅ Frontend port $FRONTEND_PORT is free${NC}"
    fi
    
    # Check for Python processes
    echo -e "${YELLOW}🔍 Python processes:${NC}"
    ps aux | grep -E "(python.*app\.py|uv.*python)" | grep -v grep || echo -e "${GREEN}✅ No Python app processes found${NC}"
    
    # Check for Vite processes
    echo -e "${YELLOW}🔍 Vite processes:${NC}"
    ps aux | grep -E "(vite|npm.*dev)" | grep -v grep || echo -e "${GREEN}✅ No Vite processes found${NC}"
}

# Main execution
case "${1:-cleanup}" in
    "status")
        show_status
        ;;
    "cleanup")
        cleanup_all
        echo -e "${BLUE}==============================${NC}"
        echo -e "${GREEN}🎉 Cleanup complete!${NC}"
        echo -e "${BLUE}==============================${NC}"
        ;;
    *)
        echo -e "${YELLOW}Usage: $0 [status|cleanup]${NC}"
        echo -e "${YELLOW}  status  - Show current status${NC}"
        echo -e "${YELLOW}  cleanup - Clean up all processes (default)${NC}"
        exit 1
        ;;
esac
