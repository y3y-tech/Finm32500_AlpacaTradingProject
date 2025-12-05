#!/usr/bin/env python3
"""
Adaptive Portfolio Trader - Dynamic Capital Allocation Across Multiple Strategies

This script runs an AdaptivePortfolioStrategy that dynamically allocates capital
between multiple sub-strategies based on their performance. Winners get more weight,
losers get less weight over time.

Perfect for comprehensive market coverage with adaptive rebalancing.

Usage:
    python scripts/traders/run_adaptive_portfolio.py
    python scripts/traders/run_adaptive_portfolio.py --initial-cash 100000
    python scripts/traders/run_adaptive_portfolio.py --live  # CAREFUL!
    python scripts/traders/run_adaptive_portfolio.py --rebalance-period 120
"""

import argparse
import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

from AlpacaTrading.logging_config import setup_logging
from AlpacaTrading.strategies.adaptive_portfolio import AdaptivePortfolioStrategy
from AlpacaTrading.strategies.base import TradingStrategy
from AlpacaTrading.strategies.bollinger_bands import BollingerBandsStrategy
from AlpacaTrading.strategies.donchian_breakout import DonchianBreakoutStrategy
from AlpacaTrading.strategies.keltner_channel import KeltnerChannelStrategy
from AlpacaTrading.strategies.macd_strategy import MACDStrategy
from AlpacaTrading.strategies.mean_reversion import MovingAverageCrossoverStrategy
from AlpacaTrading.strategies.momentum import MomentumStrategy
from AlpacaTrading.strategies.multi_indicator_reversion import (
    MultiIndicatorReversionStrategy,
)
from AlpacaTrading.strategies.rate_of_change import RateOfChangeStrategy
from AlpacaTrading.strategies.rsi_strategy import RSIStrategy
from AlpacaTrading.strategies.stochastic_strategy import StochasticStrategy
from AlpacaTrading.strategies.volume_breakout import VolumeBreakoutStrategy
from AlpacaTrading.strategies.vwap_strategy import VWAPStrategy
from AlpacaTrading.strategies.zscore_mean_reversion import (
    ZScoreMeanReversionStrategy,
)
from AlpacaTrading.trading.live_trader import LiveTrader
from AlpacaTrading.trading.order_manager import RiskConfig

logger = logging.getLogger(__name__)

# Comprehensive ticker list covering all major asset classes (NO CRYPTO)
DEFAULT_TICKERS = [
    # === CORE INDICES ===
    "SPY",  # S&P 500
    "QQQ",  # Nasdaq 100
    "IWM",  # Russell 2000
    "DIA",  # Dow Jones
    # === MEGA-CAP TECH ===
    "AAPL",  # Apple
    "MSFT",  # Microsoft
    "NVDA",  # NVIDIA
    "GOOGL",  # Alphabet
    "AMZN",  # Amazon
    "META",  # Meta
    "TSLA",  # Tesla
    # === SECTOR ETFS ===
    "XLF",  # Financials
    "XLK",  # Technology
    "XLE",  # Energy
    "XLV",  # Healthcare
    "XLI",  # Industrials
    "XLP",  # Consumer Staples
    "XLY",  # Consumer Discretionary
    # === BONDS ===
    "TLT",  # 20+ Year Treasury
    "IEF",  # 7-10 Year Treasury
    "LQD",  # Investment Grade Corporate
    # === COMMODITIES ===
    "GLD",  # Gold
    "SLV",  # Silver
    "USO",  # Oil
    # === INTERNATIONAL ===
    "EEM",  # Emerging Markets
    "VGK",  # European Stocks
]


def create_comprehensive_strategies(
    position_size: float, max_position: int
) -> dict[str, TradingStrategy]:
    """
    Create a comprehensive set of strategies for adaptive portfolio allocation.

    Returns a dict of {name: strategy} for use with AdaptivePortfolioStrategy.
    """
    return {
        # === MOMENTUM STRATEGIES (3) ===
        "momentum_fast": MomentumStrategy(
            lookback_period=10,
            momentum_threshold=0.008,
            position_size=position_size,
            max_position=max_position,
        ),
        "momentum_medium": MomentumStrategy(
            lookback_period=15,
            momentum_threshold=0.006,
            position_size=position_size,
            max_position=max_position,
        ),
        "momentum_slow": MomentumStrategy(
            lookback_period=25,
            momentum_threshold=0.004,
            position_size=position_size,
            max_position=max_position,
        ),
        # === MEAN REVERSION STRATEGIES (3) ===
        "ma_cross_fast": MovingAverageCrossoverStrategy(
            short_window=5,
            long_window=15,
            position_size=position_size,
            max_position=max_position,
        ),
        "ma_cross_medium": MovingAverageCrossoverStrategy(
            short_window=10,
            long_window=30,
            position_size=position_size,
            max_position=max_position,
        ),
        "ma_cross_slow": MovingAverageCrossoverStrategy(
            short_window=20,
            long_window=60,
            position_size=position_size,
            max_position=max_position,
        ),
        # === RSI STRATEGIES (2) ===
        "rsi_aggressive": RSIStrategy(
            rsi_period=14,
            oversold_threshold=25,
            overbought_threshold=75,
            position_size=position_size,
            max_position=max_position,
            profit_target=2.0,
            stop_loss=1.0,
        ),
        "rsi_conservative": RSIStrategy(
            rsi_period=14,
            oversold_threshold=30,
            overbought_threshold=70,
            position_size=position_size,
            max_position=max_position,
            profit_target=1.5,
            stop_loss=0.8,
        ),
        # === TREND FOLLOWING (3) ===
        "donchian": DonchianBreakoutStrategy(
            entry_period=20,
            exit_period=10,
            position_size=position_size,
            max_position=max_position,
        ),
        "macd_crossover": MACDStrategy(
            fast_period=12,
            slow_period=26,
            signal_period=9,
            signal_type="crossover",
            position_size=position_size,
            max_position=max_position,
        ),
        "roc": RateOfChangeStrategy(
            lookback_period=12,
            entry_threshold=1.0,
            exit_threshold=0.0,
            position_size=position_size,
            max_position=max_position,
            use_smoothing=True,
        ),
        # === VOLATILITY STRATEGIES (3) ===
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
        "keltner": KeltnerChannelStrategy(
            ema_period=20,
            atr_period=10,
            atr_multiplier=2.0,
            mode="breakout",
            position_size=position_size,
            max_position=max_position,
        ),
        # === ADVANCED REVERSION (2) ===
        "zscore": ZScoreMeanReversionStrategy(
            lookback_period=20,
            entry_threshold=2.0,
            exit_threshold=0.5,
            position_size=position_size,
            max_position=max_position,
            enable_shorting=False,
        ),
        "multi_indicator": MultiIndicatorReversionStrategy(
            lookback_period=20,
            rsi_period=14,
            entry_score=60,
            position_size=position_size,
            max_position=max_position,
        ),
        # === OTHER (3) ===
        "stochastic": StochasticStrategy(
            k_period=14,
            d_period=3,
            oversold_threshold=20,
            overbought_threshold=80,
            signal_type="crossover",
            position_size=position_size,
            max_position=max_position,
        ),
        "volume_breakout": VolumeBreakoutStrategy(
            volume_period=20,
            volume_multiplier=2.0,
            hold_periods=30,
            position_size=position_size,
            max_position=max_position,
            min_price_change=0.008,
        ),
        "vwap": VWAPStrategy(
            deviation_threshold=0.005,
            reset_period=0,
            position_size=position_size,
            max_position=max_position,
            min_samples=20,
        ),
    }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run adaptive portfolio with dynamic capital allocation"
    )
    parser.add_argument(
        "--initial-cash",
        type=float,
        default=80000.0,
        help="Initial trading capital (default: $80,000)",
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=DEFAULT_TICKERS,
        help="Tickers to trade (default: comprehensive list)",
    )
    parser.add_argument(
        "--min-warmup-bars",
        type=int,
        default=70,
        help="Minimum bars before trading (default: 70)",
    )
    parser.add_argument(
        "--rebalance-period",
        type=int,
        default=90,
        help="Bars between rebalances (default: 90 = ~1.5 hours at 1min)",
    )
    parser.add_argument(
        "--allocation-method",
        type=str,
        choices=["pnl", "sharpe", "win_rate"],
        default="sharpe",
        help="Method for allocating capital (default: sharpe)",
    )
    parser.add_argument(
        "--min-allocation",
        type=float,
        default=0.03,
        help="Minimum allocation per strategy (default: 0.03 = 3%%)",
    )
    parser.add_argument(
        "--max-allocation",
        type=float,
        default=0.15,
        help="Maximum allocation per strategy (default: 0.15 = 15%%)",
    )
    parser.add_argument(
        "--live", action="store_true", help="Use live trading (default: paper trading)"
    )
    parser.add_argument(
        "--save-data", action="store_true", help="Save market data to file"
    )
    parser.add_argument(
        "--data-file", type=str, help="Path to save market data (optional)"
    )
    parser.add_argument(
        "--no-close-on-exit",
        action="store_false",
        help="Do not liquidate all positions on exit (Ctrl-C)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()
    api_key = os.getenv("APCA_API_KEY_ID")
    api_secret = os.getenv("APCA_API_SECRET_KEY")

    if not api_key or not api_secret:
        logger.error(
            "Missing Alpaca API credentials. Set APCA_API_KEY_ID and APCA_API_SECRET_KEY."
        )
        sys.exit(1)

    # Setup logging
    log_level = getattr(logging, args.log_level)
    setup_logging(level=log_level)

    # Calculate position sizing
    position_size = args.initial_cash / 50  # ~$1,600 per position at $80k
    max_position = int(position_size / 100)  # ~16 shares max

    logger.info("=" * 80)
    logger.info("ADAPTIVE PORTFOLIO TRADER - DYNAMIC CAPITAL ALLOCATION")
    logger.info("=" * 80)
    logger.info(f"Initial Capital: ${args.initial_cash:,.2f}")
    logger.info(f"Tickers: {len(args.tickers)} total")
    logger.info("Sub-Strategies: 19 different strategies")
    logger.info(f"Rebalance Period: Every {args.rebalance_period} bars")
    logger.info(f"Allocation Method: {args.allocation_method}")
    logger.info(
        f"Min/Max Allocation: {args.min_allocation:.1%} / {args.max_allocation:.1%}"
    )
    logger.info(f"Position Size: ${position_size:,.0f} per trade")
    logger.info(f"Max Position: {max_position} shares")
    logger.info(f"Trading Mode: {'LIVE' if args.live else 'PAPER'}")
    logger.info("=" * 80)
    logger.info("")
    logger.info("🎯 ADAPTIVE ALLOCATION: Winners get more capital, losers get less!")
    logger.info("")

    # Create sub-strategies
    logger.info("Creating 19 sub-strategies...")
    strategies = create_comprehensive_strategies(position_size, max_position)
    logger.info(f"✓ Created {len(strategies)} strategies")

    # Create adaptive portfolio strategy
    logger.info("Creating adaptive portfolio meta-strategy...")
    adaptive_strategy = AdaptivePortfolioStrategy(
        strategies=strategies,
        rebalance_period=args.rebalance_period,
        min_allocation=args.min_allocation,
        max_allocation=args.max_allocation,
        performance_lookback=args.rebalance_period,
        allocation_method=args.allocation_method,
    )
    logger.info("✓ Adaptive portfolio created")

    # Create risk configuration
    risk_config = RiskConfig(
        max_position_size=args.initial_cash * 0.05,  # 5% max per position
        max_position_value=args.initial_cash * 0.15,  # 15% max position value
        max_total_exposure=args.initial_cash * 2.0,  # 200% max exposure
        max_orders_per_minute=50,
        max_orders_per_symbol_per_minute=10,
        min_cash_buffer=args.initial_cash * 0.10,  # Keep 10% in cash
    )

    # Create and run the LiveTrader
    logger.info("Initializing live trader...")
    trader = LiveTrader(
        api_key=api_key,
        api_secret=api_secret,
        tickers=args.tickers,
        strategy=adaptive_strategy,
        initial_cash=args.initial_cash,
        paper=not args.live,
        min_warmup_bars=args.min_warmup_bars,
        risk_config=risk_config,
        save_data=args.save_data,
        data_file=args.data_file
        if args.data_file is not None
        else "logs/adaptive_portfolio_data.csv",
        close_positions_on_shutdown=args.no_close_on_exit,
    )

    logger.info("✓ Trader initialized")
    logger.info("")
    logger.info("Starting adaptive portfolio trader...")
    logger.info("Press Ctrl-C to stop")
    logger.info("")

    # Run the trader
    try:
        asyncio.run(trader.run())
    except KeyboardInterrupt:
        logger.info("\nShutdown requested by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
