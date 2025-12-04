"""
Stochastic Oscillator Strategy - Momentum oscillator for overbought/oversold.

Compares closing price to price range over N periods. Works well in
ranging markets to identify potential reversal points.

Best for: Range-bound markets, counter-trend trades
Works well with: Sector ETFs, stable equities
"""

from collections import deque
import logging

from AlpacaTrading.models import MarketDataPoint, Order, OrderSide, OrderType
from AlpacaTrading.trading.portfolio import TradingPortfolio
from .base import TradingStrategy

logger = logging.getLogger(__name__)


class StochasticStrategy(TradingStrategy):
    """
    Stochastic Oscillator strategy.

    %K = (Current Close - Lowest Low) / (Highest High - Lowest Low) * 100
    %D = SMA of %K (signal line)

    Signal Types:
    - oversold: Buy when %K < oversold_threshold, sell when %K > overbought_threshold
    - crossover: Buy when %K crosses above %D from oversold, sell on opposite

    Parameters:
        k_period: Lookback for %K calculation (default: 14)
        d_period: Smoothing period for %D (default: 3)
        oversold_threshold: Buy below this (default: 20)
        overbought_threshold: Sell above this (default: 80)
        signal_type: 'oversold' or 'crossover'
        position_size: Dollar amount per trade
        max_position: Maximum shares per symbol
        use_slow_stoch: Use slow stochastic (smooth %K first)
    """

    def __init__(
        self,
        k_period: int = 14,
        d_period: int = 3,
        oversold_threshold: float = 20,
        overbought_threshold: float = 80,
        signal_type: str = "oversold",
        position_size: float = 10000,
        max_position: int = 100,
        use_slow_stoch: bool = True,
    ):
        super().__init__("Stochastic")

        if k_period <= 0:
            raise ValueError(f"k_period must be positive, got {k_period}")
        if d_period <= 0:
            raise ValueError(f"d_period must be positive, got {d_period}")
        if oversold_threshold >= overbought_threshold:
            raise ValueError("oversold_threshold must be < overbought_threshold")

        self.k_period = k_period
        self.d_period = d_period
        self.oversold_threshold = oversold_threshold
        self.overbought_threshold = overbought_threshold
        self.signal_type = signal_type
        self.position_size = position_size
        self.max_position = max_position
        self.use_slow_stoch = use_slow_stoch

        # History per symbol
        self.price_history: dict[str, deque] = {}
        self.k_history: dict[str, deque] = {}
        self.prev_k: dict[str, float | None] = {}
        self.prev_d: dict[str, float | None] = {}

    def _calculate_stochastic(self, prices: list[float]) -> tuple[float, float] | None:
        """Calculate %K and %D."""
        if len(prices) < self.k_period:
            return None

        recent = prices[-self.k_period :]
        highest_high = max(recent)
        lowest_low = min(recent)

        if highest_high == lowest_low:
            return None

        # Raw %K
        k = ((prices[-1] - lowest_low) / (highest_high - lowest_low)) * 100

        return k, k  # Will calculate %D separately

    def on_market_data(
        self, tick: MarketDataPoint, portfolio: TradingPortfolio
    ) -> list[Order]:
        symbol = tick.symbol
        price = tick.price

        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=self.k_period + 10)
            self.k_history[symbol] = deque(maxlen=self.d_period + 5)

        self.price_history[symbol].append(price)
        prices = list(self.price_history[symbol])

        result = self._calculate_stochastic(prices)
        if result is None:
            return []

        raw_k, _ = result

        # Store %K for slow stochastic / %D calculation
        self.k_history[symbol].append(raw_k)
        k_values = list(self.k_history[symbol])

        # Calculate %K (smoothed for slow stochastic)
        if self.use_slow_stoch and len(k_values) >= self.d_period:
            k = sum(k_values[-self.d_period :]) / self.d_period
        else:
            k = raw_k

        # Calculate %D (SMA of %K)
        if len(k_values) >= self.d_period:
            d = sum(k_values[-self.d_period :]) / self.d_period
        else:
            d = k

        prev_k = self.prev_k.get(symbol)
        prev_d = self.prev_d.get(symbol)

        self.prev_k[symbol] = k
        self.prev_d[symbol] = d

        position = portfolio.get_position(symbol)
        current_qty = position.quantity if position else 0

        orders = []

        if self.signal_type == "oversold":
            # Buy in oversold territory
            if current_qty == 0 and k < self.oversold_threshold:
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
                        f"STOCH OVERSOLD BUY {symbol}: %K={k:.1f} < {self.oversold_threshold}"
                    )

            # Sell in overbought territory
            elif current_qty > 0 and k > self.overbought_threshold:
                orders.append(
                    Order(
                        symbol=symbol,
                        side=OrderSide.SELL,
                        order_type=OrderType.MARKET,
                        quantity=current_qty,
                    )
                )
                logger.info(
                    f"STOCH OVERBOUGHT SELL {symbol}: %K={k:.1f} > {self.overbought_threshold}"
                )

        elif (
            self.signal_type == "crossover"
            and prev_k is not None
            and prev_d is not None
        ):
            # Bullish crossover from oversold
            if (
                current_qty == 0
                and k < self.oversold_threshold + 10  # Near oversold
                and prev_k <= prev_d
                and k > d
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
                    logger.info(
                        f"STOCH BULLISH CROSSOVER {symbol}: %K={k:.1f} crossed above %D={d:.1f}"
                    )

            # Bearish crossover from overbought
            elif (
                current_qty > 0
                and k > self.overbought_threshold - 10  # Near overbought
                and prev_k >= prev_d
                and k < d
            ):
                orders.append(
                    Order(
                        symbol=symbol,
                        side=OrderSide.SELL,
                        order_type=OrderType.MARKET,
                        quantity=current_qty,
                    )
                )
                logger.info(
                    f"STOCH BEARISH CROSSOVER {symbol}: %K={k:.1f} crossed below %D={d:.1f}"
                )

        return orders
