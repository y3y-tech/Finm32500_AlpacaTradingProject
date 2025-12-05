"""
Live trading system with Alpaca streaming integration.

Provides base LiveTrader class that coordinates:
- Market data streaming (stocks or crypto)
- Portfolio management
- Order execution and risk management
- Data buffering and persistence
- Trading activation after warmup
"""

import asyncio
import logging
import time
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
from alpaca.data.live import CryptoDataStream, StockDataStream
from alpaca.data.models import Bar
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide as AlpacaOrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

from ..models import MarketDataPoint, Order, OrderSide
from .order_manager import OrderManager, RiskConfig
from .portfolio import TradingPortfolio

if TYPE_CHECKING:
    from ..strategies.base import TradingStrategy

logger = logging.getLogger(__name__)


class LiveTrader:
    """
    Base class for live trading with Alpaca streaming API.

    Coordinates all aspects of live trading:
    - Connects to Alpaca streaming (auto-detects stocks vs crypto)
    - Buffers incoming market data
    - Manages portfolio and positions
    - Executes trading strategy
    - Validates and submits orders with risk management
    - Optionally saves streaming data to CSV

    Designed to be instantiated with specific strategy configurations,
    not subclassed.
    """

    def __init__(
        self,
        tickers: list[str],
        strategy: "TradingStrategy",
        api_key: str,
        api_secret: str,
        paper: bool = True,
        initial_cash: float = 10000,
        min_warmup_bars: int = 30,
        save_data: bool = False,
        data_file: str = "logs/live_data.csv",
        save_frequency_bars: int = 50,
        save_frequency_seconds: int = 300,
        risk_config: RiskConfig | None = None,
        close_positions_on_shutdown: bool = False,
    ):
        """
        Initialize live trader.

        Args:
            tickers: List of ticker symbols to trade
            strategy: Trading strategy to execute
            api_key: Alpaca API key
            api_secret: Alpaca API secret
            paper: Use paper trading (True) or live (False)
            initial_cash: Starting capital
            min_warmup_bars: Minimum bars before trading starts
            save_data: Save streaming data to CSV
            data_file: Path to save data file
            save_frequency_bars: Save data every N bars
            save_frequency_seconds: Save data every N seconds
            risk_config: Risk management configuration (uses defaults if None)
            close_positions_on_shutdown: Close all positions on Ctrl-C/shutdown
        """
        self.tickers = tickers
        self.strategy = strategy
        self.api_key = api_key
        self.api_secret = api_secret
        self.paper = paper
        self.initial_cash = initial_cash
        self.min_warmup_bars = min_warmup_bars
        self.save_data = save_data
        self.data_file = data_file
        self.save_frequency_bars = save_frequency_bars
        self.save_frequency_seconds = save_frequency_seconds
        self.close_positions_on_shutdown = close_positions_on_shutdown

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

        # Trading components
        self.trading_active = False
        self.portfolio = TradingPortfolio(initial_cash=initial_cash)
        self.order_manager = OrderManager(
            risk_config=risk_config or self._default_risk_config()
        )

        # Statistics
        self.total_bars_received = 0
        self.orders_submitted = 0
        self.last_save_time = datetime.now()
        self.last_save_bar_count = 0
        self.last_warmup_log_time = 0.0  # Track when we last logged warmup progress

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

    def _default_risk_config(self) -> RiskConfig:
        """Create default risk configuration."""
        return RiskConfig(
            max_position_size=100,
            max_position_value=self.initial_cash * 0.15,
            max_total_exposure=self.initial_cash * 0.90,
            max_orders_per_minute=50,
            max_orders_per_symbol_per_minute=10,
            min_cash_buffer=self.initial_cash * 0.05,
        )

    def _check_warmup_complete(self) -> bool:
        """Check if we have enough data to start trading."""
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
        logger.info("TRADING ACTIVATED")
        logger.info("=" * 80)
        logger.info(f"Warmup complete: All symbols have {self.min_warmup_bars}+ bars")
        logger.info(f"Total bars collected: {self.total_bars_received}")
        logger.info("Starting trading...")
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
                    # Log warmup progress periodically (every 10 seconds)
                    current_time = time.time()
                    if current_time - self.last_warmup_log_time > 10:
                        self.last_warmup_log_time = current_time

                        # Calculate overall progress
                        total_bars = sum(self.bar_count.values())
                        total_needed = len(self.tickers) * self.min_warmup_bars
                        progress_pct = (total_bars / total_needed * 100) if total_needed > 0 else 0

                        # Show per-ticker progress
                        ticker_progress = ", ".join(
                            f"{t}:{self.bar_count.get(t, 0)}/{self.min_warmup_bars}"
                            for t in sorted(self.tickers)[:5]  # Show first 5 tickers
                        )
                        more_tickers = len(self.tickers) - 5
                        if more_tickers > 0:
                            ticker_progress += f" (+{more_tickers} more)"

                        logger.info(
                            f"⏳ Warmup progress: {progress_pct:.1f}% "
                            f"({total_bars}/{total_needed} bars) | {ticker_progress}"
                        )
                return

            # Trading is active - process market data
            orders = self.strategy.on_market_data(tick, self.portfolio)

            # Debug: Log orders received from strategy
            if orders:
                logger.debug(f"📋 Received {len(orders)} order(s) from strategy: {[f'{o.side.value} {o.quantity} {o.symbol}' for o in orders]}")

            # Build current prices dict
            prices = {
                s: self.data_buffer[s][-1].price
                for s in self.tickers
                if self.data_buffer[s]
            }

            # Process orders
            for order in orders:
                # Validate with order manager
                is_valid, reason = self.order_manager.validate_order(
                    order,
                    self.portfolio.cash,
                    self.portfolio.positions,
                    prices,
                )

                if is_valid:
                    # Submit to Alpaca
                    self._submit_order(order)
                    self.order_manager.record_order(order)
                else:
                    logger.warning(f"❌ Order rejected: {reason}")

            # Update portfolio prices
            self.portfolio.update_prices(prices)

            # Periodic data saving
            if self.save_data:
                bars_since_save = self.total_bars_received - self.last_save_bar_count
                seconds_since_save = (
                    datetime.now() - self.last_save_time
                ).total_seconds()

                should_save = (
                    bars_since_save >= self.save_frequency_bars
                    or seconds_since_save >= self.save_frequency_seconds
                )

                if should_save:
                    asyncio.create_task(self._save_data_async())
                    self.last_save_time = datetime.now()
                    self.last_save_bar_count = self.total_bars_received

            # Log status periodically
            if self.total_bars_received % 100 == 0:
                equity = self.portfolio.get_total_value()
                pnl = self.portfolio.get_total_pnl()
                logger.info(
                    f"📊 Bars={self.total_bars_received}, "
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
                f"✅ Order: {order.side.value} {order.quantity} {order.symbol} "
                f"(ID: {response.id})"
            )

            return response

        except Exception as e:
            logger.error(f"❌ Failed to submit order {order}: {e}")
            return None

    async def _save_data_async(self):
        """Asynchronously save buffered data to CSV file."""
        if not self.all_data:
            return

        try:
            await asyncio.get_event_loop().run_in_executor(
                None, self._save_data_to_csv_sync
            )
        except Exception as e:
            logger.error(f"Failed to save data asynchronously: {e}")

    def _save_data_to_csv_sync(self):
        """Synchronous CSV save operation."""
        try:
            df = pd.DataFrame(self.all_data)
            df = df.sort_values("timestamp")

            # Create directory if needed
            Path(self.data_file).parent.mkdir(parents=True, exist_ok=True)

            df.to_csv(self.data_file, index=False)
            logger.debug(f"💾 Saved {len(df)} bars to {self.data_file}")

        except Exception as e:
            logger.error(f"Failed to save data: {e}")

    def _save_data_on_shutdown(self):
        """Save data on shutdown (blocking version)."""
        if not self.all_data:
            logger.info("No data to save")
            return

        try:
            df = pd.DataFrame(self.all_data)
            df = df.sort_values("timestamp")

            Path(self.data_file).parent.mkdir(parents=True, exist_ok=True)

            df.to_csv(self.data_file, index=False)
            logger.info(f"💾 Saved {len(df)} bars to {self.data_file}")

        except Exception as e:
            logger.error(f"Failed to save data: {e}")

    def _close_all_positions(self):
        """Close all open positions via Alpaca API."""
        try:
            # Get all open positions from Alpaca
            positions = self.trading_client.get_all_positions()

            if not positions:
                logger.info("No open positions to close")
                return

            logger.info(f"Closing {len(positions)} open position(s)...")

            for position in positions:
                try:
                    # Close position (Alpaca handles the side automatically)
                    self.trading_client.close_position(position.symbol)
                    logger.info(
                        f"✅ Closed position: {position.symbol} "
                        f"(qty={position.qty}, unrealized_pl=${float(position.unrealized_pl):,.2f})"
                    )
                except Exception as e:
                    logger.error(f"❌ Failed to close {position.symbol}: {e}")

            logger.info("✅ All positions closed")

        except Exception as e:
            logger.error(f"Error closing positions: {e}", exc_info=True)

    def _print_session_summary(self):
        """Print final session statistics."""
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

        logger.info("=" * 80)

    async def run(self):
        """Start the live trading system."""
        logger.info("=" * 80)
        logger.info(f"LIVE TRADER ({self.asset_type.upper()})")
        logger.info("=" * 80)
        logger.info(
            f"Mode: {'📄 PAPER TRADING' if self.paper else '⚠️  LIVE TRADING ⚠️ '}"
        )
        logger.info(f"Initial capital: ${self.initial_cash:,.2f}")
        logger.info(f"Asset type: {self.asset_type}")
        logger.info(f"Tickers: {', '.join(self.tickers)}")
        logger.info(f"Strategy: {type(self.strategy).__name__}")
        logger.info(f"Min warmup bars: {self.min_warmup_bars}")
        logger.info(f"Save data: {self.save_data}")
        if self.save_data:
            logger.info(f"Data file: {self.data_file}")
        logger.info("=" * 80)
        logger.info("⏳ Starting warmup phase - collecting data before trading...")

        # Subscribe to bars for all tickers
        self.data_stream.subscribe_bars(self._handle_bar, *self.tickers)

        try:
            # Start streaming
            await self.data_stream._run_forever()

        except KeyboardInterrupt:
            logger.info("🛑 Shutting down gracefully...")
            self._print_session_summary()

        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            raise

        finally:
            # Close all positions if requested
            if self.close_positions_on_shutdown:
                logger.info("Closing all positions (close_positions_on_shutdown=True)...")
                self._close_all_positions()

            # Save data if enabled
            if self.save_data:
                logger.info("Saving collected data...")
                self._save_data_on_shutdown()

            # Always close the connection properly
            try:
                logger.info("Closing WebSocket connection...")
                await self.data_stream.close()
                logger.info("✅ Connection closed")
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")

            logger.info("✅ Shutdown complete")
