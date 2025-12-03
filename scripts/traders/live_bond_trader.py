#!/usr/bin/env python3
"""
Live Treasury/Bond Trader

Trades treasury ETFs using mean-reversion strategies.
Bonds tend to be range-bound and mean-reverting, making them ideal
for statistical strategies.

Tickers: IEF, TLT, SHY, BND, AGG, LQD

Usage:
    python scripts/traders/live_bond_trader.py
    python scripts/traders/live_bond_trader.py --tickers TLT IEF LQD
    python scripts/traders/live_bond_trader.py --save-data
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Treasury and bond ETFs
DEFAULT_TICKERS = [
    "IEF",  # 7-10 Year Treasury
    "TLT",  # 20+ Year Treasury
    "TLH",  # 10-20 Year Treasury
    "BND",  # Total Bond Market
    "LQD",  # Investment Grade Corporate
]


def main():
    import argparse
    import logging
    import os
    from collections import defaultdict

    import pandas as pd
    from alpaca.data.live import StockDataStream
    from alpaca.trading.client import TradingClient
    from alpaca.trading.enums import OrderSide as AlpacaOrderSide, TimeInForce
    from alpaca.trading.requests import MarketOrderRequest
    from dotenv import load_dotenv

    from AlpacaTrading.models import MarketDataPoint, Order, OrderSide
    from AlpacaTrading.strategies.adaptive_portfolio import AdaptivePortfolioStrategy
    from AlpacaTrading.strategies.rsi_strategy import RSIStrategy
    from AlpacaTrading.strategies.bollinger_bands import BollingerBandsStrategy
    from AlpacaTrading.strategies.mean_reversion import MovingAverageCrossoverStrategy
    from AlpacaTrading.strategies.cross_sectional_momentum import (
        CrossSectionalMomentumStrategy,
    )
    from AlpacaTrading.trading.order_manager import OrderManager, RiskConfig
    from AlpacaTrading.trading.portfolio import TradingPortfolio

    # Import new strategies
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
    from strategies.zscore_mean_reversion import ZScoreMeanReversionStrategy
    from strategies.multi_indicator_reversion import MultiIndicatorReversionStrategy
    from strategies.stochastic_strategy import StochasticStrategy
    from strategies.macd_strategy import MACDStrategy

    load_dotenv()

    parser = argparse.ArgumentParser(description="Live Treasury/Bond Trader")
    parser.add_argument("--tickers", nargs="+", default=DEFAULT_TICKERS)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--initial-cash", type=float, default=15000)
    parser.add_argument("--rebalance-period", type=int, default=120)  # Slower for bonds
    parser.add_argument(
        "--allocation-method", default="sharpe", choices=["pnl", "sharpe", "win_rate"]
    )
    parser.add_argument("--min-warmup-bars", type=int, default=60)
    parser.add_argument(
        "--position-size", type=float, default=2000
    )  # Larger for low-vol
    parser.add_argument("--max-position", type=int, default=40)
    parser.add_argument("--save-data", action="store_true")
    parser.add_argument("--data-file", default="logs/live_bond_data.csv")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("logs/live_bond_trader.log"),
        ],
    )
    logger = logging.getLogger(__name__)

    api_key = os.getenv("APCA_API_KEY_ID")
    api_secret = os.getenv("APCA_API_SECRET_KEY")

    if not api_key or not api_secret:
        print("ERROR: Missing Alpaca API credentials")
        sys.exit(1)

    # Mean-reversion focused for bonds
    def create_strategies(position_size: float, max_position: int, num_tickers: int):
        return {
            # Z-Score with different parameters
            "zscore_tight": ZScoreMeanReversionStrategy(
                lookback_period=15,
                entry_threshold=1.5,  # Tighter for low-vol bonds
                exit_threshold=0.0,
                position_size=position_size,
                max_position=max_position,
                enable_shorting=False,
            ),
            "zscore_wide": ZScoreMeanReversionStrategy(
                lookback_period=30,
                entry_threshold=2.0,
                exit_threshold=0.25,
                position_size=position_size,
                max_position=max_position,
                enable_shorting=False,
            ),
            # Multi-indicator composite
            "multi_indicator": MultiIndicatorReversionStrategy(
                lookback_period=25,
                rsi_period=14,
                entry_score=50,  # Lower threshold for bonds
                exit_score=0,
                position_size=position_size,
                max_position=max_position,
            ),
            # Stochastic
            "stoch_oversold": StochasticStrategy(
                k_period=14,
                d_period=3,
                oversold_threshold=25,
                overbought_threshold=75,
                signal_type="oversold",
                position_size=position_size,
                max_position=max_position,
            ),
            "stoch_crossover": StochasticStrategy(
                k_period=21,  # Longer for bonds
                d_period=5,
                oversold_threshold=20,
                overbought_threshold=80,
                signal_type="crossover",
                position_size=position_size,
                max_position=max_position,
            ),
            # RSI
            "rsi_conservative": RSIStrategy(
                rsi_period=14,
                oversold_threshold=35,  # Tighter ranges for bonds
                overbought_threshold=65,
                position_size=position_size,
                max_position=max_position,
                profit_target=1.0,
                stop_loss=0.5,
            ),
            "rsi_aggressive": RSIStrategy(
                rsi_period=10,
                oversold_threshold=30,
                overbought_threshold=70,
                position_size=position_size,
                max_position=max_position,
                profit_target=0.8,
                stop_loss=0.4,
            ),
            # Bollinger reversion
            "bb_reversion": BollingerBandsStrategy(
                period=25,
                num_std_dev=2.0,
                mode="reversion",
                position_size=position_size,
                max_position=max_position,
            ),
            # MA crossover (slower)
            "ma_cross": MovingAverageCrossoverStrategy(
                short_window=10,
                long_window=40,  # Longer for bonds
                position_size=position_size,
                max_position=max_position,
            ),
            # MACD for trend (bonds do trend on rate expectations)
            "macd": MACDStrategy(
                fast_period=12,
                slow_period=26,
                signal_period=9,
                signal_type="crossover",
                position_size=position_size,
                max_position=max_position,
            ),
            # Cross-sectional for duration/credit rotation
            "cross_sectional": CrossSectionalMomentumStrategy(
                lookback_period=20,
                rebalance_period=60,
                long_percentile=0.33,  # Top 2 of 6
                short_percentile=0.0,
                enable_shorting=False,
                position_size=position_size,
                max_position_per_stock=max_position,
                min_stocks=max(2, num_tickers // 2),
            ),
        }

    strategies = create_strategies(
        args.position_size, args.max_position, len(args.tickers)
    )

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
        max_position_value=args.initial_cash * 0.25,  # Larger positions OK for bonds
        max_total_exposure=args.initial_cash * 0.9,
        max_orders_per_minute=20,  # Slower trading
        max_orders_per_symbol_per_minute=5,
        min_cash_buffer=args.initial_cash * 0.08,
    )
    order_manager = OrderManager(risk_config=risk_config)

    trading_client = TradingClient(api_key, api_secret, paper=not args.live)
    data_stream = StockDataStream(api_key, api_secret)

    bar_count = defaultdict(int)
    trading_active = False
    data_buffer = []

    logger.info("=" * 60)
    logger.info("TREASURY/BOND TRADER")
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
                logger.info("🚀 TRADING ACTIVATED - Bond strategies ready!")
                adaptive.on_start(portfolio)
            else:
                if bar_count[symbol] % 15 == 0:
                    logger.info(f"Warming up: {min_bars}/{args.min_warmup_bars} bars")
                return

        tick = MarketDataPoint(
            timestamp=timestamp,
            symbol=symbol,
            price=price,
            volume=volume,
        )

        orders = adaptive.on_market_data(tick, portfolio)

        for order in orders:
            validated, reason = order_manager.validate_order(order, portfolio)
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
        logger.info("Starting bond trader stream...")
        data_stream.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        if args.save_data and data_buffer:
            df = pd.DataFrame(data_buffer)
            df.to_csv(args.data_file, index=False)
            logger.info(f"Data saved to {args.data_file}")


if __name__ == "__main__":
    main()
