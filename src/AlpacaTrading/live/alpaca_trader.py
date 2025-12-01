"""
Alpaca Live Trading Integration.

Provides real-time market data streaming and order execution via Alpaca API.
"""

import logging
import os
from dataclasses import dataclass
from typing import Any, Callable

from alpaca.data.enums import DataFeed  # Import DataFeed enum
from alpaca.data.live import StockDataStream
from alpaca.data.models import Bar, Quote, Trade
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import (
    OrderSide as AlpacaOrderSide,
)
from alpaca.trading.enums import (
    QueryOrderStatus,
    TimeInForce,
)
from alpaca.trading.requests import (
    GetOrdersRequest,
    LimitOrderRequest,
    MarketOrderRequest,
)
from dotenv import load_dotenv

from AlpacaTrading.models import (
    MarketDataPoint,
    Order,
    OrderSide,
    OrderType,
)

logger = logging.getLogger(__name__)


@dataclass
class AlpacaConfig:
    """
    Configuration for Alpaca API connection.

    Attributes:
        api_key: Alpaca API key
        secret_key: Alpaca secret key
        paper: Use paper trading (default: True)
        feed: Data feed (default: "iex" for paper trading)
    """

    api_key: str
    secret_key: str
    paper: bool = True
    feed: DataFeed = DataFeed.IEX

    @classmethod
    def from_env(cls) -> "AlpacaConfig":
        """
        Load configuration from environment variables.

        Expects .env file with:
        - APCA_API_KEY_ID
        - APCA_API_SECRET_KEY
        - ALPACA_PAPER (optional, default: true)

        Returns:
            AlpacaConfig instance
        """
        load_dotenv()

        api_key = os.getenv("APCA_API_KEY_ID")
        secret_key = os.getenv("APCA_API_SECRET_KEY")
        paper = os.getenv("ALPACA_PAPER", "true").lower() == "true"

        if not api_key or not secret_key:
            raise ValueError(
                "Missing Alpaca credentials. "
                "Set APCA_API_KEY_ID and APCA_API_SECRET_KEY in .env file"
            )

        return cls(api_key=api_key, secret_key=secret_key, paper=paper)


class AlpacaTrader:
    """
    Alpaca live trading integration.

    Features:
    - Real-time market data streaming via WebSocket
    - Order submission and management
    - Position and account tracking
    - Automatic reconnection on errors

    Example:
        config = AlpacaConfig.from_env()
        trader = AlpacaTrader(config)

        # Set up market data callback
        def on_data(tick: MarketDataPoint):
            print(f"Received: {tick}")

        # Start streaming
        trader.start_streaming(symbols=["AAPL", "MSFT"], callback=on_data)

        # Submit order
        order = Order(symbol="AAPL", side=OrderSide.BUY, quantity=10, ...)
        alpaca_order = trader.submit_order(order)
    """

    def __init__(self, config: AlpacaConfig):
        """
        Initialize Alpaca trader.

        Args:
            config: Alpaca configuration
        """
        self.config = config

        logger.debug("Initializing trading client")
        self.trading_client = TradingClient(
            api_key=config.api_key, secret_key=config.secret_key, paper=config.paper
        )

        logger.debug("Initialize data stream")
        self.data_stream = StockDataStream(
            api_key=config.api_key, secret_key=config.secret_key, feed=config.feed
        )

        # Track streaming state
        self.is_streaming = False
        self.subscribed_symbols: set[str] = set()
        self.data_callback: Callable[[MarketDataPoint], None] | None = None

    def get_account(self) -> dict[str, Any]:
        """
        Get account information.

        Returns:
            Dictionary with account details (cash, equity, buying_power, etc.)
        """
        account = self.trading_client.get_account()
        return {
            "cash": float(account.cash),
            "portfolio_value": float(account.portfolio_value),
            "buying_power": float(account.buying_power),
            "equity": float(account.equity),
            "last_equity": float(account.last_equity),
            "initial_margin": float(account.initial_margin),
            "maintenance_margin": float(account.maintenance_margin),
            "daytrade_count": account.daytrade_count,
            "pattern_day_trader": account.pattern_day_trader,
        }

    def get_positions(self) -> list[dict]:
        """
        Get all open positions.

        Returns:
            List of position dictionaries
        """
        positions = self.trading_client.get_all_positions()
        return [
            {
                "symbol": pos.symbol,
                "quantity": float(pos.qty),
                "avg_entry_price": float(pos.avg_entry_price),
                "current_price": float(pos.current_price),
                "market_value": float(pos.market_value),
                "unrealized_pl": float(pos.unrealized_pl),
                "unrealized_plpc": float(pos.unrealized_plpc),
                "side": "long" if float(pos.qty) > 0 else "short",
            }
            for pos in positions
        ]

    def submit_order(self, order: Order) -> dict:
        """
        Submit order to Alpaca.

        Args:
            order: Order to submit

        Returns:
            Dictionary with Alpaca order details

        Raises:
            Exception: If order submission fails
        """
        # Convert OrderSide to AlpacaOrderSide
        side = (
            AlpacaOrderSide.BUY if order.side == OrderSide.BUY else AlpacaOrderSide.SELL
        )

        # Create order request based on type
        if order.order_type == OrderType.MARKET:
            order_request = MarketOrderRequest(
                symbol=order.symbol,
                qty=order.quantity,
                side=side,
                time_in_force=TimeInForce.DAY,
            )
        elif order.order_type == OrderType.LIMIT:
            if order.price is None:
                raise ValueError("Limit order requires price")

            order_request = LimitOrderRequest(
                symbol=order.symbol,
                qty=order.quantity,
                side=side,
                time_in_force=TimeInForce.DAY,
                limit_price=order.price,
            )
        else:
            raise ValueError(f"Unsupported order type: {order.order_type}")

        # Submit order
        alpaca_order = self.trading_client.submit_order(order_request)

        # Update our order with Alpaca's order ID
        order.order_id = alpaca_order.id

        return {
            "id": alpaca_order.id,
            "client_order_id": alpaca_order.client_order_id,
            "status": alpaca_order.status.value,
            "symbol": alpaca_order.symbol,
            "qty": float(alpaca_order.qty),
            "filled_qty": float(alpaca_order.filled_qty or 0),
            "side": alpaca_order.side.value,
            "order_type": alpaca_order.order_type.value,
            "limit_price": float(alpaca_order.limit_price)
            if alpaca_order.limit_price
            else None,
            "submitted_at": alpaca_order.submitted_at,
        }

    def get_order(self, order_id: str) -> dict:
        """
        Get order status by ID.

        Args:
            order_id: Alpaca order ID

        Returns:
            Dictionary with order details
        """
        alpaca_order = self.trading_client.get_order_by_id(order_id)

        return {
            "id": alpaca_order.id,
            "status": alpaca_order.status.value,
            "symbol": alpaca_order.symbol,
            "qty": float(alpaca_order.qty),
            "filled_qty": float(alpaca_order.filled_qty or 0),
            "filled_avg_price": float(alpaca_order.filled_avg_price)
            if alpaca_order.filled_avg_price
            else None,
            "side": alpaca_order.side.value,
            "order_type": alpaca_order.order_type.value,
            "submitted_at": alpaca_order.submitted_at,
            "filled_at": alpaca_order.filled_at,
        }

    def cancel_order(self, order_id: str) -> None:
        """
        Cancel order by ID.

        Args:
            order_id: Alpaca order ID
        """
        self.trading_client.cancel_order_by_id(order_id)

    def cancel_all_orders(self) -> list[dict]:
        """
        Cancel all open orders.

        Returns:
            List of cancellation responses
        """
        responses = self.trading_client.cancel_orders()
        return [{"id": resp.id, "status": resp.status} for resp in responses]

    def get_open_orders(self, symbol: str | None = None) -> list[dict]:
        """
        Get all open orders.

        Args:
            symbol: Optional symbol filter

        Returns:
            List of order dictionaries
        """
        filter_params = GetOrdersRequest(
            status=QueryOrderStatus.OPEN, symbols=[symbol] if symbol else None
        )

        orders = self.trading_client.get_orders(filter=filter_params)

        return [
            {
                "id": order.id,
                "symbol": order.symbol,
                "qty": float(order.qty),
                "filled_qty": float(order.filled_qty or 0),
                "side": order.side.value,
                "order_type": order.order_type.value,
                "limit_price": float(order.limit_price) if order.limit_price else None,
                "status": order.status.value,
                "submitted_at": order.submitted_at,
            }
            for order in orders
        ]

    async def _handle_trade(self, trade: Trade):
        """
        Handle incoming trade data.

        Args:
            trade: Trade data from Alpaca
        """
        if self.data_callback is None:
            return

        # Convert to MarketDataPoint
        tick = MarketDataPoint(
            timestamp=trade.timestamp,
            symbol=trade.symbol,
            price=float(trade.price),
            volume=float(trade.size),
        )

        # Call user callback
        self.data_callback(tick)

    async def _handle_quote(self, quote: Quote):
        """
        Handle incoming quote data.

        Args:
            quote: Quote data from Alpaca
        """
        if self.data_callback is None:
            return

        # Use mid-price for quotes
        mid_price = (float(quote.bid_price) + float(quote.ask_price)) / 2

        tick = MarketDataPoint(
            timestamp=quote.timestamp,
            symbol=quote.symbol,
            price=mid_price,
            volume=0,  # Quotes don't have volume
        )

        self.data_callback(tick)

    async def _handle_bar(self, bar: Bar):
        """
        Handle incoming bar data.

        Args:
            bar: Bar data from Alpaca
        """
        if self.data_callback is None:
            return

        # Use close price for bars
        tick = MarketDataPoint(
            timestamp=bar.timestamp,
            symbol=bar.symbol,
            price=float(bar.close),
            volume=float(bar.volume),
        )

        self.data_callback(tick)

    def start_streaming(
        self,
        symbols: list[str],
        callback: Callable[[MarketDataPoint], None],
        data_type: str = "trades",
    ) -> None:
        """
        Start streaming market data for symbols.

        Args:
            symbols: List of symbols to stream
            callback: Function to call with each data point
            data_type: Type of data ("trades", "quotes", or "bars")

        Note: This is a blocking call. Run in separate thread for async usage.
        """
        self.data_callback = callback
        self.subscribed_symbols = set(symbols)

        # Subscribe to appropriate data type
        if data_type == "trades":
            self.data_stream.subscribe_trades(self._handle_trade, *symbols)
        elif data_type == "quotes":
            self.data_stream.subscribe_quotes(self._handle_quote, *symbols)
        elif data_type == "bars":
            self.data_stream.subscribe_bars(self._handle_bar, *symbols)
        else:
            raise ValueError(f"Invalid data_type: {data_type}")

        # Start streaming
        self.is_streaming = True
        self.data_stream.run()

    def stop_streaming(self) -> None:
        """Stop streaming market data."""
        if self.is_streaming:
            self.data_stream.stop()
            self.is_streaming = False

    def close_all_positions(self, cancel_orders: bool = True) -> list[dict]:
        """
        Close all positions.

        Args:
            cancel_orders: Whether to cancel open orders first

        Returns:
            List of close position responses
        """
        responses = self.trading_client.close_all_positions(cancel_orders=cancel_orders)
        return [{"symbol": resp.symbol, "status": resp.status} for resp in responses]

    def __repr__(self) -> str:
        mode = "PAPER" if self.config.paper else "LIVE"
        streaming = "STREAMING" if self.is_streaming else "IDLE"
        return f"AlpacaTrader(mode={mode}, status={streaming}, symbols={len(self.subscribed_symbols)})"
