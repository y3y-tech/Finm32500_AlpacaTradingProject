"""
Profiling output validation tests.

Tests that profiling tools correctly identify hotspots and memory peaks.
"""

import unittest
import cProfile
import pstats
from io import StringIO
from datetime import datetime, timedelta
import numpy as np

from src.models import MarketDataPoint
from src.strategies import (
    NaiveMovingAverageStrategy,
    OnlineWindowedStrategy,
)


class TestProfilingOutput(unittest.TestCase):
    """Test that profiling correctly identifies performance characteristics."""

    @classmethod
    def setUpClass(cls):
        """Generate test dataset."""
        cls.dataset = cls._generate_dataset(n_ticks=10_000)

    @classmethod
    def _generate_dataset(cls, n_ticks: int) -> list[MarketDataPoint]:
        """Generate test dataset."""
        data = []
        base_time = datetime(2024, 1, 1, 9, 30, 0)
        prices = 100.0 + np.random.randn(n_ticks) * 2

        for i in range(n_ticks):
            data.append(
                MarketDataPoint(
                    timestamp=base_time + timedelta(seconds=i),
                    symbol="TEST",
                    price=prices[i],
                )
            )
        return data

    def _profile_strategy(self, strategy, data: list[MarketDataPoint]) -> pstats.Stats:
        """Profile a strategy and return stats."""
        profiler = cProfile.Profile()

        profiler.enable()
        for tick in data:
            strategy.generate_signal(tick)
        profiler.disable()

        stats = pstats.Stats(profiler)
        stats.strip_dirs()
        stats.sort_stats("cumulative")

        return stats

    def _get_top_functions(
        self, stats: pstats.Stats, top_n: int = 10
    ) -> list[tuple]:
        """Extract top N functions from profiling stats."""
        # Get stats as string
        stream = StringIO()
        stats.stream = stream
        stats.print_stats(top_n)
        output = stream.getvalue()

        # Parse function names from output
        lines = output.split("\n")
        functions = []

        for line in lines:
            # Look for lines with function names (format: "filename:lineno(funcname)")
            if "(" in line and ")" in line and not line.strip().startswith("Ordered by"):
                # Extract function name from the line
                parts = line.split()
                if len(parts) > 5:
                    func_info = parts[-1]  # Last part contains filename:line(funcname)
                    if "(" in func_info:
                        func_name = func_info.split("(")[1].rstrip(")")
                        functions.append(func_name)

        return functions

    def test_naive_strategy_hotspot_is_calculate_average(self):
        """Test that profiling identifies calculate_average as hotspot in Naive strategy."""
        strategy = NaiveMovingAverageStrategy()
        stats = self._profile_strategy(strategy, self.dataset)

        # Get profiling output as string
        stream = StringIO()
        stats.stream = stream
        stats.print_stats(15)
        output = stream.getvalue()

        print("\n" + "=" * 80)
        print("NaiveMovingAverageStrategy Profile (Top 15 Functions):")
        print("=" * 80)
        print(output)

        # Check that calculate_average appears in top functions
        self.assertIn(
            "calculate_average",
            output,
            "calculate_average should appear in profiling output for Naive strategy",
        )

        # Check that generate_signal appears
        self.assertIn(
            "generate_signal",
            output,
            "generate_signal should appear in profiling output",
        )

        # Check that numpy array operations appear (bottleneck)
        # Look for "numpy" or "array" in output
        has_numpy = "numpy" in output.lower() or "array" in output.lower()
        self.assertTrue(
            has_numpy,
            "NumPy array operations should appear in profiling output (they are the bottleneck)",
        )

    def test_online_strategy_hotspot_is_generate_signal(self):
        """Test that profiling shows generate_signal as primary function in Online strategy."""
        strategy = OnlineWindowedStrategy(window=20)
        stats = self._profile_strategy(strategy, self.dataset)

        # Get profiling output as string
        stream = StringIO()
        stats.stream = stream
        stats.print_stats(15)
        output = stream.getvalue()

        print("\n" + "=" * 80)
        print("OnlineWindowedStrategy Profile (Top 15 Functions):")
        print("=" * 80)
        print(output)

        # Check that generate_signal appears
        self.assertIn(
            "generate_signal",
            output,
            "generate_signal should appear in profiling output",
        )

        # For optimized strategy, calculate_average should have minimal time
        # because it's just a division operation
        # We can't easily check cumulative time, but the output should show it

    def test_baseline_has_more_function_calls_than_optimized(self):
        """Test that baseline strategy makes more function calls than optimized."""
        baseline_strategy = NaiveMovingAverageStrategy()
        optimized_strategy = OnlineWindowedStrategy(window=20)

        baseline_stats = self._profile_strategy(baseline_strategy, self.dataset)
        optimized_stats = self._profile_strategy(optimized_strategy, self.dataset)

        # Count total function calls
        baseline_calls = baseline_stats.total_calls
        optimized_calls = optimized_stats.total_calls

        print(f"\nFunction Call Comparison (10K ticks):")
        print(f"  Baseline (Naive):     {baseline_calls:,} calls")
        print(f"  Optimized (Online):   {optimized_calls:,} calls")
        print(f"  Ratio: {baseline_calls / optimized_calls:.2f}x more calls")

        # Baseline should make significantly more function calls
        # due to list comprehensions, array creations, etc.
        self.assertGreater(
            baseline_calls,
            optimized_calls * 1.5,
            "Baseline should make significantly more function calls than optimized",
        )

    def test_profiling_identifies_numpy_overhead_in_baseline(self):
        """Test that profiling correctly identifies NumPy overhead in baseline."""
        strategy = NaiveMovingAverageStrategy()
        stats = self._profile_strategy(strategy, self.dataset)

        # Get all function stats
        stream = StringIO()
        stats.stream = stream
        stats.print_stats()  # Print all stats
        output = stream.getvalue()

        # Look for numpy-related functions
        numpy_functions = [
            "array",  # np.array creation
            "mean",  # np.mean computation
            "_mean",  # internal mean implementation
        ]

        found_numpy = False
        for func in numpy_functions:
            if func in output.lower():
                found_numpy = True
                print(f"\n✓ Found NumPy function in profile: {func}")
                break

        self.assertTrue(
            found_numpy,
            "Profiling should identify NumPy operations as part of the overhead",
        )

    def test_execution_time_proportional_to_function_calls(self):
        """Test that strategies with more function calls take more time."""
        import time

        baseline_strategy = NaiveMovingAverageStrategy()
        optimized_strategy = OnlineWindowedStrategy(window=20)

        # Time baseline
        start = time.perf_counter()
        for tick in self.dataset:
            baseline_strategy.generate_signal(tick)
        baseline_time = time.perf_counter() - start

        # Time optimized
        start = time.perf_counter()
        for tick in self.dataset:
            optimized_strategy.generate_signal(tick)
        optimized_time = time.perf_counter() - start

        print(f"\nExecution Time Comparison:")
        print(f"  Baseline: {baseline_time:.4f}s")
        print(f"  Optimized: {optimized_time:.4f}s")
        print(f"  Speedup: {baseline_time / optimized_time:.2f}x")

        # Optimized should be significantly faster
        self.assertLess(
            optimized_time * 5,
            baseline_time,
            "Optimized strategy should be at least 5x faster",
        )

    def test_profiling_captures_per_call_overhead(self):
        """Test that profiling shows per-call timing information."""
        strategy = NaiveMovingAverageStrategy()
        stats = self._profile_strategy(strategy, self.dataset)

        # Get stats output
        stream = StringIO()
        stats.stream = stream
        stats.print_stats(20)
        output = stream.getvalue()

        # Check that output contains timing columns
        # cProfile output has columns: ncalls, tottime, percall, cumtime, percall
        self.assertIn(
            "tottime", output, "Profile output should contain total time column"
        )
        self.assertIn(
            "cumtime", output, "Profile output should contain cumulative time column"
        )
        self.assertIn("percall", output, "Profile output should contain per-call time")

    def test_memory_profiling_integration(self):
        """Test that memory profiler can be integrated with strategies."""
        from memory_profiler import profile as memory_profile
        import inspect

        # Check that strategies can be decorated with memory profiler
        strategy = OnlineWindowedStrategy(window=20)

        # Get generate_signal method
        method = strategy.generate_signal

        # Check that method is callable and can be profiled
        self.assertTrue(callable(method))

        # Test that we can wrap it with memory profiler
        # (actual profiling is tested in test_performance.py)
        try:
            # This should not raise an error
            wrapped = memory_profile(method)
            self.assertTrue(callable(wrapped))
        except Exception as e:
            self.fail(f"Failed to wrap method with memory_profile: {e}")


class TestProfilingComprehensiveness(unittest.TestCase):
    """Test that profiling covers all important aspects."""

    def test_profiling_covers_all_strategy_methods(self):
        """Test that profiling captures all strategy methods."""
        from src.strategies import OnlineWindowedStrategy

        strategy = OnlineWindowedStrategy(window=20)
        profiler = cProfile.Profile()

        # Create test data
        data = []
        base_time = datetime(2024, 1, 1, 9, 30, 0)
        for i in range(100):
            data.append(
                MarketDataPoint(
                    timestamp=base_time + timedelta(seconds=i),
                    symbol="TEST",
                    price=100.0 + i * 0.1,
                )
            )

        # Profile
        profiler.enable()
        for tick in data:
            strategy.generate_signal(tick)
        profiler.disable()

        # Get stats
        stats = pstats.Stats(profiler)
        stream = StringIO()
        stats.stream = stream
        stats.print_stats()
        output = stream.getvalue()

        # Check that all main methods appear
        expected_methods = ["generate_signal", "update_price", "calculate_average"]

        for method in expected_methods:
            self.assertIn(
                method,
                output,
                f"Method {method} should appear in profiling output",
            )

    def test_profiling_output_format_is_parseable(self):
        """Test that profiling output can be parsed for automated analysis."""
        strategy = NaiveMovingAverageStrategy()
        profiler = cProfile.Profile()

        # Create small dataset
        data = []
        base_time = datetime(2024, 1, 1, 9, 30, 0)
        for i in range(50):
            data.append(
                MarketDataPoint(
                    timestamp=base_time + timedelta(seconds=i),
                    symbol="TEST",
                    price=100.0,
                )
            )

        # Profile
        profiler.enable()
        for tick in data:
            strategy.generate_signal(tick)
        profiler.disable()

        # Get stats
        stats = pstats.Stats(profiler)

        # Test that we can extract statistics programmatically
        self.assertIsNotNone(stats.total_calls)
        self.assertGreater(stats.total_calls, 0)

        # Test that we can sort by different keys
        try:
            stats.sort_stats("cumulative")
            stats.sort_stats("tottime")
            stats.sort_stats("ncalls")
        except Exception as e:
            self.fail(f"Failed to sort stats: {e}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
