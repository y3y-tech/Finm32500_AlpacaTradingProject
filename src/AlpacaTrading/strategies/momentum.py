"""
Momentum Strategy - Trade based on price velocity and trend strength.

Buys when price momentum is positive and strong, sells when negative.
"""

from collections import deque

from AlpacaTrading.models import MarketDataPoint, Order, OrderSide, OrderType
from AlpacaTrading.trading.portfolio import TradingPortfolio
from .base import TradingStrategy


class MomentumStrategy(TradingStrategy):
    """
    Momentum-based trading strategy.

    Logic:
    1. Calculate price momentum (rate of change over lookback period)
    2. Buy when momentum > threshold (uptrend)
    3. Sell when momentum < -threshold (downtrend)
    4. Manage position size based on momentum strength

    Parameters:
        lookback_period: Number of ticks to calculate momentum (default: 20)
        momentum_threshold: Minimum momentum to trigger trade (default: 0.01 = 1%)
        position_size: Base position size in dollars (default: 10000)
        max_position: Maximum position per symbol (default: 100 shares)
    """

    def __init__(
        self,
        lookback_period: int = 20,
        momentum_threshold: float = 0.01,
        position_size: float = 10000,
        max_position: int = 100
    ):
        super().__init__("MomentumStrategy")
        self.lookback_period = lookback_period
        self.momentum_threshold = momentum_threshold
        self.position_size = position_size
        self.max_position = max_position

        # Track price history per symbol
        self.price_history: dict[str, deque] = {}

    def on_market_data(
        self,
        tick: MarketDataPoint,
        portfolio: TradingPortfolio
    ) -> list[Order]:
        """
        Generate trading signals based on momentum.

        Returns:
            List of orders (buy/sell based on momentum)
        """
        # Initialize price history for new symbol
        if tick.symbol not in self.price_history:
            self.price_history[tick.symbol] = deque(maxlen=self.lookback_period)

        # Update price history
        self.price_history[tick.symbol].append(tick.price)

        # Need enough history to calculate momentum
        if len(self.price_history[tick.symbol]) < self.lookback_period:
            return []

        # Calculate momentum (percentage change over lookback period)
        prices = list(self.price_history[tick.symbol])
        momentum = (prices[-1] - prices[0]) / prices[0]

        # Get current position
        position = portfolio.get_position(tick.symbol)
        current_qty = position.quantity if position else 0

        orders = []

        # Strong positive momentum -> BUY
        if momentum > self.momentum_threshold:
            # Only buy if not already long or below max position
            if current_qty < self.max_position:
                # Calculate quantity based on position size
                target_value = self.position_size
                quantity = min(
                    int(target_value / tick.price),
                    self.max_position - current_qty
                )

                if quantity > 0:
                    orders.append(Order(
                        symbol=tick.symbol,
                        side=OrderSide.BUY,
                        order_type=OrderType.MARKET,
                        quantity=quantity
                    ))

        # Strong negative momentum -> SELL
        elif momentum < -self.momentum_threshold:
            # Only sell if we have a position
            if current_qty > 0:
                # Sell entire position
                orders.append(Order(
                    symbol=tick.symbol,
                    side=OrderSide.SELL,
                    order_type=OrderType.MARKET,
                    quantity=current_qty
                ))

        return orders

    def __repr__(self) -> str:
        return (
            f"MomentumStrategy(lookback={self.lookback_period}, "
            f"threshold={self.momentum_threshold:.3f})"
        )
