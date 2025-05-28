"""Car scraper modules for extracting data from otomoto.pl"""

from src.car_scraper.scrapers.advertisement_fetcher import AdvertisementFetcher
from src.car_scraper.scrapers.car_scraper import CarScraper

__all__ = ["AdvertisementFetcher", "CarScraper"]
