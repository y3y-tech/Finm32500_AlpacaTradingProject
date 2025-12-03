#!/usr/bin/env python3
"""
Generic Live Adaptive Trader

Connects to Alpaca streaming API, observes market data, and trades
adaptively with multiple strategies once sufficient data is collected.

Supports both US Equities and Cryptocurrencies - auto-detected from ticker format.

Features:
- Real-time Alpaca market data streaming (Stocks or Crypto)
- Automatic data buffering until strategies are ready
- Optional data saving to CSV for analysis
- Starts trading once minimum data requirements met
- All 11 strategies with adaptive rebalancing
- Flexible ticker configuration via command-line

Usage:
    # Paper trading with sector ETFs
    python scripts/traders/live_adaptive_trader.py --tickers XLF XLI XLK XLE

    # Paper trading with crypto
    python scripts/traders/live_adaptive_trader.py --tickers BTC/USD ETH/USD SOL/USD

    # Mixed (auto-detects asset type)
    python scripts/traders/live_adaptive_trader.py --tickers AAPL MSFT BTC/USD ETH/USD

    # With data saving
    python scripts/traders/live_adaptive_trader.py --tickers XLF XLI --save-data

    # Live trading (CAREFUL!)
    python scripts/traders/live_adaptive_trader.py --tickers XLF XLI --live
"""

import argparse
import logging
import os
import sys
from collections import defaultdict, deque
from pathlib import Path

import pandas as pd
from alpaca.data.live import CryptoDataStream, StockDataStream
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

logger = logging.getLogger(__name__)


class LiveAdaptiveTrader:
    """
    Generic live trading system with Alpaca streaming and adaptive portfolio.

    Supports both stocks and crypto - automatically detects asset type from ticker format.
    Crypto tickers contain "/" (e.g., "BTC/USD"), stock tickers don't (e.g., "AAPL").

    Workflow:
    1. Connect to Alpaca streaming API (Stock or Crypto)
    2. Buffer incoming market data
    3. Check if strategies have enough data
    4. Start trading once warmup complete
    5. Rebalance periodically
    6. Optionally save all data to CSV
    """

    def __init__(
        self,
        tickers: list[str],
        api_key: str,
        api_secret: str,
        paper: bool = True,
        initial_cash: float = 10000,
        rebalance_period: int = 60,
        allocation_method: str = "pnl",
        min_warmup_bars: int = 30,
        save_data: bool = False,
        data_file: str = "logs/live_data.csv",
        # Strategy parameters
        position_size: int = 100,
        max_position: int = 10,
        # Risk parameters
        max_position_value: float = 1500,
        max_total_exposure: float = 9000,
        max_orders_per_minute: int = 50,
        min_cash_buffer: float = 500,
    ):
        """
        Initialize live adaptive trader.

        Args:
            tickers: List of ticker symbols to trade
            api_key: Alpaca API key
            api_secret: Alpaca API secret
            paper: Use paper trading (True) or live (False)
            initial_cash: Starting capital
            rebalance_period: Bars between rebalancing
            allocation_method: 'pnl', 'sharpe', or 'win_rate'
            min_warmup_bars: Minimum bars before trading starts
            save_data: Save streaming data to CSV
            data_file: Path to save data file
            position_size: Default position size for strategies
            max_position: Max position per symbol for strategies
            max_position_value: Max $ per position (risk management)
            max_total_exposure: Max total portfolio $ (risk management)
            max_orders_per_minute: Order rate limit (risk management)
            min_cash_buffer: Safety cash buffer (risk management)
        """
        self.tickers = tickers
        self.api_key = api_key
        self.api_secret = api_secret
        self.paper = paper
        self.initial_cash = initial_cash
        self.rebalance_period = rebalance_period
        self.allocation_method = allocation_method
        self.min_warmup_bars = min_warmup_bars
        self.save_data = save_data
        self.data_file = data_file
        self.position_size = position_size
        self.max_position = max_position

        # Auto-detect asset type from tickers
        self.is_crypto = self._detect_crypto_tickers(tickers)
        self.asset_type = "crypto" if self.is_crypto else "stocks"

        # Initialize Alpaca clients
        self.trading_client = TradingClient(
            api_key=api_key, secret_key=api_secret, paper=paper
        )

        # Use appropriate data stream based on asset type
        if self.is_crypto:
            self.data_stream = CryptoDataStream(api_key=api_key, secret_key=api_secret)
        else:
            self.data_stream = StockDataStream(api_key=api_key, secret_key=api_secret)

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
        self.order_manager = self._create_order_manager(
            max_position_value=max_position_value,
            max_total_exposure=max_total_exposure,
            max_orders_per_minute=max_orders_per_minute,
            min_cash_buffer=min_cash_buffer,
        )

        # Statistics
        self.total_bars_received = 0
        self.orders_submitted = 0

    def _detect_crypto_tickers(self, tickers: list[str]) -> bool:
        """
        Detect if tickers are crypto or stocks based on format.

        Crypto tickers contain "/" (e.g., "BTC/USD")
        Stock tickers don't (e.g., "AAPL")

        Args:
            tickers: List of ticker symbols

        Returns:
            True if crypto, False if stocks

        Raises:
            ValueError: If mixed asset types detected
        """
        crypto_count = sum(1 for ticker in tickers if "/" in ticker)
        stock_count = len(tickers) - crypto_count

        if crypto_count > 0 and stock_count > 0:
            raise ValueError(
                f"Mixed asset types detected! Cannot mix stocks and crypto.\n"
                f"Crypto tickers (with '/'): {crypto_count}\n"
                f"Stock tickers (without '/'): {stock_count}\n"
                f"Please use either all stocks or all crypto."
            )

        return crypto_count > 0

    def _create_strategy(self) -> AdaptivePortfolioStrategy:
        """Create adaptive portfolio with all strategies."""
        # Adjust thresholds based on asset type
        if self.is_crypto:
            momentum_threshold_fast = 0.012  # Higher for crypto volatility
            momentum_threshold_slow = 0.008
            min_price_change = 0.012
            deviation_threshold = 0.008
            profit_target_aggressive = 2.0
            profit_target_conservative = 3.0
            stop_loss_aggressive = 1.0
            stop_loss_conservative = 1.5
            volume_multiplier = 2.5
        else:
            momentum_threshold_fast = 0.008
            momentum_threshold_slow = 0.005
            min_price_change = 0.008
            deviation_threshold = 0.005
            profit_target_aggressive = 1.5
            profit_target_conservative = 2.0
            stop_loss_aggressive = 0.75
            stop_loss_conservative = 1.0
            volume_multiplier = 2.0

        strategies: dict[str, TradingStrategy] = {
            "momentum_fast": MomentumStrategy(
                lookback_period=10,
                momentum_threshold=momentum_threshold_fast,
                position_size=self.position_size,
                max_position=self.max_position,
            ),
            "momentum_slow": MomentumStrategy(
                lookback_period=20,
                momentum_threshold=momentum_threshold_slow,
                position_size=self.position_size,
                max_position=self.max_position,
            ),
            "ma_cross_fast": MovingAverageCrossoverStrategy(
                short_window=5,
                long_window=15,
                position_size=self.position_size,
                max_position=self.max_position,
            ),
            "ma_cross_slow": MovingAverageCrossoverStrategy(
                short_window=10,
                long_window=30,
                position_size=self.position_size,
                max_position=self.max_position,
            ),
            "rsi_aggressive": RSIStrategy(
                rsi_period=14,
                oversold_threshold=25,
                overbought_threshold=75,
                position_size=self.position_size,
                max_position=self.max_position,
                profit_target=profit_target_aggressive,
                stop_loss=stop_loss_aggressive,
            ),
            "rsi_conservative": RSIStrategy(
                rsi_period=14,
                oversold_threshold=30,
                overbought_threshold=70,
                position_size=self.position_size,
                max_position=self.max_position,
                profit_target=profit_target_conservative,
                stop_loss=stop_loss_conservative,
            ),
            "bb_breakout": BollingerBandsStrategy(
                period=20,
                num_std_dev=2.0,
                mode="breakout",
                position_size=self.position_size,
                max_position=self.max_position,
            ),
            "bb_reversion": BollingerBandsStrategy(
                period=20,
                num_std_dev=2.5,
                mode="reversion",
                position_size=self.position_size,
                max_position=self.max_position,
            ),
            "volume_breakout": VolumeBreakoutStrategy(
                volume_period=20,
                volume_multiplier=volume_multiplier,
                price_momentum_period=5,
                min_price_change=min_price_change,
                position_size=self.position_size,
                max_position=self.max_position,
                hold_periods=30,
            ),
            "vwap": VWAPStrategy(
                deviation_threshold=deviation_threshold,
                position_size=self.position_size,
                max_position=self.max_position,
                reset_period=0,
                min_samples=20,
            ),
            "cross_sectional": CrossSectionalMomentumStrategy(
                lookback_period=20,
                rebalance_period=30,
                long_percentile=0.30,
                short_percentile=0.1,
                enable_shorting=False,
                position_size=self.position_size,
                max_position_per_stock=self.max_position,
                min_stocks=min(3, len(self.tickers)),
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

    def _create_order_manager(
        self,
        max_position_value: float,
        max_total_exposure: float,
        max_orders_per_minute: int,
        min_cash_buffer: float,
    ) -> OrderManager:
        """Create order manager with risk controls."""
        risk_config = RiskConfig(
            max_position_size=self.max_position * 2,  # Safety margin
            max_position_value=max_position_value,
            max_total_exposure=max_total_exposure,
            max_orders_per_minute=max_orders_per_minute,
            max_orders_per_symbol_per_minute=10,
            min_cash_buffer=min_cash_buffer,
        )
        return OrderManager(risk_config=risk_config)

    def _check_warmup_complete(self) -> bool:
        """Check if we have enough data to start trading."""
        # Need minimum bars for each ticker
        for ticker in self.tickers:
            if self.bar_count[ticker] < self.min_warmup_bars:
                return False
        return True

    def _activate_trading(self):
        """Activate trading after warmup complete."""
        if self.trading_active:
            return

        self.trading_active = True
        logger.info("=" * 80)
        logger.info("🚀 TRADING ACTIVATED!")
        logger.info("=" * 80)
        logger.info(f"Warmup complete: All symbols have {self.min_warmup_bars}+ bars")
        logger.info(f"Total bars collected: {self.total_bars_received}")
        logger.info("Starting adaptive multi-strategy trading...")
        logger.info(f"Rebalancing every {self.rebalance_period} bars")
        logger.info("=" * 80)

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
                            self.bar_count.get(s, 0) for s in self.tickers
                        )
                        logger.info(
                            f"Warmup: {min_bars}/{self.min_warmup_bars} bars "
                            f"(Total: {self.total_bars_received})"
                        )

                        # Show per-symbol counts
                        symbol_counts = ", ".join(
                            f"{s.split('/')[0] if '/' in s else s}:{self.bar_count.get(s, 0)}"
                            for s in self.tickers
                        )
                        logger.info(f"  Per-symbol: {symbol_counts}")
                return

            # Trading is active - run strategy
            orders = self.strategy.process_market_data(tick, self.portfolio)

            # Process orders
            for order in orders:
                # Validate with order manager
                is_valid, reason = self.order_manager.validate_order(
                    order,
                    self.portfolio.cash,
                    self.portfolio.positions,
                    {s: self.data_buffer[s][-1].price for s in self.tickers if self.data_buffer[s]},
                )

                if is_valid:
                    # Submit to Alpaca
                    self._submit_order(order)
                    self.order_manager.record_order(order)
                else:
                    logger.warning(f"Order rejected by risk manager: {reason}")

            # Update portfolio prices
            current_prices = {
                s: self.data_buffer[s][-1].price
                for s in self.tickers
                if self.data_buffer[s]
            }
            self.portfolio.update_prices(current_prices)

            # Log status periodically
            if self.total_bars_received % 100 == 0:
                equity = self.portfolio.get_total_value()
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

            # Use appropriate time in force based on asset type
            time_in_force = TimeInForce.GTC if self.is_crypto else TimeInForce.DAY

            order_request = MarketOrderRequest(
                symbol=order.symbol,
                qty=order.quantity,
                side=alpaca_side,
                time_in_force=time_in_force,
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
        """Start the live trading system."""
        logger.info("=" * 80)
        logger.info(f"LIVE ADAPTIVE TRADER ({self.asset_type.upper()})")
        logger.info("=" * 80)
        logger.info(
            f"Mode: {'📄 PAPER TRADING' if self.paper else '⚠️  LIVE TRADING ⚠️ '}"
        )
        logger.info(f"Initial capital: ${self.initial_cash:,.2f}")
        logger.info(f"Asset type: {self.asset_type}")
        logger.info(f"Tickers: {', '.join(self.tickers)}")
        logger.info("Strategies: 11 (momentum, RSI, BB, VWAP, volume, cross-sectional)")
        logger.info(f"Rebalance: Every {self.rebalance_period} bars")
        logger.info(f"Allocation method: {self.allocation_method}")
        logger.info(f"Min warmup bars: {self.min_warmup_bars}")
        logger.info(f"Save data: {self.save_data}")
        if self.save_data:
            logger.info(f"Data file: {self.data_file}")
        logger.info("=" * 80)
        logger.info("⏳ Starting warmup phase - collecting data before trading...")

        # Subscribe to bars for all tickers
        for ticker in self.tickers:
            self.data_stream.subscribe_bars(self._handle_bar, ticker)

        try:
            # Start streaming
            await self.data_stream._run_forever()

        except KeyboardInterrupt:
            logger.info("🛑 Shutting down gracefully...")

            # Final statistics
            logger.info("=" * 80)
            logger.info("SESSION SUMMARY")
            logger.info("=" * 80)
            logger.info(f"Total bars received: {self.total_bars_received}")
            logger.info(f"Orders submitted: {self.orders_submitted}")
            logger.info(f"Trading was active: {self.trading_active}")

            if self.trading_active:
                equity = self.portfolio.get_total_value()
                pnl = self.portfolio.get_total_pnl()
                ret = (equity - self.initial_cash) / self.initial_cash * 100

                logger.info("PERFORMANCE:")
                logger.info(f"  Final equity: ${equity:,.2f}")
                logger.info(f"  Total P&L: ${pnl:,.2f}")
                logger.info(f"  Return: {ret:.2f}%")

                # Strategy performance
                logger.info("STRATEGY ALLOCATIONS:")
                for name, perf in self.strategy.performance.items():
                    logger.info(
                        f"  {name:<20} {perf.target_allocation * 100:>5.1f}% "
                        f"(P&L: ${perf.total_pnl:>8,.2f})"
                    )

            logger.info("=" * 80)

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
        description="Generic Live Adaptive Trader with Alpaca Streaming",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Paper trading with sector ETFs
  python scripts/traders/live_adaptive_trader.py --tickers XLF XLI XLK XLE

  # Paper trading with crypto
  python scripts/traders/live_adaptive_trader.py --tickers BTC/USD ETH/USD SOL/USD

  # With data saving
  python scripts/traders/live_adaptive_trader.py --tickers XLF XLI --save-data

  # Custom parameters
  python scripts/traders/live_adaptive_trader.py --tickers BTC/USD ETH/USD \\
      --rebalance-period 120 --allocation-method sharpe --min-warmup-bars 10

  # LIVE TRADING (use with caution!)
  python scripts/traders/live_adaptive_trader.py --tickers XLF XLI --live

Environment Variables Required:
  APCA_API_KEY_ID: Your Alpaca API key
  APCA_API_SECRET_KEY: Your Alpaca API secret

  Set these in .env file or export them:
    export APCA_API_KEY_ID="your_key"
    export APCA_API_SECRET_KEY="your_secret"

Note:
  - Crypto tickers must contain "/" (e.g., BTC/USD)
  - Stock tickers don't (e.g., AAPL)
  - Cannot mix stocks and crypto in same run
        """,
    )

    parser.add_argument(
        "--tickers",
        nargs="+",
        required=True,
        help="List of ticker symbols to trade (space-separated)",
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
        "--position-size",
        type=int,
        default=100,
        help="Default position size for strategies (default: 100)",
    )
    parser.add_argument(
        "--max-position",
        type=int,
        default=10,
        help="Max position per symbol for strategies (default: 10)",
    )
    parser.add_argument(
        "--save-data", action="store_true", help="Save streaming data to CSV"
    )
    parser.add_argument(
        "--data-file",
        type=str,
        default="logs/live_data.csv",
        help="File to save data (default: logs/live_data.csv)",
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
            logging.FileHandler("logs/live_adaptive_trader.log"),
        ],
    )

    # Load environment variables
    load_dotenv()

    api_key = os.getenv("APCA_API_KEY_ID")
    api_secret = os.getenv("APCA_API_SECRET_KEY")

    if not api_key or not api_secret:
        print("ERROR: Alpaca API credentials not found!")
        print("Set APCA_API_KEY_ID and APCA_API_SECRET_KEY environment variables")
        print("Either in .env file or export them in your shell")
        sys.exit(1)

    # Warning for live trading
    if args.live:
        print("=" * 80)
        print("⚠️  WARNING: LIVE TRADING MODE ⚠️ ")
        print("=" * 80)
        print("You are about to trade with REAL MONEY!")
        print(f"Initial capital: ${args.initial_cash:,.2f}")
        print(f"Tickers: {', '.join(args.tickers)}")
        print("\nAre you sure you want to continue?")
        response = input("Type 'YES' to confirm: ")
        if response != "YES":
            print("Aborted.")
            sys.exit(0)
        print("=" * 80 + "\n")

    # Create trader
    try:
        trader = LiveAdaptiveTrader(
            tickers=args.tickers,
            api_key=api_key,
            api_secret=api_secret,
            paper=not args.live,
            initial_cash=args.initial_cash,
            rebalance_period=args.rebalance_period,
            allocation_method=args.allocation_method,
            min_warmup_bars=args.min_warmup_bars,
            position_size=args.position_size,
            max_position=args.max_position,
            save_data=args.save_data,
            data_file=args.data_file,
        )
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # Run
    import asyncio

    asyncio.run(trader.run())


if __name__ == "__main__":
    main()
