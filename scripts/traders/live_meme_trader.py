#!/usr/bin/env python3
"""
Live Meme Stock Trader

Trades high-volatility "meme" stocks using momentum and breakout strategies.
These stocks have extreme volatility and are heavily sentiment-driven.

WARNING: These stocks are VERY volatile. Use small position sizes!

Tickers: GME, AMC, BBBY, PLTR, RIVN, LCID, SOFI

Usage:
    python scripts/traders/live_meme_trader.py
    python scripts/traders/live_meme_trader.py --tickers GME AMC PLTR
    python scripts/traders/live_meme_trader.py --save-data
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Meme / high-volatility stocks
DEFAULT_TICKERS = [
    "GME",    # GameStop
    "AMC",    # AMC Entertainment
    "PLTR",   # Palantir
    "RIVN",   # Rivian
    "LCID",   # Lucid Motors
    "SOFI",   # SoFi Technologies
    "HOOD",   # Robinhood
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
    from AlpacaTrading.strategies.momentum import MomentumStrategy
    from AlpacaTrading.strategies.bollinger_bands import BollingerBandsStrategy
    from AlpacaTrading.strategies.volume_breakout import VolumeBreakoutStrategy
    from AlpacaTrading.trading.order_manager import OrderManager, RiskConfig
    from AlpacaTrading.trading.portfolio import TradingPortfolio

    # Import new strategies
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
    from strategies.donchian_breakout import DonchianBreakoutStrategy
    from strategies.macd_strategy import MACDStrategy
    from strategies.rate_of_change import RateOfChangeStrategy
    from strategies.keltner_channel import KeltnerChannelStrategy
    from strategies.adx_trend import ADXTrendStrategy

    load_dotenv()

    parser = argparse.ArgumentParser(description="Live Meme Stock Trader")
    parser.add_argument("--tickers", nargs="+", default=DEFAULT_TICKERS)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--initial-cash", type=float, default=5000)  # Smaller for high risk
    parser.add_argument("--rebalance-period", type=int, default=30)  # Fast rebalancing
    parser.add_argument("--allocation-method", default="pnl", choices=["pnl", "sharpe", "win_rate"])
    parser.add_argument("--min-warmup-bars", type=int, default=25)
    parser.add_argument("--position-size", type=float, default=400)  # SMALL positions
    parser.add_argument("--max-position", type=int, default=50)
    parser.add_argument("--save-data", action="store_true")
    parser.add_argument("--data-file", default="logs/live_meme_data.csv")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("logs/live_meme_trader.log"),
        ],
    )
    logger = logging.getLogger(__name__)

    api_key = os.getenv("APCA_API_KEY_ID")
    api_secret = os.getenv("APCA_API_SECRET_KEY")

    if not api_key or not api_secret:
        print("ERROR: Missing Alpaca API credentials")
        sys.exit(1)

    # Momentum and breakout strategies for extreme volatility
    def create_strategies(position_size: float, max_position: int):
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

    strategies = create_strategies(args.position_size, args.max_position)
    
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
        max_position_size=args.max_position,
        max_position_value=args.initial_cash * 0.12,  # Small per position
        max_total_exposure=args.initial_cash * 0.7,  # Keep cash buffer
        max_orders_per_minute=50,  # Fast trading
        max_orders_per_symbol_per_minute=10,
        min_cash_buffer=args.initial_cash * 0.2,  # 20% cash buffer
    )
    order_manager = OrderManager(risk_config=risk_config)

    trading_client = TradingClient(api_key, api_secret, paper=not args.live)
    data_stream = StockDataStream(api_key, api_secret)

    bar_count = defaultdict(int)
    trading_active = False
    data_buffer = []

    logger.info("=" * 60)
    logger.info("⚠️  MEME STOCK TRADER - HIGH RISK! ⚠️")
    logger.info("=" * 60)
    logger.info(f"Tickers: {args.tickers}")
    logger.info(f"Strategies: {list(strategies.keys())}")
    logger.info(f"Position size: ${args.position_size} (SMALL!)")
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
            data_buffer.append({
                "timestamp": timestamp,
                "symbol": symbol,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": price,
                "volume": volume,
            })

        min_bars = min(bar_count[t] for t in args.tickers)
        if not trading_active:
            if min_bars >= args.min_warmup_bars:
                trading_active = True
                logger.info("🚀 TRADING ACTIVATED - Meme strategies ready! Be careful!")
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

        for order in orders:
            validated, reason = order_manager.validate_order(order, portfolio)
            if not validated:
                logger.warning(f"Order rejected: {reason}")
                continue

            try:
                alpaca_side = (
                    AlpacaOrderSide.BUY if order.side == OrderSide.BUY 
                    else AlpacaOrderSide.SELL
                )
                request = MarketOrderRequest(
                    symbol=order.symbol,
                    qty=order.quantity,
                    side=alpaca_side,
                    time_in_force=TimeInForce.DAY,
                )
                trading_client.submit_order(request)
                logger.info(f"ORDER: {order.side.value} {order.quantity} {order.symbol} @ ~${price:.2f}")
                
                if order.side == OrderSide.BUY:
                    portfolio.cash -= price * order.quantity
                else:
                    portfolio.cash += price * order.quantity
                    
            except Exception as e:
                logger.error(f"Order failed: {e}")

    data_stream.subscribe_bars(on_bar, *args.tickers)

    try:
        logger.info("Starting meme trader stream...")
        data_stream.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        if args.save_data and data_buffer:
            df = pd.DataFrame(data_buffer)
            df.to_csv(args.data_file, index=False)
            logger.info(f"Data saved to {args.data_file}")


if __name__ == "__main__":
    main()
