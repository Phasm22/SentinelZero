#!/bin/bash

# SentinelZero Production Startup Script
# Builds frontend and starts backend with systemd

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🛡️  SentinelZero Production Startup${NC}"
echo -e "${BLUE}====================================${NC}"

# Configuration
BACKEND_PORT=5000
FRONTEND_DIR="/home/sentinel/SentinelZero/frontend/react-sentinelzero"
BACKEND_DIR="/home/sentinel/SentinelZero/backend"
SERVICE_NAME="sentinelzero"

# Function to check if service is running
check_service() {
    if systemctl is-active --quiet $SERVICE_NAME; then
        return 0  # Service is running
    else
        return 1  # Service is not running
    fi
}

# Function to build frontend
build_frontend() {
    echo -e "${YELLOW}🔨 Building frontend...${NC}"
    cd "$FRONTEND_DIR"
    
    # Install dependencies if needed
    if [ ! -d "node_modules" ]; then
        echo -e "${YELLOW}📦 Installing frontend dependencies...${NC}"
        npm install
    fi
    
    # Build frontend
    echo -e "${YELLOW}🏗️  Building frontend for production...${NC}"
    npm run build
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Frontend build successful${NC}"
    else
        echo -e "${RED}❌ Frontend build failed${NC}"
        exit 1
    fi
}

# Function to install systemd service
install_service() {
    echo -e "${YELLOW}⚙️  Installing systemd service...${NC}"
    
    # Copy service file
    sudo cp "$BACKEND_DIR/../sentinelzero.service" /etc/systemd/system/
    
    # Reload systemd
    sudo systemctl daemon-reload
    
    # Enable service
    sudo systemctl enable $SERVICE_NAME
    
    echo -e "${GREEN}✅ Systemd service installed and enabled${NC}"
}

# Function to start service
start_service() {
    echo -e "${YELLOW}🚀 Starting SentinelZero service...${NC}"
    
    if check_service; then
        echo -e "${YELLOW}⚠️  Service is already running, restarting...${NC}"
        sudo systemctl restart $SERVICE_NAME
    else
        sudo systemctl start $SERVICE_NAME
    fi
    
    # Wait for service to start
    echo -e "${YELLOW}⏳ Waiting for service to start...${NC}"
    for i in {1..30}; do
        if check_service; then
            echo -e "${GREEN}✅ Service started successfully${NC}"
            break
        fi
        if [ $i -eq 30 ]; then
            echo -e "${RED}❌ Service failed to start within 30 seconds${NC}"
            echo -e "${YELLOW}📋 Service status:${NC}"
            sudo systemctl status $SERVICE_NAME
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
    
    # Test frontend (served by backend)
    if curl -s http://localhost:$BACKEND_PORT > /dev/null; then
        echo -e "${GREEN}✅ Frontend responding${NC}"
    else
        echo -e "${RED}❌ Frontend not responding${NC}"
        return 1
    fi
}

# Function to show status
show_status() {
    echo -e "${BLUE}====================================${NC}"
    echo -e "${GREEN}🎉 SentinelZero is running in production!${NC}"
    echo -e "${BLUE}====================================${NC}"
    echo -e "${GREEN}🌐 Application: http://localhost:$BACKEND_PORT${NC}"
    echo -e "${GREEN}📊 Dashboard: http://localhost:$BACKEND_PORT/dashboard${NC}"
    echo -e "${GREEN}⚙️  Settings: http://localhost:$BACKEND_PORT/settings${NC}"
    echo -e "${BLUE}====================================${NC}"
    echo -e "${YELLOW}📋 Service management:${NC}"
    echo -e "${YELLOW}   Status:  sudo systemctl status $SERVICE_NAME${NC}"
    echo -e "${YELLOW}   Logs:    sudo journalctl -u $SERVICE_NAME -f${NC}"
    echo -e "${YELLOW}   Stop:    sudo systemctl stop $SERVICE_NAME${NC}"
    echo -e "${YELLOW}   Restart: sudo systemctl restart $SERVICE_NAME${NC}"
    echo -e "${BLUE}====================================${NC}"
}

# Main execution
main() {
    build_frontend
    install_service
    start_service
    
    if test_connectivity; then
        show_status
    else
        echo -e "${RED}❌ Connectivity test failed${NC}"
        exit 1
    fi
}

# Run main function
main "$@"
