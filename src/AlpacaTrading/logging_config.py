"""
Logging configuration for AlpacaTrading.

Provides centralized logging setup for consistent log formatting across all modules.
"""

import logging
import sys
from pathlib import Path


def setup_logging(
    level: int | str = logging.INFO,
    log_file: str | Path | None = None,
    format_string: str | None = None,
    datefmt: str = "%Y-%m-%d %H:%M:%S",
) -> logging.Logger:
    """
    Configure logging for the AlpacaTrading package.

    Call this once at application startup to enable logging output.

    Args:
        level: Logging level (e.g., logging.DEBUG, logging.INFO, "DEBUG", "INFO")
        log_file: Optional path to write logs to file (in addition to console)
        format_string: Custom format string (uses sensible default if None)
        datefmt: Date format for timestamps

    Returns:
        The root logger for the AlpacaTrading package

    Example:
        from AlpacaTrading import setup_logging

        # Basic setup - INFO level to console
        setup_logging()

        # Debug level with file output
        setup_logging(level=logging.DEBUG, log_file="trading.log")

        # Custom format
        setup_logging(format_string="%(levelname)s: %(message)s")
    """
    # Convert string level to int if needed
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    # Default format
    if format_string is None:
        format_string = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    # Get the package logger
    logger = logging.getLogger("AlpacaTrading")
    logger.setLevel(level)

    # Clear existing handlers to avoid duplicates on repeated calls
    logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(format_string, datefmt=datefmt)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file is not None:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Prevent propagation to root logger (avoid duplicate logs)
    logger.propagate = False

    logger.debug(f"Logging configured: level={logging.getLevelName(level)}, file={log_file}")

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific module.

    Use this in individual modules to get a child logger of the main package logger.

    Args:
        name: Module name (typically __name__)

    Returns:
        Logger instance

    Example:
        from AlpacaTrading.logging_config import get_logger
        logger = get_logger(__name__)
        logger.info("Module initialized")
    """
    return logging.getLogger(name)
