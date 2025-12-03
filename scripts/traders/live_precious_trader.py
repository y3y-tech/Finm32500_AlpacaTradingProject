#!/usr/bin/env python3
"""
Live Adaptive Precious Metals Trader

Trades physical precious metals ETFs to capture safe-haven flows,
inflation expectations, and relative value between metals.

Assets: GLD, SLV, PPLT, PALL
Theme: Precious metals momentum, gold/silver ratio, inflation plays

Note: Lower correlation to equities - good diversifier.
      Silver more volatile than gold. Platinum/Palladium industrial demand.

Usage:
    python scripts/traders/live_precious_trader.py
    python scripts/traders/live_precious_trader.py --save-data
    python scripts/traders/live_precious_trader.py --live  # REAL MONEY!
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

DEFAULT_PRECIOUS_ETFS = [
    "GLD",   # Gold
    "SLV",   # Silver
    "PPLT",  # Platinum
    "PALL",  # Palladium
]


def main():
    if "--tickers" not in sys.argv:
        sys.argv.extend(["--tickers"] + DEFAULT_PRECIOUS_ETFS)

    if "--data-file" not in sys.argv:
        sys.argv.extend(["--data-file", "logs/live_precious_data.csv"])

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
