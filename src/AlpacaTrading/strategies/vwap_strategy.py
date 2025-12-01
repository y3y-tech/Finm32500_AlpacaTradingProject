"""
VWAP (Volume Weighted Average Price) Mean Reversion Strategy.

Trades around VWAP - the average price weighted by volume throughout the day.
VWAP is heavily used by institutions and acts as a magnet for price.

Buy when price is below VWAP (cheap), sell when above VWAP (expensive).
Excellent for intraday mean reversion in liquid markets.
"""

from collections import deque
import logging

from AlpacaTrading.models import MarketDataPoint, Order, OrderSide, OrderType
from AlpacaTrading.trading.portfolio import TradingPortfolio
from .base import TradingStrategy

logger = logging.getLogger(__name__)


class VWAPStrategy(TradingStrategy):
    """
    VWAP mean reversion strategy.

    Logic:
    1. Calculate cumulative VWAP (sum(price * volume) / sum(volume))
    2. Buy when price < VWAP - threshold (trading below fair value)
    3. Sell when price > VWAP + threshold (trading above fair value)
    4. Optional: Reset VWAP calculation periodically (e.g., daily)

    Parameters:
        deviation_threshold: Price must be this % away from VWAP to trade (default: 0.005 = 0.5%)
        position_size: Target position size in dollars (default: 10000)
        max_position: Maximum position per symbol (default: 100 shares)
        reset_period: Reset VWAP after N ticks (0 = never reset, default: 0)
        min_samples: Minimum data points before trading (default: 10)
    """

    def __init__(
        self,
        deviation_threshold: float = 0.005,
        position_size: float = 10000,
        max_position: int = 100,
        reset_period: int = 0,
        min_samples: int = 10,
    ):
        super().__init__("VWAP_MeanReversion")

        # Parameter validation
        if deviation_threshold < 0:
            raise ValueError(
                f"deviation_threshold must be non-negative, got {deviation_threshold}"
            )
        if position_size <= 0:
            raise ValueError(f"position_size must be positive, got {position_size}")
        if max_position <= 0:
            raise ValueError(f"max_position must be positive, got {max_position}")
        if reset_period < 0:
            raise ValueError(f"reset_period must be non-negative, got {reset_period}")
        if min_samples <= 0:
            raise ValueError(f"min_samples must be positive, got {min_samples}")

        self.deviation_threshold = deviation_threshold
        self.position_size = position_size
        self.max_position = max_position
        self.reset_period = reset_period
        self.min_samples = min_samples

        # Track cumulative data for VWAP calculation
        self.cumulative_pv: dict[str, float] = {}  # sum(price * volume)
        self.cumulative_volume: dict[str, float] = {}  # sum(volume)
        self.vwap: dict[str, float] = {}
        self.tick_count: dict[str, int] = {}
        self.price_history: dict[str, deque] = {}  # For additional analysis

    def _reset_vwap(self, symbol: str) -> None:
        """Reset VWAP calculation for a symbol."""
        self.cumulative_pv[symbol] = 0.0
        self.cumulative_volume[symbol] = 0.0
        self.tick_count[symbol] = 0
        logger.info(f"Reset VWAP calculation for {symbol}")

    def _update_vwap(self, symbol: str, price: float, volume: float) -> float | None:
        """
        Update and return VWAP for symbol.

        Returns:
            Current VWAP or None if not enough data
        """
        # Initialize if new symbol
        if symbol not in self.cumulative_pv:
            self.cumulative_pv[symbol] = 0.0
            self.cumulative_volume[symbol] = 0.0
            self.tick_count[symbol] = 0
            self.price_history[symbol] = deque(maxlen=100)

        # Check if we should reset
        if self.reset_period > 0 and self.tick_count[symbol] >= self.reset_period:
            self._reset_vwap(symbol)

        # Update cumulative values
        self.cumulative_pv[symbol] += price * volume
        self.cumulative_volume[symbol] += volume
        self.tick_count[symbol] += 1
        self.price_history[symbol].append(price)

        # Calculate VWAP
        if self.cumulative_volume[symbol] == 0:
            return None

        if self.tick_count[symbol] < self.min_samples:
            return None

        vwap = self.cumulative_pv[symbol] / self.cumulative_volume[symbol]
        self.vwap[symbol] = vwap

        return vwap

    def on_market_data(
        self, tick: MarketDataPoint, portfolio: TradingPortfolio
    ) -> list[Order]:
        """
        Generate trading signals based on price deviation from VWAP.

        Returns:
            List of orders (buy below VWAP, sell above VWAP)
        """
        # Validate tick
        if tick.price <= 0:
            logger.warning(
                f"Invalid price {tick.price} for {tick.symbol}, skipping tick"
            )
            return []

        if tick.volume < 0:
            logger.warning(
                f"Invalid volume {tick.volume} for {tick.symbol}, skipping tick"
            )
            return []

        # Update VWAP
        vwap = self._update_vwap(tick.symbol, tick.price, tick.volume)
        if vwap is None:
            return []

        # Calculate deviation from VWAP
        deviation = (tick.price - vwap) / vwap
        deviation_pct = deviation * 100

        # Get current position
        position = portfolio.get_position(tick.symbol)
        current_qty = position.quantity if position else 0

        orders = []

        # Price significantly below VWAP -> BUY (cheap)
        if deviation < -self.deviation_threshold:
            if current_qty < self.max_position:
                quantity = min(
                    int(self.position_size / tick.price),
                    self.max_position - current_qty,
                )

                if quantity > 0:
                    logger.info(
                        f"BUY signal (BELOW VWAP) for {tick.symbol}: "
                        f"price={tick.price:.2f}, vwap={vwap:.2f}, "
                        f"deviation={deviation_pct:.2f}%, quantity={quantity}"
                    )
                    orders.append(
                        Order(
                            symbol=tick.symbol,
                            side=OrderSide.BUY,
                            order_type=OrderType.MARKET,
                            quantity=quantity,
                        )
                    )

        # Price significantly above VWAP -> SELL (expensive)
        elif deviation > self.deviation_threshold:
            if current_qty > 0:
                logger.info(
                    f"SELL signal (ABOVE VWAP) for {tick.symbol}: "
                    f"price={tick.price:.2f}, vwap={vwap:.2f}, "
                    f"deviation={deviation_pct:.2f}%, quantity={current_qty}"
                )
                orders.append(
                    Order(
                        symbol=tick.symbol,
                        side=OrderSide.SELL,
                        order_type=OrderType.MARKET,
                        quantity=current_qty,
                    )
                )

        # Price close to VWAP -> Neutral (no action)
        # This creates a "dead zone" around VWAP to avoid overtrading

        return orders

    def on_start(self, portfolio: TradingPortfolio) -> None:
        """Log strategy start."""
        super().on_start(portfolio)
        logger.info(
            f"VWAP Strategy configured: deviation_threshold={self.deviation_threshold * 100:.2f}%, "
            f"reset_period={self.reset_period if self.reset_period > 0 else 'never'}"
        )

    def __repr__(self) -> str:
        return f"VWAPStrategy(deviation={self.deviation_threshold * 100:.2f}%)"
