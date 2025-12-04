#!/usr/bin/env python3
"""
Live Adaptive Developed Markets Trader

Trades across major developed economy ETFs to capture country/region
rotation and relative value opportunities.

Assets: VGK, EWJ, EWC, EWA, EWU, EWG, EWL
Theme: Country rotation, regional momentum, currency-adjusted plays

Note: Currency exposure embedded - EUR, JPY, CAD, AUD, GBP, CHF
      Consider pairing with currency hedges if desired.

Usage:
    python scripts/traders/live_developed_trader.py
    python scripts/traders/live_developed_trader.py --save-data
    python scripts/traders/live_developed_trader.py --live  # REAL MONEY!
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

DEFAULT_DEVELOPED_ETFS = [
    "VGK",  # FTSE Europe
    "EWJ",  # MSCI Japan
    "EWC",  # MSCI Canada
    "EWA",  # MSCI Australia
    "EWU",  # MSCI United Kingdom
    "EWG",  # MSCI Germany
    "EWL",  # MSCI Switzerland
]


def main():
    if "--tickers" not in sys.argv:
        sys.argv.extend(["--tickers"] + DEFAULT_DEVELOPED_ETFS)

    if "--data-file" not in sys.argv:
        sys.argv.extend(["--data-file", "logs/live_developed_data.csv"])

    if "--min-warmup-bars" not in sys.argv:
        sys.argv.extend(["--min-warmup-bars", "60"])

    if "--position-size" not in sys.argv:
        sys.argv.extend(["--position-size", "800"])

    if "--max-position" not in sys.argv:
        sys.argv.extend(["--max-position", "15"])

    from live_adaptive_trader import main as generic_main

    generic_main()


if __name__ == "__main__":
    main()
