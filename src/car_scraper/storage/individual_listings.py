"""Individual listings storage for tracking price changes over time, organized by model"""

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
    """Handles storage and tracking of individual car listings over time, organized by model"""

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
        model_dir.mkdir(exist_ok=True)
        return model_dir

    def _get_model_id_mapping(self, model: str) -> IdMappingStorage:
        """
        Get the ID mapping storage for a specific model

        Args:
            model: Model name

        Returns:
            IdMappingStorage instance for the model
        """
        model_dir = self._get_model_dir(model)
        return IdMappingStorage(str(model_dir))

    def store_model_listings_data(
        self,
        model: str,
        listings_data: List[Dict],
        date_str: str,
        output_format: str = "json",
    ) -> None:
        """
        Store individual listings data for a specific model with time series tracking

        Args:
            model: Model name (e.g., 'bmw-i8')
            listings_data: List of listing dictionaries
            date_str: Date string in YYYY-MM-DD format
            output_format: 'json' or 'csv'
        """
        logger.info(
            f"Storing individual listings data for model {model} on date: {date_str}"
        )

        if not listings_data:
            logger.warning(f"No listings data provided for model {model}")
            return

        model_dir = self._get_model_dir(model)
        id_mapping = self._get_model_id_mapping(model)

        # Load existing historical data for this model
        historical_file = model_dir / f"listings_history.{output_format}"
        existing_data = self._load_existing_data(historical_file, output_format)

        # Update historical data with new entries
        updated_data = self._update_listings_history(
            existing_data, listings_data, date_str, id_mapping
        )

        # Save updated historical data
        self._save_historical_data(updated_data, historical_file, output_format, model)

    def store_listings_data(self, date_str: str, output_format: str = "json") -> None:
        """
        Store individual listings data with time series tracking (legacy method)
        Now processes data by model and stores in model-specific directories

        Args:
            date_str: Date string in YYYY-MM-DD format
            output_format: 'json' or 'csv'
        """
        logger.info(f"Storing individual listings data for date: {date_str}")

        # Find all model data files in the root data directory
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

        # Process each model file separately
        for file_path in model_files:
            try:
                # Extract model name from filename
                model_name = file_path.stem  # e.g., 'bmw-i8' from 'bmw-i8.csv'

                if file_path.suffix == ".json":
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                else:  # CSV
                    data = pd.read_csv(file_path).to_dict("records")

                if len(data) == 0:
                    continue

                # Store data for this specific model
                self.store_model_listings_data(
                    model_name, data, date_str, output_format
                )

            except Exception as e:
                logger.error(f"Error processing {file_path}: {str(e)}")
                click.echo(f"Error processing {file_path}: {str(e)}")
                continue

    def _load_existing_data(
        self, historical_file: Path, output_format: str
    ) -> List[Dict]:
        """Load existing historical data"""
        if not historical_file.exists():
            return []

        try:
            if output_format == "json":
                with open(historical_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            else:  # CSV
                df = pd.read_csv(historical_file)
                return df.to_dict("records")
        except Exception as e:
            logger.warning(f"Error loading existing data from {historical_file}: {e}")
            return []

    def _save_historical_data(
        self, data: List[Dict], historical_file: Path, output_format: str, model: str
    ) -> None:
        """Save historical data to file"""
        try:
            if output_format == "json":
                with open(historical_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            else:  # CSV
                df = pd.DataFrame(data)
                df.to_csv(historical_file, index=False)

            logger.info(
                f"Updated listings history for {model}: {len(data)} total entries"
            )
            click.echo(
                f"Updated listings history for {model}: {len(data)} total entries"
            )
            click.echo(f"Historical data saved to {historical_file}")

        except Exception as e:
            logger.error(f"Error saving historical data: {e}")
            click.echo(f"Error saving historical data: {e}")

    def _update_listings_history(
        self,
        existing_data: List[Dict],
        new_listings: List[Dict],
        date_str: str,
        id_mapping: IdMappingStorage,
    ) -> List[Dict]:
        """Update historical data with new listings"""
        # Create lookup for existing data
        existing_lookup = {item["id"]: item for item in existing_data}
        updated_data = list(existing_data)  # Copy existing data

        for listing in new_listings:
            listing_id = listing.get("id")
            if not listing_id:
                continue

            # Get or assign internal ID
            internal_id = id_mapping.get_internal_id(listing_id)

            # Prepare the listing entry
            listing_entry = {
                "id": listing_id,
                "internal_id": internal_id,
                "title": listing.get("title", ""),
                "price": listing.get("price", 0),
                "year": listing.get("year"),
                "mileage": listing.get("mileage"),
                "url": listing.get("url", ""),
                "model": listing.get("model", ""),
                "date": date_str,
                "scrape_timestamp": int(time.time()),
            }

            # Check if this listing already exists for this date
            existing_entry = existing_lookup.get(listing_id)

            if existing_entry:
                # Check if we have data for this date already
                existing_dates = [existing_entry.get("date")]
                if isinstance(existing_entry.get("price_history"), list):
                    existing_dates.extend(
                        [h.get("date") for h in existing_entry["price_history"]]
                    )

                if date_str not in existing_dates:
                    # Add price history tracking
                    if "price_history" not in existing_entry:
                        existing_entry["price_history"] = []

                    # Calculate price change
                    old_price = existing_entry.get("price", 0)
                    new_price = listing_entry["price"]
                    price_change = (
                        new_price - old_price if old_price and new_price else 0
                    )

                    # Add to price history
                    existing_entry["price_history"].append(
                        {
                            "date": date_str,
                            "price": new_price,
                            "price_change": price_change,
                            "scrape_timestamp": listing_entry["scrape_timestamp"],
                        }
                    )

                    # Update current price and price change
                    existing_entry["price"] = new_price
                    existing_entry["price_change"] = price_change
                    existing_entry["date"] = date_str
                    existing_entry["scrape_timestamp"] = listing_entry[
                        "scrape_timestamp"
                    ]
            else:
                # New listing
                listing_entry["price_change"] = 0
                listing_entry["price_history"] = []
                updated_data.append(listing_entry)
                existing_lookup[listing_id] = listing_entry

        return updated_data

    def get_historical_data(self, model: Optional[str] = None) -> pd.DataFrame:
        """
        Get historical data for plotting and analysis

        Args:
            model: Optional model filter

        Returns:
            DataFrame with historical listings data
        """
        if model:
            # Get data for specific model
            model_dir = self._get_model_dir(model)
            historical_file = model_dir / "listings_history.json"

            if not historical_file.exists():
                raise FileNotFoundError(f"No historical data found for model: {model}")

            try:
                with open(historical_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if not data:
                    raise ValueError(f"No data found for model: {model}")

                # Flatten the data to include price history
                flattened_data = []
                for listing in data:
                    # Add the main entry
                    main_entry = listing.copy()
                    flattened_data.append(main_entry)

                    # Add price history entries
                    if "price_history" in listing and listing["price_history"]:
                        for history_entry in listing["price_history"]:
                            history_row = listing.copy()
                            history_row.update(history_entry)
                            flattened_data.append(history_row)

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
                if d.is_dir()
                and not d.name.startswith(".")
                and d.name not in ["plots", "individual_listings"]
            ]

            for model_dir in model_dirs:
                historical_file = model_dir / "listings_history.json"
                if historical_file.exists():
                    try:
                        with open(historical_file, "r", encoding="utf-8") as f:
                            model_data = json.load(f)
                            all_data.extend(model_data)
                    except Exception as e:
                        logger.warning(
                            f"Error loading data from {historical_file}: {e}"
                        )
                        continue

            if not all_data:
                raise FileNotFoundError("No historical data found")

            return pd.DataFrame(all_data)

    def assign_internal_ids_to_existing_data(self) -> None:
        """Assign internal IDs to existing data across all models"""
        logger.info("Assigning internal IDs to existing data across all models")

        model_dirs = [
            d
            for d in self.data_dir.iterdir()
            if d.is_dir()
            and not d.name.startswith(".")
            and d.name not in ["plots", "individual_listings"]
        ]

        for model_dir in model_dirs:
            model_name = model_dir.name
            historical_file = model_dir / "listings_history.json"

            if not historical_file.exists():
                continue

            try:
                id_mapping = self._get_model_id_mapping(model_name)

                with open(historical_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Assign internal IDs
                for listing in data:
                    listing_id = listing.get("id")
                    if listing_id and "internal_id" not in listing:
                        listing["internal_id"] = id_mapping.get_internal_id(listing_id)

                # Save updated data
                with open(historical_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False, default=str)

                logger.info(f"Updated internal IDs for model: {model_name}")

            except Exception as e:
                logger.error(f"Error updating internal IDs for {model_name}: {e}")

    def simulate_price_changes(self, model: str, change_count: int = 5) -> None:
        """
        Simulate price changes for testing (model-specific)

        Args:
            model: Model name
            change_count: Number of listings to modify
        """
        logger.info(f"Simulating {change_count} price changes for model: {model}")

        model_dir = self._get_model_dir(model)
        historical_file = model_dir / "listings_history.json"

        if not historical_file.exists():
            logger.warning(f"No historical data found for model: {model}")
            return

        try:
            with open(historical_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            if len(data) < change_count:
                change_count = len(data)

            # Simulate price changes for random listings
            import random

            selected_listings = random.sample(data, change_count)

            for listing in selected_listings:
                current_price = listing.get("price", 0)
                if current_price > 0:
                    # Random price change between -20% and +15%
                    change_percent = random.uniform(-0.20, 0.15)
                    new_price = int(current_price * (1 + change_percent))
                    price_change = new_price - current_price

                    # Update price history
                    if "price_history" not in listing:
                        listing["price_history"] = []

                    listing["price_history"].append(
                        {
                            "date": datetime.now().strftime("%Y-%m-%d"),
                            "price": new_price,
                            "price_change": price_change,
                            "scrape_timestamp": int(time.time()),
                        }
                    )

                    # Update current values
                    listing["price"] = new_price
                    listing["price_change"] = price_change
                    listing["date"] = datetime.now().strftime("%Y-%m-%d")

            # Save updated data
            with open(historical_file, "w", encoding="utf-8") as f:
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
