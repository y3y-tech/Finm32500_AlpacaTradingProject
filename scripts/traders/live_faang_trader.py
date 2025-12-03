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

import sys
from pathlib import Path

from AlpacaTrading.strategies.base import TradingStrategy

sys.path.insert(0, str(Path(__file__).parent))

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
    from AlpacaTrading.strategies.bollinger_bands import BollingerBandsStrategy
    from AlpacaTrading.strategies.keltner_channel import KeltnerChannelStrategy
    from AlpacaTrading.strategies.macd_strategy import MACDStrategy
    from AlpacaTrading.strategies.momentum import MomentumStrategy
    from AlpacaTrading.strategies.rate_of_change import RateOfChangeStrategy
    from AlpacaTrading.strategies.rsi_strategy import RSIStrategy
    from AlpacaTrading.strategies.stochastic_strategy import StochasticStrategy
    from AlpacaTrading.strategies.volume_breakout import VolumeBreakoutStrategy
    from AlpacaTrading.trading.order_manager import OrderManager, RiskConfig
    from AlpacaTrading.trading.portfolio import TradingPortfolio

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
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("logs/live_faang_trader.log"),
        ],
    )
    logger = logging.getLogger(__name__)

    api_key = os.getenv("APCA_API_KEY_ID")
    api_secret = os.getenv("APCA_API_SECRET_KEY")

    if not api_key or not api_secret:
        print("ERROR: Missing Alpaca API credentials")
        sys.exit(1)

    # Mixed momentum + reversion strategies for volatile stocks
    def create_strategies(
        position_size: float, max_position: int
    ) -> dict[str, TradingStrategy]:
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

    strategies = create_strategies(args.position_size, args.max_position)

    adaptive = AdaptivePortfolioStrategy(
        strategies=strategies,
        rebalance_period=args.rebalance_period,
        min_allocation=0.05,
        max_allocation=0.20,
        performance_lookback=args.rebalance_period,
        allocation_method=args.allocation_method,
    )

    portfolio = TradingPortfolio(initial_cash=args.initial_cash)
    risk_config = RiskConfig(
        max_position_size=args.max_position * 2,
        max_position_value=args.initial_cash * 0.18,
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
    logger.info("FAANG+ TECH TRADER")
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
                logger.info("🚀 TRADING ACTIVATED - FAANG strategies ready!")
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
                    f"ORDER SUBMITTED: {order.side.value} {order.quantity} {order.symbol}"
                )

                if order.side == OrderSide.BUY:
                    portfolio.cash -= price * order.quantity
                else:
                    portfolio.cash += price * order.quantity

            except Exception as e:
                logger.error(f"Order failed: {e}")

    data_stream.subscribe_bars(on_bar, *args.tickers)

    try:
        logger.info("Starting FAANG trader stream...")
        data_stream.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        if args.save_data and data_buffer:
            df = pd.DataFrame(data_buffer)
            df.to_csv(args.data_file, index=False)
            logger.info(f"Data saved to {args.data_file}")


if __name__ == "__main__":
    main()
