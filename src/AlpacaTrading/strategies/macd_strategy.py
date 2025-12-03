"""
MACD (Moving Average Convergence Divergence) Strategy.

Classic trend-following momentum indicator. Uses the relationship between
two EMAs to identify trend changes and momentum shifts.

Best for: Trending markets, medium-term positions
Works well with: Equities, ETFs, currencies
"""

from collections import deque
import logging

from AlpacaTrading.models import MarketDataPoint, Order, OrderSide, OrderType
from AlpacaTrading.trading.portfolio import TradingPortfolio
from .base import TradingStrategy

logger = logging.getLogger(__name__)


class MACDStrategy(TradingStrategy):
    """
    MACD crossover strategy.

    Components:
    - MACD Line: Fast EMA - Slow EMA
    - Signal Line: EMA of MACD Line
    - Histogram: MACD Line - Signal Line

    Signal Types:
    - crossover: Trade MACD/Signal crossovers
    - zero_cross: Trade MACD zero-line crossovers
    - histogram: Trade histogram momentum

    Parameters:
        fast_period: Fast EMA period (default: 12)
        slow_period: Slow EMA period (default: 26)
        signal_period: Signal line EMA period (default: 9)
        signal_type: 'crossover', 'zero_cross', or 'histogram'
        position_size: Dollar amount per trade
        max_position: Maximum shares per symbol
    """

    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
        signal_type: str = "crossover",
        position_size: float = 10000,
        max_position: int = 100,
    ):
        super().__init__("MACD")

        if fast_period >= slow_period:
            raise ValueError("fast_period must be < slow_period")
        if signal_period <= 0:
            raise ValueError(f"signal_period must be positive, got {signal_period}")

        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        self.signal_type = signal_type
        self.position_size = position_size
        self.max_position = max_position

        # State per symbol
        self.price_history: dict[str, deque] = {}
        self.fast_ema: dict[str, float | None] = {}
        self.slow_ema: dict[str, float | None] = {}
        self.signal_ema: dict[str, float | None] = {}
        self.prev_macd: dict[str, float | None] = {}
        self.prev_signal: dict[str, float | None] = {}
        self.prev_histogram: dict[str, float | None] = {}

    def _update_ema(
        self, current_ema: float | None, price: float, period: int, prices: list[float]
    ) -> float | None:
        """Update EMA value."""
        if current_ema is None:
            if len(prices) >= period:
                return sum(prices[-period:]) / period
            return None

        multiplier = 2 / (period + 1)
        return (price - current_ema) * multiplier + current_ema

    def on_market_data(
        self, tick: MarketDataPoint, portfolio: TradingPortfolio
    ) -> list[Order]:
        symbol = tick.symbol
        price = tick.price

        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=self.slow_period + 10)

        self.price_history[symbol].append(price)
        prices = list(self.price_history[symbol])

        # Update EMAs
        self.fast_ema[symbol] = self._update_ema(
            self.fast_ema.get(symbol), price, self.fast_period, prices
        )
        self.slow_ema[symbol] = self._update_ema(
            self.slow_ema.get(symbol), price, self.slow_period, prices
        )

        if self.fast_ema[symbol] is None or self.slow_ema[symbol] is None:
            return []

        # Calculate MACD line
        macd = self.fast_ema[symbol] - self.slow_ema[symbol]

        # Update signal line (EMA of MACD)
        # We need to track MACD history for signal line calculation
        if self.signal_ema.get(symbol) is None:
            # Initialize signal line after we have enough MACD values
            self.signal_ema[symbol] = macd
        else:
            multiplier = 2 / (self.signal_period + 1)
            self.signal_ema[symbol] = (
                (macd - self.signal_ema[symbol]) * multiplier + self.signal_ema[symbol]
            )

        signal = self.signal_ema[symbol]
        histogram = macd - signal

        # Get previous values for crossover detection
        prev_macd = self.prev_macd.get(symbol)
        prev_signal = self.prev_signal.get(symbol)
        prev_hist = self.prev_histogram.get(symbol)

        # Store current values for next iteration
        self.prev_macd[symbol] = macd
        self.prev_signal[symbol] = signal
        self.prev_histogram[symbol] = histogram

        if prev_macd is None or prev_signal is None:
            return []

        position = portfolio.get_position(symbol)
        current_qty = position.quantity if position else 0

        orders = []

        if self.signal_type == "crossover":
            # Bullish crossover: MACD crosses above signal
            if current_qty == 0 and prev_macd <= prev_signal and macd > signal:
                qty = min(int(self.position_size / price), self.max_position)
                if qty > 0:
                    orders.append(
                        Order(
                            symbol=symbol,
                            side=OrderSide.BUY,
                            order_type=OrderType.MARKET,
                            quantity=qty,
                        )
                    )
                    logger.info(
                        f"MACD BULLISH CROSSOVER {symbol}: MACD={macd:.4f} > Signal={signal:.4f}"
                    )

            # Bearish crossover: MACD crosses below signal
            elif current_qty > 0 and prev_macd >= prev_signal and macd < signal:
                orders.append(
                    Order(
                        symbol=symbol,
                        side=OrderSide.SELL,
                        order_type=OrderType.MARKET,
                        quantity=current_qty,
                    )
                )
                logger.info(
                    f"MACD BEARISH CROSSOVER {symbol}: MACD={macd:.4f} < Signal={signal:.4f}"
                )

        elif self.signal_type == "zero_cross":
            # Bullish: MACD crosses above zero
            if current_qty == 0 and prev_macd <= 0 and macd > 0:
                qty = min(int(self.position_size / price), self.max_position)
                if qty > 0:
                    orders.append(
                        Order(
                            symbol=symbol,
                            side=OrderSide.BUY,
                            order_type=OrderType.MARKET,
                            quantity=qty,
                        )
                    )
                    logger.info(f"MACD ZERO CROSS UP {symbol}: MACD={macd:.4f}")

            # Bearish: MACD crosses below zero
            elif current_qty > 0 and prev_macd >= 0 and macd < 0:
                orders.append(
                    Order(
                        symbol=symbol,
                        side=OrderSide.SELL,
                        order_type=OrderType.MARKET,
                        quantity=current_qty,
                    )
                )
                logger.info(f"MACD ZERO CROSS DOWN {symbol}: MACD={macd:.4f}")

        elif self.signal_type == "histogram":
            # Bullish: Histogram turning positive and increasing
            if (
                current_qty == 0
                and prev_hist is not None
                and prev_hist <= 0
                and histogram > 0
            ):
                qty = min(int(self.position_size / price), self.max_position)
                if qty > 0:
                    orders.append(
                        Order(
                            symbol=symbol,
                            side=OrderSide.BUY,
                            order_type=OrderType.MARKET,
                            quantity=qty,
                        )
                    )
                    logger.info(f"MACD HISTOGRAM POSITIVE {symbol}: hist={histogram:.4f}")

            # Bearish: Histogram turning negative
            elif (
                current_qty > 0
                and prev_hist is not None
                and prev_hist >= 0
                and histogram < 0
            ):
                orders.append(
                    Order(
                        symbol=symbol,
                        side=OrderSide.SELL,
                        order_type=OrderType.MARKET,
                        quantity=current_qty,
                    )
                )
                logger.info(f"MACD HISTOGRAM NEGATIVE {symbol}: hist={histogram:.4f}")

        return orders
