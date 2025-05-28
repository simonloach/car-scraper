"""Individual listings plotting functionality"""

from pathlib import Path
from typing import Optional

import click
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.car_scraper.storage.individual_listings import IndividualListingsStorage
from src.car_scraper.utils.logger import logger


class IndividualListingsPlotter:
    """Generates plots for individual car listings price trends"""
    
    def __init__(self, data_dir: str) -> None:
        """
        Initialize plotter
        
        Args:
            data_dir: Base data directory
        """
        self.data_dir = Path(data_dir)
        self.plots_dir = self.data_dir / 'plots'
        self.plots_dir.mkdir(exist_ok=True)
        self.storage = IndividualListingsStorage(str(self.data_dir))
    
    def generate_individual_listing_plots(self, model: Optional[str] = None, min_data_points: int = 2) -> None:
        """
        Generate plots showing individual listing price trends over time
        
        Args:
            model: Optional model filter
            min_data_points: Minimum number of data points required for a listing to be included
        """
        logger.info(f"Generating individual listing plots for model: {model}")
        
        try:
            df = self.storage.get_historical_data(model)
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"Cannot generate plots: {str(e)}")
            click.echo(f"Cannot generate plots: {str(e)}")
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
            logger.warning(f"No listings found with at least {min_data_points} data points.")
            click.echo(f"No listings found with at least {min_data_points} data points.")
            return
        
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
        
        plot_file = self.plots_dir / f'individual_listings_trends{"_" + model.replace("/", "_") if model else ""}.png'
        plt.savefig(plot_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Individual listings plot saved to {plot_file}")
        click.echo(f"Individual listings plot saved to {plot_file}")
        
        # Price change analysis
        self._analyze_price_changes(df, model)
    
    def _analyze_price_changes(self, df: pd.DataFrame, model: Optional[str] = None) -> None:
        """
        Analyze and plot price changes for listings
        
        Args:
            df: DataFrame with listings data
            model: Optional model name for plot title
        """
        # Get latest data for each listing
        latest_data = df.groupby('id').last().reset_index()
        
        # Filter listings with price changes
        price_changes = latest_data[latest_data['price_change'].notna() & (latest_data['price_change'] != 0)]
        
        if len(price_changes) == 0:
            logger.info("No price changes detected.")
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
        
        plot_file = self.plots_dir / f'price_changes{"_" + model.replace("/", "_") if model else ""}.png'
        plt.savefig(plot_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Price changes plot saved to {plot_file}")
        click.echo(f"Price changes plot saved to {plot_file}")
        
        # Print top price changes
        self._print_price_change_summary(decreases, increases)
    
    def _print_price_change_summary(self, decreases: pd.DataFrame, increases: pd.DataFrame) -> None:
        """Print summary of price changes"""
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
    
    def generate_enhanced_individual_plots(self, model: Optional[str] = None, min_data_points: int = 2) -> None:
        """
        Enhanced version of individual listing plots with year-based markers
        
        Args:
            model: Optional model filter
            min_data_points: Minimum number of data points required
        """
        logger.info(f"Generating enhanced individual plots for model: {model}")
        
        try:
            df = self.storage.get_historical_data(model)
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"Cannot generate enhanced plots: {str(e)}")
            click.echo(f"Cannot generate enhanced plots: {str(e)}")
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
            logger.warning(f"No listings found with at least {min_data_points} data points for trend analysis.")
            click.echo(f"No listings found with at least {min_data_points} data points for trend analysis.")
            return
        
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
        
        enhanced_plot_file = self.plots_dir / f'enhanced_individual_trends{"_" + model.replace("/", "_") if model else ""}.png'
        plt.savefig(enhanced_plot_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Enhanced individual trends plot saved to {enhanced_plot_file}")
        click.echo(f"Enhanced individual trends plot saved to {enhanced_plot_file}")
