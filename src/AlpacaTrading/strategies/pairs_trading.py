"""
Pairs Trading Strategy - Statistical arbitrage on mean-reverting pairs.

Identifies correlated asset pairs and trades temporary divergences.
When the spread widens, short the outperformer and long the underperformer.
When the spread normalizes, close positions for profit.

Classic market-neutral strategy used by hedge funds.
"""

from collections import deque
import logging
import math

from AlpacaTrading.models import MarketDataPoint, Order, OrderSide, OrderType
from AlpacaTrading.trading.portfolio import TradingPortfolio
from .base import TradingStrategy

logger = logging.getLogger(__name__)


class PairsTradingStrategy(TradingStrategy):
    """
    Pairs trading strategy for mean-reverting spreads.

    Logic:
    1. Track price ratio between two symbols (spread)
    2. Calculate mean and standard deviation of spread
    3. Enter when spread > mean + entry_threshold * std_dev (short pair1, long pair2)
       or spread < mean - entry_threshold * std_dev (long pair1, short pair2)
    4. Exit when spread returns to mean ± exit_threshold * std_dev

    Parameters:
        symbol_pair: Tuple of (symbol1, symbol2) to pair trade
        lookback_period: Period for calculating spread statistics (default: 50)
        entry_threshold: Std deviations from mean to enter (default: 2.0)
        exit_threshold: Std deviations from mean to exit (default: 0.5)
        position_size: Position size per leg in dollars (default: 10000)
        max_position: Max shares per symbol (default: 100)
        hedge_ratio: Static hedge ratio (1.0 = equal $, None = calculate dynamically)
    """

    def __init__(
        self,
        symbol_pair: tuple[str, str],
        lookback_period: int = 50,
        entry_threshold: float = 2.0,
        exit_threshold: float = 0.5,
        position_size: float = 10000,
        max_position: int = 100,
        hedge_ratio: float | None = None,
    ):
        super().__init__(f"PairsTrading_{symbol_pair[0]}_{symbol_pair[1]}")

        # Parameter validation
        if len(symbol_pair) != 2:
            raise ValueError(
                f"symbol_pair must have exactly 2 symbols, got {len(symbol_pair)}"
            )
        if symbol_pair[0] == symbol_pair[1]:
            raise ValueError(f"Symbols must be different, got {symbol_pair}")
        if lookback_period <= 5:
            raise ValueError(f"lookback_period must be > 5, got {lookback_period}")
        if entry_threshold <= 0:
            raise ValueError(f"entry_threshold must be positive, got {entry_threshold}")
        if exit_threshold < 0:
            raise ValueError(
                f"exit_threshold must be non-negative, got {exit_threshold}"
            )
        if exit_threshold >= entry_threshold:
            raise ValueError(
                f"exit_threshold ({exit_threshold}) must be < entry_threshold ({entry_threshold})"
            )
        if position_size <= 0:
            raise ValueError(f"position_size must be positive, got {position_size}")
        if max_position <= 0:
            raise ValueError(f"max_position must be positive, got {max_position}")
        if hedge_ratio is not None and hedge_ratio <= 0:
            raise ValueError(f"hedge_ratio must be positive, got {hedge_ratio}")

        self.symbol1, self.symbol2 = symbol_pair
        self.lookback_period = lookback_period
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.position_size = position_size
        self.max_position = max_position
        self.hedge_ratio = hedge_ratio

        # Track prices and spread
        self.prices: dict[str, float] = {}
        self.spread_history: deque = deque(maxlen=lookback_period + 10)
        self.current_spread: float | None = None
        self.spread_mean: float | None = None
        self.spread_std: float | None = None

        # Track position state
        self.in_position = False
        self.entry_spread: float | None = None

    def _calculate_spread(self) -> float | None:
        """
        Calculate current spread (price ratio).

        Returns:
            Current spread or None if prices not available
        """
        if self.symbol1 not in self.prices or self.symbol2 not in self.prices:
            return None

        price1 = self.prices[self.symbol1]
        price2 = self.prices[self.symbol2]

        if price2 == 0:
            return None

        # Spread = ratio of symbol1/symbol2
        return price1 / price2

    def _calculate_spread_stats(self) -> tuple[float, float] | None:
        """
        Calculate mean and standard deviation of spread.

        Returns:
            Tuple of (mean, std_dev) or None if insufficient data
        """
        if len(self.spread_history) < self.lookback_period:
            return None

        spreads = list(self.spread_history)[-self.lookback_period :]

        # Calculate mean
        mean = sum(spreads) / len(spreads)

        # Calculate standard deviation
        variance = sum((s - mean) ** 2 for s in spreads) / len(spreads)
        std_dev = math.sqrt(variance)

        return mean, std_dev

    def _calculate_z_score(self, spread: float, mean: float, std_dev: float) -> float:
        """Calculate z-score of current spread."""
        if std_dev == 0:
            return 0.0
        return (spread - mean) / std_dev

    def on_market_data(
        self, tick: MarketDataPoint, portfolio: TradingPortfolio
    ) -> list[Order]:
        """
        Generate pairs trading signals based on spread divergence.

        Returns:
            List of orders (paired orders for both legs)
        """
        # Validate tick
        if tick.price <= 0:
            logger.warning(
                f"Invalid price {tick.price} for {tick.symbol}, skipping tick"
            )
            return []

        # Update prices
        self.prices[tick.symbol] = tick.price

        # Need both prices
        if self.symbol1 not in self.prices or self.symbol2 not in self.prices:
            return []

        # Calculate spread
        spread = self._calculate_spread()
        if spread is None:
            return []

        self.current_spread = spread
        self.spread_history.append(spread)

        # Calculate spread statistics
        stats = self._calculate_spread_stats()
        if stats is None:
            return []

        mean, std_dev = stats
        self.spread_mean = mean
        self.spread_std = std_dev

        # Calculate z-score
        z_score = self._calculate_z_score(spread, mean, std_dev)

        # Get current positions
        pos1 = portfolio.get_position(self.symbol1)
        pos2 = portfolio.get_position(self.symbol2)
        qty1 = pos1.quantity if pos1 else 0
        qty2 = pos2.quantity if pos2 else 0

        orders = []

        # Check if in position
        self.in_position = qty1 != 0 or qty2 != 0

        # ENTRY LOGIC
        if not self.in_position:
            # Spread too high -> short symbol1, long symbol2
            if z_score > self.entry_threshold:
                # Calculate quantities
                qty1_target = -min(
                    int(self.position_size / self.prices[self.symbol1]),
                    self.max_position,
                )
                qty2_target = min(
                    int(self.position_size / self.prices[self.symbol2]),
                    self.max_position,
                )

                if qty1_target < 0 and qty2_target > 0:
                    logger.info(
                        f"ENTER PAIRS TRADE (spread too high):\n"
                        f"  Z-score: {z_score:.2f} (threshold: {self.entry_threshold})\n"
                        f"  Spread: {spread:.4f} (mean: {mean:.4f}, std: {std_dev:.4f})\n"
                        f"  SHORT {abs(qty1_target)} {self.symbol1} @ ${self.prices[self.symbol1]:.2f}\n"
                        f"  LONG {qty2_target} {self.symbol2} @ ${self.prices[self.symbol2]:.2f}"
                    )

                    orders.extend(
                        [
                            Order(
                                symbol=self.symbol1,
                                side=OrderSide.SELL,
                                order_type=OrderType.MARKET,
                                quantity=abs(qty1_target),
                            ),
                            Order(
                                symbol=self.symbol2,
                                side=OrderSide.BUY,
                                order_type=OrderType.MARKET,
                                quantity=qty2_target,
                            ),
                        ]
                    )
                    self.entry_spread = spread

            # Spread too low -> long symbol1, short symbol2
            elif z_score < -self.entry_threshold:
                qty1_target = min(
                    int(self.position_size / self.prices[self.symbol1]),
                    self.max_position,
                )
                qty2_target = -min(
                    int(self.position_size / self.prices[self.symbol2]),
                    self.max_position,
                )

                if qty1_target > 0 and qty2_target < 0:
                    logger.info(
                        f"ENTER PAIRS TRADE (spread too low):\n"
                        f"  Z-score: {z_score:.2f} (threshold: {-self.entry_threshold})\n"
                        f"  Spread: {spread:.4f} (mean: {mean:.4f}, std: {std_dev:.4f})\n"
                        f"  LONG {qty1_target} {self.symbol1} @ ${self.prices[self.symbol1]:.2f}\n"
                        f"  SHORT {abs(qty2_target)} {self.symbol2} @ ${self.prices[self.symbol2]:.2f}"
                    )

                    orders.extend(
                        [
                            Order(
                                symbol=self.symbol1,
                                side=OrderSide.BUY,
                                order_type=OrderType.MARKET,
                                quantity=qty1_target,
                            ),
                            Order(
                                symbol=self.symbol2,
                                side=OrderSide.SELL,
                                order_type=OrderType.MARKET,
                                quantity=abs(qty2_target),
                            ),
                        ]
                    )
                    self.entry_spread = spread

        # EXIT LOGIC
        else:
            # Check if spread has mean-reverted
            if abs(z_score) <= self.exit_threshold:
                logger.info(
                    f"EXIT PAIRS TRADE (spread normalized):\n"
                    f"  Z-score: {z_score:.2f} (threshold: ±{self.exit_threshold})\n"
                    f"  Spread: {spread:.4f} (mean: {mean:.4f})\n"
                    f"  Entry spread: {self.entry_spread:.4f}\n"
                    f"  Closing all positions"
                )

                # Close both positions
                if qty1 > 0:
                    orders.append(
                        Order(
                            symbol=self.symbol1,
                            side=OrderSide.SELL,
                            order_type=OrderType.MARKET,
                            quantity=qty1,
                        )
                    )
                elif qty1 < 0:
                    orders.append(
                        Order(
                            symbol=self.symbol1,
                            side=OrderSide.BUY,
                            order_type=OrderType.MARKET,
                            quantity=abs(qty1),
                        )
                    )

                if qty2 > 0:
                    orders.append(
                        Order(
                            symbol=self.symbol2,
                            side=OrderSide.SELL,
                            order_type=OrderType.MARKET,
                            quantity=qty2,
                        )
                    )
                elif qty2 < 0:
                    orders.append(
                        Order(
                            symbol=self.symbol2,
                            side=OrderSide.BUY,
                            order_type=OrderType.MARKET,
                            quantity=abs(qty2),
                        )
                    )

                self.entry_spread = None

        return orders

    def on_start(self, portfolio: TradingPortfolio) -> None:
        """Log strategy start."""
        super().on_start(portfolio)
        logger.info(
            f"Pairs Trading Strategy initialized:\n"
            f"  Pair: {self.symbol1} / {self.symbol2}\n"
            f"  Entry threshold: {self.entry_threshold} std dev\n"
            f"  Exit threshold: {self.exit_threshold} std dev\n"
            f"  Lookback: {self.lookback_period} ticks"
        )

    def __repr__(self) -> str:
        return (
            f"PairsTradingStrategy({self.symbol1}/{self.symbol2}, "
            f"entry={self.entry_threshold}σ, exit={self.exit_threshold}σ)"
        )
