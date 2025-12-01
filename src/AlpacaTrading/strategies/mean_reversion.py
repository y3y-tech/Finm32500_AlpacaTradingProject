"""
Mean Reversion Strategy - Moving Average Crossover.

Trades based on short-term vs long-term moving average relationship.
"""

from collections import deque
from enum import Enum
import logging

from AlpacaTrading.models import MarketDataPoint, Order, OrderSide, OrderType
from AlpacaTrading.trading.portfolio import TradingPortfolio
from .base import TradingStrategy

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Market signal types for MA crossover"""
    BULLISH = "BULLISH"  # Short MA > Long MA
    BEARISH = "BEARISH"  # Short MA < Long MA
    NEUTRAL = "NEUTRAL"  # MAs equal (rare)


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

        # Parameter validation
        if short_window <= 0:
            raise ValueError(f"short_window must be positive, got {short_window}")
        if long_window <= 0:
            raise ValueError(f"long_window must be positive, got {long_window}")
        if short_window >= long_window:
            raise ValueError(
                f"short_window ({short_window}) must be less than long_window ({long_window})"
            )
        if position_size <= 0:
            raise ValueError(f"position_size must be positive, got {position_size}")
        if max_position <= 0:
            raise ValueError(f"max_position must be positive, got {max_position}")

        self.short_window = short_window
        self.long_window = long_window
        self.position_size = position_size
        self.max_position = max_position

        # Track price history and MAs per symbol
        self.price_history: dict[str, deque] = {}
        self.short_ma: dict[str, float] = {}
        self.long_ma: dict[str, float] = {}
        self.prev_signal: dict[str, SignalType] = {}  # Track previous signal to detect crossovers

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
        # Validate tick price
        if tick.price <= 0:
            logger.warning(f"Invalid price {tick.price} for {tick.symbol}, skipping tick")
            return []

        # Initialize for new symbol
        if tick.symbol not in self.price_history:
            self.price_history[tick.symbol] = deque(maxlen=self.long_window)
            self.prev_signal[tick.symbol] = SignalType.NEUTRAL
            logger.info(f"Initialized MA crossover tracking for {tick.symbol}")

        # Update price history
        self.price_history[tick.symbol].append(tick.price)

        # Need enough history for long MA
        if len(self.price_history[tick.symbol]) < self.long_window:
            return []

        # Calculate moving averages (optimized: avoid numpy conversion)
        price_list = list(self.price_history[tick.symbol])
        self.short_ma[tick.symbol] = sum(price_list[-self.short_window:]) / self.short_window
        self.long_ma[tick.symbol] = sum(price_list) / self.long_window

        # Determine current signal
        short_ma = self.short_ma[tick.symbol]
        long_ma = self.long_ma[tick.symbol]

        if short_ma > long_ma:
            current_signal = SignalType.BULLISH
        elif short_ma < long_ma:
            current_signal = SignalType.BEARISH
        else:
            current_signal = SignalType.NEUTRAL

        # Get current position
        position = portfolio.get_position(tick.symbol)
        current_qty = position.quantity if position else 0

        orders = []

        # Detect crossover events
        prev = self.prev_signal[tick.symbol]

        # Golden Cross: short MA crosses above long MA -> BUY
        if prev != SignalType.BULLISH and current_signal == SignalType.BULLISH:
            # Calculate target position
            target_qty = min(
                int(self.position_size / tick.price),
                self.max_position
            )

            # Calculate quantity to buy (handles flat, long, and short positions)
            if current_qty < target_qty:
                buy_qty = target_qty - current_qty
                logger.info(
                    f"GOLDEN CROSS for {tick.symbol}: short_ma={short_ma:.2f}, "
                    f"long_ma={long_ma:.2f}, buying {buy_qty} shares "
                    f"(current_qty={current_qty}, target={target_qty})"
                )
                orders.append(Order(
                    symbol=tick.symbol,
                    side=OrderSide.BUY,
                    order_type=OrderType.MARKET,
                    quantity=buy_qty
                ))

        # Death Cross: short MA crosses below long MA -> SELL
        elif prev != SignalType.BEARISH and current_signal == SignalType.BEARISH:
            # Sell/cover all long positions
            if current_qty > 0:
                logger.info(
                    f"DEATH CROSS for {tick.symbol}: short_ma={short_ma:.2f}, "
                    f"long_ma={long_ma:.2f}, selling {current_qty} shares"
                )
                orders.append(Order(
                    symbol=tick.symbol,
                    side=OrderSide.SELL,
                    order_type=OrderType.MARKET,
                    quantity=current_qty
                ))
            # Note: Not handling short positions (sell when already short)
            # as this is a long-only mean reversion strategy

        # Update previous signal
        self.prev_signal[tick.symbol] = current_signal

        return orders

    def __repr__(self) -> str:
        return (
            f"MovingAverageCrossoverStrategy("
            f"short={self.short_window}, long={self.long_window})"
        )
