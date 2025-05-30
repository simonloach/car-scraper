#!/usr/bin/env python3
"""
Car Scraper CLI
A refactored, modular car scraper for otomoto.pl with comprehensive features.

This application provides:
- Car listing scraping from otomoto.pl
- Individual listing price tracking over time
- Comprehensive data analysis and visualization
- Price change detection and alerts
- Multiple output formats (CSV, JSON)
- Professional logging and error handling
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from loguru import logger

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.car_scraper.config import Config
from src.car_scraper.models import ScrapingResults
from src.car_scraper.scrapers import CarScraper
from src.car_scraper.storage import IndividualListingsStorage
from src.car_scraper.plotters import IndividualListingsPlotter, YearAnalysisPlotter
from src.car_scraper.utils import DataProcessor, DemoRunner
from src.car_scraper.utils.logger import setup_logger


# Initialize configuration
config = Config()


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--log-level', default='INFO', 
              type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
              help='Set logging level')
def cli(verbose: bool, log_level: str):
    """
    🚗 Modern Car Scraper CLI for otomoto.pl
    
    A professional car listing scraper with price tracking, analysis, and visualization.
    """
    # Setup logging
    level = 'DEBUG' if verbose else log_level
    setup_logger(log_level=level)
    
    logger.info("Car Scraper CLI initialized")
    logger.debug(f"Logging level set to: {level}")


@cli.command()
@click.option('--url', help='Search URL from otomoto.pl (for advanced queries)')
@click.option('--manufacturer', '--make', help='Car manufacturer (e.g., lexus, bmw, audi)')
@click.option('--model', help='Car model (e.g., lc, i8, r8)')
@click.option('--data-dir', default='./data', help='Directory to save data')
@click.option('--max-pages', default=10, help='Maximum number of pages to scrape')
@click.option('--format', 'output_format', default='csv', 
              type=click.Choice(['csv', 'json']), help='Output format')
@click.option('--delay', default=1.0, help='Delay between requests (seconds)')
def scrape(url: str, manufacturer: str, model: str, data_dir: str, max_pages: int, 
           output_format: str, delay: float):
    """
    🔍 Scrape car listings from otomoto.pl
    
    Extract car listings with prices, specifications, and metadata.
    Automatically tracks individual listings over time for price analysis.
    
    Two modes:
    1. Simple: --manufacturer lexus --model lc
    2. Advanced: --url "https://www.otomoto.pl/osobowe/lexus/lc?specific=query"
    
    Examples:
        python main.py scrape --manufacturer lexus --model lc
        python main.py scrape --url "https://www.otomoto.pl/osobowe/bmw/i8"
    """
    
    # Validate input - must have either URL or manufacturer+model
    if not url and not (manufacturer and model):
        raise click.UsageError(
            "Must provide either --url OR both --manufacturer and --model"
        )
    
    # Mode 1: Simple mode - generate URL from manufacturer and model
    if manufacturer and model and not url:
        url = f"https://www.otomoto.pl/osobowe/{manufacturer.lower()}/{model.lower()}"
        make = manufacturer.lower()
        car_model = model.lower()
        model_key = f"{make}-{car_model}"
        logger.info(f"Simple mode: Generated URL from manufacturer and model")
        
    # Mode 2: Advanced mode - extract from URL, allow overrides
    elif url:
        # Extract manufacturer and model from URL
        import re
        url_parts = re.findall(r'/osobowe/([^/]+)/([^/?]+)', url)
        if url_parts:
            url_make, url_model = url_parts[0]
        else:
            raise click.UsageError(
                "Cannot extract manufacturer/model from URL. "
                "Please provide --manufacturer and --model explicitly."
            )
            
        # Use provided manufacturer/model or fall back to URL extraction
        make = manufacturer.lower() if manufacturer else url_make.lower()
        car_model = model.lower() if model else url_model.lower()
        model_key = f"{make}-{car_model}"
        
        if manufacturer or model:
            logger.info(f"Advanced mode: Using URL with manufacturer/model override")
        else:
            logger.info(f"Advanced mode: Extracted manufacturer/model from URL")
    
    logger.info(f"Starting scrape for: {make} {car_model}")
    logger.info(f"URL: {url}")
    logger.info(f"Model key: {model_key}")
    logger.info(f"Data directory: {data_dir}")
    logger.info(f"Max pages: {max_pages}")
    logger.info(f"Output format: {output_format}")
    
    try:
        # Initialize scraper with make and model
        scraper = CarScraper(data_dir, make, car_model)
        
        # Scrape the model
        scraper.scrape_model(url, model_key, max_pages)
        
        # Initialize individual listings storage for historical tracking
        storage = IndividualListingsStorage(data_dir)
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        # Load the scraped data and trigger individual listings storage
        logger.info(f"Processing individual listings data for {model_key}")
        click.echo(f"📊 Processing individual listings data for {model_key}")
        
        # Read the scraped data from the model directory
        model_dir = Path(data_dir) / model_key.replace("/", "_")
        model_json_file = model_dir / f"{model_key.replace('/', '_')}.json"
        
        if model_json_file.exists():
            import json
            with open(model_json_file, "r", encoding="utf-8") as f:
                scraped_data = json.load(f)
            
            # Store in individual listings tracking system
            storage.store_model_listings_data(model_key, scraped_data, current_date, "json")
        else:
            logger.warning(f"No scraped data file found for {model_key}")
        
        # Log completion
        logger.success(f"Scraping completed successfully!")
        click.echo(f"✅ Scraping completed for: {make} {car_model}")
        click.echo(f"📁 Data saved to: {data_dir}")
            
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        raise click.ClickException(f"Scraping failed: {e}")
        sys.exit(1)


@cli.command()
@click.option('--model', required=True, help='Model name to generate plots for')
@click.option('--data-dir', default='./data', help='Directory containing data')
@click.option('--plot-type', default='all', 
              type=click.Choice(['all', 'individual', 'year']),
              help='Type of plots to generate')
@click.option('--output-dir', default='./plots', help='Directory to save plots')
def plot(model: str, data_dir: str, plot_type: str, output_dir: str):
    """
    📊 Generate visualization plots for scraped data
    
    Create comprehensive analysis charts including price trends,
    year-based analysis, and individual listing tracking.
    
    Example:
        python main.py plot --model "bmw-i8" --plot-type "all"
    """
    logger.info(f"Generating {plot_type} plots for model: {model}")
    logger.info(f"Data directory: {data_dir}")
    logger.info(f"Output directory: {output_dir}")
    
    try:
        # Create output directory
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        if plot_type in ['all', 'individual']:
            plotter = IndividualListingsPlotter(data_dir)
            plotter.generate_individual_listing_plots(model)
            logger.success("Individual listing plots generated")
            
        if plot_type in ['all', 'year']:
            plotter = YearAnalysisPlotter(data_dir)
            plotter.generate_year_analysis_plots(model)
            logger.success("Year analysis plots generated")
            
        logger.success(f"All {plot_type} plots generated successfully!")
        
    except Exception as e:
        logger.error(f"Plot generation failed: {e}")
        sys.exit(1)


@cli.command()
@click.option('--data-dir', default='./data', help='Directory containing data')
def status(data_dir: str):
    """
    📋 Show current data status and statistics
    
    Display information about scraped models, data sizes,
    and recent scraping activity.
    """
    logger.info(f"Checking status for data directory: {data_dir}")
    
    try:
        data_path = Path(data_dir)
        if not data_path.exists():
            logger.warning(f"Data directory does not exist: {data_dir}")
            return
            
        # Find all model directories
        model_dirs = [d for d in data_path.iterdir() if d.is_dir()]
        
        if not model_dirs:
            logger.info("No models found in data directory")
            return
            
        logger.info(f"Found {len(model_dirs)} models:")
        
        for model_dir in model_dirs:
            model_name = model_dir.name
            
            # Check for data files
            csv_files = list(model_dir.glob("*.csv"))
            json_files = list(model_dir.glob("*.json"))
            
            logger.info(f"  📁 {model_name}:")
            logger.info(f"    CSV files: {len(csv_files)}")
            logger.info(f"    JSON files: {len(json_files)}")
            
            # Get latest file modification time
            all_files = csv_files + json_files
            if all_files:
                latest_file = max(all_files, key=lambda f: f.stat().st_mtime)
                latest_time = datetime.fromtimestamp(latest_file.stat().st_mtime)
                logger.info(f"    Last updated: {latest_time.strftime('%Y-%m-%d %H:%M:%S')}")
                
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        sys.exit(1)


@cli.command()
@click.option('--data-dir', default='./data', help='Directory containing data')
def demo(data_dir: str):
    """
    🎪 Run full demo workflow
    
    Execute a complete demonstration of the scraper capabilities
    including data generation, analysis, and visualization.
    """
    logger.info("Starting demo workflow")
    logger.info(f"Data directory: {data_dir}")
    
    try:
        demo_runner = DemoRunner(data_dir)
        demo_runner.run_complete_demo()
        
        logger.success("Demo completed successfully!")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    cli()
