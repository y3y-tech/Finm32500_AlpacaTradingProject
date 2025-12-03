#!/usr/bin/env python3
"""
Live SPY Single-Stock Trader

Concentrated trading on SPY using all available strategies.
SPY is the most liquid ETF, making it ideal for high-frequency strategy testing.

Uses a comprehensive mix of:
- Trend strategies (Donchian, MACD, ROC, ADX)
- Reversion strategies (Z-Score, Stochastic, Multi-Indicator)
- Volatility strategies (Keltner, Bollinger)
- Momentum strategies

Usage:
    python scripts/traders/live_spy_trader.py
    python scripts/traders/live_spy_trader.py --initial-cash 20000
    python scripts/traders/live_spy_trader.py --save-data
"""

import sys
from pathlib import Path

from AlpacaTrading.strategies.base import TradingStrategy

sys.path.insert(0, str(Path(__file__).parent))

# Single stock - maximum concentration
DEFAULT_TICKERS = ["SPY"]


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
    from AlpacaTrading.trading.order_manager import OrderManager, RiskConfig
    from AlpacaTrading.trading.portfolio import TradingPortfolio

    load_dotenv()

    parser = argparse.ArgumentParser(description="Live SPY Single-Stock Trader")
    parser.add_argument("--tickers", nargs="+", default=DEFAULT_TICKERS)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--initial-cash", type=float, default=20000)
    parser.add_argument(
        "--rebalance-period", type=int, default=30
    )  # Faster for single stock
    parser.add_argument(
        "--allocation-method", default="sharpe", choices=["pnl", "sharpe", "win_rate"]
    )
    parser.add_argument("--min-warmup-bars", type=int, default=35)
    parser.add_argument("--position-size", type=float, default=2000)
    parser.add_argument(
        "--max-position", type=int, default=50
    )  # Larger for single stock
    parser.add_argument("--save-data", action="store_true")
    parser.add_argument("--data-file", default="logs/live_spy_data.csv")
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
            logging.FileHandler("logs/live_spy_trader.log"),
        ],
    )
    logger = logging.getLogger(__name__)

    api_key = os.getenv("APCA_API_KEY_ID")
    api_secret = os.getenv("APCA_API_SECRET_KEY")

    if not api_key or not api_secret:
        print("ERROR: Missing Alpaca API credentials")
        sys.exit(1)

    # Comprehensive strategy mix for single-stock trading
    def create_strategies(
        position_size: float, max_position: int
    ) -> dict[str, TradingStrategy]:
        return {
            # === TREND FOLLOWING ===
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
            "macd_histogram": MACDStrategy(
                fast_period=12,
                slow_period=26,
                signal_period=9,
                signal_type="histogram",
                position_size=position_size,
                max_position=max_position,
            ),
            "roc": RateOfChangeStrategy(
                lookback_period=12,
                entry_threshold=0.8,  # Lower for SPY (less volatile)
                exit_threshold=0.0,
                position_size=position_size,
                max_position=max_position,
                use_smoothing=True,
            ),
            "adx": ADXTrendStrategy(
                adx_period=14,
                adx_threshold=20,
                di_threshold=5,
                position_size=position_size,
                max_position=max_position,
            ),
            # === MEAN REVERSION ===
            "zscore": ZScoreMeanReversionStrategy(
                lookback_period=20,
                entry_threshold=2.0,
                exit_threshold=0.0,
                position_size=position_size,
                max_position=max_position,
                enable_shorting=False,
            ),
            "multi_indicator": MultiIndicatorReversionStrategy(
                lookback_period=20,
                rsi_period=14,
                entry_score=60,
                exit_score=0,
                position_size=position_size,
                max_position=max_position,
            ),
            "stochastic": StochasticStrategy(
                k_period=14,
                d_period=3,
                oversold_threshold=20,
                overbought_threshold=80,
                signal_type="crossover",
                position_size=position_size,
                max_position=max_position,
            ),
            "rsi": RSIStrategy(
                rsi_period=14,
                oversold_threshold=30,
                overbought_threshold=70,
                position_size=position_size,
                max_position=max_position,
                profit_target=1.5,
                stop_loss=0.8,
            ),
            # === VOLATILITY BANDS ===
            "keltner_breakout": KeltnerChannelStrategy(
                ema_period=20,
                atr_period=10,
                atr_multiplier=2.0,
                mode="breakout",
                position_size=position_size,
                max_position=max_position,
            ),
            "keltner_reversion": KeltnerChannelStrategy(
                ema_period=20,
                atr_period=10,
                atr_multiplier=2.5,
                mode="reversion",
                position_size=position_size,
                max_position=max_position,
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
            # === MOMENTUM ===
            "momentum_fast": MomentumStrategy(
                lookback_period=8,
                momentum_threshold=0.006,
                position_size=position_size,
                max_position=max_position,
            ),
            "momentum_slow": MomentumStrategy(
                lookback_period=20,
                momentum_threshold=0.004,
                position_size=position_size,
                max_position=max_position,
            ),
            # === MA CROSSOVER ===
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
            # === VOLUME/VWAP ===
            "volume_breakout": VolumeBreakoutStrategy(
                volume_period=20,
                volume_multiplier=2.0,
                price_momentum_period=5,
                min_price_change=0.005,
                position_size=position_size,
                max_position=max_position,
                hold_periods=30,
            ),
            "vwap": VWAPStrategy(
                deviation_threshold=0.003,  # Tighter for SPY
                position_size=position_size,
                max_position=max_position,
                reset_period=0,
                min_samples=20,
            ),
        }

    strategies = create_strategies(args.position_size, args.max_position)

    adaptive = AdaptivePortfolioStrategy(
        strategies=strategies,
        rebalance_period=args.rebalance_period,
        min_allocation=0.02,  # Allow lower minimums with many strategies
        max_allocation=0.15,  # Cap any single strategy
        performance_lookback=args.rebalance_period,
        allocation_method=args.allocation_method,
    )

    portfolio = TradingPortfolio(initial_cash=args.initial_cash)
    risk_config = RiskConfig(
        max_position_size=args.max_position * 3,  # Higher for single stock
        max_position_value=args.initial_cash * 0.5,  # Can go heavy on SPY
        max_total_exposure=args.initial_cash * 0.95,
        max_orders_per_minute=50,  # Higher for single stock
        max_orders_per_symbol_per_minute=20,
        min_cash_buffer=args.initial_cash * 0.05,
    )
    order_manager = OrderManager(risk_config=risk_config)

    trading_client = TradingClient(api_key, api_secret, paper=not args.live)
    data_stream = StockDataStream(api_key, api_secret)

    bar_count = defaultdict(int)
    trading_active = False
    data_buffer = []

    logger.info("=" * 60)
    logger.info("SPY SINGLE-STOCK TRADER")
    logger.info("=" * 60)
    logger.info(f"Tickers: {args.tickers}")
    logger.info(f"Strategies ({len(strategies)}): {list(strategies.keys())}")
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
                logger.info(
                    f"🚀 TRADING ACTIVATED - {len(strategies)} strategies on SPY!"
                )
                adaptive.on_start(portfolio)
            else:
                if bar_count[symbol] % 5 == 0:
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
                    f"ORDER: {order.side.value} {order.quantity} {order.symbol} @ ~${price:.2f}"
                )

                if order.side == OrderSide.BUY:
                    portfolio.cash -= price * order.quantity
                else:
                    portfolio.cash += price * order.quantity

            except Exception as e:
                logger.error(f"Order failed: {e}")

    data_stream.subscribe_bars(on_bar, *args.tickers)

    try:
        logger.info("Starting SPY trader stream...")
        data_stream.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        if args.save_data and data_buffer:
            df = pd.DataFrame(data_buffer)
            df.to_csv(args.data_file, index=False)
            logger.info(f"Data saved to {args.data_file}")


if __name__ == "__main__":
    main()
