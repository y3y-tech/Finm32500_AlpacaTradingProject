#!/usr/bin/env python3
"""
Crypto Adaptive Multi-Trader - Run 19+ strategies on all crypto tickers.

This script runs a comprehensive set of trading strategies on cryptocurrency pairs
using the multi-trader framework. Each strategy operates independently with its own
capital allocation and risk management.

Features:
- 19 different trading strategies (momentum, mean reversion, volatility, etc.)
- All major crypto pairs (BTC, ETH, SOL, AVAX, LINK, MATIC, DOT, UNI)
- Shared Alpaca WebSocket connection (no connection limit issues)
- Independent risk management per strategy
- Real-time performance tracking

Usage:
    python scripts/traders/run_crypto_adaptive_multi.py
    python scripts/traders/run_crypto_adaptive_multi.py --live  # CAREFUL - Live trading!
    python scripts/traders/run_crypto_adaptive_multi.py --config configs/crypto_adaptive_multi_trader.json
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from AlpacaTrading.logging_config import setup_logging
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

logger = logging.getLogger(__name__)


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


def parse_strategy_configs(
    config_list: list, min_warmup_override: int | None = None
) -> list:
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
        # Use override if provided, otherwise use config value
        warmup_bars = (
            min_warmup_override
            if min_warmup_override is not None
            else config.get("min_warmup_bars", 50)
        )

        strategies.append(
            {
                "name": config["name"],
                "strategy": strategy,
                "tickers": config["tickers"],
                "initial_cash": config.get("initial_cash", 2000.0),
                "min_warmup_bars": warmup_bars,
                "risk_config": risk_config,
            }
        )

    return strategies


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run comprehensive crypto trading with 19+ strategies"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/crypto_adaptive_multi_trader.json",
        help="Path to JSON configuration file (default: crypto_adaptive_multi_trader.json)",
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
        default="logs/crypto_adaptive_multi_data.csv",
        help="Path to save market data",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )
    parser.add_argument(
        "--min-warmup-bars",
        type=int,
        default=None,
        help="Override minimum warmup bars for all strategies",
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

    # Load strategy configurations
    config_path = Path(args.config)
    if not config_path.exists():
        logger.error(f"Config file not found: {args.config}")
        sys.exit(1)

    logger.info(f"Loading strategies from config: {args.config}")
    config_list = load_config_file(args.config)
    strategies = parse_strategy_configs(config_list, args.min_warmup_bars)

    if args.min_warmup_bars is not None:
        logger.info(f"Overriding all warmup bars to: {args.min_warmup_bars}")

    # Print configuration summary
    logger.info("\n" + "=" * 80)
    logger.info("CRYPTO ADAPTIVE MULTI-TRADER - COMPREHENSIVE STRATEGY DEPLOYMENT")
    logger.info("=" * 80)
    logger.info(f"Trading Mode: {'LIVE' if args.live else 'PAPER'}")
    logger.info(f"Number of Strategies: {len(strategies)}")
    logger.info(
        f"Total Initial Capital: ${sum(s['initial_cash'] for s in strategies):,.2f}"
    )

    # Count unique tickers
    all_tickers = set()
    for s in strategies:
        all_tickers.update(s["tickers"])
    logger.info(f"Total Unique Crypto Pairs: {len(all_tickers)}")
    logger.info(f"Trading: {', '.join(sorted(all_tickers))}")

    # Strategy breakdown
    logger.info("\nStrategy Categories:")
    strategy_types = {}
    for config in config_list:
        st = config["strategy_type"]
        strategy_types[st] = strategy_types.get(st, 0) + 1

    for st, count in sorted(strategy_types.items()):
        logger.info(f"  {st}: {count} instance(s)")

    logger.info("=" * 80)
    logger.info("")
    logger.info("Each strategy operates independently with its own:")
    logger.info("  - Capital allocation ($6,000 per strategy)")
    logger.info("  - Risk management (max daily loss, max trades)")
    logger.info("  - Position sizing and warmup period")
    logger.info("")
    logger.info("All strategies share a single Alpaca WebSocket connection!")
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
        logger.info("Starting Crypto Adaptive Multi-Trader...")
        logger.info("Press Ctrl-C to stop and view summary")
        logger.info("")
        asyncio.run(coordinator.run())
    except KeyboardInterrupt:
        logger.info("\nShutdown requested by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
