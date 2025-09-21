#!/bin/bash

# SentinelZero Development Stop Script
# Cleanly stops all development processes

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🛑 SentinelZero Development Shutdown${NC}"
echo -e "${BLUE}====================================${NC}"

# Function to kill processes by PID file
kill_by_pid_file() {
    local pid_file=$1
    local service_name=$2
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p $pid > /dev/null 2>&1; then
            echo -e "${YELLOW}🛑 Stopping $service_name (PID: $pid)...${NC}"
            kill $pid 2>/dev/null || true
            sleep 2
            
            # Force kill if still running
            if ps -p $pid > /dev/null 2>&1; then
                echo -e "${YELLOW}⚠️  Force killing $service_name...${NC}"
                kill -9 $pid 2>/dev/null || true
            fi
            
            echo -e "${GREEN}✅ $service_name stopped${NC}"
        else
            echo -e "${YELLOW}⚠️  $service_name was not running${NC}"
        fi
        rm -f "$pid_file"
    else
        echo -e "${YELLOW}⚠️  No PID file found for $service_name${NC}"
    fi
}

# Function to kill processes by pattern
kill_by_pattern() {
    local pattern=$1
    local service_name=$2
    
    if pgrep -f "$pattern" > /dev/null; then
        echo -e "${YELLOW}🛑 Stopping $service_name...${NC}"
        pkill -f "$pattern" 2>/dev/null || true
        sleep 2
        
        # Force kill if still running
        if pgrep -f "$pattern" > /dev/null; then
            echo -e "${YELLOW}⚠️  Force killing $service_name...${NC}"
            pkill -9 -f "$pattern" 2>/dev/null || true
        fi
        
        echo -e "${GREEN}✅ $service_name stopped${NC}"
    else
        echo -e "${YELLOW}⚠️  $service_name was not running${NC}"
    fi
}

# Function to check if port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Function to free port
free_port() {
    local port=$1
    local service_name=$2
    
    if check_port $port; then
        echo -e "${YELLOW}🛑 Freeing port $port ($service_name)...${NC}"
        lsof -ti:$port | xargs -r kill -9
        sleep 1
        
        if check_port $port; then
            echo -e "${RED}❌ Failed to free port $port${NC}"
            return 1
        else
            echo -e "${GREEN}✅ Port $port is now free${NC}"
        fi
    else
        echo -e "${GREEN}✅ Port $port is already free${NC}"
    fi
}

# Main execution
main() {
    # Stop by PID files first (more graceful)
    kill_by_pid_file "/tmp/sentinelzero-backend.pid" "Backend"
    kill_by_pid_file "/tmp/sentinelzero-frontend.pid" "Frontend"
    
    # Stop by process patterns (fallback)
    kill_by_pattern "python.*app.py" "Backend (pattern)"
    kill_by_pattern "vite" "Frontend (pattern)"
    kill_by_pattern "node.*vite" "Frontend Node (pattern)"
    
    # Free specific ports
    free_port 5000 "Backend"
    free_port 3173 "Frontend"
    
    # Clean up log files
    echo -e "${YELLOW}🧹 Cleaning up log files...${NC}"
    rm -f /tmp/sentinelzero-backend.log
    rm -f /tmp/sentinelzero-frontend.log
    rm -f /tmp/sentinelzero-backend.pid
    rm -f /tmp/sentinelzero-frontend.pid
    
    echo -e "${GREEN}✅ Cleanup complete${NC}"
    echo -e "${BLUE}====================================${NC}"
    echo -e "${GREEN}🎉 SentinelZero development stopped${NC}"
    echo -e "${BLUE}====================================${NC}"
}

# Run main function
main "$@"
