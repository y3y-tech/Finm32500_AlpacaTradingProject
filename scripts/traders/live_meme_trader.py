#!/usr/bin/env python3
"""
Live Meme Stock Trader

Trades high-volatility "meme" stocks using momentum and breakout strategies.
These stocks have extreme volatility and are heavily sentiment-driven.

WARNING: These stocks are VERY volatile. Use small position sizes!

Tickers: GME, AMC, PLTR, RIVN, LCID, SOFI, HOOD

Usage:
    python scripts/traders/live_meme_trader.py
    python scripts/traders/live_meme_trader.py --tickers GME AMC PLTR
    python scripts/traders/live_meme_trader.py --save-data
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
from AlpacaTrading.strategies.bollinger_bands import BollingerBandsStrategy
from AlpacaTrading.strategies.donchian_breakout import DonchianBreakoutStrategy
from AlpacaTrading.strategies.keltner_channel import KeltnerChannelStrategy
from AlpacaTrading.strategies.macd_strategy import MACDStrategy
from AlpacaTrading.strategies.momentum import MomentumStrategy
from AlpacaTrading.strategies.rate_of_change import RateOfChangeStrategy
from AlpacaTrading.strategies.volume_breakout import VolumeBreakoutStrategy
from AlpacaTrading.trading.live_trader import LiveTrader
from AlpacaTrading.trading.order_manager import RiskConfig

# Meme / high-volatility stocks
DEFAULT_TICKERS = [
    "GME",  # GameStop
    "AMC",  # AMC Entertainment
    "PLTR",  # Palantir
    "RIVN",  # Rivian
    "LCID",  # Lucid Motors
    "SOFI",  # SoFi Technologies
    "HOOD",  # Robinhood
]


def create_meme_strategies(
    position_size: float, max_position: int
) -> dict[str, TradingStrategy]:
    """Create momentum and breakout strategies for extreme volatility."""
    return {
        # Donchian for catching big moves
        "donchian_fast": DonchianBreakoutStrategy(
            entry_period=10,
            exit_period=5,
            position_size=position_size,
            max_position=max_position,
        ),
        "donchian_slow": DonchianBreakoutStrategy(
            entry_period=15,
            exit_period=8,
            position_size=position_size,
            max_position=max_position,
        ),
        # Momentum for trend-following
        "momentum_fast": MomentumStrategy(
            lookback_period=5,
            momentum_threshold=0.03,  # 3% for memes
            position_size=position_size,
            max_position=max_position,
        ),
        "momentum_med": MomentumStrategy(
            lookback_period=10,
            momentum_threshold=0.025,
            position_size=position_size,
            max_position=max_position,
        ),
        # ROC for momentum bursts
        "roc_fast": RateOfChangeStrategy(
            lookback_period=5,
            entry_threshold=5.0,  # 5% for memes!
            exit_threshold=0.0,
            position_size=position_size,
            max_position=max_position,
            use_smoothing=False,  # Raw for fast reaction
        ),
        "roc_smoothed": RateOfChangeStrategy(
            lookback_period=10,
            entry_threshold=4.0,
            exit_threshold=1.0,
            position_size=position_size,
            max_position=max_position,
            use_smoothing=True,
        ),
        # MACD histogram for quick signals
        "macd": MACDStrategy(
            fast_period=8,  # Faster for memes
            slow_period=17,
            signal_period=6,
            signal_type="histogram",
            position_size=position_size,
            max_position=max_position,
        ),
        # ADX for filtering weak trends
        "adx": ADXTrendStrategy(
            adx_period=10,
            adx_threshold=25,  # Only trade strong trends
            di_threshold=8,
            position_size=position_size,
            max_position=max_position,
        ),
        # Keltner breakout (wide bands)
        "keltner": KeltnerChannelStrategy(
            ema_period=15,
            atr_period=10,
            atr_multiplier=3.0,  # Very wide for memes
            mode="breakout",
            position_size=position_size,
            max_position=max_position,
        ),
        # Bollinger breakout
        "bb_breakout": BollingerBandsStrategy(
            period=15,
            num_std_dev=2.5,
            mode="breakout",
            position_size=position_size,
            max_position=max_position,
        ),
        # Volume breakout (critical for memes)
        "volume_fast": VolumeBreakoutStrategy(
            volume_period=15,
            volume_multiplier=3.0,  # 3x volume for memes
            price_momentum_period=3,
            min_price_change=0.03,  # 3% move
            position_size=position_size,
            max_position=max_position,
            hold_periods=10,
        ),
        "volume_slow": VolumeBreakoutStrategy(
            volume_period=20,
            volume_multiplier=2.5,
            price_momentum_period=5,
            min_price_change=0.025,
            position_size=position_size,
            max_position=max_position,
            hold_periods=20,
        ),
    }


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Live Meme Stock Trader")
    parser.add_argument("--tickers", nargs="+", default=DEFAULT_TICKERS)
    parser.add_argument("--live", action="store_true")
    parser.add_argument(
        "--initial-cash", type=float, default=5000
    )  # Smaller for high risk
    parser.add_argument("--rebalance-period", type=int, default=30)  # Fast rebalancing
    parser.add_argument(
        "--allocation-method", default="pnl", choices=["pnl", "sharpe", "win_rate"]
    )
    parser.add_argument("--min-warmup-bars", type=int, default=25)
    parser.add_argument("--position-size", type=float, default=400)  # SMALL positions
    parser.add_argument("--max-position", type=int, default=50)
    parser.add_argument("--save-data", action="store_true")
    parser.add_argument("--data-file", default="logs/live_meme_data.csv")
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
            logging.FileHandler("logs/live_meme_trader.log"),
        ],
    )

    api_key = os.getenv("APCA_API_KEY_ID")
    api_secret = os.getenv("APCA_API_SECRET_KEY")

    if not api_key or not api_secret:
        print("ERROR: Missing Alpaca API credentials")
        sys.exit(1)

    # Create strategies and adaptive portfolio
    strategies = create_meme_strategies(args.position_size, args.max_position)
    adaptive = AdaptivePortfolioStrategy(
        strategies=strategies,
        rebalance_period=args.rebalance_period,
        min_allocation=0.04,
        max_allocation=0.20,
        performance_lookback=args.rebalance_period,
        allocation_method=args.allocation_method,
    )

    # Create risk config
    risk_config = RiskConfig(
        max_position_size=args.max_position,
        max_position_value=args.initial_cash * 0.12,  # Small per position
        max_total_exposure=args.initial_cash * 0.7,  # Keep cash buffer
        max_orders_per_minute=50,  # Fast trading
        max_orders_per_symbol_per_minute=10,
        min_cash_buffer=args.initial_cash * 0.2,  # 20% cash buffer
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
