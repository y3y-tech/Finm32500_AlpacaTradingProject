"""
RSI Mean Reversion Strategy - Trade oversold/overbought conditions.

Buys when RSI drops below oversold threshold (e.g., 30) indicating oversold conditions.
Sells when RSI rises above overbought threshold (e.g., 70) or position is held.

This strategy works well in ranging markets and for mean reversion trades.
Suitable for short-term trading (intraday to multi-day holds).
"""

from collections import deque
import logging

from AlpacaTrading.models import MarketDataPoint, Order, OrderSide, OrderType
from AlpacaTrading.trading.portfolio import TradingPortfolio
from .base import TradingStrategy

logger = logging.getLogger(__name__)


class RSIStrategy(TradingStrategy):
    """
    RSI (Relative Strength Index) mean reversion strategy.

    Logic:
    1. Calculate RSI over lookback period (default 14)
    2. Buy when RSI < oversold threshold (default 30) - oversold bounce
    3. Sell when RSI > overbought threshold (default 70) or holding position
    4. Optional: Use profit target and stop loss

    Parameters:
        rsi_period: Period for RSI calculation (default: 14)
        oversold_threshold: RSI level to trigger buy (default: 30)
        overbought_threshold: RSI level to trigger sell (default: 70)
        position_size: Target position size in dollars (default: 10000)
        max_position: Maximum position per symbol (default: 100 shares)
        profit_target: Optional profit target as percentage (default: None)
        stop_loss: Optional stop loss as percentage (default: None)
    """

    def __init__(
        self,
        rsi_period: int = 14,
        oversold_threshold: float = 30,
        overbought_threshold: float = 70,
        position_size: float = 10000,
        max_position: int = 100,
        profit_target: float | None = None,
        stop_loss: float | None = None,
    ):
        super().__init__("RSI_MeanReversion")

        # Parameter validation
        if rsi_period <= 1:
            raise ValueError(f"rsi_period must be > 1, got {rsi_period}")
        if not (0 < oversold_threshold < 100):
            raise ValueError(
                f"oversold_threshold must be between 0 and 100, got {oversold_threshold}"
            )
        if not (0 < overbought_threshold < 100):
            raise ValueError(
                f"overbought_threshold must be between 0 and 100, got {overbought_threshold}"
            )
        if oversold_threshold >= overbought_threshold:
            raise ValueError(
                f"oversold_threshold ({oversold_threshold}) must be < overbought_threshold ({overbought_threshold})"
            )
        if position_size <= 0:
            raise ValueError(f"position_size must be positive, got {position_size}")
        if max_position <= 0:
            raise ValueError(f"max_position must be positive, got {max_position}")
        if profit_target is not None and profit_target <= 0:
            raise ValueError(f"profit_target must be positive, got {profit_target}")
        if stop_loss is not None and stop_loss <= 0:
            raise ValueError(f"stop_loss must be positive, got {stop_loss}")

        self.rsi_period = rsi_period
        self.oversold_threshold = oversold_threshold
        self.overbought_threshold = overbought_threshold
        self.position_size = position_size
        self.max_position = max_position
        self.profit_target = profit_target
        self.stop_loss = stop_loss

        # Track price changes for RSI calculation
        self.price_history: dict[str, deque] = {}
        self.rsi_values: dict[str, float] = {}
        self.entry_prices: dict[str, float] = {}  # Track entry price for P&L targets

    def _calculate_rsi(self, symbol: str) -> float | None:
        """
        Calculate RSI using the standard formula.

        RSI = 100 - (100 / (1 + RS))
        where RS = Average Gain / Average Loss over period

        Returns:
            RSI value (0-100) or None if not enough data
        """
        prices = list(self.price_history[symbol])
        if len(prices) < self.rsi_period + 1:
            return None

        # Calculate price changes
        changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]

        # Separate gains and losses
        gains = [max(change, 0) for change in changes[-self.rsi_period :]]
        losses = [abs(min(change, 0)) for change in changes[-self.rsi_period :]]

        # Calculate average gain and loss
        avg_gain = sum(gains) / self.rsi_period
        avg_loss = sum(losses) / self.rsi_period

        # Avoid division by zero
        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0

        # Calculate RS and RSI
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def on_market_data(
        self, tick: MarketDataPoint, portfolio: TradingPortfolio
    ) -> list[Order]:
        """
        Generate trading signals based on RSI levels.

        Returns:
            List of orders (buy on oversold, sell on overbought or profit/stop targets)
        """
        # Validate tick price
        if tick.price <= 0:
            logger.warning(
                f"Invalid price {tick.price} for {tick.symbol}, skipping tick"
            )
            return []

        # Initialize price history for new symbol
        if tick.symbol not in self.price_history:
            # Need rsi_period + 1 prices to calculate first RSI
            self.price_history[tick.symbol] = deque(maxlen=self.rsi_period + 1)
            logger.info(f"Initialized RSI tracking for {tick.symbol}")

        # Update price history
        self.price_history[tick.symbol].append(tick.price)

        # Calculate RSI
        rsi = self._calculate_rsi(tick.symbol)
        if rsi is None:
            return []

        self.rsi_values[tick.symbol] = rsi

        # Get current position
        position = portfolio.get_position(tick.symbol)
        current_qty = position.quantity if position else 0

        orders = []

        # Check profit target and stop loss if holding position
        if current_qty > 0 and tick.symbol in self.entry_prices:
            entry_price = self.entry_prices[tick.symbol]
            pnl_pct = (tick.price - entry_price) / entry_price * 100

            # Profit target hit
            if self.profit_target and pnl_pct >= self.profit_target:
                logger.info(
                    f"PROFIT TARGET HIT for {tick.symbol}: entry={entry_price:.2f}, "
                    f"current={tick.price:.2f}, pnl={pnl_pct:.2f}%, target={self.profit_target:.2f}%"
                )
                orders.append(
                    Order(
                        symbol=tick.symbol,
                        side=OrderSide.SELL,
                        order_type=OrderType.MARKET,
                        quantity=current_qty,
                    )
                )
                del self.entry_prices[tick.symbol]
                return orders

            # Stop loss hit
            if self.stop_loss and pnl_pct <= -self.stop_loss:
                logger.info(
                    f"STOP LOSS HIT for {tick.symbol}: entry={entry_price:.2f}, "
                    f"current={tick.price:.2f}, pnl={pnl_pct:.2f}%, stop={-self.stop_loss:.2f}%"
                )
                orders.append(
                    Order(
                        symbol=tick.symbol,
                        side=OrderSide.SELL,
                        order_type=OrderType.MARKET,
                        quantity=current_qty,
                    )
                )
                del self.entry_prices[tick.symbol]
                return orders

        # RSI Oversold -> BUY
        if rsi < self.oversold_threshold:
            if current_qty < self.max_position:
                # Calculate quantity to buy
                quantity = min(
                    int(self.position_size / tick.price),
                    self.max_position - current_qty,
                )

                if quantity > 0:
                    logger.info(
                        f"BUY signal (OVERSOLD) for {tick.symbol}: RSI={rsi:.2f}, "
                        f"threshold={self.oversold_threshold}, quantity={quantity}"
                    )
                    orders.append(
                        Order(
                            symbol=tick.symbol,
                            side=OrderSide.BUY,
                            order_type=OrderType.MARKET,
                            quantity=quantity,
                        )
                    )
                    # Track entry price
                    self.entry_prices[tick.symbol] = tick.price

        # RSI Overbought -> SELL (or just exit position)
        elif rsi > self.overbought_threshold:
            if current_qty > 0:
                logger.info(
                    f"SELL signal (OVERBOUGHT) for {tick.symbol}: RSI={rsi:.2f}, "
                    f"threshold={self.overbought_threshold}, quantity={current_qty}"
                )
                orders.append(
                    Order(
                        symbol=tick.symbol,
                        side=OrderSide.SELL,
                        order_type=OrderType.MARKET,
                        quantity=current_qty,
                    )
                )
                # Clear entry price
                if tick.symbol in self.entry_prices:
                    del self.entry_prices[tick.symbol]

        return orders

    def generate_signal(self, df):
        """
        Generate trading signal from DataFrame (for multi-trader coordinator).

        Args:
            df: DataFrame with 'close' column and datetime index

        Returns:
            1 for buy signal, -1 for sell signal, 0 for no action
        """
        if len(df) < self.rsi_period + 1:
            return 0

        # Calculate price changes
        prices = df['close'].values
        changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]

        # Separate gains and losses for RSI calculation
        gains = [max(change, 0) for change in changes[-self.rsi_period :]]
        losses = [abs(min(change, 0)) for change in changes[-self.rsi_period :]]

        # Calculate average gain and loss
        avg_gain = sum(gains) / self.rsi_period
        avg_loss = sum(losses) / self.rsi_period

        # Calculate RSI
        if avg_loss == 0:
            rsi = 100.0 if avg_gain > 0 else 50.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

        # Generate signal
        if rsi < self.oversold_threshold:
            return 1  # Buy signal (oversold)
        elif rsi > self.overbought_threshold:
            return -1  # Sell signal (overbought)
        else:
            return 0  # No action

    def __repr__(self) -> str:
        return (
            f"RSIStrategy(period={self.rsi_period}, "
            f"oversold={self.oversold_threshold}, overbought={self.overbought_threshold})"
        )
