# Trading System Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Trading System                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐  │
│  │   Strategy   │─────▶│   Gateway    │◀────▶│ Market Data  │  │
│  │              │      │  (Data In)   │      │   Source     │  │
│  └──────────────┘      └──────────────┘      └──────────────┘  │
│         │                                                         │
│         │ Signals                                                │
│         ▼                                                         │
│  ┌──────────────┐      ┌──────────────┐                         │
│  │    Order     │─────▶│   Gateway    │                         │
│  │   Manager    │      │ (Order Out)  │                         │
│  └──────────────┘      └──────────────┘                         │
│         │                     │                                  │
│         │ Validated           │ Logged                           │
│         ▼                     ▼                                  │
│  ┌──────────────┐      ┌──────────────┐                         │
│  │   Matching   │      │  Order Log   │                         │
│  │    Engine    │      │    (CSV)     │                         │
│  └──────────────┘      └──────────────┘                         │
│         │                                                         │
│         │ Fills                                                  │
│         ▼                                                         │
│  ┌──────────────┐      ┌──────────────┐                         │
│  │  Portfolio   │─────▶│ Performance  │                         │
│  │   Tracker    │      │  Analytics   │                         │
│  └──────────────┘      └──────────────┘                         │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Component Design

### 1. Data Models (`src/models.py`)

Enhanced models to support full trading lifecycle:

**MarketDataPoint** (existing - keep as is)
- Immutable market tick data
- Fields: timestamp, symbol, price

**Order** (enhanced)
```python
@dataclass
class Order:
    order_id: str                    # Unique identifier
    timestamp: datetime              # Order creation time
    symbol: str                      # Asset symbol
    side: str                        # 'BUY' or 'SELL'
    order_type: str                  # 'MARKET', 'LIMIT'
    quantity: float                  # Shares/coins to trade
    price: float | None              # Limit price (None for market orders)
    status: OrderStatus              # NEW, PARTIAL, FILLED, CANCELLED
    filled_quantity: float = 0.0     # Amount filled so far
    average_fill_price: float = 0.0  # Average price of fills
```

**Trade** (new)
```python
@dataclass
class Trade:
    trade_id: str
    order_id: str
    timestamp: datetime
    symbol: str
    side: str
    quantity: float
    price: float
```

**Position** (enhanced)
```python
class Position:
    symbol: str
    quantity: float                   # Net position (+ long, - short)
    average_cost: float               # Average entry price
    realized_pnl: float               # Closed P&L
    unrealized_pnl: float             # Open P&L
```

### 2. Market Data Gateway (`src/gateway/data_gateway.py`)

**Purpose**: Stream historical data to simulate live feed

```python
class DataGateway:
    def __init__(self, data_source: str):
        """Initialize with CSV file path"""

    def start_stream(self) -> Iterator[MarketDataPoint]:
        """Yield market data points one at a time"""

    def get_current_price(self, symbol: str) -> float:
        """Get latest price for a symbol"""
```

**Features**:
- Row-by-row CSV streaming
- Timestamp-based playback
- Support for multiple symbols
- Fast-forward and replay capabilities

### 3. Order Book (`src/trading/order_book.py`)

**Purpose**: Maintain and match bid/ask orders with price-time priority

```python
class OrderBook:
    def __init__(self, symbol: str):
        self.bids: list = []  # Max heap (price, time, order)
        self.asks: list = []  # Min heap (price, time, order)

    def add_order(self, order: Order) -> None:
        """Add order to appropriate side"""

    def match_orders(self) -> list[Trade]:
        """Match crossing orders, return trades"""

    def cancel_order(self, order_id: str) -> bool:
        """Remove order from book"""

    def get_best_bid(self) -> float | None:
        """Get highest bid price"""

    def get_best_ask(self) -> float | None:
        """Get lowest ask price"""
```

**Implementation**:
- Use Python `heapq` for O(log n) insertion
- Price-time priority matching
- Support for partial fills

### 4. Order Manager (`src/trading/order_manager.py`)

**Purpose**: Validate orders before submission

```python
class OrderManager:
    def __init__(self, risk_config: RiskConfig):
        self.risk_config = risk_config
        self.order_count = {}  # Track orders per minute

    def validate_order(self, order: Order, portfolio: Portfolio) -> tuple[bool, str]:
        """
        Validate order against:
        1. Capital sufficiency
        2. Position limits (max long/short)
        3. Order rate limits (orders per minute)

        Returns: (is_valid, error_message)
        """
```

**Risk Checks**:
- Capital: `order_value <= available_cash`
- Position limits: `new_position <= max_position_size`
- Rate limits: `orders_per_minute <= max_rate`

### 5. Matching Engine (`src/trading/matching_engine.py`)

**Purpose**: Simulate realistic order execution

```python
class MatchingEngine:
    def __init__(self, fill_probability: float = 0.95):
        """Initialize with fill probability settings"""

    def execute_order(self, order: Order, market_price: float) -> list[Trade]:
        """
        Simulate order execution:
        - Random fill/partial fill/cancel based on probabilities
        - Add realistic slippage for market orders
        - Return list of trades (empty if cancelled)
        """
```

**Simulation Logic**:
- 85% full fill
- 10% partial fill (50-90% of quantity)
- 5% cancelled
- Market orders: add 0.01-0.05% slippage

### 6. Order Gateway (`src/gateway/order_gateway.py`)

**Purpose**: Log all order lifecycle events

```python
class OrderGateway:
    def __init__(self, log_file: str):
        """Initialize with order log CSV path"""

    def log_order_event(self, event_type: str, order: Order) -> None:
        """
        Log events: SENT, MODIFIED, CANCELLED, FILLED, PARTIAL_FILL
        Append to CSV with: timestamp, event_type, order_id, symbol, side, quantity, price, status
        """
```

### 7. Portfolio (`src/trading/portfolio.py`)

**Purpose**: Track positions, cash, and P&L

```python
class Portfolio:
    def __init__(self, initial_cash: float):
        self.cash: float
        self.positions: dict[str, Position]
        self.trades: list[Trade]
        self.equity_curve: list[tuple[datetime, float]]

    def process_trade(self, trade: Trade) -> None:
        """Update position and cash based on trade"""

    def get_total_value(self, current_prices: dict[str, float]) -> float:
        """Calculate total portfolio value"""

    def get_metrics(self) -> PerformanceMetrics:
        """Calculate Sharpe, drawdown, win rate, etc."""
```

### 8. Strategy Base (`src/strategies/base.py`)

**Purpose**: Abstract interface for all strategies

```python
class TradingStrategy(ABC):
    @abstractmethod
    def on_market_data(self, tick: MarketDataPoint, portfolio: Portfolio) -> list[Order]:
        """Generate orders based on new market data"""
        pass
```

**Example Strategies**:
- `MomentumStrategy`: Trade based on price velocity
- `MeanReversionStrategy`: Trade on MA crossovers
- `MLStrategy`: Use trained model for predictions

### 9. Backtesting Engine (`src/backtesting/engine.py`)

**Purpose**: Orchestrate full simulation

```python
class BacktestEngine:
    def __init__(
        self,
        strategy: TradingStrategy,
        data_gateway: DataGateway,
        order_manager: OrderManager,
        matching_engine: MatchingEngine,
        initial_cash: float
    ):
        """Initialize all components"""

    def run(self) -> BacktestResult:
        """
        Main loop:
        1. Get next market tick from data gateway
        2. Update portfolio with current prices
        3. Strategy generates signals
        4. Order manager validates orders
        5. Matching engine executes orders
        6. Portfolio processes trades
        7. Log everything

        Returns: BacktestResult with metrics and trades
        """
```

### 10. Performance Analytics (`src/analytics/metrics.py`)

**Purpose**: Calculate trading performance metrics

```python
class PerformanceAnalytics:
    @staticmethod
    def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
        """Annualized Sharpe ratio"""

    @staticmethod
    def calculate_max_drawdown(equity_curve: pd.Series) -> float:
        """Maximum drawdown percentage"""

    @staticmethod
    def calculate_win_rate(trades: list[Trade]) -> float:
        """Percentage of profitable trades"""

    def generate_report(self, backtest_result: BacktestResult) -> Report:
        """Generate comprehensive performance report"""
```

### 11. Alpaca Integration (`src/live/alpaca_trader.py`)

**Purpose**: Connect to Alpaca for live paper trading

```python
class AlpacaTrader:
    def __init__(self, api_key: str, secret_key: str, base_url: str):
        """Initialize Alpaca connection"""

    def stream_market_data(self, symbols: list[str]) -> Iterator[MarketDataPoint]:
        """Stream live market data"""

    def submit_order(self, order: Order) -> str:
        """Submit order to Alpaca, return order_id"""

    def get_positions(self) -> dict[str, Position]:
        """Fetch current positions"""
```

## Data Flow

### Backtesting Mode
1. **Data Gateway** → streams historical data → **Strategy**
2. **Strategy** → generates orders → **Order Manager**
3. **Order Manager** → validates → **Order Gateway** (logs)
4. **Order Manager** → approved orders → **Matching Engine**
5. **Matching Engine** → executes → **Trades**
6. **Trades** → update → **Portfolio**
7. **Portfolio** → metrics → **Performance Analytics**

### Live Trading Mode
1. **Alpaca** → streams real-time data → **Strategy**
2. **Strategy** → generates orders → **Order Manager**
3. **Order Manager** → validates → **Alpaca API** (submit)
4. **Alpaca** → fills → **Portfolio**
5. **Portfolio** → metrics → **Performance Analytics**

## File Structure

```
src/
├── models.py                 # Enhanced data models
├── gateway/
│   ├── __init__.py
│   ├── data_gateway.py       # Market data streaming
│   └── order_gateway.py      # Order logging
├── trading/
│   ├── __init__.py
│   ├── order_book.py         # Heap-based order matching
│   ├── order_manager.py      # Validation and risk checks
│   ├── matching_engine.py    # Execution simulator
│   └── portfolio.py          # Position and P&L tracking
├── strategies/
│   ├── __init__.py
│   ├── base.py              # Abstract base class
│   ├── momentum.py          # Momentum-based strategy
│   └── mean_reversion.py    # MA crossover strategy
├── backtesting/
│   ├── __init__.py
│   └── engine.py            # Main backtesting orchestrator
├── analytics/
│   ├── __init__.py
│   └── metrics.py           # Performance calculations
└── live/
    ├── __init__.py
    └── alpaca_trader.py     # Live trading integration

tests/
├── test_order_book.py
├── test_order_manager.py
├── test_matching_engine.py
├── test_portfolio.py
├── test_backtesting.py
└── test_strategies.py
```

## Key Design Principles

1. **Modularity**: Each component has single responsibility
2. **Testability**: All components can be unit tested independently
3. **Performance**: Use efficient data structures (heaps, deques)
4. **Extensibility**: Easy to add new strategies and risk checks
5. **Realism**: Simulate real trading conditions (slippage, partial fills, latency)
