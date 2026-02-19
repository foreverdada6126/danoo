#!/bin/bash

# DaNoo v5.2 - Institutional Management Script
# This script helps you manage your 5-pillar empire without typing long commands.

# Colors for better readability
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}==========================================${NC}"
echo -e "${CYAN}    DaNoo Institutional Command Center    ${NC}"
echo -e "${CYAN}==========================================${NC}"

show_help() {
    echo "Usage: ./manage.sh [command]"
    echo ""
    echo "Commands:"
    echo "  update    - Pull latest code from GitHub and rebuild containers"
    echo "  logs      - View live logs from the Trader (danoo-core)"
    echo "  health    - Check VPS CPU, RAM, and Disk health"
    echo "  wire      - Re-connect Hostinger apps to DaNoo network"
    echo "  restart   - Clean restart of all DaNoo services"
    echo "  status    - Show which containers are currently running"
}

case "$1" in
    update)
        echo -e "${YELLOW}🚀 Pulling latest code and rebuilding...${NC}"
        git pull origin main
        docker compose up -d --build --force-recreate
        echo -e "${GREEN}✅ Update Complete!${NC}"
        ;;
    logs)
        echo -e "${YELLOW}📋 Showing live logs (Press Ctrl+C to exit)...${NC}"
        docker logs danoo-core --tail 50 -f
        ;;
    health)
        echo -e "${CYAN}📊 --- VPS HEALTH REPORT ---${NC}"
        echo -e "${GREEN}Memory Usage:${NC}"
        free -h
        echo -e "\n${GREEN}Disk Usage:${NC}"
        df -h /
        echo -e "\n${GREEN}Docker Stats:${NC}"
        docker stats --no-stream
        ;;
    wire)
        echo -e "${YELLOW}🔌 Re-wiring Hostinger Apps...${NC}"
        # Create network if missing
        docker network create danoo-net 2>/dev/null
        
        # Connect apps using their Hostinger-generated names
        docker network connect danoo-net openclaw-w1re-openclaw-1 2>/dev/null
        docker network connect danoo-net n8n-qvze-n8n-1 2>/dev/null
        docker network connect danoo-net langflow-irf9-langflow-1 2>/dev/null
        
        echo -e "${GREEN}✅ Network Wiring Refreshed.${NC}"
        ;;
    restart)
        echo -e "${RED}🔄 Restarting all services...${NC}"
        docker compose down
        docker compose up -d
        echo -e "${GREEN}✅ Services Restarted.${NC}"
        ;;
    status)
        echo -e "${CYAN}🛰️ Currently Running Containers:${NC}"
        docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        ;;
    *)
        show_help
        ;;
esac
