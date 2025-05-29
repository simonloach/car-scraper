"""Data models for car scraping."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class CarListing(BaseModel):
    """Represents a single car listing."""

    id: str = Field(..., description="Unique listing identifier")
    title: str = Field(..., description="Car title/description")
    price: int = Field(..., ge=0, description="Price in PLN")
    year: int = Field(..., ge=1990, le=2030, description="Manufacturing year")
    mileage: Optional[int] = Field(None, ge=0, description="Mileage in kilometers")
    url: HttpUrl = Field(..., description="Link to the listing")
    model: str = Field(..., description="Model name")
    scrape_date: datetime = Field(..., description="Date of scraping")
    scrape_timestamp: int = Field(..., description="Unix timestamp of scraping")


class CarListingHistory(CarListing):
    """Car listing with historical tracking information."""

    date: str = Field(..., description="Date in YYYY-MM-DD format")
    price_change: int = Field(0, description="Price change from previous scrape")
    price_change_percent: float = Field(0.0, description="Price change percentage")
    internal_id: int = Field(..., description="Internal tracking ID")


class ScrapingResults(BaseModel):
    """Results from a scraping session."""

    total_found: int = Field(..., ge=0, description="Total links found")
    successful_fetches: int = Field(..., ge=0, description="Successful fetches")
    failed_fetches: int = Field(..., ge=0, description="Failed fetches")
    filtered_out: int = Field(..., ge=0, description="Links filtered out")
    listings: list[CarListing] = Field(
        default_factory=list, description="Scraped listings"
    )


class YearAnalysisData(BaseModel):
    """Year-based analysis data."""

    year: int = Field(..., description="Production year")
    count: int = Field(..., ge=0, description="Number of unique cars")
    avg_price: float = Field(..., ge=0, description="Average price")
    median_price: float = Field(..., ge=0, description="Median price")
    min_price: int = Field(..., ge=0, description="Minimum price")
    max_price: int = Field(..., ge=0, description="Maximum price")
    avg_mileage: Optional[float] = Field(None, ge=0, description="Average mileage")
