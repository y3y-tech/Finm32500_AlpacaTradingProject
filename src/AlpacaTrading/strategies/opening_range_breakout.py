"""
Opening Range Breakout (ORB) Strategy.

Classic intraday strategy that trades breakouts from the opening range
established in the first N minutes of trading.

Best for: Intraday trading, high-volume stocks
Works well with: US equities during market hours
Note: Requires intraday data with timestamps
"""

from collections import deque
from datetime import datetime, time
import logging

from AlpacaTrading.models import MarketDataPoint, Order, OrderSide, OrderType
from AlpacaTrading.trading.portfolio import TradingPortfolio
from .base import TradingStrategy

logger = logging.getLogger(__name__)


class OpeningRangeBreakoutStrategy(TradingStrategy):
    """
    Opening Range Breakout strategy.

    Logic:
    1. Track high/low during opening range period (first N minutes)
    2. After range established, buy on breakout above range high
    3. Sell on breakdown below range low or at end of day
    4. Optional: Use range size as volatility filter

    Parameters:
        range_minutes: Minutes to establish opening range (default: 30)
        breakout_buffer: % above/below range to confirm breakout (default: 0.1%)
        min_range_pct: Minimum range size to trade (default: 0.3%)
        max_range_pct: Maximum range size to trade (default: 3.0%)
        position_size: Dollar amount per trade
        max_position: Maximum shares per symbol
        exit_time: Time to exit all positions (default: 15:45)
    """

    def __init__(
        self,
        range_minutes: int = 30,
        breakout_buffer: float = 0.001,
        min_range_pct: float = 0.003,
        max_range_pct: float = 0.03,
        position_size: float = 10000,
        max_position: int = 100,
        exit_hour: int = 15,
        exit_minute: int = 45,
    ):
        super().__init__("OpeningRangeBreakout")

        if range_minutes <= 0:
            raise ValueError(f"range_minutes must be positive, got {range_minutes}")

        self.range_minutes = range_minutes
        self.breakout_buffer = breakout_buffer
        self.min_range_pct = min_range_pct
        self.max_range_pct = max_range_pct
        self.position_size = position_size
        self.max_position = max_position
        self.exit_time = time(exit_hour, exit_minute)

        # State per symbol per day
        self.current_date: dict[str, datetime | None] = {}
        self.range_high: dict[str, float | None] = {}
        self.range_low: dict[str, float | None] = {}
        self.range_established: dict[str, bool] = {}
        self.opening_prices: dict[str, list] = {}
        self.range_start_time: dict[str, datetime | None] = {}
        self.traded_today: dict[str, bool] = {}

    def _reset_for_new_day(self, symbol: str):
        """Reset state for new trading day."""
        self.range_high[symbol] = None
        self.range_low[symbol] = None
        self.range_established[symbol] = False
        self.opening_prices[symbol] = []
        self.range_start_time[symbol] = None
        self.traded_today[symbol] = False

    def _is_market_open(self, tick_time: datetime) -> bool:
        """Check if within regular market hours."""
        market_open = time(9, 30)
        market_close = time(16, 0)
        return market_open <= tick_time.time() <= market_close

    def _is_in_opening_range(self, tick_time: datetime, symbol: str) -> bool:
        """Check if still in opening range period."""
        if self.range_start_time.get(symbol) is None:
            return True

        start = self.range_start_time[symbol]
        elapsed_minutes = (tick_time - start).total_seconds() / 60
        return elapsed_minutes < self.range_minutes

    def on_market_data(
        self, tick: MarketDataPoint, portfolio: TradingPortfolio
    ) -> list[Order]:
        symbol = tick.symbol
        price = tick.price
        tick_time = tick.timestamp

        # Check for new trading day
        tick_date = tick_time.date()
        if self.current_date.get(symbol) != tick_date:
            self.current_date[symbol] = tick_date
            self._reset_for_new_day(symbol)

        # Skip if outside market hours
        if not self._is_market_open(tick_time):
            return []

        position = portfolio.get_position(symbol)
        current_qty = position.quantity if position else 0

        orders = []

        # Exit at end of day
        if tick_time.time() >= self.exit_time and current_qty != 0:
            side = OrderSide.SELL if current_qty > 0 else OrderSide.BUY
            orders.append(
                Order(
                    symbol=symbol,
                    side=side,
                    order_type=OrderType.MARKET,
                    quantity=abs(current_qty),
                )
            )
            logger.info(f"ORB EOD EXIT {symbol}: closing position at {tick_time.time()}")
            return orders

        # Building opening range
        if not self.range_established.get(symbol, False):
            if self.range_start_time.get(symbol) is None:
                self.range_start_time[symbol] = tick_time

            if self._is_in_opening_range(tick_time, symbol):
                # Track high/low
                self.opening_prices[symbol].append(price)
                self.range_high[symbol] = max(
                    self.range_high[symbol] or price, price
                )
                self.range_low[symbol] = min(
                    self.range_low[symbol] or price, price
                )
                return []
            else:
                # Range period ended - establish range
                self.range_established[symbol] = True

                if self.range_high[symbol] and self.range_low[symbol]:
                    range_size = (
                        self.range_high[symbol] - self.range_low[symbol]
                    ) / self.range_low[symbol]

                    logger.info(
                        f"ORB RANGE ESTABLISHED {symbol}: "
                        f"High={self.range_high[symbol]:.2f}, "
                        f"Low={self.range_low[symbol]:.2f}, "
                        f"Size={range_size*100:.2f}%"
                    )

                    # Check if range size is tradeable
                    if range_size < self.min_range_pct:
                        logger.info(f"ORB {symbol}: Range too small, skipping")
                        self.traded_today[symbol] = True  # Don't trade
                    elif range_size > self.max_range_pct:
                        logger.info(f"ORB {symbol}: Range too large, skipping")
                        self.traded_today[symbol] = True

        # Trading after range established
        if (
            self.range_established.get(symbol, False)
            and not self.traded_today.get(symbol, False)
        ):
            range_high = self.range_high[symbol]
            range_low = self.range_low[symbol]

            if range_high is None or range_low is None:
                return []

            breakout_high = range_high * (1 + self.breakout_buffer)
            breakout_low = range_low * (1 - self.breakout_buffer)

            # Long breakout
            if current_qty == 0 and price > breakout_high:
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
                    self.traded_today[symbol] = True
                    logger.info(
                        f"ORB LONG BREAKOUT {symbol}: {price:.2f} > {breakout_high:.2f}"
                    )

            # Stop loss if long and breaks down
            elif current_qty > 0 and price < breakout_low:
                orders.append(
                    Order(
                        symbol=symbol,
                        side=OrderSide.SELL,
                        order_type=OrderType.MARKET,
                        quantity=current_qty,
                    )
                )
                logger.info(
                    f"ORB STOP LOSS {symbol}: {price:.2f} < {breakout_low:.2f}"
                )

        return orders
