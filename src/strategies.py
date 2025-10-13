from typing import override
from collections import deque

import numpy as np

from .models import MarketDataPoint, Order, Strategy


class WindowedMovingAverageStrategy(Strategy):
    def __init__(self, window: int):
        """
        TIME COMPLEXITY: O(1)
        - Dictionary initialization and integer assignment are constant time

        SPACE COMPLEXITY: O(1)
        - Only allocates empty dict and stores window size
        """
        self.past_prices: dict[str, list[MarketDataPoint]] = {}
        self.window: int = window

    def update_price(self, tick: MarketDataPoint):
        """
        TIME COMPLEXITY: O(1) amortized
        - Dictionary lookup: O(1) average case
        - List append: O(1) amortized (occasionally O(n) when resizing)
        - List access [-1]: O(1)
        - Equality check: O(1)

        SPACE COMPLEXITY: O(1) per call
        - Only stores reference to tick in existing list
        - Note: Accumulated space is O(n) per symbol where n = total ticks processed
        """
        if tick.symbol not in self.past_prices:
            self.past_prices[tick.symbol] = [tick]
        elif self.past_prices[tick.symbol][-1] != tick:
            self.past_prices[tick.symbol].append(tick)

    def calculate_average(self, symbol: str):
        """
        TIME COMPLEXITY: O(n) where n = len(past_prices[symbol])
        - List comprehension over all stored prices: O(n)
        - Array creation from list: O(n)
        - Array slicing [-self.window:]: O(w) where w = min(window, n)
        - np.mean over w elements: O(w)
        - Total: O(n) dominated by list comprehension, even though we only use last w elements

        SPACE COMPLEXITY: O(n)
        - List comprehension creates temporary list of n floats
        - np.array allocates array of n elements
        - Slice creates new array of w elements
        - Total temporary space: O(n)
        """
        return float(
            np.mean(
                np.array([p.price for p in self.past_prices[symbol]])[-self.window :]
            )
        )

    @override
    def generate_signal(self, tick: MarketDataPoint) -> Order:
        """
        TIME COMPLEXITY: O(n) where n = total ticks processed for this symbol
        - update_price: O(1) amortized
        - calculate_average: O(n) - dominates the complexity
        - Order creation: O(1)
        - Total: O(n)

        SPACE COMPLEXITY: O(n)
        - Temporary space from calculate_average: O(n)
        - Order object: O(1)
        """
        self.update_price(tick)
        return Order(
            timestamp=tick.timestamp,
            symbol=tick.symbol,
            price=tick.price,
            action="ask" if tick.price > self.calculate_average(tick.symbol) else "bid",
            quantity=1,
        )


class NaiveMovingAverageStrategy(WindowedMovingAverageStrategy):
    """
    Naive strategy that computes average over ALL historical prices (no window).
    Inherits from WindowedMovingAverageStrategy with window=0 (which means no slicing limit).

    COMPLEXITY ANALYSIS:
    - Same as WindowedMovingAverageStrategy but window effectively equals n
    - Time complexity for generate_signal: O(n) per call, grows with history
    - Space complexity: O(n * s) total where s = number of symbols, n = ticks per symbol
    """

    def __init__(self):
        """
        TIME COMPLEXITY: O(1)
        - Calls parent __init__ with constant-time operations

        SPACE COMPLEXITY: O(1)
        - Inherits parent's space allocation
        """
        super().__init__(window=0)


# ============================================================================
# OPTIMIZED STRATEGIES
# ============================================================================


class DequeWindowedStrategy(Strategy):
    """
    OPTIMIZED windowed moving average using collections.deque.

    OPTIMIZATION: Uses deque(maxlen=window) to automatically maintain fixed-size window
    and only iterates over w elements instead of full history.

    COMPLEXITY ANALYSIS:
    - Time complexity: O(w) per tick (iterate over w elements to compute mean)
    - Space complexity: O(w * s) total where s = number of symbols
    - Improvement over WindowedMovingAverageStrategy: n/w times faster and smaller
    """

    def __init__(self, window: int):
        """
        TIME COMPLEXITY: O(1)
        - Dictionary initialization and window size storage

        SPACE COMPLEXITY: O(1)
        - Only allocates empty dict and stores window size
        """
        self.past_prices: dict[str, deque[float]] = {}
        self.window: int = window

    def update_price(self, tick: MarketDataPoint):
        """
        TIME COMPLEXITY: O(1)
        - Dictionary lookup: O(1) average case
        - Deque append: O(1) - automatically evicts oldest when at maxlen

        SPACE COMPLEXITY: O(1) per call
        - Deque append is O(1) - no growth beyond maxlen
        - Accumulated space is O(w) per symbol (bounded by window size)
        """
        if tick.symbol not in self.past_prices:
            self.past_prices[tick.symbol] = deque(maxlen=self.window)
        self.past_prices[tick.symbol].append(tick.price)

    def calculate_average(self, symbol: str) -> float:
        """
        TIME COMPLEXITY: O(w) where w = window size
        - np.mean over deque of at most w elements: O(w)
        - No list comprehension over full history needed

        SPACE COMPLEXITY: O(w)
        - np.mean creates temporary array of w elements
        - Much more efficient than O(n) of unoptimized version
        """
        return float(np.mean(self.past_prices[symbol]))

    @override
    def generate_signal(self, tick: MarketDataPoint) -> Order:
        """
        TIME COMPLEXITY: O(w) where w = window size
        - update_price: O(1)
        - calculate_average: O(w) - dominates
        - Order creation: O(1)
        - Total: O(w) - constant per tick regardless of history length!

        SPACE COMPLEXITY: O(w)
        - Temporary space from calculate_average: O(w)
        - Order object: O(1)
        """
        self.update_price(tick)
        return Order(
            timestamp=tick.timestamp,
            symbol=tick.symbol,
            price=tick.price,
            action="ask" if tick.price > self.calculate_average(tick.symbol) else "bid",
            quantity=1,
        )


class OnlineWindowedStrategy(Strategy):
    """
    HIGHLY OPTIMIZED windowed moving average using deque + running sum.

    OPTIMIZATION: Maintains running sum alongside deque, updating incrementally:
    - When adding new price: add to sum, append to deque
    - When deque evicts old price: subtract from sum
    - Average = sum / count in O(1)

    COMPLEXITY ANALYSIS:
    - Time complexity: O(1) per tick (constant time updates!)
    - Space complexity: O(w * s) total where s = number of symbols
    - Best possible complexity for windowed moving average
    """

    def __init__(self, window: int):
        """
        TIME COMPLEXITY: O(1)
        - Dictionary initialization and window size storage

        SPACE COMPLEXITY: O(1)
        - Allocates empty dicts and stores window size
        """
        self.past_prices: dict[str, deque[float]] = {}
        self.running_sums: dict[str, float] = {}
        self.window: int = window

    def update_price(self, tick: MarketDataPoint):
        """
        TIME COMPLEXITY: O(1)
        - Dictionary lookup: O(1) average case
        - Deque append: O(1)
        - Check if eviction happened: O(1)
        - Update running sum: O(1) arithmetic

        SPACE COMPLEXITY: O(1) per call
        - Deque bounded at maxlen, running sum is single float
        - Accumulated space is O(w) per symbol
        """
        if tick.symbol not in self.past_prices:
            self.past_prices[tick.symbol] = deque(maxlen=self.window)
            self.running_sums[tick.symbol] = 0.0

        prices_deque = self.past_prices[tick.symbol]

        # If deque is at capacity, we'll evict the oldest value
        evicted_price = None
        if len(prices_deque) == self.window:
            evicted_price = prices_deque[0]  # Get oldest before it's evicted

        # Add new price
        prices_deque.append(tick.price)
        self.running_sums[tick.symbol] += tick.price

        # Subtract evicted price from sum
        if evicted_price is not None:
            self.running_sums[tick.symbol] -= evicted_price

    def calculate_average(self, symbol: str) -> float:
        """
        TIME COMPLEXITY: O(1)
        - Division operation: O(1)
        - No iteration over elements needed!

        SPACE COMPLEXITY: O(1)
        - No temporary arrays or lists created
        - Returns single float value
        """
        count = len(self.past_prices[symbol])
        if count == 0:
            return 0.0
        return self.running_sums[symbol] / count

    @override
    def generate_signal(self, tick: MarketDataPoint) -> Order:
        """
        TIME COMPLEXITY: O(1) - CONSTANT TIME!
        - update_price: O(1)
        - calculate_average: O(1)
        - Order creation: O(1)
        - Total: O(1) - optimal complexity!

        SPACE COMPLEXITY: O(1) per call
        - No temporary allocations
        - Order object: O(1)
        """
        self.update_price(tick)
        return Order(
            timestamp=tick.timestamp,
            symbol=tick.symbol,
            price=tick.price,
            action="ask" if tick.price > self.calculate_average(tick.symbol) else "bid",
            quantity=1,
        )


class StreamingNaiveStrategy(Strategy):
    """
    OPTIMIZED naive (full-history) moving average using online/streaming algorithm.

    OPTIMIZATION: Instead of storing all prices and recomputing mean each time,
    maintains running sum and count for incremental O(1) average calculation.

    COMPLEXITY ANALYSIS:
    - Time complexity: O(1) per tick (constant time updates!)
    - Space complexity: O(s) total where s = number of symbols (only stores sum + count)
    - Massive improvement over NaiveMovingAverageStrategy: O(1) vs O(n) per tick
    """

    def __init__(self):
        """
        TIME COMPLEXITY: O(1)
        - Dictionary initialization

        SPACE COMPLEXITY: O(1)
        - Only allocates empty dicts
        """
        self.running_sums: dict[str, float] = {}
        self.counts: dict[str, int] = {}

    def update_price(self, tick: MarketDataPoint):
        """
        TIME COMPLEXITY: O(1)
        - Dictionary lookup: O(1) average case
        - Arithmetic operations: O(1)

        SPACE COMPLEXITY: O(1) per call
        - Only stores two numbers (sum and count) per symbol
        - No price history storage required!
        """
        if tick.symbol not in self.running_sums:
            self.running_sums[tick.symbol] = 0.0
            self.counts[tick.symbol] = 0

        self.running_sums[tick.symbol] += tick.price
        self.counts[tick.symbol] += 1

    def calculate_average(self, symbol: str) -> float:
        """
        TIME COMPLEXITY: O(1)
        - Division operation: O(1)
        - No iteration needed!

        SPACE COMPLEXITY: O(1)
        - Returns single float value
        - No temporary storage
        """
        if self.counts[symbol] == 0:
            return 0.0
        return self.running_sums[symbol] / self.counts[symbol]

    @override
    def generate_signal(self, tick: MarketDataPoint) -> Order:
        """
        TIME COMPLEXITY: O(1) - CONSTANT TIME!
        - update_price: O(1)
        - calculate_average: O(1)
        - Order creation: O(1)
        - Total: O(1) - optimal for full-history average!

        SPACE COMPLEXITY: O(1) per call
        - No temporary allocations
        - Order object: O(1)
        """
        self.update_price(tick)
        return Order(
            timestamp=tick.timestamp,
            symbol=tick.symbol,
            price=tick.price,
            action="ask" if tick.price > self.calculate_average(tick.symbol) else "bid",
            quantity=1,
        )
