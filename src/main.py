import os
import random
import time
import json
import datetime
import re
from pathlib import Path

import click
import httpx
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from bs4 import BeautifulSoup
import matplotlib.dates as mdates
from bs4 import BeautifulSoup


class AdvertisementFetcher:
    """
    Fetches advertisements from otomoto.pl
    """
    
    def __init__(self, data_directory):
        self.data_directory = data_directory
        self.ads = []
        
    def setup_fetcher(self):
        """Reset the ads list for a new scraping session"""
        self.ads = []
        
    def _is_lexus_lc_link(self, link):
        """
        Check if a link is for a Lexus LC model
        Args:
            link: URL to check
        Returns:
            bool: True if link is for Lexus LC model
        """
        import re
        
        # Check if the link contains both 'lexus' and 'lc' in the right pattern
        # Pattern should match URLs like: .../oferta/lexus-lc-...
        if '/oferta/' not in link:
            return False
            
        # Extract the part after /oferta/
        oferta_part = link.split('/oferta/')[-1].lower()
        
        # Check if it starts with lexus-lc pattern
        lexus_lc_pattern = r'^lexus[-\s]lc[-\s]'
        if re.match(lexus_lc_pattern, oferta_part):
            return True
            
        return False
        
    def fetch_ads(self, links, model):
        """
        Fetch ads from links
        Args:
            links: list of links to ads
            model: car model being fetched
        """
        successful_fetches = 0
        failed_fetches = 0
        filtered_out = 0
        
        for link in links:
            # Filter for Lexus LC models only
            if not self._is_lexus_lc_link(link):
                filtered_out += 1
                continue
                
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7',
                    'Referer': 'https://www.google.com/',
                }
                
                # Use httpx with automatic redirect following
                response = httpx.get(link, headers=headers, timeout=30, follow_redirects=True)
                
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'lxml')
                
                # Extract price
                price = 0
                try:
                    # Try different price selectors
                    price_selectors = [
                        'span[data-testid="price"]',
                        '.price-value',
                        '.offer-price__number',
                        '[data-testid="price-value"]'
                    ]
                    
                    for selector in price_selectors:
                        price_element = soup.select_one(selector)
                        if price_element:
                            price_text = price_element.get_text(strip=True)
                            # Extract numbers from price text
                            price_digits = ''.join(filter(str.isdigit, price_text.replace(' ', '')))
                            if price_digits:
                                price = int(price_digits)
                                break
                except Exception as e:
                    click.echo(f"Error extracting price from {link}: {str(e)}")
                
                # Extract title
                title = "Unknown"
                try:
                    title_selectors = [
                        'h1[data-testid="ad-title"]',
                        'h1.offer-title',
                        '.ad-title'
                    ]
                    
                    for selector in title_selectors:
                        title_element = soup.select_one(selector)
                        if title_element:
                            title = title_element.get_text(strip=True)
                            break
                except Exception as e:
                    click.echo(f"Error extracting title from {link}: {str(e)}")
                
                # Extract year
                year = None
                try:
                    # Look for year in various places
                    year_patterns = soup.find_all(string=lambda text: text and any(str(y) in text for y in range(1990, 2025)))
                    for pattern in year_patterns:
                        for y in range(1990, 2025):
                            if str(y) in pattern:
                                year = y
                                break
                        if year:
                            break
                except Exception:
                    pass
                
                # Extract mileage
                mileage = None
                try:
                    import re
                    # Look for mileage in specific sections first
                    mileage_selectors = [
                        '[data-testid="mileage"]',
                        '.offer-params__value',
                        '.parameter-value'
                    ]
                    
                    for selector in mileage_selectors:
                        mileage_elements = soup.select(selector)
                        for element in mileage_elements:
                            text = element.get_text(strip=True).lower()
                            if 'km' in text:
                                # Extract numbers from mileage text - improved pattern
                                mileage_pattern = re.search(r'(\d{1,3}(?:[\s\xa0]*\d{3})*)\s*km', text)
                                if mileage_pattern:
                                    mileage_str = mileage_pattern.group(1).replace(' ', '').replace('\xa0', '')
                                    if mileage_str.isdigit() and 1 <= len(mileage_str) <= 7:  # Reasonable length
                                        mileage_val = int(mileage_str)
                                        if mileage_val <= 9999999:  # Max reasonable mileage
                                            mileage = mileage_val
                                            break
                        if mileage:
                            break
                    
                    # Fallback: look for mileage in parameter tables
                    if mileage is None:
                        param_sections = soup.find_all(['li', 'div'], class_=re.compile(r'param|detail|spec'))
                        for section in param_sections:
                            text = section.get_text(strip=True).lower()
                            if 'przebieg' in text or ('km' in text and any(char.isdigit() for char in text)):
                                # More conservative pattern
                                mileage_pattern = re.search(r'(\d{1,3}(?:[\s\xa0]*\d{3})*)\s*km', text)
                                if mileage_pattern:
                                    mileage_str = mileage_pattern.group(1).replace(' ', '').replace('\xa0', '')
                                    if mileage_str.isdigit() and 1 <= len(mileage_str) <= 7:
                                        mileage_val = int(mileage_str)
                                        if mileage_val <= 9999999:
                                            mileage = mileage_val
                                            break
                except Exception:
                    pass
                
                # Create ad entry
                ad_id = link.split('/')[-1].split('#')[0].split('?')[0]
                
                ad_data = {
                    'id': ad_id,
                    'title': title,
                    'price': price,
                    'year': year,
                    'mileage': mileage,
                    'url': link,
                    'model': model,
                    'scrape_date': datetime.datetime.now().isoformat(),
                    'scrape_timestamp': int(time.time())
                }
                
                self.ads.append(ad_data)
                successful_fetches += 1
                
                # Small delay to be respectful
                time.sleep(0.1)
                
            except Exception as e:
                failed_fetches += 1
                click.echo(f"Error fetching ad from {link}: {str(e)}")
                continue
        
        click.echo(f"Fetch summary: {successful_fetches} successful, {failed_fetches} failed, {filtered_out} filtered out (not LC models)")
    
    def save_ads(self, model):
        """
        Save ads to CSV and JSON
        Args:
            model: car model to save
        """
        if not self.ads:
            click.echo(f"No ads found for {model}")
            return
            
        # Create model-specific data
        model_ads = [ad for ad in self.ads if ad['model'] == model]
        if not model_ads:
            click.echo(f"No ads found for model {model}")
            return
        
        df = pd.DataFrame(model_ads)
        
        # Save to CSV
        csv_file = os.path.join(self.data_directory, f'{model.replace("/", "_")}.csv')
        df.to_csv(csv_file, index=False)
        
        # Save to JSON
        json_file = os.path.join(self.data_directory, f'{model.replace("/", "_")}.json')
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(model_ads, f, indent=2, ensure_ascii=False)
        
        click.echo(f"Saved {len(model_ads)} ads for {model}")
        click.echo(f"  CSV: {csv_file}")
        click.echo(f"  JSON: {json_file}")


class CarScraper:
    """
    Scraps cars from otomoto.pl
    Args:
        data_directory: path to directory where data will be saved
    """

    def __init__(self, data_directory):
        click.echo('Initializing Car scraper')
        self.data_directory = Path(data_directory)
        self.data_directory.mkdir(parents=True, exist_ok=True)
        self.ad_fetcher = AdvertisementFetcher(str(self.data_directory))

    def get_cars_in_page(self, path, page_num):
        """
        Gets cars in page
        Args:
            path: path to page
            page_num: page number
        return:
            list of links
        """
        click.echo(f'Scraping page: {page_num}')
        headers = [
            {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7',
                'Referer': 'https://www.google.com/',
            },
            {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/109.0',
                'Accept-Language': 'pl-PL,pl;q=0.9,en-US,en;q=0.7',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Referer': 'https://www.google.com/',
            }
        ]
        
        header = random.choice(headers)
        
        try:
            if page_num == 1:
                url = path  # First page uses base URL
            else:
                # Add page parameter for subsequent pages
                separator = '&' if '?' in path else '?'
                url = f'{path}{separator}page={page_num}'
                
            res = httpx.get(url, headers=header, timeout=30)
            res.raise_for_status()
        except Exception as e:
            click.echo(f"Error fetching page {page_num}: {str(e)}")
            return []
        
        soup = BeautifulSoup(res.text, features='lxml')
        links = []
        
        # Try different selectors for car links
        try:
            # Try main search results container
            car_links_section = soup.find('main', attrs={'data-testid': 'search-results'})
            if car_links_section:
                articles = car_links_section.find_all('article')
                for article in articles:
                    try:
                        link_element = article.find('a', href=True)
                        if link_element and link_element['href']:
                            full_link = link_element['href']
                            if not full_link.startswith('http'):
                                full_link = 'https://www.otomoto.pl' + full_link
                            links.append(full_link)
                    except Exception:
                        continue
            
            # Alternative selector
            if not links:
                car_links_section = soup.find('div', attrs={'data-testid': 'search-results'})
                if car_links_section:
                    articles = car_links_section.find_all('article')  # Remove the data-media-size filter
                    for article in articles:
                        try:
                            # Try multiple ways to find the link
                            link_element = article.find('a', href=True)
                            if not link_element:
                                # Try finding in section
                                section = article.find('section')
                                if section:
                                    link_element = section.find('a', href=True)
                            if not link_element:
                                # Try finding by heading link
                                heading = article.find('h2')
                                if heading:
                                    link_element = heading.find('a', href=True)
                            
                            if link_element and link_element['href']:
                                full_link = link_element['href']
                                if not full_link.startswith('http'):
                                    full_link = 'https://www.otomoto.pl' + full_link
                                links.append(full_link)
                        except Exception:
                            continue
                            
        except Exception as e:
            click.echo(f"Error parsing page {page_num}: {str(e)}")

        click.echo(f'Found {len(links)} links on page {page_num}')
        return links

    def scrape_model(self, search_url, model_name, max_pages=10):
        """
        Scraps model from search URL
        Args:
            search_url: URL to search for cars
            model_name: name to save the model as
            max_pages: maximum number of pages to scrape
        """
        click.echo(f'Start scraping model: {model_name}')
        self.ad_fetcher.setup_fetcher()
        
        # Get the first page to determine total pages
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7',
                'Referer': 'https://www.google.com/',
            }
            res = httpx.get(search_url, headers=headers, timeout=30)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, features='lxml')
            
            # Try to find pagination info
            last_page_num = 1
            try:
                # Look for pagination items with the correct class pattern
                pagination_items = soup.find_all('li', class_=re.compile(r'ooa-.*'))
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
                    pagination_container = soup.find('nav', attrs={'aria-label': re.compile(r'[Pp]aginat.*')})
                    if pagination_container:
                        page_links = pagination_container.find_all('li')
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
                
            last_page_num = min(last_page_num, max_pages)
            click.echo(f'Model has: {last_page_num} pages (limited to {max_pages})')
            
        except Exception as e:
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
                click.echo(f"Error scraping page {page}: {str(e)}")
                continue
                
        self.ad_fetcher.save_ads(model_name)
        click.echo(f'End scraping model: {model_name}')


def store_individual_listings_data(data_dir, date_str, output_format):
    """
    Store individual listings data with time series tracking
    
    Args:
        data_dir: Path to data directory
        date_str: Date string in YYYY-MM-DD format
        output_format: 'json' or 'csv'
    """
    data_path = Path(data_dir)
    listings_dir = data_path / 'individual_listings'
    listings_dir.mkdir(exist_ok=True)
    
    # Find all model data files
    model_files = list(data_path.glob('*.json')) + list(data_path.glob('*.csv'))
    
    if not model_files:
        click.echo("No model data files found. Skipping individual listings storage.")
        return
    
    all_listings = []
    
    for file_path in model_files:
        try:
            if file_path.suffix == '.json':
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:  # CSV
                data = pd.read_csv(file_path).to_dict('records')
            
            if len(data) == 0:
                continue
                
            # Add current data to listings
            all_listings.extend(data)
                
        except Exception as e:
            click.echo(f"Error processing {file_path}: {str(e)}")
            continue
    
    if not all_listings:
        click.echo("No valid listings found.")
        return
    
    # Load existing historical data
    historical_file = listings_dir / f"listings_history.{output_format}"
    existing_data = []
    
    try:
        if historical_file.exists():
            if output_format == 'json':
                with open(historical_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            else:
                existing_df = pd.read_csv(historical_file)
                existing_data = existing_df.to_dict('records')
    except Exception as e:
        click.echo(f"Error loading existing data: {str(e)}")
    
    # Update historical data with new entries
    updated_data = update_listings_history(existing_data, all_listings, date_str, data_dir)
    
    # Save updated historical data
    try:
        if output_format == 'json':
            with open(historical_file, 'w', encoding='utf-8') as f:
                json.dump(updated_data, f, indent=2, ensure_ascii=False)
        else:
            pd.DataFrame(updated_data).to_csv(historical_file, index=False)
        
        click.echo(f"Updated listings history: {len(updated_data)} total entries")
        click.echo(f"Historical data saved to {historical_file}")
        
    except Exception as e:
        click.echo(f"Error saving historical data: {str(e)}")


def update_listings_history(existing_data, new_listings, date_str, data_dir='./data'):
    """
    Update listings history with new data, tracking price changes for individual listings
    and automatically assigning internal IDs
    """
    # Load or create ID mapping for automatic internal ID assignment
    id_mapping, next_id = load_or_create_id_mapping(data_dir)
    
    # First, ensure all existing data has internal IDs
    for entry in existing_data:
        listing_id = entry.get('id')
        if listing_id:
            # Assign internal ID if this listing doesn't have one yet
            if listing_id not in id_mapping:
                id_mapping[listing_id] = next_id
                next_id += 1
            # Add internal_id to existing entry if it doesn't have one
            if 'internal_id' not in entry:
                entry['internal_id'] = id_mapping[listing_id]
    
    # Create a lookup for existing listings by ID
    existing_by_id = {}
    for entry in existing_data:
        listing_id = entry.get('id')
        if listing_id:
            if listing_id not in existing_by_id:
                existing_by_id[listing_id] = []
            existing_by_id[listing_id].append(entry)
    
    updated_data = list(existing_data)  # Keep all existing data
    
    # Process new listings
    for listing in new_listings:
        listing_id = listing.get('id')
        if not listing_id:
            continue
            
        # Assign internal ID if this listing doesn't have one yet
        if listing_id not in id_mapping:
            id_mapping[listing_id] = next_id
            next_id += 1
            
        # Check if this is a new price entry for an existing listing
        existing_entries = existing_by_id.get(listing_id, [])
        
        # Check if we already have an entry for this exact date
        date_exists = any(entry.get('date') == date_str for entry in existing_entries)
        
        if not date_exists:
            # Add new entry with date and internal ID
            new_entry = listing.copy()
            new_entry['date'] = date_str
            new_entry['internal_id'] = id_mapping[listing_id]  # Add internal ID
            updated_data.append(new_entry)
            
            # Calculate price change if we have previous data
            if existing_entries:
                latest_entry = max(existing_entries, key=lambda x: x.get('date', ''))
                if latest_entry.get('price') and listing.get('price'):
                    price_change = listing['price'] - latest_entry['price']
                    new_entry['price_change'] = price_change
                    new_entry['price_change_percent'] = (price_change / latest_entry['price']) * 100
                else:
                    new_entry['price_change'] = 0
                    new_entry['price_change_percent'] = 0
            else:
                new_entry['price_change'] = 0
                new_entry['price_change_percent'] = 0
    
    # Save the updated ID mapping
    save_id_mapping(data_dir, id_mapping)
    
    return updated_data


def generate_individual_listing_plots(data_dir, model=None, min_data_points=2):
    """
    Generate plots showing individual listing price trends over time
    """
    listings_dir = Path(data_dir) / 'individual_listings'
    historical_file_csv = listings_dir / 'listings_history.csv'
    historical_file_json = listings_dir / 'listings_history.json'
    
    # Try CSV first (new format with internal IDs), then JSON (legacy)
    if historical_file_csv.exists():
        try:
            df = pd.read_csv(historical_file_csv)
        except Exception as e:
            click.echo(f"Error loading CSV data: {str(e)}")
            return
    elif historical_file_json.exists():
        try:
            with open(historical_file_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            df = pd.DataFrame(data)
        except Exception as e:
            click.echo(f"Error loading JSON data: {str(e)}")
            return
    else:
        click.echo("No historical listings data found. Run scraping first.")
        return
    
    if len(df) == 0:
        click.echo("No data found in historical file.")
        return
    
    # Filter by model if specified
    if model:
        df = df[df['model'] == model]
        if len(df) == 0:
            click.echo(f"No data found for model: {model}")
            return
    
    # Convert date to datetime
    df['date'] = pd.to_datetime(df['date'])
    
    # Group by listing ID and filter listings with multiple data points
    listing_groups = df.groupby('id')
    valid_listings = []
    
    for listing_id, group in listing_groups:
        if len(group) >= min_data_points and group['price'].notna().sum() >= min_data_points:
            valid_listings.append((listing_id, group))
    
    if not valid_listings:
        click.echo(f"No listings found with at least {min_data_points} data points.")
        return
    
    # Create plots
    plots_dir = Path(data_dir) / 'plots'
    plots_dir.mkdir(exist_ok=True)
    
    # Individual listing trends plot
    plt.figure(figsize=(15, 10))
    
    colors = plt.cm.tab20(range(len(valid_listings)))
    
    for idx, (listing_id, group) in enumerate(valid_listings[:20]):  # Limit to 20 for readability
        group_sorted = group.sort_values('date')
        valid_prices = group_sorted[group_sorted['price'] > 0]
        
        if len(valid_prices) >= min_data_points:
            # Get internal ID for legend (fallback to index if not available)
            internal_id = group_sorted['internal_id'].iloc[0] if 'internal_id' in group_sorted.columns else idx + 1
            plt.plot(valid_prices['date'], valid_prices['price'], 
                    marker='o', linewidth=2, markersize=4, 
                    color=colors[idx], alpha=0.8,
                    label=f"#{internal_id}")  # Use internal ID
    
    plt.title(f'Individual Listing Price Trends Over Time{" - " + model if model else ""}')
    plt.xlabel('Date')
    plt.ylabel('Price (PLN)')
    plt.xticks(rotation=45)
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    plot_file = plots_dir / f'individual_listings_trends{"_" + model.replace("/", "_") if model else ""}.png'
    plt.savefig(plot_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    click.echo(f"Individual listings plot saved to {plot_file}")
    
    # Price change analysis
    analyze_price_changes(df, plots_dir, model)


def analyze_price_changes(df, plots_dir, model=None):
    """
    Analyze and plot price changes for listings
    """
    # Get latest data for each listing
    latest_data = df.groupby('id').last().reset_index()
    
    # Filter listings with price changes
    price_changes = latest_data[latest_data['price_change'].notna() & (latest_data['price_change'] != 0)]
    
    if len(price_changes) == 0:
        click.echo("No price changes detected.")
        return
    
    # Sort by price change
    price_changes = price_changes.sort_values('price_change')
    
    # Create price change analysis plot
    plt.figure(figsize=(12, 8))
    
    # Color code: red for decreases, green for increases
    colors = ['red' if x < 0 else 'green' for x in price_changes['price_change']]
    
    plt.bar(range(len(price_changes)), price_changes['price_change'], color=colors, alpha=0.7)
    plt.title(f'Price Changes by Listing{" - " + model if model else ""}')
    plt.xlabel('Listings (sorted by price change)')
    plt.ylabel('Price Change (PLN)')
    plt.axhline(y=0, color='black', linestyle='-', alpha=0.3)
    plt.xticks([])  # Hide x-axis labels as they're not meaningful
    plt.grid(True, alpha=0.3)
    
    # Add summary text
    decreases = price_changes[price_changes['price_change'] < 0]
    increases = price_changes[price_changes['price_change'] > 0]
    
    summary_text = f'Decreases: {len(decreases)} listings\nIncreases: {len(increases)} listings'
    if len(decreases) > 0:
        summary_text += f'\nLargest decrease: {decreases["price_change"].min():,.0f} PLN'
    if len(increases) > 0:
        summary_text += f'\nLargest increase: {increases["price_change"].max():,.0f} PLN'
    
    plt.text(0.02, 0.98, summary_text, transform=plt.gca().transAxes, 
             verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    plt.tight_layout()
    
    plot_file = plots_dir / f'price_changes{"_" + model.replace("/", "_") if model else ""}.png'
    plt.savefig(plot_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    click.echo(f"Price changes plot saved to {plot_file}")
    
    # Print top price changes
    click.echo("\nTop 5 Price Decreases:")
    top_decreases = decreases.nsmallest(5, 'price_change')[['id', 'internal_id', 'title', 'price', 'price_change', 'url']]
    for _, row in top_decreases.iterrows():
        internal_id = row.get('internal_id', 'N/A')
        click.echo(f"  #{internal_id} {row['title'][:40]}: {row['price_change']:,.0f} PLN ({row['url']})")
    
    click.echo("\nTop 5 Price Increases:")
    top_increases = increases.nlargest(5, 'price_change')[['id', 'internal_id', 'title', 'price', 'price_change', 'url']]
    for _, row in top_increases.iterrows():
        internal_id = row.get('internal_id', 'N/A')
        click.echo(f"  #{internal_id} {row['title'][:40]}: +{row['price_change']:,.0f} PLN ({row['url']})")


def store_time_series_data(data_dir, date_str, output_format):
    """
    Legacy function - now redirects to individual listings tracking
    """
    click.echo("Storing individual listings data (new tracking system)...")
    store_individual_listings_data(data_dir, date_str, output_format)


def update_historical_data(time_series_dir, new_data, output_format):
    """
    Update the historical data file with new data
    """
    historical_file = time_series_dir / f"historical.{output_format}"
    
    try:
        if output_format == 'json':
            if historical_file.exists():
                with open(historical_file, 'r', encoding='utf-8') as f:
                    historical_data = json.load(f)
            else:
                historical_data = []
            
            # Remove existing data for the same date and models to prevent duplicates
            new_entries = {(item['model'], item['date']) for item in new_data}
            historical_data = [item for item in historical_data 
                             if (item['model'], item['date']) not in new_entries]
            
            historical_data.extend(new_data)
            
            with open(historical_file, 'w', encoding='utf-8') as f:
                json.dump(historical_data, f, indent=2, ensure_ascii=False)
        else:
            if historical_file.exists():
                historical_df = pd.read_csv(historical_file)
            else:
                historical_df = pd.DataFrame()
            
            new_df = pd.DataFrame(new_data)
            
            # Remove existing data for the same date and model combinations
            if len(historical_df) > 0 and len(new_df) > 0:
                for _, row in new_df.iterrows():
                    historical_df = historical_df[
                        ~((historical_df['date'] == row['date']) & 
                          (historical_df['model'] == row['model']))
                    ]
            
            combined_df = pd.concat([historical_df, new_df], ignore_index=True)
            combined_df.to_csv(historical_file, index=False)
        
        click.echo(f"Updated historical data in {historical_file}")
        
    except Exception as e:
        click.echo(f"Error updating historical data: {str(e)}")


def generate_plots(data_dir, model=None, plot_type='individual'):
    """
    Generate plots from individual listings data (new system)
    """
    click.echo("Generating individual listings plots...")
    generate_individual_listing_plots(data_dir, model)
    
    click.echo("Generating enhanced individual plots...")
    generate_enhanced_individual_plots(data_dir, model)
    
    click.echo("Generating year-based analysis plots...")
    generate_year_analysis_plots(data_dir, model)
    
    # Also generate legacy aggregated plots if data exists
    generate_legacy_plots(data_dir, model, plot_type)
    
    # Summary of generated plots
    plots_dir = Path(data_dir) / 'plots'
    model_suffix = f"_{model.replace('/', '_')}" if model else ""
    
    click.echo(f"\n--- Plot Generation Summary ---")
    click.echo(f"All plots saved to: {plots_dir}")
    click.echo("Generated plots:")
    click.echo(f"  1. Individual listings trends: individual_listings_trends{model_suffix}.png")
    click.echo(f"  2. Enhanced individual trends (with year markers): enhanced_individual_trends{model_suffix}.png")
    click.echo(f"  3. Year analysis (4-panel): year_analysis{model_suffix}.png")
    click.echo(f"     - Average & median price by year")
    click.echo(f"     - Number of unique cars by year") 
    click.echo(f"     - Price range by year")
    click.echo(f"     - Average mileage by year")
    click.echo(f"  4. Unique cars by year (scatter): listings_by_year{model_suffix}.png")
    click.echo(f"  5. Price vs mileage (colored by year): price_vs_mileage{model_suffix}.png")


def generate_legacy_plots(data_dir, model=None, plot_type='both'):
    """
    Generate legacy aggregated plots from historical data
    """
    time_series_dir = Path(data_dir) / 'time_series'
    historical_csv = time_series_dir / 'historical.csv'
    historical_json = time_series_dir / 'historical.json'
    
    # Load historical data
    if historical_csv.exists():
        data = pd.read_csv(historical_csv)
    elif historical_json.exists():
        with open(historical_json, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        data = pd.DataFrame(json_data)
    else:
        click.echo("No legacy historical data found. Skipping legacy plots.")
        return
    
    if len(data) == 0:
        click.echo("No data available for plotting.")
        return
    
    # Filter by model if specified
    if model:
        data = data[data['model'] == model]
        if len(data) == 0:
            click.echo(f"No data found for model: {model}")
            return
    
    # Convert date to datetime
    data['date'] = pd.to_datetime(data['date'])
    data = data.sort_values(['model', 'date'])
    
    # Create plots directory
    plots_dir = Path(data_dir) / 'plots'
    plots_dir.mkdir(exist_ok=True)
    
    # Generate price plot
    if plot_type in ['price', 'both']:
        plt.figure(figsize=(12, 8))
        for model_name, group in data.groupby('model'):
            plt.plot(group['date'], group['avg_price'], 
                    marker='o', label=f'{model_name} - Avg Price', linewidth=2)
            plt.fill_between(group['date'], group['min_price'], group['max_price'], 
                           alpha=0.2)
        
        plt.title('Car Prices Over Time', fontsize=16)
        plt.xlabel('Date', fontsize=12)
        plt.ylabel('Price (PLN)', fontsize=12)
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        price_plot_path = plots_dir / 'price_trends.png'
        plt.savefig(price_plot_path, dpi=300, bbox_inches='tight')
        plt.close()
        click.echo(f"Price trend plot saved to {price_plot_path}")
    
    # Generate count plot
    if plot_type in ['count', 'both']:
        plt.figure(figsize=(12, 8))
        for model_name, group in data.groupby('model'):
            plt.plot(group['date'], group['count'], 
                    marker='s', label=f'{model_name} - Count', linewidth=2)
        
        plt.title('Number of Listings Over Time', fontsize=16)
        plt.xlabel('Date', fontsize=12)
        plt.ylabel('Number of Listings', fontsize=12)
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        count_plot_path = plots_dir / 'count_trends.png'
        plt.savefig(count_plot_path, dpi=300, bbox_inches='tight')
        plt.close()
        click.echo(f"Count trend plot saved to {count_plot_path}")


def generate_year_analysis_plots(data_dir, model=None):
    """
    Generate comprehensive year-based analysis plots
    """
    listings_dir = Path(data_dir) / 'individual_listings'
    historical_file_csv = listings_dir / 'listings_history.csv'
    historical_file_json = listings_dir / 'listings_history.json'
    
    # Load data (same logic as individual listing plots)
    if historical_file_csv.exists():
        try:
            df = pd.read_csv(historical_file_csv)
        except Exception as e:
            click.echo(f"Error loading CSV data: {str(e)}")
            return
    elif historical_file_json.exists():
        try:
            with open(historical_file_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            df = pd.DataFrame(data)
        except Exception as e:
            click.echo(f"Error loading JSON data: {str(e)}")
            return
    else:
        click.echo("No historical listings data found for year analysis.")
        return
    
    if len(df) == 0:
        click.echo("No data found for year analysis.")
        return
    
    # Filter by model if specified
    if model:
        df = df[df['model'] == model]
        if len(df) == 0:
            click.echo(f"No data found for model: {model}")
            return
    
    # Clean and prepare data
    df['year'] = pd.to_numeric(df['year'], errors='coerce')
    df['price'] = pd.to_numeric(df['price'], errors='coerce')
    df['mileage'] = pd.to_numeric(df['mileage'], errors='coerce')
    
    # Remove invalid data
    df = df.dropna(subset=['year', 'price'])
    df = df[df['price'] > 0]
    df = df[df['year'] > 1990]  # Remove invalid years
    
    if len(df) == 0:
        click.echo("No valid data found for year analysis.")
        return
    
    # IMPORTANT: Deduplicate by internal_id to get unique cars only
    # This prevents counting the same car multiple times from different scrape dates
    if 'internal_id' in df.columns:
        original_count = len(df)
        # Keep the most recent entry for each unique car (internal_id)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').groupby('internal_id').tail(1)
        click.echo(f"Deduplicated from {original_count} entries to {len(df)} unique cars")
    else:
        click.echo("Warning: No internal_id column found, analysis may include duplicates")
    
    if len(df) == 0:
        click.echo("No unique cars found after deduplication.")
        return
    
    # Create plots directory
    plots_dir = Path(data_dir) / 'plots'
    plots_dir.mkdir(exist_ok=True)
    
    # 1. Average Price by Year Plot
    plt.figure(figsize=(14, 8))
    year_stats = df.groupby('year').agg({
        'price': ['mean', 'median', 'min', 'max', 'count'],
        'mileage': 'mean'
    }).round(0)
    
    year_stats.columns = ['avg_price', 'median_price', 'min_price', 'max_price', 'count', 'avg_mileage']
    year_stats = year_stats.reset_index()
    
    plt.subplot(2, 2, 1)
    plt.bar(year_stats['year'], year_stats['avg_price'], alpha=0.7, color='skyblue', label='Average Price')
    plt.plot(year_stats['year'], year_stats['median_price'], marker='o', color='red', linewidth=2, label='Median Price')
    plt.title(f'Average & Median Price by Year (Unique Cars){" - " + model if model else ""}')
    plt.xlabel('Year')
    plt.ylabel('Price (PLN)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    
    # 2. Number of Listings by Year
    plt.subplot(2, 2, 2)
    plt.bar(year_stats['year'], year_stats['count'], alpha=0.7, color='lightgreen')
    plt.title(f'Number of Unique Cars by Year{" - " + model if model else ""}')
    plt.xlabel('Year')
    plt.ylabel('Number of Unique Cars')
    plt.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    
    # Add count labels on bars
    for i, v in enumerate(year_stats['count']):
        plt.text(year_stats['year'].iloc[i], v + max(year_stats['count']) * 0.01, str(int(v)), 
                ha='center', va='bottom', fontsize=8)
    
    # 3. Price Range by Year (Min/Max)
    plt.subplot(2, 2, 3)
    plt.fill_between(year_stats['year'], year_stats['min_price'], year_stats['max_price'], 
                     alpha=0.3, color='orange', label='Price Range')
    plt.plot(year_stats['year'], year_stats['avg_price'], marker='o', color='blue', 
             linewidth=2, label='Average Price')
    plt.title(f'Price Range by Year (Unique Cars){" - " + model if model else ""}')
    plt.xlabel('Year')
    plt.ylabel('Price (PLN)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    
    # 4. Average Mileage by Year
    plt.subplot(2, 2, 4)
    valid_mileage = year_stats[year_stats['avg_mileage'].notna()]
    if len(valid_mileage) > 0:
        plt.bar(valid_mileage['year'], valid_mileage['avg_mileage'], alpha=0.7, color='coral')
        plt.title(f'Average Mileage by Year (Unique Cars){" - " + model if model else ""}')
        plt.xlabel('Year')
        plt.ylabel('Average Mileage (km)')
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
    
    plt.tight_layout()
    
    year_plot_file = plots_dir / f'year_analysis{"_" + model.replace("/", "_") if model else ""}.png'
    plt.savefig(year_plot_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    click.echo(f"Year analysis plot saved to {year_plot_file}")
    
    # 5. Individual Listings with Year-based Markers
    plt.figure(figsize=(16, 10))
    
    # Convert date to datetime
    df['date'] = pd.to_datetime(df['date'])
    
    # Create year-based color mapping
    unique_years = sorted(df['year'].unique())
    year_colors = plt.cm.viridis(np.linspace(0, 1, len(unique_years)))
    year_color_map = dict(zip(unique_years, year_colors))
    
    # Define markers for different year ranges
    markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', '*', 'h']
    year_markers = {}
    for i, year in enumerate(unique_years):
        year_markers[year] = markers[i % len(markers)]
    
    # Plot each listing with year-based styling
    for _, row in df.iterrows():
        year = row['year']
        internal_id = row.get('internal_id', 'N/A')
        
        plt.scatter(row['date'], row['price'], 
                   color=year_color_map[year], 
                   marker=year_markers[year],
                   s=60, alpha=0.7,
                   label=f"{int(year)}" if f"{int(year)}" not in plt.gca().get_legend_handles_labels()[1] else "")
    
    plt.title(f'Unique Cars by Year{" - " + model if model else ""}')
    plt.xlabel('Date')
    plt.ylabel('Price (PLN)')
    plt.xticks(rotation=45)
    plt.grid(True, alpha=0.3)
    
    # Create custom legend for years
    handles, labels = plt.gca().get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    sorted_items = sorted(by_label.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0)
    plt.legend([item[1] for item in sorted_items], [item[0] for item in sorted_items], 
              title='Production Year', bbox_to_anchor=(1.05, 1), loc='upper left')
    
    plt.tight_layout()
    
    year_scatter_file = plots_dir / f'listings_by_year{"_" + model.replace("/", "_") if model else ""}.png'
    plt.savefig(year_scatter_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    click.echo(f"Year-based scatter plot saved to {year_scatter_file}")
    
    # 6. Price vs Mileage with Year Coloring
    plt.figure(figsize=(12, 8))
    
    valid_data = df[df['mileage'].notna() & (df['mileage'] > 0)]
    if len(valid_data) > 0:
        scatter = plt.scatter(valid_data['mileage'], valid_data['price'], 
                            c=valid_data['year'], cmap='viridis', 
                            s=60, alpha=0.7)
        
        plt.colorbar(scatter, label='Production Year')
        plt.title(f'Price vs Mileage (unique cars, colored by year){" - " + model if model else ""}')
        plt.xlabel('Mileage (km)')
        plt.ylabel('Price (PLN)')
        plt.grid(True, alpha=0.3)
        
        # Add trend line
        z = np.polyfit(valid_data['mileage'], valid_data['price'], 1)
        p = np.poly1d(z)
        plt.plot(valid_data['mileage'], p(valid_data['mileage']), "r--", alpha=0.8, linewidth=2)
        
        plt.tight_layout()
        
        price_mileage_file = plots_dir / f'price_vs_mileage{"_" + model.replace("/", "_") if model else ""}.png'
        plt.savefig(price_mileage_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        click.echo(f"Price vs mileage plot saved to {price_mileage_file}")
    
    # Print summary statistics
    click.echo(f"\n--- Year Analysis Summary{' - ' + model if model else ''} ---")
    click.echo(f"Total unique cars: {len(df)}")
    click.echo(f"Year range: {int(df['year'].min())} - {int(df['year'].max())}")
    click.echo(f"Price range: {df['price'].min():,.0f} - {df['price'].max():,.0f} PLN")
    if df['mileage'].notna().sum() > 0:
        click.echo(f"Mileage range: {df['mileage'].min():,.0f} - {df['mileage'].max():,.0f} km")
    
    click.echo("\nUnique cars by year:")
    for _, row in year_stats.iterrows():
        year = int(row['year'])
        count = int(row['count'])
        avg_price = int(row['avg_price'])
        click.echo(f"  {year}: {count} cars, avg price: {avg_price:,} PLN")


def generate_enhanced_individual_plots(data_dir, model=None, min_data_points=2):
    """
    Enhanced version of individual listing plots with year-based markers
    """
    listings_dir = Path(data_dir) / 'individual_listings'
    historical_file_csv = listings_dir / 'listings_history.csv'
    historical_file_json = listings_dir / 'listings_history.json'
    
    # Load data (same logic as before)
    if historical_file_csv.exists():
        try:
            df = pd.read_csv(historical_file_csv)
        except Exception as e:
            click.echo(f"Error loading CSV data: {str(e)}")
            return
    elif historical_file_json.exists():
        try:
            with open(historical_file_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            df = pd.DataFrame(data)
        except Exception as e:
            click.echo(f"Error loading JSON data: {str(e)}")
            return
    else:
        click.echo("No historical listings data found.")
        return
    
    if len(df) == 0:
        click.echo("No data found.")
        return
    
    # Filter by model if specified
    if model:
        df = df[df['model'] == model]
        if len(df) == 0:
            click.echo(f"No data found for model: {model}")
            return
    
    # Convert date to datetime and clean data
    df['date'] = pd.to_datetime(df['date'])
    df['year'] = pd.to_numeric(df['year'], errors='coerce')
    
    # Group by listing ID and filter listings with multiple data points
    listing_groups = df.groupby('id')
    valid_listings = []
    
    for listing_id, group in listing_groups:
        if len(group) >= min_data_points and group['price'].notna().sum() >= min_data_points:
            valid_listings.append((listing_id, group))
    
    if not valid_listings:
        click.echo(f"No listings found with at least {min_data_points} data points for trend analysis.")
        return
    
    # Create plots directory
    plots_dir = Path(data_dir) / 'plots'
    plots_dir.mkdir(exist_ok=True)
    
    # Enhanced individual listing trends with year-based markers
    plt.figure(figsize=(16, 10))
    
    # Create year-based color and marker mapping
    all_years = df['year'].dropna().unique()
    year_colors = plt.cm.tab20(np.linspace(0, 1, len(all_years)))
    year_color_map = dict(zip(sorted(all_years), year_colors))
    
    markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', '*', 'h']
    year_markers = {}
    for i, year in enumerate(sorted(all_years)):
        year_markers[year] = markers[i % len(markers)]
    
    for idx, (listing_id, group) in enumerate(valid_listings[:20]):  # Limit to 20 for readability
        group_sorted = group.sort_values('date')
        valid_prices = group_sorted[group_sorted['price'] > 0]
        
        if len(valid_prices) >= min_data_points:
            # Get internal ID and year for styling
            internal_id = group_sorted['internal_id'].iloc[0] if 'internal_id' in group_sorted.columns else idx + 1
            year = group_sorted['year'].iloc[0] if 'year' in group_sorted.columns and pd.notna(group_sorted['year'].iloc[0]) else 2020
            
            color = year_color_map.get(year, 'gray')
            marker = year_markers.get(year, 'o')
            
            plt.plot(valid_prices['date'], valid_prices['price'], 
                    marker=marker, linewidth=2, markersize=6, 
                    color=color, alpha=0.8,
                    label=f"#{internal_id} ({int(year)})")
    
    plt.title(f'Individual Listing Price Trends (with production year){" - " + model if model else ""}')
    plt.xlabel('Date')
    plt.ylabel('Price (PLN)')
    plt.xticks(rotation=45)
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    enhanced_plot_file = plots_dir / f'enhanced_individual_trends{"_" + model.replace("/", "_") if model else ""}.png'
    plt.savefig(enhanced_plot_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    click.echo(f"Enhanced individual trends plot saved to {enhanced_plot_file}")


# Click CLI Commands
@click.group()
def cli():
    """Car scraper CLI for otomoto.pl"""
    pass


@cli.command()
@click.option('--url', required=True, help='Search URL from otomoto.pl')
@click.option('--model', required=True, help='Model name to save data as')
@click.option('--data-dir', default='./data', help='Directory to save data')
@click.option('--max-pages', default=10, help='Maximum number of pages to scrape')
@click.option('--format', 'output_format', default='csv', type=click.Choice(['csv', 'json']), help='Output format')
def scrape(url, model, data_dir, max_pages, output_format):
    """Scrape car listings from otomoto.pl"""
    click.echo(f"Starting scrape for model: {model}")
    click.echo(f"URL: {url}")
    click.echo(f"Data directory: {data_dir}")
    click.echo(f"Max pages: {max_pages}")
    
    # Initialize scraper
    scraper = CarScraper(data_dir)
    
    # Scrape the model
    scraper.scrape_model(url, model, max_pages)
    
    # Store time series data
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    store_time_series_data(data_dir, today, output_format)
    
    click.echo("Scraping completed!")


@cli.command()
@click.option('--data-dir', default='./data', help='Directory containing data')
@click.option('--model', help='Specific model to plot (optional)')
@click.option('--type', 'plot_type', default='both', type=click.Choice(['price', 'count', 'both']), help='Type of plot to generate')
def plot(data_dir, model, plot_type):
    """Generate plots from scraped data"""
    click.echo("Generating plots...")
    generate_plots(data_dir, model, plot_type)
    click.echo("Plots generated!")


@cli.command()
@click.option('--data-dir', default='./data', help='Directory containing data')
def status(data_dir):
    """Show scraping status and data summary"""
    data_path = Path(data_dir)
    
    if not data_path.exists():
        click.echo(f"Data directory {data_dir} does not exist.")
        return
    
    # Show model files
    model_files = list(data_path.glob('*.json')) + list(data_path.glob('*.csv'))
    click.echo(f"Found {len(model_files)} model data files:")
    
    for file_path in model_files:
        try:
            if file_path.suffix == '.json':
                with open(file_path, 'r') as f:
                    data = json.load(f)
                count = len(data)
            else:
                df = pd.read_csv(file_path)
                count = len(df)
            
            click.echo(f"  {file_path.name}: {count} records")
        except Exception as e:
            click.echo(f"  {file_path.name}: Error reading file ({str(e)})")
    
    # Show time series data
    time_series_dir = data_path / 'time_series'
    if time_series_dir.exists():
        time_series_files = list(time_series_dir.glob('*.json')) + list(time_series_dir.glob('*.csv'))
        click.echo(f"\nFound {len(time_series_files)} time series files:")
        for file_path in time_series_files:
            click.echo(f"  {file_path.name}")


@cli.command()
@click.option('--data-dir', default='./data', help='Directory containing data')
@click.option('--dry-run', is_flag=True, help='Show what would be removed without actually removing')
def clean(data_dir, dry_run):
    """Remove duplicate entries from time series data"""
    data_path = Path(data_dir)
    time_series_dir = data_path / 'time_series'
    
    if not time_series_dir.exists():
        click.echo("No time series directory found.")
        return
    
    # Clean historical files
    for ext in ['csv', 'json']:
        historical_file = time_series_dir / f"historical.{ext}"
        if not historical_file.exists():
            continue
            
        try:
            if ext == 'json':
                with open(historical_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                df = pd.DataFrame(data)
            else:
                df = pd.read_csv(historical_file)
            
            original_count = len(df)
            
            # Remove duplicates based on model and date
            df_clean = df.drop_duplicates(subset=['model', 'date'], keep='last')
            removed_count = original_count - len(df_clean)
            
            if removed_count > 0:
                if dry_run:
                    click.echo(f"Would remove {removed_count} duplicate entries from {historical_file.name}")
                else:
                    if ext == 'json':
                        with open(historical_file, 'w', encoding='utf-8') as f:
                            json.dump(df_clean.to_dict('records'), f, indent=2, ensure_ascii=False)
                    else:
                        df_clean.to_csv(historical_file, index=False)
                    click.echo(f"Removed {removed_count} duplicate entries from {historical_file.name}")
            else:
                click.echo(f"No duplicates found in {historical_file.name}")
                
        except Exception as e:
            click.echo(f"Error cleaning {historical_file.name}: {str(e)}")
    
    # Clean daily snapshot duplicates if any
    snapshot_files = list(time_series_dir.glob('*.json')) + list(time_series_dir.glob('*.csv'))
    snapshot_files = [f for f in snapshot_files if not f.name.startswith('historical')]
    
    for file_path in snapshot_files:
        try:
            if file_path.suffix == '.json':
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                df = pd.DataFrame(data)
            else:
                df = pd.read_csv(file_path)
            
            original_count = len(df)
            df_clean = df.drop_duplicates(subset=['model', 'date'], keep='last')
            removed_count = original_count - len(df_clean)
            
            if removed_count > 0:
                if dry_run:
                    click.echo(f"Would remove {removed_count} duplicate entries from {file_path.name}")
                else:
                    if file_path.suffix == '.json':
                        with open(file_path, 'w', encoding='utf-8') as f:
                            json.dump(df_clean.to_dict('records'), f, indent=2, ensure_ascii=False)
                    else:
                        df_clean.to_csv(file_path, index=False)
                    click.echo(f"Removed {removed_count} duplicate entries from {file_path.name}")
                        
        except Exception as e:
            click.echo(f"Error cleaning {file_path.name}: {str(e)}")
    
    if dry_run:
        click.echo("\nDry run completed. Use --dry-run=false to actually remove duplicates.")


@cli.command()
@click.option('--data-dir', default='./data', help='Directory containing data')
@click.option('--change-count', default=5, help='Number of listings to modify for demonstration')
def simulate_changes(data_dir, change_count):
    """Simulate price changes for demonstration purposes"""
    click.echo(f"Simulating price changes for {change_count} listings...")
    
    data_path = Path(data_dir)
    listings_dir = data_path / 'individual_listings'
    historical_file = listings_dir / 'listings_history.json'
    
    if not historical_file.exists():
        click.echo("No historical data found. Run scraping first.")
        return
    
    try:
        with open(historical_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        click.echo(f"Error loading historical data: {str(e)}")
        return
    
    if not data:
        click.echo("No data found.")
        return
    
    import random
    from datetime import datetime, timedelta
    
    # Get unique listing IDs with valid prices
    valid_listings = {}
    for entry in data:
        if entry.get('price') and entry.get('price') > 0 and entry.get('id'):
            if entry['id'] not in valid_listings:
                valid_listings[entry['id']] = entry
    
    if len(valid_listings) < change_count:
        change_count = len(valid_listings)
        click.echo(f"Reducing change count to {change_count} (available listings)")
    
    # Select random listings to modify
    selected_ids = random.sample(list(valid_listings.keys()), change_count)
    
    # Create new date (tomorrow)
    new_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    # Simulate price changes
    for listing_id in selected_ids:
        original_listing = valid_listings[listing_id]
        original_price = original_listing['price']
        
        # Generate realistic price change (-20% to +10%)
        change_percent = random.uniform(-0.20, 0.10)
        new_price = int(original_price * (1 + change_percent))
        price_change = new_price - original_price
        
        # Create new entry with changed price
        new_entry = original_listing.copy()
        new_entry['price'] = new_price
        new_entry['date'] = new_date
        new_entry['scrape_date'] = datetime.now().isoformat()
        new_entry['scrape_timestamp'] = int(time.time())
        new_entry['price_change'] = price_change
        new_entry['price_change_percent'] = change_percent * 100
        
        data.append(new_entry)
        
        change_str = f"{price_change:+,} PLN ({change_percent*100:+.1f}%)"
        click.echo(f"  {listing_id[:20]}... {original_price:,} → {new_price:,} ({change_str})")
    
    # Save updated data
    try:
        with open(historical_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Also update CSV
        csv_file = listings_dir / 'listings_history.csv'
        pd.DataFrame(data).to_csv(csv_file, index=False)
        
        click.echo(f"Simulated {change_count} price changes for date {new_date}")
        click.echo("Now run 'plot' command to see the changes!")
        
    except Exception as e:
        click.echo(f"Error saving simulated data: {str(e)}")


@cli.command()
@click.option('--data-dir', default='./data', help='Directory containing data')
def demo(data_dir):
    """Run a complete demonstration of the price tracking system"""
    click.echo("🚗 Starting Car Price Tracking Demonstration...")
    click.echo()
    
    # Step 1: Check current data
    click.echo("📊 Step 1: Checking current data...")
    ctx = click.get_current_context()
    ctx.invoke(status, data_dir=data_dir)
    click.echo()
    
    # Step 2: Simulate some price changes
    click.echo("💰 Step 2: Simulating price changes...")
    ctx.invoke(simulate_changes, data_dir=data_dir, change_count=8)
    click.echo()
    
    # Step 3: Generate plots
    click.echo("📈 Step 3: Generating updated plots...")
    ctx.invoke(plot, data_dir=data_dir, model="lexus-lc")
    click.echo()
    
    # Step 4: Show summary
    click.echo("📋 Step 4: Final status...")
    ctx.invoke(status, data_dir=data_dir)
    click.echo()
    
    click.echo("✅ Demonstration complete!")
    click.echo("🔍 Check the plots in 'data/plots/' to see individual listing price trends")
    click.echo("🎯 Run 'python -m src.main scrape --url \"https://www.otomoto.pl/osobowe/lexus/lc\" --model \"lexus-lc\"' regularly to track real price changes")


def load_or_create_id_mapping(data_dir):
    """
    Load existing ID mapping or create new one
    Returns: (id_mapping dict, next_available_id int)
    """
    listings_dir = Path(data_dir) / 'individual_listings'
    listings_dir.mkdir(exist_ok=True)
    id_mapping_file = listings_dir / 'id_mapping.json'
    
    id_mapping = {}
    if id_mapping_file.exists():
        try:
            with open(id_mapping_file, 'r', encoding='utf-8') as f:
                id_mapping = json.load(f)
        except Exception as e:
            click.echo(f"Warning: Could not load ID mapping: {str(e)}")
    
    # Find next available internal ID
    existing_internal_ids = set(id_mapping.values()) if id_mapping else set()
    next_id = 1
    while next_id in existing_internal_ids:
        next_id += 1
    
    return id_mapping, next_id


def save_id_mapping(data_dir, id_mapping):
    """
    Save ID mapping to file
    """
    listings_dir = Path(data_dir) / 'individual_listings'
    id_mapping_file = listings_dir / 'id_mapping.json'
    
    try:
        with open(id_mapping_file, 'w', encoding='utf-8') as f:
            json.dump(id_mapping, f, indent=2, ensure_ascii=False)
    except Exception as e:
        click.echo(f"Error saving ID mapping: {str(e)}")


def assign_internal_ids_to_existing_data(data_dir):
    """
    Add internal IDs to existing historical data
    """
    listings_dir = Path(data_dir) / 'individual_listings'
    historical_json = listings_dir / 'listings_history.json'
    historical_csv = listings_dir / 'listings_history.csv'
    
    if not historical_json.exists():
        click.echo("No historical data found.")
        return
    
    # Load existing data
    try:
        with open(historical_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        click.echo(f"Error loading historical data: {str(e)}")
        return
    
    if not data:
        click.echo("No data found.")
        return
    
    # Load or create ID mapping
    id_mapping, next_id = load_or_create_id_mapping(data_dir)
    
    # Assign internal IDs to all entries
    for entry in data:
        listing_id = entry.get('id')
        if not listing_id:
            continue
        
        # Assign internal ID if not exists
        if listing_id not in id_mapping:
            id_mapping[listing_id] = next_id
            next_id += 1
        
        # Add internal_id to entry
        entry['internal_id'] = id_mapping[listing_id]
    
    # Save updated data
    try:
        with open(historical_json, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Also update CSV
        if historical_csv.exists():
            pd.DataFrame(data).to_csv(historical_csv, index=False)
        
        # Save ID mapping
        save_id_mapping(data_dir, id_mapping)
        
        click.echo(f"Assigned internal IDs to {len(data)} entries")
        click.echo(f"Total unique listings: {len(id_mapping)}")
        
    except Exception as e:
        click.echo(f"Error saving updated data: {str(e)}")


if __name__ == '__main__':
    cli()


