"""
Donchian Channel Breakout Strategy - Classic trend-following system.

Made famous by the Turtle Traders. Buys on breakout above N-period high,
sells on breakdown below M-period low.

Best for: Trending assets (commodities, currencies, EM)
Avoid: Range-bound markets, choppy conditions
"""

from collections import deque
import logging

from AlpacaTrading.models import MarketDataPoint, Order, OrderSide, OrderType
from AlpacaTrading.trading.portfolio import TradingPortfolio
from .base import TradingStrategy

logger = logging.getLogger(__name__)


class DonchianBreakoutStrategy(TradingStrategy):
    """
    Donchian Channel breakout strategy (Turtle Trading style).

    Logic:
    1. Track N-period high and M-period low
    2. Buy when price breaks above N-period high (long entry)
    3. Sell when price breaks below M-period low (exit)
    4. Optional: Short on breakdown, cover on breakup

    The asymmetric entry/exit periods (e.g., 20/10) allow riding trends
    while exiting faster on reversals.

    Parameters:
        entry_period: Lookback for entry signal (default: 20)
        exit_period: Lookback for exit signal (default: 10)
        position_size: Dollar amount per trade
        max_position: Maximum shares per symbol
        enable_shorting: Allow short positions (default: False)
    """

    def __init__(
        self,
        entry_period: int = 20,
        exit_period: int = 10,
        position_size: float = 10000,
        max_position: int = 100,
        enable_shorting: bool = False,
    ):
        super().__init__("DonchianBreakout")

        if entry_period <= 0:
            raise ValueError(f"entry_period must be positive, got {entry_period}")
        if exit_period <= 0:
            raise ValueError(f"exit_period must be positive, got {exit_period}")
        if exit_period > entry_period:
            raise ValueError("exit_period should be <= entry_period")

        self.entry_period = entry_period
        self.exit_period = exit_period
        self.position_size = position_size
        self.max_position = max_position
        self.enable_shorting = enable_shorting

        # Track high/low history per symbol
        self.high_history: dict[str, deque] = {}
        self.low_history: dict[str, deque] = {}

    def on_market_data(
        self, tick: MarketDataPoint, portfolio: TradingPortfolio
    ) -> list[Order]:
        symbol = tick.symbol
        price = tick.price

        # Initialize history for new symbols
        if symbol not in self.high_history:
            self.high_history[symbol] = deque(maxlen=self.entry_period)
            self.low_history[symbol] = deque(maxlen=self.entry_period)

        highs = self.high_history[symbol]
        lows = self.low_history[symbol]

        # Add current price as high/low (intraday bars would have separate H/L)
        highs.append(price)
        lows.append(price)

        # Need full history
        if len(highs) < self.entry_period:
            return []

        # Calculate channels
        entry_high = max(list(highs)[-self.entry_period:])
        entry_low = min(list(lows)[-self.entry_period:])
        exit_high = max(list(highs)[-self.exit_period:])
        exit_low = min(list(lows)[-self.exit_period:])

        position = portfolio.get_position(symbol)
        current_qty = position.quantity if position else 0

        orders = []

        # Long entry: break above entry_high
        if current_qty == 0 and price >= entry_high:
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
                    f"DONCHIAN LONG {symbol}: price {price:.2f} >= "
                    f"{self.entry_period}-period high {entry_high:.2f}"
                )

        # Long exit: break below exit_low
        elif current_qty > 0 and price <= exit_low:
            orders.append(
                Order(
                    symbol=symbol,
                    side=OrderSide.SELL,
                    order_type=OrderType.MARKET,
                    quantity=current_qty,
                )
            )
            logger.info(
                f"DONCHIAN EXIT LONG {symbol}: price {price:.2f} <= "
                f"{self.exit_period}-period low {exit_low:.2f}"
            )

        # Short entry: break below entry_low
        elif self.enable_shorting and current_qty == 0 and price <= entry_low:
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
                    f"DONCHIAN SHORT {symbol}: price {price:.2f} <= "
                    f"{self.entry_period}-period low {entry_low:.2f}"
                )

        # Short exit: break above exit_high
        elif current_qty < 0 and price >= exit_high:
            orders.append(
                Order(
                    symbol=symbol,
                    side=OrderSide.BUY,
                    order_type=OrderType.MARKET,
                    quantity=abs(current_qty),
                )
            )
            logger.info(
                f"DONCHIAN COVER SHORT {symbol}: price {price:.2f} >= "
                f"{self.exit_period}-period high {exit_high:.2f}"
            )

        return orders
