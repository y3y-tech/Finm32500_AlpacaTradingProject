"""
Multi-Indicator Mean Reversion Strategy.

Combines RSI, Bollinger Bands, and price distance from MA to create
a composite oversold/overbought score. More robust than single indicators.

Best for: Range-bound markets, catching reversals
Works well with: Sector rotation, stable equities
"""

from collections import deque
import logging
import math

from AlpacaTrading.models import MarketDataPoint, Order, OrderSide, OrderType
from AlpacaTrading.trading.portfolio import TradingPortfolio
from .base import TradingStrategy

logger = logging.getLogger(__name__)


class MultiIndicatorReversionStrategy(TradingStrategy):
    """
    Multi-indicator mean reversion strategy.

    Combines multiple signals into a composite score:
    1. RSI extremes
    2. Bollinger Band position
    3. Distance from moving average

    Each indicator contributes to an "extreme score" from -100 to +100.
    Trade when composite score exceeds threshold.

    Parameters:
        lookback_period: Period for calculations (default: 20)
        rsi_period: Period for RSI (default: 14)
        entry_score: Composite score to enter (default: 60)
        exit_score: Composite score to exit (default: 0)
        position_size: Dollar amount per trade
        max_position: Maximum shares per symbol
        indicator_weights: Dict of weights for each indicator
    """

    def __init__(
        self,
        lookback_period: int = 20,
        rsi_period: int = 14,
        entry_score: float = 60,
        exit_score: float = 0,
        position_size: float = 10000,
        max_position: int = 100,
        indicator_weights: dict[str, float] | None = None,
    ):
        super().__init__("MultiIndicatorReversion")

        self.lookback_period = lookback_period
        self.rsi_period = rsi_period
        self.entry_score = entry_score
        self.exit_score = exit_score
        self.position_size = position_size
        self.max_position = max_position

        # Default equal weights
        self.weights = indicator_weights or {
            "rsi": 0.4,
            "bollinger": 0.35,
            "ma_distance": 0.25,
        }

        # Normalize weights
        total_weight = sum(self.weights.values())
        self.weights = {k: v / total_weight for k, v in self.weights.items()}

        # History per symbol
        self.price_history: dict[str, deque] = {}
        self.gain_history: dict[str, deque] = {}
        self.loss_history: dict[str, deque] = {}
        self.prev_price: dict[str, float | None] = {}

    def _calculate_rsi(self, symbol: str, price: float) -> float | None:
        """Calculate RSI and return score from -100 (oversold) to +100 (overbought)."""
        prev = self.prev_price.get(symbol)
        if prev is None:
            return None

        change = price - prev

        if symbol not in self.gain_history:
            self.gain_history[symbol] = deque(maxlen=self.rsi_period)
            self.loss_history[symbol] = deque(maxlen=self.rsi_period)

        if change >= 0:
            self.gain_history[symbol].append(change)
            self.loss_history[symbol].append(0)
        else:
            self.gain_history[symbol].append(0)
            self.loss_history[symbol].append(abs(change))

        if len(self.gain_history[symbol]) < self.rsi_period:
            return None

        avg_gain = sum(self.gain_history[symbol]) / self.rsi_period
        avg_loss = sum(self.loss_history[symbol]) / self.rsi_period

        if avg_loss == 0:
            rsi = 100
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

        # Convert RSI to score: RSI 30 -> -100, RSI 50 -> 0, RSI 70 -> +100
        if rsi <= 30:
            return -100
        elif rsi >= 70:
            return 100
        elif rsi < 50:
            return (rsi - 50) * 5  # -100 to 0
        else:
            return (rsi - 50) * 5  # 0 to +100

    def _calculate_bollinger_score(
        self, prices: list[float], current: float
    ) -> float | None:
        """Calculate position within Bollinger Bands as score."""
        if len(prices) < self.lookback_period:
            return None

        recent = prices[-self.lookback_period :]
        mean = sum(recent) / len(recent)
        variance = sum((p - mean) ** 2 for p in recent) / len(recent)
        std = math.sqrt(variance)

        if std == 0:
            return 0

        # How many std devs from mean
        z_score = (current - mean) / std

        # Clamp to -2 to +2 std devs and convert to -100 to +100
        z_score = max(-2, min(2, z_score))
        return z_score * 50  # -100 to +100

    def _calculate_ma_distance_score(
        self, prices: list[float], current: float
    ) -> float | None:
        """Calculate distance from MA as score."""
        if len(prices) < self.lookback_period:
            return None

        ma = sum(prices[-self.lookback_period :]) / self.lookback_period

        if ma == 0:
            return 0

        # Percentage distance from MA
        pct_distance = ((current - ma) / ma) * 100

        # Clamp to -5% to +5% and convert to -100 to +100
        pct_distance = max(-5, min(5, pct_distance))
        return pct_distance * 20  # -100 to +100

    def on_market_data(
        self, tick: MarketDataPoint, portfolio: TradingPortfolio
    ) -> list[Order]:
        symbol = tick.symbol
        price = tick.price

        if symbol not in self.price_history:
            self.price_history[symbol] = deque(
                maxlen=max(self.lookback_period, self.rsi_period) + 5
            )

        self.price_history[symbol].append(price)
        prices = list(self.price_history[symbol])

        # Calculate individual scores
        rsi_score = self._calculate_rsi(symbol, price)
        self.prev_price[symbol] = price

        bb_score = self._calculate_bollinger_score(prices, price)
        ma_score = self._calculate_ma_distance_score(prices, price)

        if rsi_score is None or bb_score is None or ma_score is None:
            return []

        # Calculate composite score
        composite_score = (
            rsi_score * self.weights["rsi"]
            + bb_score * self.weights["bollinger"]
            + ma_score * self.weights["ma_distance"]
        )

        position = portfolio.get_position(symbol)
        current_qty = position.quantity if position else 0

        orders = []

        # Oversold - buy signal (negative score = oversold)
        if current_qty == 0 and composite_score < -self.entry_score:
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
                    f"MULTI-IND BUY {symbol}: score={composite_score:.1f} "
                    f"(RSI={rsi_score:.0f}, BB={bb_score:.0f}, MA={ma_score:.0f})"
                )

        # Reversion complete - exit
        elif current_qty > 0 and composite_score >= self.exit_score:
            orders.append(
                Order(
                    symbol=symbol,
                    side=OrderSide.SELL,
                    order_type=OrderType.MARKET,
                    quantity=current_qty,
                )
            )
            logger.info(
                f"MULTI-IND EXIT {symbol}: score={composite_score:.1f} >= {self.exit_score}"
            )

        # Overbought - could add short logic here if desired

        return orders

    def generate_signal(self, df):
        """
        Generate trading signal from DataFrame (for multi-trader coordinator).

        Args:
            df: DataFrame with 'close' column and datetime index

        Returns:
            1 for buy signal, -1 for sell signal, 0 for no action
        """
        min_required = max(self.lookback_period, self.rsi_period) + 1
        if len(df) < min_required:
            return 0

        prices = df['close'].values

        # Calculate RSI score
        changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [max(change, 0) for change in changes[-self.rsi_period:]]
        losses = [abs(min(change, 0)) for change in changes[-self.rsi_period:]]

        avg_gain = sum(gains) / self.rsi_period
        avg_loss = sum(losses) / self.rsi_period

        if avg_loss == 0:
            rsi = 100 if avg_gain > 0 else 50
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

        # Convert RSI to score
        if rsi <= 30:
            rsi_score = -100
        elif rsi >= 70:
            rsi_score = 100
        elif rsi < 50:
            rsi_score = (rsi - 50) * 5
        else:
            rsi_score = (rsi - 50) * 5

        # Calculate Bollinger Band score
        recent_prices = prices[-self.lookback_period:]
        mean = sum(recent_prices) / len(recent_prices)
        variance = sum((p - mean) ** 2 for p in recent_prices) / len(recent_prices)
        std = math.sqrt(variance)

        if std == 0:
            bb_score = 0
        else:
            z_score = (prices[-1] - mean) / std
            z_score = max(-2, min(2, z_score))
            bb_score = z_score * 50

        # Calculate MA distance score
        ma = sum(prices[-self.lookback_period:]) / self.lookback_period
        if ma == 0:
            ma_score = 0
        else:
            pct_distance = ((prices[-1] - ma) / ma) * 100
            pct_distance = max(-5, min(5, pct_distance))
            ma_score = pct_distance * 20

        # Calculate composite score
        composite_score = (
            rsi_score * self.weights["rsi"]
            + bb_score * self.weights["bollinger"]
            + ma_score * self.weights["ma_distance"]
        )

        # Generate signal
        if composite_score < -self.entry_score:
            return 1  # Oversold - buy signal
        elif composite_score >= self.exit_score:
            return -1  # Reversion complete - sell signal
        else:
            return 0  # No action

    def __repr__(self) -> str:
        return (
            f"MultiIndicatorReversionStrategy(lookback={self.lookback_period}, "
            f"entry_score={self.entry_score})"
        )
