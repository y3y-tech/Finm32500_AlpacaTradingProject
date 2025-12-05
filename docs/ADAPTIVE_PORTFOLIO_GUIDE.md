# Adaptive Portfolio Trader - $80k Dynamic Capital Allocation

## Overview

The **Adaptive Portfolio Trader** is a sophisticated meta-strategy that dynamically allocates ~$80,000 (configurable) across 19 different trading sub-strategies based on their performance. Winners get more capital, losers get less. This mimics a professional fund manager constantly rebalancing to favor what's working.

## ✨ Key Features

- 💰 **$80k Default Capital** - Automatically distributed across 19 strategies
- 🔄 **Dynamic Rebalancing** - Every 90 bars (~1.5 hours)
- 📊 **Performance-Based** - Sharpe ratio determines allocation
- 🎯 **19 Sub-Strategies** - Momentum, mean reversion, trend, volatility, RSI
- 🌍 **27+ Tickers** - Indices, tech, sectors, bonds, commodities, international
- ⚡ **Adaptive Learning** - Automatically favors winning strategies
- 🛡️ **Risk Management** - Position limits, cash buffers, daily loss limits
- 🚪 **Close on Exit** - Optional position liquidation with `--close-on-exit`

## Quick Start

### Basic Usage (Paper Trading, $80k)

```bash
export PYTHONPATH="/path/to/project/src:$PYTHONPATH"
python scripts/traders/run_adaptive_portfolio.py
```

### With Position Closing on Exit

```bash
python scripts/traders/run_adaptive_portfolio.py --close-on-exit
```

This will **liquidate all positions** when you press Ctrl-C.

## How It Works

### The Adaptive Allocation Algorithm

1. **Initial State**: All 19 strategies start with equal allocation (~5.3% each)

2. **Trading Phase**: Each strategy trades independently for 90 bars

3. **Performance Tracking**: Metrics tracked include:
   - Total P&L
   - Sharpe Ratio (risk-adjusted returns)
   - Win Rate
   - Number of trades

4. **Rebalancing**: Every 90 bars:
   - Calculate performance scores for each strategy
   - Redistribute capital based on scores
   - Winners get up to 15% max
   - Losers get down to 3% min
   - Capital smoothly transitions over next period

5. **Repeat**: Continuous adaptation as market conditions evolve

### Example Rebalancing

```
Initial:  All strategies at 5.3% ($4,240 each)

After 90 bars:
  momentum_fast:     5.3% → 12.4%  (+$5,680)  ✅ Winner
  ma_cross_slow:     5.3% → 8.7%   (+$2,720)  ✅
  rsi_conservative:  5.3% → 5.3%   ($0)       —
  rsi_aggressive:    5.3% → 3.0%   (-$1,840)  ❌ Loser
  ...

Total: Still $80,000, just redistributed
```

## The 19 Sub-Strategies

### Momentum (3 strategies)
- **momentum_fast**: 10-bar lookback, 0.8% threshold - catches quick trends
- **momentum_medium**: 15-bar lookback, 0.6% threshold - balanced
- **momentum_slow**: 25-bar lookback, 0.4% threshold - longer-term trends

### Mean Reversion (3 strategies)
- **ma_cross_fast**: 5/15 MA crossover - quick reversions
- **ma_cross_medium**: 10/30 MA crossover - standard
- **ma_cross_slow**: 20/60 MA crossover - long-term reversions

### RSI (2 strategies)
- **rsi_aggressive**: 25/75 levels, 2% profit target, 1% stop loss
- **rsi_conservative**: 30/70 levels, 1.5% profit target, 0.8% stop loss

### Trend Following (3 strategies)
- **donchian**: 20-bar entry, 10-bar exit - breakout trading
- **macd_crossover**: 12/26/9 MACD - trend confirmation
- **roc**: 12-bar rate of change with smoothing - momentum bursts

### Volatility (3 strategies)
- **bb_breakout**: Bollinger breakout, 2.0 std dev
- **bb_reversion**: Bollinger reversion, 2.5 std dev
- **keltner**: Keltner channel breakouts, 2.0x ATR

### Advanced Reversion (2 strategies)
- **zscore**: Z-score mean reversion, 2.0 entry threshold
- **multi_indicator**: Multi-indicator reversion score

### Other (3 strategies)
- **stochastic**: Stochastic oscillator crossovers
- **volume_breakout**: Volume spike breakouts
- **vwap**: VWAP deviation trading

## Default Asset Coverage

### 27 Tickers Across All Major Asset Classes

**Core Indices (4)**
- SPY - S&P 500
- QQQ - Nasdaq 100
- IWM - Russell 2000
- DIA - Dow Jones

**Mega-Cap Tech (7)**
- AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA

**Sector ETFs (7)**
- XLF (Financials), XLK (Tech), XLE (Energy), XLV (Healthcare)
- XLI (Industrials), XLP (Staples), XLY (Discretionary)

**Bonds (3)**
- TLT - 20+ Year Treasury
- IEF - 7-10 Year Treasury
- LQD - Investment Grade Corporate

**Commodities (3)**
- GLD - Gold
- SLV - Silver
- USO - Oil

**International (2)**
- EEM - Emerging Markets
- VGK - European Stocks

**Total Coverage**: Stocks + ETFs + Bonds + Commodities = Diversified!

**Note**: NO CRYPTO included by design for stability

## Usage Examples

### 1. Default Run ($80k, Paper Trading)

```bash
python scripts/traders/run_adaptive_portfolio.py
```

### 2. Custom Capital

```bash
# $100k
python scripts/traders/run_adaptive_portfolio.py --initial-cash 100000

# $50k
python scripts/traders/run_adaptive_portfolio.py --initial-cash 50000
```

### 3. Faster Rebalancing

```bash
# Every 60 bars (~1 hour)
python scripts/traders/run_adaptive_portfolio.py --rebalance-period 60

# Every 30 bars (~30 min) - very aggressive
python scripts/traders/run_adaptive_portfolio.py --rebalance-period 30
```

### 4. Different Allocation Methods

```bash
# Sharpe ratio (risk-adjusted) - DEFAULT, RECOMMENDED
python scripts/traders/run_adaptive_portfolio.py --allocation-method sharpe

# Raw PnL (absolute profit)
python scripts/traders/run_adaptive_portfolio.py --allocation-method pnl

# Win rate (% winning trades)
python scripts/traders/run_adaptive_portfolio.py --allocation-method win_rate
```

### 5. Custom Allocation Limits

```bash
# Allow 5-25% per strategy (more aggressive)
python scripts/traders/run_adaptive_portfolio.py --min-allocation 0.05 --max-allocation 0.25

# Keep 2-10% per strategy (more conservative)
python scripts/traders/run_adaptive_portfolio.py --min-allocation 0.02 --max-allocation 0.10
```

### 6. Live Trading ⚠️

```bash
# LIVE TRADING - BE CAREFUL!
python scripts/traders/run_adaptive_portfolio.py --live --initial-cash 80000
```

### 7. Save Data & Close on Exit

```bash
python scripts/traders/run_adaptive_portfolio.py \
  --save-data \
  --data-file logs/adaptive_$(date +%Y%m%d).csv \
  --close-on-exit
```

### 8. Custom Tickers

```bash
# Only indices and bonds
python scripts/traders/run_adaptive_portfolio.py \
  --tickers SPY QQQ IWM TLT IEF BND

# Only tech stocks
python scripts/traders/run_adaptive_portfolio.py \
  --tickers AAPL MSFT NVDA GOOGL AMZN META TSLA
```

### 9. Full-Featured Production Run

```bash
python scripts/traders/run_adaptive_portfolio.py \
  --initial-cash 100000 \
  --rebalance-period 120 \
  --allocation-method sharpe \
  --min-allocation 0.05 \
  --max-allocation 0.20 \
  --save-data \
  --data-file logs/adaptive_portfolio_$(date +%Y%m%d_%H%M).csv \
  --close-on-exit
```

**What this does**:
- $100k capital
- Rebalances every 2 hours
- Sharpe ratio allocation (risk-adjusted)
- Strategies get 5-20% of capital
- Saves all market data
- Closes positions on Ctrl-C

## Configuration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--initial-cash` | 80000 | Total capital to allocate ($) |
| `--tickers` | 27 default | List of tickers to trade |
| `--min-warmup-bars` | 70 | Bars required before trading |
| `--rebalance-period` | 90 | Bars between rebalances |
| `--allocation-method` | sharpe | pnl, sharpe, or win_rate |
| `--min-allocation` | 0.03 | Min % per strategy (3%) |
| `--max-allocation` | 0.15 | Max % per strategy (15%) |
| `--live` | False | Enable live trading |
| `--save-data` | False | Save market data to CSV |
| `--data-file` | logs/adaptive_portfolio_data.csv | Data file path |
| `--close-on-exit` | False | Liquidate on Ctrl-C ✅ |

## Monitoring & Logs

### Startup

```
================================================================================
ADAPTIVE PORTFOLIO TRADER - DYNAMIC CAPITAL ALLOCATION
================================================================================
Initial Capital: $80,000.00
Tickers: 27 total
Sub-Strategies: 19 different strategies
Rebalance Period: Every 90 bars
Allocation Method: sharpe
Min/Max Allocation: 3.0% / 15.0%
Position Size: $1,600 per trade
Max Position: 16 shares
Trading Mode: PAPER
================================================================================

🎯 ADAPTIVE ALLOCATION: Winners get more capital, losers get less!
```

### Rebalancing Logs

```
[REBALANCE #1] Evaluating strategy performance...
  momentum_fast:      PnL: +$450, Sharpe: 1.8 → 12.4% allocation ✅
  ma_cross_medium:    PnL: +$280, Sharpe: 1.2 → 8.7% allocation
  rsi_aggressive:     PnL: -$120, Sharpe: -0.3 → 3.0% allocation ❌
  ...

[REBALANCE #1] New allocations applied. Top performers:
  1. momentum_fast: 12.4% ($9,920)
  2. bb_breakout: 11.2% ($8,960)
  3. donchian: 9.8% ($7,840)
  ...
```

### Performance Summary (Ctrl-C)

```
================================================================================
ADAPTIVE PORTFOLIO PERFORMANCE SUMMARY
================================================================================
Total P&L: +$3,450 (+4.31%)
Best Strategy: momentum_fast (+$890)
Worst Strategy: rsi_aggressive (-$180)
Win Rate: 58.3%
Total Trades: 247
Rebalances: 8
================================================================================
```

## Advantages

✅ **Automatic Adaptation**: No manual rebalancing needed
✅ **Diversification**: 19 strategies reduce single-strategy risk
✅ **Efficient Capital**: Money flows to what's working
✅ **Market Flexibility**: Different strategies win in different regimes
✅ **Risk Management**: Position limits, exposure controls, cash buffers
✅ **Comprehensive Coverage**: 27 tickers across all major asset classes
✅ **Close on Exit**: Clean shutdown with position liquidation

## Limitations & Risks

⚠️ **Complexity**: 19 strategies = harder to debug
⚠️ **Warmup Time**: 70+ bars required before trading
⚠️ **Transaction Costs**: Rebalancing incurs trades/commissions
⚠️ **Overfitting Risk**: Past performance ≠ future results
⚠️ **Memory Usage**: ~500MB-1GB for all strategies
⚠️ **Market Dependent**: Performance varies by market regime

## Best Practices

### 1. Start Small
```bash
# Begin with $10k to test
python scripts/traders/run_adaptive_portfolio.py --initial-cash 10000
```

### 2. Monitor First Rebalance
Watch the first rebalance closely to understand how capital shifts

### 3. Longer Rebalance Periods
Reduce transaction costs:
```bash
python scripts/traders/run_adaptive_portfolio.py --rebalance-period 180
```

### 4. Use Sharpe Method
Risk-adjusted returns are better than raw PnL:
```bash
python scripts/traders/run_adaptive_portfolio.py --allocation-method sharpe
```

### 5. Always Save Data
```bash
python scripts/traders/run_adaptive_portfolio.py --save-data
```

### 6. Paper Trade First
Run for at least 1-2 weeks in paper mode before going live

### 7. Set Reasonable Limits
```bash
# Don't let any strategy dominate
python scripts/traders/run_adaptive_portfolio.py --max-allocation 0.12
```

## Comparison: Adaptive vs Fixed Allocation

### Adaptive Portfolio (This System)

| Metric | Value |
|--------|-------|
| Capital Allocation | **Dynamic** |
| Rebalancing | **Automatic** (every 90 bars) |
| Strategies | **19 built-in** |
| Adaptation | **Performance-based** |
| Best For | Large capital, hands-off |

### Fixed Multi-Trader (Alternative)

| Metric | Value |
|--------|-------|
| Capital Allocation | **Fixed** |
| Rebalancing | **None** (manual config edits) |
| Strategies | **User-defined** (2-10 typical) |
| Adaptation | **None** |
| Best For | Custom combos, testing |

## Performance Expectations

### Realistic Expectations

- **Startup**: 70 bars warmup (~1 hour 10 min at 1-min bars)
- **First Rebalance**: After 90 bars (~1.5 hours)
- **Memory**: ~500MB-1GB
- **CPU**: Moderate (19 strategies calculating)
- **Network**: Low (single WebSocket connection)

### Capital Efficiency

With $80k and 19 strategies:
- Average per strategy: ~$4,210
- Best performer could get: ~$12,000 (15% max)
- Worst performer could get: ~$2,400 (3% min)

## Troubleshooting

### "Strategies not trading"
- Wait for warmup (70 bars minimum)
- Check market hours
- Verify tickers are valid

### "Memory usage high"
- Reduce number of tickers with `--tickers`
- Increase `--rebalance-period` to reduce tracking overhead

### "Too many rebalances"
- Increase `--rebalance-period` (try 120-180)

### "One strategy dominating"
- Lower `--max-allocation` (try 0.10 or 10%)

### "Not enough diversification"
- Raise `--min-allocation` (try 0.05 or 5%)

## FAQ

**Q: Does this close positions on exit?**
A: **YES** - Use `--close-on-exit` flag to liquidate all positions when you press Ctrl-C

**Q: Can I trade crypto with this?**
A: No, this system is designed for stocks/ETFs/bonds only (no crypto)

**Q: How often does it rebalance?**
A: Every 90 bars by default (~1.5 hours at 1-min bars), configurable with `--rebalance-period`

**Q: What if a strategy loses money?**
A: It gets reduced allocation (down to 3% minimum) but stays active

**Q: Can I add my own strategies?**
A: Yes, but requires modifying `run_adaptive_portfolio.py` code

**Q: How much capital do I need?**
A: Minimum ~$10k, recommended $50k+, default $80k

**Q: What's the best allocation method?**
A: Sharpe ratio (default) - it's risk-adjusted and most robust

## Next Steps

1. **Test with defaults**:
   ```bash
   python scripts/traders/run_adaptive_portfolio.py
   ```

2. **Monitor first rebalance** to see how capital shifts

3. **Save data** for analysis:
   ```bash
   python scripts/traders/run_adaptive_portfolio.py --save-data
   ```

4. **Customize** based on your risk tolerance and capital

5. **Go live** only after successful paper trading

## Environment Setup

```bash
# Required environment variables
export APCA_API_KEY_ID="your_key"
export APCA_API_SECRET_KEY="your_secret"

# Python path (if needed)
export PYTHONPATH="/path/to/project/src:$PYTHONPATH"
```

---

**Ready to start?**

```bash
python scripts/traders/run_adaptive_portfolio.py --close-on-exit
```

The system will dynamically allocate your capital and favor winning strategies automatically! 🚀
