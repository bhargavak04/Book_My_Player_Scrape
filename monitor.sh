#!/bin/bash

# BookMyPlayer Scraper - Monitoring Script
set -e

CONTAINER_NAME="bmp-scraper"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

while true; do
    clear
    echo -e "${BLUE}=== BookMyPlayer Scraper Monitor ===${NC}"
    echo "$(date)"
    echo

    # Container status
    if docker ps -q -f name=$CONTAINER_NAME | grep -q .; then
        echo -e "${GREEN}Status: RUNNING${NC}"
        
        # Container stats
        echo -e "${BLUE}Container Stats:${NC}"
        docker stats $CONTAINER_NAME --no-stream --format "table {{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"
        echo
        
        # Recent logs
        echo -e "${BLUE}Recent Logs (last 10 lines):${NC}"
        docker logs --tail 10 $CONTAINER_NAME
        echo
        
        # Output files
        echo -e "${BLUE}Output Files:${NC}"
        if [ -d "output" ]; then
            ls -la output/ | tail -10
        else
            echo "No output directory found"
        fi
        echo
        
        # Progress from logs
        echo -e "${BLUE}Latest Progress:${NC}"
        if [ -f "logs/progress.log" ]; then
            tail -5 logs/progress.log
        else
            echo "No progress log found"
        fi
        
    else
        echo -e "${RED}Status: NOT RUNNING${NC}"
        echo "Run './run.sh' to start the scraper"
    fi
    
    echo
    echo "Press Ctrl+C to exit monitor"
    sleep 10
done
