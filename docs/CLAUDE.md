# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an **End-to-End Algorithmic Trading System** for the FINM 32500 Alpaca Trading Competition. The project implements a professional-grade trading and backtesting infrastructure with comprehensive risk management, order execution simulation, and performance analytics.

**Key Features:**
- Modular backtesting engine with realistic order execution
- Heap-based order book with price-time priority matching
- Risk management (capital checks, position limits, rate limiting)
- Complete order lifecycle tracking and logging
- Portfolio management with P&L calculation
- Extensible strategy framework
- Performance analytics (Sharpe, drawdown, win rate, etc.)
- Support for both equities and crypto assets

## Development Setup

### Environment
```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies (already done if venv exists)
pip install -r requirements.txt
```

### Alpaca API Setup
API credentials are configured in `.env` (never commit this file):
- Get keys from https://app.alpaca.markets/paper/dashboard/overview
- Use paper trading only
- See SETUP_CREDENTIALS.md for details

## Common Commands

### Run Backtests
```bash
# Run example backtest with momentum strategy
python examples/backtest_example.py --strategy momentum

# Compare multiple strategies
python examples/backtest_example.py --strategy compare

# Save results to CSV
python examples/backtest_example.py --strategy momentum --save
```

### Testing
```bash
# Run integration tests
source .venv/bin/activate
python -m unittest tests.test_integration

# Run specific test
python -m unittest tests.test_integration.TestTradingSystemIntegration.test_order_lifecycle
```

### Data Ingestion
```bash
# Equities (yfinance)
cd equities_data
python equities_data_ingestion_&_cleaning.py

# Crypto (Binance)
cd crypto_data
python crypto_data_ingestion
```

## System Architecture

### High-Level Flow

```
Market Data → DataGateway → Strategy → OrderManager (validation)
                               ↓              ↓
                          OrderGateway   MatchingEngine
                            (logs)         (executes)
                               ↓              ↓
                          Order Log      Portfolio
                           (CSV)         (P&L tracking)
```

### Core Components

#### 1. Data Models (`src/models.py`)

**Key Classes:**
- `Order`: Enhanced order with order_id, status, fills (supports MARKET/LIMIT orders)
- `Trade`: Represents executed trades (may be multiple per order for partials)
- `Position`: Tracks positions with realized/unrealized P&L
- `MarketDataPoint`: Immutable market tick data
- `OrderStatus`, `OrderSide`, `OrderType`: Enums for type safety

**Important**: The file contains legacy classes for backward compatibility with old strategies. New code should use the enhanced versions.

#### 2. Gateway Layer (`src/gateway/`)

**DataGateway** (`data_gateway.py`):
- Streams historical CSV data row-by-row to simulate live feed
- Supports flexible CSV formats (timestamp/Datetime, price/Close columns)
- Methods: `stream()`, `get_current_price()`, `load_all()`, `get_symbols()`
- Key feature: Maintains current price cache for all symbols

**OrderGateway** (`order_gateway.py`):
- Logs ALL order lifecycle events to CSV for audit trail
- Events: SENT, MODIFIED, PARTIAL_FILL, FILLED, CANCELLED, REJECTED
- Methods: `log_order_sent()`, `log_order_filled()`, `log_order_rejected()`, etc.
- Output: CSV file with complete order history

#### 3. Trading Layer (`src/trading/`)

**OrderBook** (`order_book.py`):
- Heap-based bid/ask order matching with O(log n) insertion
- Price-time priority: best price first, then FIFO
- Supports partial fills and order cancellation
- Methods: `add_order()`, `match_orders()`, `cancel_order()`, `get_best_bid/ask()`
- Note: Market orders should go directly to MatchingEngine, only limit orders in book

**OrderManager** (`order_manager.py`):
- Validates orders against risk limits BEFORE submission
- Checks: capital sufficiency, position limits, rate limits, total exposure
- Uses `RiskConfig` for configuration (max_position_size, max_orders_per_minute, etc.)
- Methods: `validate_order()`, `record_order()`, `get_order_rate_stats()`
- Critical: Call `record_order()` AFTER successful submission for rate limiting

**MatchingEngine** (`matching_engine.py`):
- Simulates realistic order execution with probabilistic fills
- Default: 85% full fill, 10% partial fill (50-90% of quantity), 5% cancelled
- Applies market impact/slippage to market orders
- Methods: `execute_order()`, `set_probabilities()`
- Returns: List of `Trade` objects

**TradingPortfolio** (`portfolio.py`):
- Tracks cash, positions, trades, and equity curve
- Automatically calculates realized/unrealized P&L
- Methods: `process_trade()`, `update_prices()`, `record_equity()`, `get_performance_metrics()`
- Performance metrics: return, P&L, win rate, Sharpe, max drawdown

#### 4. Strategy Layer (`src/strategies/`)

**TradingStrategy** (`base.py`):
- Abstract base class for all strategies
- Must implement: `on_market_data(tick, portfolio) -> list[Order]`
- Optional hooks: `on_start()`, `on_end()`

**Example Strategies:**
- `MomentumStrategy` (`momentum.py`): Trades based on price velocity
- `MovingAverageCrossoverStrategy` (`mean_reversion.py`): MA golden/death cross

**Creating New Strategies:**
1. Inherit from `TradingStrategy`
2. Implement `on_market_data()` to return list of orders
3. Maintain any state (price history, indicators) in instance variables
4. Use `portfolio.get_position(symbol)` to check current positions

#### 5. Backtesting Engine (`src/backtesting/engine.py`)

**BacktestEngine**:
- Main orchestrator that ties all components together
- Main loop: data → strategy → validation → execution → portfolio update → logging
- Configuration: `DataGateway`, `TradingStrategy`, `RiskConfig`, `MatchingEngine`
- Methods: `run(max_ticks=None)` returns `BacktestResult`
- Prints progress every 10k ticks and detailed summary at end

**BacktestResult**:
- Contains: portfolio, trades, performance_metrics, equity_curve, order_log_path
- Performance metrics include: returns, P&L, trade stats, Sharpe, drawdown

## Design Patterns and Best Practices

### Order Lifecycle
1. Strategy generates `Order` (status=NEW)
2. `OrderManager.validate_order()` checks risk limits
3. If valid: `OrderManager.record_order()` for rate limiting
4. `OrderGateway.log_order_sent()` logs submission
5. `MatchingEngine.execute_order()` simulates fills → returns `Trade` list
6. `Portfolio.process_trade()` updates positions and cash
7. `OrderGateway.log_order_filled/partial/cancelled()` logs outcome

### Position P&L Calculation
- **Opening**: Set quantity and average_cost
- **Adding**: Update average_cost = (old_value + new_value) / new_quantity
- **Reducing**: Realize P&L on closed portion, keep average_cost for remaining
- **Reversing**: Realize all P&L, start new position at trade price
- Call `position.update_unrealized_pnl(current_price)` each tick

### Risk Management Flow
OrderManager validates BEFORE execution:
1. Rate limits (orders/minute globally and per-symbol)
2. Capital sufficiency (ensure cash - buffer >= order_value)
3. Position limits (max shares and max $ per symbol)
4. Total exposure (sum of all position values)

Rejected orders are logged but not executed.

### Strategy Development Tips
- Use `collections.deque(maxlen=N)` for efficient windowed history
- Check `len(price_history)` before calculating indicators
- Use `portfolio.get_position(symbol)` to avoid KeyError
- Return empty list `[]` when no signals (don't return None)
- Market orders: don't specify price. Limit orders: must specify price

## File Organization

```
src/
├── models.py                    # Core data models and enums
├── gateway/
│   ├── data_gateway.py          # Market data streaming
│   └── order_gateway.py         # Order event logging
├── trading/
│   ├── order_book.py            # Heap-based order matching
│   ├── order_manager.py         # Risk validation
│   ├── matching_engine.py       # Execution simulation
│   └── portfolio.py             # Position & P&L tracking
├── strategies/
│   ├── base.py                  # Abstract strategy class
│   ├── momentum.py              # Momentum strategy
│   └── mean_reversion.py        # MA crossover strategy
└── backtesting/
    └── engine.py                # Main backtesting orchestrator

examples/
└── backtest_example.py          # Complete usage example

tests/
└── test_integration.py          # Integration tests
```

## Testing Strategy

**Integration Tests** (`tests/test_integration.py`):
- Test individual components: Order, Portfolio, OrderManager
- Test component interaction: order validation, execution, portfolio updates
- Test full backtest with limited data (max_ticks=100)
- Run with: `python -m unittest tests.test_integration`

**Legacy Tests** (old moving average strategies):
- `tests/test_strategy_correctness.py`: Verify optimized strategies match baseline
- `tests/test_performance.py`: Benchmark execution time
- `tests/test_profiling.py`: Memory profiling
- Run with: `python run_tests.py [correctness|performance|profiling]`

## Key Configuration Options

### RiskConfig Parameters
```python
RiskConfig(
    max_position_size=1000,              # Max shares per symbol
    max_position_value=100_000,          # Max $ per symbol
    max_total_exposure=500_000,          # Max total portfolio $
    max_orders_per_minute=100,           # Global order rate
    max_orders_per_symbol_per_minute=20, # Per-symbol order rate
    min_cash_buffer=5000                 # Safety cash buffer
)
```

### MatchingEngine Probabilities
```python
MatchingEngine(
    fill_probability=0.85,           # 85% chance of full fill
    partial_fill_probability=0.10,   # 10% chance of 50-90% fill
    cancel_probability=0.05,         # 5% chance of cancel
    market_impact=0.0002            # 0.02% slippage on market orders
)
```

## Data Requirements

**CSV Format for DataGateway:**
- Required columns: `timestamp` (or Datetime), `symbol`, `price` (or Close)
- Optional: `volume`, `open`, `high`, `low`
- Timestamps: ISO format or pandas-parseable
- Multiple symbols: Include all in one file, sorted by timestamp

**Example:**
```csv
timestamp,symbol,price,volume
2024-01-01T09:30:00,AAPL,150.25,1000000
2024-01-01T09:30:01,AAPL,150.30,950000
2024-01-01T09:30:00,MSFT,380.50,500000
```

## Common Gotchas

1. **Order price for market orders**: Set `price=None` for MARKET orders, required for LIMIT
2. **Portfolio methods**: `get_position()` returns None if no position, always check
3. **Rate limiting**: Call `OrderManager.record_order()` AFTER successful submission, not before
4. **Position quantity**: Positive = long, negative = short, zero = flat
5. **Equity curve**: Call `portfolio.record_equity()` periodically, not every tick (expensive)
6. **Order status**: Check `order.is_filled` property rather than comparing filled_quantity
7. **Trade execution**: One order can produce multiple trades (partial fills)

## Performance Considerations

- **DataGateway**: Use `stream()` for memory efficiency, not `load_all()` for large files
- **Strategy history**: Use `deque(maxlen=N)` to bound memory, don't store unlimited history
- **Equity recording**: Record every 100-1000 ticks, not every tick
- **OrderBook**: Cancelled orders stay in heap until matched (lazy deletion)
- **Portfolio metrics**: `get_performance_metrics()` iterates all positions, don't call every tick

## Dependencies

Core libraries:
- `pandas`: Data manipulation and time series
- `numpy`: Numerical computations for strategies
- `alpaca-py`: Alpaca API integration (for live trading)
- `python-dotenv`: Environment variable management

Python 3.13+ required (uses modern type hints).

## Next Steps for Development

Current system supports backtesting. To add live trading:
1. Create `src/live/alpaca_trader.py` module
2. Implement `AlpacaTrader` class with `stream_market_data()` and `submit_order()`
3. Create live trading mode in BacktestEngine or new LiveEngine class
4. Add real-time monitoring and error recovery
5. Test extensively in paper trading before any real money

See ARCHITECTURE.md for detailed component design specifications.
