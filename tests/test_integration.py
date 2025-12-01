"""
Integration tests for the trading system.

Tests that all components work together correctly.
"""

import pytest
from datetime import datetime
from pathlib import Path
import tempfile

from AlpacaTrading.models import Order, OrderSide, OrderType, MarketDataPoint, Trade
from AlpacaTrading.gateway.data_gateway import DataGateway
from AlpacaTrading.trading.order_manager import OrderManager, RiskConfig
from AlpacaTrading.trading.matching_engine import MatchingEngine
from AlpacaTrading.trading.portfolio import TradingPortfolio
from AlpacaTrading.strategies.momentum import MomentumStrategy
from AlpacaTrading.backtesting.engine import BacktestEngine


class TestTradingSystemIntegration:
    """Integration tests for complete trading system."""

    def test_order_lifecycle(self):
        """Test complete order lifecycle from creation to execution."""
        # Create order
        order = Order(
            symbol="TEST", side=OrderSide.BUY, order_type=OrderType.MARKET, quantity=10
        )

        assert order.status.value == "NEW"
        assert order.filled_quantity == 0

        # Execute with matching engine
        engine = MatchingEngine(
            fill_probability=1.0,  # Always fill for test
            partial_fill_probability=0.0,
            cancel_probability=0.0,
        )

        trades = engine.execute_order(order, market_price=100.0)

        assert len(trades) == 1
        assert trades[0].quantity == 10
        assert order.is_filled

    def test_portfolio_trade_processing(self):
        """Test portfolio processes trades correctly."""
        portfolio = TradingPortfolio(initial_cash=10000)

        # Create and process buy trade
        buy_trade = Trade(
            trade_id="test1",
            order_id="order1",
            timestamp=datetime.now(),
            symbol="TEST",
            side=OrderSide.BUY,
            quantity=10,
            price=100.0,
        )

        portfolio.process_trade(buy_trade)

        # Check position
        position = portfolio.get_position("TEST")
        assert position is not None
        assert position.quantity == 10
        assert position.average_cost == 100.0

        # Check cash
        expected_cash = 10000 - (10 * 100.0)
        assert portfolio.cash == expected_cash

    def test_order_validation(self):
        """Test order manager validates orders correctly."""
        config = RiskConfig(
            max_position_size=50, max_position_value=10000, min_cash_buffer=1000
        )
        manager = OrderManager(config)

        # Test capital check - should pass
        order1 = Order(
            symbol="TEST",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=10,
            price=100.0,
        )

        is_valid, error = manager.validate_order(
            order1, cash=5000, positions={}, current_prices={"TEST": 100.0}
        )
        assert is_valid

        # Test capital check - should fail
        order2 = Order(
            symbol="TEST",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=100.0,
        )

        is_valid, error = manager.validate_order(
            order2, cash=5000, positions={}, current_prices={"TEST": 100.0}
        )
        assert not is_valid
        assert "Insufficient capital" in error

    def test_strategy_generates_orders(self):
        """Test strategy generates valid orders."""
        strategy = MomentumStrategy(lookback_period=5)
        portfolio = TradingPortfolio(initial_cash=10000)

        # Feed some ticks to build history
        for i in range(10):
            tick = MarketDataPoint(
                timestamp=datetime.now(),
                symbol="TEST",
                price=100.0 + i,  # Rising prices
                volume=1000,
            )
            orders = strategy.on_market_data(tick, portfolio)

        # Should eventually generate buy orders due to positive momentum
        # (Last tick should trigger if momentum threshold is met)
        assert isinstance(orders, list)

    @pytest.mark.skipif(
        not Path("data/assignment3_market_data.csv").exists(),
        reason="Market data file not found",
    )
    def test_full_backtest(self):
        """Test complete backtest with real data."""
        # Setup
        data_gateway = DataGateway("data/assignment3_market_data.csv")
        strategy = MomentumStrategy(lookback_period=10)

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "orders.csv"

            engine = BacktestEngine(
                data_gateway=data_gateway,
                strategy=strategy,
                initial_cash=100_000,
                order_log_file=str(log_file),
            )

            # Run with limited ticks
            result = engine.run(max_ticks=100)

            # Verify result structure
            assert result is not None
            assert result.portfolio is not None
            assert result.performance_metrics is not None
            assert result.total_ticks > 0

            # Verify order log was created
            assert log_file.exists()


class TestDataGateway:
    """Test data gateway functionality."""

    @pytest.mark.skipif(
        not Path("data/assignment3_market_data.csv").exists(),
        reason="Market data file not found",
    )
    def test_data_streaming(self):
        """Test data gateway streams data correctly."""
        gateway = DataGateway("data/assignment3_market_data.csv")

        # Stream first few ticks
        tick_count = 0
        for tick in gateway.stream():
            assert isinstance(tick, MarketDataPoint)
            assert tick.timestamp is not None
            assert tick.symbol is not None
            assert tick.price > 0

            tick_count += 1
            if tick_count >= 10:
                break

        assert tick_count == 10
