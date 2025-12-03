"""
Bollinger Bands Strategy - Trade breakouts and reversions from volatility bands.

Two modes:
1. Breakout mode: Buy when price breaks above upper band (momentum)
2. Mean reversion mode: Buy when price touches lower band (oversold)

This strategy adapts to market volatility and works well in trending markets (breakout)
or ranging markets (mean reversion).
"""

from collections import deque
import logging
import math
from typing import Literal

from AlpacaTrading.models import MarketDataPoint, Order, OrderSide, OrderType
from AlpacaTrading.trading.portfolio import TradingPortfolio
from .base import TradingStrategy

logger = logging.getLogger(__name__)


class BollingerBandsStrategy(TradingStrategy):
    """
    Bollinger Bands trading strategy with breakout and mean reversion modes.

    Bollinger Bands = SMA ± (std_dev * num_std_dev)

    Breakout Mode:
    - Buy when price breaks above upper band (strong momentum)
    - Sell when price falls back below middle band (SMA)

    Mean Reversion Mode:
    - Buy when price touches/crosses lower band (oversold)
    - Sell when price reaches middle band or upper band

    Parameters:
        period: Lookback period for SMA and std dev (default: 20)
        num_std_dev: Number of standard deviations for bands (default: 2.0)
        mode: 'breakout' or 'reversion' (default: 'breakout')
        position_size: Target position size in dollars (default: 10000)
        max_position: Maximum position per symbol (default: 100 shares)
        band_threshold: Price must be this far beyond band to trigger (default: 0.001 = 0.1%)
    """

    def __init__(
        self,
        period: int = 20,
        num_std_dev: float = 2.0,
        mode: Literal["breakout", "reversion"] = "breakout",
        position_size: float = 10000,
        max_position: int = 100,
        band_threshold: float = 0.001,
    ):
        super().__init__(f"BollingerBands_{mode.capitalize()}")

        # Parameter validation
        if period <= 1:
            raise ValueError(f"period must be > 1, got {period}")
        if num_std_dev <= 0:
            raise ValueError(f"num_std_dev must be positive, got {num_std_dev}")
        if mode not in ["breakout", "reversion"]:
            raise ValueError(f"mode must be 'breakout' or 'reversion', got {mode}")
        if position_size <= 0:
            raise ValueError(f"position_size must be positive, got {position_size}")
        if max_position <= 0:
            raise ValueError(f"max_position must be positive, got {max_position}")
        if band_threshold < 0:
            raise ValueError(
                f"band_threshold must be non-negative, got {band_threshold}"
            )

        self.period = period
        self.num_std_dev = num_std_dev
        self.mode = mode
        self.position_size = position_size
        self.max_position = max_position
        self.band_threshold = band_threshold

        # Track price history per symbol
        self.price_history: dict[str, deque] = {}
        self.upper_band: dict[str, float] = {}
        self.middle_band: dict[str, float] = {}
        self.lower_band: dict[str, float] = {}
        self.prev_price: dict[
            str, float
        ] = {}  # Track previous price for crossover detection

    def _calculate_bands(self, symbol: str) -> tuple[float, float, float] | None:
        """
        Calculate Bollinger Bands.

        Returns:
            Tuple of (upper_band, middle_band, lower_band) or None if not enough data
        """
        prices = list(self.price_history[symbol])
        if len(prices) < self.period:
            return None

        # Calculate SMA (middle band)
        recent_prices = prices[-self.period :]
        sma = sum(recent_prices) / self.period

        # Calculate standard deviation
        variance = sum((p - sma) ** 2 for p in recent_prices) / self.period
        std_dev = math.sqrt(variance)

        # Calculate bands
        upper = sma + (self.num_std_dev * std_dev)
        lower = sma - (self.num_std_dev * std_dev)

        return upper, sma, lower

    def on_market_data(
        self, tick: MarketDataPoint, portfolio: TradingPortfolio
    ) -> list[Order]:
        """
        Generate trading signals based on Bollinger Bands.

        Returns:
            List of orders (buy/sell based on band interactions)
        """
        # Validate tick price
        if tick.price <= 0:
            logger.warning(
                f"Invalid price {tick.price} for {tick.symbol}, skipping tick"
            )
            return []

        # Initialize for new symbol
        if tick.symbol not in self.price_history:
            self.price_history[tick.symbol] = deque(
                maxlen=self.period + 10
            )  # Extra buffer
            logger.info(f"Initialized Bollinger Bands tracking for {tick.symbol}")

        # Track previous price for crossover detection
        prev_price = self.prev_price.get(tick.symbol, tick.price)

        # Update price history
        self.price_history[tick.symbol].append(tick.price)
        self.prev_price[tick.symbol] = tick.price

        # Calculate bands
        bands = self._calculate_bands(tick.symbol)
        if bands is None:
            return []

        upper, middle, lower = bands
        self.upper_band[tick.symbol] = upper
        self.middle_band[tick.symbol] = middle
        self.lower_band[tick.symbol] = lower

        # Get current position
        position = portfolio.get_position(tick.symbol)
        current_qty = position.quantity if position else 0

        orders = []

        # BREAKOUT MODE
        if self.mode == "breakout":
            # Buy when price breaks above upper band (strong upward momentum)
            if prev_price <= upper and tick.price > upper * (1 + self.band_threshold):
                if current_qty < self.max_position:
                    quantity = min(
                        int(self.position_size / tick.price),
                        self.max_position - current_qty,
                    )

                    if quantity > 0:
                        logger.info(
                            f"BUY signal (BREAKOUT) for {tick.symbol}: price={tick.price:.2f}, "
                            f"upper_band={upper:.2f}, middle={middle:.2f}, lower={lower:.2f}"
                        )
                        orders.append(
                            Order(
                                symbol=tick.symbol,
                                side=OrderSide.BUY,
                                order_type=OrderType.MARKET,
                                quantity=quantity,
                            )
                        )

            # Sell when price falls back below middle band (momentum fading)
            elif current_qty > 0 and tick.price < middle:
                logger.info(
                    f"SELL signal (FADE) for {tick.symbol}: price={tick.price:.2f}, "
                    f"middle_band={middle:.2f}"
                )
                orders.append(
                    Order(
                        symbol=tick.symbol,
                        side=OrderSide.SELL,
                        order_type=OrderType.MARKET,
                        quantity=current_qty,
                    )
                )

        # MEAN REVERSION MODE
        elif self.mode == "reversion":
            # Buy when price touches lower band (oversold, expect bounce)
            if tick.price <= lower * (1 + self.band_threshold):
                if current_qty < self.max_position:
                    quantity = min(
                        int(self.position_size / tick.price),
                        self.max_position - current_qty,
                    )

                    if quantity > 0:
                        logger.info(
                            f"BUY signal (OVERSOLD) for {tick.symbol}: price={tick.price:.2f}, "
                            f"lower_band={lower:.2f}, middle={middle:.2f}, upper={upper:.2f}"
                        )
                        orders.append(
                            Order(
                                symbol=tick.symbol,
                                side=OrderSide.BUY,
                                order_type=OrderType.MARKET,
                                quantity=quantity,
                            )
                        )

            # Sell when price reaches middle band (mean reversion complete)
            # or upper band (overbought)
            elif current_qty > 0 and tick.price >= middle:
                logger.info(
                    f"SELL signal (REVERSION) for {tick.symbol}: price={tick.price:.2f}, "
                    f"middle_band={middle:.2f}"
                )
                orders.append(
                    Order(
                        symbol=tick.symbol,
                        side=OrderSide.SELL,
                        order_type=OrderType.MARKET,
                        quantity=current_qty,
                    )
                )

        return orders

    def __repr__(self) -> str:
        return (
            f"BollingerBandsStrategy(period={self.period}, "
            f"std_dev={self.num_std_dev}, mode={self.mode})"
        )
