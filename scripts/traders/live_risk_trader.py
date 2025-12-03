#!/usr/bin/env python3
"""
Live Adaptive Risk-On/Risk-Off Trader

Trades a basket designed to capture market risk sentiment shifts.
Long risk-on assets vs risk-off assets with cross-sectional momentum.

Assets:
  Risk-On:  QQQ, HYG, EEM
  Risk-Off: TLT, GLD, UUP

Theme: Sentiment rotation, flight-to-quality, risk appetite momentum

The cross-sectional momentum strategy should naturally go long winners
and short losers, effectively expressing risk-on or risk-off views.

Usage:
    python scripts/traders/live_risk_trader.py
    python scripts/traders/live_risk_trader.py --save-data
    python scripts/traders/live_risk_trader.py --live  # REAL MONEY!
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

DEFAULT_RISK_ETFS = [
    # Risk-On assets
    "QQQ",   # Tech/Growth equities
    "HYG",   # High Yield (credit risk)
    "EEM",   # Emerging Markets
    # Risk-Off assets
    "TLT",   # Long Treasuries (flight to quality)
    "GLD",   # Gold (safe haven)
    "UUP",   # US Dollar (reserve currency)
]


def main():
    if "--tickers" not in sys.argv:
        sys.argv.extend(["--tickers"] + DEFAULT_RISK_ETFS)

    if "--data-file" not in sys.argv:
        sys.argv.extend(["--data-file", "logs/live_risk_data.csv"])

    if "--min-warmup-bars" not in sys.argv:
        sys.argv.extend(["--min-warmup-bars", "45"])

    if "--position-size" not in sys.argv:
        sys.argv.extend(["--position-size", "800"])

    if "--max-position" not in sys.argv:
        sys.argv.extend(["--max-position", "15"])

    # Faster rebalance to capture sentiment shifts
    if "--rebalance-period" not in sys.argv:
        sys.argv.extend(["--rebalance-period", "45"])

    from live_adaptive_trader import main as generic_main
    generic_main()


if __name__ == "__main__":
    main()
