"""Individual listings storage for tracking price changes over time"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import click
import pandas as pd

from src.car_scraper.models import CarListing, CarListingHistory
from src.car_scraper.storage.id_mapping import IdMappingStorage
from src.car_scraper.utils.logger import logger


class IndividualListingsStorage:
    """Handles storage and tracking of individual car listings over time"""

    def __init__(self, data_dir: str) -> None:
        """
        Initialize storage handler

        Args:
            data_dir: Base data directory
        """
        self.data_dir = Path(data_dir)
        self.listings_dir = self.data_dir / "individual_listings"
        self.listings_dir.mkdir(exist_ok=True)
        self.id_mapping = IdMappingStorage(str(self.data_dir))

    def store_listings_data(self, date_str: str, output_format: str = "json") -> None:
        """
        Store individual listings data with time series tracking

        Args:
            date_str: Date string in YYYY-MM-DD format
            output_format: 'json' or 'csv'
        """
        logger.info(f"Storing individual listings data for date: {date_str}")

        # Find all model data files
        model_files = list(self.data_dir.glob("*.json")) + list(
            self.data_dir.glob("*.csv")
        )

        if not model_files:
            logger.warning(
                "No model data files found. Skipping individual listings storage."
            )
            click.echo(
                "No model data files found. Skipping individual listings storage."
            )
            return

        all_listings = []

        for file_path in model_files:
            try:
                if file_path.suffix == ".json":
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                else:  # CSV
                    data = pd.read_csv(file_path).to_dict("records")

                if len(data) == 0:
                    continue

                # Add current data to listings
                all_listings.extend(data)

            except Exception as e:
                logger.error(f"Error processing {file_path}: {str(e)}")
                click.echo(f"Error processing {file_path}: {str(e)}")
                continue

        if not all_listings:
            logger.warning("No valid listings found.")
            click.echo("No valid listings found.")
            return

        # Load existing historical data
        historical_file = self.listings_dir / f"listings_history.{output_format}"
        existing_data = self._load_existing_data(historical_file, output_format)

        # Update historical data with new entries
        updated_data = self._update_listings_history(
            existing_data, all_listings, date_str
        )

        # Save updated historical data
        self._save_historical_data(updated_data, historical_file, output_format)

    def _load_existing_data(
        self, historical_file: Path, output_format: str
    ) -> List[Dict]:
        """Load existing historical data"""
        existing_data = []

        try:
            if historical_file.exists():
                if output_format == "json":
                    with open(historical_file, "r", encoding="utf-8") as f:
                        existing_data = json.load(f)
                else:
                    existing_df = pd.read_csv(historical_file)
                    existing_data = existing_df.to_dict("records")
        except Exception as e:
            logger.error(f"Error loading existing data: {str(e)}")
            click.echo(f"Error loading existing data: {str(e)}")

        return existing_data

    def _save_historical_data(
        self, updated_data: List[Dict], historical_file: Path, output_format: str
    ) -> None:
        """Save updated historical data"""
        try:
            if output_format == "json":
                with open(historical_file, "w", encoding="utf-8") as f:
                    json.dump(updated_data, f, indent=2, ensure_ascii=False)
            else:
                pd.DataFrame(updated_data).to_csv(historical_file, index=False)

            logger.info(f"Updated listings history: {len(updated_data)} total entries")
            click.echo(f"Updated listings history: {len(updated_data)} total entries")
            click.echo(f"Historical data saved to {historical_file}")

        except Exception as e:
            logger.error(f"Error saving historical data: {str(e)}")
            click.echo(f"Error saving historical data: {str(e)}")

    def _update_listings_history(
        self, existing_data: List[Dict], new_listings: List[Dict], date_str: str
    ) -> List[Dict]:
        """
        Update listings history with new data, tracking price changes for individual listings
        and automatically assigning internal IDs
        """
        # Load or create ID mapping for automatic internal ID assignment
        id_mapping, next_id = self.id_mapping.load_or_create_mapping()

        # First, ensure all existing data has internal IDs
        for entry in existing_data:
            listing_id = entry.get("id")
            if listing_id:
                # Assign internal ID if this listing doesn't have one yet
                if listing_id not in id_mapping:
                    id_mapping[listing_id] = next_id
                    next_id += 1
                # Add internal_id to existing entry if it doesn't have one
                if "internal_id" not in entry:
                    entry["internal_id"] = id_mapping[listing_id]

        # Create a lookup for existing listings by ID
        existing_by_id = {}
        for entry in existing_data:
            listing_id = entry.get("id")
            if listing_id:
                if listing_id not in existing_by_id:
                    existing_by_id[listing_id] = []
                existing_by_id[listing_id].append(entry)

        updated_data = list(existing_data)  # Keep all existing data

        # Process new listings
        for listing in new_listings:
            listing_id = listing.get("id")
            if not listing_id:
                continue

            # Assign internal ID if this listing doesn't have one yet
            if listing_id not in id_mapping:
                id_mapping[listing_id] = next_id
                next_id += 1

            # Check if this is a new price entry for an existing listing
            existing_entries = existing_by_id.get(listing_id, [])

            # Check if we already have an entry for this exact date
            date_exists = any(
                entry.get("date") == date_str for entry in existing_entries
            )

            if not date_exists:
                # Add new entry with date and internal ID
                new_entry = listing.copy()
                new_entry["date"] = date_str
                new_entry["internal_id"] = id_mapping[listing_id]  # Add internal ID
                updated_data.append(new_entry)

                # Calculate price change if we have previous data
                if existing_entries:
                    latest_entry = max(
                        existing_entries, key=lambda x: x.get("date", "")
                    )
                    if latest_entry.get("price") and listing.get("price"):
                        price_change = listing["price"] - latest_entry["price"]
                        new_entry["price_change"] = price_change
                        new_entry["price_change_percent"] = (
                            price_change / latest_entry["price"]
                        ) * 100
                    else:
                        new_entry["price_change"] = 0
                        new_entry["price_change_percent"] = 0
                else:
                    new_entry["price_change"] = 0
                    new_entry["price_change_percent"] = 0

        # Save the updated ID mapping
        self.id_mapping.save_mapping(id_mapping)

        return updated_data

    def get_historical_data(self, model: Optional[str] = None) -> pd.DataFrame:
        """
        Get historical data as DataFrame

        Args:
            model: Optional model filter

        Returns:
            DataFrame with historical data
        """
        historical_file_csv = self.listings_dir / "listings_history.csv"
        historical_file_json = self.listings_dir / "listings_history.json"

        # Try CSV first (new format with internal IDs), then JSON (legacy)
        if historical_file_csv.exists():
            try:
                df = pd.read_csv(historical_file_csv)
            except Exception as e:
                logger.error(f"Error loading CSV data: {str(e)}")
                raise
        elif historical_file_json.exists():
            try:
                with open(historical_file_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
                df = pd.DataFrame(data)
            except Exception as e:
                logger.error(f"Error loading JSON data: {str(e)}")
                raise
        else:
            raise FileNotFoundError(
                "No historical listings data found. Run scraping first."
            )

        if len(df) == 0:
            raise ValueError("No data found in historical file.")

        # Filter by model if specified
        if model:
            df = df[df["model"] == model]
            if len(df) == 0:
                raise ValueError(f"No data found for model: {model}")

        return df

    def assign_internal_ids_to_existing_data(self) -> None:
        """
        Add internal IDs to existing historical data
        """
        historical_json = self.listings_dir / "listings_history.json"
        historical_csv = self.listings_dir / "listings_history.csv"

        if not historical_json.exists():
            logger.warning("No historical data found.")
            click.echo("No historical data found.")
            return

        # Load existing data
        try:
            with open(historical_json, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Error loading historical data: {str(e)}")
            click.echo(f"Error loading historical data: {str(e)}")
            return

        if not data:
            logger.warning("No data found.")
            click.echo("No data found.")
            return

        # Load or create ID mapping
        id_mapping, next_id = self.id_mapping.load_or_create_mapping()

        # Assign internal IDs to all entries
        for entry in data:
            listing_id = entry.get("id")
            if not listing_id:
                continue

            # Assign internal ID if not exists
            if listing_id not in id_mapping:
                id_mapping[listing_id] = next_id
                next_id += 1

            # Add internal_id to entry
            entry["internal_id"] = id_mapping[listing_id]

        # Save updated data
        try:
            with open(historical_json, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Also update CSV
            if historical_csv.exists():
                pd.DataFrame(data).to_csv(historical_csv, index=False)

            # Save ID mapping
            self.id_mapping.save_mapping(id_mapping)

            logger.info(f"Assigned internal IDs to {len(data)} entries")
            click.echo(f"Assigned internal IDs to {len(data)} entries")
            click.echo(f"Total unique listings: {len(id_mapping)}")

        except Exception as e:
            logger.error(f"Error saving updated data: {str(e)}")
            click.echo(f"Error saving updated data: {str(e)}")

    def simulate_price_changes(self, change_count: int = 5) -> None:
        """
        Simulate price changes for demonstration purposes

        Args:
            change_count: Number of listings to modify
        """
        logger.info(f"Simulating price changes for {change_count} listings...")
        click.echo(f"Simulating price changes for {change_count} listings...")

        historical_file = self.listings_dir / "listings_history.json"

        if not historical_file.exists():
            logger.error("No historical data found. Run scraping first.")
            click.echo("No historical data found. Run scraping first.")
            return

        try:
            with open(historical_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Error loading historical data: {str(e)}")
            click.echo(f"Error loading historical data: {str(e)}")
            return

        if not data:
            logger.warning("No data found.")
            click.echo("No data found.")
            return

        import random
        from datetime import datetime, timedelta

        # Get unique listing IDs with valid prices
        valid_listings = {}
        for entry in data:
            if entry.get("price") and entry.get("price") > 0 and entry.get("id"):
                if entry["id"] not in valid_listings:
                    valid_listings[entry["id"]] = entry

        if len(valid_listings) < change_count:
            change_count = len(valid_listings)
            click.echo(f"Reducing change count to {change_count} (available listings)")

        # Select random listings to modify
        selected_ids = random.sample(list(valid_listings.keys()), change_count)

        # Create new date (tomorrow)
        new_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        # Simulate price changes
        for listing_id in selected_ids:
            original_listing = valid_listings[listing_id]
            original_price = original_listing["price"]

            # Generate realistic price change (-20% to +10%)
            change_percent = random.uniform(-0.20, 0.10)
            new_price = int(original_price * (1 + change_percent))
            price_change = new_price - original_price

            # Create new entry with changed price
            new_entry = original_listing.copy()
            new_entry["price"] = new_price
            new_entry["date"] = new_date
            new_entry["scrape_date"] = datetime.now().isoformat()
            new_entry["scrape_timestamp"] = int(time.time())
            new_entry["price_change"] = price_change
            new_entry["price_change_percent"] = change_percent * 100

            data.append(new_entry)

            change_str = f"{price_change:+,} PLN ({change_percent*100:+.1f}%)"
            click.echo(
                f"  {listing_id[:20]}... {original_price:,} → {new_price:,} ({change_str})"
            )

        # Save updated data
        try:
            with open(historical_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Also update CSV
            csv_file = self.listings_dir / "listings_history.csv"
            pd.DataFrame(data).to_csv(csv_file, index=False)

            logger.info(f"Simulated {change_count} price changes for date {new_date}")
            click.echo(f"Simulated {change_count} price changes for date {new_date}")
            click.echo("Now run 'plot' command to see the changes!")

        except Exception as e:
            logger.error(f"Error saving simulated data: {str(e)}")
            click.echo(f"Error saving simulated data: {str(e)}")
