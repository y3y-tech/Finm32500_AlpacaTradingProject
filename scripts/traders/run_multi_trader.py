#!/usr/bin/env python3
"""
Multi-Trader Launcher - Run multiple strategies with shared Alpaca connection.

This script demonstrates how to run multiple trading strategies simultaneously
while sharing a single Alpaca WebSocket connection, bypassing the 2-connection limit.

Usage:
    python scripts/traders/run_multi_trader.py --config configs/multi_trader_config.json
    python scripts/traders/run_multi_trader.py --live  # Use live trading
"""

import argparse
import asyncio
import json
import logging
import os
import sys

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
from AlpacaTrading.trading.multi_trader_coordinator import (
    MultiTraderCoordinator,
    RiskConfig,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_api_credentials():
    """Load API credentials from environment."""
    api_key = os.getenv("APCA_API_KEY_ID")
    api_secret = os.getenv("APCA_API_SECRET_KEY")

    if not api_key or not api_secret:
        logger.error(
            "Missing Alpaca API credentials. Set APCA_API_KEY_ID and APCA_API_SECRET_KEY."
        )
        sys.exit(1)

    return api_key, api_secret


def create_strategy(strategy_type: str, **params):
    """Factory function to create strategy instances."""
    strategies = {
        "mean_reversion": MovingAverageCrossoverStrategy,
        "momentum": MomentumStrategy,
        "rsi": RSIStrategy,
        "bollinger_bands": BollingerBandsStrategy,
        "donchian_breakout": DonchianBreakoutStrategy,
        "keltner_channel": KeltnerChannelStrategy,
        "macd": MACDStrategy,
        "rate_of_change": RateOfChangeStrategy,
        "stochastic": StochasticStrategy,
        "volume_breakout": VolumeBreakoutStrategy,
        "vwap": VWAPStrategy,
        "zscore_mean_reversion": ZScoreMeanReversionStrategy,
        "multi_indicator_reversion": MultiIndicatorReversionStrategy,
    }

    strategy_class = strategies.get(strategy_type.lower())
    if not strategy_class:
        raise ValueError(f"Unknown strategy type: {strategy_type}")

    return strategy_class(**params)


def load_config_file(config_path: str) -> list:
    """Load strategy configurations from JSON file."""
    with open(config_path, "r") as f:
        config = json.load(f)
    return config.get("strategies", [])


def create_default_strategies() -> list:
    """Create a default set of strategies for demonstration."""
    return [
        {
            "name": "SPY_MeanReversion",
            "strategy_type": "mean_reversion",
            "strategy_params": {
                "short_window": 10,
                "long_window": 30,
            },
            "tickers": ["SPY"],
            "initial_cash": 10000.0,
            "min_warmup_bars": 50,
            "risk_config": {
                "max_position_size": 0.95,
                "max_daily_trades": 10,
                "max_daily_loss": 500.0,
            },
        },
        {
            "name": "QQQ_Momentum",
            "strategy_type": "momentum",
            "strategy_params": {"lookback_period": 20, "momentum_threshold": 0.02},
            "tickers": ["QQQ"],
            "initial_cash": 10000.0,
            "min_warmup_bars": 30,
            "risk_config": {
                "max_position_size": 0.9,
                "max_daily_trades": 8,
                "max_daily_loss": 500.0,
            },
        },
        {
            "name": "IWM_RSI",
            "strategy_type": "rsi",
            "strategy_params": {
                "rsi_period": 14,
                "rsi_overbought": 70,
                "rsi_oversold": 30,
            },
            "tickers": ["IWM"],
            "initial_cash": 10000.0,
            "min_warmup_bars": 20,
            "risk_config": {
                "max_position_size": 0.9,
                "max_daily_trades": 10,
            },
        },
        {
            "name": "Tech_Basket",
            "strategy_type": "mean_reversion",
            "strategy_params": {
                "short_window": 5,
                "long_window": 20,
            },
            "tickers": ["AAPL", "MSFT", "GOOGL", "AMZN"],
            "initial_cash": 20000.0,
            "min_warmup_bars": 30,
            "risk_config": {
                "max_position_size": 0.2,  # 20% per ticker
                "max_daily_trades": 20,
                "max_daily_loss": 1000.0,
            },
        },
        {
            "name": "Crypto_BTC",
            "strategy_type": "mean_reversion",
            "strategy_params": {
                "short_window": 15,
                "long_window": 50,
            },
            "tickers": ["BTC/USD"],
            "initial_cash": 10000.0,
            "min_warmup_bars": 60,
            "risk_config": {
                "max_position_size": 0.8,
                "max_daily_trades": 5,
                "max_daily_loss": 800.0,
            },
        },
    ]


def parse_strategy_configs(config_list: list) -> list:
    """Parse strategy configurations and create strategy instances."""
    strategies = []

    for config in config_list:
        # Create strategy instance
        strategy = create_strategy(
            config["strategy_type"], **config.get("strategy_params", {})
        )

        # Create risk config
        risk_params = config.get("risk_config", {})
        risk_config = RiskConfig(
            max_position_size=risk_params.get("max_position_size"),
            max_daily_loss=risk_params.get("max_daily_loss"),
            max_daily_trades=risk_params.get("max_daily_trades"),
            stop_loss_pct=risk_params.get("stop_loss_pct"),
            take_profit_pct=risk_params.get("take_profit_pct"),
        )

        # Build strategy config for coordinator
        strategies.append(
            {
                "name": config["name"],
                "strategy": strategy,
                "tickers": config["tickers"],
                "initial_cash": config.get("initial_cash", 10000.0),
                "min_warmup_bars": config.get("min_warmup_bars", 50),
                "risk_config": risk_config,
            }
        )

    return strategies


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run multiple trading strategies with shared connection"
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to JSON configuration file (uses default strategies if not provided)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use live trading (default: paper trading)",
    )
    parser.add_argument(
        "--save-data",
        action="store_true",
        help="Save market data to file",
    )
    parser.add_argument(
        "--data-file",
        type=str,
        help="Path to save market data",
    )

    args = parser.parse_args()

    # Load API credentials
    api_key, api_secret = load_api_credentials()

    # Load strategy configurations
    if args.config:
        logger.info(f"Loading strategies from config: {args.config}")
        config_list = load_config_file(args.config)
    else:
        logger.info("Using default strategy configurations")
        config_list = create_default_strategies()

    strategies = parse_strategy_configs(config_list)

    # Print configuration summary
    logger.info("\n" + "=" * 80)
    logger.info("MULTI-TRADER CONFIGURATION")
    logger.info("=" * 80)
    logger.info(f"Trading Mode: {'LIVE' if not args.live else 'PAPER'}")
    logger.info(f"Number of Strategies: {len(strategies)}")
    logger.info(
        f"Total Initial Capital: ${sum(s['initial_cash'] for s in strategies):,.2f}"
    )

    # Count unique tickers
    all_tickers = set()
    for s in strategies:
        all_tickers.update(s["tickers"])
    logger.info(f"Total Unique Tickers: {len(all_tickers)}")
    logger.info(f"Tickers: {', '.join(sorted(all_tickers))}")
    logger.info("=" * 80 + "\n")

    # Create and run coordinator
    coordinator = MultiTraderCoordinator(
        strategies=strategies,
        api_key=api_key,
        api_secret=api_secret,
        paper=not args.live,
        save_data=args.save_data,
        data_file=args.data_file,
    )

    # Run the coordinator
    try:
        asyncio.run(coordinator.run())
    except KeyboardInterrupt:
        logger.info("\nShutdown requested by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
