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
            'model_files': [],
            'time_series_files': [],
            'individual_listings': {},
            'plots': []
        }
        
        if not self.data_dir.exists():
            return status
        
        # Model files
        model_files = list(self.data_dir.glob('*.json')) + list(self.data_dir.glob('*.csv'))
        for file_path in model_files:
            try:
                if file_path.suffix == '.json':
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                    count = len(data)
                else:
                    df = pd.read_csv(file_path)
                    count = len(df)
                
                status['model_files'].append({
                    'name': file_path.name,
                    'count': count,
                    'size': file_path.stat().st_size
                })
            except Exception as e:
                status['model_files'].append({
                    'name': file_path.name,
                    'count': 0,
                    'error': str(e)
                })
        
        # Time series data
        time_series_dir = self.data_dir / 'time_series'
        if time_series_dir.exists():
            time_series_files = list(time_series_dir.glob('*.json')) + list(time_series_dir.glob('*.csv'))
            for file_path in time_series_files:
                status['time_series_files'].append({
                    'name': file_path.name,
                    'size': file_path.stat().st_size
                })
        
        # Individual listings data
        listings_dir = self.data_dir / 'individual_listings'
        if listings_dir.exists():
            history_csv = listings_dir / 'listings_history.csv'
            history_json = listings_dir / 'listings_history.json'
            id_mapping = listings_dir / 'id_mapping.json'
            
            if history_csv.exists():
                try:
                    df = pd.read_csv(history_csv)
                    status['individual_listings']['history_csv'] = {
                        'entries': len(df),
                        'unique_listings': df['id'].nunique() if 'id' in df.columns else 0
                    }
                except Exception as e:
                    status['individual_listings']['history_csv'] = {'error': str(e)}
            
            if history_json.exists():
                try:
                    with open(history_json, 'r') as f:
                        data = json.load(f)
                    status['individual_listings']['history_json'] = {
                        'entries': len(data),
                        'size': history_json.stat().st_size
                    }
                except Exception as e:
                    status['individual_listings']['history_json'] = {'error': str(e)}
            
            if id_mapping.exists():
                try:
                    with open(id_mapping, 'r') as f:
                        mapping = json.load(f)
                    status['individual_listings']['id_mapping'] = {
                        'unique_listings': len(mapping)
                    }
                except Exception as e:
                    status['individual_listings']['id_mapping'] = {'error': str(e)}
        
        # Plots
        plots_dir = self.data_dir / 'plots'
        if plots_dir.exists():
            plot_files = list(plots_dir.glob('*.png'))
            status['plots'] = [{'name': f.name, 'size': f.stat().st_size} for f in plot_files]
        
        return status
    
    def print_status(self) -> None:
        """Print formatted data status"""
        status = self.get_data_status()
        
        if not self.data_dir.exists():
            click.echo(f"Data directory {self.data_dir} does not exist.")
            return
        
        # Model files
        click.echo(f"Found {len(status['model_files'])} model data files:")
        for file_info in status['model_files']:
            if 'error' in file_info:
                click.echo(f"  {file_info['name']}: Error reading file ({file_info['error']})")
            else:
                click.echo(f"  {file_info['name']}: {file_info['count']} records")
        
        # Time series data
        if status['time_series_files']:
            click.echo(f"\nFound {len(status['time_series_files'])} time series files:")
            for file_info in status['time_series_files']:
                click.echo(f"  {file_info['name']}")
        
        # Individual listings
        if status['individual_listings']:
            click.echo(f"\nIndividual listings data:")
            if 'history_csv' in status['individual_listings']:
                hist_info = status['individual_listings']['history_csv']
                if 'error' not in hist_info:
                    click.echo(f"  History CSV: {hist_info['entries']} entries, {hist_info['unique_listings']} unique listings")
                else:
                    click.echo(f"  History CSV: Error - {hist_info['error']}")
            
            if 'id_mapping' in status['individual_listings']:
                mapping_info = status['individual_listings']['id_mapping']
                if 'error' not in mapping_info:
                    click.echo(f"  ID Mapping: {mapping_info['unique_listings']} unique listings tracked")
                else:
                    click.echo(f"  ID Mapping: Error - {mapping_info['error']}")
        
        # Plots
        if status['plots']:
            click.echo(f"\nFound {len(status['plots'])} generated plots:")
            for plot_info in status['plots']:
                size_kb = plot_info['size'] / 1024
                click.echo(f"  {plot_info['name']} ({size_kb:.1f} KB)")
    
    def clean_data(self, dry_run: bool = True) -> None:
        """
        Clean and validate data files
        
        Args:
            dry_run: If True, show what would be cleaned without actually doing it
        """
        logger.info(f"Cleaning data (dry_run={dry_run})")
        
        # Clean individual listings duplicates
        self._clean_individual_listings(dry_run)
        
        # Clean time series duplicates
        self._clean_time_series(dry_run)
        
        if dry_run:
            click.echo("\nDry run completed. Use --dry-run=false to actually clean data.")
    
    def _clean_individual_listings(self, dry_run: bool) -> None:
        """Clean individual listings data"""
        listings_dir = self.data_dir / 'individual_listings'
        if not listings_dir.exists():
            return
        
        for file_name in ['listings_history.csv', 'listings_history.json']:
            file_path = listings_dir / file_name
            if not file_path.exists():
                continue
            
            try:
                if file_name.endswith('.json'):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    df = pd.DataFrame(data)
                else:
                    df = pd.read_csv(file_path)
                
                original_count = len(df)
                
                # Remove duplicates based on id and date
                df_clean = df.drop_duplicates(subset=['id', 'date'], keep='last')
                removed_count = original_count - len(df_clean)
                
                if removed_count > 0:
                    if dry_run:
                        click.echo(f"Would remove {removed_count} duplicate entries from {file_name}")
                    else:
                        if file_name.endswith('.json'):
                            with open(file_path, 'w', encoding='utf-8') as f:
                                json.dump(df_clean.to_dict('records'), f, indent=2, ensure_ascii=False)
                        else:
                            df_clean.to_csv(file_path, index=False)
                        click.echo(f"Removed {removed_count} duplicate entries from {file_name}")
                else:
                    click.echo(f"No duplicates found in {file_name}")
                    
            except Exception as e:
                logger.error(f"Error cleaning {file_name}: {str(e)}")
                click.echo(f"Error cleaning {file_name}: {str(e)}")
    
    def _clean_time_series(self, dry_run: bool) -> None:
        """Clean time series data"""
        time_series_dir = self.data_dir / 'time_series'
        if not time_series_dir.exists():
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
                logger.error(f"Error cleaning {historical_file.name}: {str(e)}")
                click.echo(f"Error cleaning {historical_file.name}: {str(e)}")
    
    def export_data(self, format: str = 'csv', model: Optional[str] = None) -> None:
        """
        Export data in specified format
        
        Args:
            format: Export format ('csv', 'json', 'excel')
            model: Optional model filter
        """
        logger.info(f"Exporting data in {format} format for model: {model}")
        
        # Create exports directory
        exports_dir = self.data_dir / 'exports'
        exports_dir.mkdir(exist_ok=True)
        
        # Export individual listings data
        self._export_individual_listings(exports_dir, format, model)
        
        # Export aggregated data
        self._export_aggregated_data(exports_dir, format, model)
        
        click.echo(f"Data exported to {exports_dir}")
    
    def _export_individual_listings(self, exports_dir: Path, format: str, model: Optional[str]) -> None:
        """Export individual listings data"""
        listings_dir = self.data_dir / 'individual_listings'
        history_file = listings_dir / 'listings_history.csv'
        
        if not history_file.exists():
            return
        
        try:
            df = pd.read_csv(history_file)
            
            if model:
                df = df[df['model'] == model]
                if len(df) == 0:
                    return
            
            filename = f"individual_listings{'_' + model.replace('/', '_') if model else ''}.{format}"
            output_file = exports_dir / filename
            
            if format == 'csv':
                df.to_csv(output_file, index=False)
            elif format == 'json':
                df.to_json(output_file, orient='records', indent=2)
            elif format == 'excel':
                df.to_excel(output_file, index=False)
            
            click.echo(f"Exported individual listings to {filename}")
            
        except Exception as e:
            logger.error(f"Error exporting individual listings: {str(e)}")
    
    def _export_aggregated_data(self, exports_dir: Path, format: str, model: Optional[str]) -> None:
        """Export aggregated statistical data"""
        try:
            from ..storage.individual_listings import IndividualListingsStorage
            storage = IndividualListingsStorage(str(self.data_dir))
            df = storage.get_historical_data(model)
            
            # Create aggregated statistics
            stats = df.groupby(['model', 'year']).agg({
                'price': ['count', 'mean', 'median', 'min', 'max', 'std'],
                'mileage': ['mean', 'median']
            }).round(2)
            
            # Flatten column names
            stats.columns = ['_'.join(col).strip() for col in stats.columns.values]
            stats = stats.reset_index()
            
            filename = f"aggregated_stats{'_' + model.replace('/', '_') if model else ''}.{format}"
            output_file = exports_dir / filename
            
            if format == 'csv':
                stats.to_csv(output_file, index=False)
            elif format == 'json':
                stats.to_json(output_file, orient='records', indent=2)
            elif format == 'excel':
                stats.to_excel(output_file, index=False)
            
            click.echo(f"Exported aggregated statistics to {filename}")
            
        except Exception as e:
            logger.error(f"Error exporting aggregated data: {str(e)}")
