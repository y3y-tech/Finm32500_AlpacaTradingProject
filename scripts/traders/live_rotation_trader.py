#!/usr/bin/env python3
"""
Live Adaptive Tech vs Defensives Trader

Trades growth/tech against defensive sectors to capture the classic
cyclical rotation between offensive and defensive equity positioning.

Assets:
  Growth/Offensive: XLK, XLY, XLC
  Defensive:        XLU, XLP, XLV

Theme: Sector rotation, growth vs value proxy, economic cycle positioning

When economy is expanding: tech/discretionary outperform
When economy is slowing: utilities/staples/healthcare outperform

Usage:
    python scripts/traders/live_rotation_trader.py
    python scripts/traders/live_rotation_trader.py --save-data
    python scripts/traders/live_rotation_trader.py --live  # REAL MONEY!
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

DEFAULT_ROTATION_ETFS = [
    # Growth/Offensive sectors
    "XLK",  # Technology
    "XLY",  # Consumer Discretionary
    "XLC",  # Communication Services
    # Defensive sectors
    "XLU",  # Utilities
    "XLP",  # Consumer Staples
    "XLV",  # Health Care
]


def main():
    if "--tickers" not in sys.argv:
        sys.argv.extend(["--tickers"] + DEFAULT_ROTATION_ETFS)

    if "--data-file" not in sys.argv:
        sys.argv.extend(["--data-file", "logs/live_rotation_data.csv"])

    if "--min-warmup-bars" not in sys.argv:
        sys.argv.extend(["--min-warmup-bars", "60"])

    if "--position-size" not in sys.argv:
        sys.argv.extend(["--position-size", "1000"])

    if "--max-position" not in sys.argv:
        sys.argv.extend(["--max-position", "20"])

    from live_adaptive_trader import main as generic_main

    generic_main()


if __name__ == "__main__":
    main()
