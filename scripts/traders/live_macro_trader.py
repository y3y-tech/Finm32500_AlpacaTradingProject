#!/usr/bin/env python3
"""
Live Adaptive Global Macro Trader

Trades a diversified basket across asset classes to capture macro themes:
equities, bonds, commodities, and currencies in one portfolio.

Assets: SPY, TLT, GLD, UUP, EEM, VGK
Theme: Cross-asset momentum, risk parity lite, macro rotation

This is a "all-weather" style trader that should have lower correlation
to any single asset class. Good for diversification across your traders.

Usage:
    python scripts/traders/live_macro_trader.py
    python scripts/traders/live_macro_trader.py --save-data
    python scripts/traders/live_macro_trader.py --live  # REAL MONEY!
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

DEFAULT_MACRO_ETFS = [
    "SPY",   # US Equities
    "TLT",   # Long Treasuries (rate hedge)
    "GLD",   # Gold (inflation/crisis hedge)
    "UUP",   # US Dollar
    "EEM",   # Emerging Markets
    "VGK",   # Europe
]


def main():
    if "--tickers" not in sys.argv:
        sys.argv.extend(["--tickers"] + DEFAULT_MACRO_ETFS)

    if "--data-file" not in sys.argv:
        sys.argv.extend(["--data-file", "logs/live_macro_data.csv"])

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
