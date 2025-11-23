from dataclasses import dataclass, field
import datetime
from abc import ABC, abstractmethod
from enum import Enum
import uuid


# ============================================================================
# ENUMS
# ============================================================================


class OrderStatus(Enum):
    """Order lifecycle states"""
    NEW = "NEW"
    PENDING = "PENDING"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class OrderSide(Enum):
    """Order side (buy or sell)"""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    """Order types"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"


# ============================================================================
# MARKET DATA
# ============================================================================


@dataclass(frozen=True)
class MarketDataPoint:
    """Immutable market tick data"""
    timestamp: datetime.datetime
    symbol: str
    price: float
    volume: float = 0.0  # Optional volume data


# ============================================================================
# ORDERS AND TRADES
# ============================================================================


@dataclass
class Order:
    """
    Enhanced order model supporting full trading lifecycle.

    Fields:
        order_id: Unique identifier (auto-generated if not provided)
        timestamp: Order creation time
        symbol: Asset symbol (e.g., 'AAPL', 'BTCUSD')
        side: BUY or SELL
        order_type: MARKET or LIMIT
        quantity: Shares/coins to trade
        price: Limit price (None for market orders)
        status: Current order status
        filled_quantity: Amount filled so far
        average_fill_price: Average price of fills
    """
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)
    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    price: float | None = None
    status: OrderStatus = OrderStatus.NEW
    filled_quantity: float = 0.0
    average_fill_price: float = 0.0

    def __post_init__(self):
        """Validate order parameters"""
        if self.quantity <= 0:
            raise ValueError("Order quantity must be positive")
        if self.order_type == OrderType.LIMIT and self.price is None:
            raise ValueError("Limit orders must specify a price")
        if self.price is not None and self.price <= 0:
            raise ValueError("Order price must be positive")

    @property
    def remaining_quantity(self) -> float:
        """Calculate unfilled quantity"""
        return self.quantity - self.filled_quantity

    @property
    def is_filled(self) -> bool:
        """Check if order is completely filled"""
        return self.filled_quantity >= self.quantity

    def fill(self, quantity: float, price: float) -> None:
        """
        Record a fill for this order.

        Updates filled_quantity and average_fill_price.
        """
        if quantity <= 0:
            raise ValueError("Fill quantity must be positive")
        if quantity > self.remaining_quantity:
            raise ValueError(f"Fill quantity {quantity} exceeds remaining {self.remaining_quantity}")

        # Update average fill price
        total_value = self.average_fill_price * self.filled_quantity + price * quantity
        self.filled_quantity += quantity
        self.average_fill_price = total_value / self.filled_quantity

        # Update status
        if self.is_filled:
            self.status = OrderStatus.FILLED
        else:
            self.status = OrderStatus.PARTIAL


@dataclass
class Trade:
    """
    Represents an executed trade (fill or partial fill).

    A single order can generate multiple trades if partially filled.
    """
    trade_id: str
    order_id: str
    timestamp: datetime.datetime
    symbol: str
    side: OrderSide
    quantity: float
    price: float

    def __post_init__(self):
        """Validate trade parameters"""
        if self.quantity <= 0:
            raise ValueError("Trade quantity must be positive")
        if self.price <= 0:
            raise ValueError("Trade price must be positive")

    @property
    def value(self) -> float:
        """Calculate trade notional value"""
        return self.quantity * self.price


# ============================================================================
# POSITIONS
# ============================================================================


class Position:
    """
    Tracks position in a single symbol with P&L calculation.

    Attributes:
        symbol: Asset symbol
        quantity: Net position (positive = long, negative = short, 0 = flat)
        average_cost: Average entry price (cost basis)
        realized_pnl: Closed P&L from completed trades
        unrealized_pnl: Open P&L based on current market price
    """

    def __init__(
        self,
        symbol: str,
        quantity: float = 0.0,
        average_cost: float = 0.0,
        realized_pnl: float = 0.0
    ):
        self.symbol = symbol
        self.quantity = quantity
        self.average_cost = average_cost
        self.realized_pnl = realized_pnl
        self.unrealized_pnl = 0.0

    def update_from_trade(self, trade: Trade) -> None:
        """
        Update position based on executed trade.

        Handles:
        - Opening positions (flat -> long/short)
        - Adding to positions (long -> more long, short -> more short)
        - Reducing positions (partial close)
        - Closing positions (flat)
        - Reversing positions (long -> short, short -> long)
        """
        trade_qty = trade.quantity if trade.side == OrderSide.BUY else -trade.quantity
        new_quantity = self.quantity + trade_qty

        # Case 1: Opening or adding to position
        if self.quantity == 0 or (self.quantity > 0 and new_quantity > self.quantity) or \
           (self.quantity < 0 and new_quantity < self.quantity):
            # Update average cost
            if self.quantity == 0:
                self.average_cost = trade.price
            else:
                total_cost = self.quantity * self.average_cost + trade_qty * trade.price
                self.average_cost = total_cost / new_quantity
            self.quantity = new_quantity

        # Case 2: Reducing or closing position
        elif (self.quantity > 0 and trade.side == OrderSide.SELL) or \
             (self.quantity < 0 and trade.side == OrderSide.BUY):
            # Realize P&L on the closed portion
            closed_qty = min(abs(trade_qty), abs(self.quantity))
            if self.quantity > 0:
                pnl_per_share = trade.price - self.average_cost
            else:
                pnl_per_share = self.average_cost - trade.price
            self.realized_pnl += pnl_per_share * closed_qty
            self.quantity = new_quantity

            # If position reversed, update average cost
            if (self.quantity > 0 and trade.side == OrderSide.BUY) or \
               (self.quantity < 0 and trade.side == OrderSide.SELL):
                self.average_cost = trade.price

    def update_unrealized_pnl(self, current_price: float) -> None:
        """Calculate unrealized P&L based on current market price"""
        if self.quantity == 0:
            self.unrealized_pnl = 0.0
        else:
            pnl_per_share = current_price - self.average_cost
            self.unrealized_pnl = pnl_per_share * self.quantity

    @property
    def total_pnl(self) -> float:
        """Total P&L (realized + unrealized)"""
        return self.realized_pnl + self.unrealized_pnl

    def __repr__(self) -> str:
        return (f"Position(symbol={self.symbol}, qty={self.quantity:.2f}, "
                f"avg_cost={self.average_cost:.2f}, realized_pnl={self.realized_pnl:.2f}, "
                f"unrealized_pnl={self.unrealized_pnl:.2f})")


# ============================================================================
# LEGACY MODELS (for backward compatibility with old strategies)
# ============================================================================


class Portfolio:
    """
    Legacy portfolio class for backward compatibility.

    NOTE: For new code, use src.trading.portfolio.Portfolio instead.
    This is kept to support old moving average strategies.
    """
    def __init__(self, initial_cash: float):
        self.cash: float = initial_cash
        self.positions: dict[str, Position] = {}
        self.order_history: list[Order] = []

    def calculate_pnl(self, order: Order) -> float:
        """Legacy P&L calculation"""
        if order.side == OrderSide.BUY:
            return -order.average_fill_price * order.quantity
        else:
            return order.average_fill_price * order.quantity

    def update_position(self, order: Order):
        """Legacy position update"""
        if order.symbol not in self.positions:
            self.positions[order.symbol] = Position(
                symbol=order.symbol,
                quantity=order.quantity if order.side == OrderSide.BUY else -order.quantity,
            )
        else:
            qty_delta = order.quantity if order.side == OrderSide.BUY else -order.quantity
            self.positions[order.symbol].quantity += qty_delta

        self.cash += self.calculate_pnl(order)
        self.order_history.append(order)


class Strategy(ABC):
    """
    Legacy strategy base class.

    NOTE: For new trading strategies, use src.strategies.base.TradingStrategy instead.
    This is kept to support old moving average strategies.
    """
    @abstractmethod
    def generate_signal(self, tick: MarketDataPoint) -> Order:
        pass
