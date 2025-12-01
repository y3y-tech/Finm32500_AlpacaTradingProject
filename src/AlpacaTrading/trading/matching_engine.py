"""
Matching Engine - Simulates realistic order execution.

Implements probabilistic fill simulation with:
- Full fills
- Partial fills
- Cancellations
- Market impact/slippage
"""

import logging
import random
import uuid
from datetime import datetime

from AlpacaTrading.models import Order, Trade, OrderSide, OrderType, OrderStatus

logger = logging.getLogger(__name__)


class MatchingEngine:
    """
    Simulates order execution with realistic fill probabilities and transaction costs.

    Simulation Parameters:
    - fill_probability: Chance of full fill (default: 0.85)
    - partial_fill_probability: Chance of partial fill (default: 0.10)
    - cancel_probability: Chance of cancellation (default: 0.05)
    - market_impact: Slippage factor for market orders (default: 0.0002 = 0.02%)

    Transaction Cost Parameters:
    - commission_per_share: Fixed commission per share (default: 0.0, Alpaca is commission-free)
    - commission_min: Minimum commission per order (default: 0.0)
    - bid_ask_spread_bps: Bid-ask spread in basis points (default: 5 = 0.05%)
    - sec_fee_rate: SEC fee rate on sales (default: 0.0000278 = $27.80 per $1M)
    - liquidity_impact_factor: Additional slippage per $100k order size (default: 0.0001)

    Example:
        engine = MatchingEngine(
            fill_probability=0.9,
            bid_ask_spread_bps=5,
            commission_per_share=0.0
        )
        trades = engine.execute_order(order, current_market_price=150.0)

        for trade in trades:
            print(f"Filled {trade.quantity} @ {trade.price}")
    """

    def __init__(
        self,
        fill_probability: float = 0.85,
        partial_fill_probability: float = 0.10,
        cancel_probability: float = 0.05,
        market_impact: float = 0.0002,
        commission_per_share: float = 0.0,
        commission_min: float = 0.0,
        bid_ask_spread_bps: float = 5.0,
        sec_fee_rate: float = 0.0000278,
        liquidity_impact_factor: float = 0.0001,
        random_seed: int | None = None,
    ):
        """
        Initialize matching engine.

        Args:
            fill_probability: Probability of complete fill (0-1)
            partial_fill_probability: Probability of partial fill (0-1)
            cancel_probability: Probability of cancellation (0-1)
            market_impact: Slippage factor for market orders (e.g., 0.0002 = 0.02%)
            commission_per_share: Commission charged per share (Alpaca = 0.0)
            commission_min: Minimum commission per trade
            bid_ask_spread_bps: Bid-ask spread in basis points (1 bp = 0.01%)
            sec_fee_rate: SEC transaction fee on sales (US equities only)
            liquidity_impact_factor: Additional slippage per $100k order value
            random_seed: Random seed for reproducibility (None for random)
        """
        if not (0 <= fill_probability <= 1):
            raise ValueError("fill_probability must be between 0 and 1")
        if not (0 <= partial_fill_probability <= 1):
            raise ValueError("partial_fill_probability must be between 0 and 1")
        if not (0 <= cancel_probability <= 1):
            raise ValueError("cancel_probability must be between 0 and 1")

        total_prob = fill_probability + partial_fill_probability + cancel_probability
        if not (0.99 <= total_prob <= 1.01):  # Allow small floating point error
            raise ValueError(f"Probabilities must sum to 1.0, got {total_prob}")

        # Execution probabilities
        self.fill_probability = fill_probability
        self.partial_fill_probability = partial_fill_probability
        self.cancel_probability = cancel_probability
        self.market_impact = market_impact

        # Transaction costs
        self.commission_per_share = commission_per_share
        self.commission_min = commission_min
        self.bid_ask_spread_bps = bid_ask_spread_bps
        self.sec_fee_rate = sec_fee_rate
        self.liquidity_impact_factor = liquidity_impact_factor

        if random_seed is not None:
            random.seed(random_seed)

    def execute_order(
        self,
        order: Order,
        market_price: float,
        best_bid: float | None = None,
        best_ask: float | None = None,
    ) -> list[Trade]:
        """
        Execute order with probabilistic fill simulation.

        Args:
            order: Order to execute
            market_price: Current market price
            best_bid: Best bid price in order book (optional, for limit orders)
            best_ask: Best ask price in order book (optional, for limit orders)

        Returns:
            List of Trade objects (empty if cancelled/rejected)
        """
        # Determine execution outcome
        outcome = self._determine_outcome()

        if outcome == "CANCELLED":
            order.status = OrderStatus.CANCELLED
            return []

        # Determine fill quantity
        if outcome == "FULL_FILL":
            fill_qty = order.quantity
        else:  # PARTIAL_FILL
            # Partial fill: 50-90% of quantity
            fill_ratio = random.uniform(0.5, 0.9)
            fill_qty = order.quantity * fill_ratio

        # Determine fill price
        fill_price = self._determine_fill_price(order, market_price, best_bid, best_ask)

        # Create trade
        trade = Trade(
            trade_id=str(uuid.uuid4()),
            order_id=order.order_id,
            timestamp=datetime.now(),
            symbol=order.symbol,
            side=order.side,
            quantity=fill_qty,
            price=fill_price,
        )

        # Update order
        order.fill(fill_qty, fill_price)

        return [trade]

    def _determine_outcome(self) -> str:
        """
        Determine execution outcome based on probabilities.

        Returns:
            'FULL_FILL', 'PARTIAL_FILL', or 'CANCELLED'
        """
        rand = random.random()

        if rand < self.fill_probability:
            return "FULL_FILL"
        elif rand < self.fill_probability + self.partial_fill_probability:
            return "PARTIAL_FILL"
        else:
            return "CANCELLED"

    def _determine_fill_price(
        self,
        order: Order,
        market_price: float,
        best_bid: float | None,
        best_ask: float | None,
    ) -> float:
        """
        Determine realistic fill price based on order type and market conditions.

        Incorporates:
        - Bid-ask spread
        - Market impact slippage
        - Liquidity impact based on order size
        - Commission costs (added to effective price)
        - SEC fees for sales (added to effective cost)

        Logic:
        - Limit orders: Fill at limit price (if order would be marketable)
        - Market orders: Fill at best opposite side + spread + slippage + costs
        """
        if order.order_type == OrderType.LIMIT:
            # Limit orders fill at their limit price
            # Still apply commission as effective price adjustment
            fill_price = order.price
            commission = self._calculate_commission(order.quantity, fill_price)
            commission_per_share = (
                commission / order.quantity if order.quantity > 0 else 0
            )

            if order.side == OrderSide.BUY:
                return fill_price + commission_per_share
            else:
                # For sells, also add SEC fees
                sec_fee = self._calculate_sec_fee(order.quantity, fill_price)
                total_costs = commission + sec_fee
                return fill_price - (
                    total_costs / order.quantity if order.quantity > 0 else 0
                )

        # Market orders - incorporate all transaction costs
        # Calculate bid-ask spread if not provided
        if best_bid is None or best_ask is None:
            spread_bps = self.bid_ask_spread_bps
            spread = market_price * (spread_bps / 10000.0)  # Convert bps to decimal
            half_spread = spread / 2
            best_bid = market_price - half_spread
            best_ask = market_price + half_spread

        # Calculate liquidity impact based on order value
        order_value = order.quantity * market_price
        liquidity_impact = self._calculate_liquidity_impact(order_value)

        # Calculate commission and fees
        commission = self._calculate_commission(order.quantity, market_price)
        commission_per_share = commission / order.quantity if order.quantity > 0 else 0

        if order.side == OrderSide.BUY:
            # Buy: pay ask price + market impact + liquidity impact + commission
            base_slippage = random.uniform(0, self.market_impact)
            total_impact = base_slippage + liquidity_impact
            fill_price = best_ask * (1 + total_impact)
            return fill_price + commission_per_share
        else:  # SELL
            # Sell: receive bid price - market impact - liquidity impact - commission - SEC fees
            base_slippage = random.uniform(0, self.market_impact)
            total_impact = base_slippage + liquidity_impact
            fill_price = best_bid * (1 - total_impact)

            sec_fee = self._calculate_sec_fee(order.quantity, fill_price)
            total_costs = commission + sec_fee
            costs_per_share = total_costs / order.quantity if order.quantity > 0 else 0
            return fill_price - costs_per_share

    def _calculate_commission(self, quantity: float, price: float) -> float:
        """
        Calculate commission for a trade.

        Args:
            quantity: Number of shares
            price: Price per share

        Returns:
            Total commission in dollars
        """
        commission = quantity * self.commission_per_share
        return max(commission, self.commission_min)

    def _calculate_sec_fee(self, quantity: float, price: float) -> float:
        """
        Calculate SEC transaction fee (US equities only, on sales).

        SEC charges $27.80 per million dollars of sale proceeds.

        Args:
            quantity: Number of shares
            price: Price per share

        Returns:
            SEC fee in dollars
        """
        sale_value = quantity * price
        return sale_value * self.sec_fee_rate

    def _calculate_liquidity_impact(self, order_value: float) -> float:
        """
        Calculate additional slippage based on order size.

        Larger orders have more market impact and slippage.

        Args:
            order_value: Total value of order in dollars

        Returns:
            Additional slippage factor (e.g., 0.0001 = 0.01%)
        """
        # Liquidity impact scales with order size
        # Every $100k adds liquidity_impact_factor of slippage
        impact_units = order_value / 100000.0
        return impact_units * self.liquidity_impact_factor

    def set_probabilities(
        self,
        fill_prob: float | None = None,
        partial_prob: float | None = None,
        cancel_prob: float | None = None,
    ) -> None:
        """
        Update execution probabilities.

        Args:
            fill_prob: New fill probability
            partial_prob: New partial fill probability
            cancel_prob: New cancel probability

        Note: Probabilities must sum to 1.0
        """
        if fill_prob is not None:
            self.fill_probability = fill_prob
        if partial_prob is not None:
            self.partial_fill_probability = partial_prob
        if cancel_prob is not None:
            self.cancel_probability = cancel_prob

        total = (
            self.fill_probability
            + self.partial_fill_probability
            + self.cancel_probability
        )
        if not (0.99 <= total <= 1.01):
            raise ValueError(f"Probabilities must sum to 1.0, got {total}")

    def get_execution_stats(self) -> dict:
        """
        Get current execution probability and transaction cost settings.

        Returns:
            Dictionary with probability and cost settings
        """
        return {
            "fill_probability": self.fill_probability,
            "partial_fill_probability": self.partial_fill_probability,
            "cancel_probability": self.cancel_probability,
            "market_impact": self.market_impact,
            "commission_per_share": self.commission_per_share,
            "commission_min": self.commission_min,
            "bid_ask_spread_bps": self.bid_ask_spread_bps,
            "sec_fee_rate": self.sec_fee_rate,
            "liquidity_impact_factor": self.liquidity_impact_factor,
        }

    def __repr__(self) -> str:
        return (
            f"MatchingEngine(fill={self.fill_probability:.2f}, "
            f"partial={self.partial_fill_probability:.2f}, "
            f"cancel={self.cancel_probability:.2f})"
        )
