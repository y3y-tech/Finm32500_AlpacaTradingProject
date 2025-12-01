#!/usr/bin/env python3
"""
Live Adaptive Crypto Trader

Connects to Alpaca crypto streaming API, observes market data, and trades
adaptively with multiple strategies once sufficient data is collected.

Features:
- Real-time Alpaca crypto data streaming (24/7 trading!)
- Automatic data buffering until strategies are ready
- Optional data saving to CSV for analysis
- Starts trading once minimum data requirements met
- All 11 strategies on 10 most liquid cryptocurrencies
- Hourly rebalancing with automatic winner selection

Usage:
    # Paper trading (default)
    python scripts/live_adaptive_crypto_trader.py

    # With data saving
    python scripts/live_adaptive_crypto_trader.py --save-data

    # Custom warmup period (shorter for crypto since 24/7)
    python scripts/live_adaptive_crypto_trader.py --min-warmup-bars 10

    # Live trading (CAREFUL!)
    python scripts/live_adaptive_crypto_trader.py --live
"""

import argparse
import logging
import os
import sys
from collections import defaultdict, deque
from pathlib import Path

import pandas as pd
from alpaca.data.live import CryptoDataStream
from alpaca.data.models import Bar
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide as AlpacaOrderSide
from alpaca.trading.enums import TimeInForce
from alpaca.trading.requests import MarketOrderRequest
from dotenv import load_dotenv

from AlpacaTrading.models import MarketDataPoint, Order, OrderSide
from AlpacaTrading.strategies.adaptive_portfolio import AdaptivePortfolioStrategy
from AlpacaTrading.strategies.base import TradingStrategy
from AlpacaTrading.strategies.bollinger_bands import BollingerBandsStrategy
from AlpacaTrading.strategies.cross_sectional_momentum import (
    CrossSectionalMomentumStrategy,
)
from AlpacaTrading.strategies.mean_reversion import MovingAverageCrossoverStrategy
from AlpacaTrading.strategies.momentum import MomentumStrategy
from AlpacaTrading.strategies.rsi_strategy import RSIStrategy
from AlpacaTrading.strategies.volume_breakout import VolumeBreakoutStrategy
from AlpacaTrading.strategies.vwap_strategy import VWAPStrategy
from AlpacaTrading.trading.order_manager import OrderManager, RiskConfig
from AlpacaTrading.trading.portfolio import TradingPortfolio

# Top 10 most liquid cryptocurrencies on Alpaca
# Using USD pairs for simplicity
LIQUID_CRYPTOS = [
    "BTC/USD",  # Bitcoin
    "ETH/USD",  # Ethereum
    "SOL/USD",  # Solana
    "XRP/USD",  # Ripple
    "ADA/USD",  # Cardano
    "AVAX/USD",  # Avalanche
    "DOGE/USD",  # Dogecoin
    "MATIC/USD",  # Polygon
    "DOT/USD",  # Polkadot
    "LTC/USD",  # Litecoin
]

logger = logging.getLogger(__name__)


class LiveAdaptiveCryptoTrader:
    """
    Live crypto trading system with Alpaca streaming and adaptive portfolio.

    Workflow:
    1. Connect to Alpaca crypto streaming API
    2. Buffer incoming market data
    3. Check if strategies have enough data
    4. Start trading once warmup complete
    5. Rebalance periodically (hourly)
    6. Optionally save all data to CSV
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        paper: bool = True,
        initial_cash: float = 10000,
        rebalance_period: int = 60,
        allocation_method: str = "pnl",
        min_warmup_bars: int = 30,
        save_data: bool = False,
        data_file: str = "logs/live_crypto_data.csv",
    ):
        """
        Initialize live adaptive crypto trader.

        Args:
            api_key: Alpaca API key
            api_secret: Alpaca API secret
            paper: Use paper trading (True) or live (False)
            initial_cash: Starting capital
            rebalance_period: Bars between rebalancing
            allocation_method: 'pnl', 'sharpe', or 'win_rate'
            min_warmup_bars: Minimum bars before trading starts
            save_data: Save streaming data to CSV
            data_file: Path to save data file
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.paper = paper
        self.initial_cash = initial_cash
        self.rebalance_period = rebalance_period
        self.allocation_method = allocation_method
        self.min_warmup_bars = min_warmup_bars
        self.save_data = save_data
        self.data_file = data_file

        # Initialize Alpaca clients
        self.trading_client = TradingClient(
            api_key=api_key, secret_key=api_secret, paper=paper
        )

        # Use CryptoDataStream instead of StockDataStream
        self.data_stream = CryptoDataStream(api_key=api_key, secret_key=api_secret)

        # Data buffering
        self.data_buffer: defaultdict[str, deque] = defaultdict(
            lambda: deque(maxlen=500)
        )
        self.bar_count: defaultdict[str, int] = defaultdict(int)
        self.all_data: list[dict] = []  # For saving to CSV

        # Trading state
        self.trading_active = False
        self.portfolio = TradingPortfolio(initial_cash=initial_cash)
        self.strategy = self._create_strategy()
        self.order_manager = self._create_order_manager()

        # Statistics
        self.total_bars_received = 0
        self.orders_submitted = 0

    def _create_strategy(self) -> AdaptivePortfolioStrategy:
        """Create adaptive portfolio with all strategies."""
        strategies: dict[str, TradingStrategy] = {
            "momentum_fast": MomentumStrategy(
                lookback_period=10,
                momentum_threshold=0.012,  # Higher threshold for crypto volatility
                position_size=100,  # Smaller position sizes for crypto
                max_position=5,
            ),
            "momentum_slow": MomentumStrategy(
                lookback_period=20,
                momentum_threshold=0.008,
                position_size=100,
                max_position=5,
            ),
            "ma_cross_fast": MovingAverageCrossoverStrategy(
                short_window=5, long_window=15, position_size=100, max_position=5
            ),
            "ma_cross_slow": MovingAverageCrossoverStrategy(
                short_window=10, long_window=30, position_size=100, max_position=5
            ),
            "rsi_aggressive": RSIStrategy(
                rsi_period=14,
                oversold_threshold=25,
                overbought_threshold=75,
                position_size=100,
                max_position=5,
                profit_target=2.0,  # Higher targets for crypto
                stop_loss=1.0,
            ),
            "rsi_conservative": RSIStrategy(
                rsi_period=14,
                oversold_threshold=30,
                overbought_threshold=70,
                position_size=100,
                max_position=5,
                profit_target=3.0,
                stop_loss=1.5,
            ),
            "bb_breakout": BollingerBandsStrategy(
                period=20,
                num_std_dev=2.0,
                mode="breakout",
                position_size=100,
                max_position=5,
            ),
            "bb_reversion": BollingerBandsStrategy(
                period=20,
                num_std_dev=2.5,
                mode="reversion",
                position_size=100,
                max_position=5,
            ),
            "volume_breakout": VolumeBreakoutStrategy(
                volume_period=20,
                volume_multiplier=2.5,  # Higher for crypto
                price_momentum_period=5,
                min_price_change=0.012,
                position_size=100,
                max_position=5,
                hold_periods=30,
            ),
            "vwap": VWAPStrategy(
                deviation_threshold=0.008,  # Higher deviation for crypto
                position_size=100,
                max_position=5,
                reset_period=0,
                min_samples=20,
            ),
            "cross_sectional": CrossSectionalMomentumStrategy(
                lookback_period=20,
                rebalance_period=30,
                long_percentile=0.30,  # Top 30% (3 out of 10)
                short_percentile=0.1,
                enable_shorting=False,
                position_size=100,
                max_position_per_stock=5,
                min_stocks=3,  # At least 3 cryptos
            ),
        }

        return AdaptivePortfolioStrategy(
            strategies=strategies,
            rebalance_period=self.rebalance_period,
            min_allocation=0.03,
            max_allocation=0.25,
            performance_lookback=self.rebalance_period,
            allocation_method=self.allocation_method,
        )

    def _create_order_manager(self) -> OrderManager:
        """Create order manager with risk controls for crypto."""
        risk_config = RiskConfig(
            max_position_size=10,  # Smaller sizes for crypto
            max_position_value=1500,  # Lower per-position limits
            max_total_exposure=9000,
            max_orders_per_minute=30,
            max_orders_per_symbol_per_minute=5,
            min_cash_buffer=500,
        )
        return OrderManager(risk_config=risk_config)

    def _check_warmup_complete(self) -> bool:
        """Check if we have enough data to start trading."""
        # Need minimum bars for each crypto
        for symbol in LIQUID_CRYPTOS:
            if self.bar_count[symbol] < self.min_warmup_bars:
                return False
        return True

    def _activate_trading(self):
        """Activate trading after warmup complete."""
        if self.trading_active:
            return

        self.trading_active = True
        logger.info(f"\n{'=' * 80}")
        logger.info("🚀 TRADING ACTIVATED!")
        logger.info(f"{'=' * 80}")
        logger.info(f"Warmup complete: All symbols have {self.min_warmup_bars}+ bars")
        logger.info(f"Total bars collected: {self.total_bars_received}")
        logger.info("Starting adaptive multi-strategy crypto trading...")
        logger.info(f"Rebalancing every {self.rebalance_period} bars")
        logger.info(f"{'=' * 80}\n")

        # Initialize strategy
        self.strategy.on_start(self.portfolio)

    async def _handle_bar(self, bar: Bar):
        """Handle incoming bar from Alpaca stream."""
        try:
            symbol = bar.symbol

            # Create MarketDataPoint
            tick = MarketDataPoint(
                timestamp=bar.timestamp,
                symbol=symbol,
                price=float(bar.close),
                volume=float(bar.volume),
            )

            # Buffer the data
            self.data_buffer[symbol].append(tick)
            self.bar_count[symbol] += 1
            self.total_bars_received += 1

            # Save to CSV if enabled
            if self.save_data:
                self.all_data.append(
                    {
                        "timestamp": tick.timestamp,
                        "symbol": symbol,
                        "price": tick.price,
                        "volume": tick.volume,
                        "open": float(bar.open),
                        "high": float(bar.high),
                        "low": float(bar.low),
                    }
                )

            # Check if warmup complete
            if not self.trading_active:
                if self._check_warmup_complete():
                    self._activate_trading()
                else:
                    # Log warmup progress every 10 bars
                    if self.total_bars_received % 10 == 0:
                        min_bars = min(
                            self.bar_count.get(s, 0) for s in LIQUID_CRYPTOS
                        )
                        logger.info(
                            f"Warmup: {min_bars}/{self.min_warmup_bars} bars "
                            f"(Total: {self.total_bars_received})"
                        )
                return

            # Trading is active - run strategy
            orders = self.strategy.process_market_data(tick, self.portfolio)

            # Process orders
            for order in orders:
                # Validate with order manager
                if self.order_manager.validate_order(order, self.portfolio):
                    # Submit to Alpaca
                    self._submit_order(order)
                    self.order_manager.record_order(order)
                else:
                    logger.warning(f"Order rejected by risk manager: {order}")

            # Update portfolio prices
            current_prices = {
                s: self.data_buffer[s][-1].price
                for s in LIQUID_CRYPTOS
                if self.data_buffer[s]
            }
            self.portfolio.update_prices(current_prices)

            # Log status periodically
            if self.total_bars_received % 100 == 0:
                equity = self.portfolio.get_total_equity()
                pnl = self.portfolio.get_total_pnl()
                logger.info(
                    f"📊 Status: Bars={self.total_bars_received}, "
                    f"Equity=${equity:,.2f}, P&L=${pnl:,.2f}, "
                    f"Orders={self.orders_submitted}"
                )

        except Exception as e:
            logger.error(f"Error handling bar: {e}", exc_info=True)

    def _submit_order(self, order: Order):
        """Submit order to Alpaca."""
        try:
            # Convert to Alpaca order
            alpaca_side = (
                AlpacaOrderSide.BUY
                if order.side == OrderSide.BUY
                else AlpacaOrderSide.SELL
            )

            order_request = MarketOrderRequest(
                symbol=order.symbol,
                qty=order.quantity,
                side=alpaca_side,
                time_in_force=TimeInForce.GTC,  # Good-til-cancelled for crypto
            )

            # Submit
            response = self.trading_client.submit_order(order_request)
            self.orders_submitted += 1

            logger.info(
                f"✅ Order submitted: {order.side.value} {order.quantity} {order.symbol} "
                f"(Order ID: {response.id})"
            )

            return response

        except Exception as e:
            logger.error(f"❌ Failed to submit order {order}: {e}")
            return None

    def _save_data_to_csv(self):
        """Save buffered data to CSV file."""
        if not self.all_data:
            logger.info("No data to save")
            return

        try:
            df = pd.DataFrame(self.all_data)
            df = df.sort_values("timestamp")

            # Create directory if needed
            Path(self.data_file).parent.mkdir(parents=True, exist_ok=True)

            df.to_csv(self.data_file, index=False)
            logger.info(f"💾 Saved {len(df)} bars to {self.data_file}")

        except Exception as e:
            logger.error(f"Failed to save data: {e}")

    async def run(self):
        """Start the live crypto trading system."""
        logger.info(f"\n{'=' * 80}")
        logger.info("🪙 LIVE ADAPTIVE CRYPTO TRADER 🪙")
        logger.info(f"{'=' * 80}")
        logger.info(
            f"Mode: {'📄 PAPER TRADING' if self.paper else '⚠️  LIVE TRADING ⚠️ '}"
        )
        logger.info(f"Initial capital: ${self.initial_cash:,.2f}")
        logger.info(f"Cryptos: {', '.join(LIQUID_CRYPTOS)}")
        logger.info("Strategies: 11 (momentum, RSI, BB, VWAP, volume, cross-sectional)")
        logger.info(f"Rebalance: Every {self.rebalance_period} bars")
        logger.info(f"Allocation method: {self.allocation_method}")
        logger.info(f"Min warmup bars: {self.min_warmup_bars}")
        logger.info(f"Save data: {self.save_data}")
        if self.save_data:
            logger.info(f"Data file: {self.data_file}")
        logger.info(f"{'=' * 80}\n")
        logger.info("⏳ Starting warmup phase - collecting data before trading...\n")

        # Subscribe to bars for all cryptos
        for symbol in LIQUID_CRYPTOS:
            self.data_stream.subscribe_bars(self._handle_bar, symbol)

        try:
            # Start streaming
            await self.data_stream._run_forever()

        except KeyboardInterrupt:
            logger.info("\n\n🛑 Shutting down gracefully...")

            # Final statistics
            logger.info(f"\n{'=' * 80}")
            logger.info("SESSION SUMMARY")
            logger.info(f"{'=' * 80}")
            logger.info(f"Total bars received: {self.total_bars_received}")
            logger.info(f"Orders submitted: {self.orders_submitted}")
            logger.info(f"Trading was active: {self.trading_active}")

            if self.trading_active:
                equity = self.portfolio.get_total_equity()
                pnl = self.portfolio.get_total_pnl()
                ret = (equity - self.initial_cash) / self.initial_cash * 100

                logger.info("\nPERFORMANCE:")
                logger.info(f"  Final equity: ${equity:,.2f}")
                logger.info(f"  Total P&L: ${pnl:,.2f}")
                logger.info(f"  Return: {ret:.2f}%")

                # Strategy performance
                logger.info("\nSTRATEGY ALLOCATIONS:")
                for name, perf in self.strategy.performance.items():
                    logger.info(
                        f"  {name:<20} {perf.target_allocation * 100:>5.1f}% "
                        f"(P&L: ${perf.total_pnl:>8,.2f})"
                    )

            logger.info(f"{'=' * 80}\n")

            # Save data if enabled
            if self.save_data:
                logger.info("Saving collected data...")
                self._save_data_to_csv()

            logger.info("✅ Shutdown complete")

        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            raise


def main():
    parser = argparse.ArgumentParser(
        description="Live Adaptive Crypto Trader with Alpaca Streaming",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Paper trading with default settings
  python scripts/live_adaptive_crypto_trader.py

  # Paper trading with data saving
  python scripts/live_adaptive_crypto_trader.py --save-data

  # Shorter warmup (10 bars instead of 30)
  python scripts/live_adaptive_crypto_trader.py --min-warmup-bars 10

  # Custom rebalancing (every 120 bars = 2 hours)
  python scripts/live_adaptive_crypto_trader.py --rebalance-period 120

  # Use Sharpe ratio for allocation
  python scripts/live_adaptive_crypto_trader.py --allocation-method sharpe

  # LIVE TRADING (use with caution!)
  python scripts/live_adaptive_crypto_trader.py --live --initial-cash 10000

Environment Variables Required:
  ALPACA_API_KEY: Your Alpaca API key
  ALPACA_SECRET_KEY: Your Alpaca API secret

  Set these in .env file or export them:
    export ALPACA_API_KEY="your_key"
    export ALPACA_SECRET_KEY="your_secret"

Note: Crypto markets trade 24/7, so this will work anytime!
        """,
    )

    parser.add_argument(
        "--live", action="store_true", help="Use LIVE trading (default: paper trading)"
    )
    parser.add_argument(
        "--initial-cash",
        type=float,
        default=10000,
        help="Initial capital (default: 10000)",
    )
    parser.add_argument(
        "--rebalance-period",
        type=int,
        default=60,
        help="Bars between rebalances (default: 60)",
    )
    parser.add_argument(
        "--allocation-method",
        type=str,
        default="pnl",
        choices=["pnl", "sharpe", "win_rate"],
        help="Allocation method (default: pnl)",
    )
    parser.add_argument(
        "--min-warmup-bars",
        type=int,
        default=30,
        help="Minimum bars before trading starts (default: 30)",
    )
    parser.add_argument(
        "--save-data", action="store_true", help="Save streaming data to CSV"
    )
    parser.add_argument(
        "--data-file",
        type=str,
        default="logs/live_crypto_data.csv",
        help="File to save data (default: logs/live_crypto_data.csv)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING"],
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("logs/live_adaptive_crypto_trader.log"),
        ],
    )

    # Load environment variables
    load_dotenv()

    api_key = os.getenv("ALPACA_API_KEY")
    api_secret = os.getenv("ALPACA_SECRET_KEY")

    if not api_key or not api_secret:
        print("ERROR: Alpaca API credentials not found!")
        print("Set ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables")
        print("Either in .env file or export them in your shell")
        sys.exit(1)

    # Warning for live trading
    if args.live:
        print("\n" + "=" * 80)
        print("⚠️  WARNING: LIVE CRYPTO TRADING MODE ⚠️ ")
        print("=" * 80)
        print("You are about to trade with REAL MONEY!")
        print(f"Initial capital: ${args.initial_cash:,.2f}")
        print("\nAre you sure you want to continue?")
        response = input("Type 'YES' to confirm: ")
        if response != "YES":
            print("Aborted.")
            sys.exit(0)
        print("=" * 80 + "\n")

    # Create trader
    trader = LiveAdaptiveCryptoTrader(
        api_key=api_key,
        api_secret=api_secret,
        paper=not args.live,
        initial_cash=args.initial_cash,
        rebalance_period=args.rebalance_period,
        allocation_method=args.allocation_method,
        min_warmup_bars=args.min_warmup_bars,
        save_data=args.save_data,
        data_file=args.data_file,
    )

    # Run
    import asyncio

    asyncio.run(trader.run())


if __name__ == "__main__":
    main()
