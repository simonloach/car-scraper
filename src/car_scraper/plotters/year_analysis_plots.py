"""Year-based analysis plotting functionality"""

from pathlib import Path
from typing import Optional

import click
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.car_scraper.storage.individual_listings import IndividualListingsStorage
from src.car_scraper.utils.logger import logger


class YearAnalysisPlotter:
    """Generates comprehensive year-based analysis plots"""

    def __init__(self, data_dir: str) -> None:
        """
        Initialize year analysis plotter

        Args:
            data_dir: Base data directory
        """
        self.data_dir = Path(data_dir)
        # Use root-level plots directory instead of data/plots
        self.plots_dir = self.data_dir.parent / "plots"
        self.plots_dir.mkdir(exist_ok=True)
        self.storage = IndividualListingsStorage(str(self.data_dir))

    def _get_model_plots_dir(self, model: Optional[str]) -> Path:
        """
        Get the plots directory for a specific model
        
        Args:
            model: Model name (e.g., 'bmw-i8')
            
        Returns:
            Path to model-specific plots directory
        """
        if model:
            # Create plots directory structure: plots/bmw-i8/
            model_plots_dir = self.plots_dir / model.replace("/", "_")
            model_plots_dir.mkdir(parents=True, exist_ok=True)
            return model_plots_dir
        else:
            return self.plots_dir

    def generate_year_analysis_plots(self, model: Optional[str] = None) -> None:
        """
        Generate comprehensive year-based analysis plots

        Args:
            model: Optional model filter
        """
        logger.info(f"Generating year analysis plots for model: {model}")

        try:
            df = self.storage.get_historical_data(model)
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"Cannot generate year analysis: {str(e)}")
            click.echo(f"Cannot generate year analysis: {str(e)}")
            return

        # Clean and prepare data
        df["year"] = pd.to_numeric(df["year"], errors="coerce")
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        df["mileage"] = pd.to_numeric(df["mileage"], errors="coerce")

        # Remove invalid data
        df = df.dropna(subset=["year", "price"])
        df = df[df["price"] > 0]
        df = df[df["year"] > 1990]  # Remove invalid years

        if len(df) == 0:
            logger.warning("No valid data found for year analysis.")
            click.echo("No valid data found for year analysis.")
            return

        # IMPORTANT: Deduplicate by internal_id to get unique cars only
        # This prevents counting the same car multiple times from different scrape dates
        if "internal_id" in df.columns:
            original_count = len(df)
            # Keep the most recent entry for each unique car (internal_id)
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").groupby("internal_id").tail(1)
            logger.info(
                f"Deduplicated from {original_count} entries to {len(df)} unique cars"
            )
            click.echo(
                f"Deduplicated from {original_count} entries to {len(df)} unique cars"
            )
        else:
            logger.warning(
                "No internal_id column found, analysis may include duplicates"
            )
            click.echo(
                "Warning: No internal_id column found, analysis may include duplicates"
            )

        if len(df) == 0:
            logger.warning("No unique cars found after deduplication.")
            click.echo("No unique cars found after deduplication.")
            return

        # Generate comprehensive year analysis
        self._generate_four_panel_analysis(df, model)
        self._generate_year_scatter_plot(df, model)
        self._generate_price_vs_mileage_plot(df, model)
        self._print_year_analysis_summary(df, model)

    def _generate_four_panel_analysis(
        self, df: pd.DataFrame, model: Optional[str] = None
    ) -> None:
        """Generate 4-panel year analysis plot"""
        # Create year statistics
        year_stats = (
            df.groupby("year")
            .agg(
                {"price": ["mean", "median", "min", "max", "count"], "mileage": "mean"}
            )
            .round(0)
        )

        year_stats.columns = [
            "avg_price",
            "median_price",
            "min_price",
            "max_price",
            "count",
            "avg_mileage",
        ]
        year_stats = year_stats.reset_index()

        plt.figure(figsize=(14, 8))

        # 1. Average Price by Year Plot
        plt.subplot(2, 2, 1)
        plt.bar(
            year_stats["year"],
            year_stats["avg_price"],
            alpha=0.7,
            color="skyblue",
            label="Average Price",
        )
        plt.plot(
            year_stats["year"],
            year_stats["median_price"],
            marker="o",
            color="red",
            linewidth=2,
            label="Median Price",
        )
        plt.title(
            f'Average & Median Price by Year (Unique Cars){" - " + model if model else ""}'
        )
        plt.xlabel("Year")
        plt.ylabel("Price (PLN)")
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)

        # 2. Number of Listings by Year
        plt.subplot(2, 2, 2)
        plt.bar(year_stats["year"], year_stats["count"], alpha=0.7, color="lightgreen")
        plt.title(f'Number of Unique Cars by Year{" - " + model if model else ""}')
        plt.xlabel("Year")
        plt.ylabel("Number of Unique Cars")
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)

        # Add count labels on bars
        for i, v in enumerate(year_stats["count"]):
            plt.text(
                year_stats["year"].iloc[i],
                v + max(year_stats["count"]) * 0.01,
                str(int(v)),
                ha="center",
                va="bottom",
                fontsize=8,
            )

        # 3. Price Range by Year (Min/Max)
        plt.subplot(2, 2, 3)
        plt.fill_between(
            year_stats["year"],
            year_stats["min_price"],
            year_stats["max_price"],
            alpha=0.3,
            color="orange",
            label="Price Range",
        )
        plt.plot(
            year_stats["year"],
            year_stats["avg_price"],
            marker="o",
            color="blue",
            linewidth=2,
            label="Average Price",
        )
        plt.title(f'Price Range by Year (Unique Cars){" - " + model if model else ""}')
        plt.xlabel("Year")
        plt.ylabel("Price (PLN)")
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)

        # 4. Average Mileage by Year
        plt.subplot(2, 2, 4)
        valid_mileage = year_stats[year_stats["avg_mileage"].notna()]
        if len(valid_mileage) > 0:
            plt.bar(
                valid_mileage["year"],
                valid_mileage["avg_mileage"],
                alpha=0.7,
                color="coral",
            )
            plt.title(
                f'Average Mileage by Year (Unique Cars){" - " + model if model else ""}'
            )
            plt.xlabel("Year")
            plt.ylabel("Average Mileage (km)")
            plt.grid(True, alpha=0.3)
            plt.xticks(rotation=45)

        plt.tight_layout()

        model_plots_dir = self._get_model_plots_dir(model)
        year_plot_file = model_plots_dir / f'year_analysis.png'
        plt.savefig(year_plot_file, dpi=300, bbox_inches="tight")
        plt.close()

        logger.info(f"Year analysis plot saved to {year_plot_file}")
        click.echo(f"Year analysis plot saved to {year_plot_file}")

    def _generate_year_scatter_plot(
        self, df: pd.DataFrame, model: Optional[str] = None
    ) -> None:
        """Generate scatter plot with year-based markers"""
        plt.figure(figsize=(16, 10))

        # Convert date to datetime
        df["date"] = pd.to_datetime(df["date"])

        # Create year-based color mapping
        unique_years = sorted(df["year"].unique())
        year_colors = plt.cm.viridis(np.linspace(0, 1, len(unique_years)))
        year_color_map = dict(zip(unique_years, year_colors))

        # Define markers for different year ranges
        markers = ["o", "s", "^", "D", "v", "<", ">", "p", "*", "h"]
        year_markers = {}
        for i, year in enumerate(unique_years):
            year_markers[year] = markers[i % len(markers)]

        # Plot each listing with year-based styling
        for _, row in df.iterrows():
            year = row["year"]

            plt.scatter(
                row["date"],
                row["price"],
                color=year_color_map[year],
                marker=year_markers[year],
                s=60,
                alpha=0.7,
                label=(
                    f"{int(year)}"
                    if f"{int(year)}" not in plt.gca().get_legend_handles_labels()[1]
                    else ""
                ),
            )

        plt.title(f'Unique Cars by Year{" - " + model if model else ""}')
        plt.xlabel("Date")
        plt.ylabel("Price (PLN)")
        plt.xticks(rotation=45)
        plt.grid(True, alpha=0.3)

        # Create custom legend for years
        handles, labels = plt.gca().get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        sorted_items = sorted(
            by_label.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0
        )
        plt.legend(
            [item[1] for item in sorted_items],
            [item[0] for item in sorted_items],
            title="Production Year",
            bbox_to_anchor=(1.05, 1),
            loc="upper left",
        )

        plt.tight_layout()

        model_plots_dir = self._get_model_plots_dir(model)
        year_scatter_file = model_plots_dir / f'listings_by_year.png'
        plt.savefig(year_scatter_file, dpi=300, bbox_inches="tight")
        plt.close()

        logger.info(f"Year-based scatter plot saved to {year_scatter_file}")
        click.echo(f"Year-based scatter plot saved to {year_scatter_file}")

    def _generate_price_vs_mileage_plot(
        self, df: pd.DataFrame, model: Optional[str] = None
    ) -> None:
        """Generate price vs mileage scatter plot with year coloring"""
        plt.figure(figsize=(12, 8))

        valid_data = df[df["mileage"].notna() & (df["mileage"] > 0)]
        if len(valid_data) > 0:
            scatter = plt.scatter(
                valid_data["mileage"],
                valid_data["price"],
                c=valid_data["year"],
                cmap="viridis",
                s=60,
                alpha=0.7,
            )

            plt.colorbar(scatter, label="Production Year")
            plt.title(
                f'Price vs Mileage (unique cars, colored by year){" - " + model if model else ""}'
            )
            plt.xlabel("Mileage (km)")
            plt.ylabel("Price (PLN)")
            plt.grid(True, alpha=0.3)

            # Add trend line
            z = np.polyfit(valid_data["mileage"], valid_data["price"], 1)
            p = np.poly1d(z)
            plt.plot(
                valid_data["mileage"],
                p(valid_data["mileage"]),
                "r--",
                alpha=0.8,
                linewidth=2,
            )

            plt.tight_layout()

            model_plots_dir = self._get_model_plots_dir(model)
            price_mileage_file = model_plots_dir / f'price_vs_mileage.png'
            plt.savefig(price_mileage_file, dpi=300, bbox_inches="tight")
            plt.close()

            logger.info(f"Price vs mileage plot saved to {price_mileage_file}")
            click.echo(f"Price vs mileage plot saved to {price_mileage_file}")

    def _print_year_analysis_summary(
        self, df: pd.DataFrame, model: Optional[str] = None
    ) -> None:
        """Print year analysis summary statistics"""
        year_stats = (
            df.groupby("year")
            .agg(
                {
                    "price": ["mean", "count"],
                }
            )
            .round(0)
        )
        year_stats.columns = ["avg_price", "count"]
        year_stats = year_stats.reset_index()

        click.echo(f"\n--- Year Analysis Summary{' - ' + model if model else ''} ---")
        click.echo(f"Total unique cars: {len(df)}")
        click.echo(f"Year range: {int(df['year'].min())} - {int(df['year'].max())}")
        click.echo(
            f"Price range: {df['price'].min():,.0f} - {df['price'].max():,.0f} PLN"
        )
        if df["mileage"].notna().sum() > 0:
            click.echo(
                f"Mileage range: {df['mileage'].min():,.0f} - {df['mileage'].max():,.0f} km"
            )

        click.echo("\nUnique cars by year:")
        for _, row in year_stats.iterrows():
            year = int(row["year"])
            count = int(row["count"])
            avg_price = int(row["avg_price"])
            click.echo(f"  {year}: {count} cars, avg price: {avg_price:,} PLN")
