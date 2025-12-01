"""
Relative Strength Cross-Sectional Strategy.

Ranks stocks by relative strength (RSI, price momentum, or combination)
and rotates into the strongest/weakest performers.

Unlike CrossSectionalMomentum which uses simple price returns, this uses
multi-factor ranking combining technical indicators.
"""

from collections import deque
import logging
from typing import Dict
import math

from AlpacaTrading.models import MarketDataPoint, Order, OrderSide, OrderType
from AlpacaTrading.trading.portfolio import TradingPortfolio
from .base import TradingStrategy

logger = logging.getLogger(__name__)


class RelativeStrengthStrategy(TradingStrategy):
    """
    Multi-factor relative strength strategy.

    Combines multiple technical factors to rank stocks:
    1. Price momentum (return over period)
    2. RSI (relative strength index)
    3. Volatility (inverse - prefer stable stocks)

    Logic:
    1. Calculate composite score for each stock
    2. Rank by composite score
    3. Long top N stocks, close/short bottom N stocks
    4. Rebalance periodically

    Parameters:
        momentum_period: Period for momentum calculation (default: 20)
        rsi_period: Period for RSI calculation (default: 14)
        volatility_period: Period for volatility calculation (default: 20)
        rebalance_period: Ticks between rebalances (default: 50)
        top_n: Number of top stocks to hold (default: 3)
        momentum_weight: Weight for momentum in composite score (default: 0.5)
        rsi_weight: Weight for RSI in composite score (default: 0.3)
        volatility_weight: Weight for volatility in composite score (default: 0.2)
        position_size: Position size per stock (default: 10000)
        max_position: Max shares per stock (default: 100)
        min_stocks: Minimum stocks needed (default: 5)
    """

    def __init__(
        self,
        momentum_period: int = 20,
        rsi_period: int = 14,
        volatility_period: int = 20,
        rebalance_period: int = 50,
        top_n: int = 3,
        momentum_weight: float = 0.5,
        rsi_weight: float = 0.3,
        volatility_weight: float = 0.2,
        position_size: float = 10000,
        max_position: int = 100,
        min_stocks: int = 5
    ):
        super().__init__("RelativeStrength")

        # Parameter validation
        if momentum_period <= 1:
            raise ValueError(f"momentum_period must be > 1, got {momentum_period}")
        if rsi_period <= 1:
            raise ValueError(f"rsi_period must be > 1, got {rsi_period}")
        if volatility_period <= 1:
            raise ValueError(f"volatility_period must be > 1, got {volatility_period}")
        if rebalance_period <= 0:
            raise ValueError(f"rebalance_period must be positive, got {rebalance_period}")
        if top_n <= 0:
            raise ValueError(f"top_n must be positive, got {top_n}")

        weights_sum = momentum_weight + rsi_weight + volatility_weight
        if abs(weights_sum - 1.0) > 0.01:
            raise ValueError(f"Weights must sum to 1.0, got {weights_sum}")

        if position_size <= 0:
            raise ValueError(f"position_size must be positive, got {position_size}")
        if max_position <= 0:
            raise ValueError(f"max_position must be positive, got {max_position}")

        self.momentum_period = momentum_period
        self.rsi_period = rsi_period
        self.volatility_period = volatility_period
        self.rebalance_period = rebalance_period
        self.top_n = top_n
        self.momentum_weight = momentum_weight
        self.rsi_weight = rsi_weight
        self.volatility_weight = volatility_weight
        self.position_size = position_size
        self.max_position = max_position
        self.min_stocks = min_stocks

        # Track price history
        self.price_history: Dict[str, deque] = {}
        self.current_prices: Dict[str, float] = {}

        # Track scores
        self.composite_scores: Dict[str, float] = {}

        # Track rebalancing
        self.global_tick_count = 0
        self.last_rebalance_tick = 0

        # Current holdings
        self.target_holdings: set[str] = set()

    def _calculate_momentum(self, symbol: str) -> float | None:
        """Calculate momentum (percentage return)."""
        prices = list(self.price_history[symbol])
        if len(prices) < self.momentum_period:
            return None

        first_price = prices[-self.momentum_period]
        last_price = prices[-1]

        if first_price == 0:
            return None

        return (last_price - first_price) / first_price

    def _calculate_rsi(self, symbol: str) -> float | None:
        """Calculate RSI."""
        prices = list(self.price_history[symbol])
        if len(prices) < self.rsi_period + 1:
            return None

        changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [max(c, 0) for c in changes[-self.rsi_period:]]
        losses = [abs(min(c, 0)) for c in changes[-self.rsi_period:]]

        avg_gain = sum(gains) / self.rsi_period
        avg_loss = sum(losses) / self.rsi_period

        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        # Normalize RSI to 0-1 range
        return rsi / 100.0

    def _calculate_volatility(self, symbol: str) -> float | None:
        """Calculate volatility (standard deviation of returns)."""
        prices = list(self.price_history[symbol])
        if len(prices) < self.volatility_period + 1:
            return None

        returns = [
            (prices[i] - prices[i-1]) / prices[i-1]
            for i in range(-self.volatility_period, 0)
            if prices[i-1] != 0
        ]

        if not returns:
            return None

        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        volatility = math.sqrt(variance)

        # Return inverse (lower volatility = better)
        return 1.0 / (1.0 + volatility) if volatility > 0 else 1.0

    def _calculate_composite_score(self, symbol: str) -> float | None:
        """
        Calculate composite score from multiple factors.

        Returns:
            Composite score (0-1) or None if insufficient data
        """
        momentum = self._calculate_momentum(symbol)
        rsi = self._calculate_rsi(symbol)
        volatility = self._calculate_volatility(symbol)

        if momentum is None or rsi is None or volatility is None:
            return None

        # Normalize momentum to 0-1 (assuming -50% to +50% range)
        momentum_normalized = max(0, min(1, (momentum + 0.5)))

        # Composite score
        score = (
            self.momentum_weight * momentum_normalized +
            self.rsi_weight * rsi +
            self.volatility_weight * volatility
        )

        return score

    def _rank_stocks(self) -> list[str]:
        """
        Rank all stocks by composite score.

        Returns:
            List of top N stocks to hold
        """
        valid_symbols = []

        for symbol in self.price_history.keys():
            score = self._calculate_composite_score(symbol)
            if score is not None:
                self.composite_scores[symbol] = score
                valid_symbols.append(symbol)

        if len(valid_symbols) < self.min_stocks:
            logger.warning(
                f"Only {len(valid_symbols)} stocks with data (min: {self.min_stocks})"
            )
            return []

        # Sort by composite score (descending)
        sorted_symbols = sorted(
            valid_symbols,
            key=lambda s: self.composite_scores[s],
            reverse=True
        )

        # Return top N
        return sorted_symbols[:min(self.top_n, len(sorted_symbols))]

    def on_market_data(
        self,
        tick: MarketDataPoint,
        portfolio: TradingPortfolio
    ) -> list[Order]:
        """
        Process market data and rebalance to top-ranked stocks.

        Returns:
            List of rebalancing orders
        """
        # Validate tick
        if tick.price <= 0:
            logger.warning(f"Invalid price {tick.price} for {tick.symbol}")
            return []

        # Initialize price history
        if tick.symbol not in self.price_history:
            max_period = max(self.momentum_period, self.rsi_period, self.volatility_period)
            self.price_history[tick.symbol] = deque(maxlen=max_period + 10)
            logger.info(f"Added {tick.symbol} to relative strength universe")

        # Update prices
        self.price_history[tick.symbol].append(tick.price)
        self.current_prices[tick.symbol] = tick.price

        # Increment tick count
        self.global_tick_count += 1

        # Check if time to rebalance
        if self.global_tick_count - self.last_rebalance_tick < self.rebalance_period:
            return []

        # Rebalance!
        logger.info(f"\n{'='*80}")
        logger.info(f"REBALANCING RELATIVE STRENGTH at tick {self.global_tick_count}")
        logger.info(f"{'='*80}")

        # Rank stocks
        top_stocks = self._rank_stocks()

        if not top_stocks:
            return []

        # Log rankings
        logger.info(f"\nTop {len(top_stocks)} stocks by composite score:")
        for symbol in top_stocks:
            score = self.composite_scores[symbol]
            logger.info(f"  {symbol}: score={score:.4f}")

        # Generate rebalance orders
        orders = []
        self.target_holdings = set(top_stocks)

        # Close positions not in top N
        for symbol in self.current_prices.keys():
            position = portfolio.get_position(symbol)
            current_qty = position.quantity if position else 0

            if symbol not in self.target_holdings and current_qty > 0:
                logger.info(f"Closing position in {symbol} (no longer in top {self.top_n})")
                orders.append(Order(
                    symbol=symbol,
                    side=OrderSide.SELL,
                    order_type=OrderType.MARKET,
                    quantity=current_qty
                ))

        # Open/adjust positions in top N
        for symbol in top_stocks:
            price = self.current_prices[symbol]
            position = portfolio.get_position(symbol)
            current_qty = position.quantity if position else 0

            target_qty = min(
                int(self.position_size / price),
                self.max_position
            )

            qty_diff = target_qty - current_qty

            if qty_diff > 0:
                logger.info(f"Buying {qty_diff} shares of {symbol}")
                orders.append(Order(
                    symbol=symbol,
                    side=OrderSide.BUY,
                    order_type=OrderType.MARKET,
                    quantity=qty_diff
                ))

        self.last_rebalance_tick = self.global_tick_count

        return orders

    def __repr__(self) -> str:
        return (
            f"RelativeStrengthStrategy(top_{self.top_n}, "
            f"weights=[mom:{self.momentum_weight},rsi:{self.rsi_weight},vol:{self.volatility_weight}])"
        )
