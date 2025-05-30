"""Data processing utilities"""

import json
from pathlib import Path
from typing import Dict, List, Optional

import click
import pandas as pd

from src.car_scraper.utils.logger import logger


class DataProcessor:
    """Utility class for data processing operations"""

    def __init__(self, data_dir: str) -> None:
        """
        Initialize data processor

        Args:
            data_dir: Base data directory
        """
        self.data_dir = Path(data_dir)

    def get_data_status(self) -> Dict:
        """
        Get comprehensive status of scraped data

        Returns:
            Dictionary with data status information
        """
        status = {
            "model_files": [],
            "time_series_files": [],
            "simplified_listings": {},
            "plots": [],
        }

        if not self.data_dir.exists():
            return status

        # Model files
        model_files = list(self.data_dir.glob("*.json")) + list(
            self.data_dir.glob("*.csv")
        )
        for file_path in model_files:
            try:
                if file_path.suffix == ".json":
                    with open(file_path, "r") as f:
                        data = json.load(f)
                    count = len(data)
                else:
                    df = pd.read_csv(file_path)
                    count = len(df)

                status["model_files"].append(
                    {
                        "name": file_path.name,
                        "count": count,
                        "size": file_path.stat().st_size,
                    }
                )
            except Exception as e:
                status["model_files"].append(
                    {"name": file_path.name, "count": 0, "error": str(e)}
                )

        # Time series data
        time_series_dir = self.data_dir / "time_series"
        if time_series_dir.exists():
            time_series_files = list(time_series_dir.glob("*.json")) + list(
                time_series_dir.glob("*.csv")
            )
            for file_path in time_series_files:
                status["time_series_files"].append(
                    {"name": file_path.name, "size": file_path.stat().st_size}
                )

        # Simplified listings data (new format)
        for model_dir in self.data_dir.iterdir():
            if model_dir.is_dir() and not model_dir.name.startswith("."):
                model_file = model_dir / f"{model_dir.name}.json"
                if model_file.exists():
                    try:
                        with open(model_file, "r") as f:
                            data = json.load(f)

                        # Handle both old format (list) and new format (dict with 'listings' key)
                        if isinstance(data, list):
                            # Old format - just count the listings
                            total_listings = len(data)
                            price_readings = 0  # Old format doesn't have price readings
                            last_updated = "unknown (old format)"
                        else:
                            # New format
                            total_listings = len(data.get("listings", {}))
                            price_readings = sum(
                                len(listing.get("price_readings", []))
                                for listing in data.get("listings", {}).values()
                            )
                            last_updated = data.get("metadata", {}).get(
                                "last_updated", "unknown"
                            )

                        status["simplified_listings"][model_dir.name] = {
                            "total_listings": total_listings,
                            "total_price_readings": price_readings,
                            "file_size": model_file.stat().st_size,
                            "last_updated": last_updated,
                        }
                    except Exception as e:
                        status["simplified_listings"][model_dir.name] = {
                            "error": str(e)
                        }

        # Plots
        plots_dir = self.data_dir / "plots"
        if plots_dir.exists():
            plot_files = list(plots_dir.glob("*.png"))
            status["plots"] = [
                {"name": f.name, "size": f.stat().st_size} for f in plot_files
            ]

        return status

    def print_status(self) -> None:
        """Print formatted data status"""
        status = self.get_data_status()

        if not self.data_dir.exists():
            click.echo(f"Data directory {self.data_dir} does not exist.")
            return

        # Model files
        click.echo(f"Found {len(status['model_files'])} model data files:")
        for file_info in status["model_files"]:
            if "error" in file_info:
                click.echo(
                    f"  {file_info['name']}: Error reading file ({file_info['error']})"
                )
            else:
                click.echo(f"  {file_info['name']}: {file_info['count']} records")

        # Time series data
        if status["time_series_files"]:
            click.echo(f"\nFound {len(status['time_series_files'])} time series files:")
            for file_info in status["time_series_files"]:
                click.echo(f"  {file_info['name']}")

        # Simplified listings data
        if status["simplified_listings"]:
            click.echo(f"\nSimplified listings data:")
            for model, model_info in status["simplified_listings"].items():
                if "error" not in model_info:
                    click.echo(
                        f"  {model}: {model_info['total_listings']} listings, "
                        f"{model_info['total_price_readings']} price readings, "
                        f"last updated: {model_info['last_updated']}"
                    )
                else:
                    click.echo(f"  {model}: Error - {model_info['error']}")

        # Plots
        if status["plots"]:
            click.echo(f"\nFound {len(status['plots'])} generated plots:")
            for plot_info in status["plots"]:
                size_kb = plot_info["size"] / 1024
                click.echo(f"  {plot_info['name']} ({size_kb:.1f} KB)")

    def clean_data(self, dry_run: bool = True) -> None:
        """
        Clean and validate data files

        Args:
            dry_run: If True, show what would be cleaned without actually doing it
        """
        logger.info(f"Cleaning data (dry_run={dry_run})")

        # Clean simplified listings duplicates
        self._clean_simplified_listings(dry_run)

        # Clean time series duplicates
        self._clean_time_series(dry_run)

        if dry_run:
            click.echo(
                "\nDry run completed. Use --dry-run=false to actually clean data."
            )

    def _clean_simplified_listings(self, dry_run: bool) -> None:
        """Clean simplified listings data"""
        for model_dir in self.data_dir.iterdir():
            if not model_dir.is_dir() or model_dir.name.startswith("."):
                continue

            model_file = model_dir / f"{model_dir.name}.json"
            if not model_file.exists():
                continue

            try:
                with open(model_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                listings = data.get("listings", {})
                total_before = sum(
                    len(listing.get("price_readings", []))
                    for listing in listings.values()
                )

                # Clean duplicate price readings for each listing
                cleaned_count = 0
                for listing_id, listing in listings.items():
                    price_readings = listing.get("price_readings", [])
                    if not price_readings:
                        continue

                    # Remove duplicate readings based on date
                    seen_dates = set()
                    clean_readings = []
                    for reading in price_readings:
                        date = reading.get("date")
                        if date not in seen_dates:
                            clean_readings.append(reading)
                            seen_dates.add(date)
                        else:
                            cleaned_count += 1

                    listings[listing_id]["price_readings"] = clean_readings

                if cleaned_count > 0:
                    if dry_run:
                        click.echo(
                            f"Would remove {cleaned_count} duplicate price readings from {model_file.name}"
                        )
                    else:
                        with open(model_file, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2, ensure_ascii=False)
                        click.echo(
                            f"Removed {cleaned_count} duplicate price readings from {model_file.name}"
                        )
                else:
                    click.echo(f"No duplicates found in {model_file.name}")

            except Exception as e:
                logger.error(f"Error cleaning {model_file}: {str(e)}")
                click.echo(f"Error cleaning {model_file}: {str(e)}")

    def _clean_time_series(self, dry_run: bool) -> None:
        """Clean time series data"""
        time_series_dir = self.data_dir / "time_series"
        if not time_series_dir.exists():
            return

        # Clean historical files
        for ext in ["csv", "json"]:
            historical_file = time_series_dir / f"historical.{ext}"
            if not historical_file.exists():
                continue

            try:
                if ext == "json":
                    with open(historical_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    df = pd.DataFrame(data)
                else:
                    df = pd.read_csv(historical_file)

                original_count = len(df)

                # Remove duplicates based on model and date
                df_clean = df.drop_duplicates(subset=["model", "date"], keep="last")
                removed_count = original_count - len(df_clean)

                if removed_count > 0:
                    if dry_run:
                        click.echo(
                            f"Would remove {removed_count} duplicate entries from {historical_file.name}"
                        )
                    else:
                        if ext == "json":
                            with open(historical_file, "w", encoding="utf-8") as f:
                                json.dump(
                                    df_clean.to_dict("records"),
                                    f,
                                    indent=2,
                                    ensure_ascii=False,
                                )
                        else:
                            df_clean.to_csv(historical_file, index=False)
                        click.echo(
                            f"Removed {removed_count} duplicate entries from {historical_file.name}"
                        )
                else:
                    click.echo(f"No duplicates found in {historical_file.name}")

            except Exception as e:
                logger.error(f"Error cleaning {historical_file.name}: {str(e)}")
                click.echo(f"Error cleaning {historical_file.name}: {str(e)}")

    def export_data(self, format: str = "csv", model: Optional[str] = None) -> None:
        """
        Export data in specified format

        Args:
            format: Export format ('csv', 'json', 'excel')
            model: Optional model filter
        """
        logger.info(f"Exporting data in {format} format for model: {model}")

        # Create exports directory
        exports_dir = self.data_dir / "exports"
        exports_dir.mkdir(exist_ok=True)

        # Export individual listings data
        self._export_individual_listings(exports_dir, format, model)

        # Export aggregated data
        self._export_aggregated_data(exports_dir, format, model)

        click.echo(f"Data exported to {exports_dir}")

    def _export_individual_listings(
        self, exports_dir: Path, format: str, model: Optional[str]
    ) -> None:
        """Export individual listings data from simplified storage"""
        try:
            from ..storage.simplified_listings import SimplifiedListingsStorage

            storage = SimplifiedListingsStorage(str(self.data_dir))
            df = storage.get_historical_data(model)

            if len(df) == 0:
                click.echo("No data found to export")
                return

            filename = f"individual_listings{'_' + model.replace('/', '_') if model else ''}.{format}"
            output_file = exports_dir / filename

            if format == "csv":
                df.to_csv(output_file, index=False)
            elif format == "json":
                df.to_json(output_file, orient="records", indent=2)
            elif format == "excel":
                df.to_excel(output_file, index=False)

            click.echo(f"Exported individual listings to {filename}")

        except Exception as e:
            logger.error(f"Error exporting individual listings: {str(e)}")

    def _export_aggregated_data(
        self, exports_dir: Path, format: str, model: Optional[str]
    ) -> None:
        """Export aggregated statistical data"""
        try:
            from ..storage.simplified_listings import SimplifiedListingsStorage

            storage = SimplifiedListingsStorage(str(self.data_dir))
            df = storage.get_historical_data(model)

            # Create aggregated statistics
            stats = (
                df.groupby(["model", "year"])
                .agg(
                    {
                        "price": ["count", "mean", "median", "min", "max", "std"],
                        "mileage": ["mean", "median"],
                    }
                )
                .round(2)
            )

            # Flatten column names
            stats.columns = ["_".join(col).strip() for col in stats.columns.values]
            stats = stats.reset_index()

            filename = f"aggregated_stats{'_' + model.replace('/', '_') if model else ''}.{format}"
            output_file = exports_dir / filename

            if format == "csv":
                stats.to_csv(output_file, index=False)
            elif format == "json":
                stats.to_json(output_file, orient="records", indent=2)
            elif format == "excel":
                stats.to_excel(output_file, index=False)

            click.echo(f"Exported aggregated statistics to {filename}")

        except Exception as e:
            logger.error(f"Error exporting aggregated data: {str(e)}")

    def export_to_csv(self, model: str, output_file: str) -> pd.DataFrame:
        """
        Export data for a specific model to CSV format

        Args:
            model: Model name to export
            output_file: Output file path

        Returns:
            DataFrame with the exported data
        """
        try:
            from ..storage.simplified_listings import SimplifiedListingsStorage

            storage = SimplifiedListingsStorage(str(self.data_dir))
            df = storage.get_historical_data(model)

            if len(df) == 0:
                logger.warning(f"No data found for model: {model}")
                return pd.DataFrame()

            # Export to CSV
            df.to_csv(output_file, index=False)
            logger.info(f"Exported {len(df)} records to {output_file}")

            return df

        except Exception as e:
            logger.error(f"Error exporting to CSV: {str(e)}")
            raise

    def export_to_json(self, model: str, output_file: str) -> pd.DataFrame:
        """
        Export data for a specific model to JSON format

        Args:
            model: Model name to export
            output_file: Output file path

        Returns:
            DataFrame with the exported data
        """
        try:
            from ..storage.simplified_listings import SimplifiedListingsStorage

            storage = SimplifiedListingsStorage(str(self.data_dir))
            df = storage.get_historical_data(model)

            if len(df) == 0:
                logger.warning(f"No data found for model: {model}")
                return pd.DataFrame()

            # Export to JSON
            df.to_json(output_file, orient="records", indent=2)
            logger.info(f"Exported {len(df)} records to {output_file}")

            return df

        except Exception as e:
            logger.error(f"Error exporting to JSON: {str(e)}")
            raise
