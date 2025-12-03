#!/usr/bin/env python3
"""
Live Trend-Following Trader

Uses trend-focused strategies:
- Donchian Breakout (Turtle Trading)
- MACD (crossover and zero-cross)
- Rate of Change (momentum)
- ADX Trend Filter

Best for: Trending assets like commodities, currencies, EM ETFs

Usage:
    python scripts/traders/live_trend_trader.py
    python scripts/traders/live_trend_trader.py --tickers USO UNG GLD SLV
    python scripts/traders/live_trend_trader.py --save-data
"""

import sys
from pathlib import Path

from AlpacaTrading.strategies.base import TradingStrategy

sys.path.insert(0, str(Path(__file__).parent))

# Commodity-focused tickers good for trend following
DEFAULT_TICKERS = [
    "USO",  # Oil
    "UNG",  # Natural Gas
    "GLD",  # Gold
    "SLV",  # Silver
    "DBA",  # Agriculture
    "DBB",  # Base Metals
]


def main():
    import argparse
    import logging
    import os
    from collections import defaultdict, deque

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
    from AlpacaTrading.strategies.donchian_breakout import DonchianBreakoutStrategy
    from AlpacaTrading.strategies.keltner_channel import KeltnerChannelStrategy
    from AlpacaTrading.strategies.macd_strategy import MACDStrategy
    from AlpacaTrading.strategies.rate_of_change import RateOfChangeStrategy
    from AlpacaTrading.trading.order_manager import OrderManager, RiskConfig
    from AlpacaTrading.trading.portfolio import TradingPortfolio

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
    logger = logging.getLogger(__name__)

    api_key = os.getenv("APCA_API_KEY_ID")
    api_secret = os.getenv("APCA_API_SECRET_KEY")

    if not api_key or not api_secret:
        print("ERROR: Missing Alpaca API credentials")
        sys.exit(1)

    # Create trend-focused strategies
    def create_strategies(
        position_size: float, max_position: int
    ) -> dict[str, TradingStrategy]:
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

    strategies = create_strategies(args.position_size, args.max_position)

    adaptive = AdaptivePortfolioStrategy(
        strategies=strategies,
        rebalance_period=args.rebalance_period,
        min_allocation=0.05,
        max_allocation=0.25,
        performance_lookback=args.rebalance_period,
        allocation_method=args.allocation_method,
    )

    portfolio = TradingPortfolio(initial_cash=args.initial_cash)
    risk_config = RiskConfig(
        max_position_size=args.max_position * 2,
        max_position_value=args.initial_cash * 0.15,
        max_total_exposure=args.initial_cash * 0.8,
        max_orders_per_minute=30,
        max_orders_per_symbol_per_minute=8,
        min_cash_buffer=args.initial_cash * 0.1,
    )
    order_manager = OrderManager(risk_config=risk_config)

    trading_client = TradingClient(api_key, api_secret, paper=not args.live)
    data_stream = StockDataStream(api_key, api_secret)

    bar_count = defaultdict(int)
    price_history = defaultdict(lambda: deque(maxlen=100))
    trading_active = False
    data_buffer = []

    logger.info("=" * 60)
    logger.info("TREND-FOLLOWING TRADER")
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
        price_history[symbol].append(price)

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

        # Check warmup
        min_bars = min(bar_count[t] for t in args.tickers)
        if not trading_active:
            if min_bars >= args.min_warmup_bars:
                trading_active = True
                logger.info("🚀 TRADING ACTIVATED - Trend strategies ready!")
                adaptive.on_start(portfolio)
            else:
                if bar_count[symbol] % 10 == 0:
                    logger.info(f"Warming up: {min_bars}/{args.min_warmup_bars} bars")
                return

        # Create tick
        tick = MarketDataPoint(
            timestamp=timestamp,
            symbol=symbol,
            price=price,
            volume=volume,
        )

        # Get orders from adaptive strategy
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
                result = trading_client.submit_order(request)
                logger.info(
                    f"ORDER SUBMITTED: {order.side.value} {order.quantity} {order.symbol}"
                )

                # Update portfolio
                if order.side == OrderSide.BUY:
                    portfolio.cash -= price * order.quantity
                else:
                    portfolio.cash += price * order.quantity

            except Exception as e:
                logger.error(f"Order failed: {e}")

    data_stream.subscribe_bars(on_bar, *args.tickers)

    try:
        logger.info("Starting trend trader stream...")
        data_stream.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        if args.save_data and data_buffer:
            df = pd.DataFrame(data_buffer)
            df.to_csv(args.data_file, index=False)
            logger.info(f"Data saved to {args.data_file}")


if __name__ == "__main__":
    main()
