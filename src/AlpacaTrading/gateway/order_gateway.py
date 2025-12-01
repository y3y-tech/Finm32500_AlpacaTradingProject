"""
Order Gateway - Logs all order lifecycle events for audit and analysis.

Tracks order submission, modifications, fills, and cancellations.
"""

import csv
from datetime import datetime
import logging
from pathlib import Path

from AlpacaTrading.models import Order, Trade

logger = logging.getLogger(__name__)


class OrderGateway:
    """
    Logs all order lifecycle events to CSV for audit trail and analysis.

    Events Logged:
    - SENT: Order submitted
    - MODIFIED: Order parameters changed
    - PARTIAL_FILL: Order partially filled
    - FILLED: Order completely filled
    - CANCELLED: Order cancelled
    - REJECTED: Order rejected by validation

    CSV Format:
    timestamp, event_type, order_id, symbol, side, order_type, quantity,
    price, status, filled_quantity, average_fill_price, message
    """

    def __init__(self, log_file: str, append: bool = False):
        """
        Initialize order gateway with log file.

        Args:
            log_file: Path to CSV log file
            append: If True, append to existing file. If False, create new file.
        """
        self.log_file = Path(log_file)
        self.append = append

        # Create directory if it doesn't exist
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        # Initialize file with headers if not appending
        if not append or not self.log_file.exists():
            self._write_header()

    def _write_header(self) -> None:
        """Write CSV header to log file."""
        with self.log_file.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "timestamp",
                    "event_type",
                    "order_id",
                    "symbol",
                    "side",
                    "order_type",
                    "quantity",
                    "price",
                    "status",
                    "filled_quantity",
                    "average_fill_price",
                    "message",
                ]
            )

    def log_order_sent(self, order: Order, message: str = "") -> None:
        """Log order submission event."""
        self._log_event("SENT", order, message)

    def log_order_modified(self, order: Order, message: str = "") -> None:
        """Log order modification event."""
        self._log_event("MODIFIED", order, message)

    def log_order_filled(self, order: Order, message: str = "") -> None:
        """Log order complete fill event."""
        self._log_event("FILLED", order, message)

    def log_order_partial_fill(
        self, order: Order, fill_qty: float, fill_price: float
    ) -> None:
        """Log partial fill event."""
        message = f"Partial fill: {fill_qty} @ {fill_price}"
        self._log_event("PARTIAL_FILL", order, message)

    def log_order_cancelled(self, order: Order, message: str = "") -> None:
        """Log order cancellation event."""
        self._log_event("CANCELLED", order, message)

    def log_order_rejected(self, order: Order, reason: str) -> None:
        """Log order rejection event."""
        self._log_event("REJECTED", order, reason)

    def log_trade(self, trade: Trade, order: Order) -> None:
        """Log trade execution (generated from order fill)."""
        message = f"Trade: {trade.trade_id}, {trade.quantity} @ {trade.price}"
        self._log_event("TRADE", order, message)

    def _log_event(self, event_type: str, order: Order, message: str = "") -> None:
        """
        Internal method to log an order event.

        Args:
            event_type: Type of event (SENT, FILLED, etc.)
            order: Order object
            message: Additional message or context
        """
        with self.log_file.open("a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    datetime.now().isoformat(),
                    event_type,
                    order.order_id,
                    order.symbol,
                    order.side.value,
                    order.order_type.value,
                    order.quantity,
                    order.price if order.price is not None else "",
                    order.status.value,
                    order.filled_quantity,
                    order.average_fill_price,
                    message,
                ]
            )

    def get_order_history(self, order_id: str | None = None) -> list[dict]:
        """
        Retrieve order history from log file.

        Args:
            order_id: If provided, filter to specific order. Otherwise return all.

        Returns:
            List of order event dictionaries
        """
        if not self.log_file.exists():
            return []

        events = []
        with self.log_file.open("r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if order_id is None or row["order_id"] == order_id:
                    events.append(row)

        return events

    def get_fill_summary(self) -> dict:
        """
        Get summary statistics of order fills.

        Returns:
            Dictionary with fill statistics:
            - total_orders: Total orders sent
            - filled_orders: Orders completely filled
            - partial_fills: Orders partially filled
            - cancelled_orders: Orders cancelled
            - rejected_orders: Orders rejected
            - fill_rate: Percentage of orders filled
        """
        if not self.log_file.exists():
            return {
                "total_orders": 0,
                "filled_orders": 0,
                "partial_fills": 0,
                "cancelled_orders": 0,
                "rejected_orders": 0,
                "fill_rate": 0.0,
            }

        order_ids = set()
        filled = set()
        partial = set()
        cancelled = set()
        rejected = set()

        with self.log_file.open("r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                order_id = row["order_id"]
                event = row["event_type"]

                if event == "SENT":
                    order_ids.add(order_id)
                elif event == "FILLED":
                    filled.add(order_id)
                elif event == "PARTIAL_FILL":
                    partial.add(order_id)
                elif event == "CANCELLED":
                    cancelled.add(order_id)
                elif event == "REJECTED":
                    rejected.add(order_id)

        total = len(order_ids)
        fill_rate = (len(filled) / total * 100) if total > 0 else 0.0

        return {
            "total_orders": total,
            "filled_orders": len(filled),
            "partial_fills": len(partial),
            "cancelled_orders": len(cancelled),
            "rejected_orders": len(rejected),
            "fill_rate": fill_rate,
        }

    def clear_log(self) -> None:
        """Clear the log file and write new header."""
        self._write_header()

    def __repr__(self) -> str:
        return f"OrderGateway(log_file={self.log_file})"
