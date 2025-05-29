"""Demo runner utility for car scraper demonstrations"""

import json
import random
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
from loguru import logger

from src.car_scraper.models import CarListing
from src.car_scraper.utils.data_processor import DataProcessor


class DemoRunner:
    """
    Handles demonstration scenarios for the car scraper system.

    This class provides methods to simulate price changes, generate sample data,
    and run complete demonstration workflows to showcase the system's capabilities.
    """

    def __init__(self, data_dir: str = "./data"):
        """
        Initialize demo runner.

        Args:
            data_dir: Directory where data is stored
        """
        self.data_dir = Path(data_dir)
        self.listings_dir = self.data_dir / "individual_listings"
        self.listings_dir.mkdir(parents=True, exist_ok=True)
        self.data_processor = DataProcessor(str(self.data_dir))

        logger.info(f"Demo runner initialized for data directory: {self.data_dir}")

    def simulate_price_changes(self, change_count: int = 5) -> bool:
        """
        Simulate price changes for demonstration purposes.

        Args:
            change_count: Number of listings to modify

        Returns:
            True if simulation was successful, False otherwise
        """
        logger.info(f"Simulating price changes for {change_count} listings")

        historical_file = self.listings_dir / "listings_history.json"

        if not historical_file.exists():
            logger.error("No historical data found. Run scraping first.")
            return False

        try:
            with open(historical_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Error loading historical data: {str(e)}")
            return False

        if not data:
            logger.warning("No data found in historical file")
            return False

        # Get unique listing IDs with valid prices
        valid_listings = {}
        for entry in data:
            if (
                entry.get("price")
                and entry.get("price") > 0
                and entry.get("id")
                and entry["id"] not in valid_listings
            ):
                valid_listings[entry["id"]] = entry

        if len(valid_listings) < change_count:
            change_count = len(valid_listings)
            logger.warning(
                f"Reducing change count to {change_count} (available listings)"
            )

        if change_count == 0:
            logger.error("No valid listings found for simulation")
            return False

        # Select random listings to modify
        selected_ids = random.sample(list(valid_listings.keys()), change_count)

        # Create new date (tomorrow)
        new_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        changes_made = []

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

            change_info = {
                "id": listing_id,
                "original_price": original_price,
                "new_price": new_price,
                "change": price_change,
                "change_percent": change_percent * 100,
            }
            changes_made.append(change_info)

            logger.info(
                f"Simulated change for {listing_id[:20]}...: "
                f"{original_price:,} → {new_price:,} "
                f"({price_change:+,} PLN, {change_percent*100:+.1f}%)"
            )

        # Save updated data
        try:
            with open(historical_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Also update CSV if it exists
            csv_file = self.listings_dir / "listings_history.csv"
            pd.DataFrame(data).to_csv(csv_file, index=False)

            logger.success(
                f"Simulated {change_count} price changes for date {new_date}"
            )
            return True

        except Exception as e:
            logger.error(f"Error saving simulated data: {str(e)}")
            return False

    def create_sample_data(self, model: str = "lexus-lc", count: int = 10) -> bool:
        """
        Create sample data for demonstration purposes.

        Args:
            model: Model name to create sample data for
            count: Number of sample listings to create

        Returns:
            True if sample data was created successfully, False otherwise
        """
        logger.info(f"Creating {count} sample listings for model: {model}")

        sample_listings = []
        base_date = datetime.now() - timedelta(days=30)

        for i in range(count):
            # Generate realistic sample data
            listing_id = f"sample_{model}_{i+1:03d}"
            year = random.randint(2015, 2023)
            base_price = random.randint(200000, 800000)
            mileage = random.randint(10000, 150000)

            listing_data = {
                "id": listing_id,
                "title": f"Lexus LC {year} Sample Listing {i+1}",
                "price": base_price,
                "year": year,
                "mileage": mileage,
                "url": f"https://www.otomoto.pl/oferta/{listing_id}",
                "model": model,
                "scrape_date": base_date.isoformat(),
                "scrape_timestamp": int(base_date.timestamp()),
                "date": base_date.strftime("%Y-%m-%d"),
            }

            sample_listings.append(listing_data)

            # Create some historical entries with price variations
            for days_ahead in range(7, 30, 7):  # Weekly entries
                variation_date = base_date + timedelta(days=days_ahead)
                price_variation = random.uniform(-0.05, 0.05)  # ±5% variation
                new_price = int(base_price * (1 + price_variation))

                historical_entry = listing_data.copy()
                historical_entry["price"] = new_price
                historical_entry["date"] = variation_date.strftime("%Y-%m-%d")
                historical_entry["scrape_date"] = variation_date.isoformat()
                historical_entry["scrape_timestamp"] = int(variation_date.timestamp())
                historical_entry["price_change"] = new_price - base_price
                historical_entry["price_change_percent"] = (
                    (new_price - base_price) / base_price * 100
                )

                sample_listings.append(historical_entry)

        # Save sample data using the existing storage system
        try:
            # Use the data processor's update method
            date_str = datetime.now().strftime("%Y-%m-%d")
            updated_data = self.data_processor.update_listings_history(
                [], sample_listings, date_str
            )

            # Save to files
            historical_file = self.listings_dir / "listings_history.json"
            with open(historical_file, "w", encoding="utf-8") as f:
                json.dump(updated_data, f, indent=2, ensure_ascii=False)

            csv_file = self.listings_dir / "listings_history.csv"
            pd.DataFrame(updated_data).to_csv(csv_file, index=False)

            logger.success(f"Created {len(sample_listings)} sample data entries")
            return True

        except Exception as e:
            logger.error(f"Error creating sample data: {str(e)}")
            return False

    def run_complete_demo(self, model: Optional[str] = None) -> bool:
        """
        Run a complete demonstration of the price tracking system.

        Args:
            model: Specific model to demonstrate (optional)

        Returns:
            True if demo completed successfully, False otherwise
        """
        logger.info("🚗 Starting Car Price Tracking Demonstration")

        try:
            # Step 1: Check current data status
            logger.info("📊 Step 1: Checking current data status")
            status_info = self.data_processor.get_data_status()
            logger.info(
                f"Found {len(status_info.get('model_files', []))} model data files"
            )

            # Step 2: Create sample data if needed
            if not status_info.get("model_files"):
                logger.info("💾 Step 2: Creating sample data for demonstration")
                self.create_sample_data("lexus-lc", 10)

            # Step 3: Simulate price changes
            logger.info("💰 Step 3: Simulating price changes")
            self.simulate_price_changes(8)

            # Step 4: Generate plots (would call plotting modules)
            logger.info("📈 Step 4: Plot generation would be triggered here")
            logger.info("(In CLI mode, this would generate actual plots)")

            # Step 5: Show final summary
            logger.info("📋 Step 5: Final status summary")
            final_status = self.data_processor.get_data_status()
            logger.info(
                f"Demo completed with {len(final_status.get('model_files', []))} data files"
            )

            logger.success("✅ Demonstration completed successfully!")
            logger.info(
                "🔍 Check the plots in 'data/plots/' to see individual listing price trends"
            )
            logger.info("🎯 Run regular scraping to track real price changes over time")

            return True

        except Exception as e:
            logger.error(f"Demo failed: {str(e)}")
            return False

    def assign_internal_ids_to_existing_data(self) -> bool:
        """
        Add internal IDs to existing historical data that doesn't have them.

        Returns:
            True if assignment was successful, False otherwise
        """
        logger.info("Assigning internal IDs to existing data")

        historical_json = self.listings_dir / "listings_history.json"
        historical_csv = self.listings_dir / "listings_history.csv"

        if not historical_json.exists():
            logger.warning("No historical data found")
            return False

        try:
            # Load existing data
            with open(historical_json, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not data:
                logger.warning("No data found in historical file")
                return False

            # Load or create ID mapping using data processor
            updated_data = self.data_processor.update_listings_history(
                data, [], datetime.now().strftime("%Y-%m-%d")
            )

            # Save updated data
            with open(historical_json, "w", encoding="utf-8") as f:
                json.dump(updated_data, f, indent=2, ensure_ascii=False)

            # Also update CSV
            if historical_csv.exists():
                pd.DataFrame(updated_data).to_csv(historical_csv, index=False)

            unique_ids = len(
                set(
                    entry.get("internal_id")
                    for entry in updated_data
                    if entry.get("internal_id")
                )
            )

            logger.success(f"Assigned internal IDs to {len(updated_data)} entries")
            logger.info(f"Total unique listings: {unique_ids}")

            return True

        except Exception as e:
            logger.error(f"Error assigning internal IDs: {str(e)}")
            return False
