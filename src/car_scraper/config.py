"""Configuration management."""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class ScrapingConfig(BaseModel):
    """Configuration for scraping operations."""

    max_pages: int = Field(10, ge=1, description="Maximum number of pages to scrape")
    request_timeout: int = Field(30, ge=1, description="Request timeout in seconds")
    delay_between_requests: float = Field(
        0.1, ge=0, description="Delay between requests"
    )
    delay_between_pages: float = Field(0.5, ge=0, description="Delay between pages")
    user_agents: list[str] = Field(
        default_factory=lambda: [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/109.0",
        ],
        description="List of user agents to rotate",
    )


class PlottingConfig(BaseModel):
    """Configuration for plotting operations."""

    figure_size: tuple[int, int] = Field((14, 8), description="Default figure size")
    dpi: int = Field(100, ge=50, description="DPI for plots")
    color_palette: list[str] = Field(
        default_factory=lambda: [
            "#1f77b4",
            "#ff7f0e",
            "#2ca02c",
            "#d62728",
            "#9467bd",
            "#8c564b",
            "#e377c2",
            "#7f7f7f",
        ],
        description="Color palette for plots",
    )


class Config(BaseModel):
    """Main application configuration."""

    data_dir: Path = Field(Path("./data"), description="Data directory path")
    plots_dir: Optional[Path] = Field(None, description="Plots directory path")
    scraping: ScrapingConfig = Field(default_factory=ScrapingConfig)
    plotting: PlottingConfig = Field(default_factory=PlottingConfig)

    def __post_init__(self) -> None:
        """Set default plots directory if not provided."""
        if self.plots_dir is None:
            self.plots_dir = self.data_dir / "plots"

    @classmethod
    def load_from_file(cls, config_path: Path) -> "Config":
        """Load configuration from file."""
        if config_path.exists():
            import json

            with open(config_path, "r") as f:
                data = json.load(f)
            return cls(**data)
        return cls()

    def save_to_file(self, config_path: Path) -> None:
        """Save configuration to file."""
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            import json

            json.dump(self.model_dump(), f, indent=2, default=str)
