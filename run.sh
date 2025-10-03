#!/bin/bash

# BookMyPlayer Scraper - Azure VPS Deployment Script
set -e

echo "=== BookMyPlayer Scraper Deployment ==="
echo "Starting deployment on Azure VPS..."

# Configuration
CONTAINER_NAME="bmp-scraper"
IMAGE_NAME="bookmyplayer-scraper"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    log_error "Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null; then
    log_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create required directories
log_info "Creating required directories..."
mkdir -p input output logs

# Check if input file exists
if [ ! -f "input/urls.xlsx" ] && [ ! -f "input/urls.csv" ]; then
    log_warning "No input file found in input/ directory."
    log_info "Please place your URLs file (urls.xlsx or urls.csv) in the input/ directory."
    log_info "Example: cp your_urls_file.xlsx input/urls.xlsx"
    read -p "Press Enter to continue when ready..."
fi

# Stop existing container if running
if docker ps -q -f name=$CONTAINER_NAME | grep -q .; then
    log_info "Stopping existing container..."
    docker stop $CONTAINER_NAME
    docker rm $CONTAINER_NAME
fi

# Build the image
log_info "Building Docker image..."
docker build -t $IMAGE_NAME .

# Start the container
log_info "Starting scraper container..."
docker-compose up -d

# Show container status
log_info "Container status:"
docker ps -f name=$CONTAINER_NAME

# Show logs
log_info "Showing recent logs (press Ctrl+C to exit log view):"
sleep 2
docker logs -f $CONTAINER_NAME &
LOG_PID=$!

# Wait for user to stop log viewing
trap "kill $LOG_PID 2>/dev/null || true" EXIT

echo
log_success "Scraper is running!"
echo
echo "=== USEFUL COMMANDS ==="
echo "View logs:           docker logs -f $CONTAINER_NAME"
echo "Stop scraper:        docker stop $CONTAINER_NAME"
echo "Restart scraper:     docker restart $CONTAINER_NAME"
echo "Check status:        docker ps -f name=$CONTAINER_NAME"
echo "View output files:   ls -la output/"
echo "View log files:      ls -la logs/"
echo
echo "=== FILE MONITORING ==="
echo "Output directory:    ./output/"
echo "Log directory:       ./logs/"
echo "Progress files are auto-saved every 1000 records"
echo

wait
