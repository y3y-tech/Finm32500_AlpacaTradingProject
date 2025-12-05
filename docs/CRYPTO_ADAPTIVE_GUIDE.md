# Crypto Adaptive Multi-Trader Guide

## Overview

The Crypto Adaptive Multi-Trader is a comprehensive trading system that runs **19+ different trading strategies** simultaneously on **8 major cryptocurrency pairs**, all through a single Alpaca WebSocket connection. This modernizes the original adaptive portfolio approach by using the multi-trader config framework for better scalability and management.

## Key Features

- **19 Trading Strategies**: Momentum, Mean Reversion, Volatility, Breakout, and more
- **8 Crypto Pairs**: BTC/USD, ETH/USD, SOL/USD, AVAX/USD, LINK/USD, MATIC/USD, DOT/USD, UNI/USD
- **Independent Risk Management**: Each strategy has its own capital allocation and risk limits
- **Shared Connection**: Bypasses Alpaca's 2-connection limit by sharing a single WebSocket
- **Real-time Performance**: Track performance across all strategies simultaneously

## Quick Start

### Paper Trading (Recommended for Testing)

```bash
# Using the shell script
./scripts/traders/run_crypto_adaptive.sh

# Or directly with Python
python scripts/traders/run_crypto_adaptive_multi.py
```

### Live Trading (Use with Caution!)

```bash
# Shell script
./scripts/traders/run_crypto_adaptive.sh --live

# Python
python scripts/traders/run_crypto_adaptive_multi.py --live
```

### Custom Configuration

```bash
python scripts/traders/run_crypto_adaptive_multi.py \
    --config configs/my_custom_crypto_config.json \
    --save-data \
    --data-file logs/my_crypto_data.csv
```

## Strategy Breakdown

The system includes 19 strategies across multiple categories:

### Momentum Strategies (3)
- **Crypto_Momentum_Fast**: 10-bar lookback, 0.8% threshold
- **Crypto_Momentum_Medium**: 15-bar lookback, 0.6% threshold
- **Crypto_Momentum_Slow**: 25-bar lookback, 0.4% threshold

### Mean Reversion Strategies (3)
- **Crypto_MA_Cross_Fast**: 5/15 moving average crossover
- **Crypto_MA_Cross_Medium**: 10/30 moving average crossover
- **Crypto_MA_Cross_Slow**: 20/60 moving average crossover

### RSI Strategies (2)
- **Crypto_RSI_Aggressive**: 25/75 thresholds, 2.5% profit target, 1.2% stop loss
- **Crypto_RSI_Conservative**: 30/70 thresholds, 1.8% profit target, 1.0% stop loss

### Trend Following (3)
- **Crypto_Donchian**: 20-period entry, 10-period exit
- **Crypto_MACD**: 12/26/9 MACD crossover
- **Crypto_ROC**: 12-bar rate of change with smoothing

### Volatility Strategies (3)
- **Crypto_BB_Breakout**: 20-period, 2.0 std dev breakout
- **Crypto_BB_Reversion**: 20-period, 2.5 std dev reversion
- **Crypto_Keltner**: 20-period EMA, 10-period ATR, 2.0x multiplier

### Advanced Reversion (2)
- **Crypto_ZScore**: 20-bar lookback, 2.0 entry threshold
- **Crypto_Multi_Indicator**: Combined RSI, Bollinger, and momentum

### Other Strategies (3)
- **Crypto_Stochastic**: 14/3 stochastic with crossover signals
- **Crypto_Volume_Breakout**: 2x volume spike with price confirmation
- **Crypto_VWAP**: 0.5% deviation from volume-weighted average price

## Configuration Structure

The configuration file (`configs/crypto_adaptive_multi_trader.json`) defines each strategy:

```json
{
  "strategies": [
    {
      "name": "Crypto_Momentum_Fast",
      "strategy_type": "momentum",
      "strategy_params": {
        "lookback_period": 10,
        "momentum_threshold": 0.008,
        "position_size": 800,
        "max_position": 8
      },
      "tickers": ["BTC/USD", "ETH/USD", "SOL/USD", ...],
      "initial_cash": 6000.0,
      "min_warmup_bars": 20,
      "risk_config": {
        "max_position_size": 0.15,
        "max_daily_trades": 20,
        "max_daily_loss": 500.0
      }
    },
    ...
  ]
}
```

### Configuration Parameters

#### Strategy Configuration
- `name`: Unique identifier for the strategy
- `strategy_type`: Type of strategy (see supported types below)
- `strategy_params`: Strategy-specific parameters
- `tickers`: List of crypto pairs to trade
- `initial_cash`: Starting capital for this strategy
- `min_warmup_bars`: Minimum bars before trading starts

#### Risk Configuration
- `max_position_size`: Maximum position as fraction of initial capital (0.15 = 15%)
- `max_daily_trades`: Maximum number of trades per day
- `max_daily_loss`: Maximum loss in dollars before stopping for the day
- `stop_loss_pct`: (Optional) Percentage-based stop loss
- `take_profit_pct`: (Optional) Percentage-based take profit

## Supported Strategy Types

The following strategy types can be used in the configuration:

| Strategy Type | Description |
|--------------|-------------|
| `momentum` | Momentum-based trend following |
| `mean_reversion` | Moving average crossover |
| `rsi` | RSI-based overbought/oversold |
| `bollinger_bands` | Bollinger Band breakout/reversion |
| `donchian_breakout` | Donchian channel breakout |
| `keltner_channel` | Keltner channel breakout |
| `macd` | MACD crossover signals |
| `rate_of_change` | Rate of change momentum |
| `stochastic` | Stochastic oscillator |
| `volume_breakout` | Volume-confirmed breakouts |
| `vwap` | VWAP deviation trading |
| `zscore_mean_reversion` | Z-score statistical reversion |
| `multi_indicator_reversion` | Multi-indicator combined signals |

## Capital Allocation

Default allocation per strategy:
- **Initial Cash**: $6,000 per strategy
- **Total Capital**: $114,000 (19 strategies × $6,000)
- **Position Size**: ~$800 per trade (configurable)
- **Max Position**: 15% of strategy capital

This allows each strategy to operate independently without interfering with others.

## Risk Management

Each strategy has independent risk controls:

1. **Position Limits**: Max 15% of capital per position
2. **Daily Trade Limits**: 12-20 trades per day depending on strategy
3. **Daily Loss Limits**: $500 max loss per strategy per day
4. **Warmup Period**: 20-65 bars depending on strategy requirements

## Performance Monitoring

When running, you'll see:

```
[Crypto_Momentum_Fast] 🟢 BUY 0.0125 BTC/USD @ $42,350.00 (Order ID: ...)
[Crypto_RSI_Aggressive] 🔴 SELL 0.0150 ETH/USD @ $2,240.50 (Order ID: ...)
[Crypto_BB_Breakout] ✓ Warmup complete - TRADING ACTIVE
```

On shutdown (Ctrl-C), you'll get a comprehensive summary:

```
================================================================================
MULTI-TRADER COORDINATOR SUMMARY
================================================================================

[Crypto_Momentum_Fast]
  Initial Cash: $6,000.00
  Available Cash: $5,450.00
  Total Value: $6,234.50
  PnL: $234.50 (+3.91%)
  Daily Trades: 12
  Active Positions: 3

[Crypto_RSI_Aggressive]
  Initial Cash: $6,000.00
  Available Cash: $5,820.00
  Total Value: $5,985.00
  PnL: -$15.00 (-0.25%)
  Daily Trades: 8
  Active Positions: 1

...

================================================================================
TOTAL PnL ACROSS ALL STRATEGIES: $1,234.50
================================================================================
```

## Customization

### Adding a New Strategy

1. Edit `configs/crypto_adaptive_multi_trader.json`
2. Add a new strategy configuration:

```json
{
  "name": "My_Custom_Strategy",
  "strategy_type": "momentum",
  "strategy_params": {
    "lookback_period": 20,
    "momentum_threshold": 0.01,
    "position_size": 800,
    "max_position": 8
  },
  "tickers": ["BTC/USD", "ETH/USD"],
  "initial_cash": 10000.0,
  "min_warmup_bars": 25,
  "risk_config": {
    "max_position_size": 0.2,
    "max_daily_trades": 15,
    "max_daily_loss": 800.0
  }
}
```

### Modifying Crypto Pairs

To trade different crypto pairs, update the `tickers` list:

```json
"tickers": ["BTC/USD", "ETH/USD", "ADA/USD", "XLM/USD"]
```

Note: Make sure the pairs are supported by Alpaca Crypto.

### Adjusting Risk Parameters

To make strategies more/less aggressive:

```json
"risk_config": {
  "max_position_size": 0.25,      // Increase position size
  "max_daily_trades": 30,         // Allow more trades
  "max_daily_loss": 1000.0        // Higher loss tolerance
}
```

## Architecture

```
run_crypto_adaptive_multi.py
    ├── Loads config from JSON
    ├── Creates strategy instances via factory
    └── Initializes MultiTraderCoordinator
            ├── Single Alpaca WebSocket connection
            ├── Routes bars to interested strategies
            ├── Executes trades independently per strategy
            └── Tracks performance separately
```

### Key Components

1. **Configuration File**: JSON file defining all strategies
2. **Strategy Factory**: Creates strategy instances from config
3. **Multi-Trader Coordinator**: Manages all strategies with shared connection
4. **Risk Manager**: Enforces limits per strategy independently

## Comparison with Original Adaptive Portfolio

| Feature | Original Adaptive Portfolio | New Crypto Adaptive Multi |
|---------|---------------------------|--------------------------|
| Architecture | Single LiveTrader instance | Multi-Trader Coordinator |
| Capital Allocation | Dynamic rebalancing | Fixed per strategy |
| Risk Management | Global | Per-strategy independent |
| Configuration | Code-based | JSON-based |
| Scalability | Limited by code changes | Easily scalable via config |
| Connection Sharing | No | Yes |
| Crypto Support | No (stocks only) | Yes (crypto-focused) |

## Tips and Best Practices

1. **Start with Paper Trading**: Always test with paper trading first
2. **Monitor Warmup**: Wait for all strategies to warm up before judging performance
3. **Check Daily Limits**: Ensure risk limits are appropriate for your capital
4. **Diversify Strategy Types**: Mix momentum, reversion, and volatility strategies
5. **Review Performance**: Check the summary after each session to identify winners
6. **Adjust Gradually**: Make small changes to configuration and observe results
7. **Watch for Correlations**: Some crypto pairs move together; consider this in allocation

## Troubleshooting

### Config File Not Found
```
Config file not found: configs/crypto_adaptive_multi_trader.json
```
**Solution**: Ensure the config file exists or provide the correct path with `--config`

### Unknown Strategy Type
```
ValueError: Unknown strategy type: my_strategy
```
**Solution**: Use a supported strategy type from the table above

### API Connection Issues
```
Error in coordinator: WebSocket connection failed
```
**Solution**: Check API credentials and network connection

### No Trades Executing
- Check that warmup period has completed
- Verify risk limits aren't too restrictive
- Ensure market is open for crypto trading (24/7)

## Future Enhancements

Potential improvements to consider:

1. **Dynamic Rebalancing**: Add adaptive capital allocation like original
2. **Performance Analytics**: Add detailed performance metrics per strategy
3. **ML Integration**: Use ML to predict which strategies will perform best
4. **Auto-tuning**: Automatically adjust parameters based on performance
5. **Multi-timeframe**: Support different timeframes per strategy
6. **Portfolio Constraints**: Add global portfolio-level risk management

## Related Documentation

- [Multi-Trader Guide](MULTI_TRADER_GUIDE.md) - General multi-trader framework
- [Adaptive Portfolio Guide](ADAPTIVE_PORTFOLIO_GUIDE.md) - Original adaptive approach
- [Setup Credentials](SETUP_CREDENTIALS.md) - API setup instructions

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the multi-trader coordinator logs
3. Verify your configuration file syntax
4. Test with a minimal configuration first

---

**Happy Trading!** Remember to always test thoroughly in paper trading before going live.
