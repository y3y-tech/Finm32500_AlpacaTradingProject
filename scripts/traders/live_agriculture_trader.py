#!/usr/bin/env python3
"""
Live Adaptive Agriculture Trader

Trades agricultural commodity ETFs to capture food/feed price movements,
weather-driven volatility, and seasonal patterns.

Assets: DBA, CORN, WEAT, SOYB, COW
Theme: Agriculture momentum, weather plays, seasonal patterns

Note: Lower liquidity than other asset classes - use limit orders.
      Strong seasonal patterns (planting/harvest cycles).
      Weather-sensitive - can gap on USDA reports.

Usage:
    python scripts/traders/live_agriculture_trader.py
    python scripts/traders/live_agriculture_trader.py --save-data
    python scripts/traders/live_agriculture_trader.py --live  # REAL MONEY!
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

DEFAULT_AGRICULTURE_ETFS = [
    "DBA",   # Broad Agriculture
    "CORN",  # Corn
    "WEAT",  # Wheat
    "SOYB",  # Soybeans
    "COW",   # Livestock
]


def main():
    if "--tickers" not in sys.argv:
        sys.argv.extend(["--tickers"] + DEFAULT_AGRICULTURE_ETFS)

    if "--data-file" not in sys.argv:
        sys.argv.extend(["--data-file", "logs/live_agriculture_data.csv"])

    # Longer warmup - ags can be choppy
    if "--min-warmup-bars" not in sys.argv:
        sys.argv.extend(["--min-warmup-bars", "90"])

    # Smaller positions - lower liquidity
    if "--position-size" not in sys.argv:
        sys.argv.extend(["--position-size", "400"])

    if "--max-position" not in sys.argv:
        sys.argv.extend(["--max-position", "8"])

    # Slower rebalance - less liquid
    if "--rebalance-period" not in sys.argv:
        sys.argv.extend(["--rebalance-period", "90"])

    from live_adaptive_trader import main as generic_main
    generic_main()


if __name__ == "__main__":
    main()
