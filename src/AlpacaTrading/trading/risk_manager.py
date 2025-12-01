"""
Risk Manager - Implements stop-loss and risk control mechanisms.

Provides multiple types of stop-loss protection:
- Position-level stops (fixed %, trailing %)
- Portfolio-level stops (max daily loss, max drawdown)
- Circuit breakers (pause trading on unusual conditions)
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import logging

from AlpacaTrading.models import Order, OrderSide, OrderType, Position

logger = logging.getLogger(__name__)


class StopType(Enum):
    """Types of stop-loss orders."""
    FIXED_PERCENT = "fixed_percent"  # Stop at X% loss from entry
    TRAILING_PERCENT = "trailing_percent"  # Trailing stop that moves with profit
    ABSOLUTE_PRICE = "absolute_price"  # Stop at specific price level
    PORTFOLIO_LOSS = "portfolio_loss"  # Stop all trading if portfolio down X%
    MAX_DRAWDOWN = "max_drawdown"  # Stop if drawdown exceeds threshold


@dataclass
class StopLossConfig:
    """
    Configuration for stop-loss risk management.

    Attributes:
        position_stop_pct: Per-position stop loss as % from entry (e.g., 2.0 = 2% loss)
        trailing_stop_pct: Trailing stop % from peak price (e.g., 3.0 = 3% trailing)
        portfolio_stop_pct: Max portfolio loss % before circuit breaker (e.g., 5.0 = 5% daily loss)
        max_drawdown_pct: Max drawdown % before circuit breaker (e.g., 10.0 = 10% from peak)
        use_trailing_stops: Enable trailing stops (default: False)
        enable_circuit_breaker: Enable portfolio-level circuit breaker (default: True)
    """
    position_stop_pct: float = 2.0  # 2% position stop loss
    trailing_stop_pct: float = 3.0  # 3% trailing stop
    portfolio_stop_pct: float = 5.0  # 5% portfolio stop loss
    max_drawdown_pct: float = 10.0  # 10% max drawdown
    use_trailing_stops: bool = False
    enable_circuit_breaker: bool = True


@dataclass
class PositionStop:
    """
    Tracks stop-loss information for a position.

    Attributes:
        symbol: Asset symbol
        entry_price: Price at which position was entered
        stop_price: Current stop price level
        highest_price: Highest price seen (for trailing stops)
        stop_type: Type of stop loss
    """
    symbol: str
    entry_price: float
    stop_price: float
    highest_price: float
    stop_type: StopType


class RiskManager:
    """
    Manages stop-loss orders and portfolio risk controls.

    Features:
    - Position-level stop losses (fixed or trailing)
    - Portfolio-level circuit breakers
    - Automatic exit order generation when stops triggered
    - Tracks high water marks for trailing stops

    Example:
        config = StopLossConfig(position_stop_pct=2.0, use_trailing_stops=True)
        risk_mgr = RiskManager(config, initial_portfolio_value=100_000)

        # Add stop for new position
        risk_mgr.add_position_stop(symbol="AAPL", entry_price=150.0, quantity=100)

        # Check stops on price update
        exit_orders = risk_mgr.check_stops(
            current_prices={"AAPL": 147.0},
            portfolio_value=98_000,
            positions=portfolio.positions
        )

        # Execute exit orders if any
        for order in exit_orders:
            execute_order(order)
    """

    def __init__(self, config: StopLossConfig, initial_portfolio_value: float):
        """
        Initialize risk manager.

        Args:
            config: Stop-loss configuration
            initial_portfolio_value: Starting portfolio value for circuit breaker
        """
        self.config = config
        self.initial_portfolio_value = initial_portfolio_value
        self.daily_start_value = initial_portfolio_value
        self.high_water_mark = initial_portfolio_value

        # Track stops for each position
        self.position_stops: dict[str, PositionStop] = {}

        # Circuit breaker state
        self.circuit_breaker_triggered = False
        self.circuit_breaker_time: datetime | None = None

    def add_position_stop(
        self,
        symbol: str,
        entry_price: float,
        quantity: float,
        stop_type: StopType | None = None
    ) -> None:
        """
        Add or update stop-loss for a position.

        Args:
            symbol: Asset symbol
            entry_price: Entry price for position
            quantity: Position size (positive for long, negative for short)
            stop_type: Type of stop (default: uses config settings)
        """
        # Determine stop type
        if stop_type is None:
            stop_type = (
                StopType.TRAILING_PERCENT
                if self.config.use_trailing_stops
                else StopType.FIXED_PERCENT
            )

        # Calculate initial stop price
        if quantity > 0:  # Long position
            stop_pct = (
                self.config.trailing_stop_pct
                if stop_type == StopType.TRAILING_PERCENT
                else self.config.position_stop_pct
            )
            stop_price = entry_price * (1 - stop_pct / 100)
        else:  # Short position
            stop_pct = (
                self.config.trailing_stop_pct
                if stop_type == StopType.TRAILING_PERCENT
                else self.config.position_stop_pct
            )
            stop_price = entry_price * (1 + stop_pct / 100)

        self.position_stops[symbol] = PositionStop(
            symbol=symbol,
            entry_price=entry_price,
            stop_price=stop_price,
            highest_price=entry_price,
            stop_type=stop_type
        )

    def remove_position_stop(self, symbol: str) -> None:
        """
        Remove stop-loss tracking for a position.

        Args:
            symbol: Asset symbol
        """
        if symbol in self.position_stops:
            del self.position_stops[symbol]

    def check_stops(
        self,
        current_prices: dict[str, float],
        portfolio_value: float,
        positions: dict[str, Position]
    ) -> list[Order]:
        """
        Check all stop-loss conditions and generate exit orders if triggered.

        Args:
            current_prices: Current market prices by symbol
            portfolio_value: Current total portfolio value
            positions: Current positions from portfolio

        Returns:
            List of exit orders to execute (empty if no stops triggered)
        """
        exit_orders = []

        # Check circuit breaker first
        if self._check_circuit_breaker(portfolio_value):
            # Circuit breaker triggered - exit all positions
            return self._generate_exit_all_orders(positions, current_prices)

        # Check individual position stops
        for symbol, position in positions.items():
            if symbol not in current_prices:
                continue  # Skip if no current price

            if symbol not in self.position_stops:
                # Auto-add stop for positions without explicit stop
                self.add_position_stop(
                    symbol=symbol,
                    entry_price=position.average_cost,
                    quantity=position.quantity
                )

            current_price = current_prices[symbol]
            stop = self.position_stops[symbol]

            # Update trailing stop if applicable
            if stop.stop_type == StopType.TRAILING_PERCENT:
                self._update_trailing_stop(stop, current_price, position.quantity)

            # Check if stop triggered
            if self._is_stop_triggered(stop, current_price, position.quantity):
                # Generate exit order
                exit_order = Order(
                    symbol=symbol,
                    side=OrderSide.SELL if position.quantity > 0 else OrderSide.BUY,
                    quantity=abs(position.quantity),
                    order_type=OrderType.MARKET,
                    price=None  # Market order
                )
                exit_orders.append(exit_order)

                # Remove stop (will be re-added if position re-entered)
                self.remove_position_stop(symbol)

        return exit_orders

    def _check_circuit_breaker(self, portfolio_value: float) -> bool:
        """
        Check if portfolio-level circuit breaker should trigger.

        Args:
            portfolio_value: Current portfolio value

        Returns:
            True if circuit breaker triggered
        """
        if not self.config.enable_circuit_breaker:
            return False

        if self.circuit_breaker_triggered:
            return True  # Already triggered

        # Update high water mark
        if portfolio_value > self.high_water_mark:
            self.high_water_mark = portfolio_value

        # Check daily loss limit
        daily_loss_pct = (
            (self.daily_start_value - portfolio_value) / self.daily_start_value * 100
        )
        if daily_loss_pct >= self.config.portfolio_stop_pct:
            self.circuit_breaker_triggered = True
            self.circuit_breaker_time = datetime.now()
            return True

        # Check max drawdown
        drawdown_pct = (
            (self.high_water_mark - portfolio_value) / self.high_water_mark * 100
        )
        if drawdown_pct >= self.config.max_drawdown_pct:
            self.circuit_breaker_triggered = True
            self.circuit_breaker_time = datetime.now()
            return True

        return False

    def _update_trailing_stop(
        self,
        stop: PositionStop,
        current_price: float,
        quantity: float
    ) -> None:
        """
        Update trailing stop price if position is profitable.

        Args:
            stop: Position stop to update
            current_price: Current market price
            quantity: Position size
        """
        if quantity > 0:  # Long position
            if current_price > stop.highest_price:
                stop.highest_price = current_price
                # Move stop up
                new_stop = current_price * (1 - self.config.trailing_stop_pct / 100)
                stop.stop_price = max(stop.stop_price, new_stop)
        else:  # Short position
            if current_price < stop.highest_price:
                stop.highest_price = current_price
                # Move stop down
                new_stop = current_price * (1 + self.config.trailing_stop_pct / 100)
                stop.stop_price = min(stop.stop_price, new_stop)

    def _is_stop_triggered(
        self,
        stop: PositionStop,
        current_price: float,
        quantity: float
    ) -> bool:
        """
        Check if stop-loss is triggered.

        Args:
            stop: Position stop configuration
            current_price: Current market price
            quantity: Position size

        Returns:
            True if stop triggered
        """
        if quantity > 0:  # Long position
            return current_price <= stop.stop_price
        else:  # Short position
            return current_price >= stop.stop_price

    def _generate_exit_all_orders(
        self,
        positions: dict[str, Position],
        current_prices: dict[str, float]
    ) -> list[Order]:
        """
        Generate market orders to exit all positions (circuit breaker).

        Args:
            positions: All current positions
            current_prices: Current market prices

        Returns:
            List of exit orders
        """
        exit_orders = []

        for symbol, position in positions.items():
            if position.quantity == 0:
                continue  # No position to exit

            exit_order = Order(
                symbol=symbol,
                side=OrderSide.SELL if position.quantity > 0 else OrderSide.BUY,
                quantity=abs(position.quantity),
                order_type=OrderType.MARKET,
                price=None
            )
            exit_orders.append(exit_order)

            # Remove position stop
            self.remove_position_stop(symbol)

        return exit_orders

    def reset_daily_tracking(self, current_portfolio_value: float) -> None:
        """
        Reset daily tracking (call at start of trading day).

        Args:
            current_portfolio_value: Portfolio value at start of day
        """
        self.daily_start_value = current_portfolio_value

    def reset_circuit_breaker(self) -> None:
        """
        Reset circuit breaker (use with caution).

        Only reset if you're certain you want to resume trading after a stop.
        """
        self.circuit_breaker_triggered = False
        self.circuit_breaker_time = None

    def get_status(self) -> dict:
        """
        Get current risk manager status.

        Returns:
            Dictionary with status information
        """
        return {
            'circuit_breaker_triggered': self.circuit_breaker_triggered,
            'circuit_breaker_time': self.circuit_breaker_time,
            'num_active_stops': len(self.position_stops),
            'high_water_mark': self.high_water_mark,
            'daily_start_value': self.daily_start_value,
            'config': {
                'position_stop_pct': self.config.position_stop_pct,
                'trailing_stop_pct': self.config.trailing_stop_pct,
                'portfolio_stop_pct': self.config.portfolio_stop_pct,
                'max_drawdown_pct': self.config.max_drawdown_pct,
                'use_trailing_stops': self.config.use_trailing_stops,
                'enable_circuit_breaker': self.config.enable_circuit_breaker
            }
        }

    def __repr__(self) -> str:
        status = "TRIGGERED" if self.circuit_breaker_triggered else "ACTIVE"
        return (
            f"RiskManager(status={status}, "
            f"active_stops={len(self.position_stops)}, "
            f"position_stop={self.config.position_stop_pct}%)"
        )
