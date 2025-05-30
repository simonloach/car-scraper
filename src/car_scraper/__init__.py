"""
Car scraper packagefrom src.car_scraper.plotters import (
    IndividualListingsPlotter,
    YearAnalysisPlotter,
)
from src.car_scraper.scrapers import AdvertisementFetcher, CarScraper
from src.car_scraper.storage import (
    IdMappingStorage,
    IndividualListingsStorage,
)o.pl.

A professional car listing scraper with comprehensive features:
- Individual listing price tracking over time
- Advanced data analysis and visualization
- Multiple export formats and storage options
- Professional logging and error handling
- Modular architecture following Python best practices
"""

__version__ = "0.1.0"
__author__ = "Szymon Piskorz"
__email__ = "sim.piskorz@gmail.com"

# Main exports
from src.car_scraper.config import Config
from src.car_scraper.models import (
    CarListing,
    CarListingHistory,
    ScrapingResults,
    YearAnalysisData,
)
from src.car_scraper.plotters import IndividualListingsPlotter, YearAnalysisPlotter
from src.car_scraper.scrapers import AdvertisementFetcher, CarScraper
from src.car_scraper.storage import (
    IdMappingStorage,
    IndividualListingsStorage,
    SimplifiedListingsStorage,
)
from src.car_scraper.utils import DataProcessor, DemoRunner

__all__ = [
    # Core classes
    "Config",
    "CarScraper",
    "AdvertisementFetcher",
    # Data models
    "CarListing",
    "CarListingHistory",
    "ScrapingResults",
    "YearAnalysisData",
    # Storage
    "IndividualListingsStorage",
    "IdMappingStorage",
    "SimplifiedListingsStorage",
    # Plotting
    "IndividualListingsPlotter",
    "YearAnalysisPlotter",
    # Utilities
    "DataProcessor",
    "DemoRunner",
]
