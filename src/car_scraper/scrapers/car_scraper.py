"""Car scraper for otomoto.pl search pages.

Thin wrapper over :mod:`otomoto_search`, which reads otomoto's embedded
structured data instead of scraping individual advert pages. Kept as a class
for backward compatibility with the CLI and tests.
"""

import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import click

from src.car_scraper.scrapers.otomoto_search import scrape_search
from src.car_scraper.utils.logger import logger


class CarScraper:
    """Scrapes cars from otomoto.pl search pages.

    Args:
        data_directory: path to directory where data will be saved.
        make: car make (e.g. ``lexus``) - used for logging only.
        model: car model (e.g. ``lc``) - used for logging only.
    """

    def __init__(
        self, data_directory: str, make: str = None, model: str = None
    ) -> None:
        logger.info(f"Initializing Car scraper for {make} {model}")
        click.echo(f"Initializing Car scraper for {make} {model}")

        self.data_directory = Path(data_directory)
        self.data_directory.mkdir(parents=True, exist_ok=True)
        self.make = make
        self.model = model
        self.listings: List[Dict] = []

    def scrape_model(
        self, search_url: str, model_name: str, max_pages: int = 10
    ) -> List[Dict]:
        """Scrape a model from a search URL.

        Args:
            search_url: URL to search for cars (may include filter params).
            model_name: model key to tag listings with (e.g. ``lexus-lc``).
            max_pages: maximum number of pages to scrape.

        Returns:
            List of clean listing dicts (also stored on ``self.listings``).
        """
        logger.info(f"Start scraping model: {model_name}")
        click.echo(f"Start scraping model: {model_name}")

        raw = scrape_search(search_url, max_pages=max_pages)

        scrape_date = datetime.now().isoformat()
        scrape_ts = int(time.time())
        for listing in raw:
            listing["model"] = model_name
            listing["scrape_date"] = scrape_date
            listing["scrape_timestamp"] = scrape_ts

        # Drop listings without a usable price (storage requires price > 0).
        self.listings = [x for x in raw if x.get("price")]
        dropped = len(raw) - len(self.listings)
        if dropped:
            logger.warning(f"Dropped {dropped} listings with no price")

        logger.info(f"End scraping model: {model_name} ({len(self.listings)} listings)")
        click.echo(f"End scraping model: {model_name} ({len(self.listings)} listings)")
        return self.listings
