"""Legacy time series plotting functionality"""

from pathlib import Path
from typing import Optional

import click
import matplotlib.pyplot as plt
import pandas as pd

from src.car_scraper.storage.time_series import TimeSeriesStorage
from src.car_scraper.utils.logger import logger


class LegacyPlotter:
    """Generates legacy aggregated plots from historical time series data"""

    def __init__(self, data_dir: str) -> None:
        """
        Initialize legacy plotter

        Args:
            data_dir: Base data directory
        """
        self.data_dir = Path(data_dir)
        self.plots_dir = self.data_dir / "plots"
        self.plots_dir.mkdir(exist_ok=True)
        self.storage = TimeSeriesStorage(str(self.data_dir))

    def generate_legacy_plots(
        self, model: Optional[str] = None, plot_type: str = "both"
    ) -> None:
        """
        Generate legacy aggregated plots from historical data

        Args:
            model: Optional model filter
            plot_type: 'price', 'count', or 'both'
        """
        logger.info(f"Generating legacy plots for model: {model}, type: {plot_type}")

        try:
            data = self.storage.get_historical_data(model)
        except (FileNotFoundError, ValueError) as e:
            logger.warning(f"No legacy historical data found: {str(e)}")
            click.echo("No legacy historical data found. Skipping legacy plots.")
            return

        # Convert date to datetime
        data["date"] = pd.to_datetime(data["date"])
        data = data.sort_values(["model", "date"])

        # Generate price plot
        if plot_type in ["price", "both"]:
            self._generate_price_plot(data)

        # Generate count plot
        if plot_type in ["count", "both"]:
            self._generate_count_plot(data)

    def _generate_price_plot(self, data: pd.DataFrame) -> None:
        """Generate price trend plot"""
        plt.figure(figsize=(12, 8))

        for model_name, group in data.groupby("model"):
            plt.plot(
                group["date"],
                group["avg_price"],
                marker="o",
                label=f"{model_name} - Avg Price",
                linewidth=2,
            )
            plt.fill_between(
                group["date"], group["min_price"], group["max_price"], alpha=0.2
            )

        plt.title("Car Prices Over Time", fontsize=16)
        plt.xlabel("Date", fontsize=12)
        plt.ylabel("Price (PLN)", fontsize=12)
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()

        price_plot_path = self.plots_dir / "price_trends.png"
        plt.savefig(price_plot_path, dpi=300, bbox_inches="tight")
        plt.close()

        logger.info(f"Price trend plot saved to {price_plot_path}")
        click.echo(f"Price trend plot saved to {price_plot_path}")

    def _generate_count_plot(self, data: pd.DataFrame) -> None:
        """Generate count trend plot"""
        plt.figure(figsize=(12, 8))

        for model_name, group in data.groupby("model"):
            plt.plot(
                group["date"],
                group["count"],
                marker="s",
                label=f"{model_name} - Count",
                linewidth=2,
            )

        plt.title("Number of Listings Over Time", fontsize=16)
        plt.xlabel("Date", fontsize=12)
        plt.ylabel("Number of Listings", fontsize=12)
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()

        count_plot_path = self.plots_dir / "count_trends.png"
        plt.savefig(count_plot_path, dpi=300, bbox_inches="tight")
        plt.close()

        logger.info(f"Count trend plot saved to {count_plot_path}")
        click.echo(f"Count trend plot saved to {count_plot_path}")
