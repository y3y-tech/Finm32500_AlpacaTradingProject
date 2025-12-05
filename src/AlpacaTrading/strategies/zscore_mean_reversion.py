"""
Z-Score Mean Reversion Strategy - Statistical approach to mean reversion.

Uses z-score (standard deviations from mean) to identify extreme deviations
and trade the reversion. More statistically rigorous than simple band strategies.

Best for: Pairs trading, spread trading, range-bound assets
Works well with: Treasury curve, credit spreads, correlated assets
"""

from collections import deque
import logging
import math

from AlpacaTrading.models import MarketDataPoint, Order, OrderSide, OrderType
from AlpacaTrading.trading.portfolio import TradingPortfolio
from .base import TradingStrategy

logger = logging.getLogger(__name__)


class ZScoreMeanReversionStrategy(TradingStrategy):
    """
    Z-Score based mean reversion strategy.

    Logic:
    1. Calculate rolling mean and standard deviation
    2. Compute z-score: (price - mean) / std
    3. Buy when z-score < -entry_threshold (oversold)
    4. Sell when z-score > exit_threshold or z-score > entry_threshold (overbought)

    The z-score approach is more robust than fixed bands because it
    adapts to changing volatility regimes.

    Parameters:
        lookback_period: Period for mean/std calculation (default: 20)
        entry_threshold: Z-score to enter (default: 2.0 = 2 std devs)
        exit_threshold: Z-score to exit (default: 0.0 = at mean)
        position_size: Dollar amount per trade
        max_position: Maximum shares per symbol
        enable_shorting: Allow short positions (default: True)
    """

    def __init__(
        self,
        lookback_period: int = 20,
        entry_threshold: float = 2.0,
        exit_threshold: float = 0.0,
        position_size: float = 10000,
        max_position: int = 100,
        enable_shorting: bool = True,
    ):
        super().__init__("ZScoreMeanReversion")

        if lookback_period <= 1:
            raise ValueError(f"lookback_period must be > 1, got {lookback_period}")
        if entry_threshold <= 0:
            raise ValueError(f"entry_threshold must be positive, got {entry_threshold}")

        self.lookback_period = lookback_period
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.position_size = position_size
        self.max_position = max_position
        self.enable_shorting = enable_shorting

        self.price_history: dict[str, deque] = {}

    def _calculate_zscore(
        self, prices: list[float], current_price: float
    ) -> float | None:
        """Calculate z-score of current price relative to history."""
        if len(prices) < self.lookback_period:
            return None

        recent = prices[-self.lookback_period :]
        mean = sum(recent) / len(recent)

        # Calculate standard deviation
        variance = sum((p - mean) ** 2 for p in recent) / len(recent)
        std = math.sqrt(variance)

        if std == 0:
            return None

        return (current_price - mean) / std

    def on_market_data(
        self, tick: MarketDataPoint, portfolio: TradingPortfolio
    ) -> list[Order]:
        symbol = tick.symbol
        price = tick.price

        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=self.lookback_period + 5)

        self.price_history[symbol].append(price)
        prices = list(self.price_history[symbol])

        zscore = self._calculate_zscore(prices, price)
        if zscore is None:
            return []

        position = portfolio.get_position(symbol)
        current_qty = position.quantity if position else 0

        orders = []

        # Long entry: z-score very negative (oversold)
        if current_qty == 0 and zscore < -self.entry_threshold:
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
                    f"ZSCORE LONG {symbol}: z={zscore:.2f} < -{self.entry_threshold}"
                )

        # Long exit: z-score reverts to exit threshold or goes positive
        elif current_qty > 0 and zscore >= self.exit_threshold:
            orders.append(
                Order(
                    symbol=symbol,
                    side=OrderSide.SELL,
                    order_type=OrderType.MARKET,
                    quantity=current_qty,
                )
            )
            logger.info(
                f"ZSCORE EXIT LONG {symbol}: z={zscore:.2f} >= {self.exit_threshold}"
            )

        # Short entry: z-score very positive (overbought)
        elif (
            self.enable_shorting and current_qty == 0 and zscore > self.entry_threshold
        ):
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
                    f"ZSCORE SHORT {symbol}: z={zscore:.2f} > {self.entry_threshold}"
                )

        # Short exit: z-score reverts toward zero
        elif current_qty < 0 and zscore <= self.exit_threshold:
            orders.append(
                Order(
                    symbol=symbol,
                    side=OrderSide.BUY,
                    order_type=OrderType.MARKET,
                    quantity=abs(current_qty),
                )
            )
            logger.info(
                f"ZSCORE COVER SHORT {symbol}: z={zscore:.2f} <= {self.exit_threshold}"
            )

        return orders

    def generate_signal(self, df):
        """
        Generate trading signal from DataFrame (for multi-trader coordinator).

        Args:
            df: DataFrame with 'close' column and datetime index

        Returns:
            1 for buy signal, -1 for sell signal, 0 for no action
        """
        if len(df) < self.lookback_period:
            return 0

        prices = df['close'].values
        current_price = prices[-1]

        # Calculate z-score
        recent_prices = prices[-self.lookback_period:]
        mean = sum(recent_prices) / len(recent_prices)

        # Calculate standard deviation
        variance = sum((p - mean) ** 2 for p in recent_prices) / len(recent_prices)
        std = math.sqrt(variance)

        if std == 0:
            return 0

        zscore = (current_price - mean) / std

        # Generate signal
        if zscore < -self.entry_threshold:
            return 1  # Long entry: oversold
        elif zscore > self.entry_threshold:
            return -1  # Short entry: overbought (or long exit)
        elif abs(zscore) <= abs(self.exit_threshold):
            return -1  # Exit: reverted to mean
        else:
            return 0  # No action

    def __repr__(self) -> str:
        return (
            f"ZScoreMeanReversionStrategy(lookback={self.lookback_period}, "
            f"entry_threshold={self.entry_threshold})"
        )
