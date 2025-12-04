#!/usr/bin/env python3
"""
Live Trend-Following Trader

Uses trend-focused strategies:
- Donchian Breakout (Turtle Trading)
- MACD (crossover and zero-cross)
- Rate of Change (momentum)
- ADX Trend Filter
- Keltner Channels

Best for: Trending assets like commodities, currencies, EM ETFs

Usage:
    python scripts/traders/live_trend_trader.py
    python scripts/traders/live_trend_trader.py --tickers USO UNG GLD SLV
    python scripts/traders/live_trend_trader.py --save-data
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
from AlpacaTrading.strategies.adx_trend import ADXTrendStrategy
from AlpacaTrading.strategies.base import TradingStrategy
from AlpacaTrading.strategies.donchian_breakout import DonchianBreakoutStrategy
from AlpacaTrading.strategies.keltner_channel import KeltnerChannelStrategy
from AlpacaTrading.strategies.macd_strategy import MACDStrategy
from AlpacaTrading.strategies.rate_of_change import RateOfChangeStrategy
from AlpacaTrading.trading.live_trader import LiveTrader
from AlpacaTrading.trading.order_manager import RiskConfig

# Commodity-focused tickers good for trend following
DEFAULT_TICKERS = [
    "USO",  # Oil
    "UNG",  # Natural Gas
    "GLD",  # Gold
    "SLV",  # Silver
    "DBA",  # Agriculture
    "DBB",  # Base Metals
]


def create_trend_strategies(
    position_size: float, max_position: int
) -> dict[str, TradingStrategy]:
    """Create trend-focused strategies."""
    return {
        "donchian_fast": DonchianBreakoutStrategy(
            entry_period=15,
            exit_period=7,
            position_size=position_size,
            max_position=max_position,
        ),
        "donchian_slow": DonchianBreakoutStrategy(
            entry_period=25,
            exit_period=12,
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
        "macd_zero": MACDStrategy(
            fast_period=12,
            slow_period=26,
            signal_period=9,
            signal_type="zero_cross",
            position_size=position_size,
            max_position=max_position,
        ),
        "roc_fast": RateOfChangeStrategy(
            lookback_period=10,
            entry_threshold=1.5,
            exit_threshold=0.0,
            position_size=position_size,
            max_position=max_position,
            use_smoothing=True,
        ),
        "roc_slow": RateOfChangeStrategy(
            lookback_period=20,
            entry_threshold=2.5,
            exit_threshold=0.5,
            position_size=position_size,
            max_position=max_position,
            use_smoothing=True,
        ),
        "adx_trend": ADXTrendStrategy(
            adx_period=14,
            adx_threshold=20,
            di_threshold=5,
            position_size=position_size,
            max_position=max_position,
        ),
        "keltner_breakout": KeltnerChannelStrategy(
            ema_period=20,
            atr_period=10,
            atr_multiplier=2.0,
            mode="breakout",
            position_size=position_size,
            max_position=max_position,
        ),
    }


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Live Trend-Following Trader")
    parser.add_argument("--tickers", nargs="+", default=DEFAULT_TICKERS)
    parser.add_argument(
        "--live", action="store_true", help="Use live trading (default: paper)"
    )
    parser.add_argument("--initial-cash", type=float, default=4000)
    parser.add_argument("--rebalance-period", type=int, default=60)
    parser.add_argument(
        "--allocation-method", default="pnl", choices=["pnl", "sharpe", "win_rate"]
    )
    parser.add_argument("--min-warmup-bars", type=int, default=45)
    parser.add_argument("--position-size", type=float, default=800)
    parser.add_argument("--max-position", type=int, default=15)
    parser.add_argument("--save-data", action="store_true")
    parser.add_argument("--data-file", default="logs/live_trend_data.csv")
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING"],
        help="Logging level (default: INFO)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("logs/live_trend_trader.log"),
        ],
    )

    api_key = os.getenv("APCA_API_KEY_ID")
    api_secret = os.getenv("APCA_API_SECRET_KEY")

    if not api_key or not api_secret:
        print("ERROR: Missing Alpaca API credentials")
        sys.exit(1)

    # Create strategies and adaptive portfolio
    strategies = create_trend_strategies(args.position_size, args.max_position)
    adaptive = AdaptivePortfolioStrategy(
        strategies=strategies,
        rebalance_period=args.rebalance_period,
        min_allocation=0.05,
        max_allocation=0.25,
        performance_lookback=args.rebalance_period,
        allocation_method=args.allocation_method,
    )

    # Create risk config
    risk_config = RiskConfig(
        max_position_size=args.max_position * 2,
        max_position_value=args.initial_cash * 0.15,
        max_total_exposure=args.initial_cash * 0.8,
        max_orders_per_minute=30,
        max_orders_per_symbol_per_minute=8,
        min_cash_buffer=args.initial_cash * 0.1,
    )

    # Create and run trader
    trader = LiveTrader(
        tickers=args.tickers,
        strategy=adaptive,
        api_key=api_key,
        api_secret=api_secret,
        paper=not args.live,
        initial_cash=args.initial_cash,
        min_warmup_bars=args.min_warmup_bars,
        save_data=args.save_data,
        data_file=args.data_file,
        risk_config=risk_config,
    )

    asyncio.run(trader.run())


if __name__ == "__main__":
    main()
