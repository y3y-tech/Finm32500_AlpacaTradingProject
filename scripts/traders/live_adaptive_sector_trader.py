#!/usr/bin/env python3
"""
Live Adaptive Sector ETF Trader

Simple wrapper script that runs the generic LiveAdaptiveTrader with
preconfigured SPDR sector ETF tickers.

Usage:
    # Paper trading with default sector ETFs
    python scripts/traders/live_adaptive_sector_trader.py

    # Override with custom tickers
    python scripts/traders/live_adaptive_sector_trader.py --tickers XLF XLK XLE XLV

    # With data saving
    python scripts/traders/live_adaptive_sector_trader.py --save-data

    # Custom warmup period
    python scripts/traders/live_adaptive_sector_trader.py --min-warmup-bars 60

    # Live trading (CAREFUL!)
    python scripts/traders/live_adaptive_sector_trader.py --live
"""

import sys
from pathlib import Path

# Add parent directory to path to import live_adaptive_trader
sys.path.insert(0, str(Path(__file__).parent))

# Default sector ETF tickers - SPDR Select Sector ETFs
DEFAULT_SECTOR_ETFS = [
    "XLF",  # Financial
    "XLI",  # Industrial
    "XLRE",  # Real Estate
    "XLB",  # Materials
    "XLC",  # Communication
    "XLE",  # Energy
    "XLK",  # Technology
    "XLP",  # Consumer Staples
    "XLV",  # Health Care
    "XLU",  # Utilities
    "XLY",  # Consumer Discretionary
]


def main():
    """
    Run the generic live adaptive trader with sector ETF defaults.

    Injects default sector ETF tickers if none provided.
    """
    # Check if --tickers was provided
    if "--tickers" not in sys.argv:
        # Insert default sector ETF tickers
        sys.argv.extend(["--tickers"] + DEFAULT_SECTOR_ETFS)

    # Update default data file for sectors
    if "--data-file" not in sys.argv:
        sys.argv.extend(["--data-file", "logs/live_sector_data.csv"])

    # Use higher default warmup for stocks (market hours only)
    if "--min-warmup-bars" not in sys.argv:
        sys.argv.extend(["--min-warmup-bars", "60"])

    # Use higher position sizes for stocks (less volatile than crypto)
    if "--position-size" not in sys.argv:
        sys.argv.extend(["--position-size", "1000"])

    if "--max-position" not in sys.argv:
        sys.argv.extend(["--max-position", "15"])

    # Import and run the generic trader
    from live_adaptive_trader import main as generic_main

    generic_main()


if __name__ == "__main__":
    main()
