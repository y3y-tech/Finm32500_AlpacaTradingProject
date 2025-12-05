# Multi-Trader Configuration Files

This directory contains JSON configuration files for running multiple trading strategies simultaneously using the `run_multi_trader.py` script. These configurations replicate the functionality of the individual trader scripts but with a unified approach that shares a single Alpaca WebSocket connection.

## Available Configurations

### Core Market Configs

#### `spy_multi_trader.json`
- **Focus**: SPY (S&P 500 ETF) concentrated trading
- **Strategies**: 5 strategies (2x Momentum, 2x Mean Reversion, 1x RSI)
- **Total Capital**: $25,000
- **Use Case**: High-liquidity, low-spread single-instrument trading
- **Risk Profile**: Moderate

#### `faang_multi_trader.json`
- **Focus**: Major tech stocks (META, AAPL, AMZN, NVDA, GOOGL, MSFT, TSLA)
- **Strategies**: 2 strategies (Momentum + Mean Reversion)
- **Total Capital**: $15,000
- **Use Case**: High-volatility tech stock trading
- **Risk Profile**: Higher volatility, growth-focused

#### `crypto_multi_trader.json`
- **Focus**: Top cryptocurrencies (BTC, ETH, SOL, AVAX, LINK)
- **Strategies**: 3 strategies (2x Momentum, 1x RSI)
- **Total Capital**: $15,000
- **Use Case**: 24/7 crypto market trading
- **Risk Profile**: High volatility, aggressive

#### `crypto_adaptive_multi_trader.json` ⭐ NEW
- **Focus**: 8 major crypto pairs (BTC, ETH, SOL, AVAX, LINK, MATIC, DOT, UNI)
- **Strategies**: 19 comprehensive strategies across all categories
- **Total Capital**: $114,000 (19 strategies × $6,000 each)
- **Use Case**: Advanced multi-strategy crypto trading with full coverage
- **Risk Profile**: Diversified across strategy types, moderate per-strategy risk
- **Special Features**:
  - Momentum (3), Mean Reversion (3), RSI (2), Trend Following (3)
  - Volatility (3), Advanced Reversion (2), Other (3)
  - Independent risk management per strategy
  - Comprehensive market coverage across all crypto pairs

### Sector & Theme Configs

#### `sector_multi_trader.json`
- **Focus**: All 11 sector ETFs (XLF, XLI, XLRE, XLB, XLC, XLE, XLK, XLP, XLV, XLU, XLY)
- **Strategies**: 2 strategies (Momentum + Mean Reversion)
- **Total Capital**: $10,000
- **Use Case**: Sector rotation trading
- **Risk Profile**: Diversified, moderate

#### `bonds_multi_trader.json`
- **Focus**: Treasury and corporate bonds (IEF, TLT, TLH, BND, LQD)
- **Strategies**: 2x Mean Reversion strategies (Fast + Slow)
- **Total Capital**: $15,000
- **Use Case**: Low-volatility fixed income trading
- **Risk Profile**: Conservative, income-focused

#### `commodities_multi_trader.json`
- **Focus**: Energy, metals, and agriculture commodities
- **Strategies**: 3 strategies targeting different commodity classes
- **Total Capital**: $10,000
- **Use Case**: Diversified commodity exposure
- **Risk Profile**: Moderate to high volatility

### International & Macro Configs

#### `global_multi_trader.json`
- **Focus**: Emerging and developed market ETFs
- **Strategies**: 2 strategies (EM Momentum + DM Mean Reversion)
- **Total Capital**: $10,000
- **Use Case**: International market exposure
- **Risk Profile**: Higher volatility (EM) + stable (DM)

#### `macro_multi_trader.json`
- **Focus**: Risk-on/risk-off assets and currencies
- **Strategies**: 3 strategies (Risk-On, Risk-Off, Currencies)
- **Total Capital**: $10,000
- **Use Case**: Macro regime trading
- **Risk Profile**: Diversified, defensive options

### Special Configs

#### `meme_multi_trader.json`
- **Focus**: High-volatility meme stocks (GME, AMC, PLTR, RIVN, LCID, SOFI, HOOD)
- **Strategies**: 2 aggressive strategies (Momentum + RSI)
- **Total Capital**: $5,000 (smaller for high risk)
- **Use Case**: Speculative high-volatility trading
- **Risk Profile**: Very high risk, small position sizes

#### `diversified_multi_trader.json`
- **Focus**: Cross-asset class diversification
- **Strategies**: 6 strategies across equities, crypto, bonds, commodities, and sectors
- **Total Capital**: $40,000
- **Use Case**: Comprehensive multi-asset portfolio
- **Risk Profile**: Balanced diversification

### Example Configs

#### `multi_trader_simple.json`
- **Focus**: Simple 3-strategy example (SPY, QQQ, BTC)
- **Total Capital**: $30,000
- **Use Case**: Learning and testing

#### `multi_trader_example.json`
- **Focus**: Comprehensive 10-strategy example across all asset classes
- **Total Capital**: $112,000
- **Use Case**: Full-featured demonstration

## Usage

### Basic Usage

```bash
# Run with specific config
python scripts/traders/run_multi_trader.py --config configs/spy_multi_trader.json

# Run with live trading (CAREFUL!)
python scripts/traders/run_multi_trader.py --config configs/crypto_multi_trader.json --live

# Save market data
python scripts/traders/run_multi_trader.py --config configs/sector_multi_trader.json --save-data --data-file logs/sector_data.csv
```

### Crypto Adaptive Multi-Trader (New!)

The crypto adaptive multi-trader has its own dedicated script with 19 strategies:

```bash
# Paper trading (recommended)
./scripts/traders/run_crypto_adaptive.sh

# Or with Python directly
python scripts/traders/run_crypto_adaptive_multi.py

# Live trading (use with caution!)
python scripts/traders/run_crypto_adaptive_multi.py --live

# Custom config
python scripts/traders/run_crypto_adaptive_multi.py --config configs/my_crypto_config.json
```

See [CRYPTO_ADAPTIVE_GUIDE.md](../docs/CRYPTO_ADAPTIVE_GUIDE.md) for complete documentation.

### Default Strategies (No Config)

If you don't provide a config file, the script uses default strategies:
```bash
# Uses default config with SPY, QQQ, IWM, Tech Basket, and Crypto
python scripts/traders/run_multi_trader.py
```

## Configuration File Format

Each JSON config file contains a list of strategy configurations:

```json
{
  "strategies": [
    {
      "name": "Strategy_Name",
      "strategy_type": "momentum|mean_reversion|rsi",
      "strategy_params": {
        // Strategy-specific parameters
      },
      "tickers": ["TICKER1", "TICKER2"],
      "initial_cash": 10000.0,
      "min_warmup_bars": 50,
      "risk_config": {
        "max_position_size": 0.9,
        "max_daily_trades": 10,
        "max_daily_loss": 500.0,
        "stop_loss_pct": 0.05,
        "take_profit_pct": 0.10
      }
    }
  ]
}
```

### Strategy Types and Parameters

#### `momentum`
```json
"strategy_params": {
  "lookback_period": 20,
  "momentum_threshold": 0.01,
  "position_size": 1000,
  "max_position": 20
}
```

#### `mean_reversion`
```json
"strategy_params": {
  "short_window": 10,
  "long_window": 30,
  "position_size": 1000,
  "max_position": 20
}
```

#### `rsi`
```json
"strategy_params": {
  "rsi_period": 14,
  "oversold_threshold": 30,
  "overbought_threshold": 70,
  "position_size": 1000,
  "max_position": 20,
  "profit_target": 1.5,
  "stop_loss": 0.8
}
```

#### `bollinger_bands`
```json
"strategy_params": {
  "period": 20,
  "num_std_dev": 2.0,
  "mode": "breakout",  // or "reversion"
  "position_size": 1000,
  "max_position": 20
}
```

#### `donchian_breakout`
```json
"strategy_params": {
  "entry_period": 20,
  "exit_period": 10,
  "position_size": 1000,
  "max_position": 20
}
```

#### `keltner_channel`
```json
"strategy_params": {
  "ema_period": 20,
  "atr_period": 10,
  "atr_multiplier": 2.0,
  "mode": "breakout",
  "position_size": 1000,
  "max_position": 20
}
```

#### `macd`
```json
"strategy_params": {
  "fast_period": 12,
  "slow_period": 26,
  "signal_period": 9,
  "signal_type": "crossover",
  "position_size": 1000,
  "max_position": 20
}
```

#### `rate_of_change`
```json
"strategy_params": {
  "lookback_period": 12,
  "entry_threshold": 1.0,
  "exit_threshold": 0.0,
  "position_size": 1000,
  "max_position": 20,
  "use_smoothing": true
}
```

#### `stochastic`
```json
"strategy_params": {
  "k_period": 14,
  "d_period": 3,
  "oversold_threshold": 20,
  "overbought_threshold": 80,
  "signal_type": "crossover",
  "position_size": 1000,
  "max_position": 20
}
```

#### `volume_breakout`
```json
"strategy_params": {
  "volume_period": 20,
  "volume_multiplier": 2.0,
  "hold_periods": 30,
  "position_size": 1000,
  "max_position": 20,
  "min_price_change": 0.008
}
```

#### `vwap`
```json
"strategy_params": {
  "deviation_threshold": 0.005,
  "reset_period": 0,
  "position_size": 1000,
  "max_position": 20,
  "min_samples": 20
}
```

#### `zscore_mean_reversion`
```json
"strategy_params": {
  "lookback_period": 20,
  "entry_threshold": 2.0,
  "exit_threshold": 0.5,
  "position_size": 1000,
  "max_position": 20,
  "enable_shorting": false
}
```

#### `multi_indicator_reversion`
```json
"strategy_params": {
  "lookback_period": 20,
  "rsi_period": 14,
  "entry_score": 60,
  "position_size": 1000,
  "max_position": 20
}
```

### Risk Configuration Parameters

- `max_position_size`: Maximum position size as fraction of initial cash (0.0 to 1.0)
- `max_daily_trades`: Maximum number of trades per day per strategy
- `max_daily_loss`: Maximum dollar loss per day before stopping trading
- `stop_loss_pct`: Optional stop loss percentage (e.g., 0.05 = 5%)
- `take_profit_pct`: Optional take profit percentage (e.g., 0.10 = 10%)

## Key Advantages of Multi-Trader Format

1. **Single WebSocket Connection**: Bypasses Alpaca's 2-connection limit for paper trading
2. **Shared Market Data**: All strategies receive the same data stream efficiently
3. **Centralized Risk Management**: Global position and risk tracking
4. **Easy Configuration**: JSON files are easier to modify than Python code
5. **Resource Efficient**: Lower memory and network usage vs running separate scripts
6. **Unified Logging**: All strategies log to the same output for easy monitoring

## Tips for Creating Custom Configs

1. **Start Small**: Begin with 2-3 strategies and scale up
2. **Diversify Assets**: Mix stocks, crypto, bonds, commodities for better risk-adjusted returns
3. **Balance Strategy Types**: Combine momentum (trend-following) with mean reversion (contrarian)
4. **Size Appropriately**: Allocate more capital to lower-volatility assets
5. **Set Warmup Bars**: Ensure enough data for strategy initialization
6. **Risk Management**: Always set `max_daily_loss` to protect capital
7. **Test First**: Run in paper trading mode before going live

## Environment Variables Required

```bash
export APCA_API_KEY_ID="your_api_key"
export APCA_API_SECRET_KEY="your_api_secret"
```

## Monitoring

All configs support data saving for post-analysis:
```bash
python scripts/traders/run_multi_trader.py \
  --config configs/diversified_multi_trader.json \
  --save-data \
  --data-file logs/diversified_trading_$(date +%Y%m%d).csv
```

## Performance Considerations

- **Too Many Strategies**: >10 strategies may cause performance degradation
- **Too Many Tickers**: >20 unique tickers may overwhelm the data stream
- **High-Frequency**: Lower `min_warmup_bars` = faster startup but potentially unstable
- **Memory Usage**: Each strategy maintains price history buffers

## Troubleshooting

**Import Errors**: Set PYTHONPATH before running:
```bash
export PYTHONPATH="/path/to/project/src:$PYTHONPATH"
```

**Configuration Errors**: Validate JSON syntax using `jq` or online validators

**Strategy Not Trading**: Check that `min_warmup_bars` threshold has been met

**Connection Issues**: Verify Alpaca API credentials and network connectivity
