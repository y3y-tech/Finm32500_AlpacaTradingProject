"""
Unit tests for strategy correctness.

Tests that all strategies produce correct and equivalent results.
"""

import unittest
from datetime import datetime, timedelta
from src.models import MarketDataPoint, Order
from src.strategies import (
    NaiveMovingAverageStrategy,
    WindowedMovingAverageStrategy,
    DequeWindowedStrategy,
    OnlineWindowedStrategy,
    StreamingNaiveStrategy,
)


class TestStrategyCorrectness(unittest.TestCase):
    """Test that all strategies produce correct outputs."""

    def setUp(self):
        """Set up test fixtures."""
        # Create simple test data
        self.test_data = self._generate_test_data(n_ticks=100, symbol="TEST")
        self.window_size = 20

    def _generate_test_data(self, n_ticks: int, symbol: str) -> list[MarketDataPoint]:
        """Generate deterministic test data."""
        data = []
        base_time = datetime(2024, 1, 1, 9, 30, 0)
        base_price = 100.0

        for i in range(n_ticks):
            # Simple linear price movement for predictability
            price = base_price + i * 0.5
            timestamp = base_time + timedelta(seconds=i)
            data.append(MarketDataPoint(timestamp=timestamp, symbol=symbol, price=price))

        return data

    def _run_strategy(self, strategy, data: list[MarketDataPoint]) -> list[Order]:
        """Run strategy through data and collect orders."""
        orders = []
        for tick in data:
            order = strategy.generate_signal(tick)
            orders.append(order)
        return orders

    def test_naive_vs_streaming_equivalence(self):
        """Test that NaiveMovingAverageStrategy and StreamingNaiveStrategy produce identical results."""
        naive_strategy = NaiveMovingAverageStrategy()
        streaming_strategy = StreamingNaiveStrategy()

        naive_orders = self._run_strategy(naive_strategy, self.test_data)
        streaming_orders = self._run_strategy(streaming_strategy, self.test_data)

        self.assertEqual(len(naive_orders), len(streaming_orders))

        for i, (naive_order, streaming_order) in enumerate(
            zip(naive_orders, streaming_orders)
        ):
            with self.subTest(tick=i):
                self.assertEqual(naive_order.action, streaming_order.action,
                    f"Tick {i}: Actions differ - Naive: {naive_order.action}, Streaming: {streaming_order.action}")
                self.assertEqual(naive_order.symbol, streaming_order.symbol)
                self.assertEqual(naive_order.price, streaming_order.price)
                self.assertEqual(naive_order.quantity, streaming_order.quantity)

    def test_windowed_strategies_equivalence(self):
        """Test that all windowed strategies produce identical results."""
        windowed_baseline = WindowedMovingAverageStrategy(self.window_size)
        deque_windowed = DequeWindowedStrategy(self.window_size)
        online_windowed = OnlineWindowedStrategy(self.window_size)

        baseline_orders = self._run_strategy(windowed_baseline, self.test_data)
        deque_orders = self._run_strategy(deque_windowed, self.test_data)
        online_orders = self._run_strategy(online_windowed, self.test_data)

        self.assertEqual(len(baseline_orders), len(deque_orders))
        self.assertEqual(len(baseline_orders), len(online_orders))

        for i in range(len(baseline_orders)):
            with self.subTest(tick=i):
                # All three should produce same action
                self.assertEqual(
                    baseline_orders[i].action,
                    deque_orders[i].action,
                    f"Tick {i}: Baseline vs Deque action mismatch",
                )
                self.assertEqual(
                    baseline_orders[i].action,
                    online_orders[i].action,
                    f"Tick {i}: Baseline vs Online action mismatch",
                )

    def test_moving_average_calculation(self):
        """Test that moving average is calculated correctly."""
        # Use simple data: [100, 101, 102, 103, 104]
        simple_data = []
        base_time = datetime(2024, 1, 1, 9, 30, 0)
        for i in range(5):
            simple_data.append(
                MarketDataPoint(
                    timestamp=base_time + timedelta(seconds=i),
                    symbol="TEST",
                    price=100.0 + i,
                )
            )

        # Test with window=3
        strategy = OnlineWindowedStrategy(window=3)

        # Process first 3 ticks
        for tick in simple_data[:3]:
            strategy.generate_signal(tick)

        # After [100, 101, 102], average should be 101.0
        avg = strategy.calculate_average("TEST")
        self.assertAlmostEqual(avg, 101.0, places=5)

        # Process tick 103
        strategy.generate_signal(simple_data[3])
        # After [101, 102, 103], average should be 102.0
        avg = strategy.calculate_average("TEST")
        self.assertAlmostEqual(avg, 102.0, places=5)

        # Process tick 104
        strategy.generate_signal(simple_data[4])
        # After [102, 103, 104], average should be 103.0
        avg = strategy.calculate_average("TEST")
        self.assertAlmostEqual(avg, 103.0, places=5)

    def test_signal_generation_logic(self):
        """Test that buy/sell signals are generated correctly."""
        # Create data where price is above/below moving average
        test_data = []
        base_time = datetime(2024, 1, 1, 9, 30, 0)

        # First 3 prices: 100, 100, 100 (avg = 100)
        for i in range(3):
            test_data.append(
                MarketDataPoint(
                    timestamp=base_time + timedelta(seconds=i),
                    symbol="TEST",
                    price=100.0,
                )
            )

        # Price jumps to 110 (above average of 100)
        test_data.append(
            MarketDataPoint(
                timestamp=base_time + timedelta(seconds=3),
                symbol="TEST",
                price=110.0,
            )
        )

        strategy = OnlineWindowedStrategy(window=3)
        orders = self._run_strategy(strategy, test_data)

        # Last order should be "ask" because price (110) > average (~103.33)
        self.assertEqual(orders[-1].action, "ask")
        self.assertEqual(orders[-1].price, 110.0)

        # Add price below average
        test_data.append(
            MarketDataPoint(
                timestamp=base_time + timedelta(seconds=4),
                symbol="TEST",
                price=95.0,
            )
        )

        # Process new tick
        order = strategy.generate_signal(test_data[-1])

        # Should be "bid" because price (95) < average (~105)
        self.assertEqual(order.action, "bid")
        self.assertEqual(order.price, 95.0)

    def test_multiple_symbols(self):
        """Test that strategies handle multiple symbols independently."""
        data = []
        base_time = datetime(2024, 1, 1, 9, 30, 0)

        # Interleave data from two symbols
        for i in range(50):
            # Symbol A: prices go up
            data.append(
                MarketDataPoint(
                    timestamp=base_time + timedelta(seconds=i * 2),
                    symbol="SYMBOL_A",
                    price=100.0 + i,
                )
            )
            # Symbol B: prices go down
            data.append(
                MarketDataPoint(
                    timestamp=base_time + timedelta(seconds=i * 2 + 1),
                    symbol="SYMBOL_B",
                    price=200.0 - i,
                )
            )

        strategy = OnlineWindowedStrategy(window=10)
        orders = self._run_strategy(strategy, data)

        # Separate orders by symbol
        orders_a = [o for o in orders if o.symbol == "SYMBOL_A"]
        orders_b = [o for o in orders if o.symbol == "SYMBOL_B"]

        self.assertEqual(len(orders_a), 50)
        self.assertEqual(len(orders_b), 50)

        # Since Symbol A prices are increasing, later orders should be "ask"
        # (price > average of recent lower prices)
        self.assertEqual(orders_a[-1].action, "ask")

        # Since Symbol B prices are decreasing, later orders should be "bid"
        # (price < average of recent higher prices)
        self.assertEqual(orders_b[-1].action, "bid")

    def test_empty_data_handling(self):
        """Test that strategies handle edge cases gracefully."""
        strategy = OnlineWindowedStrategy(window=20)

        # First tick should not crash
        first_tick = MarketDataPoint(
            timestamp=datetime(2024, 1, 1, 9, 30, 0), symbol="TEST", price=100.0
        )

        order = strategy.generate_signal(first_tick)

        # Should generate an order
        self.assertIsNotNone(order)
        self.assertEqual(order.symbol, "TEST")
        self.assertEqual(order.price, 100.0)

    def test_window_smaller_than_data(self):
        """Test windowed strategies when window size < available data."""
        data = self._generate_test_data(n_ticks=5, symbol="TEST")
        window = 10  # Larger than data size

        strategy = OnlineWindowedStrategy(window=window)
        orders = self._run_strategy(strategy, data)

        # Should process all ticks without error
        self.assertEqual(len(orders), 5)

        # All orders should be valid
        for order in orders:
            self.assertIsNotNone(order)
            self.assertIn(order.action, ["ask", "bid"])

    def test_numerical_precision(self):
        """Test that online algorithms maintain numerical precision."""
        # Create data with small increments
        data = []
        base_time = datetime(2024, 1, 1, 9, 30, 0)
        for i in range(1000):
            data.append(
                MarketDataPoint(
                    timestamp=base_time + timedelta(seconds=i),
                    symbol="TEST",
                    price=100.0 + i * 0.001,  # Small increments
                )
            )

        baseline = WindowedMovingAverageStrategy(window=50)
        online = OnlineWindowedStrategy(window=50)

        baseline_orders = self._run_strategy(baseline, data)
        online_orders = self._run_strategy(online, data)

        # Compare last 100 orders (after window is full)
        for i in range(-100, 0):
            with self.subTest(tick=i):
                self.assertEqual(
                    baseline_orders[i].action,
                    online_orders[i].action,
                    f"Tick {i}: Numerical precision issue - actions differ",
                )


if __name__ == "__main__":
    unittest.main()
