#!/bin/bash

# SentinelZero Development Startup Script
# Ensures clean startup on correct ports: 5000 (backend), 3173 (frontend)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BACKEND_PORT=5000
FRONTEND_PORT=3173
BACKEND_DIR="/home/sentinel/SentinelZero/backend"
FRONTEND_DIR="/home/sentinel/SentinelZero/frontend/react-sentinelzero"

echo -e "${BLUE}🛡️  SentinelZero Development Startup${NC}"
echo -e "${BLUE}====================================${NC}"

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

# Function to kill any existing SentinelZero processes
cleanup_processes() {
    echo -e "${YELLOW}🧹 Cleaning up existing processes...${NC}"
    
    # Kill any existing Python app.py processes
    pkill -f "python.*app.py" 2>/dev/null || true
    
    # Kill any existing Vite processes
    pkill -f "vite" 2>/dev/null || true
    pkill -f "node.*vite" 2>/dev/null || true
    
    # Kill any processes on our target ports
    kill_port $BACKEND_PORT
    kill_port $FRONTEND_PORT
    
    echo -e "${GREEN}✅ Process cleanup complete${NC}"
}

# Function to start backend
start_backend() {
    echo -e "${YELLOW}🚀 Starting backend on port $BACKEND_PORT...${NC}"
    cd "$BACKEND_DIR"
    
    # Check if uv is available
    if ! command -v uv &> /dev/null; then
        echo -e "${RED}❌ uv not found. Please install uv first.${NC}"
        exit 1
    fi
    
    # Start backend in background
    nohup uv run python app.py > /tmp/sentinelzero-backend.log 2>&1 &
    BACKEND_PID=$!
    echo $BACKEND_PID > /tmp/sentinelzero-backend.pid
    
    # Wait for backend to start
    echo -e "${YELLOW}⏳ Waiting for backend to start...${NC}"
    for i in {1..30}; do
        if check_port $BACKEND_PORT; then
            echo -e "${GREEN}✅ Backend started successfully on port $BACKEND_PORT${NC}"
            break
        fi
        if [ $i -eq 30 ]; then
            echo -e "${RED}❌ Backend failed to start within 30 seconds${NC}"
            echo -e "${YELLOW}📋 Backend logs:${NC}"
            tail -20 /tmp/sentinelzero-backend.log
            exit 1
        fi
        sleep 1
    done
}

# Function to start frontend
start_frontend() {
    echo -e "${YELLOW}🚀 Starting frontend on port $FRONTEND_PORT...${NC}"
    cd "$FRONTEND_DIR"
    
    # Check if npm is available
    if ! command -v npm &> /dev/null; then
        echo -e "${RED}❌ npm not found. Please install Node.js and npm first.${NC}"
        exit 1
    fi
    
    # Start frontend in background
    nohup npm run dev > /tmp/sentinelzero-frontend.log 2>&1 &
    FRONTEND_PID=$!
    echo $FRONTEND_PID > /tmp/sentinelzero-frontend.pid
    
    # Wait for frontend to start
    echo -e "${YELLOW}⏳ Waiting for frontend to start...${NC}"
    for i in {1..30}; do
        if check_port $FRONTEND_PORT; then
            echo -e "${GREEN}✅ Frontend started successfully on port $FRONTEND_PORT${NC}"
            break
        fi
        if [ $i -eq 30 ]; then
            echo -e "${RED}❌ Frontend failed to start within 30 seconds${NC}"
            echo -e "${YELLOW}📋 Frontend logs:${NC}"
            tail -20 /tmp/sentinelzero-frontend.log
            exit 1
        fi
        sleep 1
    done
}

# Function to test connectivity
test_connectivity() {
    echo -e "${YELLOW}🔍 Testing connectivity...${NC}"
    
    # Test backend
    if curl -s http://localhost:$BACKEND_PORT/api/ping > /dev/null; then
        echo -e "${GREEN}✅ Backend API responding${NC}"
    else
        echo -e "${RED}❌ Backend API not responding${NC}"
        return 1
    fi
    
    # Test frontend
    if curl -s http://localhost:$FRONTEND_PORT > /dev/null; then
        echo -e "${GREEN}✅ Frontend responding${NC}"
    else
        echo -e "${RED}❌ Frontend not responding${NC}"
        return 1
    fi
}

# Function to show status
show_status() {
    echo -e "${BLUE}====================================${NC}"
    echo -e "${GREEN}🎉 SentinelZero is running!${NC}"
    echo -e "${BLUE}====================================${NC}"
    echo -e "${GREEN}📡 Backend:  http://localhost:$BACKEND_PORT${NC}"
    echo -e "${GREEN}🌐 Frontend: http://localhost:$FRONTEND_PORT${NC}"
    echo -e "${GREEN}📊 Dashboard: http://localhost:$FRONTEND_PORT/dashboard${NC}"
    echo -e "${GREEN}⚙️  Settings: http://localhost:$FRONTEND_PORT/settings${NC}"
    echo -e "${BLUE}====================================${NC}"
    echo -e "${YELLOW}📋 Logs:${NC}"
    echo -e "${YELLOW}   Backend:  tail -f /tmp/sentinelzero-backend.log${NC}"
    echo -e "${YELLOW}   Frontend: tail -f /tmp/sentinelzero-frontend.log${NC}"
    echo -e "${YELLOW}🛑 Stop:    ./stop-dev.sh${NC}"
    echo -e "${BLUE}====================================${NC}"
}

# Function to handle cleanup on exit
cleanup_on_exit() {
    echo -e "\n${YELLOW}🛑 Shutting down SentinelZero...${NC}"
    if [ -f /tmp/sentinelzero-backend.pid ]; then
        kill $(cat /tmp/sentinelzero-backend.pid) 2>/dev/null || true
        rm -f /tmp/sentinelzero-backend.pid
    fi
    if [ -f /tmp/sentinelzero-frontend.pid ]; then
        kill $(cat /tmp/sentinelzero-frontend.pid) 2>/dev/null || true
        rm -f /tmp/sentinelzero-frontend.pid
    fi
    echo -e "${GREEN}✅ Shutdown complete${NC}"
}

# Set up signal handlers
trap cleanup_on_exit EXIT INT TERM

# Main execution
main() {
    cleanup_processes
    start_backend
    start_frontend
    
    if test_connectivity; then
        show_status
        
        # Keep script running and show logs
        echo -e "${YELLOW}📋 Press Ctrl+C to stop all services${NC}"
        echo -e "${YELLOW}📋 Monitoring logs...${NC}"
        
        # Follow both log files
        tail -f /tmp/sentinelzero-backend.log /tmp/sentinelzero-frontend.log &
        wait
    else
        echo -e "${RED}❌ Connectivity test failed${NC}"
        exit 1
    fi
}

# Run main function
main "$@"
