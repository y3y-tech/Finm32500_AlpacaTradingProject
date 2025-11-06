"""
Order Book - Heap-based bid/ask order matching with price-time priority.

Implements a realistic order book with:
- Price-time priority matching
- Partial fills
- Order cancellation
- Best bid/ask quotes
"""

import heapq
from typing import Optional
from datetime import datetime
import uuid

from src.models import Order, Trade, OrderSide, OrderStatus, OrderType


class OrderBook:
    """
    Maintains bid and ask orders with price-time priority matching.

    Uses heaps for O(log n) insertion and O(1) best price lookup:
    - Bids: Max heap (highest price first)
    - Asks: Min heap (lowest price first)

    Within same price level, orders are matched FIFO (time priority).

    Example:
        book = OrderBook("AAPL")
        book.add_order(buy_order)
        book.add_order(sell_order)
        trades = book.match_orders()  # Returns list of executed trades
    """

    def __init__(self, symbol: str):
        """
        Initialize order book for a specific symbol.

        Args:
            symbol: Asset symbol (e.g., 'AAPL', 'BTCUSD')
        """
        self.symbol = symbol

        # Heaps for bid and ask orders
        # Bids: max heap (negate price for heapq min heap)
        # Format: (-price, timestamp, order)
        self.bids: list[tuple[float, datetime, Order]] = []

        # Asks: min heap (lowest price first)
        # Format: (price, timestamp, order)
        self.asks: list[tuple[float, datetime, Order]] = []

        # Order lookup by ID for fast cancellation
        self.orders: dict[str, Order] = {}

    def add_order(self, order: Order) -> None:
        """
        Add order to the book.

        Args:
            order: Order to add

        Raises:
            ValueError: If order symbol doesn't match book symbol
        """
        if order.symbol != self.symbol:
            raise ValueError(
                f"Order symbol {order.symbol} doesn't match book symbol {self.symbol}"
            )

        if order.order_type != OrderType.LIMIT:
            raise ValueError(
                "Only LIMIT orders can be added to order book. "
                "MARKET orders should go directly to matching engine."
            )

        if order.price is None:
            raise ValueError("LIMIT orders must have a price")

        # Add to appropriate heap
        if order.side == OrderSide.BUY:
            # Max heap: negate price
            heapq.heappush(self.bids, (-order.price, order.timestamp, order))
        else:  # SELL
            # Min heap: keep price positive
            heapq.heappush(self.asks, (order.price, order.timestamp, order))

        # Add to lookup dict
        self.orders[order.order_id] = order

    def match_orders(self) -> list[Trade]:
        """
        Match crossing orders and generate trades.

        Matching logic:
        - Best bid >= best ask → orders cross, execute trade
        - Match at the price of the resting order (maker price)
        - Continue until no more crossing orders

        Returns:
            List of Trade objects for all matched orders
        """
        trades = []

        while self.bids and self.asks:
            # Peek at best bid and ask (without removing)
            best_bid = -self.bids[0][0]  # Negate back to positive
            best_ask = self.asks[0][0]

            # Check if orders cross
            if best_bid < best_ask:
                break  # No more matches possible

            # Pop best bid and ask
            _, bid_time, bid_order = heapq.heappop(self.bids)
            _, ask_time, ask_order = heapq.heappop(self.asks)

            # Skip cancelled orders
            if bid_order.status == OrderStatus.CANCELLED or \
               ask_order.status == OrderStatus.CANCELLED:
                continue

            # Determine fill quantity (minimum of both orders' remaining)
            fill_qty = min(bid_order.remaining_quantity, ask_order.remaining_quantity)

            # Determine fill price (maker price = resting order's price)
            # The order that arrived first gets its price
            if bid_time < ask_time:
                fill_price = bid_order.price  # Bid was resting
            else:
                fill_price = ask_order.price  # Ask was resting

            # Create trades
            trade_id = str(uuid.uuid4())
            timestamp = datetime.now()

            # Trade for buy order
            buy_trade = Trade(
                trade_id=trade_id + "_BUY",
                order_id=bid_order.order_id,
                timestamp=timestamp,
                symbol=self.symbol,
                side=OrderSide.BUY,
                quantity=fill_qty,
                price=fill_price
            )

            # Trade for sell order
            sell_trade = Trade(
                trade_id=trade_id + "_SELL",
                order_id=ask_order.order_id,
                timestamp=timestamp,
                symbol=self.symbol,
                side=OrderSide.SELL,
                quantity=fill_qty,
                price=fill_price
            )

            trades.extend([buy_trade, sell_trade])

            # Update order fill quantities
            bid_order.fill(fill_qty, fill_price)
            ask_order.fill(fill_qty, fill_price)

            # If orders still have remaining quantity, put them back
            if not bid_order.is_filled:
                heapq.heappush(self.bids, (-bid_order.price, bid_time, bid_order))
            else:
                bid_order.status = OrderStatus.FILLED

            if not ask_order.is_filled:
                heapq.heappush(self.asks, (ask_order.price, ask_time, ask_order))
            else:
                ask_order.status = OrderStatus.FILLED

        return trades

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order by ID.

        Note: Order is marked as cancelled but remains in heap until
        it would be matched (for performance). Heap is cleaned lazily.

        Args:
            order_id: Order ID to cancel

        Returns:
            True if order was cancelled, False if not found or already filled
        """
        order = self.orders.get(order_id)
        if order is None:
            return False

        if order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED]:
            return False

        order.status = OrderStatus.CANCELLED
        return True

    def get_best_bid(self) -> Optional[float]:
        """
        Get the best (highest) bid price.

        Returns:
            Best bid price or None if no bids
        """
        # Clean cancelled orders from top of heap
        while self.bids and self.bids[0][2].status == OrderStatus.CANCELLED:
            heapq.heappop(self.bids)

        if not self.bids:
            return None

        return -self.bids[0][0]  # Negate back to positive

    def get_best_ask(self) -> Optional[float]:
        """
        Get the best (lowest) ask price.

        Returns:
            Best ask price or None if no asks
        """
        # Clean cancelled orders from top of heap
        while self.asks and self.asks[0][2].status == OrderStatus.CANCELLED:
            heapq.heappop(self.asks)

        if not self.asks:
            return None

        return self.asks[0][0]

    def get_spread(self) -> Optional[float]:
        """
        Get the bid-ask spread.

        Returns:
            Spread (ask - bid) or None if either side is empty
        """
        bid = self.get_best_bid()
        ask = self.get_best_ask()

        if bid is None or ask is None:
            return None

        return ask - bid

    def get_mid_price(self) -> Optional[float]:
        """
        Get the mid price (average of best bid and ask).

        Returns:
            Mid price or None if either side is empty
        """
        bid = self.get_best_bid()
        ask = self.get_best_ask()

        if bid is None or ask is None:
            return None

        return (bid + ask) / 2

    def get_order_count(self) -> dict[str, int]:
        """
        Get count of active orders on each side.

        Returns:
            Dictionary with 'bids' and 'asks' counts
        """
        # Count non-cancelled orders
        bid_count = sum(
            1 for _, _, order in self.bids
            if order.status not in [OrderStatus.CANCELLED, OrderStatus.FILLED]
        )
        ask_count = sum(
            1 for _, _, order in self.asks
            if order.status not in [OrderStatus.CANCELLED, OrderStatus.FILLED]
        )

        return {'bids': bid_count, 'asks': ask_count}

    def clear(self) -> None:
        """Clear all orders from the book."""
        self.bids.clear()
        self.asks.clear()
        self.orders.clear()

    def __repr__(self) -> str:
        counts = self.get_order_count()
        bid = self.get_best_bid()
        ask = self.get_best_ask()
        return (
            f"OrderBook(symbol={self.symbol}, "
            f"bids={counts['bids']} @ {bid}, "
            f"asks={counts['asks']} @ {ask})"
        )
