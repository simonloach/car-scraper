"""ID mapping storage for tracking unique car listings"""

import json
from pathlib import Path
from typing import Dict, Tuple

import click

from src.car_scraper.utils.logger import logger


class IdMappingStorage:
    """Handles storage and management of internal ID mappings"""
    
    def __init__(self, data_dir: str) -> None:
        """
        Initialize ID mapping storage
        
        Args:
            data_dir: Base data directory
        """
        self.data_dir = Path(data_dir)
        self.listings_dir = self.data_dir / 'individual_listings'
        self.listings_dir.mkdir(exist_ok=True)
        self.id_mapping_file = self.listings_dir / 'id_mapping.json'
    
    def load_or_create_mapping(self) -> Tuple[Dict[str, int], int]:
        """
        Load existing ID mapping or create new one
        
        Returns:
            Tuple of (id_mapping dict, next_available_id int)
        """
        id_mapping = {}
        if self.id_mapping_file.exists():
            try:
                with open(self.id_mapping_file, 'r', encoding='utf-8') as f:
                    id_mapping = json.load(f)
                    logger.debug(f"Loaded ID mapping with {len(id_mapping)} entries")
            except Exception as e:
                logger.warning(f"Could not load ID mapping: {str(e)}")
                click.echo(f"Warning: Could not load ID mapping: {str(e)}")
        
        # Find next available internal ID
        existing_internal_ids = set(id_mapping.values()) if id_mapping else set()
        next_id = 1
        while next_id in existing_internal_ids:
            next_id += 1
        
        return id_mapping, next_id
    
    def save_mapping(self, id_mapping: Dict[str, int]) -> None:
        """
        Save ID mapping to file
        
        Args:
            id_mapping: Dictionary mapping listing IDs to internal IDs
        """
        try:
            with open(self.id_mapping_file, 'w', encoding='utf-8') as f:
                json.dump(id_mapping, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved ID mapping with {len(id_mapping)} entries")
        except Exception as e:
            logger.error(f"Error saving ID mapping: {str(e)}")
            click.echo(f"Error saving ID mapping: {str(e)}")
    
    def get_internal_id(self, listing_id: str) -> int:
        """
        Get internal ID for a listing ID, creating one if it doesn't exist
        
        Args:
            listing_id: External listing ID
            
        Returns:
            Internal ID number
        """
        id_mapping, next_id = self.load_or_create_mapping()
        
        if listing_id not in id_mapping:
            id_mapping[listing_id] = next_id
            self.save_mapping(id_mapping)
            return next_id
        
        return id_mapping[listing_id]
    
    def get_mapping_stats(self) -> Dict:
        """
        Get statistics about the ID mapping
        
        Returns:
            Dictionary with mapping statistics
        """
        id_mapping, _ = self.load_or_create_mapping()
        
        return {
            'total_unique_listings': len(id_mapping),
            'highest_internal_id': max(id_mapping.values()) if id_mapping else 0,
            'mapping_file_exists': self.id_mapping_file.exists()
        }
