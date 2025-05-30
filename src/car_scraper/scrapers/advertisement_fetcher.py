"""Advertisement fetcher for individual car listings from otomoto.pl"""

import datetime
import json
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional

import click
import httpx
import pandas as pd
from bs4 import BeautifulSoup

from src.car_scraper.models import CarListing
from src.car_scraper.utils.logger import logger


class AdvertisementFetcher:
    """
    Fetches advertisements from otomoto.pl
    """

    def __init__(
        self, data_directory: str, make: str = None, model: str = None
    ) -> None:
        """
        Initialize the advertisement fetcher

        Args:
            data_directory: Directory to save scraped data
            make: Car make (e.g., 'lexus', 'bmw', 'audi')
            model: Car model (e.g., 'lc', 'i8', 'r8')
        """
        self.data_directory = Path(data_directory)
        self.make = make.lower() if make else None
        self.model = model.lower() if model else None
        self.ads: List[Dict] = []
        logger.info(
            f"Initialized AdvertisementFetcher with data directory: {data_directory}, make: {make}, model: {model}"
        )

    def setup_fetcher(self) -> None:
        """Reset the ads list for a new scraping session"""
        self.ads = []
        logger.info("Reset ads list for new scraping session")

    def _is_valid_car_link(self, link: str) -> bool:
        """
        Check if a link is for the specified car make and model

        Args:
            link: URL to check

        Returns:
            bool: True if link matches the specified make and model
        """
        # If no make/model specified, accept any otomoto link
        if not self.make or not self.model:
            return "/oferta/" in link

        # Check if the link contains the make and model in the right pattern
        # Pattern should match URLs like: .../oferta/make-model-...
        if "/oferta/" not in link:
            return False

        # Extract the part after /oferta/
        oferta_part = link.split("/oferta/")[-1].lower()

        # Check if it starts with make-model pattern
        car_pattern = rf"^{re.escape(self.make)}[-\s]{re.escape(self.model)}[-\s]"
        if re.match(car_pattern, oferta_part):
            return True

        return False

    def fetch_ads(self, links: List[str], model: str) -> None:
        """
        Fetch ads from links

        Args:
            links: list of links to ads
            model: car model being fetched
        """
        successful_fetches = 0
        failed_fetches = 0
        filtered_out = 0

        logger.info(f"Starting to fetch {len(links)} ads for model: {model}")

        for link in links:
            # Filter for valid car model links only
            if not self._is_valid_car_link(link):
                filtered_out += 1
                continue

            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Referer": "https://www.google.com/",
                }

                # Use httpx with automatic redirect following
                response = httpx.get(
                    link, headers=headers, timeout=30, follow_redirects=True
                )
                response.raise_for_status()

                soup = BeautifulSoup(response.text, "lxml")

                # Extract car data
                car_data = self._extract_car_data(soup, link, model)
                if car_data:
                    self.ads.append(car_data)
                    successful_fetches += 1
                    logger.debug(f"Successfully extracted data from {link}")

                # Small delay to be respectful
                time.sleep(0.1)

            except Exception as e:
                failed_fetches += 1
                logger.error(f"Error fetching ad from {link}: {str(e)}")
                continue

        logger.info(
            f"Fetch summary: {successful_fetches} successful, {failed_fetches} failed, {filtered_out} filtered out (not matching model)"
        )
        click.echo(
            f"Fetch summary: {successful_fetches} successful, {failed_fetches} failed, {filtered_out} filtered out (not matching model)"
        )

    def _extract_car_data(
        self, soup: BeautifulSoup, link: str, model: str
    ) -> Optional[Dict]:
        """
        Extract car data from BeautifulSoup object

        Args:
            soup: BeautifulSoup parsed HTML
            link: Original URL
            model: Car model

        Returns:
            Dict with car data or None if extraction failed
        """
        try:
            # Extract price
            price = self._extract_price(soup, link)

            # Extract title
            title = self._extract_title(soup, link)

            # Extract year
            year = self._extract_year(soup)

            # Extract mileage
            mileage = self._extract_mileage(soup)

            # Create ad entry
            ad_id = link.split("/")[-1].split("#")[0].split("?")[0]

            ad_data = {
                "id": ad_id,
                "title": title,
                "price": price,
                "year": year,
                "mileage": mileage,
                "url": link,
                "model": model,
                "scrape_date": datetime.datetime.now().isoformat(),
                "scrape_timestamp": int(time.time()),
            }

            return ad_data

        except Exception as e:
            logger.error(f"Error extracting car data from {link}: {str(e)}")
            return None

    def _extract_price(self, soup: BeautifulSoup, link: str) -> int:
        """Extract price from soup"""
        price = 0
        try:
            # Try different price selectors
            price_selectors = [
                'span[data-testid="price"]',
                ".price-value",
                ".offer-price__number",
                '[data-testid="price-value"]',
            ]

            for selector in price_selectors:
                price_element = soup.select_one(selector)
                if price_element:
                    price_text = price_element.get_text(strip=True)
                    # Extract numbers from price text
                    price_digits = "".join(
                        filter(str.isdigit, price_text.replace(" ", ""))
                    )
                    if price_digits:
                        price = int(price_digits)
                        break
        except Exception as e:
            logger.warning(f"Error extracting price from {link}: {str(e)}")

        return price

    def _extract_title(self, soup: BeautifulSoup, link: str) -> str:
        """Extract title from soup"""
        title = "Unknown"
        try:
            title_selectors = [
                'h1[data-testid="ad-title"]',
                "h1.offer-title",
                ".ad-title",
            ]

            for selector in title_selectors:
                title_element = soup.select_one(selector)
                if title_element:
                    title = title_element.get_text(strip=True)
                    break
        except Exception as e:
            logger.warning(f"Error extracting title from {link}: {str(e)}")

        return title

    def _extract_year(self, soup: BeautifulSoup) -> Optional[int]:
        """Extract year from soup"""
        year = None
        try:
            # Look for year in various places
            year_patterns = soup.find_all(
                string=lambda text: text
                and any(str(y) in text for y in range(1990, 2025))
            )
            for pattern in year_patterns:
                for y in range(1990, 2025):
                    if str(y) in pattern:
                        year = y
                        break
                if year:
                    break
        except Exception:
            pass

        return year

    def _extract_mileage(self, soup: BeautifulSoup) -> Optional[int]:
        """Extract mileage from soup"""
        mileage = None
        try:
            # Look for mileage in specific sections first
            mileage_selectors = [
                '[data-testid="mileage"]',
                ".offer-params__value",
                ".parameter-value",
            ]

            for selector in mileage_selectors:
                mileage_elements = soup.select(selector)
                for element in mileage_elements:
                    text = element.get_text(strip=True).lower()
                    if "km" in text:
                        # Extract numbers from mileage text - improved pattern
                        mileage_pattern = re.search(
                            r"(\d{1,3}(?:[\s\xa0]*\d{3})*)\s*km", text
                        )
                        if mileage_pattern:
                            mileage_str = (
                                mileage_pattern.group(1)
                                .replace(" ", "")
                                .replace("\xa0", "")
                            )
                            if (
                                mileage_str.isdigit() and 1 <= len(mileage_str) <= 7
                            ):  # Reasonable length
                                mileage_val = int(mileage_str)
                                if mileage_val <= 9999999:  # Max reasonable mileage
                                    mileage = mileage_val
                                    break
                if mileage:
                    break

            # Fallback: look for mileage in parameter tables
            if mileage is None:
                param_sections = soup.find_all(
                    ["li", "div"], class_=re.compile(r"param|detail|spec")
                )
                for section in param_sections:
                    text = section.get_text(strip=True).lower()
                    if "przebieg" in text or (
                        "km" in text and any(char.isdigit() for char in text)
                    ):
                        # More conservative pattern
                        mileage_pattern = re.search(
                            r"(\d{1,3}(?:[\s\xa0]*\d{3})*)\s*km", text
                        )
                        if mileage_pattern:
                            mileage_str = (
                                mileage_pattern.group(1)
                                .replace(" ", "")
                                .replace("\xa0", "")
                            )
                            if mileage_str.isdigit() and 1 <= len(mileage_str) <= 7:
                                mileage_val = int(mileage_str)
                                if mileage_val <= 9999999:
                                    mileage = mileage_val
                                    break
        except Exception:
            pass

        return mileage

    def save_ads(self, model: str) -> None:
        """
        Save ads using simplified storage system

        Args:
            model: car model to save
        """
        if not self.ads:
            logger.warning(f"No ads found for {model}")
            click.echo(f"No ads found for {model}")
            return

        # Create model-specific data
        model_ads = [ad for ad in self.ads if ad["model"] == model]
        if not model_ads:
            logger.warning(f"No ads found for model {model}")
            click.echo(f"No ads found for model {model}")
            return

        logger.info(f"Saved {len(model_ads)} ads for {model} using simplified storage")
        click.echo(f"Saved {len(model_ads)} ads for {model} using simplified storage")
