"""
Logging configuration for AlpacaTrading.

Provides centralized logging setup for consistent log formatting across all modules.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path


def setup_logging(
    level: int | str = logging.INFO,
    log_file: str | Path | None = None,
    format_string: str | None = None,
    datefmt: str = "%Y-%m-%d %H:%M:%S",
    console_output: bool = True,
) -> logging.Logger:
    """
    Configure logging for the AlpacaTrading package.

    Call this once at application startup to enable logging output.
    By default, logs are written to both console and timestamped files in logs/ directory.

    Args:
        level: Logging level (e.g., logging.DEBUG, logging.INFO, "DEBUG", "INFO")
        log_file: Optional path to write logs to file. If None, creates timestamped file in logs/
        format_string: Custom format string (uses sensible default if None)
        datefmt: Date format for timestamps
        console_output: Whether to also output logs to console (default: True)

    Returns:
        The root logger for the AlpacaTrading package

    Example:
        from AlpacaTrading import setup_logging

        # Basic setup - INFO level to console and timestamped file
        setup_logging()

        # Debug level with custom file name
        setup_logging(level=logging.DEBUG, log_file="logs/my_custom_log.log")

        # File only (no console output)
        setup_logging(console_output=False)
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

    # Console handler (optional)
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # File handler - always enabled with timestamped filename
    if log_file is None:
        # Create logs directory if it doesn't exist
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        # Generate timestamped filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"alpaca_trading_{timestamp}.log"
    else:
        log_file = Path(log_file)
        # Ensure parent directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(log_file, mode="a")  # Append mode
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Prevent propagation to root logger (avoid duplicate logs)
    logger.propagate = False

    logger.info(
        f"Logging configured: level={logging.getLevelName(level)}, file={log_file}"
    )

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
