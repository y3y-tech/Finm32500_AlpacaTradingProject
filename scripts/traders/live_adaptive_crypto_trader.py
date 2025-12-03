#!/usr/bin/env python3
"""
Live Adaptive Crypto Trader

Simple wrapper script that runs the generic LiveAdaptiveTrader with
preconfigured cryptocurrency tickers.

Usage:
    # Paper trading with default crypto tickers
    python scripts/traders/live_adaptive_crypto_trader.py

    # Override with custom tickers
    python scripts/traders/live_adaptive_crypto_trader.py --tickers BTC/USD ETH/USD SOL/USD

    # With data saving
    python scripts/traders/live_adaptive_crypto_trader.py --save-data

    # Custom warmup period (shorter for crypto since 24/7)
    python scripts/traders/live_adaptive_crypto_trader.py --min-warmup-bars 10

    # Live trading (CAREFUL!)
    python scripts/traders/live_adaptive_crypto_trader.py --live
"""

import sys
from pathlib import Path

# Add parent directory to path to import live_adaptive_trader
sys.path.insert(0, str(Path(__file__).parent))

# Default crypto tickers - most liquid on Alpaca
DEFAULT_CRYPTO_TICKERS = [
    "AAVE/USD",
    "AVAX/USD",
    "BAT/USD",
    "BCH/USD",
    "BTC/USD",
    "CRV/USD",
    "DOGE/USD",
    "DOT/USD",
    "ETH/USD",
    "GRT/USD",
    "LINK/USD",
    "LTC/USD",
    "PEPE/USD",
    "SHIB/USD",
    "SKY/USD",
    "SOL/USD",
    "SUSHI/USD",
    "TRUMP/USD",
    "UNI/USD",
    "USDG/USD",
    "XRP/USD",
    "XTZ/USD",
    "YFI/USD",
]


def main():
    """
    Run the generic live adaptive trader with crypto defaults.

    Injects default crypto tickers if none provided.
    """
    # Check if --tickers was provided
    if "--tickers" not in sys.argv:
        # Insert default crypto tickers
        sys.argv.extend(["--tickers"] + DEFAULT_CRYPTO_TICKERS)

    # Update default data file for crypto
    if "--data-file" not in sys.argv:
        sys.argv.extend(["--data-file", "logs/live_crypto_data.csv"])

    # Update default log file by patching sys.argv temporarily
    # (The generic script will handle logging setup)

    # Import and run the generic trader
    from live_adaptive_trader import main as generic_main

    generic_main()


if __name__ == "__main__":
    main()
