#!/usr/bin/env python3
"""
Live Adaptive US Equity Cap Trader

Trades across the market cap spectrum (large, mid, small) to capture
size rotation and relative value opportunities.

Assets: SPY, QQQ, IWM, IJH, IWR
Theme: Size rotation, momentum across caps, mean reversion

Usage:
    python scripts/traders/live_cap_trader.py
    python scripts/traders/live_cap_trader.py --save-data
    python scripts/traders/live_cap_trader.py --live  # REAL MONEY!
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

DEFAULT_CAP_ETFS = [
    "SPY",  # S&P 500 Large Cap
    "QQQ",  # Nasdaq 100 (tech-heavy large)
    "IWM",  # Russell 2000 Small Cap
    "IJH",  # S&P 400 Mid Cap
    "IWR",  # Russell Mid Cap
]


def main():
    if "--tickers" not in sys.argv:
        sys.argv.extend(["--tickers"] + DEFAULT_CAP_ETFS)

    if "--data-file" not in sys.argv:
        sys.argv.extend(["--data-file", "logs/live_cap_data.csv"])

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
