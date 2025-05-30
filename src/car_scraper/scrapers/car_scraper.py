"""Main car scraper for otomoto.pl search pages"""

import random
import re
import time
from pathlib import Path
from typing import List, Optional

import click
import httpx
from bs4 import BeautifulSoup

from src.car_scraper.scrapers.advertisement_fetcher import AdvertisementFetcher
from src.car_scraper.utils.logger import logger


class CarScraper:
    """
    Scraps cars from otomoto.pl

    Args:
        data_directory: path to directory where data will be saved
        make: Car make (e.g., 'lexus', 'bmw', 'audi')
        model: Car model (e.g., 'lc', 'i8', 'r8')
    """

    def __init__(self, data_directory: str, make: str = None, model: str = None) -> None:
        logger.info(f"Initializing Car scraper for {make} {model}")
        click.echo(f"Initializing Car scraper for {make} {model}")

        self.data_directory = Path(data_directory)
        self.data_directory.mkdir(parents=True, exist_ok=True)
        self.make = make
        self.model = model
        self.ad_fetcher = AdvertisementFetcher(str(self.data_directory), make, model)

    def get_cars_in_page(self, path: str, page_num: int) -> List[str]:
        """
        Gets cars in page

        Args:
            path: path to page
            page_num: page number

        Returns:
            list of links
        """
        logger.info(f"Scraping page: {page_num}")
        click.echo(f"Scraping page: {page_num}")

        headers = [
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
                "Referer": "https://www.google.com/",
            },
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/109.0",
                "Accept-Language": "pl-PL,pl;q=0.9,en-US,en;q=0.7",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Referer": "https://www.google.com/",
            },
        ]

        header = random.choice(headers)

        try:
            if page_num == 1:
                url = path  # First page uses base URL
            else:
                # Add page parameter for subsequent pages
                separator = "&" if "?" in path else "?"
                url = f"{path}{separator}page={page_num}"

            res = httpx.get(url, headers=header, timeout=30)
            res.raise_for_status()
        except Exception as e:
            logger.error(f"Error fetching page {page_num}: {str(e)}")
            click.echo(f"Error fetching page {page_num}: {str(e)}")
            return []

        soup = BeautifulSoup(res.text, features="lxml")
        links = []

        # Try different selectors for car links
        try:
            # Try main search results container
            car_links_section = soup.find(
                "main", attrs={"data-testid": "search-results"}
            )
            if car_links_section:
                articles = car_links_section.find_all("article")
                for article in articles:
                    try:
                        link_element = article.find("a", href=True)
                        if link_element and link_element["href"]:
                            full_link = link_element["href"]
                            if not full_link.startswith("http"):
                                full_link = "https://www.otomoto.pl" + full_link
                            links.append(full_link)
                    except Exception:
                        continue

            # Alternative selector
            if not links:
                car_links_section = soup.find(
                    "div", attrs={"data-testid": "search-results"}
                )
                if car_links_section:
                    articles = car_links_section.find_all(
                        "article"
                    )  # Remove the data-media-size filter
                    for article in articles:
                        try:
                            # Try multiple ways to find the link
                            link_element = article.find("a", href=True)
                            if not link_element:
                                # Try finding in section
                                section = article.find("section")
                                if section:
                                    link_element = section.find("a", href=True)
                            if not link_element:
                                # Try finding by heading link
                                heading = article.find("h2")
                                if heading:
                                    link_element = heading.find("a", href=True)

                            if link_element and link_element["href"]:
                                full_link = link_element["href"]
                                if not full_link.startswith("http"):
                                    full_link = "https://www.otomoto.pl" + full_link
                                links.append(full_link)
                        except Exception:
                            continue

        except Exception as e:
            logger.error(f"Error parsing page {page_num}: {str(e)}")
            click.echo(f"Error parsing page {page_num}: {str(e)}")

        logger.info(f"Found {len(links)} links on page {page_num}")
        click.echo(f"Found {len(links)} links on page {page_num}")
        return links

    def scrape_model(
        self, search_url: str, model_name: str, max_pages: int = 10
    ) -> None:
        """
        Scraps model from search URL

        Args:
            search_url: URL to search for cars
            model_name: name to save the model as
            max_pages: maximum number of pages to scrape
        """
        logger.info(f"Start scraping model: {model_name}")
        click.echo(f"Start scraping model: {model_name}")
        self.ad_fetcher.setup_fetcher()

        # Get the first page to determine total pages
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
                "Referer": "https://www.google.com/",
            }
            res = httpx.get(search_url, headers=headers, timeout=30)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, features="lxml")

            # Try to find pagination info
            last_page_num = self._get_last_page_number(soup, max_pages)

            logger.info(f"Model has: {last_page_num} pages (limited to {max_pages})")
            click.echo(f"Model has: {last_page_num} pages (limited to {max_pages})")

        except Exception as e:
            logger.error(f"Error getting pagination info: {str(e)}")
            click.echo(f"Error getting pagination info: {str(e)}")
            last_page_num = 1

        # Scrape each page
        for page in range(1, last_page_num + 1):
            try:
                links = self.get_cars_in_page(search_url, page)
                if links:
                    self.ad_fetcher.fetch_ads(links, model_name)
                time.sleep(0.5)  # Be respectful to the server
            except Exception as e:
                logger.error(f"Error scraping page {page}: {str(e)}")
                click.echo(f"Error scraping page {page}: {str(e)}")
                continue

        self.ad_fetcher.save_ads(model_name)
        logger.info(f"End scraping model: {model_name}")
        click.echo(f"End scraping model: {model_name}")

    def _get_last_page_number(self, soup: BeautifulSoup, max_pages: int) -> int:
        """
        Extract the last page number from pagination

        Args:
            soup: BeautifulSoup object of the page
            max_pages: Maximum number of pages to limit to

        Returns:
            Last page number
        """
        last_page_num = 1
        try:
            # Look for pagination items with the correct class pattern
            pagination_items = soup.find_all("li", class_=re.compile(r"ooa-.*"))
            if pagination_items:
                for item in pagination_items:
                    try:
                        text = item.get_text(strip=True)
                        if text.isdigit():
                            page_num = int(text)
                            last_page_num = max(last_page_num, page_num)
                    except ValueError:
                        continue

            # Alternative: look for pagination by aria-label or other attributes
            if last_page_num == 1:
                pagination_container = soup.find(
                    "nav", attrs={"aria-label": re.compile(r"[Pp]aginat.*")}
                )
                if pagination_container:
                    page_links = pagination_container.find_all("li")
                    for link in page_links:
                        try:
                            text = link.get_text(strip=True)
                            if text.isdigit():
                                page_num = int(text)
                                last_page_num = max(last_page_num, page_num)
                        except ValueError:
                            continue
        except Exception:
            pass

        return min(last_page_num, max_pages)
