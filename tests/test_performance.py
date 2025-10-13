"""
Performance validation tests.

Validates that optimized strategies meet performance requirements:
- Runtime < 1 second for 100K ticks
- Memory usage < 100 MB for 100K ticks
"""

import unittest
import time
from datetime import datetime, timedelta
from memory_profiler import memory_usage
import numpy as np

from src.models import MarketDataPoint
from src.strategies import (
    OnlineWindowedStrategy,
    StreamingNaiveStrategy,
    DequeWindowedStrategy,
)


class TestPerformanceRequirements(unittest.TestCase):
    """Test that optimized strategies meet performance requirements."""

    @classmethod
    def setUpClass(cls):
        """Generate test dataset once for all tests."""
        cls.large_dataset = cls._generate_large_dataset(n_ticks=100_000)

    @classmethod
    def _generate_large_dataset(cls, n_ticks: int) -> list[MarketDataPoint]:
        """Generate large dataset for performance testing."""
        data = []
        base_time = datetime(2024, 1, 1, 9, 30, 0)
        base_price = 100.0

        # Use numpy for faster generation
        prices = base_price + np.random.randn(n_ticks) * 2

        for i in range(n_ticks):
            timestamp = base_time + timedelta(seconds=i)
            data.append(
                MarketDataPoint(timestamp=timestamp, symbol="TEST", price=prices[i])
            )

        return data

    def _run_strategy_timed(self, strategy, data: list[MarketDataPoint]) -> float:
        """Run strategy and measure execution time."""
        start_time = time.perf_counter()

        for tick in data:
            strategy.generate_signal(tick)

        end_time = time.perf_counter()
        return end_time - start_time

    def _measure_memory(self, strategy_class, data: list[MarketDataPoint], **kwargs):
        """Measure peak memory usage of strategy."""

        def run_strategy():
            strategy = strategy_class(**kwargs)
            for tick in data:
                strategy.generate_signal(tick)

        # Measure memory with 0.1s sampling interval
        mem_usage = memory_usage(run_strategy, interval=0.1, max_usage=True)
        return mem_usage

    def test_online_windowed_runtime_requirement(self):
        """Test that OnlineWindowedStrategy runs 100K ticks in < 1 second."""
        strategy = OnlineWindowedStrategy(window=20)
        execution_time = self._run_strategy_timed(strategy, self.large_dataset)

        print(f"\nOnlineWindowedStrategy execution time: {execution_time:.4f}s")

        self.assertLess(
            execution_time,
            1.0,
            f"OnlineWindowedStrategy took {execution_time:.4f}s (requirement: < 1.0s)",
        )

    def test_streaming_naive_runtime_requirement(self):
        """Test that StreamingNaiveStrategy runs 100K ticks in < 1 second."""
        strategy = StreamingNaiveStrategy()
        execution_time = self._run_strategy_timed(strategy, self.large_dataset)

        print(f"\nStreamingNaiveStrategy execution time: {execution_time:.4f}s")

        self.assertLess(
            execution_time,
            1.0,
            f"StreamingNaiveStrategy took {execution_time:.4f}s (requirement: < 1.0s)",
        )

    def test_deque_windowed_runtime_requirement(self):
        """Test that DequeWindowedStrategy runs 100K ticks in < 1 second."""
        strategy = DequeWindowedStrategy(window=20)
        execution_time = self._run_strategy_timed(strategy, self.large_dataset)

        print(f"\nDequeWindowedStrategy execution time: {execution_time:.4f}s")

        self.assertLess(
            execution_time,
            1.0,
            f"DequeWindowedStrategy took {execution_time:.4f}s (requirement: < 1.0s)",
        )

    def test_online_windowed_memory_requirement(self):
        """Test that OnlineWindowedStrategy uses < 100 MB for 100K ticks."""
        # Note: We measure the memory increase from baseline, not absolute memory
        # Python interpreter + imports already use ~175 MB

        baseline_mem = memory_usage(max_usage=True, proc=-1)
        print(f"\nBaseline memory: {baseline_mem:.2f} MB")

        strategy_mem = self._measure_memory(
            OnlineWindowedStrategy, self.large_dataset, window=20
        )

        memory_increase = strategy_mem - baseline_mem
        print(f"OnlineWindowedStrategy memory increase: {memory_increase:.2f} MB")
        print(f"OnlineWindowedStrategy peak memory: {strategy_mem:.2f} MB")

        # The strategy itself should use very little memory (O(w))
        # We allow 100 MB for the strategy + data processing overhead
        self.assertLess(
            memory_increase,
            100.0,
            f"OnlineWindowedStrategy used {memory_increase:.2f} MB (requirement: < 100 MB increase)",
        )

    def test_streaming_naive_memory_requirement(self):
        """Test that StreamingNaiveStrategy uses < 100 MB for 100K ticks."""
        baseline_mem = memory_usage(max_usage=True, proc=-1)
        print(f"\nBaseline memory: {baseline_mem:.2f} MB")

        strategy_mem = self._measure_memory(StreamingNaiveStrategy, self.large_dataset)

        memory_increase = strategy_mem - baseline_mem
        print(f"StreamingNaiveStrategy memory increase: {memory_increase:.2f} MB")
        print(f"StreamingNaiveStrategy peak memory: {strategy_mem:.2f} MB")

        # Streaming strategy should use minimal memory (O(1))
        self.assertLess(
            memory_increase,
            100.0,
            f"StreamingNaiveStrategy used {memory_increase:.2f} MB (requirement: < 100 MB increase)",
        )

    def test_per_tick_performance_consistency(self):
        """Test that per-tick time remains constant as history grows."""
        strategy = OnlineWindowedStrategy(window=20)

        # Measure time for different segments
        segment_size = 10_000
        times = []

        for i in range(0, 100_000, segment_size):
            segment = self.large_dataset[i : i + segment_size]
            segment_time = self._run_strategy_timed(strategy, segment)
            per_tick_time = segment_time / segment_size
            times.append(per_tick_time)

        print(f"\nPer-tick times across segments: {[f'{t*1e6:.2f}μs' for t in times]}")

        # Verify that per-tick time doesn't grow significantly
        # Allow 2x variation due to system noise, but should not grow linearly
        max_time = max(times)
        min_time = min(times)
        ratio = max_time / min_time

        self.assertLess(
            ratio,
            2.0,
            f"Per-tick time varies too much ({ratio:.2f}x), suggesting O(n) behavior",
        )

    def test_memory_does_not_grow_unbounded(self):
        """Test that memory usage doesn't grow with dataset size for optimized strategies."""
        # Test with progressively larger datasets
        sizes = [10_000, 50_000, 100_000]
        memories = []

        for size in sizes:
            data = self._generate_large_dataset(size)
            mem = self._measure_memory(OnlineWindowedStrategy, data, window=20)
            memories.append(mem)

        print(f"\nMemory usage by dataset size:")
        for size, mem in zip(sizes, memories):
            print(f"  {size:,} ticks: {mem:.2f} MB")

        # Memory should not grow significantly with dataset size
        # Allow small growth due to overhead, but not linear
        memory_growth_ratio = memories[-1] / memories[0]

        # For 10x data increase, memory should not increase by more than 1.5x
        # (allowing for some overhead and fragmentation)
        dataset_size_ratio = sizes[-1] / sizes[0]

        self.assertLess(
            memory_growth_ratio,
            1.5,
            f"Memory grew {memory_growth_ratio:.2f}x for {dataset_size_ratio}x data increase",
        )


class TestPerformanceComparison(unittest.TestCase):
    """Compare performance of optimized vs baseline strategies."""

    @classmethod
    def setUpClass(cls):
        """Generate test dataset."""
        cls.dataset = cls._generate_dataset(n_ticks=10_000)

    @classmethod
    def _generate_dataset(cls, n_ticks: int) -> list[MarketDataPoint]:
        """Generate dataset for comparison."""
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

    def _benchmark_strategy(self, strategy_class, data, **kwargs):
        """Benchmark a strategy and return execution time."""
        strategy = strategy_class(**kwargs)
        start_time = time.perf_counter()

        for tick in data:
            strategy.generate_signal(tick)

        end_time = time.perf_counter()
        return end_time - start_time

    def test_optimized_windowed_faster_than_baseline(self):
        """Verify that optimized windowed strategies are significantly faster."""
        from src.strategies import WindowedMovingAverageStrategy

        baseline_time = self._benchmark_strategy(
            WindowedMovingAverageStrategy, self.dataset, window=20
        )
        online_time = self._benchmark_strategy(
            OnlineWindowedStrategy, self.dataset, window=20
        )
        deque_time = self._benchmark_strategy(
            DequeWindowedStrategy, self.dataset, window=20
        )

        print(f"\nWindowed Strategy Performance (10K ticks):")
        print(f"  Baseline: {baseline_time:.4f}s")
        print(f"  Deque:    {deque_time:.4f}s ({baseline_time/deque_time:.1f}x faster)")
        print(
            f"  Online:   {online_time:.4f}s ({baseline_time/online_time:.1f}x faster)"
        )

        # Optimized should be at least 10x faster for 10K ticks
        self.assertLess(online_time * 10, baseline_time)
        self.assertLess(deque_time * 10, baseline_time)

    def test_optimized_naive_faster_than_baseline(self):
        """Verify that optimized naive strategy is significantly faster."""
        from src.strategies import NaiveMovingAverageStrategy

        baseline_time = self._benchmark_strategy(NaiveMovingAverageStrategy, self.dataset)
        streaming_time = self._benchmark_strategy(
            StreamingNaiveStrategy, self.dataset
        )

        print(f"\nNaive Strategy Performance (10K ticks):")
        print(f"  Baseline:  {baseline_time:.4f}s")
        print(
            f"  Streaming: {streaming_time:.4f}s ({baseline_time/streaming_time:.1f}x faster)"
        )

        # Optimized should be at least 10x faster for 10K ticks
        self.assertLess(streaming_time * 10, baseline_time)


if __name__ == "__main__":
    # Run with verbose output to see timing information
    unittest.main(verbosity=2)
