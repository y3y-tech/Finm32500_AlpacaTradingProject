# Logging Configuration Summary

This document describes the logging setup implemented across the AlpacaTrading project.

## Overview

All logging in the project now:
- ✅ Writes to timestamped log files in `logs/` directory
- ✅ Never overwrites older logs
- ✅ Outputs to both console and file by default
- ✅ Uses proper log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)

## Log File Location

All log files are stored in the `logs/` directory with timestamped filenames:
```
logs/alpaca_trading_YYYYMMDD_HHMMSS.log
```

For example:
- `logs/alpaca_trading_20251201_094943.log`
- `logs/alpaca_trading_20251201_095010.log`

Each run creates a new log file, so logs are never overwritten.

## Usage

### Basic Setup

```python
from AlpacaTrading.logging_config import setup_logging

# Setup with default INFO level, writes to timestamped file + console
setup_logging()

# Setup with DEBUG level
setup_logging(level="DEBUG")

# Setup with custom log file name
setup_logging(log_file="logs/my_custom_log.log")

# Setup without console output (file only)
setup_logging(console_output=False)
```

### Using Loggers in Modules

Every module under `src/AlpacaTrading/` now has logging configured:

```python
import logging

logger = logging.getLogger(__name__)

# Use appropriate log levels
logger.debug("Detailed debugging information")
logger.info("General information about execution")
logger.warning("Warning messages for unexpected situations")

# For errors in exception handlers, use logger.exception()
try:
    risky_operation()
except Exception as e:
    logger.exception(f"Operation failed: {e}")  # Automatically includes traceback

# For critical errors
logger.critical("Critical failures", exc_info=True)  # Use exc_info=True for CRITICAL
```

**Best Practice:** Use `logger.exception()` instead of `logger.error(..., exc_info=True)` when logging from inside exception handlers. It's more idiomatic and cleaner.

## Files Modified

### Core Configuration
- **`src/AlpacaTrading/logging_config.py`**: Updated to always write to timestamped log files by default

### Files with Print Statements Replaced
1. **`src/AlpacaTrading/backtesting/engine.py`**: All print statements replaced with logger.info/debug
2. **`src/AlpacaTrading/profiler.py`**: Print replaced with logger.info
3. **`src/AlpacaTrading/live/live_engine_crypto.py`**: All 40+ print statements replaced with appropriate log levels:
   - Info messages → logger.info()
   - Errors in exception handlers → logger.exception()
   - Warnings → logger.warning()
   - Debug info → logger.debug()
   - Critical failures → logger.critical(exc_info=True)
   - Removed duplicate traceback.print_exc() calls

### Files with Logging Added
All files under `src/AlpacaTrading/` now import logging and create a module logger:
- models.py
- gateway/data_gateway.py
- gateway/order_gateway.py
- trading/order_book.py
- trading/order_manager.py
- trading/matching_engine.py
- trading/portfolio.py
- trading/risk_manager.py
- strategies/base.py
- strategies/momentum.py
- strategies/mean_reversion.py
- live/alpaca_trader.py (already had logging)
- live/alpaca_trader_crypto.py
- live/live_engine.py (already had logging)

## Log Levels Used

The project uses the following log level conventions:

- **DEBUG**: Detailed diagnostic information (e.g., "TICK RECEIVED: BTC/USD @ 45000.0")
- **INFO**: General informational messages (e.g., "Order SUBMITTED", "Backtest Complete", progress updates)
- **WARNING**: Warning messages for non-critical issues (e.g., "Order REJECTED", "STOP-LOSS TRIGGERED", timeouts)
- **ERROR**: Error messages for failures (e.g., "Order FAILED", "Error processing market data")
- **CRITICAL**: Critical failures that halt execution (e.g., "CIRCUIT BREAKER ACTIVE", fatal errors)

## Log Format

All logs use a consistent format:
```
YYYY-MM-DD HH:MM:SS | LEVEL    | module.name | message
```

Example:
```
2025-12-01 09:49:43 | INFO     | AlpacaTrading.backtesting.engine | Starting backtest at 2025-12-01 09:49:43
2025-12-01 09:49:43 | WARNING  | AlpacaTrading.trading.order_manager | Order REJECTED: Rate limit exceeded
2025-12-01 09:49:43 | ERROR    | AlpacaTrading.live.live_engine_crypto | Order FAILED: Connection timeout
```

## Git Configuration

The `logs/` directory has a `.gitignore` file that excludes all `.log` files from version control:
```gitignore
# Ignore all log files
*.log

# But keep this .gitignore file
!.gitignore
```

## Benefits

1. **Complete Audit Trail**: All execution details are logged to files with timestamps
2. **No Lost Logs**: Timestamped filenames ensure logs are never overwritten
3. **Easy Debugging**: Different log levels help filter relevant information
4. **Production Ready**: Proper logging instead of print statements allows for better monitoring
5. **Structured Logging**: Consistent format across all modules makes parsing easier
6. **Proper Exception Logging**: Uses `logger.exception()` for automatic traceback inclusion
7. **Appropriate Log Levels**: DEBUG for diagnostics, INFO for operations, WARNING for issues, ERROR for failures, CRITICAL for fatal problems

## Related Documentation

See **`LOG_LEVELS_GUIDE.md`** for detailed guidance on when to use each log level and best practices.

## Testing

Run any backtest or trading script and check the `logs/` directory for the timestamped log file.

Example:
```bash
python examples/backtest_example.py
# Check logs/alpaca_trading_YYYYMMDD_HHMMSS.log for complete execution log
```
