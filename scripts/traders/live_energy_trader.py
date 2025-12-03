#!/usr/bin/env python3
"""
Live Adaptive Energy Commodities Trader

Trades physical energy commodity ETFs to capture oil/gas price movements,
spread opportunities, and energy cycle plays.

Assets: USO, BNO, UNG, UGA
Theme: Energy momentum, WTI/Brent spread, seasonal patterns

WARNING: USO and UNG use futures - suffer from contango drag over time.
         These are trading vehicles, NOT long-term holds.
         Best for momentum and short-term mean reversion.

Usage:
    python scripts/traders/live_energy_trader.py
    python scripts/traders/live_energy_trader.py --save-data
    python scripts/traders/live_energy_trader.py --live  # REAL MONEY!
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

DEFAULT_ENERGY_ETFS = [
    "USO",   # WTI Crude Oil
    "BNO",   # Brent Crude Oil
    "UNG",   # Natural Gas
    "UGA",   # Gasoline
]


def main():
    if "--tickers" not in sys.argv:
        sys.argv.extend(["--tickers"] + DEFAULT_ENERGY_ETFS)

    if "--data-file" not in sys.argv:
        sys.argv.extend(["--data-file", "logs/live_energy_data.csv"])

    # Energy is volatile - shorter warmup catches trends faster
    if "--min-warmup-bars" not in sys.argv:
        sys.argv.extend(["--min-warmup-bars", "45"])

    # Smaller positions - energy is very volatile
    if "--position-size" not in sys.argv:
        sys.argv.extend(["--position-size", "500"])

    if "--max-position" not in sys.argv:
        sys.argv.extend(["--max-position", "10"])

    # Faster rebalance for volatile asset class
    if "--rebalance-period" not in sys.argv:
        sys.argv.extend(["--rebalance-period", "45"])

    from live_adaptive_trader import main as generic_main
    generic_main()


if __name__ == "__main__":
    main()
