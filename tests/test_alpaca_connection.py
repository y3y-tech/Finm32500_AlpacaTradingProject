"""
Tests for Alpaca API connection.

Requires valid API credentials in .env file.
"""

import pytest
import os
import time
from dotenv import load_dotenv

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

from AlpacaTrading.live.alpaca_trader import AlpacaConfig, AlpacaTrader


load_dotenv()


def has_alpaca_credentials() -> bool:
    """Check if Alpaca credentials are configured."""
    return bool(
        os.getenv("ALPACA_API_KEY") and
        os.getenv("ALPACA_SECRET_KEY")
    )


pytestmark = pytest.mark.skipif(
    not has_alpaca_credentials(),
    reason="Alpaca API credentials not configured"
)


@pytest.fixture
def trader() -> AlpacaTrader:
    """Create Alpaca trader instance."""
    config = AlpacaConfig.from_env()
    return AlpacaTrader(config)


class TestAlpacaConnection:
    """Tests for Alpaca API connection."""

    def test_config_from_env(self):
        """Test loading config from environment."""
        config = AlpacaConfig.from_env()
        assert config.api_key
        assert config.secret_key
        assert config.paper is True

    def test_get_account(self, trader: AlpacaTrader):
        """Test fetching account information."""
        account = trader.get_account()

        assert "cash" in account
        assert "buying_power" in account
        assert "equity" in account
        assert isinstance(account["cash"], float)
        assert account["buying_power"] >= 0

    def test_get_positions(self, trader: AlpacaTrader):
        """Test fetching positions."""
        positions = trader.get_positions()
        assert isinstance(positions, list)

    def test_get_open_orders(self, trader: AlpacaTrader):
        """Test fetching open orders."""
        orders = trader.get_open_orders()
        assert isinstance(orders, list)


class TestBTCRoundTrip:
    """Test opening and closing a BTC position."""

    @pytest.fixture
    def trading_client(self) -> TradingClient:
        """Create trading client for crypto."""
        config = AlpacaConfig.from_env()
        return TradingClient(
            api_key=config.api_key,
            secret_key=config.secret_key,
            paper=config.paper
        )

    def test_btc_round_trip(self, trading_client: TradingClient):
        """
        Open and close a small BTC/USD position, report P&L.

        Uses minimum quantity (0.0001 BTC) to minimize risk.
        """
        symbol = "BTC/USD"
        qty = 0.0001  # Minimum BTC quantity on Alpaca

        # Get initial account state
        account_before = trading_client.get_account()
        cash_before = float(account_before.cash)

        # Open position (BUY)
        buy_order = trading_client.submit_order(
            MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.GTC
            )
        )

        # Wait for fill
        time.sleep(2)

        # Get buy order details
        buy_filled = trading_client.get_order_by_id(buy_order.id)
        assert buy_filled.status.value in ("filled", "partially_filled")
        buy_price = float(buy_filled.filled_avg_price)

        # Close position (SELL)
        sell_order = trading_client.submit_order(
            MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.GTC
            )
        )

        # Wait for fill
        time.sleep(2)

        # Get sell order details
        sell_filled = trading_client.get_order_by_id(sell_order.id)
        assert sell_filled.status.value in ("filled", "partially_filled")
        sell_price = float(sell_filled.filled_avg_price)

        # Calculate P&L
        pnl = (sell_price - buy_price) * qty

        # Get final account state
        account_after = trading_client.get_account()
        cash_after = float(account_after.cash)

        # Report results
        print(f"\n{'='*50}")
        print(f"BTC/USD Round Trip Results")
        print(f"{'='*50}")
        print(f"Quantity:    {qty} BTC")
        print(f"Buy Price:   ${buy_price:,.2f}")
        print(f"Sell Price:  ${sell_price:,.2f}")
        print(f"P&L:         ${pnl:,.4f}")
        print(f"Cash Before: ${cash_before:,.2f}")
        print(f"Cash After:  ${cash_after:,.2f}")
        print(f"{'='*50}")
