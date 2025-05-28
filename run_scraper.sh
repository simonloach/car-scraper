#!/bin/bash

# Car Scraper Cron Script
# This script runs the car scraper and can be called from cron

# Set the project directory (update this path)
PROJECT_DIR="/path/to/car-scraper"

# Set the data directory
DATA_DIR="$PROJECT_DIR/data"

# Create data directory if it doesn't exist
mkdir -p "$DATA_DIR"

# Change to project directory
cd "$PROJECT_DIR"

# Log file
LOG_FILE="$DATA_DIR/scraper.log"

# Function to log with timestamp
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

log "Starting car scraper..."

# Run the scraper with Docker
docker run --rm \
    -v "$DATA_DIR:/app/data" \
    car-scraper scrape \
    --url "https://www.otomoto.pl/osobowe/lexus/lc?search%5Border%5D=relevance_web" \
    --model "lexus-lc" \
    --data-dir "/app/data" \
    --max-pages 5 \
    --format "csv" >> "$LOG_FILE" 2>&1

if [ $? -eq 0 ]; then
    log "Scraper completed successfully"
    
    # Generate plots after successful scraping
    log "Generating plots..."
    docker run --rm \
        -v "$DATA_DIR:/app/data" \
        car-scraper plot \
        --data-dir "/app/data" \
        --type "both" >> "$LOG_FILE" 2>&1
    
    if [ $? -eq 0 ]; then
        log "Plots generated successfully"
    else
        log "Plot generation failed"
    fi
else
    log "Scraper failed"
fi

log "Scraper job finished"
