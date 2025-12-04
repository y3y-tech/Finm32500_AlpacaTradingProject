#!/usr/bin/env python3
"""
Generic Live Adaptive Trader

Connects to Alpaca streaming API, observes market data, and trades
adaptively with multiple strategies once sufficient data is collected.

Supports both US Equities and Cryptocurrencies - auto-detected from ticker format.

Features:
- Real-time Alpaca market data streaming (Stocks or Crypto)
- Automatic data buffering until strategies are ready
- Optional data saving to CSV for analysis
- Starts trading once minimum data requirements met
- All 11 strategies with adaptive rebalancing
- Flexible ticker configuration via command-line

Usage:
    # Paper trading with sector ETFs
    python scripts/traders/live_adaptive_trader.py --tickers XLF XLI XLK XLE

    # Paper trading with crypto
    python scripts/traders/live_adaptive_trader.py --tickers BTC/USD ETH/USD SOL/USD

    # Mixed (auto-detects asset type)
    python scripts/traders/live_adaptive_trader.py --tickers AAPL MSFT BTC/USD ETH/USD

    # With data saving
    python scripts/traders/live_adaptive_trader.py --tickers XLF XLI --save-data

    # Live trading (CAREFUL!)
    python scripts/traders/live_adaptive_trader.py --tickers XLF XLI --live
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from AlpacaTrading.strategies.adaptive_portfolio import AdaptivePortfolioStrategy
from AlpacaTrading.strategies.base import TradingStrategy
from AlpacaTrading.strategies.bollinger_bands import BollingerBandsStrategy
from AlpacaTrading.strategies.cross_sectional_momentum import (
    CrossSectionalMomentumStrategy,
)
from AlpacaTrading.strategies.mean_reversion import MovingAverageCrossoverStrategy
from AlpacaTrading.strategies.momentum import MomentumStrategy
from AlpacaTrading.strategies.rsi_strategy import RSIStrategy
from AlpacaTrading.strategies.volume_breakout import VolumeBreakoutStrategy
from AlpacaTrading.strategies.vwap_strategy import VWAPStrategy
from AlpacaTrading.trading.live_trader import LiveTrader
from AlpacaTrading.trading.order_manager import RiskConfig

logger = logging.getLogger(__name__)


def detect_crypto_tickers(tickers: list[str]) -> bool:
    """Detect if tickers are crypto based on "/" character."""
    crypto_count = sum(1 for ticker in tickers if "/" in ticker)
    stock_count = len(tickers) - crypto_count

    if crypto_count > 0 and stock_count > 0:
        raise ValueError(
            f"Mixed asset types detected! Cannot mix stocks and crypto.\n"
            f"Crypto tickers (with '/'): {crypto_count}\n"
            f"Stock tickers (without '/'): {stock_count}"
        )

    return crypto_count > 0


def create_adaptive_strategy(
    tickers: list[str],
    position_size: int,
    max_position: int,
    rebalance_period: int,
    allocation_method: str,
) -> AdaptivePortfolioStrategy:
    """Create adaptive portfolio with all 11 strategies."""
    is_crypto = detect_crypto_tickers(tickers)

    # Adjust thresholds based on asset type
    if is_crypto:
        momentum_threshold_fast = 0.012
        momentum_threshold_slow = 0.008
        min_price_change = 0.012
        deviation_threshold = 0.008
        profit_target_aggressive = 2.0
        profit_target_conservative = 3.0
        stop_loss_aggressive = 1.0
        stop_loss_conservative = 1.5
        volume_multiplier = 2.5
    else:
        momentum_threshold_fast = 0.008
        momentum_threshold_slow = 0.005
        min_price_change = 0.008
        deviation_threshold = 0.005
        profit_target_aggressive = 1.5
        profit_target_conservative = 2.0
        stop_loss_aggressive = 0.75
        stop_loss_conservative = 1.0
        volume_multiplier = 2.0

    strategies: dict[str, TradingStrategy] = {
        "momentum_fast": MomentumStrategy(
            lookback_period=10,
            momentum_threshold=momentum_threshold_fast,
            position_size=position_size,
            max_position=max_position,
        ),
        "momentum_slow": MomentumStrategy(
            lookback_period=20,
            momentum_threshold=momentum_threshold_slow,
            position_size=position_size,
            max_position=max_position,
        ),
        "ma_cross_fast": MovingAverageCrossoverStrategy(
            short_window=5,
            long_window=15,
            position_size=position_size,
            max_position=max_position,
        ),
        "ma_cross_slow": MovingAverageCrossoverStrategy(
            short_window=10,
            long_window=30,
            position_size=position_size,
            max_position=max_position,
        ),
        "rsi_aggressive": RSIStrategy(
            rsi_period=14,
            oversold_threshold=25,
            overbought_threshold=75,
            position_size=position_size,
            max_position=max_position,
            profit_target=profit_target_aggressive,
            stop_loss=stop_loss_aggressive,
        ),
        "rsi_conservative": RSIStrategy(
            rsi_period=14,
            oversold_threshold=30,
            overbought_threshold=70,
            position_size=position_size,
            max_position=max_position,
            profit_target=profit_target_conservative,
            stop_loss=stop_loss_conservative,
        ),
        "bb_breakout": BollingerBandsStrategy(
            period=20,
            num_std_dev=2.0,
            mode="breakout",
            position_size=position_size,
            max_position=max_position,
        ),
        "bb_reversion": BollingerBandsStrategy(
            period=20,
            num_std_dev=2.5,
            mode="reversion",
            position_size=position_size,
            max_position=max_position,
        ),
        "volume_breakout": VolumeBreakoutStrategy(
            volume_period=20,
            volume_multiplier=volume_multiplier,
            price_momentum_period=5,
            min_price_change=min_price_change,
            position_size=position_size,
            max_position=max_position,
            hold_periods=30,
        ),
        "vwap": VWAPStrategy(
            deviation_threshold=deviation_threshold,
            position_size=position_size,
            max_position=max_position,
            reset_period=0,
            min_samples=20,
        ),
        "cross_sectional": CrossSectionalMomentumStrategy(
            lookback_period=20,
            rebalance_period=30,
            long_percentile=0.20,
            short_percentile=0.20,
            enable_shorting=True,
            position_size=position_size,
            max_position_per_stock=max_position,
            min_stocks=min(3, len(tickers)),
        ),
    }

    return AdaptivePortfolioStrategy(
        strategies=strategies,
        rebalance_period=rebalance_period,
        min_allocation=0.03,
        max_allocation=0.25,
        performance_lookback=rebalance_period,
        allocation_method=allocation_method,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Generic Live Adaptive Trader with Alpaca Streaming",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Paper trading with sector ETFs
  python scripts/traders/live_adaptive_trader.py --tickers XLF XLI XLK XLE

  # Paper trading with crypto
  python scripts/traders/live_adaptive_trader.py --tickers BTC/USD ETH/USD SOL/USD

  # With data saving
  python scripts/traders/live_adaptive_trader.py --tickers XLF XLI --save-data

  # Custom parameters
  python scripts/traders/live_adaptive_trader.py --tickers BTC/USD ETH/USD \\
      --rebalance-period 120 --allocation-method sharpe --min-warmup-bars 10

  # LIVE TRADING (use with caution!)
  python scripts/traders/live_adaptive_trader.py --tickers XLF XLI --live

Environment Variables Required:
  APCA_API_KEY_ID: Your Alpaca API key
  APCA_API_SECRET_KEY: Your Alpaca API secret

  Set these in .env file or export them:
    export APCA_API_KEY_ID="your_key"
    export APCA_API_SECRET_KEY="your_secret"

Note:
  - Crypto tickers must contain "/" (e.g., BTC/USD)
  - Stock tickers don't (e.g., AAPL)
  - Cannot mix stocks and crypto in same run
        """,
    )

    parser.add_argument(
        "--tickers",
        nargs="+",
        required=True,
        help="List of ticker symbols to trade (space-separated)",
    )
    parser.add_argument(
        "--live", action="store_true", help="Use LIVE trading (default: paper trading)"
    )
    parser.add_argument(
        "--initial-cash",
        type=float,
        default=10000,
        help="Initial capital (default: 10000)",
    )
    parser.add_argument(
        "--rebalance-period",
        type=int,
        default=60,
        help="Bars between rebalances (default: 60)",
    )
    parser.add_argument(
        "--allocation-method",
        type=str,
        default="pnl",
        choices=["pnl", "sharpe", "win_rate"],
        help="Allocation method (default: pnl)",
    )
    parser.add_argument(
        "--min-warmup-bars",
        type=int,
        default=30,
        help="Minimum bars before trading starts (default: 30)",
    )
    parser.add_argument(
        "--position-size",
        type=int,
        default=100,
        help="Default position size for strategies (default: 100)",
    )
    parser.add_argument(
        "--max-position",
        type=int,
        default=10,
        help="Max position per symbol for strategies (default: 10)",
    )
    parser.add_argument(
        "--save-data", action="store_true", help="Save streaming data to CSV"
    )
    parser.add_argument(
        "--data-file",
        type=str,
        default="logs/live_data.csv",
        help="File to save data (default: logs/live_data.csv)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING"],
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("logs/live_adaptive_trader.log"),
        ],
    )

    # Load environment variables
    load_dotenv()

    api_key = os.getenv("APCA_API_KEY_ID")
    api_secret = os.getenv("APCA_API_SECRET_KEY")

    if not api_key or not api_secret:
        print("ERROR: Alpaca API credentials not found!")
        print("Set APCA_API_KEY_ID and APCA_API_SECRET_KEY environment variables")
        print("Either in .env file or export them in your shell")
        sys.exit(1)

    # Warning for live trading
    if args.live:
        print("=" * 80)
        print("⚠️  WARNING: LIVE TRADING MODE ⚠️ ")
        print("=" * 80)
        print("You are about to trade with REAL MONEY!")
        print(f"Initial capital: ${args.initial_cash:,.2f}")
        print(f"Tickers: {', '.join(args.tickers)}")
        print("\nAre you sure you want to continue?")
        response = input("Type 'YES' to confirm: ")
        if response != "YES":
            print("Aborted.")
            sys.exit(0)
        print("=" * 80 + "\n")

    # Create adaptive strategy
    try:
        strategy = create_adaptive_strategy(
            tickers=args.tickers,
            position_size=args.position_size,
            max_position=args.max_position,
            rebalance_period=args.rebalance_period,
            allocation_method=args.allocation_method,
        )
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # Create risk config
    risk_config = RiskConfig(
        max_position_size=args.max_position * 2,
        max_position_value=1500,
        max_total_exposure=9000,
        max_orders_per_minute=50,
        max_orders_per_symbol_per_minute=10,
        min_cash_buffer=500,
    )

    # Create and run trader
    trader = LiveTrader(
        tickers=args.tickers,
        strategy=strategy,
        api_key=api_key,
        api_secret=api_secret,
        paper=not args.live,
        initial_cash=args.initial_cash,
        min_warmup_bars=args.min_warmup_bars,
        save_data=args.save_data,
        data_file=args.data_file,
        risk_config=risk_config,
    )

    # Run
    asyncio.run(trader.run())


if __name__ == "__main__":
    main()
