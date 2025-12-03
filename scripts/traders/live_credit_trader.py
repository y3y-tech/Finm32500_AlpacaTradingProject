#!/usr/bin/env python3
"""
Live Adaptive Credit Spread Trader

Trades across the credit quality spectrum (investment grade to high yield)
to capture credit spread dynamics and risk appetite shifts.

Assets: LQD, VCIT, HYG, JNK, BKLN
Theme: Credit spread momentum, risk-on/risk-off rotation

Note: High yield (HYG, JNK) correlates with equities during stress.
      Investment grade (LQD, VCIT) more rate-sensitive.

Usage:
    python scripts/traders/live_credit_trader.py
    python scripts/traders/live_credit_trader.py --save-data
    python scripts/traders/live_credit_trader.py --live  # REAL MONEY!
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

DEFAULT_CREDIT_ETFS = [
    "VCIT",  # Intermediate-Term Corp
    "VCLT",  # Long-Term Corp
    "LQD",  # Investment Grade Corporate
    "HYG",  # High Yield Corporate
    "JNK",  # SPDR High Yield
    "BKLN",  # Senior Loans (floating rate)
]


def main():
    if "--tickers" not in sys.argv:
        sys.argv.extend(["--tickers"] + DEFAULT_CREDIT_ETFS)

    if "--data-file" not in sys.argv:
        sys.argv.extend(["--data-file", "logs/live_credit_data.csv"])

    if "--min-warmup-bars" not in sys.argv:
        sys.argv.extend(["--min-warmup-bars", "90"])

    if "--position-size" not in sys.argv:
        sys.argv.extend(["--position-size", "1200"])

    if "--max-position" not in sys.argv:
        sys.argv.extend(["--max-position", "20"])

    from live_adaptive_trader import main as generic_main

    generic_main()


if __name__ == "__main__":
    main()
