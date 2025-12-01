"""
Order Manager - Validates orders against risk limits before execution.

Checks:
1. Capital sufficiency
2. Position limits (max long/short)
3. Order rate limits (orders per minute)
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import deque
import logging

from AlpacaTrading.models import Order, OrderSide, Position

logger = logging.getLogger(__name__)


@dataclass
class RiskConfig:
    """
    Risk management configuration parameters.

    Attributes:
        max_position_size: Maximum position size per symbol (in shares/coins)
        max_position_value: Maximum position value per symbol (in dollars)
        max_total_exposure: Maximum total portfolio exposure (sum of all position values)
        max_orders_per_minute: Maximum orders allowed per minute
        max_orders_per_symbol_per_minute: Maximum orders per symbol per minute
        min_cash_buffer: Minimum cash to maintain (safety buffer)
    """

    max_position_size: float = 1000.0
    max_position_value: float = 100_000.0
    max_total_exposure: float = 500_000.0
    max_orders_per_minute: int = 100
    max_orders_per_symbol_per_minute: int = 20
    min_cash_buffer: float = 1000.0


class OrderManager:
    """
    Validates and manages orders before submission to matching engine.

    Performs risk checks:
    - Capital: Ensure sufficient cash for buy orders
    - Position limits: Prevent excessive concentration
    - Rate limits: Prevent order spam

    Example:
        config = RiskConfig(max_position_size=500)
        manager = OrderManager(config)

        is_valid, error = manager.validate_order(order, portfolio)
        if is_valid:
            # Submit order
        else:
            print(f"Order rejected: {error}")
    """

    def __init__(self, risk_config: RiskConfig | None = None):
        """
        Initialize order manager.

        Args:
            risk_config: Risk configuration (uses defaults if not provided)
        """
        self.risk_config = risk_config or RiskConfig()

        # Track order timestamps for rate limiting
        # Format: { timestamp: order_id }
        self.order_timestamps: deque[tuple[datetime, str]] = deque()

        # Track orders per symbol
        # Format: { symbol: deque[(timestamp, order_id)] }
        self.symbol_order_timestamps: dict[str, deque[tuple[datetime, str]]] = {}

    def validate_order(
        self,
        order: Order,
        cash: float,
        positions: dict[str, Position],
        current_prices: dict[str, float],
    ) -> tuple[bool, str]:
        """
        Validate order against all risk checks.

        Args:
            order: Order to validate
            cash: Available cash
            positions: Current positions by symbol
            current_prices: Current market prices by symbol

        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if order passes all checks
            - error_message: Explanation if rejected, empty string if valid
        """
        # 1. Check rate limits
        is_valid, error = self._check_rate_limits(order)
        if not is_valid:
            return False, f"Rate limit exceeded: {error}"

        # 2. Check capital sufficiency
        is_valid, error = self._check_capital(order, cash)
        if not is_valid:
            return False, f"Insufficient capital: {error}"

        # 3. Check position limits
        is_valid, error = self._check_position_limits(order, positions, current_prices)
        if not is_valid:
            return False, f"Position limit exceeded: {error}"

        # 4. Check total exposure
        is_valid, error = self._check_total_exposure(order, positions, current_prices)
        if not is_valid:
            return False, f"Total exposure limit exceeded: {error}"

        # All checks passed
        return True, ""

    def record_order(self, order: Order) -> None:
        """
        Record order submission for rate limiting.

        Call this AFTER order is successfully submitted.

        Args:
            order: Submitted order
        """
        now = datetime.now()
        self.order_timestamps.append((now, order.order_id))

        if order.symbol not in self.symbol_order_timestamps:
            self.symbol_order_timestamps[order.symbol] = deque()
        self.symbol_order_timestamps[order.symbol].append((now, order.order_id))

        # Clean old timestamps (older than 1 minute)
        self._clean_old_timestamps()

    def _check_rate_limits(self, order: Order) -> tuple[bool, str]:
        """Check order rate limits."""
        self._clean_old_timestamps()

        # Check global rate limit
        if len(self.order_timestamps) >= self.risk_config.max_orders_per_minute:
            return (
                False,
                f"Global rate limit: {self.risk_config.max_orders_per_minute}/min",
            )

        # Check per-symbol rate limit
        symbol_timestamps = self.symbol_order_timestamps.get(order.symbol, deque())
        if len(symbol_timestamps) >= self.risk_config.max_orders_per_symbol_per_minute:
            return False, (
                f"Symbol rate limit: {self.risk_config.max_orders_per_symbol_per_minute}/min "
                f"for {order.symbol}"
            )

        return True, ""

    def _check_capital(self, order: Order, cash: float) -> tuple[bool, str]:
        """Check if sufficient capital for order."""
        # Only check for buy orders (sells release capital)
        if order.side == OrderSide.SELL:
            return True, ""

        # Estimate order value
        # For market orders, we don't know exact price, so this is approximate
        if order.price is None:
            # Market order: assume some slippage/cost
            # We can't validate precisely without market price
            return True, ""  # Let matching engine handle market orders

        order_value = order.quantity * order.price

        # Check if enough cash after maintaining buffer
        available = cash - self.risk_config.min_cash_buffer
        if order_value > available:
            return False, (
                f"Order value ${order_value:,.2f} exceeds available cash "
                f"${available:,.2f} (after ${self.risk_config.min_cash_buffer:,.2f} buffer)"
            )

        return True, ""

    def _check_position_limits(
        self,
        order: Order,
        positions: dict[str, Position],
        current_prices: dict[str, float],
    ) -> tuple[bool, str]:
        """Check position size and value limits."""
        current_position = positions.get(order.symbol)
        current_qty = current_position.quantity if current_position else 0.0

        # Calculate new position after order
        if order.side == OrderSide.BUY:
            new_qty = current_qty + order.quantity
        else:
            new_qty = current_qty - order.quantity

        # Check position size limit
        if abs(new_qty) > self.risk_config.max_position_size:
            return False, (
                f"Position size {abs(new_qty):,.0f} would exceed limit "
                f"{self.risk_config.max_position_size:,.0f} for {order.symbol}"
            )

        # Check position value limit
        current_price = current_prices.get(order.symbol)
        if current_price is not None:
            position_value = abs(new_qty) * current_price
            if position_value > self.risk_config.max_position_value:
                return False, (
                    f"Position value ${position_value:,.2f} would exceed limit "
                    f"${self.risk_config.max_position_value:,.2f} for {order.symbol}"
                )

        return True, ""

    def _check_total_exposure(
        self,
        order: Order,
        positions: dict[str, Position],
        current_prices: dict[str, float],
    ) -> tuple[bool, str]:
        """Check total portfolio exposure limit."""
        # Calculate current total exposure
        total_exposure = 0.0
        for symbol, position in positions.items():
            price = current_prices.get(symbol)
            if price is not None:
                total_exposure += abs(position.quantity) * price

        # Add this order's contribution
        if order.price is not None:
            order_value = order.quantity * order.price
            if order.side == OrderSide.BUY:
                total_exposure += order_value
            # For sells, exposure decreases, so no need to add

        if total_exposure > self.risk_config.max_total_exposure:
            return False, (
                f"Total exposure ${total_exposure:,.2f} would exceed limit "
                f"${self.risk_config.max_total_exposure:,.2f}"
            )

        return True, ""

    def _clean_old_timestamps(self) -> None:
        """Remove timestamps older than 1 minute."""
        cutoff = datetime.now() - timedelta(minutes=1)

        # Clean global timestamps
        while self.order_timestamps and self.order_timestamps[0][0] < cutoff:
            self.order_timestamps.popleft()

        # Clean per-symbol timestamps
        for symbol in self.symbol_order_timestamps:
            symbol_deque = self.symbol_order_timestamps[symbol]
            while symbol_deque and symbol_deque[0][0] < cutoff:
                symbol_deque.popleft()

    def get_order_rate_stats(self) -> dict:
        """
        Get current order rate statistics.

        Returns:
            Dictionary with rate stats:
            - orders_last_minute: Total orders in last minute
            - limit: Max orders per minute
            - available: Remaining order capacity
        """
        self._clean_old_timestamps()
        current = len(self.order_timestamps)
        limit = self.risk_config.max_orders_per_minute

        return {
            "orders_last_minute": current,
            "limit": limit,
            "available": limit - current,
        }

    def __repr__(self) -> str:
        return f"OrderManager(config={self.risk_config})"
