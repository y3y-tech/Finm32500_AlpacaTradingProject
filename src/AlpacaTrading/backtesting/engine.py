"""
Backtesting Engine - Orchestrates full trading simulation.

Integrates all components:
- Data gateway for market data
- Strategy for signal generation
- Order manager for validation
- Matching engine for execution
- Portfolio for tracking
- Order gateway for logging
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import pandas as pd

from AlpacaTrading.models import MarketDataPoint, Order, Trade, OrderType, OrderSide
from AlpacaTrading.gateway.data_gateway import DataGateway
from AlpacaTrading.gateway.order_gateway import OrderGateway
from AlpacaTrading.trading.order_manager import OrderManager, RiskConfig
from AlpacaTrading.trading.matching_engine import MatchingEngine
from AlpacaTrading.trading.portfolio import TradingPortfolio


@dataclass
class BacktestResult:
    """
    Results from a backtest run.

    Attributes:
        portfolio: Final portfolio state
        trades: All executed trades
        performance_metrics: Dict of performance statistics
        equity_curve: DataFrame of portfolio value over time
        order_log_path: Path to order log file
        start_time: Backtest start timestamp
        end_time: Backtest end timestamp
        total_ticks: Number of market data points processed
    """
    portfolio: TradingPortfolio
    trades: list[Trade]
    performance_metrics: dict
    equity_curve: pd.DataFrame
    order_log_path: str
    start_time: datetime
    end_time: datetime
    total_ticks: int


class BacktestEngine:
    """
    Main backtesting engine that orchestrates trading simulation.

    Components:
    1. DataGateway - streams market data
    2. Strategy - generates trading signals
    3. OrderManager - validates orders
    4. MatchingEngine - executes orders
    5. Portfolio - tracks positions and P&L
    6. OrderGateway - logs all order events

    Example:
        # Setup
        data_gateway = DataGateway("data/market_data.csv")
        strategy = MyStrategy()
        engine = BacktestEngine(
            data_gateway=data_gateway,
            strategy=strategy,
            initial_cash=100_000
        )

        # Run backtest
        result = engine.run()

        # Analyze results
        print(f"Total Return: {result.performance_metrics['total_return']:.2f}%")
        print(f"Sharpe Ratio: {result.performance_metrics['sharpe_ratio']:.2f}")
    """

    def __init__(
        self,
        data_gateway: DataGateway,
        strategy: 'TradingStrategy',  # Forward reference
        initial_cash: float,
        risk_config: RiskConfig | None = None,
        matching_engine: MatchingEngine | None = None,
        order_log_file: str = "logs/orders.csv",
        record_equity_frequency: int = 100  # Record equity every N ticks
    ):
        """
        Initialize backtest engine.

        Args:
            data_gateway: Market data source
            strategy: Trading strategy
            initial_cash: Starting capital
            risk_config: Risk management configuration
            matching_engine: Order execution simulator (uses default if None)
            order_log_file: Path to order log CSV
            record_equity_frequency: How often to record equity (in ticks)
        """
        self.data_gateway = data_gateway
        self.strategy = strategy
        self.initial_cash = initial_cash
        self.record_equity_frequency = record_equity_frequency

        # Initialize components
        self.portfolio = TradingPortfolio(initial_cash)
        self.order_manager = OrderManager(risk_config or RiskConfig())
        self.matching_engine = matching_engine or MatchingEngine()
        self.order_gateway = OrderGateway(order_log_file)

        # Current market state
        self.current_prices: dict[str, float] = {}
        self.current_tick: MarketDataPoint | None = None

        # Statistics
        self.tick_count = 0
        self.orders_submitted = 0
        self.orders_rejected = 0

    def run(self, max_ticks: int | None = None) -> BacktestResult:
        """
        Run the backtest simulation.

        Main loop:
        1. Stream market data
        2. Update portfolio with current prices
        3. Strategy generates signals (orders)
        4. Validate orders through order manager
        5. Execute valid orders through matching engine
        6. Process resulting trades
        7. Record equity periodically

        Args:
            max_ticks: Maximum number of ticks to process (None for all)

        Returns:
            BacktestResult with complete performance data
        """
        start_time = datetime.now()
        print(f"Starting backtest at {start_time}")
        print(f"Initial capital: ${self.initial_cash:,.2f}")
        print("-" * 60)

        # Main simulation loop
        for tick in self.data_gateway.stream():
            # Update current market state
            self.current_tick = tick
            self.current_prices[tick.symbol] = tick.price
            self.portfolio.update_prices(self.current_prices)
            self.tick_count += 1

            # Strategy generates orders
            orders = self.strategy.on_market_data(tick, self.portfolio)

            # Process each order
            for order in orders:
                self._process_order(order)

            # Record equity periodically
            if self.tick_count % self.record_equity_frequency == 0:
                self.portfolio.record_equity(tick.timestamp, self.current_prices)

            # Progress update
            if self.tick_count % 10000 == 0:
                self._print_progress()

            # Check max ticks limit
            if max_ticks and self.tick_count >= max_ticks:
                print(f"\nReached max_ticks limit: {max_ticks}")
                break

        # Final equity recording
        if self.current_tick:
            self.portfolio.record_equity(self.current_tick.timestamp, self.current_prices)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Generate results
        print("\n" + "=" * 60)
        print("Backtest Complete!")
        print(f"Duration: {duration:.2f}s")
        print(f"Ticks processed: {self.tick_count:,}")
        print(f"Orders submitted: {self.orders_submitted}")
        print(f"Orders rejected: {self.orders_rejected}")
        print("=" * 60)

        result = self._generate_result(start_time, end_time)
        self._print_summary(result)

        return result

    def _process_order(self, order: Order) -> None:
        """
        Process a single order through validation and execution.

        Args:
            order: Order to process
        """
        # Log order submission
        self.order_gateway.log_order_sent(order)
        self.orders_submitted += 1

        # Validate order
        is_valid, error_msg = self.order_manager.validate_order(
            order,
            self.portfolio.cash,
            self.portfolio.positions,
            self.current_prices
        )

        if not is_valid:
            # Order rejected
            self.order_gateway.log_order_rejected(order, error_msg)
            self.orders_rejected += 1
            return

        # Record order for rate limiting
        self.order_manager.record_order(order)

        # Execute order
        if order.order_type == OrderType.MARKET:
            # Market orders: execute immediately at current price
            market_price = self.current_prices.get(order.symbol, 0.0)
            trades = self.matching_engine.execute_order(order, market_price)
        else:
            # Limit orders: would normally go to order book
            # For simplicity, execute at limit price if marketable
            limit_price = order.price
            trades = self.matching_engine.execute_order(order, limit_price)

        # Process resulting trades
        for trade in trades:
            self.portfolio.process_trade(trade)
            self.order_gateway.log_trade(trade, order)

        # Log final order status
        if order.status.value == "FILLED":
            self.order_gateway.log_order_filled(order)
        elif order.status.value == "PARTIAL":
            self.order_gateway.log_order_partial_fill(
                order,
                order.filled_quantity,
                order.average_fill_price
            )
        elif order.status.value == "CANCELLED":
            self.order_gateway.log_order_cancelled(order, "Simulation cancelled")

    def _print_progress(self) -> None:
        """Print progress update."""
        total_value = self.portfolio.get_total_value()
        pnl = total_value - self.initial_cash
        pnl_pct = (pnl / self.initial_cash) * 100

        print(
            f"Tick {self.tick_count:,} | "
            f"Value: ${total_value:,.2f} | "
            f"P&L: ${pnl:,.2f} ({pnl_pct:+.2f}%) | "
            f"Trades: {len(self.portfolio.trades)}"
        )

    def _generate_result(self, start_time: datetime, end_time: datetime) -> BacktestResult:
        """Generate backtest result object."""
        # Calculate final metrics
        metrics = self.portfolio.get_performance_metrics()

        # Add Sharpe ratio
        metrics['sharpe_ratio'] = self.portfolio.get_sharpe_ratio()

        # Get equity curve
        equity_curve = self.portfolio.get_equity_curve_dataframe()

        return BacktestResult(
            portfolio=self.portfolio,
            trades=self.portfolio.trades,
            performance_metrics=metrics,
            equity_curve=equity_curve,
            order_log_path=str(self.order_gateway.log_file),
            start_time=start_time,
            end_time=end_time,
            total_ticks=self.tick_count
        )

    def _print_summary(self, result: BacktestResult) -> None:
        """Print performance summary."""
        metrics = result.performance_metrics

        print("\n" + "=" * 60)
        print("PERFORMANCE SUMMARY")
        print("=" * 60)
        print(f"Initial Capital:    ${self.initial_cash:,.2f}")
        print(f"Final Value:        ${self.portfolio.get_total_value():,.2f}")
        print(f"Total Return:       {metrics['total_return']:+.2f}%")
        print(f"Total P&L:          ${metrics['total_pnl']:+,.2f}")
        print(f"  Realized:         ${metrics['realized_pnl']:+,.2f}")
        print(f"  Unrealized:       ${metrics['unrealized_pnl']:+,.2f}")
        print()
        print(f"Total Trades:       {metrics['num_trades']}")
        print(f"Winning Trades:     {metrics['winning_trades']}")
        print(f"Losing Trades:      {metrics['losing_trades']}")
        print(f"Win Rate:           {metrics['win_rate']:.2f}%")
        if metrics['avg_win'] > 0:
            print(f"Avg Win:            ${metrics['avg_win']:,.2f}")
        if metrics['avg_loss'] != 0:
            print(f"Avg Loss:           ${metrics['avg_loss']:,.2f}")
        print()
        print(f"Max Drawdown:       {metrics['max_drawdown']:.2f}%")
        print(f"Sharpe Ratio:       {metrics['sharpe_ratio']:.2f}")
        print("=" * 60)
        print(f"\nOrder log saved to: {result.order_log_path}")
