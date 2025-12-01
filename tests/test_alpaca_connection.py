"""
Tests for Alpaca API connection.

Requires valid API credentials in .env file.
"""

import pytest
import os
import time
import logging
from dotenv import load_dotenv

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

from AlpacaTrading.live.alpaca_trader import AlpacaConfig, AlpacaTrader

logger = logging.getLogger(__name__)


load_dotenv()


def has_alpaca_credentials() -> bool:
    """Check if Alpaca credentials are configured."""
    return bool(os.getenv("ALPACA_API_KEY") and os.getenv("ALPACA_SECRET_KEY"))


pytestmark = pytest.mark.skipif(
    not has_alpaca_credentials(), reason="Alpaca API credentials not configured"
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
            api_key=config.api_key, secret_key=config.secret_key, paper=config.paper
        )

    def test_btc_round_trip(self, trading_client: TradingClient):
        """
        Open and close a small BTC/USD position, report P&L.

        Uses minimum quantity (0.0001 BTC) to minimize risk.
        """
        symbol = "BTC/USD"
        qty = 0.001  # Minimum BTC quantity on Alpaca

        # Get initial account state
        account_before = trading_client.get_account()
        cash_before = float(account_before.cash)

        # Open position (BUY)
        buy_order = trading_client.submit_order(
            MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.GTC,
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
                time_in_force=TimeInForce.GTC,
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
        logger.info(f"\n{'=' * 50}")
        logger.info("BTC/USD Round Trip Results")
        logger.info(f"{'=' * 50}")
        logger.info(f"Quantity:    {qty} BTC")
        logger.info(f"Buy Price:   ${buy_price:,.2f}")
        logger.info(f"Sell Price:  ${sell_price:,.2f}")
        logger.info(f"P&L:         ${pnl:,.4f}")
        logger.info(f"Cash Before: ${cash_before:,.2f}")
        logger.info(f"Cash After:  ${cash_after:,.2f}")
        logger.info(f"{'=' * 50}")


class TestStrategyRoundTrip:
    """Test executing a strategy-driven round trip on Alpaca."""

    @pytest.fixture
    def trading_client(self) -> TradingClient:
        """Create trading client."""
        config = AlpacaConfig.from_env()
        return TradingClient(
            api_key=config.api_key, secret_key=config.secret_key, paper=config.paper
        )

    @pytest.fixture
    def trader(self) -> AlpacaTrader:
        """Create Alpaca trader instance."""
        config = AlpacaConfig.from_env()
        return AlpacaTrader(config)

    def test_momentum_strategy_round_trip(
        self,
        trading_client: TradingClient,
    ):
        """
        Execute a momentum strategy round trip: buy then sell.

        Uses a small position to minimize risk.
        Tests strategy order generation and live execution.
        """
        from AlpacaTrading.strategies.momentum import MomentumStrategy
        from AlpacaTrading.trading.portfolio import TradingPortfolio
        from AlpacaTrading.models import MarketDataPoint
        from AlpacaTrading.models import OrderSide as InternalOrderSide
        from datetime import datetime

        symbol = "BTC/USD"
        qty = 0.001  # Minimum BTC quantity on Alpaca

        # Get initial account state
        account_before = trading_client.get_account()
        cash_before = float(account_before.cash)

        # Create strategy with parameters that will trigger a buy signal
        # Low threshold ensures signal triggers easily
        strategy = MomentumStrategy(
            lookback_period=5,
            momentum_threshold=0.0001,  # Very low threshold
            position_size=500,
            max_position=10,
        )

        # Create portfolio tracker
        portfolio = TradingPortfolio(initial_cash=float(account_before.cash))

        # Simulate rising prices to trigger BUY signal
        base_price = 100.0
        for i in range(5):
            tick = MarketDataPoint(
                timestamp=datetime.now(),
                symbol=symbol,
                price=base_price * (1 + 0.001 * i),  # Rising prices
                volume=10000,
            )
            orders = strategy.on_market_data(tick, portfolio)

        # The last tick should generate a buy order
        assert len(orders) > 0, "Strategy should generate buy order on rising momentum"
        buy_order = orders[0]
        assert buy_order.side == InternalOrderSide.BUY

        # Execute buy on Alpaca using TradingClient directly (crypto requires GTC)
        logger.info(f"\nExecuting BUY order from strategy: {buy_order}")
        alpaca_buy = trading_client.submit_order(
            MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.GTC,
            )
        )

        # Wait for fill
        time.sleep(2)

        # Verify buy filled
        buy_filled = trading_client.get_order_by_id(alpaca_buy.id)
        assert buy_filled.status.value in ("filled", "partially_filled")
        buy_price = float(buy_filled.filled_avg_price)
        filled_qty = float(buy_filled.filled_qty)

        logger.info(f"BUY filled: {filled_qty} BTC @ ${buy_price:,.2f}")

        # Update portfolio with the trade
        portfolio.positions[symbol] = type("Position", (), {"quantity": filled_qty})()

        # Simulate falling prices to trigger SELL signal
        for i in range(5):
            tick = MarketDataPoint(
                timestamp=datetime.now(),
                symbol=symbol,
                price=base_price * (1 - 0.001 * i),  # Falling prices
                volume=10000,
            )
            orders = strategy.on_market_data(tick, portfolio)

        # Should generate sell order
        assert len(orders) > 0, (
            "Strategy should generate sell order on falling momentum"
        )
        sell_order = orders[0]
        assert sell_order.side == InternalOrderSide.SELL

        # Execute sell on Alpaca using TradingClient directly (crypto requires GTC)
        logger.info(f"Executing SELL order from strategy: {sell_order}")
        alpaca_sell = trading_client.submit_order(
            MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.GTC,
            )
        )

        # Wait for fill
        time.sleep(2)

        # Verify sell filled
        sell_filled = trading_client.get_order_by_id(alpaca_sell.id)
        assert sell_filled.status.value in ("filled", "partially_filled")
        sell_price = float(sell_filled.filled_avg_price)

        logger.info(f"SELL filled: {filled_qty} BTC @ ${sell_price:,.2f}")

        # Calculate P&L
        pnl = (sell_price - buy_price) * filled_qty

        # Get final account state
        account_after = trading_client.get_account()
        cash_after = float(account_after.cash)

        # Report results
        logger.info(f"\n{'=' * 50}")
        logger.info("Strategy Round Trip Results (MomentumStrategy)")
        logger.info(f"{'=' * 50}")
        logger.info(f"Symbol:      {symbol}")
        logger.info(f"Quantity:    {filled_qty} BTC")
        logger.info(f"Buy Price:   ${buy_price:,.2f}")
        logger.info(f"Sell Price:  ${sell_price:,.2f}")
        logger.info(f"P&L:         ${pnl:,.4f}")
        logger.info(f"Cash Before: ${cash_before:,.2f}")
        logger.info(f"Cash After:  ${cash_after:,.2f}")
        logger.info(f"{'=' * 50}")
