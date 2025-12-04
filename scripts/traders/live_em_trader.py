#!/usr/bin/env python3
"""
Live Adaptive Emerging Markets Trader

Trades single-country EM ETFs to capture country-specific momentum
and rotation opportunities in higher-volatility markets.

Assets: FXI, INDA, EWZ, EWT, EWY, EWW, THD
Theme: EM country rotation, momentum (trends strongly), mean reversion on overreactions

Note: Higher volatility than developed markets - adjust position sizes.
      Political/currency risk embedded in each country.

Usage:
    python scripts/traders/live_em_trader.py
    python scripts/traders/live_em_trader.py --save-data
    python scripts/traders/live_em_trader.py --live  # REAL MONEY!
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

DEFAULT_EM_ETFS = [
    "FXI",  # China Large-Cap
    "INDA",  # India
    "EWZ",  # Brazil
    "EWT",  # Taiwan
    "EWY",  # South Korea
    "EWW",  # Mexico
    "THD",  # Thailand
]


def main():
    if "--tickers" not in sys.argv:
        sys.argv.extend(["--tickers"] + DEFAULT_EM_ETFS)

    if "--data-file" not in sys.argv:
        sys.argv.extend(["--data-file", "logs/live_em_data.csv"])

    if "--min-warmup-bars" not in sys.argv:
        sys.argv.extend(["--min-warmup-bars", "45"])

    # Smaller positions due to higher volatility
    if "--position-size" not in sys.argv:
        sys.argv.extend(["--position-size", "600"])

    if "--max-position" not in sys.argv:
        sys.argv.extend(["--max-position", "12"])

    # Faster rebalance for volatile markets
    if "--rebalance-period" not in sys.argv:
        sys.argv.extend(["--rebalance-period", "45"])

    from live_adaptive_trader import main as generic_main

    generic_main()


if __name__ == "__main__":
    main()
