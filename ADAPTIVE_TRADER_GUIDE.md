# Adaptive Sector ETF Trader - Complete Guide

**Purpose**: Multi-strategy adaptive portfolio for SPDR sector ETFs with $10k budget

---

## What It Does

The Adaptive Sector ETF Trader is a **meta-strategy** that:

1. ✅ Runs **11 different strategies simultaneously** on all 11 SPDR sector ETFs
2. ✅ Tracks each strategy's P&L independently
3. ✅ **Rebalances every hour** - winners get more capital, losers get less
4. ✅ Automatically adapts to market conditions
5. ✅ Manages $10,000 budget with strict risk controls

**It's like having 11 traders working for you, and you automatically give more money to the best performers!**

---

## Strategies Included

All 11 strategies run simultaneously:

| Strategy | Type | Description |
|----------|------|-------------|
| **momentum_fast** | Trend | 10-tick lookback, 0.8% threshold |
| **momentum_slow** | Trend | 20-tick lookback, 0.5% threshold |
| **ma_cross_fast** | Mean Reversion | 5/15 MA crossover |
| **ma_cross_slow** | Mean Reversion | 10/30 MA crossover |
| **rsi_aggressive** | Oscillator | RSI 25/75 with 1.5% profit target |
| **rsi_conservative** | Oscillator | RSI 30/70 with 2.0% profit target |
| **bb_breakout** | Volatility | Bollinger breakout mode |
| **bb_reversion** | Volatility | Bollinger reversion mode |
| **volume_breakout** | Momentum | 2x volume with 0.8% price move |
| **vwap** | Intraday | 0.5% deviation from VWAP |
| **cross_sectional** | Relative Value | Long top 3 sectors |

---

## SPDR Sector ETFs Traded

All 11 sector ETFs are eligible for trading:

| Sector | ETF | Description |
|--------|-----|-------------|
| Financial | XLF | Banks, insurance, real estate investment |
| Industrial | XLI | Aerospace, construction, machinery |
| Real Estate | XLRE | REITs and real estate companies |
| Materials | XLB | Chemicals, metals, mining |
| Communication | XLC | Telecom, media, entertainment |
| Energy | XLE | Oil, gas, energy companies |
| Technology | XLK | Software, hardware, semiconductors |
| Consumer Staples | XLP | Food, beverages, household products |
| Health Care | XLV | Pharma, biotech, healthcare providers |
| Utilities | XLU | Electric, gas, water utilities |
| Consumer Discretionary | XLY | Retail, automotive, leisure |

---

## How It Works

### Phase 1: Initial Setup (Equal Weight)

```
Each strategy starts with equal allocation: 100% / 11 = 9.09% each
Budget: $10,000
Per strategy: $909
```

### Phase 2: Strategies Trade

All 11 strategies generate signals independently:
- Momentum strategies look for trends
- RSI strategies look for oversold/overbought
- Cross-sectional picks best sectors

Orders are scaled by each strategy's allocation.

### Phase 3: Hourly Rebalancing

Every hour (60 ticks @ 1-min bars):

1. **Calculate Performance**
   - Track each strategy's P&L since last rebalance
   - Calculate win rate, Sharpe ratio, etc.

2. **Rank Strategies**
   - By default: Rank by recent P&L
   - Optional: Rank by Sharpe ratio or win rate

3. **Reallocate Capital**
   - Winners get more capital (up to 25% max)
   - Losers get less capital (down to 3% min)
   - Always sum to 100%

4. **Example Rebalancing**:
   ```
   Before (all equal):
   momentum_fast: 9% | P&L: +$150
   rsi_aggressive: 9% | P&L: +$80
   ma_cross_slow:  9% | P&L: -$20

   After (winners get more):
   momentum_fast: 15% ↑ (best performer)
   rsi_aggressive: 12% ↑ (good performer)
   ma_cross_slow:   5% ↓ (underperformer)
   ```

---

## Usage

### Basic Usage

```bash
# Run on 1-minute bar data
python scripts/adaptive_sector_trader.py \
    --data data/sector_etfs_1min.csv

# The script will:
# 1. Load all 11 strategies
# 2. Trade all 11 sector ETFs
# 3. Rebalance every 60 ticks (1 hour)
# 4. Output results to logs/adaptive/
```

### Advanced Options

```bash
# Use 10-second bars (rebalance every 360 ticks = 1 hour)
python scripts/adaptive_sector_trader.py \
    --data data/sector_etfs_10sec.csv \
    --rebalance-period 360

# Different allocation method (Sharpe ratio)
python scripts/adaptive_sector_trader.py \
    --data data/sector_etfs_1min.csv \
    --allocation-method sharpe

# Custom budget
python scripts/adaptive_sector_trader.py \
    --data data/sector_etfs_1min.csv \
    --initial-cash 25000

# Test with limited data
python scripts/adaptive_sector_trader.py \
    --data data/sector_etfs_1min.csv \
    --max-ticks 5000

# Enable debug logging
python scripts/adaptive_sector_trader.py \
    --data data/sector_etfs_1min.csv \
    --log-level DEBUG
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--data` | Required | CSV file with sector ETF data |
| `--initial-cash` | 10000 | Starting capital ($) |
| `--rebalance-period` | 60 | Ticks between rebalances |
| `--allocation-method` | pnl | How to rank strategies (pnl/sharpe/win_rate) |
| `--max-ticks` | None | Limit ticks for testing |
| `--output-dir` | logs/adaptive | Where to save results |
| `--log-level` | INFO | Logging verbosity (DEBUG/INFO/WARNING) |

---

## Data Requirements

### CSV Format

The data file must contain all 11 sector ETFs:

```csv
timestamp,symbol,price,volume
2024-01-01 09:30:00,XLF,35.42,1000000
2024-01-01 09:30:00,XLI,110.23,500000
2024-01-01 09:30:00,XLRE,38.91,300000
...
2024-01-01 09:31:00,XLF,35.45,950000
2024-01-01 09:31:00,XLI,110.28,480000
...
```

**Requirements**:
- All 11 ETF symbols
- Timestamps in chronological order
- Price and volume data
- Consistent time intervals (1-min, 10-sec, etc.)

### Getting Data

You can download sector ETF data from:
- **Yahoo Finance**: `yfinance` library
- **Alpaca Markets**: Historical bars API
- **Your existing data sources**

Example with `yfinance`:
```python
import yfinance as yf
import pandas as pd

symbols = ["XLF", "XLI", "XLRE", "XLB", "XLC", "XLE", "XLK", "XLP", "XLV", "XLU", "XLY"]

# Download 1-minute bars for past 5 days
dfs = []
for symbol in symbols:
    df = yf.download(symbol, period="5d", interval="1m")
    df['symbol'] = symbol
    dfs.append(df)

combined = pd.concat(dfs)
combined.to_csv('data/sector_etfs_1min.csv')
```

---

## Output Files

After running, you'll find:

### 1. Performance Log (`logs/adaptive/adaptive_sector_trader.log`)
```
2024-01-01 10:30:00 - REBALANCING ADAPTIVE PORTFOLIO at tick 60
Strategy Performance & Allocations:
Strategy             Recent P&L    Total P&L   Win Rate   Old%   New%
-------------------- ------------ ------------ ---------- ------ ------
momentum_fast        $      85.50 $      85.50      62.5%   9.1%  14.2%
rsi_aggressive       $      42.30 $      42.30      55.0%   9.1%  11.5%
ma_cross_slow        $     -15.20 $     -15.20      40.0%   9.1%   5.8%
...
```

### 2. Order Log (`logs/adaptive/orders.csv`)
Complete history of all orders from all strategies.

### 3. Trades (`logs/adaptive/trades.csv`)
All executed trades with timestamps, prices, quantities.

### 4. Equity Curve (`logs/adaptive/equity_curve.csv`)
Portfolio value over time (for plotting).

### 5. Console Output
Real-time updates on rebalancing and final performance summary.

---

## Understanding the Results

### Rebalancing Log

Every hour you'll see which strategies are winning:

```
Strategy             Recent P&L    Total P&L   Win Rate   Old%   New%
momentum_fast        $     150.25 $     342.18      65.2%  12.0%  18.5%
cross_sectional      $     125.80 $     298.45      58.3%  11.5%  16.2%
rsi_conservative     $      45.30 $     112.90      52.1%   8.5%  10.3%
bb_reversion         $     -12.50 $      28.40      48.0%   9.0%   6.5%
ma_cross_slow        $     -45.80 $     -95.20      35.7%   7.5%   3.0%
```

**Interpretation**:
- **momentum_fast**: Up 18.5% allocation (from 12%) → Winner gets more capital!
- **ma_cross_slow**: Down to 3.0% allocation (from 7.5%) → Loser gets less capital
- **Recent P&L**: Performance since last rebalance (resets each hour)
- **Total P&L**: Cumulative performance across entire backtest

### Final Summary

```
ADAPTIVE PORTFOLIO FINAL PERFORMANCE
Strategy             Total P&L   Trades  Win Rate  Final%
momentum_fast        $   482.35      142      62.7%    18.5%
cross_sectional      $   398.22       89      61.8%    16.2%
rsi_aggressive       $   285.90      201      55.4%    13.8%
vwap                 $   142.50      156      51.3%    11.2%
bb_breakout          $    95.30       78      49.0%     8.5%
rsi_conservative     $    78.20      145      52.1%     8.0%
bb_reversion         $    45.60       92      48.9%     6.8%
volume_breakout      $    12.40       34      47.1%     5.5%
ma_cross_fast        $   -15.80       67      42.5%     4.2%
momentum_slow        $   -28.90       89      39.3%     3.8%
ma_cross_slow        $   -52.30      112      35.7%     3.0%
```

**Key Insights**:
- **Top performers** (momentum_fast, cross_sectional) ended with highest allocations
- **Worst performers** (ma_cross_slow) dropped to minimum 3% allocation
- **System adapts**: Capital flows to winners automatically!

---

## Allocation Methods

You can choose how strategies are ranked:

### 1. P&L (Default) - `--allocation-method pnl`
Ranks by dollar P&L since last rebalance.

**Pros**: Simple, directly measures profit
**Cons**: Favors high-volatility strategies

### 2. Sharpe Ratio - `--allocation-method sharpe`
Ranks by risk-adjusted returns (return / volatility).

**Pros**: Rewards consistent performers
**Cons**: Needs more data for accuracy

### 3. Win Rate - `--allocation-method win_rate`
Ranks by percentage of winning trades.

**Pros**: Rewards accuracy
**Cons**: Ignores trade size (many small wins vs few big wins)

**Recommendation**: Start with `pnl` (default), experiment with `sharpe` for more stable allocations.

---

## Risk Management

Built-in safety limits:

```python
RiskConfig(
    max_position_size=20,          # Max 20 shares per ETF
    max_position_value=2000,       # Max $2k per position
    max_total_exposure=9000,       # Max $9k total (90% of capital)
    max_orders_per_minute=50,      # Rate limiting
    min_cash_buffer=500            # Always keep $500 cash
)
```

**Allocation Constraints**:
- Min per strategy: 3%
- Max per strategy: 25%
- Always sums to 100%

This ensures:
- No single strategy dominates
- All strategies get a fair chance
- Losers don't get eliminated completely (can recover)

---

## Tips for Best Results

### 1. Data Quality
- Use clean, complete data for all 11 ETFs
- Ensure synchronized timestamps
- Remove gaps and outliers

### 2. Rebalance Frequency
- **1-minute bars**: Use `--rebalance-period 60` (1 hour)
- **10-second bars**: Use `--rebalance-period 360` (1 hour)
- **5-minute bars**: Use `--rebalance-period 12` (1 hour)

### 3. Monitor Performance
- Check which strategies consistently win
- If one strategy dominates, you might just use that one alone
- If all strategies struggle, market conditions may not suit this approach

### 4. Live Trading Preparation
- Backtest on at least 1 month of data
- Test different time periods (bull, bear, sideways markets)
- Verify strategies work on out-of-sample data

---

## Troubleshooting

### "Data file not found"
- Check file path is correct
- Use absolute path if relative path fails

### "Only N stocks with data (min: 5)"
- Some strategies need multiple symbols
- Ensure all 11 ETFs are in your data file
- Check data quality (no missing symbols)

### "No trades executed"
- Strategies may not generate signals early on (need history)
- Try longer backtests (more ticks)
- Check log file for strategy initialization

### Poor performance
- Try different `--allocation-method`
- Adjust `--rebalance-period` (more/less frequent)
- Check if strategies are suited for current market regime
- Review individual strategy performance in logs

---

## Next Steps

1. **Get Data**: Download sector ETF historical data
2. **Backtest**: Run adaptive trader on past 1-3 months
3. **Analyze**: Review which strategies perform best
4. **Optimize**: Tune rebalance period and allocation method
5. **Forward Test**: Test on recent (unseen) data
6. **Deploy**: Run live with paper trading first

---

## Example Workflow

```bash
# Step 1: Get data (using your existing data sources)
# Make sure you have data/sector_etfs_1min.csv with all 11 ETFs

# Step 2: Run initial backtest
python scripts/adaptive_sector_trader.py \
    --data data/sector_etfs_1min.csv \
    --max-ticks 10000

# Step 3: Review results
cat logs/adaptive/adaptive_sector_trader.log

# Step 4: Analyze equity curve
python -c "
import pandas as pd
import matplotlib.pyplot as plt
df = pd.read_csv('logs/adaptive/equity_curve.csv')
plt.plot(df['equity'])
plt.title('Adaptive Portfolio Equity Curve')
plt.savefig('logs/adaptive/equity_plot.png')
"

# Step 5: Full backtest if results look good
python scripts/adaptive_sector_trader.py \
    --data data/sector_etfs_1min.csv

# Step 6: Deploy to live trading (paper first!)
# Use your live trading engine with the best-performing config
```

---

## Summary

The Adaptive Sector ETF Trader gives you:

✅ **Diversification**: 11 different strategies, 11 different sectors
✅ **Adaptability**: Winners get more capital automatically
✅ **Risk Management**: Strict position limits, cash buffers
✅ **Transparency**: Complete logging and performance tracking
✅ **Simplicity**: One command to run everything

**Perfect for trading competitions where you want multiple strategies competing against each other!**

Start with a backtest, see which strategies win, and let the system adapt to market conditions automatically! 🚀
