"""
Live Trading Engine - Orchestrates real-time trading with Alpaca.

Integrates strategy execution, risk management, and order execution for live trading.
"""

import logging
import time
import signal
from datetime import datetime
from dataclasses import dataclass

from AlpacaTrading.models import MarketDataPoint, Order, OrderSide, Trade
from AlpacaTrading.strategies.base import TradingStrategy
from AlpacaTrading.trading import (
    TradingPortfolio,
    OrderManager,
    RiskConfig,
    RiskManager,
    StopLossConfig,
)
from AlpacaTrading.gateway.order_gateway import OrderGateway
from AlpacaTrading.live.alpaca_trader import AlpacaTrader, AlpacaConfig

logger = logging.getLogger(__name__)


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
        self.config: LiveEngineConfig = config
        self.strategy: TradingStrategy = strategy

        self.trader: AlpacaTrader = AlpacaTrader(config.alpaca_config)

        account = self.trader.get_account()
        self.portfolio = TradingPortfolio(initial_cash=account["cash"])

        self.order_manager = OrderManager(config.risk_config)

        self.risk_manager = RiskManager(
            config.stop_loss_config, initial_portfolio_value=account["portfolio_value"]
        )

        if config.log_orders:
            self.order_gateway = OrderGateway(config.order_log_path)
        else:
            self.order_gateway = None

        self.current_prices: dict[str, float] = {}

        self.running: bool = False
        self.tick_count: int = 0

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}. Shutting down gracefully...")
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
                    self.portfolio.positions,
                )

                # Execute stop-loss orders immediately
                for order in stop_orders:
                    logger.info(f"\n⚠️  STOP-LOSS TRIGGERED for {order.symbol}")
                    self._execute_order(order, tick.timestamp, is_stop=True)

            # If circuit breaker triggered, don't generate new signals
            if self.risk_manager.circuit_breaker_triggered:
                if self.tick_count % 100 == 0:  # logger.info reminder periodically
                    logger.info("\n🛑 CIRCUIT BREAKER ACTIVE - Trading halted")
                return

            # Pass to strategy for signal generation (with error handling wrapper)
            orders = self.strategy.process_market_data(tick, self.portfolio)

            if not orders:
                return

            # Process each order
            for order in orders:
                self._execute_order(order, tick.timestamp, is_stop=False)

            # Periodically record equity and logger.info status
            self.tick_count += 1
            if self.tick_count % 100 == 0:
                self.portfolio.record_equity(tick.timestamp, self.current_prices)
                self._print_status()

        except Exception as e:
            logger.exception(f"\n❌ Error processing market data: {e}")

    def _execute_order(
        self, order: Order, timestamp: datetime, is_stop: bool = False
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
                    self.current_prices,
                )

                if not is_valid:
                    logger.info(f"\n⛔ Order REJECTED: {reason}")
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
                    logger.info(
                        f"\n✅ Order SUBMITTED: {order.side.value} {order.quantity} {order.symbol} @ {order.order_type.value}"
                    )
                    logger.info(f"\tAlpaca Order ID: {alpaca_order['id']}")

                    # Record order for rate limiting (skip for stops)
                    if not is_stop:
                        self.order_manager.record_order(order)

                    # Poll for fill (simplified - in production use WebSocket trade_updates)
                    self._wait_for_fill(alpaca_order["id"], order)

                except Exception as e:
                    logger.info(f"\n❌ Order FAILED: {e}")
                    if self.order_gateway:
                        self.order_gateway.log_order_rejected(order, str(e))

            else:
                # Dry run mode - simulate fill
                logger.info(
                    f"\n🔍 DRY RUN: {order.side.value} {order.quantity} {order.symbol} @ {order.order_type.value}"
                )
                self._simulate_fill(order, timestamp)

        except Exception as e:
            logger.exception(f"\n❌ Error executing order: {e}")

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

        status = ""
        while time.time() - start_time < timeout:
            alpaca_order = self.trader.get_order(order_id)
            status = alpaca_order["status"]

            if status == "filled":
                # Create trade from fill
                trade = Trade(
                    trade_id=order_id,
                    order_id=order_id,
                    timestamp=alpaca_order["filled_at"],
                    symbol=order.symbol,
                    side=order.side,
                    quantity=alpaca_order["filled_qty"],
                    price=alpaca_order["filled_avg_price"],
                )

                # Update portfolio
                self.portfolio.process_trade(trade)

                # Update risk manager stops
                if self.config.enable_stop_loss and order.side == OrderSide.BUY:
                    self.risk_manager.add_position_stop(
                        symbol=order.symbol,
                        entry_price=trade.price,
                        quantity=trade.quantity,
                    )

                # Log fill
                if self.order_gateway:
                    self.order_gateway.log_order_filled(order, str(trade))

                logger.info(f"\tFILLED: {trade.quantity} @ ${trade.price:.2f}")
                return

            elif status == "partially_filled":
                filled_qty = alpaca_order["filled_qty"]
                logger.info(f"\tPARTIAL FILL: {filled_qty} / {order.quantity}")

            elif status in ("canceled", "expired", "rejected"):
                logger.info(f"\tOrder {status.upper()}")
                if self.order_gateway:
                    self.order_gateway.log_order_cancelled(order)
                return

            time.sleep(0.5)  # Poll every 500ms

        logger.info(f"\t⏱️  Timeout waiting for fill (status: {status})")

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
            price=price,
        )

        self.portfolio.process_trade(trade)

        if self.order_gateway:
            self.order_gateway.log_order_filled(order, str(trade))

    def _print_status(self) -> None:
        """logger.info current engine status."""
        total_value = self.portfolio.get_total_value()
        pnl = self.portfolio.get_total_pnl()
        pnl_pct = (pnl / self.portfolio.initial_cash) * 100

        logger.info(f"\n📊 Status (Tick #{self.tick_count}):")
        logger.info(f"\tPortfolio Value: ${total_value:,.2f}")
        logger.info(f"\tCash: ${self.portfolio.cash:,.2f}")
        logger.info(f"\tP&L: ${pnl:,.2f} ({pnl_pct:+.2f}%)")
        logger.info(f"\tPositions: {len(self.portfolio.positions)}")
        logger.info(f"\tTrades: {len(self.portfolio.trades)}")

        if self.risk_manager.circuit_breaker_triggered:
            logger.info("\t⚠️  Circuit Breaker: TRIGGERED")

    def run(self, symbols: list[str], data_type: str = "trades") -> None:
        """
        Start live trading.

        Args:
            symbols: List of symbols to trade
            data_type: Type of market data ("trades", "quotes", or "bars")

        Note: This is a blocking call. Press Ctrl+C to stop.
        """
        logger.info("=" * 60)
        logger.info("LIVE TRADING ENGINE")
        logger.info("=" * 60)
        logger.info(f"Mode: {'PAPER' if self.config.alpaca_config.paper else 'LIVE'}")
        logger.info(
            f"Trading: {'ENABLED' if self.config.enable_trading else 'DRY RUN'}"
        )
        logger.info(f"Strategy: {self.strategy.__class__.__name__}")
        logger.info(f"Symbols: {', '.join(symbols)}")
        logger.info(f"Data Type: {data_type}")
        logger.info("=" * 60)

        # Call strategy initialization
        self.strategy.on_start(self.portfolio)

        # Sync positions from Alpaca
        self._sync_positions()

        logger.info("\n🚀 Starting market data stream...")
        logger.info("Press Ctrl+C to stop\n")

        self.running = True

        try:
            # Start streaming (blocking call)
            logger.debug("starting streaming")
            self.trader.start_streaming(
                symbols=symbols, callback=self._on_market_data, data_type=data_type
            )
        except KeyboardInterrupt:
            logger.info("\n\n⏹️  Keyboard interrupt received")
            self.stop()
        except Exception as e:
            logger.exception(f"\n\n❌ Fatal error: {e}")
            self.stop()

    def _sync_positions(self) -> None:
        """Sync existing Alpaca positions to portfolio."""
        positions = self.trader.get_positions()

        if positions:
            logger.info(
                f"📦 Syncing {len(positions)} existing positions from Alpaca..."
            )
            for pos in positions:
                logger.info(
                    f"\t{pos['symbol']}: {pos['quantity']} @ ${pos['avg_entry_price']:.2f}"
                )

                # Create synthetic trade to populate portfolio
                # Note: This is a simplification - in production, track position history properly
                trade = Trade(
                    trade_id=f"sync_{pos['symbol']}",
                    order_id=f"sync_{pos['symbol']}",
                    timestamp=datetime.now(),
                    symbol=pos["symbol"],
                    side=OrderSide.BUY if pos["side"] == "long" else OrderSide.SELL,
                    quantity=abs(pos["quantity"]),
                    price=pos["avg_entry_price"],
                )
                self.portfolio.process_trade(trade)

                # Add stop-loss for existing position
                if self.config.enable_stop_loss:
                    self.risk_manager.add_position_stop(
                        symbol=pos["symbol"],
                        entry_price=pos["avg_entry_price"],
                        quantity=pos["quantity"],
                    )

    def stop(self) -> None:
        """Stop live trading and clean up."""
        if not self.running:
            return

        logger.info("\n" + "=" * 60)
        logger.info("SHUTTING DOWN")
        logger.info("=" * 60)

        self.running = False

        # Stop streaming
        logger.info("Stopping market data stream...")
        self.trader.stop_streaming()

        # Call strategy cleanup
        self.strategy.on_end()  # TODO: figure ts out man

        # TODO: write portfolio.log_metric or whatever
        logger.info("\n📈 FINAL PERFORMANCE:")
        metrics = self.portfolio.get_performance_metrics()
        logger.info(f"\tTotal Return: {metrics['total_return']:+.2f}%")
        logger.info(f"\tTotal P&L: ${metrics['total_pnl']:,.2f}")
        logger.info(f"\tRealized P&L: ${metrics['realized_pnl']:,.2f}")
        logger.info(f"\tUnrealized P&L: ${metrics['unrealized_pnl']:,.2f}")
        logger.info(f"\tTotal Trades: {metrics['num_trades']}")
        logger.info(f"\tWin Rate: {metrics['win_rate']:.1f}%")
        logger.info(f"\tMax Drawdown: {metrics['max_drawdown']:.2f}%")

        # logger.info positions
        if self.portfolio.positions:
            logger.info("\n📦 OPEN POSITIONS:")
            for symbol, pos in self.portfolio.positions.items():
                if pos.quantity != 0:
                    logger.info(
                        f"\t{symbol}: {pos.quantity} @ ${pos.average_cost:.2f} (P&L: ${pos.total_pnl:+,.2f})"
                    )

        logger.info("\n✅ Shutdown complete")
        logger.info("=" * 60 + "\n")

    def __repr__(self) -> str:
        status = "RUNNING" if self.running else "STOPPED"
        return f"LiveTradingEngine(status={status}, ticks={self.tick_count})"
