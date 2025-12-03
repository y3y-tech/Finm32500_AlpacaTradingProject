#!/usr/bin/env python3
"""
Live Adaptive Industrial Metals & Mining Trader

Trades base metals and mining equities to capture industrial demand
cycles, China growth expectations, and commodity supercycle plays.

Assets: CPER, DBB, GDX, SIL, XME, PICK
Theme: Industrial cycle, China demand proxy, physical vs miners divergence

Note: Mining equities (GDX, SIL, XME) have equity beta + commodity exposure.
      Physical (CPER, DBB) pure commodity play.

Usage:
    python scripts/traders/live_metals_trader.py
    python scripts/traders/live_metals_trader.py --save-data
    python scripts/traders/live_metals_trader.py --live  # REAL MONEY!
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

DEFAULT_METALS_ETFS = [
    "CPER",  # Copper
    "DBB",   # Base Metals (copper, aluminum, zinc)
    "GDX",   # Gold Miners
    "SIL",   # Silver Miners
    "XME",   # Metals & Mining equities
    "PICK",  # Global Metals & Mining
]


def main():
    if "--tickers" not in sys.argv:
        sys.argv.extend(["--tickers"] + DEFAULT_METALS_ETFS)

    if "--data-file" not in sys.argv:
        sys.argv.extend(["--data-file", "logs/live_metals_data.csv"])

    if "--min-warmup-bars" not in sys.argv:
        sys.argv.extend(["--min-warmup-bars", "60"])

    # Higher volatility - moderate position sizes
    if "--position-size" not in sys.argv:
        sys.argv.extend(["--position-size", "700"])

    if "--max-position" not in sys.argv:
        sys.argv.extend(["--max-position", "12"])

    from live_adaptive_trader import main as generic_main
    generic_main()


if __name__ == "__main__":
    main()
