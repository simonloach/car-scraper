"""Simplified listings storage with integrated price tracking"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import click
import pandas as pd

from src.car_scraper.utils.logger import logger


class SimplifiedListingsStorage:
    """Simplified storage handler with integrated price tracking"""

    def __init__(self, data_dir: str) -> None:
        """
        Initialize storage handler

        Args:
            data_dir: Base data directory
        """
        self.data_dir = Path(data_dir)

    def _get_model_dir(self, model: str) -> Path:
        """
        Get the model-specific directory path

        Args:
            model: Model name (e.g., 'bmw-i8', 'lexus-lc')

        Returns:
            Path to model directory
        """
        model_dir = self.data_dir / model.replace("/", "_")
        model_dir.mkdir(parents=True, exist_ok=True)
        return model_dir

    def _get_model_data_file(self, model: str) -> Path:
        """
        Get the path to the model's JSON data file

        Args:
            model: Model name

        Returns:
            Path to model's JSON file
        """
        model_dir = self._get_model_dir(model)
        return model_dir / f"{model.replace('/', '_')}.json"

    def _assign_internal_id(self, existing_data: List[Dict], listing_id: str) -> int:
        """
        Assign internal ID to a listing

        Args:
            existing_data: Existing listings data
            listing_id: External listing ID

        Returns:
            Internal ID number
        """
        # Find the highest existing internal ID
        max_internal_id = 0
        for listing in existing_data:
            internal_id = listing.get("internal_id", 0)
            if internal_id > max_internal_id:
                max_internal_id = internal_id

        return max_internal_id + 1

    def store_listings_data(
        self, model: str, listings_data: List[Dict], date_str: str
    ) -> None:
        """
        Store listings data with integrated price tracking

        Args:
            model: Model name (e.g., 'bmw-i8')
            listings_data: List of listing dictionaries
            date_str: Date string in YYYY-MM-DD format
        """
        logger.info(f"Storing listings data for model {model} on date: {date_str}")

        if not listings_data:
            logger.warning(f"No listings data provided for model {model}")
            return

        data_file = self._get_model_data_file(model)

        # Load existing data
        existing_data = []
        if data_file.exists():
            try:
                with open(data_file, "r", encoding="utf-8") as f:
                    file_data = json.load(f)

                # Handle both old format (list) and new format (dict with 'listings' key)
                if isinstance(file_data, list):
                    existing_data = file_data  # Old format
                elif isinstance(file_data, dict) and "listings" in file_data:
                    existing_data = list(file_data["listings"].values())  # New format
                else:
                    logger.warning(f"Unknown data format in {data_file}")
                    existing_data = []

            except Exception as e:
                logger.warning(f"Error loading existing data from {data_file}: {e}")
                existing_data = []

        # Create lookup for existing listings
        existing_lookup = {listing["id"]: listing for listing in existing_data}
        current_timestamp = int(time.time())

        # Process new listings
        updated_data = []
        price_changes = 0
        new_listings = 0

        # First, create lookup for current scrape listings
        current_listings_lookup = {
            listing.get("id"): listing for listing in listings_data if listing.get("id")
        }

        # Process all existing listings first (to preserve historical data)
        for existing_listing in existing_data:
            listing_id = existing_listing.get("id")
            if not listing_id:
                continue

            if listing_id in current_listings_lookup:
                # Listing exists in current scrape - update it
                listing_data = current_listings_lookup[listing_id]
                current_price = listing_data.get("price", 0)
                if current_price <= 0:
                    # Keep the existing listing unchanged if price is invalid
                    updated_data.append(existing_listing)
                    continue

                last_price = existing_listing.get(
                    "current_price", existing_listing.get("initial_price", 0)
                )

                # Update basic info
                existing_listing.update(
                    {
                        "title": listing_data.get(
                            "title", existing_listing.get("title", "")
                        ),
                        "year": listing_data.get("year", existing_listing.get("year")),
                        "mileage": listing_data.get(
                            "mileage", existing_listing.get("mileage")
                        ),
                        "url": listing_data.get("url", existing_listing.get("url", "")),
                        "model": model,
                        "current_price": current_price,
                        "last_seen": date_str,
                        "last_scrape_timestamp": current_timestamp,
                    }
                )

                # Check for price change
                if current_price != last_price:
                    price_change = current_price - last_price

                    # Add to price readings
                    if "price_readings" not in existing_listing:
                        existing_listing["price_readings"] = []

                    existing_listing["price_readings"].append(
                        [current_timestamp, current_price]
                    )
                    existing_listing["price_change"] = price_change
                    price_changes += 1

                    logger.info(
                        f"Price change detected for {listing_id}: {last_price} → {current_price} ({price_change:+d})"
                    )

                updated_data.append(existing_listing)
            else:
                # Listing not in current scrape - preserve it as historical
                updated_data.append(existing_listing)

        # Process new listings that weren't in existing data
        for listing_data in listings_data:
            listing_id = listing_data.get("id")
            if not listing_id:
                continue

            current_price = listing_data.get("price", 0)
            if current_price <= 0:
                continue

            if listing_id not in existing_lookup:
                # New listing
                new_listing = {
                    "id": listing_id,
                    "internal_id": self._assign_internal_id(existing_data, listing_id),
                    "title": listing_data.get("title", ""),
                    "initial_price": current_price,
                    "current_price": current_price,
                    "year": listing_data.get("year"),
                    "mileage": listing_data.get("mileage"),
                    "url": listing_data.get("url", ""),
                    "model": model,
                    "first_seen": date_str,
                    "last_seen": date_str,
                    "first_scrape_timestamp": current_timestamp,
                    "last_scrape_timestamp": current_timestamp,
                    "price_readings": [[current_timestamp, current_price]],
                    "price_change": 0,
                }
                updated_data.append(new_listing)
                new_listings += 1

        # Save updated data in new format
        try:
            # Convert list to dictionary keyed by listing id
            listings_dict = {}
            for listing in updated_data:
                listings_dict[listing["id"]] = listing

            # Create new format structure
            new_format_data = {
                "metadata": {
                    "last_updated": datetime.now().isoformat(),
                    "total_listings": len(updated_data),
                    "model": model,
                },
                "listings": listings_dict,
            }

            with open(data_file, "w", encoding="utf-8") as f:
                json.dump(new_format_data, f, indent=2, ensure_ascii=False, default=str)

            logger.info(
                f"Updated data for {model}: {len(updated_data)} total listings, {new_listings} new, {price_changes} price changes"
            )
            click.echo(
                f"Updated data for {model}: {len(updated_data)} total listings, {new_listings} new, {price_changes} price changes"
            )
            click.echo(f"Data saved to {data_file}")

        except Exception as e:
            logger.error(f"Error saving data: {e}")
            click.echo(f"Error saving data: {e}")

    def get_historical_data(self, model: Optional[str] = None) -> pd.DataFrame:
        """
        Get historical data for plotting and analysis

        Args:
            model: Optional model filter

        Returns:
            DataFrame with historical listings data compatible with plotting system
        """
        if model:
            # Get data for specific model
            data_file = self._get_model_data_file(model)

            if not data_file.exists():
                raise FileNotFoundError(f"No data found for model: {model}")

            try:
                with open(data_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if not data:
                    raise ValueError(f"No data found for model: {model}")

                # Handle both old format (list) and new format (dict with 'listings' key)
                if isinstance(data, list):
                    # Old format - convert to DataFrame directly
                    flattened_data = []
                    for listing in data:
                        entry = {
                            "id": listing["id"],
                            "internal_id": listing.get(
                                "id", listing["id"]
                            ),  # Use id as internal_id for old format
                            "title": listing["title"],
                            "price": listing["price"],
                            "year": listing["year"],
                            "mileage": listing["mileage"],
                            "url": listing["url"],
                            "model": listing["model"],
                            "date": listing.get("scrape_date", "").split("T")[0]
                            if "scrape_date" in listing
                            else "",
                            "scrape_timestamp": listing.get("scrape_timestamp", 0),
                        }
                        flattened_data.append(entry)
                    return pd.DataFrame(flattened_data)
                else:
                    # New format - process listings with price history
                    flattened_data = []
                    listings = data.get("listings", {})

                    for listing in listings.values():
                        # Add the current entry (latest data point)
                        main_entry = {
                            "id": listing["id"],
                            "internal_id": listing["internal_id"],
                            "title": listing["title"],
                            "price": listing["current_price"],
                            "year": listing["year"],
                            "mileage": listing["mileage"],
                            "url": listing["url"],
                            "model": listing["model"],
                            "date": listing["last_seen"],
                            "scrape_timestamp": listing["last_scrape_timestamp"],
                        }
                        flattened_data.append(main_entry)

                        # Add historical price readings
                        price_readings = listing.get("price_readings", [])
                        if (
                            len(price_readings) > 1
                        ):  # More than just the initial reading
                            for timestamp, price in price_readings[
                                :-1
                            ]:  # Exclude the last one (already added as main_entry)
                                history_entry = main_entry.copy()
                                history_entry.update(
                                    {
                                        "price": price,
                                        "date": datetime.fromtimestamp(
                                            timestamp
                                        ).strftime("%Y-%m-%d"),
                                        "scrape_timestamp": timestamp,
                                    }
                                )
                                flattened_data.append(history_entry)

                    return pd.DataFrame(flattened_data)

            except Exception as e:
                logger.error(f"Error loading data for model {model}: {e}")
                raise ValueError(f"Error loading data for model {model}: {e}")
        else:
            # Get data for all models
            all_data = []
            model_dirs = [
                d
                for d in self.data_dir.iterdir()
                if d.is_dir() and not d.name.startswith(".") and d.name not in ["plots"]
            ]

            for model_dir in model_dirs:
                model_name = model_dir.name
                data_file = model_dir / f"{model_name}.json"
                if data_file.exists():
                    try:
                        with open(data_file, "r", encoding="utf-8") as f:
                            model_data = json.load(f)
                            all_data.extend(model_data)
                    except Exception as e:
                        logger.warning(f"Error loading data from {data_file}: {e}")
                        continue

            if not all_data:
                raise FileNotFoundError("No data found")

            return pd.DataFrame(all_data)

    def get_summary_stats(self, model: Optional[str] = None) -> Dict:
        """
        Get summary statistics for the data

        Args:
            model: Optional model filter

        Returns:
            Dictionary with summary statistics
        """
        if model:
            data_file = self._get_model_data_file(model)
            if not data_file.exists():
                return {"error": f"No data found for model: {model}"}

            try:
                with open(data_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                total_listings = len(data)
                price_changes = len(
                    [
                        listing
                        for listing in data
                        if len(listing.get("price_readings", [])) > 1
                    ]
                )
                avg_price = (
                    sum(listing["current_price"] for listing in data) / total_listings
                    if total_listings > 0
                    else 0
                )

                return {
                    "model": model,
                    "total_listings": total_listings,
                    "listings_with_price_changes": price_changes,
                    "average_current_price": avg_price,
                    "data_file": str(data_file),
                }

            except Exception as e:
                return {"error": f"Error loading data for model {model}: {e}"}
        else:
            # Get stats for all models
            stats = {}
            model_dirs = [
                d
                for d in self.data_dir.iterdir()
                if d.is_dir() and not d.name.startswith(".") and d.name not in ["plots"]
            ]

            for model_dir in model_dirs:
                model_name = model_dir.name
                model_stats = self.get_summary_stats(model_name)
                stats[model_name] = model_stats

            return stats

    def simulate_price_changes(self, model: str, change_count: int = 5) -> None:
        """
        Simulate price changes for testing

        Args:
            model: Model name
            change_count: Number of listings to modify
        """
        logger.info(f"Simulating {change_count} price changes for model: {model}")

        data_file = self._get_model_data_file(model)

        if not data_file.exists():
            logger.warning(f"No data found for model: {model}")
            return

        try:
            with open(data_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            if len(data) < change_count:
                change_count = len(data)

            # Simulate price changes for random listings
            import random

            selected_listings = random.sample(data, change_count)
            current_timestamp = int(time.time())
            current_date = datetime.now().strftime("%Y-%m-%d")

            for listing in selected_listings:
                current_price = listing.get("current_price", 0)
                if current_price > 0:
                    # Random price change between -20% and +15%
                    change_percent = random.uniform(-0.20, 0.15)
                    new_price = int(current_price * (1 + change_percent))
                    price_change = new_price - current_price

                    # Update listing
                    if "price_readings" not in listing:
                        listing["price_readings"] = [
                            [
                                listing.get(
                                    "first_scrape_timestamp", current_timestamp
                                ),
                                listing.get("initial_price", current_price),
                            ]
                        ]

                    listing["price_readings"].append([current_timestamp, new_price])
                    listing["current_price"] = new_price
                    listing["price_change"] = price_change
                    listing["last_seen"] = current_date
                    listing["last_scrape_timestamp"] = current_timestamp

            # Save updated data
            with open(data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)

            logger.info(
                f"Simulated price changes for {change_count} listings in model: {model}"
            )
            click.echo(
                f"Simulated price changes for {change_count} listings in model: {model}"
            )

        except Exception as e:
            logger.error(f"Error simulating price changes for {model}: {e}")
            click.echo(f"Error simulating price changes for {model}: {e}")
