"""
Mean Reversion Strategy - Moving Average Crossover.

Trades based on short-term vs long-term moving average relationship.
"""

from collections import deque
import numpy as np

from src.models import MarketDataPoint, Order, OrderSide, OrderType
from src.trading.portfolio import TradingPortfolio
from .base import TradingStrategy


class MovingAverageCrossoverStrategy(TradingStrategy):
    """
    Mean reversion strategy using moving average crossover.

    Logic:
    1. Calculate short-term and long-term moving averages
    2. Buy when short MA crosses above long MA (golden cross)
    3. Sell when short MA crosses below long MA (death cross)

    Parameters:
        short_window: Short-term MA period (default: 10)
        long_window: Long-term MA period (default: 30)
        position_size: Target position size in dollars (default: 10000)
        max_position: Maximum position per symbol (default: 100 shares)
    """

    def __init__(
        self,
        short_window: int = 10,
        long_window: int = 30,
        position_size: float = 10000,
        max_position: int = 100
    ):
        super().__init__("MA_Crossover")

        if short_window >= long_window:
            raise ValueError("short_window must be less than long_window")

        self.short_window = short_window
        self.long_window = long_window
        self.position_size = position_size
        self.max_position = max_position

        # Track price history and MAs per symbol
        self.price_history: dict[str, deque] = {}
        self.short_ma: dict[str, float] = {}
        self.long_ma: dict[str, float] = {}
        self.prev_signal: dict[str, str] = {}  # Track previous signal to detect crossovers

    def on_market_data(
        self,
        tick: MarketDataPoint,
        portfolio: TradingPortfolio
    ) -> list[Order]:
        """
        Generate trading signals based on MA crossover.

        Returns:
            List of orders (buy on golden cross, sell on death cross)
        """
        # Initialize for new symbol
        if tick.symbol not in self.price_history:
            self.price_history[tick.symbol] = deque(maxlen=self.long_window)
            self.prev_signal[tick.symbol] = "NEUTRAL"

        # Update price history
        self.price_history[tick.symbol].append(tick.price)

        # Need enough history for long MA
        if len(self.price_history[tick.symbol]) < self.long_window:
            return []

        # Calculate moving averages
        prices = np.array(list(self.price_history[tick.symbol]))
        self.short_ma[tick.symbol] = np.mean(prices[-self.short_window:])
        self.long_ma[tick.symbol] = np.mean(prices[-self.long_window:])

        # Determine current signal
        if self.short_ma[tick.symbol] > self.long_ma[tick.symbol]:
            current_signal = "BULLISH"
        elif self.short_ma[tick.symbol] < self.long_ma[tick.symbol]:
            current_signal = "BEARISH"
        else:
            current_signal = "NEUTRAL"

        # Get current position
        position = portfolio.get_position(tick.symbol)
        current_qty = position.quantity if position else 0

        orders = []

        # Detect crossover events
        prev = self.prev_signal[tick.symbol]

        # Golden Cross: short MA crosses above long MA -> BUY
        if prev != "BULLISH" and current_signal == "BULLISH":
            if current_qty <= 0:  # Only buy if flat or short
                quantity = min(
                    int(self.position_size / tick.price),
                    self.max_position
                )
                if quantity > 0:
                    orders.append(Order(
                        symbol=tick.symbol,
                        side=OrderSide.BUY,
                        order_type=OrderType.MARKET,
                        quantity=quantity
                    ))

        # Death Cross: short MA crosses below long MA -> SELL
        elif prev != "BEARISH" and current_signal == "BEARISH":
            if current_qty > 0:  # Only sell if we have a position
                orders.append(Order(
                    symbol=tick.symbol,
                    side=OrderSide.SELL,
                    order_type=OrderType.MARKET,
                    quantity=current_qty
                ))

        # Update previous signal
        self.prev_signal[tick.symbol] = current_signal

        return orders

    def __repr__(self) -> str:
        return (
            f"MovingAverageCrossoverStrategy("
            f"short={self.short_window}, long={self.long_window})"
        )
