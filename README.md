# Alpaca Trading System - FINM 32500

A professional-grade algorithmic trading and backtesting system built for the Alpaca Trading Competition.

## 🎯 Project Overview

This project implements a complete end-to-end trading system with:
- **Robust Backtesting Engine** - Simulate trading strategies on historical data
- **Risk Management** - Position limits, capital checks, rate limiting
- **Order Management** - Validation, logging, execution simulation
- **Strategy Framework** - Easy-to-extend base classes for custom strategies
- **Performance Analytics** - P&L tracking, Sharpe ratio, drawdown analysis
- **Alpaca Integration** - Ready for live paper trading (coming soon)

Built with performance, reliability, and extensibility in mind.

## 🚀 Quick Start

### 1. Environment Setup

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Alpaca API

```bash
# Copy environment template
cp .env.example .env

# Edit .env and add your Alpaca API keys
# Get keys from: https://app.alpaca.markets/paper/dashboard/overview
```

### 3. Run Example Backtest

```bash
# Run momentum strategy backtest
python examples/backtest_example.py --strategy momentum

# Compare multiple strategies
python examples/backtest_example.py --strategy compare

# Save results to CSV
python examples/backtest_example.py --strategy momentum --save
```

## 📊 System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Trading System                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Data Gateway → Strategy → Order Manager → Matching Engine      │
│                              ↓                    ↓              │
│                        Order Gateway         Portfolio           │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Core Components

| Component | Purpose | Location |
|-----------|---------|----------|
| **DataGateway** | Stream market data from CSV | `src/gateway/data_gateway.py` |
| **OrderGateway** | Log all order events | `src/gateway/order_gateway.py` |
| **OrderBook** | Heap-based order matching | `src/trading/order_book.py` |
| **OrderManager** | Risk validation | `src/trading/order_manager.py` |
| **MatchingEngine** | Execution simulator | `src/trading/matching_engine.py` |
| **TradingPortfolio** | Position & P&L tracking | `src/trading/portfolio.py` |
| **BacktestEngine** | Main orchestrator | `src/backtesting/engine.py` |
| **TradingStrategy** | Strategy base class | `src/strategies/base.py` |

## 💡 Creating a Custom Strategy

```python
from src.models import MarketDataPoint, Order, OrderSide, OrderType
from src.trading.portfolio import TradingPortfolio
from src.strategies.base import TradingStrategy

class MyStrategy(TradingStrategy):
    """Your custom strategy."""

    def on_market_data(self, tick: MarketDataPoint, portfolio: TradingPortfolio) -> list[Order]:
        """
        Generate orders based on market data.

        Args:
            tick: Current market tick (timestamp, symbol, price, volume)
            portfolio: Current portfolio state

        Returns:
            List of orders to submit
        """
        orders = []

        # Your logic here
        if self.should_buy(tick, portfolio):
            orders.append(Order(
                symbol=tick.symbol,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=100
            ))

        return orders
```

## 📈 Running a Backtest

```python
from src.gateway.data_gateway import DataGateway
from src.backtesting.engine import BacktestEngine
from src.trading.order_manager import RiskConfig

# Load market data
data = DataGateway("data/market_data.csv")

# Configure your strategy
strategy = MyStrategy()

# Set risk parameters
risk_config = RiskConfig(
    max_position_size=100,
    max_position_value=50_000,
    max_orders_per_minute=50
)

# Create and run backtest
engine = BacktestEngine(
    data_gateway=data,
    strategy=strategy,
    initial_cash=100_000,
    risk_config=risk_config
)

result = engine.run()

# Analyze results
print(f"Total Return: {result.performance_metrics['total_return']:.2f}%")
print(f"Sharpe Ratio: {result.performance_metrics['sharpe_ratio']:.2f}")
print(f"Max Drawdown: {result.performance_metrics['max_drawdown']:.2f}%")
```

## 🛡️ Risk Management

The system includes comprehensive risk checks:

- **Capital Sufficiency**: Ensures enough cash for orders
- **Position Limits**: Max size per symbol and total exposure
- **Rate Limiting**: Prevents order spam (orders per minute)
- **Order Validation**: Checks before execution

Configure via `RiskConfig`:

```python
from src.trading.order_manager import RiskConfig

config = RiskConfig(
    max_position_size=1000,           # Max shares per symbol
    max_position_value=100_000,       # Max $ per symbol
    max_total_exposure=500_000,       # Max total portfolio exposure
    max_orders_per_minute=100,        # Global rate limit
    max_orders_per_symbol_per_minute=20,  # Per-symbol rate limit
    min_cash_buffer=5000             # Safety buffer
)
```

## 📊 Performance Metrics

The system tracks comprehensive performance metrics:

- **Returns**: Total return, P&L (realized + unrealized)
- **Trade Stats**: Win rate, avg win/loss, number of trades
- **Risk Metrics**: Max drawdown, Sharpe ratio
- **Equity Curve**: Portfolio value over time

## 🧪 Testing

```bash
# Run integration tests
source .venv/bin/activate
python -m unittest tests.test_integration

# Run all tests
python run_tests.py
```

## 📁 Project Structure

```
.
├── src/
│   ├── models.py              # Data models (Order, Trade, Position)
│   ├── gateway/               # Data and order gateways
│   ├── trading/               # Order book, manager, matching engine, portfolio
│   ├── strategies/            # Strategy base class and implementations
│   ├── backtesting/           # Backtesting engine
│   └── analytics/             # Performance metrics (coming soon)
├── examples/
│   └── backtest_example.py    # Complete backtest example
├── tests/
│   └── test_integration.py    # Integration tests
├── logs/                      # Order logs (auto-created)
├── results/                   # Backtest results (auto-created)
└── data/                      # Market data files
```

## 📚 Example Strategies

### 1. Momentum Strategy

Trades based on price velocity:
- Buys when momentum > threshold (uptrend)
- Sells when momentum < threshold (downtrend)

```python
from src.strategies.momentum import MomentumStrategy

strategy = MomentumStrategy(
    lookback_period=20,
    momentum_threshold=0.015,  # 1.5%
    position_size=5000,
    max_position=50
)
```

### 2. Moving Average Crossover

Classic mean reversion strategy:
- Golden Cross: Short MA > Long MA → BUY
- Death Cross: Short MA < Long MA → SELL

```python
from src.strategies.mean_reversion import MovingAverageCrossoverStrategy

strategy = MovingAverageCrossoverStrategy(
    short_window=10,
    long_window=30,
    position_size=8000,
    max_position=75
)
```

## 🎯 Trading Competition Workflow

1. **Data Collection**: Fetch historical data from Alpaca or other sources
2. **Strategy Development**: Create and backtest your strategy
3. **Optimization**: Tune parameters based on backtest results
4. **Risk Testing**: Verify risk limits are appropriate
5. **Paper Trading**: Deploy to Alpaca paper trading (coming soon)
6. **Monitor**: Track live performance and adjust

## 📝 Data Format

Market data CSV should have these columns:
- `timestamp` (or `Datetime`): ISO format timestamp
- `symbol`: Asset symbol (e.g., 'AAPL', 'BTCUSD')
- `price` (or `Close`): Price data
- `volume` (optional): Volume data

Example:
```csv
timestamp,symbol,price,volume
2024-01-01T09:30:00,AAPL,150.25,1000000
2024-01-01T09:30:01,AAPL,150.30,950000
```

## 🔧 Advanced Configuration

### Matching Engine

Control execution simulation:

```python
from src.trading.matching_engine import MatchingEngine

engine = MatchingEngine(
    fill_probability=0.90,         # 90% full fill
    partial_fill_probability=0.08, # 8% partial fill
    cancel_probability=0.02,       # 2% cancelled
    market_impact=0.0001          # 0.01% slippage
)
```

### Order Logging

All order events are logged to CSV:
- Order submission (SENT)
- Modifications (MODIFIED)
- Fills (FILLED, PARTIAL_FILL)
- Cancellations (CANCELLED)
- Rejections (REJECTED)

View logs in `logs/orders.csv` after backtest.

## 🚧 Coming Soon

- [ ] Alpaca live trading integration
- [ ] Real-time visualization dashboard
- [ ] Multi-asset portfolio optimization
- [ ] Machine learning strategy templates
- [ ] Advanced analytics (factor analysis, attribution)

## 🤝 Contributing

This is a class project, but suggestions are welcome! Please test thoroughly before submitting changes.

## 📄 License

Academic project for FINM 32500.

## ⚠️ Disclaimer

This is educational software. Do not use for live trading without thorough testing and risk management. Never risk money you cannot afford to lose.
