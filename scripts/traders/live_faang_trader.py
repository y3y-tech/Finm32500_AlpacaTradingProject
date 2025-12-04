#!/usr/bin/env python3
"""
Live FAANG+ Tech Giant Trader

Trades high-volume tech stocks with a mix of momentum and reversion strategies.
These stocks have high liquidity and volatility, suitable for active trading.

Tickers: META, AAPL, AMZN, NVDA, GOOGL, MSFT, TSLA

Usage:
    python scripts/traders/live_faang_trader.py
    python scripts/traders/live_faang_trader.py --tickers AAPL NVDA TSLA
    python scripts/traders/live_faang_trader.py --save-data
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
from AlpacaTrading.strategies.keltner_channel import KeltnerChannelStrategy
from AlpacaTrading.strategies.macd_strategy import MACDStrategy
from AlpacaTrading.strategies.momentum import MomentumStrategy
from AlpacaTrading.strategies.rate_of_change import RateOfChangeStrategy
from AlpacaTrading.strategies.rsi_strategy import RSIStrategy
from AlpacaTrading.strategies.stochastic_strategy import StochasticStrategy
from AlpacaTrading.strategies.volume_breakout import VolumeBreakoutStrategy
from AlpacaTrading.trading.live_trader import LiveTrader
from AlpacaTrading.trading.order_manager import RiskConfig

# FAANG+ mega-cap tech stocks
DEFAULT_TICKERS = [
    "META",  # Meta (Facebook)
    "AAPL",  # Apple
    "AMZN",  # Amazon
    "NVDA",  # NVIDIA
    "GOOGL",  # Alphabet
    "MSFT",  # Microsoft
    "TSLA",  # Tesla
]


def create_faang_strategies(
    position_size: float, max_position: int
) -> dict[str, TradingStrategy]:
    """Create mixed momentum + reversion strategies for volatile stocks."""
    return {
        # Momentum for trends
        "momentum_fast": MomentumStrategy(
            lookback_period=8,
            momentum_threshold=0.012,  # 1.2% for volatile stocks
            position_size=position_size,
            max_position=max_position,
        ),
        "momentum_slow": MomentumStrategy(
            lookback_period=15,
            momentum_threshold=0.008,
            position_size=position_size,
            max_position=max_position,
        ),
        # MACD for trend confirmation
        "macd": MACDStrategy(
            fast_period=12,
            slow_period=26,
            signal_period=9,
            signal_type="crossover",
            position_size=position_size,
            max_position=max_position,
        ),
        # ROC for momentum bursts
        "roc": RateOfChangeStrategy(
            lookback_period=10,
            entry_threshold=2.0,
            exit_threshold=0.0,
            position_size=position_size,
            max_position=max_position,
            use_smoothing=True,
        ),
        # Keltner for breakouts
        "keltner": KeltnerChannelStrategy(
            ema_period=20,
            atr_period=10,
            atr_multiplier=2.5,  # Wider for volatile stocks
            mode="breakout",
            position_size=position_size,
            max_position=max_position,
        ),
        # RSI for reversions
        "rsi": RSIStrategy(
            rsi_period=14,
            oversold_threshold=28,
            overbought_threshold=72,
            position_size=position_size,
            max_position=max_position,
            profit_target=2.5,
            stop_loss=1.2,
        ),
        # Stochastic for oversold bounces
        "stochastic": StochasticStrategy(
            k_period=14,
            d_period=3,
            oversold_threshold=18,
            overbought_threshold=82,
            signal_type="crossover",
            position_size=position_size,
            max_position=max_position,
        ),
        # Bollinger breakout
        "bb_breakout": BollingerBandsStrategy(
            period=20,
            num_std_dev=2.0,
            mode="breakout",
            position_size=position_size,
            max_position=max_position,
        ),
        # Volume breakout for news/earnings
        "volume": VolumeBreakoutStrategy(
            volume_period=20,
            volume_multiplier=2.5,
            price_momentum_period=5,
            min_price_change=0.015,  # 1.5% move
            position_size=position_size,
            max_position=max_position,
            hold_periods=20,
        ),
    }


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Live FAANG+ Trader")
    parser.add_argument("--tickers", nargs="+", default=DEFAULT_TICKERS)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--initial-cash", type=float, default=15000)
    parser.add_argument("--rebalance-period", type=int, default=45)
    parser.add_argument(
        "--allocation-method", default="pnl", choices=["pnl", "sharpe", "win_rate"]
    )
    parser.add_argument("--min-warmup-bars", type=int, default=40)
    parser.add_argument("--position-size", type=float, default=1500)
    parser.add_argument(
        "--max-position", type=int, default=10
    )  # Lower due to high prices
    parser.add_argument("--save-data", action="store_true")
    parser.add_argument("--data-file", default="logs/live_faang_data.csv")
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
            logging.FileHandler("logs/live_faang_trader.log"),
        ],
    )

    api_key = os.getenv("APCA_API_KEY_ID")
    api_secret = os.getenv("APCA_API_SECRET_KEY")

    if not api_key or not api_secret:
        print("ERROR: Missing Alpaca API credentials")
        sys.exit(1)

    # Create strategies and adaptive portfolio
    strategies = create_faang_strategies(args.position_size, args.max_position)
    adaptive = AdaptivePortfolioStrategy(
        strategies=strategies,
        rebalance_period=args.rebalance_period,
        min_allocation=0.05,
        max_allocation=0.20,
        performance_lookback=args.rebalance_period,
        allocation_method=args.allocation_method,
    )

    # Create risk config
    risk_config = RiskConfig(
        max_position_size=args.max_position * 2,
        max_position_value=args.initial_cash * 0.18,
        max_total_exposure=args.initial_cash * 0.85,
        max_orders_per_minute=40,
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
