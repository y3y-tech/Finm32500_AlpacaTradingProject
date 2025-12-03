#!/usr/bin/env python3
"""
Live Adaptive G7 Currency Trader

Trades major currency ETFs to capture FX momentum, carry dynamics,
and relative central bank policy plays.

Assets: UUP, FXE, FXY, FXB, FXC, FXA
Theme: Currency momentum, rate differentials, risk-on/risk-off flows

Note: UUP is long USD vs basket. Others are long foreign currency vs USD.
      FX trends tend to persist - momentum strategies work well.
      Lower volatility than equities - need larger positions.

Usage:
    python scripts/traders/live_currency_trader.py
    python scripts/traders/live_currency_trader.py --save-data
    python scripts/traders/live_currency_trader.py --live  # REAL MONEY!
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

DEFAULT_CURRENCY_ETFS = [
    "UUP",   # US Dollar Index (long USD)
    "FXE",   # Euro
    "FXY",   # Japanese Yen
    "FXB",   # British Pound
    "FXC",   # Canadian Dollar
    "FXA",   # Australian Dollar
]


def main():
    if "--tickers" not in sys.argv:
        sys.argv.extend(["--tickers"] + DEFAULT_CURRENCY_ETFS)

    if "--data-file" not in sys.argv:
        sys.argv.extend(["--data-file", "logs/live_currency_data.csv"])

    # Currencies trend slowly - longer warmup
    if "--min-warmup-bars" not in sys.argv:
        sys.argv.extend(["--min-warmup-bars", "90"])

    # Larger positions - FX ETFs have lower volatility
    if "--position-size" not in sys.argv:
        sys.argv.extend(["--position-size", "1500"])

    if "--max-position" not in sys.argv:
        sys.argv.extend(["--max-position", "30"])

    # Longer rebalance - FX trends persist
    if "--rebalance-period" not in sys.argv:
        sys.argv.extend(["--rebalance-period", "120"])

    from live_adaptive_trader import main as generic_main
    generic_main()


if __name__ == "__main__":
    main()
