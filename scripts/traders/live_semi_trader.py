#!/usr/bin/env python3
"""
Live Semiconductor Trader

Trades semiconductor stocks - high volatility, strong trends, news-driven.
Mix of trend-following and momentum strategies suited for this volatile sector.

Tickers: NVDA, AMD, INTC, AVGO, QCOM, MU, MRVL, TSM

Usage:
    python scripts/traders/live_semi_trader.py
    python scripts/traders/live_semi_trader.py --tickers NVDA AMD TSM
    python scripts/traders/live_semi_trader.py --save-data
"""

import sys
from pathlib import Path

from AlpacaTrading.strategies.base import TradingStrategy

sys.path.insert(0, str(Path(__file__).parent))

# Semiconductor stocks
DEFAULT_TICKERS = [
    "NVDA",  # NVIDIA - AI leader
    "AMD",  # AMD
    "INTC",  # Intel
    "AVGO",  # Broadcom
    "QCOM",  # Qualcomm
    "MU",  # Micron
    "MRVL",  # Marvell
    "TSM",  # Taiwan Semiconductor (ADR)
]


def main():
    import argparse
    import logging
    import os
    from collections import defaultdict

    import pandas as pd
    from alpaca.data.live import StockDataStream
    from alpaca.trading.client import TradingClient
    from alpaca.trading.enums import OrderSide as AlpacaOrderSide
    from alpaca.trading.enums import TimeInForce
    from alpaca.trading.requests import MarketOrderRequest
    from dotenv import load_dotenv

    from AlpacaTrading.models import MarketDataPoint, OrderSide
    from AlpacaTrading.strategies.adaptive_portfolio import AdaptivePortfolioStrategy
    from AlpacaTrading.strategies.adx_trend import ADXTrendStrategy
    from AlpacaTrading.strategies.bollinger_bands import BollingerBandsStrategy
    from AlpacaTrading.strategies.cross_sectional_momentum import (
        CrossSectionalMomentumStrategy,
    )
    from AlpacaTrading.strategies.donchian_breakout import DonchianBreakoutStrategy
    from AlpacaTrading.strategies.keltner_channel import KeltnerChannelStrategy
    from AlpacaTrading.strategies.macd_strategy import MACDStrategy
    from AlpacaTrading.strategies.momentum import MomentumStrategy
    from AlpacaTrading.strategies.rate_of_change import RateOfChangeStrategy
    from AlpacaTrading.strategies.volume_breakout import VolumeBreakoutStrategy
    from AlpacaTrading.trading.order_manager import OrderManager, RiskConfig
    from AlpacaTrading.trading.portfolio import TradingPortfolio

    load_dotenv()

    parser = argparse.ArgumentParser(description="Live Semiconductor Trader")
    parser.add_argument("--tickers", nargs="+", default=DEFAULT_TICKERS)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--initial-cash", type=float, default=12000)
    parser.add_argument("--rebalance-period", type=int, default=40)
    parser.add_argument(
        "--allocation-method", default="pnl", choices=["pnl", "sharpe", "win_rate"]
    )
    parser.add_argument("--min-warmup-bars", type=int, default=35)
    parser.add_argument("--position-size", type=float, default=1000)
    parser.add_argument("--max-position", type=int, default=12)
    parser.add_argument("--save-data", action="store_true")
    parser.add_argument("--data-file", default="logs/live_semi_data.csv")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("logs/live_semi_trader.log"),
        ],
    )
    logger = logging.getLogger(__name__)

    api_key = os.getenv("APCA_API_KEY_ID")
    api_secret = os.getenv("APCA_API_SECRET_KEY")

    if not api_key or not api_secret:
        print("ERROR: Missing Alpaca API credentials")
        sys.exit(1)

    # Trend + momentum strategies for volatile sector
    def create_strategies(
        position_size: float, max_position: int, num_tickers: int
    ) -> dict[str, TradingStrategy]:
        return {
            # Donchian for strong trends
            "donchian_fast": DonchianBreakoutStrategy(
                entry_period=12,
                exit_period=6,
                position_size=position_size,
                max_position=max_position,
            ),
            "donchian_slow": DonchianBreakoutStrategy(
                entry_period=20,
                exit_period=10,
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
            "roc_fast": RateOfChangeStrategy(
                lookback_period=8,
                entry_threshold=2.5,  # Higher for semis
                exit_threshold=0.0,
                position_size=position_size,
                max_position=max_position,
                use_smoothing=True,
            ),
            "roc_slow": RateOfChangeStrategy(
                lookback_period=15,
                entry_threshold=3.5,
                exit_threshold=1.0,
                position_size=position_size,
                max_position=max_position,
            ),
            # ADX trend filter
            "adx": ADXTrendStrategy(
                adx_period=14,
                adx_threshold=22,
                di_threshold=5,
                position_size=position_size,
                max_position=max_position,
            ),
            # Keltner for breakouts
            "keltner": KeltnerChannelStrategy(
                ema_period=20,
                atr_period=10,
                atr_multiplier=2.5,  # Wider for volatile semis
                mode="breakout",
                position_size=position_size,
                max_position=max_position,
            ),
            # Momentum
            "momentum_fast": MomentumStrategy(
                lookback_period=8,
                momentum_threshold=0.015,  # 1.5% for volatile stocks
                position_size=position_size,
                max_position=max_position,
            ),
            "momentum_slow": MomentumStrategy(
                lookback_period=18,
                momentum_threshold=0.01,
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
            # Volume breakout for news
            "volume": VolumeBreakoutStrategy(
                volume_period=20,
                volume_multiplier=2.5,
                price_momentum_period=5,
                min_price_change=0.02,  # 2% for semis
                position_size=position_size,
                max_position=max_position,
                hold_periods=15,
            ),
            # Cross-sectional for relative strength
            "cross_sectional": CrossSectionalMomentumStrategy(
                lookback_period=15,
                rebalance_period=30,
                long_percentile=0.25,  # Top 2 of 8
                short_percentile=0.0,
                enable_shorting=False,
                position_size=position_size,
                max_position_per_stock=max_position,
                min_stocks=max(3, num_tickers // 2),
            ),
        }

    strategies = create_strategies(
        args.position_size, args.max_position, len(args.tickers)
    )

    adaptive = AdaptivePortfolioStrategy(
        strategies=strategies,
        rebalance_period=args.rebalance_period,
        min_allocation=0.04,
        max_allocation=0.20,
        performance_lookback=args.rebalance_period,
        allocation_method=args.allocation_method,
    )

    portfolio = TradingPortfolio(initial_cash=args.initial_cash)
    risk_config = RiskConfig(
        max_position_size=args.max_position * 2,
        max_position_value=args.initial_cash * 0.15,
        max_total_exposure=args.initial_cash * 0.85,
        max_orders_per_minute=40,
        max_orders_per_symbol_per_minute=8,
        min_cash_buffer=args.initial_cash * 0.1,
    )
    order_manager = OrderManager(risk_config=risk_config)

    trading_client = TradingClient(api_key, api_secret, paper=not args.live)
    data_stream = StockDataStream(api_key, api_secret)

    bar_count = defaultdict(int)
    trading_active = False
    data_buffer = []

    logger.info("=" * 60)
    logger.info("SEMICONDUCTOR TRADER")
    logger.info("=" * 60)
    logger.info(f"Tickers: {args.tickers}")
    logger.info(f"Strategies: {list(strategies.keys())}")
    logger.info(f"Paper trading: {not args.live}")
    logger.info("=" * 60)

    async def on_bar(bar):
        nonlocal trading_active

        symbol = bar.symbol
        price = bar.close
        volume = bar.volume
        timestamp = bar.timestamp

        bar_count[symbol] += 1

        if args.save_data:
            data_buffer.append(
                {
                    "timestamp": timestamp,
                    "symbol": symbol,
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": price,
                    "volume": volume,
                }
            )

        min_bars = min(bar_count[t] for t in args.tickers)
        if not trading_active:
            if min_bars >= args.min_warmup_bars:
                trading_active = True
                logger.info("🚀 TRADING ACTIVATED - Semiconductor strategies ready!")
                adaptive.on_start(portfolio)
            else:
                if bar_count[symbol] % 10 == 0:
                    logger.info(f"Warming up: {min_bars}/{args.min_warmup_bars} bars")
                return

        tick = MarketDataPoint(
            timestamp=timestamp,
            symbol=symbol,
            price=price,
            volume=volume,
        )

        orders = adaptive.on_market_data(tick, portfolio)
        prices = {s: data_buffer[s][-1].price for s in args.tickers if data_buffer[s]}

        for order in orders:
            validated, reason = order_manager.validate_order(
                order, portfolio.cash, portfolio.positions, prices
            )
            if not validated:
                logger.warning(f"Order rejected: {reason}")
                continue

            try:
                alpaca_side = (
                    AlpacaOrderSide.BUY
                    if order.side == OrderSide.BUY
                    else AlpacaOrderSide.SELL
                )
                request = MarketOrderRequest(
                    symbol=order.symbol,
                    qty=order.quantity,
                    side=alpaca_side,
                    time_in_force=TimeInForce.DAY,
                )
                trading_client.submit_order(request)
                logger.info(
                    f"ORDER: {order.side.value} {order.quantity} {order.symbol}"
                )

                if order.side == OrderSide.BUY:
                    portfolio.cash -= price * order.quantity
                else:
                    portfolio.cash += price * order.quantity

            except Exception as e:
                logger.error(f"Order failed: {e}")

    data_stream.subscribe_bars(on_bar, *args.tickers)

    try:
        logger.info("Starting semiconductor trader stream...")
        data_stream.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        if args.save_data and data_buffer:
            df = pd.DataFrame(data_buffer)
            df.to_csv(args.data_file, index=False)
            logger.info(f"Data saved to {args.data_file}")


if __name__ == "__main__":
    main()
