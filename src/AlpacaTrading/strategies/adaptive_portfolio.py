"""
Adaptive Multi-Strategy Portfolio Manager

Runs multiple strategies simultaneously with dynamic capital allocation.
Winners get more weight, losers get less weight.
Rebalances periodically based on recent performance.

Perfect for trading competitions - let the best strategy rise to the top!
"""

from collections import defaultdict, deque
from dataclasses import dataclass
import logging
from typing import Dict, List

from AlpacaTrading.models import MarketDataPoint, Order, OrderSide, OrderType
from AlpacaTrading.trading.portfolio import TradingPortfolio
from .base import TradingStrategy

logger = logging.getLogger(__name__)


@dataclass
class StrategyPerformance:
    """Track performance metrics for a single strategy."""
    strategy_name: str
    total_pnl: float = 0.0
    recent_pnl: float = 0.0  # P&L since last rebalance
    num_trades: int = 0
    win_count: int = 0
    loss_count: int = 0
    current_allocation: float = 0.0  # Current % of capital allocated
    target_allocation: float = 0.0  # Target % after rebalance

    @property
    def win_rate(self) -> float:
        if self.num_trades == 0:
            return 0.0
        return self.win_count / self.num_trades

    @property
    def avg_trade_pnl(self) -> float:
        if self.num_trades == 0:
            return 0.0
        return self.total_pnl / self.num_trades


class AdaptivePortfolioStrategy(TradingStrategy):
    """
    Meta-strategy that runs multiple strategies with adaptive capital allocation.

    Logic:
    1. Run all sub-strategies simultaneously
    2. Track each strategy's P&L independently
    3. Periodically rebalance capital allocation based on performance
    4. Winners get more capital, losers get less

    Parameters:
        strategies: Dict of {name: strategy} to run
        rebalance_period: Ticks between rebalances (default: 360 for hourly @ 1min bars)
        min_allocation: Minimum % allocation per strategy (default: 0.05 = 5%)
        max_allocation: Maximum % allocation per strategy (default: 0.40 = 40%)
        performance_lookback: Ticks to look back for performance (default: 360)
        allocation_method: 'pnl' or 'sharpe' or 'win_rate' (default: 'pnl')
    """

    def __init__(
        self,
        strategies: Dict[str, TradingStrategy],
        rebalance_period: int = 360,  # 1 hour at 1-min bars
        min_allocation: float = 0.05,
        max_allocation: float = 0.40,
        performance_lookback: int = 360,
        allocation_method: str = 'pnl'
    ):
        super().__init__("AdaptivePortfolio")

        # Parameter validation
        if not strategies:
            raise ValueError("Must provide at least one strategy")
        if rebalance_period <= 0:
            raise ValueError(f"rebalance_period must be positive, got {rebalance_period}")
        if not (0 < min_allocation < 1):
            raise ValueError(f"min_allocation must be between 0 and 1, got {min_allocation}")
        if not (0 < max_allocation <= 1):
            raise ValueError(f"max_allocation must be between 0 and 1, got {max_allocation}")
        if min_allocation >= max_allocation:
            raise ValueError(f"min_allocation must be < max_allocation")
        if allocation_method not in ['pnl', 'sharpe', 'win_rate']:
            raise ValueError(f"allocation_method must be 'pnl', 'sharpe', or 'win_rate'")

        self.strategies = strategies
        self.rebalance_period = rebalance_period
        self.min_allocation = min_allocation
        self.max_allocation = max_allocation
        self.performance_lookback = performance_lookback
        self.allocation_method = allocation_method

        # Track performance for each strategy
        self.performance: Dict[str, StrategyPerformance] = {
            name: StrategyPerformance(strategy_name=name)
            for name in strategies.keys()
        }

        # Initialize equal allocation
        equal_weight = 1.0 / len(strategies)
        for perf in self.performance.values():
            perf.current_allocation = equal_weight
            perf.target_allocation = equal_weight

        # Track ticks and rebalancing
        self.global_tick_count = 0
        self.last_rebalance_tick = 0

        # Track P&L history for Sharpe calculation
        self.pnl_history: Dict[str, deque] = {
            name: deque(maxlen=performance_lookback)
            for name in strategies.keys()
        }

        # Track entry prices for P&L attribution
        self.entry_prices: Dict[str, Dict[str, float]] = defaultdict(dict)  # {strategy: {symbol: price}}
        self.strategy_positions: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))  # {strategy: {symbol: qty}}

    def _calculate_sharpe(self, strategy_name: str) -> float:
        """Calculate Sharpe ratio for a strategy."""
        pnls = list(self.pnl_history[strategy_name])
        if len(pnls) < 10:
            return 0.0

        mean_pnl = sum(pnls) / len(pnls)
        if mean_pnl == 0:
            return 0.0

        variance = sum((pnl - mean_pnl) ** 2 for pnl in pnls) / len(pnls)
        std_dev = variance ** 0.5

        if std_dev == 0:
            return 0.0

        return mean_pnl / std_dev

    def _calculate_allocations(self) -> Dict[str, float]:
        """
        Calculate new allocations based on performance.

        Returns:
            Dict of {strategy_name: target_allocation}
        """
        # Calculate performance scores
        scores = {}

        for name, perf in self.performance.items():
            if self.allocation_method == 'pnl':
                # Use recent P&L
                scores[name] = max(0, perf.recent_pnl)  # No negative scores

            elif self.allocation_method == 'sharpe':
                # Use Sharpe ratio
                sharpe = self._calculate_sharpe(name)
                scores[name] = max(0, sharpe)

            elif self.allocation_method == 'win_rate':
                # Use win rate
                scores[name] = perf.win_rate

        # Normalize scores to sum to 1
        total_score = sum(scores.values())

        if total_score == 0:
            # No positive performance - revert to equal weight
            equal_weight = 1.0 / len(self.strategies)
            return {name: equal_weight for name in self.strategies.keys()}

        # Calculate raw allocations
        raw_allocations = {
            name: score / total_score
            for name, score in scores.items()
        }

        # Apply min/max constraints
        allocations = {}
        for name, alloc in raw_allocations.items():
            allocations[name] = max(self.min_allocation, min(self.max_allocation, alloc))

        # Renormalize to sum to 1
        total_alloc = sum(allocations.values())
        allocations = {name: alloc / total_alloc for name, alloc in allocations.items()}

        return allocations

    def _rebalance(self, portfolio: TradingPortfolio) -> List[Order]:
        """
        Rebalance capital allocation across strategies.

        Returns:
            List of orders to execute rebalancing
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"REBALANCING ADAPTIVE PORTFOLIO at tick {self.global_tick_count}")
        logger.info(f"{'='*80}")

        # Calculate new allocations
        new_allocations = self._calculate_allocations()

        # Log performance and new allocations
        logger.info(f"\nStrategy Performance & Allocations:")
        logger.info(f"{'Strategy':<20} {'Recent P&L':>12} {'Total P&L':>12} {'Win Rate':>10} {'Old%':>6} {'New%':>6}")
        logger.info(f"{'-'*20} {'-'*12} {'-'*12} {'-'*10} {'-'*6} {'-'*6}")

        for name in sorted(self.strategies.keys()):
            perf = self.performance[name]
            old_alloc = perf.current_allocation * 100
            new_alloc = new_allocations[name] * 100

            logger.info(
                f"{name:<20} "
                f"${perf.recent_pnl:>11,.2f} "
                f"${perf.total_pnl:>11,.2f} "
                f"{perf.win_rate*100:>9.1f}% "
                f"{old_alloc:>5.1f}% "
                f"{new_alloc:>5.1f}%"
            )

        # Update allocations
        for name, alloc in new_allocations.items():
            self.performance[name].target_allocation = alloc

        # Reset recent P&L for next period
        for perf in self.performance.values():
            perf.recent_pnl = 0.0

        logger.info(f"\n{'='*80}\n")

        # Note: Actual position rebalancing happens gradually through
        # scaled order execution in on_market_data
        return []

    def on_market_data(
        self,
        tick: MarketDataPoint,
        portfolio: TradingPortfolio
    ) -> List[Order]:
        """
        Run all strategies and scale orders by their allocations.

        Returns:
            Combined list of orders from all strategies
        """
        # Validate tick
        if tick.price <= 0:
            return []

        # Increment tick count
        self.global_tick_count += 1

        # Check if time to rebalance
        if self.global_tick_count - self.last_rebalance_tick >= self.rebalance_period:
            self._rebalance(portfolio)
            self.last_rebalance_tick = self.global_tick_count

        # Run each strategy and collect orders
        all_orders = []

        for strategy_name, strategy in self.strategies.items():
            # Run strategy
            strategy_orders = strategy.process_market_data(tick, portfolio)

            if not strategy_orders:
                continue

            # Get current allocation for this strategy
            allocation = self.performance[strategy_name].target_allocation

            # Scale orders by allocation
            # Determine available capital for this strategy
            total_equity = portfolio.get_total_equity()
            strategy_capital = total_equity * allocation

            for order in strategy_orders:
                # Calculate scaled quantity based on strategy allocation
                order_value = order.quantity * tick.price
                max_value = strategy_capital * 0.9  # Use 90% of allocated capital per order

                if order_value > max_value:
                    # Scale down quantity
                    scaled_qty = int(max_value / tick.price)
                    if scaled_qty > 0:
                        # Create scaled order
                        scaled_order = Order(
                            symbol=order.symbol,
                            side=order.side,
                            order_type=order.order_type,
                            quantity=scaled_qty,
                            price=order.price
                        )

                        # Track for P&L attribution
                        if order.side == OrderSide.BUY:
                            self.entry_prices[strategy_name][order.symbol] = tick.price
                            self.strategy_positions[strategy_name][order.symbol] += scaled_qty
                        else:
                            # Attribute P&L
                            if order.symbol in self.entry_prices[strategy_name]:
                                entry_price = self.entry_prices[strategy_name][order.symbol]
                                pnl = (tick.price - entry_price) * min(scaled_qty, self.strategy_positions[strategy_name][order.symbol])

                                # Update performance
                                perf = self.performance[strategy_name]
                                perf.total_pnl += pnl
                                perf.recent_pnl += pnl
                                perf.num_trades += 1
                                if pnl > 0:
                                    perf.win_count += 1
                                else:
                                    perf.loss_count += 1

                                # Record for Sharpe calculation
                                self.pnl_history[strategy_name].append(pnl)

                            self.strategy_positions[strategy_name][order.symbol] -= scaled_qty

                        all_orders.append(scaled_order)
                        logger.debug(
                            f"{strategy_name} ({allocation*100:.1f}% allocation): "
                            f"{scaled_order.side.value} {scaled_order.quantity} {scaled_order.symbol}"
                        )
                else:
                    # Order is within allocation, keep as-is
                    all_orders.append(order)

                    # Track for P&L attribution
                    if order.side == OrderSide.BUY:
                        self.entry_prices[strategy_name][order.symbol] = tick.price
                        self.strategy_positions[strategy_name][order.symbol] += order.quantity
                    else:
                        if order.symbol in self.entry_prices[strategy_name]:
                            entry_price = self.entry_prices[strategy_name][order.symbol]
                            pnl = (tick.price - entry_price) * min(order.quantity, self.strategy_positions[strategy_name][order.symbol])

                            perf = self.performance[strategy_name]
                            perf.total_pnl += pnl
                            perf.recent_pnl += pnl
                            perf.num_trades += 1
                            if pnl > 0:
                                perf.win_count += 1
                            else:
                                perf.loss_count += 1

                            self.pnl_history[strategy_name].append(pnl)

                        self.strategy_positions[strategy_name][order.symbol] -= order.quantity

        return all_orders

    def on_start(self, portfolio: TradingPortfolio) -> None:
        """Initialize all sub-strategies."""
        super().on_start(portfolio)
        logger.info(f"\nAdaptive Portfolio initialized with {len(self.strategies)} strategies:")
        for name in self.strategies.keys():
            logger.info(f"  - {name} ({self.performance[name].current_allocation*100:.1f}% allocation)")
        logger.info(f"\nRebalancing every {self.rebalance_period} ticks")
        logger.info(f"Allocation method: {self.allocation_method}")
        logger.info(f"Allocation range: {self.min_allocation*100:.1f}% - {self.max_allocation*100:.1f}%\n")

        # Call on_start for all sub-strategies
        for strategy in self.strategies.values():
            strategy.on_start(portfolio)

    def on_end(self, portfolio: TradingPortfolio) -> None:
        """Finalize all sub-strategies."""
        # Print final performance
        logger.info(f"\n{'='*80}")
        logger.info(f"ADAPTIVE PORTFOLIO FINAL PERFORMANCE")
        logger.info(f"{'='*80}")
        logger.info(f"{'Strategy':<20} {'Total P&L':>12} {'Trades':>8} {'Win Rate':>10} {'Final%':>8}")
        logger.info(f"{'-'*20} {'-'*12} {'-'*8} {'-'*10} {'-'*8}")

        for name in sorted(self.strategies.keys()):
            perf = self.performance[name]
            logger.info(
                f"{name:<20} "
                f"${perf.total_pnl:>11,.2f} "
                f"{perf.num_trades:>8} "
                f"{perf.win_rate*100:>9.1f}% "
                f"{perf.target_allocation*100:>7.1f}%"
            )

        logger.info(f"{'='*80}\n")

        super().on_end(portfolio)

        # Call on_end for all sub-strategies
        for strategy in self.strategies.values():
            strategy.on_end(portfolio)

    def __repr__(self) -> str:
        return f"AdaptivePortfolioStrategy({len(self.strategies)} strategies)"
