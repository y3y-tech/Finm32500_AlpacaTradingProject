"""
Live Trading Engine - Orchestrates real-time trading with Alpaca.

Integrates strategy execution, risk management, and order execution for live trading.
"""

import time
import signal
from datetime import datetime
from dataclasses import dataclass

from src.models import MarketDataPoint, Order, OrderSide, Trade
from src.strategies.base import TradingStrategy
from src.trading import (
    TradingPortfolio,
    OrderManager,
    RiskConfig,
    RiskManager,
    StopLossConfig
)
from src.gateway.order_gateway import OrderGateway
from src.live.alpaca_trader import AlpacaTrader, AlpacaConfig


@dataclass
class LiveEngineConfig:
    """
    Configuration for live trading engine.

    Attributes:
        alpaca_config: Alpaca API configuration
        risk_config: Order validation risk limits
        stop_loss_config: Stop-loss risk management
        enable_trading: Enable actual order submission (default: True)
        enable_stop_loss: Enable stop-loss management (default: True)
        log_orders: Enable order logging to CSV (default: True)
        order_log_path: Path for order log CSV (default: "live_orders.csv")
    """
    alpaca_config: AlpacaConfig
    risk_config: RiskConfig
    stop_loss_config: StopLossConfig
    enable_trading: bool = True
    enable_stop_loss: bool = True
    log_orders: bool = True
    order_log_path: str = "live_orders.csv"


class LiveTradingEngine:
    """
    Real-time trading engine for live execution with Alpaca.

    Workflow:
    1. Receives real-time market data from Alpaca WebSocket
    2. Passes data to strategy for signal generation
    3. Validates orders through OrderManager (risk checks)
    4. Checks stop-loss conditions via RiskManager
    5. Submits valid orders to Alpaca
    6. Tracks positions and P&L in Portfolio
    7. Logs all events for audit trail

    Example:
        # Configure
        alpaca_config = AlpacaConfig.from_env()
        risk_config = RiskConfig(max_position_size=1000, ...)
        stop_config = StopLossConfig(position_stop_pct=2.0, ...)

        config = LiveEngineConfig(
            alpaca_config=alpaca_config,
            risk_config=risk_config,
            stop_loss_config=stop_config
        )

        # Initialize
        strategy = MomentumStrategy(...)
        engine = LiveTradingEngine(config, strategy)

        # Start trading
        engine.run(symbols=["AAPL", "MSFT"])
    """

    def __init__(
        self,
        config: LiveEngineConfig,
        strategy: TradingStrategy,
    ):
        """
        Initialize live trading engine.

        Args:
            config: Engine configuration
            strategy: Trading strategy to execute
        """
        self.config = config
        self.strategy = strategy

        # Initialize Alpaca trader
        self.trader = AlpacaTrader(config.alpaca_config)

        # Get initial account info and create portfolio
        account = self.trader.get_account()
        self.portfolio = TradingPortfolio(initial_cash=account["cash"])

        # Initialize order manager
        self.order_manager = OrderManager(config.risk_config)

        # Initialize risk manager (stop-loss)
        self.risk_manager = RiskManager(
            config.stop_loss_config,
            initial_portfolio_value=account["portfolio_value"]
        )

        # Initialize order gateway for logging
        if config.log_orders:
            self.order_gateway = OrderGateway(config.order_log_path)
        else:
            self.order_gateway = None

        # Track current prices for all symbols
        self.current_prices: dict[str, float] = {}

        # Control flags
        self.running = False
        self.tick_count = 0

        # Set up graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        print(f"\n\nReceived signal {signum}. Shutting down gracefully...")
        self.stop()

    def _on_market_data(self, tick: MarketDataPoint) -> None:
        """
        Handle incoming market data tick.

        Args:
            tick: Market data point from Alpaca
        """
        try:
            # Update current prices
            self.current_prices[tick.symbol] = tick.price

            # Update portfolio unrealized P&L
            self.portfolio.update_prices(self.current_prices)

            # Check stop-loss conditions first
            if self.config.enable_stop_loss:
                stop_orders = self.risk_manager.check_stops(
                    self.current_prices,
                    self.portfolio.get_total_value(),
                    self.portfolio.positions
                )

                # Execute stop-loss orders immediately
                for order in stop_orders:
                    print(f"\n⚠️  STOP-LOSS TRIGGERED for {order.symbol}")
                    self._execute_order(order, tick.timestamp, is_stop=True)

            # If circuit breaker triggered, don't generate new signals
            if self.risk_manager.circuit_breaker_triggered:
                if self.tick_count % 100 == 0:  # Print reminder periodically
                    print("\n🛑 CIRCUIT BREAKER ACTIVE - Trading halted")
                return

            # Pass to strategy for signal generation
            orders = self.strategy.on_market_data(tick, self.portfolio)

            if not orders:
                return

            # Process each order
            for order in orders:
                self._execute_order(order, tick.timestamp, is_stop=False)

            # Periodically record equity and print status
            self.tick_count += 1
            if self.tick_count % 100 == 0:
                self.portfolio.record_equity(tick.timestamp, self.current_prices)
                self._print_status()

        except Exception as e:
            print(f"\n❌ Error processing market data: {e}")
            import traceback
            traceback.print_exc()

    def _execute_order(
        self,
        order: Order,
        timestamp: datetime,
        is_stop: bool = False
    ) -> None:
        """
        Execute order with validation and logging.

        Args:
            order: Order to execute
            timestamp: Current timestamp
            is_stop: Whether this is a stop-loss order (skip some checks)
        """
        try:
            # Validate order (skip for stop-loss orders)
            if not is_stop:
                is_valid, reason = self.order_manager.validate_order(
                    order,
                    self.portfolio.cash,
                    self.portfolio.positions,
                    self.current_prices
                )

                if not is_valid:
                    print(f"\n⛔ Order REJECTED: {reason}")
                    if self.order_gateway:
                        self.order_gateway.log_order_rejected(order, reason)
                    return

            # Log order sent
            if self.order_gateway:
                self.order_gateway.log_order_sent(order)

            # Submit to Alpaca (if trading enabled)
            if self.config.enable_trading:
                try:
                    alpaca_order = self.trader.submit_order(order)
                    print(f"\n✅ Order SUBMITTED: {order.side.value} {order.quantity} {order.symbol} @ {order.order_type.value}")
                    print(f"   Alpaca Order ID: {alpaca_order['id']}")

                    # Record order for rate limiting (skip for stops)
                    if not is_stop:
                        self.order_manager.record_order(order.symbol, timestamp)

                    # Poll for fill (simplified - in production use WebSocket trade_updates)
                    self._wait_for_fill(alpaca_order['id'], order)

                except Exception as e:
                    print(f"\n❌ Order FAILED: {e}")
                    if self.order_gateway:
                        self.order_gateway.log_order_rejected(order, str(e))

            else:
                # Dry run mode - simulate fill
                print(f"\n🔍 DRY RUN: {order.side.value} {order.quantity} {order.symbol} @ {order.order_type.value}")
                self._simulate_fill(order, timestamp)

        except Exception as e:
            print(f"\n❌ Error executing order: {e}")
            import traceback
            traceback.print_exc()

    def _wait_for_fill(self, order_id: str, order: Order, timeout: int = 10) -> None:
        """
        Wait for order to fill (simplified polling).

        In production, use WebSocket trade_updates stream instead.

        Args:
            order_id: Alpaca order ID
            order: Our order object
            timeout: Max seconds to wait
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            alpaca_order = self.trader.get_order(order_id)
            status = alpaca_order['status']

            if status == 'filled':
                # Create trade from fill
                trade = Trade(
                    trade_id=order_id,
                    order_id=order_id,
                    timestamp=alpaca_order['filled_at'],
                    symbol=order.symbol,
                    side=order.side,
                    quantity=alpaca_order['filled_qty'],
                    price=alpaca_order['filled_avg_price']
                )

                # Update portfolio
                self.portfolio.process_trade(trade)

                # Update risk manager stops
                if self.config.enable_stop_loss and order.side == OrderSide.BUY:
                    self.risk_manager.add_position_stop(
                        symbol=order.symbol,
                        entry_price=trade.price,
                        quantity=trade.quantity
                    )

                # Log fill
                if self.order_gateway:
                    self.order_gateway.log_order_filled(order, trade)

                print(f"   FILLED: {trade.quantity} @ ${trade.price:.2f}")
                return

            elif status == 'partially_filled':
                filled_qty = alpaca_order['filled_qty']
                print(f"   PARTIAL FILL: {filled_qty} / {order.quantity}")

            elif status in ('canceled', 'expired', 'rejected'):
                print(f"   Order {status.upper()}")
                if self.order_gateway:
                    self.order_gateway.log_order_cancelled(order)
                return

            time.sleep(0.5)  # Poll every 500ms

        print(f"   ⏱️  Timeout waiting for fill (status: {status})")

    def _simulate_fill(self, order: Order, timestamp: datetime) -> None:
        """
        Simulate order fill for dry run mode.

        Args:
            order: Order to simulate
            timestamp: Current timestamp
        """
        # Use current market price
        price = self.current_prices.get(order.symbol, order.price or 0)

        trade = Trade(
            trade_id=f"sim_{timestamp.timestamp()}",
            order_id=order.order_id,
            timestamp=timestamp,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=price
        )

        self.portfolio.process_trade(trade)

        if self.order_gateway:
            self.order_gateway.log_order_filled(order, trade)

    def _print_status(self) -> None:
        """Print current engine status."""
        total_value = self.portfolio.get_total_value()
        pnl = self.portfolio.get_total_pnl()
        pnl_pct = (pnl / self.portfolio.initial_cash) * 100

        print(f"\n📊 Status (Tick #{self.tick_count}):")
        print(f"   Portfolio Value: ${total_value:,.2f}")
        print(f"   Cash: ${self.portfolio.cash:,.2f}")
        print(f"   P&L: ${pnl:,.2f} ({pnl_pct:+.2f}%)")
        print(f"   Positions: {len(self.portfolio.positions)}")
        print(f"   Trades: {len(self.portfolio.trades)}")

        if self.risk_manager.circuit_breaker_triggered:
            print(f"   ⚠️  Circuit Breaker: TRIGGERED")

    def run(
        self,
        symbols: list[str],
        data_type: str = "trades"
    ) -> None:
        """
        Start live trading.

        Args:
            symbols: List of symbols to trade
            data_type: Type of market data ("trades", "quotes", or "bars")

        Note: This is a blocking call. Press Ctrl+C to stop.
        """
        print("=" * 60)
        print("LIVE TRADING ENGINE")
        print("=" * 60)
        print(f"Mode: {'PAPER' if self.config.alpaca_config.paper else 'LIVE'}")
        print(f"Trading: {'ENABLED' if self.config.enable_trading else 'DRY RUN'}")
        print(f"Strategy: {self.strategy.__class__.__name__}")
        print(f"Symbols: {', '.join(symbols)}")
        print(f"Data Type: {data_type}")
        print("=" * 60)

        # Call strategy initialization
        self.strategy.on_start(self.portfolio)

        # Sync positions from Alpaca
        self._sync_positions()

        print("\n🚀 Starting market data stream...")
        print("Press Ctrl+C to stop\n")

        self.running = True

        try:
            # Start streaming (blocking call)
            self.trader.start_streaming(
                symbols=symbols,
                callback=self._on_market_data,
                data_type=data_type
            )
        except KeyboardInterrupt:
            print("\n\n⏹️  Keyboard interrupt received")
            self.stop()
        except Exception as e:
            print(f"\n\n❌ Fatal error: {e}")
            import traceback
            traceback.print_exc()
            self.stop()

    def _sync_positions(self) -> None:
        """Sync existing Alpaca positions to portfolio."""
        positions = self.trader.get_positions()

        if positions:
            print(f"\n📦 Syncing {len(positions)} existing positions from Alpaca...")
            for pos in positions:
                print(f"   {pos['symbol']}: {pos['quantity']} @ ${pos['avg_entry_price']:.2f}")

                # Create synthetic trade to populate portfolio
                # Note: This is a simplification - in production, track position history properly
                trade = Trade(
                    trade_id=f"sync_{pos['symbol']}",
                    order_id=f"sync_{pos['symbol']}",
                    timestamp=datetime.now(),
                    symbol=pos['symbol'],
                    side=OrderSide.BUY if pos['side'] == 'long' else OrderSide.SELL,
                    quantity=abs(pos['quantity']),
                    price=pos['avg_entry_price']
                )
                self.portfolio.process_trade(trade)

                # Add stop-loss for existing position
                if self.config.enable_stop_loss:
                    self.risk_manager.add_position_stop(
                        symbol=pos['symbol'],
                        entry_price=pos['avg_entry_price'],
                        quantity=pos['quantity']
                    )

    def stop(self) -> None:
        """Stop live trading and clean up."""
        if not self.running:
            return

        print("\n" + "=" * 60)
        print("SHUTTING DOWN")
        print("=" * 60)

        self.running = False

        # Stop streaming
        print("Stopping market data stream...")
        self.trader.stop_streaming()

        # Call strategy cleanup
        self.strategy.on_end()

        # Print final performance
        print("\n📈 FINAL PERFORMANCE:")
        metrics = self.portfolio.get_performance_metrics()
        print(f"   Total Return: {metrics['total_return']:+.2f}%")
        print(f"   Total P&L: ${metrics['total_pnl']:,.2f}")
        print(f"   Realized P&L: ${metrics['realized_pnl']:,.2f}")
        print(f"   Unrealized P&L: ${metrics['unrealized_pnl']:,.2f}")
        print(f"   Total Trades: {metrics['num_trades']}")
        print(f"   Win Rate: {metrics['win_rate']:.1f}%")
        print(f"   Max Drawdown: {metrics['max_drawdown']:.2f}%")

        # Print positions
        if self.portfolio.positions:
            print("\n📦 OPEN POSITIONS:")
            for symbol, pos in self.portfolio.positions.items():
                if pos.quantity != 0:
                    print(f"   {symbol}: {pos.quantity} @ ${pos.average_cost:.2f} (P&L: ${pos.total_pnl:+,.2f})")

        print("\n✅ Shutdown complete")
        print("=" * 60 + "\n")

    def __repr__(self) -> str:
        status = "RUNNING" if self.running else "STOPPED"
        return f"LiveTradingEngine(status={status}, ticks={self.tick_count})"
