"""
ADX (Average Directional Index) Trend Strategy.

ADX measures trend strength (not direction). Combined with +DI/-DI
to determine trend direction. Only trades when trend is strong.

Best for: Avoiding whipsaws in choppy markets
Works well with: Any trend-following strategy as a filter
"""

from collections import deque
import logging

from AlpacaTrading.models import MarketDataPoint, Order, OrderSide, OrderType
from AlpacaTrading.trading.portfolio import TradingPortfolio
from .base import TradingStrategy

logger = logging.getLogger(__name__)


class ADXTrendStrategy(TradingStrategy):
    """
    ADX-based trend strength strategy.

    Components:
    - +DI: Positive directional indicator (uptrend strength)
    - -DI: Negative directional indicator (downtrend strength)
    - ADX: Average of directional movement (trend strength)

    Logic:
    1. Only trade when ADX > threshold (strong trend)
    2. Go long when +DI > -DI (uptrend)
    3. Go short/exit when -DI > +DI (downtrend)

    Parameters:
        adx_period: Period for ADX calculation (default: 14)
        adx_threshold: Minimum ADX to trade (default: 25)
        di_threshold: Minimum DI difference (default: 5)
        position_size: Dollar amount per trade
        max_position: Maximum shares per symbol
        enable_shorting: Allow short positions (default: False)
    """

    def __init__(
        self,
        adx_period: int = 14,
        adx_threshold: float = 25,
        di_threshold: float = 5,
        position_size: float = 10000,
        max_position: int = 100,
        enable_shorting: bool = False,
    ):
        super().__init__("ADXTrend")

        if adx_period <= 1:
            raise ValueError(f"adx_period must be > 1, got {adx_period}")
        if adx_threshold < 0:
            raise ValueError(f"adx_threshold must be non-negative, got {adx_threshold}")

        self.adx_period = adx_period
        self.adx_threshold = adx_threshold
        self.di_threshold = di_threshold
        self.position_size = position_size
        self.max_position = max_position
        self.enable_shorting = enable_shorting

        # History per symbol
        self.price_history: dict[str, deque] = {}
        self.tr_history: dict[str, deque] = {}
        self.plus_dm_history: dict[str, deque] = {}
        self.minus_dm_history: dict[str, deque] = {}
        self.prev_price: dict[str, float | None] = {}

        # Smoothed values
        self.smoothed_tr: dict[str, float | None] = {}
        self.smoothed_plus_dm: dict[str, float | None] = {}
        self.smoothed_minus_dm: dict[str, float | None] = {}
        self.adx: dict[str, float | None] = {}
        self.dx_history: dict[str, deque] = {}

    def _calculate_directional_movement(
        self, current_price: float, prev_price: float
    ) -> tuple[float, float, float]:
        """
        Calculate True Range and Directional Movement.
        
        Simplified version using price changes (full version needs High/Low).
        """
        # Simplified TR (would use High-Low, |High-PrevClose|, |Low-PrevClose| normally)
        tr = abs(current_price - prev_price)

        # Directional movement
        price_change = current_price - prev_price

        if price_change > 0:
            plus_dm = price_change
            minus_dm = 0
        elif price_change < 0:
            plus_dm = 0
            minus_dm = abs(price_change)
        else:
            plus_dm = 0
            minus_dm = 0

        return tr, plus_dm, minus_dm

    def _smooth_value(
        self, current: float | None, new_value: float, period: int
    ) -> float:
        """Wilder's smoothing method."""
        if current is None:
            return new_value
        return current - (current / period) + new_value

    def on_market_data(
        self, tick: MarketDataPoint, portfolio: TradingPortfolio
    ) -> list[Order]:
        symbol = tick.symbol
        price = tick.price

        # Initialize
        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=self.adx_period + 10)
            self.tr_history[symbol] = deque(maxlen=self.adx_period)
            self.plus_dm_history[symbol] = deque(maxlen=self.adx_period)
            self.minus_dm_history[symbol] = deque(maxlen=self.adx_period)
            self.dx_history[symbol] = deque(maxlen=self.adx_period)

        self.price_history[symbol].append(price)
        prev_price = self.prev_price.get(symbol)
        self.prev_price[symbol] = price

        if prev_price is None:
            return []

        # Calculate directional movement
        tr, plus_dm, minus_dm = self._calculate_directional_movement(price, prev_price)

        self.tr_history[symbol].append(tr)
        self.plus_dm_history[symbol].append(plus_dm)
        self.minus_dm_history[symbol].append(minus_dm)

        # Need enough history
        if len(self.tr_history[symbol]) < self.adx_period:
            return []

        # Smooth TR and DMs using Wilder's method
        self.smoothed_tr[symbol] = self._smooth_value(
            self.smoothed_tr.get(symbol), tr, self.adx_period
        )
        self.smoothed_plus_dm[symbol] = self._smooth_value(
            self.smoothed_plus_dm.get(symbol), plus_dm, self.adx_period
        )
        self.smoothed_minus_dm[symbol] = self._smooth_value(
            self.smoothed_minus_dm.get(symbol), minus_dm, self.adx_period
        )

        smoothed_tr = self.smoothed_tr[symbol]
        if smoothed_tr == 0:
            return []

        # Calculate +DI and -DI
        plus_di = (self.smoothed_plus_dm[symbol] / smoothed_tr) * 100
        minus_di = (self.smoothed_minus_dm[symbol] / smoothed_tr) * 100

        # Calculate DX
        di_sum = plus_di + minus_di
        if di_sum == 0:
            return []

        dx = (abs(plus_di - minus_di) / di_sum) * 100
        self.dx_history[symbol].append(dx)

        # Calculate ADX (smoothed DX)
        if len(self.dx_history[symbol]) < self.adx_period:
            return []

        if self.adx.get(symbol) is None:
            # Initialize ADX as average of DX values
            self.adx[symbol] = sum(self.dx_history[symbol]) / len(self.dx_history[symbol])
        else:
            # Smooth ADX
            self.adx[symbol] = self._smooth_value(
                self.adx[symbol], dx, self.adx_period
            )

        adx = self.adx[symbol]

        position = portfolio.get_position(symbol)
        current_qty = position.quantity if position else 0

        orders = []

        # Only trade if trend is strong enough
        if adx < self.adx_threshold:
            # Trend too weak - exit any position
            if current_qty > 0:
                orders.append(
                    Order(
                        symbol=symbol,
                        side=OrderSide.SELL,
                        order_type=OrderType.MARKET,
                        quantity=current_qty,
                    )
                )
                logger.info(
                    f"ADX EXIT {symbol}: ADX={adx:.1f} < threshold {self.adx_threshold}"
                )
            elif current_qty < 0:
                orders.append(
                    Order(
                        symbol=symbol,
                        side=OrderSide.BUY,
                        order_type=OrderType.MARKET,
                        quantity=abs(current_qty),
                    )
                )
            return orders

        # Strong trend - check direction
        di_diff = plus_di - minus_di

        # Long signal: +DI > -DI with sufficient difference
        if current_qty <= 0 and di_diff > self.di_threshold:
            # Close short if any
            if current_qty < 0:
                orders.append(
                    Order(
                        symbol=symbol,
                        side=OrderSide.BUY,
                        order_type=OrderType.MARKET,
                        quantity=abs(current_qty),
                    )
                )

            # Open long
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
                    f"ADX LONG {symbol}: ADX={adx:.1f}, +DI={plus_di:.1f}, -DI={minus_di:.1f}"
                )

        # Short signal: -DI > +DI with sufficient difference
        elif di_diff < -self.di_threshold:
            # Close long if any
            if current_qty > 0:
                orders.append(
                    Order(
                        symbol=symbol,
                        side=OrderSide.SELL,
                        order_type=OrderType.MARKET,
                        quantity=current_qty,
                    )
                )
                logger.info(
                    f"ADX EXIT LONG {symbol}: -DI dominant, ADX={adx:.1f}"
                )

            # Open short if enabled
            if self.enable_shorting and current_qty >= 0:
                qty = min(int(self.position_size / price), self.max_position)
                if qty > 0:
                    orders.append(
                        Order(
                            symbol=symbol,
                            side=OrderSide.SELL,
                            order_type=OrderType.MARKET,
                            quantity=qty,
                        )
                    )
                    logger.info(
                        f"ADX SHORT {symbol}: ADX={adx:.1f}, +DI={plus_di:.1f}, -DI={minus_di:.1f}"
                    )

        return orders
