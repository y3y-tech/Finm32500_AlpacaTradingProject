"""
Cross-Sectional Momentum Strategy - Rank stocks and trade top/bottom performers.

Unlike time-series strategies that look at each stock independently, this strategy:
1. Ranks all stocks based on recent performance
2. Longs the top N percentile (best performers)
3. Shorts the bottom M percentile (worst performers) - if shorting enabled
4. Rebalances periodically based on new rankings

This is a classic statistical arbitrage / relative value strategy.
Excellent for trading competitions with multiple symbols.
"""

from collections import deque
import logging
from typing import Dict

from AlpacaTrading.models import MarketDataPoint, Order, OrderSide, OrderType
from AlpacaTrading.trading.portfolio import TradingPortfolio
from .base import TradingStrategy

logger = logging.getLogger(__name__)


class CrossSectionalMomentumStrategy(TradingStrategy):
    """
    Cross-sectional momentum strategy that trades relative performance.

    Logic:
    1. Track momentum for all symbols in universe
    2. Rank symbols by momentum periodically (every rebalance_period ticks)
    3. Long top long_percentile % of stocks
    4. Short bottom short_percentile % of stocks (if enabled)
    5. Close positions that fall out of top/bottom rankings

    This strategy requires multiple symbols to be effective.

    Parameters:
        lookback_period: Period for calculating momentum (default: 20)
        rebalance_period: Ticks between rebalancing (default: 50)
        long_percentile: Top % of stocks to long (default: 0.2 = top 20%)
        short_percentile: Bottom % of stocks to short (default: 0.2 = bottom 20%)
        enable_shorting: Allow short positions (default: False for long-only)
        position_size: Position size per stock in dollars (default: 10000)
        max_position_per_stock: Max shares per stock (default: 100)
        min_stocks: Minimum stocks with data before trading (default: 3)
    """

    def __init__(
        self,
        lookback_period: int = 20,
        rebalance_period: int = 50,
        long_percentile: float = 0.2,
        short_percentile: float = 0.2,
        enable_shorting: bool = False,
        position_size: float = 10000,
        max_position_per_stock: int = 100,
        min_stocks: int = 3
    ):
        super().__init__("CrossSectionalMomentum")

        # Parameter validation
        if lookback_period <= 1:
            raise ValueError(f"lookback_period must be > 1, got {lookback_period}")
        if rebalance_period <= 0:
            raise ValueError(f"rebalance_period must be positive, got {rebalance_period}")
        if not (0 < long_percentile <= 1.0):
            raise ValueError(f"long_percentile must be between 0 and 1, got {long_percentile}")
        if not (0 < short_percentile <= 1.0):
            raise ValueError(f"short_percentile must be between 0 and 1, got {short_percentile}")
        if position_size <= 0:
            raise ValueError(f"position_size must be positive, got {position_size}")
        if max_position_per_stock <= 0:
            raise ValueError(f"max_position_per_stock must be positive, got {max_position_per_stock}")
        if min_stocks <= 0:
            raise ValueError(f"min_stocks must be positive, got {min_stocks}")

        self.lookback_period = lookback_period
        self.rebalance_period = rebalance_period
        self.long_percentile = long_percentile
        self.short_percentile = short_percentile
        self.enable_shorting = enable_shorting
        self.position_size = position_size
        self.max_position_per_stock = max_position_per_stock
        self.min_stocks = min_stocks

        # Track price history for all symbols
        self.price_history: Dict[str, deque] = {}
        self.current_prices: Dict[str, float] = {}
        self.momentum_scores: Dict[str, float] = {}

        # Track rebalancing
        self.global_tick_count = 0
        self.last_rebalance_tick = 0

        # Track target positions (what we want to hold)
        self.target_longs: set[str] = set()
        self.target_shorts: set[str] = set()

        # Pending orders to execute (batched per rebalance)
        self.pending_orders: list[Order] = []

    def _calculate_momentum(self, symbol: str) -> float | None:
        """
        Calculate momentum for a symbol.

        Returns:
            Momentum (percentage return over lookback period) or None if insufficient data
        """
        prices = list(self.price_history[symbol])
        if len(prices) < self.lookback_period:
            return None

        first_price = prices[-self.lookback_period]
        last_price = prices[-1]

        if first_price == 0:
            return None

        return (last_price - first_price) / first_price

    def _rank_stocks(self) -> tuple[list[str], list[str]]:
        """
        Rank all stocks by momentum and return top/bottom performers.

        Returns:
            Tuple of (long_list, short_list) - symbols to long and short
        """
        # Calculate momentum for all symbols
        valid_symbols = []
        for symbol in self.price_history.keys():
            momentum = self._calculate_momentum(symbol)
            if momentum is not None:
                self.momentum_scores[symbol] = momentum
                valid_symbols.append(symbol)

        # Need minimum number of stocks
        if len(valid_symbols) < self.min_stocks:
            logger.warning(
                f"Only {len(valid_symbols)} stocks with sufficient data "
                f"(min required: {self.min_stocks})"
            )
            return [], []

        # Sort by momentum (descending)
        sorted_symbols = sorted(valid_symbols, key=lambda s: self.momentum_scores[s], reverse=True)

        # Select top and bottom percentiles
        n_stocks = len(sorted_symbols)
        n_long = max(1, int(n_stocks * self.long_percentile))
        n_short = max(1, int(n_stocks * self.short_percentile)) if self.enable_shorting else 0

        long_list = sorted_symbols[:n_long]
        short_list = sorted_symbols[-n_short:] if n_short > 0 else []

        return long_list, short_list

    def _generate_rebalance_orders(
        self,
        portfolio: TradingPortfolio,
        long_list: list[str],
        short_list: list[str]
    ) -> list[Order]:
        """
        Generate orders to rebalance portfolio to target positions.

        Returns:
            List of orders to execute
        """
        orders = []

        # Update target positions
        self.target_longs = set(long_list)
        self.target_shorts = set(short_list)

        # Process each symbol
        all_symbols = set(self.price_history.keys())

        for symbol in all_symbols:
            current_price = self.current_prices.get(symbol)
            if current_price is None or current_price <= 0:
                continue

            position = portfolio.get_position(symbol)
            current_qty = position.quantity if position else 0

            # Determine target quantity
            if symbol in self.target_longs:
                # Should be long
                target_qty = min(
                    int(self.position_size / current_price),
                    self.max_position_per_stock
                )
            elif symbol in self.target_shorts:
                # Should be short
                target_qty = -min(
                    int(self.position_size / current_price),
                    self.max_position_per_stock
                )
            else:
                # Should be flat
                target_qty = 0

            # Calculate order needed
            qty_diff = target_qty - current_qty

            if qty_diff == 0:
                continue  # No change needed

            # Generate order
            if qty_diff > 0:
                # Need to buy
                orders.append(Order(
                    symbol=symbol,
                    side=OrderSide.BUY,
                    order_type=OrderType.MARKET,
                    quantity=qty_diff
                ))
            else:
                # Need to sell
                orders.append(Order(
                    symbol=symbol,
                    side=OrderSide.SELL,
                    order_type=OrderType.MARKET,
                    quantity=-qty_diff
                ))

        return orders

    def on_market_data(
        self,
        tick: MarketDataPoint,
        portfolio: TradingPortfolio
    ) -> list[Order]:
        """
        Process market data and generate rebalancing orders when needed.

        Returns:
            List of orders (empty unless rebalancing)
        """
        # Validate tick
        if tick.price <= 0:
            logger.warning(f"Invalid price {tick.price} for {tick.symbol}, skipping tick")
            return []

        # Initialize price history for new symbol
        if tick.symbol not in self.price_history:
            self.price_history[tick.symbol] = deque(maxlen=self.lookback_period + 10)
            logger.info(f"Added {tick.symbol} to cross-sectional universe")

        # Update price data
        self.price_history[tick.symbol].append(tick.price)
        self.current_prices[tick.symbol] = tick.price

        # Increment global tick count
        self.global_tick_count += 1

        # Check if it's time to rebalance
        ticks_since_rebalance = self.global_tick_count - self.last_rebalance_tick

        if ticks_since_rebalance < self.rebalance_period:
            return []  # Not time to rebalance yet

        # Time to rebalance!
        logger.info(f"\n{'='*80}")
        logger.info(f"REBALANCING at tick {self.global_tick_count}")
        logger.info(f"{'='*80}")

        # Rank stocks
        long_list, short_list = self._rank_stocks()

        if not long_list and not short_list:
            logger.warning("No stocks to trade (insufficient data)")
            return []

        # Log rankings
        logger.info(f"\nTop performers (LONG):")
        for symbol in long_list:
            momentum = self.momentum_scores.get(symbol, 0)
            logger.info(f"  {symbol}: momentum={momentum*100:.2f}%")

        if short_list:
            logger.info(f"\nBottom performers (SHORT):")
            for symbol in short_list:
                momentum = self.momentum_scores.get(symbol, 0)
                logger.info(f"  {symbol}: momentum={momentum*100:.2f}%")

        # Generate rebalance orders
        orders = self._generate_rebalance_orders(portfolio, long_list, short_list)

        logger.info(f"\nGenerating {len(orders)} rebalance orders")
        for order in orders:
            side_str = "BUY" if order.side == OrderSide.BUY else "SELL"
            logger.info(f"  {side_str} {order.quantity} {order.symbol} @ market")

        # Update last rebalance tick
        self.last_rebalance_tick = self.global_tick_count

        return orders

    def on_start(self, portfolio: TradingPortfolio) -> None:
        """Log strategy start."""
        super().on_start(portfolio)
        logger.info(
            f"Cross-Sectional Momentum configured:\n"
            f"  Lookback: {self.lookback_period} ticks\n"
            f"  Rebalance: every {self.rebalance_period} ticks\n"
            f"  Long: top {self.long_percentile*100:.0f}%\n"
            f"  Short: bottom {self.short_percentile*100:.0f}% "
            f"({'ENABLED' if self.enable_shorting else 'DISABLED'})\n"
            f"  Position size: ${self.position_size:,.0f} per stock"
        )

    def __repr__(self) -> str:
        mode = "long-short" if self.enable_shorting else "long-only"
        return (
            f"CrossSectionalMomentumStrategy({mode}, "
            f"long={self.long_percentile*100:.0f}%, short={self.short_percentile*100:.0f}%)"
        )
