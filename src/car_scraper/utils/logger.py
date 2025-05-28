"""Logging configuration using loguru."""

import sys
from pathlib import Path
from typing import Optional

from loguru import logger


def setup_logger(
    log_level: str = "INFO",
    log_file: Optional[Path] = None,
    rotation: str = "10 MB",
    retention: str = "7 days"
) -> None:
    """Setup loguru logger with console and optional file output.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (optional)
        rotation: When to rotate log files
        retention: How long to keep old log files
    """
    # Remove default logger
    logger.remove()
    
    # Add console handler with colors
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
               "<level>{message}</level>",
        level=log_level,
        colorize=True
    )
    
    # Add file handler if log_file is provided
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            log_file,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
                   "{name}:{function}:{line} | {message}",
            level=log_level,
            rotation=rotation,
            retention=retention,
            compression="zip"
        )
    
    logger.info(f"Logger initialized with level: {log_level}")
    if log_file:
        logger.info(f"Logging to file: {log_file}")


def get_logger(name: str):
    """Get a logger instance for a specific module."""
    return logger.bind(name=name)
