# Car Scraper for Otomoto.pl

A Click CLI application for scraping car listings from otomoto.pl with time series tracking and plotting capabilities.

## Features

- Scrape car listings from otomoto.pl
- Track prices and listing counts over time
- Generate time series plots
- Support for both CSV and JSON data formats
- Docker support for easy deployment
- Designed for cron job automation

## Installation

### Local Development

1. Install dependencies:
```bash
poetry install
```

2. Run the CLI:
```bash
poetry run python -m src.main --help
```

### Docker

1. Build the Docker image:
```bash
docker build -t car-scraper .
```

2. Run with Docker:
```bash
docker run -v $(pwd)/data:/app/data car-scraper --help
```

## Usage

### Scraping Cars

To scrape Lexus LC models:

```bash
# Local
poetry run python -m src.main scrape \
    --url "https://www.otomoto.pl/osobowe/lexus/lc?search%5Border%5D=relevance_web" \
    --model "lexus-lc" \
    --data-dir "./data" \
    --max-pages 5

# Docker
docker run -v $(pwd)/data:/app/data car-scraper scrape \
    --url "https://www.otomoto.pl/osobowe/lexus/lc?search%5Border%5D=relevance_web" \
    --model "lexus-lc" \
    --data-dir "/app/data" \
    --max-pages 5
```

### Generating Plots

Generate price and count trend plots:

```bash
# Local
poetry run python -m src.main plot --data-dir "./data"

# Docker
docker run -v $(pwd)/data:/app/data car-scraper plot --data-dir "/app/data"
```

### Checking Status

View current data status:

```bash
# Local
poetry run python -m src.main status --data-dir "./data"

# Docker
docker run -v $(pwd)/data:/app/data car-scraper status --data-dir "/app/data"
```

## CLI Commands

### `scrape`
Scrape car listings from otomoto.pl

Options:
- `--url`: Search URL from otomoto.pl (required)
- `--model`: Model name to save data as (required)
- `--data-dir`: Directory to save data (default: ./data)
- `--max-pages`: Maximum number of pages to scrape (default: 10)
- `--format`: Output format, csv or json (default: csv)

### `plot`
Generate plots from scraped data

Options:
- `--data-dir`: Directory containing data (default: ./data)
- `--model`: Specific model to plot (optional)
- `--type`: Type of plot to generate: price, count, or both (default: both)

### `status`
Show scraping status and data summary

Options:
- `--data-dir`: Directory containing data (default: ./data)

## Data Structure

### Raw Data Files
- `{model}.csv` / `{model}.json`: Raw scraped data for each model

### Time Series Data
- `time_series/{date}.csv` / `time_series/{date}.json`: Daily snapshots
- `time_series/historical.csv` / `time_series/historical.json`: All historical data

### Generated Plots
- `plots/price_trends.png`: Price trends over time
- `plots/count_trends.png`: Listing count trends over time

## Cron Job Setup

For automated daily scraping, you have several options:

### Option 1: Using the provided script

1. Edit the `run_scraper.sh` script and update the paths:
```bash
vim run_scraper.sh
# Update PROJECT_DIR to your actual path
```

2. Make it executable:
```bash
chmod +x run_scraper.sh
```

3. Add to your crontab:
```bash
crontab -e
# Add this line for daily scraping at 2 AM:
0 2 * * * /path/to/car-scraper/run_scraper.sh
```

### Option 2: Direct cron commands

```bash
# Run daily at 2 AM using Docker
0 2 * * * cd /path/to/car-scraper && docker run -v $(pwd)/data:/app/data car-scraper scrape --url "https://www.otomoto.pl/osobowe/lexus/lc?search%5Border%5D=relevance_web" --model "lexus-lc" --data-dir "/app/data" --max-pages 5

# Or using Poetry
0 2 * * * cd /path/to/car-scraper && poetry run python -m src.main scrape --url "https://www.otomoto.pl/osobowe/lexus/lc?search%5Border%5D=relevance_web" --model "lexus-lc" --data-dir "./data" --max-pages 5
```

## Data Fields

Each scraped listing contains:
- `id`: Unique listing identifier
- `title`: Car title/description
- `price`: Price in PLN
- `year`: Manufacturing year
- `mileage`: Mileage in kilometers
- `url`: Link to the listing
- `model`: Model name
- `scrape_date`: Date of scraping
- `scrape_timestamp`: Unix timestamp of scraping

## Time Series Metrics

For each model and date:
- `count`: Number of listings
- `avg_price`: Average price
- `median_price`: Median price
- `min_price`: Minimum price
- `max_price`: Maximum price
- `price_std`: Price standard deviation

## Notes

- The scraper includes respectful delays to avoid overwhelming the server
- Error handling for missing data or network issues
- Robust HTML parsing with multiple selectors for reliability
- Time series data automatically updates historical files