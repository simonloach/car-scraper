"""Time series data storage (legacy support)"""

import json
from pathlib import Path
from typing import Dict, List

import click
import pandas as pd

from src.car_scraper.utils.logger import logger


class TimeSeriesStorage:
    """Handles legacy time series data storage"""
    
    def __init__(self, data_dir: str) -> None:
        """
        Initialize time series storage
        
        Args:
            data_dir: Base data directory
        """
        self.data_dir = Path(data_dir)
        self.time_series_dir = self.data_dir / 'time_series'
        self.time_series_dir.mkdir(exist_ok=True)
    
    def update_historical_data(self, new_data: List[Dict], output_format: str = 'json') -> None:
        """
        Update the historical data file with new data
        
        Args:
            new_data: List of new data entries
            output_format: 'json' or 'csv'
        """
        historical_file = self.time_series_dir / f"historical.{output_format}"
        
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
            
            logger.info(f"Updated historical data in {historical_file}")
            click.echo(f"Updated historical data in {historical_file}")
            
        except Exception as e:
            logger.error(f"Error updating historical data: {str(e)}")
            click.echo(f"Error updating historical data: {str(e)}")
    
    def get_historical_data(self, model: str = None) -> pd.DataFrame:
        """
        Get historical time series data
        
        Args:
            model: Optional model filter
            
        Returns:
            DataFrame with historical data
        """
        historical_csv = self.time_series_dir / 'historical.csv'
        historical_json = self.time_series_dir / 'historical.json'
        
        # Load historical data
        if historical_csv.exists():
            data = pd.read_csv(historical_csv)
        elif historical_json.exists():
            with open(historical_json, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            data = pd.DataFrame(json_data)
        else:
            raise FileNotFoundError("No legacy historical data found.")
        
        if len(data) == 0:
            raise ValueError("No data available for plotting.")
        
        # Filter by model if specified
        if model:
            data = data[data['model'] == model]
            if len(data) == 0:
                raise ValueError(f"No data found for model: {model}")
        
        return data
    
    def clean_duplicates(self, dry_run: bool = True) -> None:
        """
        Remove duplicate entries from time series data
        
        Args:
            dry_run: If True, show what would be removed without actually removing
        """
        logger.info("Cleaning duplicate entries from time series data")
        
        # Clean historical files
        for ext in ['csv', 'json']:
            historical_file = self.time_series_dir / f"historical.{ext}"
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
                        logger.info(f"Would remove {removed_count} duplicate entries from {historical_file.name}")
                        click.echo(f"Would remove {removed_count} duplicate entries from {historical_file.name}")
                    else:
                        if ext == 'json':
                            with open(historical_file, 'w', encoding='utf-8') as f:
                                json.dump(df_clean.to_dict('records'), f, indent=2, ensure_ascii=False)
                        else:
                            df_clean.to_csv(historical_file, index=False)
                        logger.info(f"Removed {removed_count} duplicate entries from {historical_file.name}")
                        click.echo(f"Removed {removed_count} duplicate entries from {historical_file.name}")
                else:
                    logger.info(f"No duplicates found in {historical_file.name}")
                    click.echo(f"No duplicates found in {historical_file.name}")
                    
            except Exception as e:
                logger.error(f"Error cleaning {historical_file.name}: {str(e)}")
                click.echo(f"Error cleaning {historical_file.name}: {str(e)}")
        
        # Clean daily snapshot duplicates if any
        snapshot_files = list(self.time_series_dir.glob('*.json')) + list(self.time_series_dir.glob('*.csv'))
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
                        logger.info(f"Would remove {removed_count} duplicate entries from {file_path.name}")
                        click.echo(f"Would remove {removed_count} duplicate entries from {file_path.name}")
                    else:
                        if file_path.suffix == '.json':
                            with open(file_path, 'w', encoding='utf-8') as f:
                                json.dump(df_clean.to_dict('records'), f, indent=2, ensure_ascii=False)
                        else:
                            df_clean.to_csv(file_path, index=False)
                        logger.info(f"Removed {removed_count} duplicate entries from {file_path.name}")
                        click.echo(f"Removed {removed_count} duplicate entries from {file_path.name}")
                            
            except Exception as e:
                logger.error(f"Error cleaning {file_path.name}: {str(e)}")
                click.echo(f"Error cleaning {file_path.name}: {str(e)}")
        
        if dry_run:
            click.echo("\nDry run completed. Use --dry-run=false to actually remove duplicates.")
