import logging
import time
from datetime import datetime

import dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

from AlpacaTrading.live.alpaca_trader import AlpacaConfig
from AlpacaTrading.models import MarketDataPoint
from AlpacaTrading.models import OrderSide as InternalOrderSide
from AlpacaTrading.strategies.momentum import MomentumStrategy
from AlpacaTrading.trading.portfolio import TradingPortfolio

_ = dotenv.load_dotenv()
logger = logging.getLogger(__name__)

config = AlpacaConfig.from_env()
trading_client = TradingClient(
    api_key=config.api_key, secret_key=config.secret_key, paper=config.paper
)

symbol = "BTC/USD"
qty = 0.001

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
        symbol=symbol, qty=qty, side=OrderSide.BUY, time_in_force=TimeInForce.GTC
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
assert len(orders) > 0, "Strategy should generate sell order on falling momentum"
sell_order = orders[0]
assert sell_order.side == InternalOrderSide.SELL

# Execute sell on Alpaca using TradingClient directly (crypto requires GTC)
logger.info(f"Executing SELL order from strategy: {sell_order}")
alpaca_sell = trading_client.submit_order(
    MarketOrderRequest(
        symbol=symbol, qty=qty, side=OrderSide.SELL, time_in_force=TimeInForce.GTC
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
