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
from src.car_scraper.storage import IndividualListingsStorage, TimeSeriesStorage
from src.car_scraper.plotters import IndividualListingsPlotter, YearAnalysisPlotter, LegacyPlotter
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
@click.option('--url', required=True, help='Search URL from otomoto.pl')
@click.option('--model', required=True, help='Model name to save data as')
@click.option('--data-dir', default='./data', help='Directory to save data')
@click.option('--max-pages', default=10, help='Maximum number of pages to scrape')
@click.option('--format', 'output_format', default='csv', 
              type=click.Choice(['csv', 'json']), help='Output format')
@click.option('--delay', default=1.0, help='Delay between requests (seconds)')
def scrape(url: str, model: str, data_dir: str, max_pages: int, 
           output_format: str, delay: float):
    """
    🔍 Scrape car listings from otomoto.pl
    
    Extract car listings with prices, specifications, and metadata.
    Automatically tracks individual listings over time for price analysis.
    
    Example:
        python main.py scrape --url "https://www.otomoto.pl/osobowe/lexus/lc" --model "lexus-lc"
    """
    logger.info(f"Starting scrape for model: {model}")
    logger.info(f"URL: {url}")
    logger.info(f"Data directory: {data_dir}")
    logger.info(f"Max pages: {max_pages}")
    logger.info(f"Output format: {output_format}")
    
    try:
        # Update scraping config with user parameters
        config.scraping.page_delay = delay
        
        # Initialize scraper
        scraper = CarScraper(data_dir, config.scraping)
        
        # Scrape the model
        results: ScrapingResults = scraper.scrape_model(url, model, max_pages)
        
        # Log results
        logger.success(f"Scraping completed successfully!")
        logger.info(f"Total ads scraped: {results.total_ads}")
        logger.info(f"Successful: {results.successful_ads}")
        logger.info(f"Failed: {results.failed_ads}")
        logger.info(f"Individual listings tracked: {results.individual_listings_tracked}")
        
        if results.failed_ads > 0:
            logger.warning(f"{results.failed_ads} ads failed to scrape")
            
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        sys.exit(1)


@cli.command()
@click.option('--model', required=True, help='Model name to generate plots for')
@click.option('--data-dir', default='./data', help='Directory containing data')
@click.option('--plot-type', default='all', 
              type=click.Choice(['all', 'individual', 'year', 'legacy']),
              help='Type of plots to generate')
@click.option('--output-dir', default='./plots', help='Directory to save plots')
def plot(model: str, data_dir: str, plot_type: str, output_dir: str):
    """
    📊 Generate visualization plots for scraped data
    
    Create comprehensive analysis charts including price trends,
    year-based analysis, and individual listing tracking.
    
    Example:
        python main.py plot --model "lexus-lc" --plot-type "all"
    """
    logger.info(f"Generating {plot_type} plots for model: {model}")
    logger.info(f"Data directory: {data_dir}")
    logger.info(f"Output directory: {output_dir}")
    
    try:
        # Create output directory
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        if plot_type in ['all', 'individual']:
            plotter = IndividualListingsPlotter(data_dir, output_dir)
            plotter.generate_plots(model)
            logger.success("Individual listing plots generated")
            
        if plot_type in ['all', 'year']:
            plotter = YearAnalysisPlotter(data_dir, output_dir)
            plotter.generate_plots(model)
            logger.success("Year analysis plots generated")
            
        if plot_type in ['all', 'legacy']:
            plotter = LegacyPlotter(data_dir, output_dir)
            plotter.generate_plots(model)
            logger.success("Legacy plots generated")
            
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
