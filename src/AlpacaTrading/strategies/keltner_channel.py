"""
Keltner Channel Strategy - ATR-based volatility bands for trend trading.

Similar to Bollinger Bands but uses ATR instead of standard deviation,
making it smoother and less reactive to price spikes.

Best for: Trending markets, breakout confirmation
Works well with: Energy, EM, commodities (trending assets)
"""

from collections import deque
import logging
from typing import Literal

from AlpacaTrading.models import MarketDataPoint, Order, OrderSide, OrderType
from AlpacaTrading.trading.portfolio import TradingPortfolio
from .base import TradingStrategy

logger = logging.getLogger(__name__)


class KeltnerChannelStrategy(TradingStrategy):
    """
    Keltner Channel strategy using EMA and ATR.

    Channels:
    - Middle: EMA of price
    - Upper: EMA + (multiplier * ATR)
    - Lower: EMA - (multiplier * ATR)

    Modes:
    - breakout: Buy on upper band break, sell on middle cross
    - reversion: Buy at lower band, sell at upper band
    - squeeze: Trade when Keltner inside Bollinger (volatility expansion)

    Parameters:
        ema_period: Period for EMA calculation (default: 20)
        atr_period: Period for ATR calculation (default: 10)
        atr_multiplier: Band width in ATRs (default: 2.0)
        mode: 'breakout', 'reversion', or 'squeeze'
        position_size: Dollar amount per trade
        max_position: Maximum shares per symbol
    """

    def __init__(
        self,
        ema_period: int = 20,
        atr_period: int = 10,
        atr_multiplier: float = 2.0,
        mode: Literal["breakout", "reversion", "squeeze"] = "breakout",
        position_size: float = 10000,
        max_position: int = 100,
    ):
        super().__init__("KeltnerChannel")

        if ema_period <= 0:
            raise ValueError(f"ema_period must be positive, got {ema_period}")
        if atr_period <= 0:
            raise ValueError(f"atr_period must be positive, got {atr_period}")
        if atr_multiplier <= 0:
            raise ValueError(f"atr_multiplier must be positive, got {atr_multiplier}")

        self.ema_period = ema_period
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
        self.mode = mode
        self.position_size = position_size
        self.max_position = max_position

        # History per symbol
        self.price_history: dict[str, deque] = {}
        self.ema: dict[str, float | None] = {}
        self.atr: dict[str, float | None] = {}
        self.prev_price: dict[str, float | None] = {}

    def _update_ema(self, symbol: str, price: float) -> float | None:
        """Update EMA with new price."""
        if symbol not in self.ema or self.ema[symbol] is None:
            # Initialize with SMA
            prices = list(self.price_history[symbol])
            if len(prices) >= self.ema_period:
                self.ema[symbol] = sum(prices[-self.ema_period :]) / self.ema_period
            return self.ema.get(symbol)

        # EMA formula
        multiplier = 2 / (self.ema_period + 1)
        self.ema[symbol] = (price - self.ema[symbol]) * multiplier + self.ema[symbol]
        return self.ema[symbol]

    def _update_atr(self, symbol: str, price: float) -> float | None:
        """Update ATR (simplified - using price changes as proxy for true range)."""
        prev = self.prev_price.get(symbol)
        if prev is None:
            self.prev_price[symbol] = price
            return None

        # True range approximation (would need high/low for full calculation)
        tr = abs(price - prev)
        self.prev_price[symbol] = price

        if symbol not in self.atr or self.atr[symbol] is None:
            # Need enough data
            prices = list(self.price_history[symbol])
            if len(prices) >= self.atr_period:
                # Initialize ATR as average of recent ranges
                ranges = [
                    abs(prices[i] - prices[i - 1])
                    for i in range(1, min(len(prices), self.atr_period + 1))
                ]
                if ranges:
                    self.atr[symbol] = sum(ranges) / len(ranges)
            return self.atr.get(symbol)

        # Smoothed ATR
        self.atr[symbol] = (
            self.atr[symbol] * (self.atr_period - 1) + tr
        ) / self.atr_period
        return self.atr[symbol]

    def on_market_data(
        self, tick: MarketDataPoint, portfolio: TradingPortfolio
    ) -> list[Order]:
        symbol = tick.symbol
        price = tick.price

        # Initialize
        if symbol not in self.price_history:
            self.price_history[symbol] = deque(
                maxlen=max(self.ema_period, self.atr_period) + 5
            )

        self.price_history[symbol].append(price)

        # Update indicators
        ema = self._update_ema(symbol, price)
        atr = self._update_atr(symbol, price)

        if ema is None or atr is None or atr == 0:
            return []

        # Calculate channels
        upper_band = ema + (self.atr_multiplier * atr)
        lower_band = ema - (self.atr_multiplier * atr)

        position = portfolio.get_position(symbol)
        current_qty = position.quantity if position else 0

        orders = []

        if self.mode == "breakout":
            # Buy on upper band breakout
            if current_qty == 0 and price > upper_band:
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
                        f"KELTNER BREAKOUT BUY {symbol}: {price:.2f} > upper {upper_band:.2f}"
                    )

            # Exit on middle line cross down
            elif current_qty > 0 and price < ema:
                orders.append(
                    Order(
                        symbol=symbol,
                        side=OrderSide.SELL,
                        order_type=OrderType.MARKET,
                        quantity=current_qty,
                    )
                )
                logger.info(f"KELTNER EXIT {symbol}: {price:.2f} < EMA {ema:.2f}")

        elif self.mode == "reversion":
            # Buy at lower band
            if current_qty == 0 and price <= lower_band:
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
                        f"KELTNER REVERSION BUY {symbol}: {price:.2f} <= lower {lower_band:.2f}"
                    )

            # Sell at upper band
            elif current_qty > 0 and price >= upper_band:
                orders.append(
                    Order(
                        symbol=symbol,
                        side=OrderSide.SELL,
                        order_type=OrderType.MARKET,
                        quantity=current_qty,
                    )
                )
                logger.info(
                    f"KELTNER REVERSION SELL {symbol}: {price:.2f} >= upper {upper_band:.2f}"
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
        min_required = max(self.ema_period, self.atr_period)
        if len(df) < min_required:
            return 0

        prices = df['close'].values

        # Calculate EMA
        if len(prices) >= self.ema_period:
            ema = sum(prices[-self.ema_period:]) / self.ema_period
            # Approximate EMA with recent smoothing
            multiplier = 2 / (self.ema_period + 1)
            for price in prices[-self.ema_period:]:
                ema = (price - ema) * multiplier + ema
        else:
            return 0

        # Calculate ATR (simplified using price changes)
        if len(prices) >= self.atr_period + 1:
            ranges = [abs(prices[i] - prices[i-1]) for i in range(-self.atr_period, 0)]
            atr = sum(ranges) / len(ranges)
        else:
            return 0

        if atr == 0:
            return 0

        # Calculate channels
        upper_band = ema + (self.atr_multiplier * atr)
        lower_band = ema - (self.atr_multiplier * atr)

        current_price = prices[-1]

        if self.mode == "breakout":
            # Buy on upper band breakout
            if current_price > upper_band:
                return 1
            # Exit on middle line cross down
            elif current_price < ema:
                return -1
            else:
                return 0

        elif self.mode == "reversion":
            # Buy at lower band
            if current_price <= lower_band:
                return 1
            # Sell at upper band
            elif current_price >= upper_band:
                return -1
            else:
                return 0

        return 0

    def __repr__(self) -> str:
        return (
            f"KeltnerChannelStrategy(ema={self.ema_period}, "
            f"atr={self.atr_period}, mode={self.mode})"
        )
