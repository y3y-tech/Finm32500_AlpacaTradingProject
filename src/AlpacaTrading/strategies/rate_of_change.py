"""
Rate of Change (ROC) Momentum Strategy - Pure price momentum indicator.

ROC measures the percentage change over N periods, giving a clear
momentum signal. Simpler and often more effective than complex indicators.

Best for: Trending assets, momentum plays
Works well with: EM, commodities, sector rotation
"""

from collections import deque
import logging

from AlpacaTrading.models import MarketDataPoint, Order, OrderSide, OrderType
from AlpacaTrading.trading.portfolio import TradingPortfolio
from .base import TradingStrategy

logger = logging.getLogger(__name__)


class RateOfChangeStrategy(TradingStrategy):
    """
    Rate of Change momentum strategy.

    ROC = (Current Price - Price N periods ago) / Price N periods ago * 100

    Logic:
    1. Calculate ROC over lookback period
    2. Buy when ROC > entry_threshold (strong upward momentum)
    3. Sell when ROC < exit_threshold (momentum fading)
    4. Optional: Short when ROC < -entry_threshold

    Parameters:
        lookback_period: Periods for ROC calculation (default: 12)
        entry_threshold: ROC % to enter long (default: 2.0 = 2%)
        exit_threshold: ROC % to exit (default: 0.0 = momentum turning)
        position_size: Dollar amount per trade
        max_position: Maximum shares per symbol
        enable_shorting: Allow short positions (default: False)
        use_smoothing: Apply EMA smoothing to ROC (default: False)
        smoothing_period: EMA period for smoothing (default: 3)
    """

    def __init__(
        self,
        lookback_period: int = 12,
        entry_threshold: float = 2.0,
        exit_threshold: float = 0.0,
        position_size: float = 10000,
        max_position: int = 100,
        enable_shorting: bool = False,
        use_smoothing: bool = False,
        smoothing_period: int = 3,
    ):
        super().__init__("RateOfChange")

        if lookback_period <= 0:
            raise ValueError(f"lookback_period must be positive, got {lookback_period}")

        self.lookback_period = lookback_period
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.position_size = position_size
        self.max_position = max_position
        self.enable_shorting = enable_shorting
        self.use_smoothing = use_smoothing
        self.smoothing_period = smoothing_period

        self.price_history: dict[str, deque] = {}
        self.roc_history: dict[str, deque] = {}
        self.smoothed_roc: dict[str, float | None] = {}

    def _calculate_roc(self, prices: list[float]) -> float | None:
        """Calculate Rate of Change."""
        if len(prices) <= self.lookback_period:
            return None

        current = prices[-1]
        past = prices[-(self.lookback_period + 1)]

        if past == 0:
            return None

        return ((current - past) / past) * 100

    def _smooth_roc(self, symbol: str, roc: float) -> float:
        """Apply EMA smoothing to ROC."""
        if symbol not in self.roc_history:
            self.roc_history[symbol] = deque(maxlen=self.smoothing_period + 5)

        self.roc_history[symbol].append(roc)

        if self.smoothed_roc.get(symbol) is None:
            # Initialize with SMA
            rocs = list(self.roc_history[symbol])
            if len(rocs) >= self.smoothing_period:
                self.smoothed_roc[symbol] = (
                    sum(rocs[-self.smoothing_period :]) / self.smoothing_period
                )
            return roc

        # EMA smoothing
        multiplier = 2 / (self.smoothing_period + 1)
        self.smoothed_roc[symbol] = (
            roc - self.smoothed_roc[symbol]
        ) * multiplier + self.smoothed_roc[symbol]
        return self.smoothed_roc[symbol]

    def on_market_data(
        self, tick: MarketDataPoint, portfolio: TradingPortfolio
    ) -> list[Order]:
        symbol = tick.symbol
        price = tick.price

        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=self.lookback_period + 10)

        self.price_history[symbol].append(price)
        prices = list(self.price_history[symbol])

        roc = self._calculate_roc(prices)
        if roc is None:
            return []

        # Optionally smooth the ROC
        if self.use_smoothing:
            roc = self._smooth_roc(symbol, roc)

        position = portfolio.get_position(symbol)
        current_qty = position.quantity if position else 0

        orders = []

        # Long entry: strong positive momentum
        if current_qty == 0 and roc > self.entry_threshold:
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
                    f"ROC LONG {symbol}: ROC={roc:.2f}% > {self.entry_threshold}%"
                )

        # Long exit: momentum fading
        elif current_qty > 0 and roc < self.exit_threshold:
            orders.append(
                Order(
                    symbol=symbol,
                    side=OrderSide.SELL,
                    order_type=OrderType.MARKET,
                    quantity=current_qty,
                )
            )
            logger.info(
                f"ROC EXIT LONG {symbol}: ROC={roc:.2f}% < {self.exit_threshold}%"
            )

        # Short entry: strong negative momentum
        elif self.enable_shorting and current_qty == 0 and roc < -self.entry_threshold:
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
                    f"ROC SHORT {symbol}: ROC={roc:.2f}% < -{self.entry_threshold}%"
                )

        # Short exit: momentum turning positive
        elif current_qty < 0 and roc > -self.exit_threshold:
            orders.append(
                Order(
                    symbol=symbol,
                    side=OrderSide.BUY,
                    order_type=OrderType.MARKET,
                    quantity=abs(current_qty),
                )
            )
            logger.info(
                f"ROC COVER SHORT {symbol}: ROC={roc:.2f}% > -{self.exit_threshold}%"
            )

        return orders
