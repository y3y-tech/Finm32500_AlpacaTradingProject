# Live Trading Scripts

This directory contains live trading scripts that connect to Alpaca's streaming API for real-time algorithmic trading.

## Available Traders

### 1. Crypto Trader (24/7 Trading)
- **Script**: `live_adaptive_crypto_trader.py`
- **Launcher**: `run_crypto_trader.sh`
- **Assets**: 10 most liquid cryptocurrencies
  - BTC/USD, ETH/USD, SOL/USD, XRP/USD, ADA/USD
  - AVAX/USD, DOGE/USD, MATIC/USD, DOT/USD, LTC/USD
- **Advantage**: Works 24/7 since crypto markets never close

### 2. Sector ETF Trader (Market Hours Only)
- **Script**: `live_adaptive_sector_trader.py`
- **Launcher**: `run_sector_trader.sh`
- **Assets**: 11 SPDR Sector ETFs
  - XLF (Financial), XLI (Industrial), XLRE (Real Estate)
  - XLB (Materials), XLC (Communication), XLE (Energy)
  - XLK (Technology), XLP (Consumer Staples), XLV (Health Care)
  - XLU (Utilities), XLY (Consumer Discretionary)
- **Limitation**: Only works during market hours (9:30 AM - 4:00 PM ET, Mon-Fri)

## Quick Start

### Using the Launcher Scripts (Recommended)

**Start Crypto Trader:**
```bash
# From project root
./scripts/traders/run_crypto_trader.sh
```

**Start Sector Trader:**
```bash
# From project root
./scripts/traders/run_sector_trader.sh
```

The launcher scripts will:
- Create a dedicated tmux session
- Activate the virtual environment
- Start the trader with optimal settings
- Enable data saving by default
- Provide helpful instructions

### Manual Execution

**Crypto Trader:**
```bash
python scripts/traders/live_adaptive_crypto_trader.py --min-warmup-bars 20 --save-data
```

**Sector Trader:**
```bash
python scripts/traders/live_adaptive_sector_trader.py --min-warmup-bars 30 --save-data
```

## Common Options

Both traders support the same command-line arguments:

```bash
--min-warmup-bars N       # Bars to collect before trading (default: 30 for sector, 20 for crypto)
--save-data               # Save streaming data to CSV
--rebalance-period N      # Bars between strategy rebalancing (default: 60)
--allocation-method METHOD # pnl, sharpe, or win_rate (default: pnl)
--initial-cash AMOUNT     # Starting capital (default: 10000)
--log-level LEVEL         # DEBUG, INFO, or WARNING (default: INFO)
--live                    # Use LIVE trading (⚠️  REAL MONEY! Default: paper)
```

## Examples

**Quick test with short warmup:**
```bash
./scripts/traders/run_crypto_trader.sh --min-warmup-bars 5
```

**Use Sharpe ratio for allocation:**
```bash
./scripts/traders/run_crypto_trader.sh --allocation-method sharpe
```

**Rebalance more frequently (every 30 bars):**
```bash
./scripts/traders/run_crypto_trader.sh --rebalance-period 30
```

## Monitoring

### Attach to Running Session

```bash
# Crypto trader
tmux attach -t crypto_trader

# Sector trader
tmux attach -t sector_trader
```

### Detach from Session
While attached to a tmux session, press: **Ctrl+b** then **d**

### View Logs

```bash
# Crypto trader
tail -f logs/live_adaptive_crypto_trader.log

# Sector trader
tail -f logs/live_adaptive_trader.log
```

### View Data

```bash
# Crypto data
head logs/live_crypto_data.csv

# Sector data (dated files)
ls -lh logs/live_session_*.csv
```

## Stopping the Traders

### Gracefully Stop (Saves Data)

1. Attach to session: `tmux attach -t crypto_trader`
2. Press **Ctrl+C**
3. Wait for graceful shutdown and data saving
4. Session will close automatically

### Force Kill Session

```bash
# Crypto trader
tmux kill-session -t crypto_trader

# Sector trader
tmux kill-session -t sector_trader
```

## Tmux Cheat Sheet

```bash
# List all sessions
tmux ls

# Attach to a session
tmux attach -t <session_name>

# Detach from current session
Ctrl+b then d

# Kill a session
tmux kill-session -t <session_name>

# Kill all sessions
tmux kill-server

# Scroll in tmux
Ctrl+b then [
# Use arrow keys or Page Up/Down to scroll
# Press q to exit scroll mode
```

## Strategy Details

Both traders use an **Adaptive Portfolio** approach with 11 strategies:

1. **Momentum Fast**: Short-term momentum (10 bars)
2. **Momentum Slow**: Long-term momentum (20 bars)
3. **MA Cross Fast**: 5/15 moving average crossover
4. **MA Cross Slow**: 10/30 moving average crossover
5. **RSI Aggressive**: RSI with 25/75 thresholds
6. **RSI Conservative**: RSI with 30/70 thresholds
7. **Bollinger Bands Breakout**: Trade breakouts
8. **Bollinger Bands Reversion**: Mean reversion
9. **Volume Breakout**: High volume + momentum
10. **VWAP**: Volume-weighted average price
11. **Cross-Sectional**: Relative strength across assets

The system automatically rebalances capital allocation every N bars based on each strategy's performance.

## Risk Management

Both traders include built-in risk controls:

- **Position limits**: Max shares and $ value per asset
- **Total exposure**: Maximum portfolio value at risk
- **Rate limiting**: Orders per minute (global and per-symbol)
- **Cash buffer**: Minimum cash reserve

Crypto trader uses more conservative position sizes due to higher volatility.

## Output Files

**Crypto Trader:**
- Logs: `logs/live_adaptive_crypto_trader.log`
- Data: `logs/live_crypto_data.csv`

**Sector Trader:**
- Logs: `logs/live_adaptive_trader.log`
- Data: `logs/live_session_YYYYMMDD.csv`

## Troubleshooting

### No Data Received (Sector Trader)
- Check if markets are open (9:30 AM - 4:00 PM ET, Mon-Fri)
- Use crypto trader for 24/7 testing

### Connection Issues
- Verify API credentials in `.env`
- Check internet connection
- Confirm Alpaca account is active

### Orders Not Executing
- Check if warmup phase completed
- Verify sufficient cash balance
- Review risk management logs for rejections

### Tmux Not Found
```bash
# macOS
brew install tmux

# Linux
sudo apt install tmux
```

## Live Trading Warning

Both scripts default to **paper trading** for safety. To use real money:

```bash
./scripts/traders/run_crypto_trader.sh --live
```

You will be prompted to confirm before any live trading begins. Start with small amounts and monitor closely.

## Next Steps

- Monitor performance in real-time
- Analyze saved data with notebooks
- Adjust strategy parameters based on results
- Compare crypto vs equity performance
- Test different allocation methods
