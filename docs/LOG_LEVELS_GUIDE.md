# Logging Levels Guide

This document provides guidance on when to use each logging level in the AlpacaTrading project.

## Python Logging Levels

Python's logging module has 5 standard levels (from lowest to highest severity):

1. **DEBUG** (10) - Detailed information for diagnosing problems
2. **INFO** (20) - Confirmation that things are working as expected
3. **WARNING** (30) - Indication of unexpected events or problems
4. **ERROR** (40) - Serious problem that prevented a function from executing
5. **CRITICAL** (50) - Very serious error that may prevent the program from continuing

## When to Use Each Level

### DEBUG - Detailed Diagnostic Information
Use for verbose, detailed information that's only useful when diagnosing problems.

**Examples in our codebase:**
- `logger.debug(f"TICK RECEIVED: {tick.symbol} @ {tick.price}")` - Per-tick data stream
- Internal state changes
- Function entry/exit points (if needed)
- Variable values during debugging

**General rules:**
- Should not be visible in normal production runs
- Can be very verbose
- Helps developers understand what's happening step-by-step

### INFO - Normal Operation
Use for important informational messages that track the normal flow of the application.

**Examples in our codebase:**
- `logger.info("Starting backtest at ...")` - System startup
- `logger.info(f"Order SUBMITTED: {order}")` - Successful operations
- `logger.info("FILLED: 100 shares @ $150.00")` - Trade executions
- `logger.info("Backtest Complete!")` - System shutdown
- `logger.info(f"Portfolio Value: $100,000")` - Status updates
- `logger.info("Syncing positions from Alpaca...")` - Data synchronization

**General rules:**
- Default log level for production
- Should provide a good overview of what's happening
- Not too verbose, but enough to track progress
- Should make sense to non-developers

### WARNING - Unexpected But Handled
Use when something unexpected happened, but the software is still working.

**Examples in our codebase:**
- `logger.warning(f"Order REJECTED: Insufficient capital")` - Validation failures
- `logger.warning(f"STOP-LOSS TRIGGERED for {symbol}")` - Risk management events
- `logger.warning("Timeout waiting for fill")` - Timing issues
- `logger.warning(f"Circuit Breaker: TRIGGERED")` - Risk controls activated
- `logger.warning("Received shutdown signal")` - Graceful shutdown requested

**General rules:**
- Something unexpected, but not an error
- The application can continue normally
- May indicate a problem that could become serious
- Should be reviewed periodically

### ERROR - Function Failed
Use when a function failed to execute due to an error, but the application can continue.

**Examples in our codebase (use `logger.exception()` in except blocks):**
- `logger.exception(f"Order FAILED: {e}")` - Order submission failed
- `logger.exception(f"Error processing market data: {e}")` - Data processing error
- `logger.exception(f"Error executing order: {e}")` - Execution failure

**General rules:**
- A specific operation failed
- The application can continue (other operations still work)
- Always log the exception with traceback
- Use `logger.exception()` instead of `logger.error(..., exc_info=True)` inside except blocks

### CRITICAL - Application-Level Failure
Use for very serious errors that may prevent the application from continuing.

**Examples in our codebase:**
- `logger.critical("CIRCUIT BREAKER ACTIVE - Trading halted")` - All trading stopped
- `logger.critical(f"Fatal error: {e}", exc_info=True)` - Unrecoverable errors

**General rules:**
- The application may need to shut down
- Requires immediate attention
- Should trigger alerts in production
- Use `exc_info=True` to include traceback (no `exception()` method at CRITICAL level)

## Best Practices

### 1. Use `logger.exception()` in Exception Handlers

❌ **Don't do this:**
```python
try:
    process_order()
except Exception as e:
    logger.error(f"Order failed: {e}", exc_info=True)
```

✅ **Do this:**
```python
try:
    process_order()
except Exception as e:
    logger.exception(f"Order failed: {e}")
```

**Why?** `logger.exception()` is a convenience method that automatically includes `exc_info=True` and is specifically designed for exception handlers.

### 2. Don't Include Traceback for Non-Exceptions

❌ **Don't do this:**
```python
logger.warning("Order rejected", exc_info=True)  # No exception!
```

✅ **Do this:**
```python
logger.warning(f"Order rejected: {reason}")
```

**Why?** `exc_info=True` only makes sense when there's an actual exception to log.

### 3. Choose the Right Level

❌ **Don't do this:**
```python
logger.error("Order was rejected by risk manager")  # Not an error!
```

✅ **Do this:**
```python
logger.warning(f"Order REJECTED: {reason}")  # Expected validation failure
```

**Why?** Risk management rejections are expected behavior (warnings), not errors.

### 4. Include Context in Log Messages

❌ **Don't do this:**
```python
logger.info("Order submitted")
```

✅ **Do this:**
```python
logger.info(f"Order SUBMITTED: {order.side.value} {order.quantity} {order.symbol} @ {order.order_type.value}")
```

**Why?** Context helps you understand what happened without looking at code.

### 5. Use Appropriate Formatting

✅ **Good examples:**
```python
# Use f-strings for formatting
logger.info(f"Processing {len(orders)} orders")

# Include relevant details
logger.warning(f"Order REJECTED: {reason} - Order: {order.order_id}")

# Use consistent prefixes for filtering
logger.info(f"FILLED: {quantity} @ ${price:.2f}")
logger.warning(f"STOP-LOSS TRIGGERED for {symbol}")
```

## Log Level Summary Table

| Level    | When to Use | Example |
|----------|-------------|---------|
| DEBUG    | Detailed diagnostics | Tick-by-tick data, internal state |
| INFO     | Normal operations | Startup, shutdown, successful operations |
| WARNING  | Unexpected but handled | Rejections, timeouts, risk triggers |
| ERROR    | Function failure | Order failed, data error, execution error |
| CRITICAL | Application failure | Trading halted, fatal errors |

## Current Implementation Status

✅ All files have logging configured
✅ All print statements replaced with appropriate log calls
✅ Exception handlers use `logger.exception()` instead of `logger.error(..., exc_info=True)`
✅ Duplicate `traceback.print_exc()` calls removed
✅ Log levels match severity appropriately

## Testing Different Log Levels

```python
from AlpacaTrading.logging_config import setup_logging

# See everything (DEBUG and above)
setup_logging(level="DEBUG")

# Normal operations (INFO and above) - DEFAULT
setup_logging(level="INFO")

# Only problems (WARNING and above)
setup_logging(level="WARNING")

# Only errors (ERROR and above)
setup_logging(level="ERROR")
```
