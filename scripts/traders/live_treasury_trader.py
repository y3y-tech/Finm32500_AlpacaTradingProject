#!/usr/bin/env python3
"""
Live Adaptive Treasury Yield Curve Trader

Trades across the yield curve (intermediate to long duration) to capture
rate direction momentum and curve steepening/flattening opportunities.

Assets: IEI, IEF, TLH, TLT
Theme: Duration rotation, rate momentum, curve trades

Note: These move inversely to interest rates. Rising rates = falling prices.
      High correlation between instruments - cross-sectional strategy less useful.

Usage:
    python scripts/traders/live_treasury_trader.py
    python scripts/traders/live_treasury_trader.py --save-data
    python scripts/traders/live_treasury_trader.py --live  # REAL MONEY!
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

DEFAULT_TREASURY_ETFS = [
    "IEI",   # 3-7 Year Treasury
    "IEF",   # 7-10 Year Treasury
    "TLH",   # 10-20 Year Treasury
    "TLT",   # 20+ Year Treasury
]


def main():
    if "--tickers" not in sys.argv:
        sys.argv.extend(["--tickers"] + DEFAULT_TREASURY_ETFS)

    if "--data-file" not in sys.argv:
        sys.argv.extend(["--data-file", "logs/live_treasury_data.csv"])

    # Bonds are less volatile - need longer warmup for meaningful signals
    if "--min-warmup-bars" not in sys.argv:
        sys.argv.extend(["--min-warmup-bars", "90"])

    # Larger position sizes since lower volatility
    if "--position-size" not in sys.argv:
        sys.argv.extend(["--position-size", "1500"])

    if "--max-position" not in sys.argv:
        sys.argv.extend(["--max-position", "25"])

    # Longer rebalance period - bonds trend slowly
    if "--rebalance-period" not in sys.argv:
        sys.argv.extend(["--rebalance-period", "120"])

    from live_adaptive_trader import main as generic_main
    generic_main()


if __name__ == "__main__":
    main()
