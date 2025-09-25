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

# Show usage if help requested
if [[ "$1" == "--help" || "$1" == "-h" ]]; then
    echo -e "${YELLOW}Usage: $0 [--test]${NC}"
    echo -e "${YELLOW}  --test    Run tests before deployment${NC}"
    echo -e "${YELLOW}  --help    Show this help message${NC}"
    echo -e "${BLUE}====================================${NC}"
    exit 0
fi

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
    
    # Optional: Run frontend tests if --test flag is provided
    if [[ "$1" == "--test" ]]; then
        echo -e "${YELLOW}🧪 Running frontend tests...${NC}"
        if npm test -- --run; then
            echo -e "${GREEN}✅ Frontend tests passed${NC}"
        else
            echo -e "${RED}❌ Frontend tests failed${NC}"
            exit 1
        fi
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
    # Check if service file already exists
    if [ -f "/etc/systemd/system/$SERVICE_NAME.service" ]; then
        echo -e "${YELLOW}⚙️  Systemd service already exists, skipping installation...${NC}"
        echo -e "${GREEN}✅ Systemd service ready${NC}"
        return 0
    fi
    
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
        echo -e "${YELLOW}⚠️  Service is already running, checking if restart is needed...${NC}"
        # Check if we need to restart (e.g., if code changed)
        echo -e "${YELLOW}⚠️  Service is running, skipping restart to avoid sudo prompt${NC}"
        echo -e "${GREEN}✅ Service is already running${NC}"
    else
        echo -e "${YELLOW}⚠️  Service not running, but restart requires sudo. Please run manually:${NC}"
        echo -e "${YELLOW}   sudo systemctl start $SERVICE_NAME${NC}"
        echo -e "${YELLOW}   Then run this script again${NC}"
        exit 1
    fi
    
    # Wait for service to be ready
    echo -e "${YELLOW}⏳ Waiting for service to be ready...${NC}"
    for i in {1..10}; do
        if check_service; then
            echo -e "${GREEN}✅ Service is ready${NC}"
            break
        fi
        if [ $i -eq 10 ]; then
            echo -e "${RED}❌ Service not ready after 10 seconds${NC}"
            exit 1
        fi
        sleep 1
    done
}

# Function to test connectivity
test_connectivity() {
    echo -e "${YELLOW}🔍 Testing connectivity...${NC}"
    
    # Wait a moment for the service to fully initialize
    echo -e "${YELLOW}⏳ Waiting for service to fully initialize...${NC}"
    sleep 3
    
    # Test backend with retries
    echo -e "${YELLOW}🔍 Testing backend API...${NC}"
    for i in {1..5}; do
        if curl -s http://localhost:$BACKEND_PORT/api/ping > /dev/null; then
            echo -e "${GREEN}✅ Backend API responding${NC}"
            break
        else
            if [ $i -eq 5 ]; then
                echo -e "${RED}❌ Backend API not responding after 5 attempts${NC}"
                return 1
            fi
            echo -e "${YELLOW}⏳ Attempt $i/5 failed, retrying in 2 seconds...${NC}"
            sleep 2
        fi
    done
    
    # Test frontend (served by backend)
    echo -e "${YELLOW}🔍 Testing frontend...${NC}"
    if curl -s http://localhost:$BACKEND_PORT > /dev/null; then
        echo -e "${GREEN}✅ Frontend responding${NC}"
    else
        echo -e "${RED}❌ Frontend not responding${NC}"
        return 1
    fi
}

# Function to get network IP
get_network_ip() {
    # Get the primary network interface IP
    ip route get 8.8.8.8 | awk '{print $7}' | head -1
}

# Function to show status
show_status() {
    local network_ip=$(get_network_ip)
    
    echo -e "${BLUE}====================================${NC}"
    echo -e "${GREEN}🎉 SentinelZero is running in production!${NC}"
    echo -e "${BLUE}====================================${NC}"
    echo -e "${GREEN}🌐 Local Access:${NC}"
    echo -e "${GREEN}   Application: http://localhost:$BACKEND_PORT${NC}"
    echo -e "${GREEN}   Dashboard: http://localhost:$BACKEND_PORT/dashboard${NC}"
    echo -e "${GREEN}   Settings: http://localhost:$BACKEND_PORT/settings${NC}"
    echo -e "${BLUE}====================================${NC}"
    echo -e "${GREEN}🌍 Network Access (from other clients):${NC}"
    echo -e "${GREEN}   Application: http://$network_ip:$BACKEND_PORT${NC}"
    echo -e "${GREEN}   Dashboard: http://$network_ip:$BACKEND_PORT/dashboard${NC}"
    echo -e "${GREEN}   Settings: http://$network_ip:$BACKEND_PORT/settings${NC}"
    echo -e "${BLUE}====================================${NC}"
    echo -e "${YELLOW}📋 Service management:${NC}"
    echo -e "${YELLOW}   Status:  sudo systemctl status $SERVICE_NAME${NC}"
    echo -e "${YELLOW}   Logs:    sudo journalctl -u $SERVICE_NAME -f${NC}"
    echo -e "${YELLOW}   Stop:    sudo systemctl stop $SERVICE_NAME${NC}"
    echo -e "${YELLOW}   Restart: sudo systemctl restart $SERVICE_NAME${NC}"
    echo -e "${BLUE}====================================${NC}"
}

# Backend prep with uv
prepare_backend() {
    echo -e "${YELLOW}📦 Syncing Python deps with uv...${NC}"
    cd "$BACKEND_DIR"
    uv sync --frozen || uv sync
    
    # Optional: Run tests if --test flag is provided
    if [[ "$1" == "--test" ]]; then
        echo -e "${YELLOW}🧪 Running backend tests...${NC}"
        if uv run pytest; then
            echo -e "${GREEN}✅ Backend tests passed${NC}"
        else
            echo -e "${RED}❌ Backend tests failed${NC}"
            exit 1
        fi
    else
        echo -e "${YELLOW}🧪 Skipping tests for production deployment...${NC}"
        echo -e "${YELLOW}   (Use --test flag to run tests)${NC}"
    fi
}

# Main execution
main() {
    build_frontend "$1"
    prepare_backend "$1"
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
