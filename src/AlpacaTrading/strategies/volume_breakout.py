"""
Volume Breakout Strategy - Trade unusual volume spikes with price momentum.

Combines price momentum with volume confirmation to catch strong moves.
High volume indicates institutional participation and conviction.

This strategy is excellent for catching breakouts, earnings moves, and news-driven rallies.
Suitable for short-term trading with quick entries and exits.
"""

from collections import deque
import logging

from AlpacaTrading.models import MarketDataPoint, Order, OrderSide, OrderType
from AlpacaTrading.trading.portfolio import TradingPortfolio
from .base import TradingStrategy

logger = logging.getLogger(__name__)


class VolumeBreakoutStrategy(TradingStrategy):
    """
    Volume breakout strategy with price confirmation.

    Logic:
    1. Calculate average volume over lookback period
    2. Detect volume spikes (volume > avg_volume * volume_multiplier)
    3. Confirm price momentum (price > recent prices)
    4. Buy on confirmed volume breakout
    5. Exit when volume normalizes or price reverses

    Parameters:
        volume_period: Period for average volume calculation (default: 20)
        volume_multiplier: Volume must be this many times average (default: 2.0)
        price_momentum_period: Period for price momentum check (default: 5)
        min_price_change: Minimum price change % to confirm breakout (default: 0.01 = 1%)
        position_size: Target position size in dollars (default: 10000)
        max_position: Maximum position per symbol (default: 100 shares)
        hold_periods: Maximum ticks to hold position (default: 50)
    """

    def __init__(
        self,
        volume_period: int = 20,
        volume_multiplier: float = 2.0,
        price_momentum_period: int = 5,
        min_price_change: float = 0.01,
        position_size: float = 10000,
        max_position: int = 100,
        hold_periods: int = 50,
    ):
        super().__init__("VolumeBreakout")

        # Parameter validation
        if volume_period <= 1:
            raise ValueError(f"volume_period must be > 1, got {volume_period}")
        if volume_multiplier <= 1.0:
            raise ValueError(
                f"volume_multiplier must be > 1.0, got {volume_multiplier}"
            )
        if price_momentum_period <= 0:
            raise ValueError(
                f"price_momentum_period must be positive, got {price_momentum_period}"
            )
        if min_price_change < 0:
            raise ValueError(
                f"min_price_change must be non-negative, got {min_price_change}"
            )
        if position_size <= 0:
            raise ValueError(f"position_size must be positive, got {position_size}")
        if max_position <= 0:
            raise ValueError(f"max_position must be positive, got {max_position}")
        if hold_periods <= 0:
            raise ValueError(f"hold_periods must be positive, got {hold_periods}")

        self.volume_period = volume_period
        self.volume_multiplier = volume_multiplier
        self.price_momentum_period = price_momentum_period
        self.min_price_change = min_price_change
        self.position_size = position_size
        self.max_position = max_position
        self.hold_periods = hold_periods

        # Track volume and price history
        self.volume_history: dict[str, deque] = {}
        self.price_history: dict[str, deque] = {}
        self.avg_volume: dict[str, float] = {}
        self.entry_tick: dict[str, int] = {}  # Track when position was entered
        self.current_tick: dict[str, int] = {}  # Track tick count per symbol

    def _calculate_avg_volume(self, symbol: str) -> float | None:
        """Calculate average volume over period."""
        volumes = list(self.volume_history[symbol])
        if len(volumes) < self.volume_period:
            return None
        return sum(volumes[-self.volume_period :]) / self.volume_period

    def _check_price_momentum(self, symbol: str, current_price: float) -> bool:
        """Check if price has positive momentum."""
        prices = list(self.price_history[symbol])
        if len(prices) < self.price_momentum_period:
            return False

        # Check if current price is higher than recent average
        recent_prices = prices[-self.price_momentum_period :]
        avg_recent_price = sum(recent_prices) / len(recent_prices)

        price_change_pct = (current_price - avg_recent_price) / avg_recent_price

        return price_change_pct >= self.min_price_change

    def on_market_data(
        self, tick: MarketDataPoint, portfolio: TradingPortfolio
    ) -> list[Order]:
        """
        Generate trading signals based on volume breakouts with price confirmation.

        Returns:
            List of orders (buy on volume breakout, sell on fade or time exit)
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

        # Initialize for new symbol
        if tick.symbol not in self.volume_history:
            self.volume_history[tick.symbol] = deque(maxlen=self.volume_period + 10)
            self.price_history[tick.symbol] = deque(
                maxlen=max(self.price_momentum_period, 20)
            )
            self.current_tick[tick.symbol] = 0
            logger.info(f"Initialized volume breakout tracking for {tick.symbol}")

        # Update histories
        self.volume_history[tick.symbol].append(tick.volume)
        self.price_history[tick.symbol].append(tick.price)
        self.current_tick[tick.symbol] += 1

        # Calculate average volume
        avg_vol = self._calculate_avg_volume(tick.symbol)
        if avg_vol is None or avg_vol == 0:
            return []

        self.avg_volume[tick.symbol] = avg_vol

        # Get current position
        position = portfolio.get_position(tick.symbol)
        current_qty = position.quantity if position else 0

        orders = []

        # Check if holding position
        if current_qty > 0 and tick.symbol in self.entry_tick:
            ticks_held = self.current_tick[tick.symbol] - self.entry_tick[tick.symbol]

            # Exit if held too long (time-based exit)
            if ticks_held >= self.hold_periods:
                logger.info(
                    f"SELL signal (TIME EXIT) for {tick.symbol}: held for {ticks_held} ticks"
                )
                orders.append(
                    Order(
                        symbol=tick.symbol,
                        side=OrderSide.SELL,
                        order_type=OrderType.MARKET,
                        quantity=current_qty,
                    )
                )
                del self.entry_tick[tick.symbol]
                return orders

            # Exit if volume drops back to normal (breakout fading)
            if tick.volume < avg_vol * 1.2:  # Volume dropped below 1.2x average
                logger.info(
                    f"SELL signal (VOLUME FADE) for {tick.symbol}: volume={tick.volume:.0f}, "
                    f"avg_volume={avg_vol:.0f}"
                )
                orders.append(
                    Order(
                        symbol=tick.symbol,
                        side=OrderSide.SELL,
                        order_type=OrderType.MARKET,
                        quantity=current_qty,
                    )
                )
                del self.entry_tick[tick.symbol]
                return orders

        # Detect volume breakout
        volume_spike = tick.volume > avg_vol * self.volume_multiplier

        if volume_spike:
            # Confirm with price momentum
            has_momentum = self._check_price_momentum(tick.symbol, tick.price)

            if has_momentum and current_qty < self.max_position:
                quantity = min(
                    int(self.position_size / tick.price),
                    self.max_position - current_qty,
                )

                if quantity > 0:
                    volume_ratio = tick.volume / avg_vol
                    prices = list(self.price_history[tick.symbol])
                    price_change = (
                        (tick.price - prices[-self.price_momentum_period])
                        / prices[-self.price_momentum_period]
                        * 100
                    )

                    logger.info(
                        f"BUY signal (VOLUME BREAKOUT) for {tick.symbol}: "
                        f"volume={tick.volume:.0f} ({volume_ratio:.1f}x avg), "
                        f"price_change={price_change:.2f}%, quantity={quantity}"
                    )
                    orders.append(
                        Order(
                            symbol=tick.symbol,
                            side=OrderSide.BUY,
                            order_type=OrderType.MARKET,
                            quantity=quantity,
                        )
                    )
                    # Track entry tick
                    self.entry_tick[tick.symbol] = self.current_tick[tick.symbol]

        return orders

    def __repr__(self) -> str:
        return (
            f"VolumeBreakoutStrategy(vol_mult={self.volume_multiplier}x, "
            f"period={self.volume_period})"
        )
