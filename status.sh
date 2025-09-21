#!/bin/bash

# SentinelZero Status Check Script
# Shows the status of all SentinelZero services

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🛡️  SentinelZero Status Check${NC}"
echo -e "${BLUE}====================================${NC}"

# Function to check if port is in use
check_port() {
    local port=$1
    local service_name=$2
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "${GREEN}✅ $service_name (port $port) - Running${NC}"
        return 0
    else
        echo -e "${RED}❌ $service_name (port $port) - Not running${NC}"
        return 1
    fi
}

# Function to check service connectivity
check_connectivity() {
    local url=$1
    local service_name=$2
    if curl -s "$url" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ $service_name - Responding${NC}"
        return 0
    else
        echo -e "${RED}❌ $service_name - Not responding${NC}"
        return 1
    fi
}

# Function to check systemd service
check_systemd_service() {
    local service_name=$1
    if systemctl is-active --quiet $service_name 2>/dev/null; then
        echo -e "${GREEN}✅ $service_name (systemd) - Running${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠️  $service_name (systemd) - Not running${NC}"
        return 1
    fi
}

# Function to show process info
show_processes() {
    echo -e "${YELLOW}📋 Running processes:${NC}"
    ps aux | grep -E "(python.*app\.py|vite|node.*vite)" | grep -v grep | while read line; do
        echo -e "${YELLOW}   $line${NC}"
    done
}

# Function to show port usage
show_ports() {
    echo -e "${YELLOW}📋 Port usage:${NC}"
    lsof -i :5000 -i :3173 2>/dev/null | grep -v COMMAND | while read line; do
        echo -e "${YELLOW}   $line${NC}"
    done
}

# Main execution
main() {
    # Check ports
    check_port 5000 "Backend"
    check_port 3173 "Frontend"
    
    echo ""
    
    # Check connectivity
    check_connectivity "http://localhost:5000/api/ping" "Backend API"
    check_connectivity "http://localhost:3173" "Frontend"
    
    echo ""
    
    # Check systemd service
    check_systemd_service "sentinelzero"
    
    echo ""
    
    # Show additional info
    show_processes
    echo ""
    show_ports
    
    echo -e "${BLUE}====================================${NC}"
    echo -e "${YELLOW}💡 Quick commands:${NC}"
    echo -e "${YELLOW}   Start dev:  ./start-dev.sh${NC}"
    echo -e "${YELLOW}   Stop dev:   ./stop-dev.sh${NC}"
    echo -e "${YELLOW}   Start prod: ./start-prod.sh${NC}"
    echo -e "${YELLOW}   Status:     ./status.sh${NC}"
    echo -e "${BLUE}====================================${NC}"
}

# Run main function
main "$@"
