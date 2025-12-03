# Strategy Logging and Performance Analysis Guide

This guide explains how to access, analyze, and reconstruct strategy performance using the comprehensive logging infrastructure.

---

## Overview

The trading system logs data at **4 levels**:

1. **Order Log (CSV)** - Every order event with timestamps
2. **Strategy Logs (Console/File)** - Signal generation with indicator values
3. **Portfolio State** - Positions, P&L, equity curve
4. **Trade History** - All executed trades with prices and quantities

---

## 1. Order Log (CSV)

### Location
`logs/orders.csv` (configurable in BacktestEngine)

### Contents
Every order lifecycle event is logged:

```csv
timestamp,event_type,order_id,symbol,side,order_type,quantity,price,status,filled_quantity,average_fill_price,message
2024-01-01 09:30:00,SENT,abc-123,AAPL,BUY,MARKET,100,,NEW,0,0.0,
2024-01-01 09:30:00,FILLED,abc-123,AAPL,BUY,MARKET,100,,FILLED,100,150.25,Executed 100 shares at $150.25
2024-01-01 10:15:00,SENT,def-456,AAPL,SELL,MARKET,100,,NEW,0,0.0,
2024-01-01 10:15:00,FILLED,def-456,AAPL,SELL,MARKET,100,,FILLED,100,152.50,Executed 100 shares at $152.50
```

### Analysis Example

```python
import pandas as pd

# Load order log
orders = pd.read_csv('logs/orders.csv', parse_dates=['timestamp'])

# Filter for filled orders only
filled_orders = orders[orders['event_type'] == 'FILLED']

# Calculate P&L per trade
buys = filled_orders[filled_orders['side'] == 'BUY']
sells = filled_orders[filled_orders['side'] == 'SELL']

# Group by symbol
for symbol in filled_orders['symbol'].unique():
    symbol_orders = filled_orders[filled_orders['symbol'] == symbol]
    print(f"\n{symbol} Order Summary:")
    print(symbol_orders[['timestamp', 'side', 'quantity', 'average_fill_price']])

# Total trades executed
print(f"Total trades: {len(filled_orders)}")
print(f"Total buy volume: {buys['quantity'].sum()}")
print(f"Total sell volume: {sells['quantity'].sum()}")
```

---

## 2. Strategy Signal Logs

### Location
- **Console output** during backtest/live trading
- **Log file** if configured: `logs/strategy.log`

### Contents
Each strategy logs:
- Signal generation (BUY/SELL) with reasons
- Indicator values at signal time
- Entry/exit prices
- Position quantities

### Example Output

```
INFO - MomentumStrategy - BUY signal for AAPL: momentum=0.0234, quantity=66, current_qty=0
INFO - MomentumStrategy - SELL signal for AAPL: momentum=-0.0156, quantity=66
INFO - RSIStrategy - BUY signal (OVERSOLD) for MSFT: RSI=28.45, threshold=30, quantity=50
INFO - RSIStrategy - PROFIT TARGET HIT for MSFT: entry=180.00, current=185.40, pnl=3.00%, target=3.00%
INFO - BollingerBandsStrategy - BUY signal (BREAKOUT) for TSLA: price=245.50, upper_band=242.30, middle=235.00
```

### Configure Logging to File

```python
import logging

# Setup file logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/strategy.log'),
        logging.StreamHandler()  # Also print to console
    ]
)
```

### Parse Strategy Logs

```python
import re

# Parse log file for trade signals
with open('logs/strategy.log', 'r') as f:
    for line in f:
        if 'BUY signal' in line or 'SELL signal' in line:
            print(line.strip())

# Extract RSI values when signals generated
rsi_signals = []
with open('logs/strategy.log', 'r') as f:
    for line in f:
        match = re.search(r'RSI=(\d+\.\d+)', line)
        if match:
            rsi_signals.append(float(match.group(1)))

print(f"Average RSI at signal: {sum(rsi_signals)/len(rsi_signals):.2f}")
```

---

## 3. Portfolio State and Equity Curve

### Access During Backtest

```python
from AlpacaTrading.backtesting.engine import BacktestEngine
from AlpacaTrading.strategies.momentum import MomentumStrategy

# Run backtest
engine = BacktestEngine(...)
result = engine.run()

# Access portfolio state
print(f"Final cash: ${result.portfolio.cash:,.2f}")
print(f"Final equity: ${result.portfolio.get_total_equity():,.2f}")
print(f"Total P&L: ${result.portfolio.get_total_pnl():,.2f}")

# Access all positions
for symbol, position in result.portfolio.positions.items():
    print(f"{symbol}: {position.quantity} shares, "
          f"avg_cost=${position.average_cost:.2f}, "
          f"realized_pnl=${position.realized_pnl:.2f}")

# Equity curve (portfolio value over time)
equity_df = result.equity_curve
print(equity_df.head())
# Columns: timestamp, equity

# Save equity curve to CSV
equity_df.to_csv('logs/equity_curve.csv', index=False)
```

### Visualize Equity Curve

```python
import matplotlib.pyplot as plt

# Plot equity curve
plt.figure(figsize=(12, 6))
plt.plot(equity_df['timestamp'], equity_df['equity'])
plt.title('Portfolio Equity Over Time')
plt.xlabel('Time')
plt.ylabel('Equity ($)')
plt.grid(True)
plt.savefig('logs/equity_curve.png')
plt.show()

# Calculate drawdown
equity_df['peak'] = equity_df['equity'].cummax()
equity_df['drawdown'] = (equity_df['equity'] - equity_df['peak']) / equity_df['peak'] * 100

plt.figure(figsize=(12, 6))
plt.plot(equity_df['timestamp'], equity_df['drawdown'])
plt.title('Drawdown Over Time')
plt.xlabel('Time')
plt.ylabel('Drawdown (%)')
plt.grid(True)
plt.savefig('logs/drawdown.png')
plt.show()
```

---

## 4. Trade History

### Access All Trades

```python
# Get all executed trades
trades = result.trades

# Convert to DataFrame for analysis
import pandas as pd

trade_data = []
for trade in trades:
    trade_data.append({
        'timestamp': trade.timestamp,
        'symbol': trade.symbol,
        'side': trade.side.value,
        'quantity': trade.quantity,
        'price': trade.price,
        'value': trade.value
    })

trades_df = pd.DataFrame(trade_data)

# Save to CSV
trades_df.to_csv('logs/trades.csv', index=False)

# Analyze trades
print(trades_df.describe())
print(f"\nTotal trades: {len(trades_df)}")
print(f"Symbols traded: {trades_df['symbol'].unique()}")
print(f"Total volume: ${trades_df['value'].sum():,.2f}")
```

### Calculate Per-Trade P&L

```python
# Match buys with sells to calculate P&L per round-trip trade
buy_trades = trades_df[trades_df['side'] == 'BUY'].copy()
sell_trades = trades_df[trades_df['side'] == 'SELL'].copy()

round_trips = []
for symbol in trades_df['symbol'].unique():
    symbol_buys = buy_trades[buy_trades['symbol'] == symbol].sort_values('timestamp')
    symbol_sells = sell_trades[sell_trades['symbol'] == symbol].sort_values('timestamp')

    # Simple FIFO matching
    remaining_qty = 0
    avg_buy_price = 0

    for _, trade in pd.concat([symbol_buys, symbol_sells]).sort_values('timestamp').iterrows():
        if trade['side'] == 'BUY':
            avg_buy_price = ((avg_buy_price * remaining_qty) + (trade['price'] * trade['quantity'])) / (remaining_qty + trade['quantity'])
            remaining_qty += trade['quantity']
        else:  # SELL
            pnl = (trade['price'] - avg_buy_price) * trade['quantity']
            pnl_pct = (trade['price'] - avg_buy_price) / avg_buy_price * 100
            round_trips.append({
                'symbol': symbol,
                'buy_price': avg_buy_price,
                'sell_price': trade['price'],
                'quantity': trade['quantity'],
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'sell_time': trade['timestamp']
            })
            remaining_qty -= trade['quantity']

round_trip_df = pd.DataFrame(round_trips)
round_trip_df.to_csv('logs/round_trip_pnl.csv', index=False)

# Analyze round-trip performance
print(f"Total round trips: {len(round_trip_df)}")
print(f"Win rate: {(round_trip_df['pnl'] > 0).sum() / len(round_trip_df) * 100:.2f}%")
print(f"Average P&L per trade: ${round_trip_df['pnl'].mean():.2f}")
print(f"Best trade: ${round_trip_df['pnl'].max():.2f}")
print(f"Worst trade: ${round_trip_df['pnl'].min():.2f}")
```

---

## 5. Performance Metrics

### Built-in Metrics

```python
# Access performance metrics from backtest result
metrics = result.performance_metrics

print("Performance Metrics:")
print(f"  Total Return: {metrics['total_return']:.2f}%")
print(f"  Total P&L: ${metrics['total_pnl']:,.2f}")
print(f"  Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
print(f"  Max Drawdown: {metrics['max_drawdown']:.2f}%")
print(f"  Win Rate: {metrics['win_rate']:.2f}%")
print(f"  Total Trades: {metrics['total_trades']}")
print(f"  Avg Trade: ${metrics['avg_trade_pnl']:,.2f}")

# Save metrics to JSON
import json
with open('logs/performance_metrics.json', 'w') as f:
    json.dump(metrics, f, indent=2)
```

---

## 6. Complete Analysis Pipeline

Here's a complete script to analyze strategy performance:

```python
import pandas as pd
import matplotlib.pyplot as plt
import json
from pathlib import Path

def analyze_strategy_performance(result, output_dir='logs/analysis'):
    """
    Complete analysis of strategy performance.

    Generates:
    - Equity curve chart
    - Drawdown chart
    - Trade distribution histogram
    - Performance metrics JSON
    - Trade log CSV
    - Round-trip P&L CSV
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # 1. Save performance metrics
    with open(f'{output_dir}/metrics.json', 'w') as f:
        json.dump(result.performance_metrics, f, indent=2)

    # 2. Save equity curve
    equity_df = result.equity_curve
    equity_df.to_csv(f'{output_dir}/equity_curve.csv', index=False)

    # 3. Plot equity curve
    plt.figure(figsize=(14, 7))
    plt.subplot(2, 1, 1)
    plt.plot(equity_df['timestamp'], equity_df['equity'])
    plt.title('Equity Curve')
    plt.ylabel('Equity ($)')
    plt.grid(True)

    # 4. Plot drawdown
    equity_df['peak'] = equity_df['equity'].cummax()
    equity_df['drawdown'] = (equity_df['equity'] - equity_df['peak']) / equity_df['peak'] * 100
    plt.subplot(2, 1, 2)
    plt.fill_between(equity_df['timestamp'], equity_df['drawdown'], 0, alpha=0.3, color='red')
    plt.plot(equity_df['timestamp'], equity_df['drawdown'], color='red')
    plt.title('Drawdown')
    plt.ylabel('Drawdown (%)')
    plt.xlabel('Time')
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f'{output_dir}/equity_and_drawdown.png', dpi=150)
    plt.close()

    # 5. Save all trades
    trade_data = [{
        'timestamp': t.timestamp,
        'symbol': t.symbol,
        'side': t.side.value,
        'quantity': t.quantity,
        'price': t.price,
        'value': t.value
    } for t in result.trades]

    trades_df = pd.DataFrame(trade_data)
    trades_df.to_csv(f'{output_dir}/all_trades.csv', index=False)

    # 6. Trade size distribution
    plt.figure(figsize=(10, 6))
    plt.hist(trades_df['value'], bins=30, edgecolor='black')
    plt.title('Trade Size Distribution')
    plt.xlabel('Trade Value ($)')
    plt.ylabel('Frequency')
    plt.grid(True, alpha=0.3)
    plt.savefig(f'{output_dir}/trade_distribution.png', dpi=150)
    plt.close()

    # 7. Summary report
    summary = f"""
STRATEGY PERFORMANCE REPORT
==========================

Strategy: {result.portfolio.__class__.__name__}
Backtest Period: {result.start_time} to {result.end_time}
Total Ticks: {result.total_ticks:,}

FINANCIAL METRICS
-----------------
Initial Capital:     ${result.performance_metrics.get('initial_capital', 0):,.2f}
Final Equity:        ${result.portfolio.get_total_equity():,.2f}
Total Return:        {result.performance_metrics['total_return']:.2f}%
Total P&L:           ${result.performance_metrics['total_pnl']:,.2f}
Max Drawdown:        {result.performance_metrics['max_drawdown']:.2f}%
Sharpe Ratio:        {result.performance_metrics['sharpe_ratio']:.2f}

TRADING METRICS
---------------
Total Trades:        {result.performance_metrics['total_trades']}
Win Rate:            {result.performance_metrics['win_rate']:.2f}%
Avg Trade P&L:       ${result.performance_metrics.get('avg_trade_pnl', 0):,.2f}
Best Trade:          ${result.performance_metrics.get('best_trade', 0):,.2f}
Worst Trade:         ${result.performance_metrics.get('worst_trade', 0):,.2f}

FILES GENERATED
---------------
- {output_dir}/metrics.json
- {output_dir}/equity_curve.csv
- {output_dir}/all_trades.csv
- {output_dir}/equity_and_drawdown.png
- {output_dir}/trade_distribution.png
- {output_dir}/summary.txt
"""

    with open(f'{output_dir}/summary.txt', 'w') as f:
        f.write(summary)

    print(summary)
    print(f"\nAnalysis complete! Results saved to {output_dir}/")

# Usage
from AlpacaTrading.backtesting.engine import BacktestEngine

result = engine.run()
analyze_strategy_performance(result, output_dir='logs/momentum_strategy')
```

---

## 7. Compare Multiple Strategies

```python
def compare_strategies(results_dict):
    """
    Compare performance of multiple strategies.

    Args:
        results_dict: Dictionary of {strategy_name: BacktestResult}
    """
    comparison = []

    for name, result in results_dict.items():
        metrics = result.performance_metrics
        comparison.append({
            'Strategy': name,
            'Return (%)': metrics['total_return'],
            'P&L ($)': metrics['total_pnl'],
            'Sharpe': metrics['sharpe_ratio'],
            'Max DD (%)': metrics['max_drawdown'],
            'Win Rate (%)': metrics['win_rate'],
            'Total Trades': metrics['total_trades']
        })

    df = pd.DataFrame(comparison)
    df = df.sort_values('Return (%)', ascending=False)

    print("\nSTRATEGY COMPARISON")
    print("=" * 80)
    print(df.to_string(index=False))

    df.to_csv('logs/strategy_comparison.csv', index=False)

    # Plot comparison
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    axes[0, 0].bar(df['Strategy'], df['Return (%)'])
    axes[0, 0].set_title('Total Return')
    axes[0, 0].set_ylabel('%')
    axes[0, 0].tick_params(axis='x', rotation=45)

    axes[0, 1].bar(df['Strategy'], df['Sharpe'])
    axes[0, 1].set_title('Sharpe Ratio')
    axes[0, 1].tick_params(axis='x', rotation=45)

    axes[1, 0].bar(df['Strategy'], df['Win Rate (%)'])
    axes[1, 0].set_title('Win Rate')
    axes[1, 0].set_ylabel('%')
    axes[1, 0].tick_params(axis='x', rotation=45)

    axes[1, 1].bar(df['Strategy'], df['Max DD (%)'])
    axes[1, 1].set_title('Max Drawdown')
    axes[1, 1].set_ylabel('%')
    axes[1, 1].tick_params(axis='x', rotation=45)

    plt.tight_layout()
    plt.savefig('logs/strategy_comparison.png', dpi=150)
    plt.show()

# Usage
results = {
    'Momentum': momentum_result,
    'RSI': rsi_result,
    'BollingerBands': bb_result,
    'VolumeBreakout': vol_result
}
compare_strategies(results)
```

---

## Summary

**You have access to**:
- ✅ Every order with timestamps, prices, quantities (CSV)
- ✅ Strategy signals with indicator values (logs)
- ✅ Complete trade history (in-memory, exportable to CSV)
- ✅ Equity curve over time (DataFrame)
- ✅ Performance metrics (dict/JSON)
- ✅ Portfolio positions and P&L (Portfolio object)

**You can reconstruct**:
- Individual trade P&L
- Round-trip trade performance
- Strategy signal accuracy
- Risk metrics (drawdown, Sharpe, volatility)
- Time-series performance
- Comparative strategy performance

All logging is **already built-in** and works automatically!
