"""
Comprehensive tests for safety features:
1. Portfolio metrics logging
2. Stop-loss manager
3. Circuit breaker
4. Integration with trading system
"""

import unittest
from datetime import datetime
from pathlib import Path
import tempfile
import csv
import uuid

from AlpacaTrading.trading import (
    TradingPortfolio,
    RiskManager,
    StopLossConfig,
)
from AlpacaTrading.models import (
    Trade,
    OrderSide,
)


def create_trade(symbol: str, side: OrderSide, quantity: float, price: float) -> Trade:
    """Helper to create a Trade with correct parameters."""
    return Trade(
        trade_id=str(uuid.uuid4()),
        order_id=str(uuid.uuid4()),
        timestamp=datetime.now(),
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
    )


class TestPortfolioLogging(unittest.TestCase):
    """Test portfolio.log_metrics() functionality."""

    def setUp(self):
        """Set up test portfolio."""
        self.portfolio = TradingPortfolio(initial_cash=100_000)
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = str(Path(self.temp_dir) / "test_metrics.csv")

    def test_log_metrics_creates_file(self):
        """Test that log_metrics creates a CSV file."""
        self.portfolio.log_metrics(self.log_file)

        # Check file exists
        self.assertTrue(Path(self.log_file).exists())

    def test_log_metrics_has_header(self):
        """Test that CSV has correct header row."""
        self.portfolio.log_metrics(self.log_file)

        with open(self.log_file, "r") as f:
            reader = csv.reader(f)
            header = next(reader)

        expected_headers = [
            "timestamp",
            "cash",
            "total_value",
            "total_return_%",
            "total_pnl",
            "realized_pnl",
            "unrealized_pnl",
            "num_positions",
            "num_trades",
            "win_rate_%",
            "max_drawdown_%",
            "current_drawdown_%",
        ]

        self.assertEqual(header, expected_headers)

    def test_log_metrics_appends_rows(self):
        """Test that multiple logs append (don't overwrite)."""
        # Log 3 times
        self.portfolio.log_metrics(self.log_file)
        self.portfolio.log_metrics(self.log_file)
        self.portfolio.log_metrics(self.log_file)

        with open(self.log_file, "r") as f:
            rows = list(csv.reader(f))

        # Should have header + 3 data rows
        self.assertEqual(len(rows), 4)

    def test_log_metrics_correct_values(self):
        """Test that logged values are correct."""
        # Execute a trade
        trade = create_trade("AAPL", OrderSide.BUY, 10, 150.0)
        self.portfolio.process_trade(trade)

        # Log metrics
        self.portfolio.log_metrics(self.log_file)

        # Read logged data
        with open(self.log_file, "r") as f:
            reader = csv.reader(f)
            next(reader)  # Skip header
            data_row = next(reader)

        # Verify values
        cash = float(data_row[1])
        total_value = float(data_row[2])
        num_positions = int(data_row[7])
        num_trades = int(data_row[8])

        self.assertEqual(cash, 98_500.0)  # 100k - 1500
        self.assertEqual(total_value, 100_000.0)  # Still same (no P&L yet)
        self.assertEqual(num_positions, 1)
        self.assertEqual(num_trades, 1)


class TestRiskManagerStopLoss(unittest.TestCase):
    """Test RiskManager stop-loss functionality."""

    def setUp(self):
        """Set up risk manager and portfolio."""
        self.config = StopLossConfig(
            position_stop_pct=5.0,
            trailing_stop_pct=7.0,
            portfolio_stop_pct=10.0,
            max_drawdown_pct=15.0,
            use_trailing_stops=False,
            enable_circuit_breaker=False,  # Test stops independently
        )
        self.risk_manager = RiskManager(self.config, initial_portfolio_value=100_000)
        self.portfolio = TradingPortfolio(initial_cash=100_000)

    def test_add_position_stop(self):
        """Test adding a stop for a position."""
        self.risk_manager.add_position_stop(
            symbol="AAPL", entry_price=150.0, quantity=100
        )

        self.assertIn("AAPL", self.risk_manager.position_stops)
        stop = self.risk_manager.position_stops["AAPL"]

        self.assertEqual(stop.entry_price, 150.0)
        self.assertAlmostEqual(stop.stop_price, 150.0 * 0.95, places=2)  # 5% stop

    def test_stop_not_triggered_small_loss(self):
        """Test that stop doesn't trigger on small loss."""
        # Add position
        trade = create_trade("AAPL", OrderSide.BUY, 100, 150.0)
        self.portfolio.process_trade(trade)
        self.risk_manager.add_position_stop("AAPL", 150.0, 100)

        # Price drops 3% (not enough to trigger 5% stop)
        current_prices = {"AAPL": 145.5}
        exit_orders = self.risk_manager.check_stops(
            current_prices=current_prices,
            portfolio_value=self.portfolio.get_total_value(),
            positions=self.portfolio.positions,
        )

        self.assertEqual(len(exit_orders), 0)

    def test_stop_triggered_large_loss(self):
        """Test that stop triggers on large loss."""
        # Add position
        trade = create_trade("AAPL", OrderSide.BUY, 100, 150.0)
        self.portfolio.process_trade(trade)
        self.risk_manager.add_position_stop("AAPL", 150.0, 100)

        # Price drops 6% (triggers 5% stop)
        current_prices = {"AAPL": 141.0}
        exit_orders = self.risk_manager.check_stops(
            current_prices=current_prices,
            portfolio_value=self.portfolio.get_total_value(),
            positions=self.portfolio.positions,
        )

        self.assertEqual(len(exit_orders), 1)
        self.assertEqual(exit_orders[0].symbol, "AAPL")
        self.assertEqual(exit_orders[0].side, OrderSide.SELL)
        self.assertEqual(exit_orders[0].quantity, 100)

    def test_trailing_stop_moves_up(self):
        """Test that trailing stop moves up with profitable position."""
        config = StopLossConfig(
            position_stop_pct=5.0,
            trailing_stop_pct=7.0,
            use_trailing_stops=True,
            enable_circuit_breaker=False,
        )
        risk_manager = RiskManager(config, 100_000)

        # Add position
        trade = create_trade("TSLA", OrderSide.BUY, 50, 200.0)
        self.portfolio.process_trade(trade)
        risk_manager.add_position_stop("TSLA", 200.0, 50)

        initial_stop = risk_manager.position_stops["TSLA"].stop_price
        self.assertAlmostEqual(initial_stop, 200.0 * 0.93, places=2)  # 7% trailing

        # Price increases
        current_prices = {"TSLA": 220.0}
        risk_manager.check_stops(
            current_prices=current_prices,
            portfolio_value=self.portfolio.get_total_value(),
            positions=self.portfolio.positions,
        )

        new_stop = risk_manager.position_stops["TSLA"].stop_price
        self.assertGreater(new_stop, initial_stop)  # Stop moved up
        self.assertAlmostEqual(new_stop, 220.0 * 0.93, places=2)

    def test_trailing_stop_triggers_on_reversal(self):
        """Test trailing stop triggers when price reverses."""
        config = StopLossConfig(
            position_stop_pct=5.0,
            trailing_stop_pct=7.0,
            use_trailing_stops=True,
            enable_circuit_breaker=False,
        )
        risk_manager = RiskManager(config, 100_000)

        # Add position
        trade = create_trade("TSLA", OrderSide.BUY, 50, 200.0)
        self.portfolio.process_trade(trade)
        risk_manager.add_position_stop("TSLA", 200.0, 50)

        # Price increases to 230
        risk_manager.check_stops(
            current_prices={"TSLA": 230.0},
            portfolio_value=self.portfolio.get_total_value(),
            positions=self.portfolio.positions,
        )

        # Now price drops to 213 (below 7% trailing stop from 230)
        exit_orders = risk_manager.check_stops(
            current_prices={"TSLA": 213.0},
            portfolio_value=self.portfolio.get_total_value(),
            positions=self.portfolio.positions,
        )

        # Should trigger stop
        self.assertEqual(len(exit_orders), 1)


class TestCircuitBreaker(unittest.TestCase):
    """Test circuit breaker functionality."""

    def setUp(self):
        """Set up risk manager with circuit breaker."""
        self.config = StopLossConfig(
            position_stop_pct=10.0,  # High (won't trigger)
            portfolio_stop_pct=5.0,  # 5% portfolio stop
            max_drawdown_pct=10.0,  # 10% max drawdown
            use_trailing_stops=False,
            enable_circuit_breaker=True,
        )
        self.risk_manager = RiskManager(self.config, initial_portfolio_value=100_000)
        self.portfolio = TradingPortfolio(initial_cash=100_000)

    def test_circuit_breaker_not_triggered_small_loss(self):
        """Test circuit breaker doesn't trigger on small loss."""
        # Portfolio drops 3% (not enough for 5% limit)
        exit_orders = self.risk_manager.check_stops(
            current_prices={},
            portfolio_value=97_000,
            positions=self.portfolio.positions,
        )

        self.assertEqual(len(exit_orders), 0)
        self.assertFalse(self.risk_manager.circuit_breaker_triggered)

    def test_circuit_breaker_triggers_daily_loss(self):
        """Test circuit breaker triggers on daily loss limit."""
        # Portfolio drops 6% (exceeds 5% limit)
        exit_orders = self.risk_manager.check_stops(
            current_prices={},
            portfolio_value=94_000,
            positions=self.portfolio.positions,
        )

        # Circuit breaker should trigger (though no positions to exit)
        self.assertTrue(self.risk_manager.circuit_breaker_triggered)

    def test_circuit_breaker_triggers_max_drawdown(self):
        """Test circuit breaker triggers on max drawdown."""
        # Simulate portfolio growth then drawdown
        self.risk_manager.high_water_mark = 110_000  # Portfolio was at 110k

        # Now portfolio at 98k = 10.9% drawdown (exceeds 10% limit)
        exit_orders = self.risk_manager.check_stops(
            current_prices={},
            portfolio_value=98_000,
            positions=self.portfolio.positions,
        )

        self.assertTrue(self.risk_manager.circuit_breaker_triggered)

    def test_circuit_breaker_exits_all_positions(self):
        """Test that circuit breaker exits ALL positions."""
        # Add multiple positions
        for symbol, price in [("AAPL", 150.0), ("MSFT", 300.0), ("GOOGL", 2800.0)]:
            trade = create_trade(symbol, OrderSide.BUY, 10, price)
            self.portfolio.process_trade(trade)

        # Trigger circuit breaker with 6% loss
        current_prices = {"AAPL": 150.0, "MSFT": 300.0, "GOOGL": 2800.0}
        exit_orders = self.risk_manager.check_stops(
            current_prices=current_prices,
            portfolio_value=94_000,  # 6% loss
            positions=self.portfolio.positions,
        )

        # Should exit all 3 positions
        self.assertEqual(len(exit_orders), 3)
        symbols = {order.symbol for order in exit_orders}
        self.assertEqual(symbols, {"AAPL", "MSFT", "GOOGL"})

    def test_circuit_breaker_reset(self):
        """Test manual circuit breaker reset."""
        # Trigger breaker
        self.risk_manager.check_stops(
            current_prices={},
            portfolio_value=94_000,
            positions=self.portfolio.positions,
        )
        self.assertTrue(self.risk_manager.circuit_breaker_triggered)

        # Reset
        self.risk_manager.reset_circuit_breaker()
        self.assertFalse(self.risk_manager.circuit_breaker_triggered)


class TestRiskManagerIntegration(unittest.TestCase):
    """Integration tests for RiskManager with portfolio."""

    def test_full_workflow_with_stop_trigger(self):
        """Test complete workflow: enter position, trigger stop, exit."""
        # Setup
        config = StopLossConfig(position_stop_pct=5.0, enable_circuit_breaker=False)
        risk_manager = RiskManager(config, 100_000)
        portfolio = TradingPortfolio(100_000)

        # Enter position
        entry_trade = create_trade("AAPL", OrderSide.BUY, 100, 150.0)
        portfolio.process_trade(entry_trade)
        risk_manager.add_position_stop("AAPL", 150.0, 100)

        # Check position exists
        self.assertEqual(portfolio.positions["AAPL"].quantity, 100)

        # Price drops, trigger stop
        current_prices = {"AAPL": 140.0}
        exit_orders = risk_manager.check_stops(
            current_prices, portfolio.get_total_value(), portfolio.positions
        )

        # Execute exit
        self.assertEqual(len(exit_orders), 1)
        exit_trade = create_trade("AAPL", OrderSide.SELL, 100, 140.0)
        portfolio.process_trade(exit_trade)

        # Verify position closed
        self.assertEqual(portfolio.positions["AAPL"].quantity, 0)

        # Verify loss recorded
        self.assertLess(portfolio.get_realized_pnl(), 0)

    def test_multiple_positions_independent_stops(self):
        """Test that each position has independent stop-loss."""
        config = StopLossConfig(position_stop_pct=5.0, enable_circuit_breaker=False)
        risk_manager = RiskManager(config, 100_000)
        portfolio = TradingPortfolio(100_000)

        # Enter 3 positions
        positions = [("AAPL", 150.0), ("MSFT", 300.0), ("GOOGL", 2800.0)]

        for symbol, price in positions:
            trade = create_trade(symbol, OrderSide.BUY, 10, price)
            portfolio.process_trade(trade)
            risk_manager.add_position_stop(symbol, price, 10)

        # Only AAPL drops enough to trigger stop
        current_prices = {"AAPL": 140.0, "MSFT": 295.0, "GOOGL": 2750.0}

        exit_orders = risk_manager.check_stops(
            current_prices, portfolio.get_total_value(), portfolio.positions
        )

        # Only AAPL should exit
        self.assertEqual(len(exit_orders), 1)
        self.assertEqual(exit_orders[0].symbol, "AAPL")


def run_safety_tests():
    """Run all safety feature tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestPortfolioLogging))
    suite.addTests(loader.loadTestsFromTestCase(TestRiskManagerStopLoss))
    suite.addTests(loader.loadTestsFromTestCase(TestCircuitBreaker))
    suite.addTests(loader.loadTestsFromTestCase(TestRiskManagerIntegration))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    import sys

    success = run_safety_tests()
    sys.exit(0 if success else 1)
