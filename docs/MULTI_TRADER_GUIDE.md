# Multi-Trader Coordinator Guide

## Overview

The **MultiTraderCoordinator** allows you to run multiple trading strategies simultaneously while sharing a single Alpaca API connection. This bypasses Alpaca's limit of 2 concurrent WebSocket connections for paper trading accounts.

## The Problem

Alpaca's paper trading API limits you to **2 concurrent WebSocket connections**. Since each trader script (`LiveTrader`) creates its own connection, you can only run 2 traders at once:
- 1 connection for stocks (StockDataStream)
- 1 connection for crypto (CryptoDataStream)

With 26+ trader scripts in this project, this becomes a severe bottleneck.

## The Solution

The MultiTraderCoordinator:
- Creates **ONE** shared Alpaca connection
- Subscribes to all tickers from all strategies
- Routes incoming market data to relevant strategies
- Maintains independent state for each strategy (capital, positions, buffers)
- Allows running **unlimited strategies** simultaneously

## Architecture

```
                        ┌─────────────────────────┐
                        │ Alpaca API (1 connection)│
                        └──────────┬──────────────┘
                                   │
                        ┌──────────▼──────────────┐
                        │ MultiTraderCoordinator  │
                        │  - Stock Stream         │
                        │  - Crypto Stream        │
                        │  - Ticker Router        │
                        └──────────┬──────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         │                         │                         │
    ┌────▼────┐              ┌─────▼────┐             ┌─────▼────┐
    │Strategy1│              │Strategy2 │             │Strategy3 │
    │ SPY     │              │ QQQ      │             │ BTC/USD  │
    │ $10k    │              │ $10k     │             │ $10k     │
    └─────────┘              └──────────┘             └──────────┘
```

Each strategy maintains:
- Independent capital allocation
- Own positions and buffers
- Separate risk limits
- Individual warmup state
- Isolated P&L tracking

## Quick Start

### 1. Basic Usage (Default Strategies)

Run with built-in example strategies:

```bash
python scripts/traders/run_multi_trader.py
```

This runs 5 default strategies:
- SPY (Adaptive)
- QQQ (Momentum)
- IWM (RSI)
- Tech Basket (AAPL, MSFT, GOOGL, AMZN)
- BTC/USD (Crypto)

### 2. Using a Configuration File

Create a custom configuration and run:

```bash
python scripts/traders/run_multi_trader.py --config configs/multi_trader_example.json
```

Or use the simple 3-strategy example:

```bash
python scripts/traders/run_multi_trader.py --config configs/multi_trader_simple.json
```

### 3. Live Trading

**WARNING:** Only use after thorough paper trading testing!

```bash
python scripts/traders/run_multi_trader.py --config configs/my_config.json --live
```

## Configuration Format

Create a JSON file in `configs/` directory:

```json
{
  "strategies": [
    {
      "name": "SPY_Adaptive",
      "strategy_type": "adaptive",
      "strategy_params": {
        "short_window": 10,
        "long_window": 30,
        "rsi_period": 14
      },
      "tickers": ["SPY"],
      "initial_cash": 10000.0,
      "min_warmup_bars": 50,
      "risk_config": {
        "max_position_size": 0.95,
        "max_daily_trades": 10,
        "max_daily_loss": 500.0
      }
    },
    {
      "name": "Crypto_Portfolio",
      "strategy_type": "momentum",
      "strategy_params": {
        "lookback_period": 20
      },
      "tickers": ["BTC/USD", "ETH/USD"],
      "initial_cash": 15000.0,
      "min_warmup_bars": 60,
      "risk_config": {
        "max_position_size": 0.4,
        "max_daily_trades": 8
      }
    }
  ]
}
```

### Configuration Fields

**Strategy Block:**
- `name` (string, required): Unique identifier for the strategy
- `strategy_type` (string, required): One of: `adaptive`, `momentum`, `mean_reversion`, `rsi`
- `strategy_params` (object, optional): Parameters specific to the strategy type
- `tickers` (array, required): List of tickers to trade
- `initial_cash` (float, optional): Starting capital (default: 10000.0)
- `min_warmup_bars` (int, optional): Bars needed before trading starts (default: 50)
- `risk_config` (object, optional): Risk management settings

**Risk Config:**
- `max_position_size` (float): Maximum position as % of capital (0.0-1.0)
- `max_daily_trades` (int): Maximum trades per day
- `max_daily_loss` (float): Maximum loss in dollars before stopping
- `stop_loss_pct` (float): Stop loss percentage (not yet implemented)
- `take_profit_pct` (float): Take profit percentage (not yet implemented)

### Available Strategy Types

1. **adaptive**: Combines multiple signals (moving averages, RSI, volume)
   ```json
   "strategy_params": {
     "short_window": 10,
     "long_window": 30,
     "rsi_period": 14,
     "rsi_overbought": 70,
     "rsi_oversold": 30
   }
   ```

2. **momentum**: Trades based on price momentum
   ```json
   "strategy_params": {
     "lookback_period": 20,
     "momentum_threshold": 0.02
   }
   ```

3. **mean_reversion**: Trades when price deviates from mean
   ```json
   "strategy_params": {
     "lookback_period": 20,
     "entry_threshold": 2.0,
     "exit_threshold": 0.5
   }
   ```

4. **rsi**: Trades based on RSI overbought/oversold
   ```json
   "strategy_params": {
     "rsi_period": 14,
     "rsi_overbought": 70,
     "rsi_oversold": 30
   }
   ```

## Example Configurations

### Example 1: Market ETF Portfolio

Run SPY, QQQ, and IWM with different strategies:

```json
{
  "strategies": [
    {
      "name": "SPY_Adaptive",
      "strategy_type": "adaptive",
      "tickers": ["SPY"],
      "initial_cash": 10000.0
    },
    {
      "name": "QQQ_Momentum",
      "strategy_type": "momentum",
      "tickers": ["QQQ"],
      "initial_cash": 10000.0
    },
    {
      "name": "IWM_MeanRev",
      "strategy_type": "mean_reversion",
      "tickers": ["IWM"],
      "initial_cash": 10000.0
    }
  ]
}
```

### Example 2: Sector Rotation

Trade different sectors with one coordinator:

```json
{
  "strategies": [
    {
      "name": "Tech",
      "strategy_type": "adaptive",
      "tickers": ["XLK"],
      "initial_cash": 10000.0
    },
    {
      "name": "Energy",
      "strategy_type": "momentum",
      "tickers": ["XLE"],
      "initial_cash": 10000.0
    },
    {
      "name": "Finance",
      "strategy_type": "rsi",
      "tickers": ["XLF"],
      "initial_cash": 10000.0
    }
  ]
}
```

### Example 3: Multi-Asset Portfolio

Combine stocks, crypto, and bonds:

```json
{
  "strategies": [
    {
      "name": "Equities",
      "strategy_type": "adaptive",
      "tickers": ["SPY", "QQQ"],
      "initial_cash": 20000.0
    },
    {
      "name": "Crypto",
      "strategy_type": "momentum",
      "tickers": ["BTC/USD", "ETH/USD"],
      "initial_cash": 10000.0
    },
    {
      "name": "Bonds",
      "strategy_type": "mean_reversion",
      "tickers": ["TLT", "IEF"],
      "initial_cash": 15000.0
    }
  ]
}
```

## Monitoring

The coordinator provides detailed logging:

```
2025-12-04 14:30:15 [INFO] ================================================================================
2025-12-04 14:30:15 [INFO] Starting MultiTraderCoordinator
2025-12-04 14:30:15 [INFO] Paper Trading: True
2025-12-04 14:30:15 [INFO] Strategies: 5
2025-12-04 14:30:15 [INFO] ================================================================================
2025-12-04 14:30:15 [INFO]   [SPY_Adaptive]
2025-12-04 14:30:15 [INFO]     Tickers: SPY
2025-12-04 14:30:15 [INFO]     Initial Cash: $10,000.00
2025-12-04 14:30:15 [INFO]     Warmup Bars: 50
2025-12-04 14:30:15 [INFO]     Asset Type: Stock
...
2025-12-04 14:32:45 [INFO] [SPY_Adaptive] ✓ Warmup complete - TRADING ACTIVE
2025-12-04 14:33:12 [INFO] [SPY_Adaptive] 🟢 BUY 23.5000 SPY @ $450.23 (Order ID: xxx)
2025-12-04 14:45:30 [INFO] [QQQ_Momentum] ✓ Warmup complete - TRADING ACTIVE
2025-12-04 14:46:15 [INFO] [QQQ_Momentum] 🟢 BUY 31.2000 QQQ @ $385.67 (Order ID: xxx)
```

On shutdown (Ctrl+C), you'll see a summary:

```
================================================================================
MULTI-TRADER COORDINATOR SUMMARY
================================================================================

[SPY_Adaptive]
  Initial Cash: $10,000.00
  Available Cash: $8,500.00
  Total Value: $10,250.00
  PnL: $250.00 (+2.50%)
  Daily Trades: 3
  Active Positions: 1

[QQQ_Momentum]
  Initial Cash: $10,000.00
  Available Cash: $9,200.00
  Total Value: $9,950.00
  PnL: -$50.00 (-0.50%)
  Daily Trades: 2
  Active Positions: 0

================================================================================
TOTAL PnL ACROSS ALL STRATEGIES: $200.00
================================================================================
```

## Advantages

1. **Bypass Connection Limits**: Run unlimited strategies with 1 connection
2. **Efficient Resource Usage**: Single WebSocket for all market data
3. **Independent Strategies**: Each maintains own capital, positions, risk
4. **Centralized Monitoring**: All strategies visible in one process
5. **Easy Configuration**: JSON files for strategy management
6. **Flexible Deployment**: Mix stocks and crypto in one coordinator

## Disadvantages & Considerations

1. **Single Point of Failure**: If coordinator crashes, all strategies stop
2. **Memory Usage**: All strategies run in one process
3. **Shared Connection**: Network issues affect all strategies
4. **Debugging Complexity**: Multiple strategies in one log stream

## Tips & Best Practices

1. **Start Small**: Test with 2-3 strategies before scaling up
2. **Capital Allocation**: Ensure total capital doesn't exceed account size
3. **Risk Limits**: Set conservative `max_daily_loss` for each strategy
4. **Warmup Bars**: Use sufficient warmup (50+ bars recommended)
5. **Monitor Logs**: Watch for connection issues or API errors
6. **Paper Test First**: Always test configurations in paper mode
7. **Ticker Overlap**: Multiple strategies can trade the same ticker independently

## Migrating from Individual Traders

If you have existing individual trader scripts, you can easily convert them:

**Old way (individual scripts):**
```bash
tmux new -s spy_trader "python scripts/traders/live_spy_trader.py"
tmux new -s qqq_trader "python scripts/traders/live_qqq_trader.py"
tmux new -s btc_trader "python scripts/traders/live_btc_trader.py"
```

**New way (multi-trader coordinator):**
```bash
# Create config/my_traders.json with all strategies
python scripts/traders/run_multi_trader.py --config configs/my_traders.json
```

## Troubleshooting

**Problem**: "Missing Alpaca API credentials"
- **Solution**: Set environment variables:
  ```bash
  export APCA_API_KEY_ID="your_key"
  export APCA_API_SECRET_KEY="your_secret"
  ```

**Problem**: Strategies not trading after warmup
- **Solution**: Check that `min_warmup_bars` is appropriate for your data frequency and that markets are open

**Problem**: "Connection refused" or WebSocket errors
- **Solution**: Check internet connection, verify API credentials, ensure Alpaca services are operational

**Problem**: High memory usage
- **Solution**: Reduce number of strategies, lower buffer sizes, or run multiple coordinators

**Problem**: Mixed crypto/stock strategies not working
- **Solution**: Coordinator handles both automatically. Ensure tickers use correct format ("BTC/USD" for crypto, "SPY" for stocks)

## Advanced Usage

### Running Multiple Coordinators

If you want process isolation, run multiple coordinators:

```bash
# Terminal 1: Stocks coordinator
python scripts/traders/run_multi_trader.py --config configs/stocks_only.json

# Terminal 2: Crypto coordinator
python scripts/traders/run_multi_trader.py --config configs/crypto_only.json
```

This gives you 2 connections (1 for stocks, 1 for crypto) but with process isolation.

### Programmatic Usage

You can also use the coordinator in your own scripts:

```python
from src.AlpacaTrading.trading.multi_trader_coordinator import (
    MultiTraderCoordinator,
    RiskConfig,
)
from src.AlpacaTrading.strategies.adaptive_strategy import AdaptiveStrategy

strategies = [
    {
        "name": "MyStrategy",
        "strategy": AdaptiveStrategy(short_window=10, long_window=30),
        "tickers": ["SPY"],
        "initial_cash": 10000.0,
        "min_warmup_bars": 50,
        "risk_config": RiskConfig(max_position_size=0.9),
    }
]

coordinator = MultiTraderCoordinator(
    strategies=strategies,
    api_key="your_key",
    api_secret="your_secret",
    paper=True,
)

await coordinator.run()
```

## Support & Contributing

For issues or questions:
1. Check this guide first
2. Review logs for error messages
3. Test with simple configurations
4. Consult existing trader scripts for examples

## Related Files

- `src/AlpacaTrading/trading/multi_trader_coordinator.py`: Main coordinator class
- `scripts/traders/run_multi_trader.py`: Launcher script
- `configs/multi_trader_example.json`: Full example with 10 strategies
- `configs/multi_trader_simple.json`: Simple 3-strategy example
- `src/AlpacaTrading/trading/live_trader.py`: Original single-trader implementation
