# Unit Tests for Financial Signal Processing Strategies

This directory contains comprehensive unit tests for validating the correctness and performance of trading strategies.

## Test Coverage

### 1. Strategy Correctness Tests (`test_strategy_correctness.py`)

Tests that all strategies produce correct and equivalent results:

- **Equivalence Tests**: Verify that optimized strategies produce identical results to baseline
- **Moving Average Calculation**: Validate correct computation of windowed averages
- **Signal Generation Logic**: Test buy/sell signal generation based on price vs average
- **Multiple Symbols**: Ensure strategies handle multiple symbols independently
- **Edge Cases**: Empty data, window size edge cases, numerical precision

**Key Tests:**
- `test_naive_vs_streaming_equivalence()` - Naive and Streaming produce same signals
- `test_windowed_strategies_equivalence()` - All windowed variants produce same signals
- `test_moving_average_calculation()` - Correct average computation
- `test_signal_generation_logic()` - Correct buy/sell signals
- `test_numerical_precision()` - Online algorithms maintain precision

### 2. Performance Validation Tests (`test_performance.py`)

Validates that optimized strategies meet performance requirements:

**Requirements:**
- ✅ Runtime < 1 second for 100,000 ticks
- ✅ Memory usage < 100 MB increase for 100,000 ticks

**Key Tests:**
- `test_online_windowed_runtime_requirement()` - OnlineWindowed < 1s
- `test_streaming_naive_runtime_requirement()` - StreamingNaive < 1s
- `test_online_windowed_memory_requirement()` - Memory < 100MB
- `test_per_tick_performance_consistency()` - O(1) per-tick time
- `test_memory_does_not_grow_unbounded()` - Memory bounded for windowed
- `test_optimized_faster_than_baseline()` - Verify 10x+ speedup

### 3. Profiling Output Validation Tests (`test_profiling.py`)

Tests that profiling tools correctly identify performance characteristics:

**Key Tests:**
- `test_naive_strategy_hotspot_is_calculate_average()` - Profile shows bottleneck
- `test_online_strategy_hotspot_is_generate_signal()` - Profile shows optimization
- `test_baseline_has_more_function_calls_than_optimized()` - Verify call reduction
- `test_profiling_identifies_numpy_overhead_in_baseline()` - NumPy overhead visible
- `test_execution_time_proportional_to_function_calls()` - Time correlates with calls
- `test_profiling_covers_all_strategy_methods()` - Complete coverage

## Running Tests

### Run All Tests

```bash
# From project root
python -m pytest tests/ -v

# Or using unittest
python -m unittest discover tests/ -v
```

### Run Specific Test File

```bash
# Correctness tests
python -m pytest tests/test_strategy_correctness.py -v

# Performance tests
python -m pytest tests/test_performance.py -v

# Profiling tests
python -m pytest tests/test_profiling.py -v
```

### Run Specific Test

```bash
# Run single test
python -m pytest tests/test_correctness.py::TestStrategyCorrectness::test_naive_vs_streaming_equivalence -v

# Or with unittest
python -m unittest tests.test_strategy_correctness.TestStrategyCorrectness.test_naive_vs_streaming_equivalence
```

### Run with Coverage

```bash
# Install coverage
pip install coverage pytest-cov

# Run with coverage report
python -m pytest tests/ --cov=src --cov-report=html --cov-report=term

# View HTML report
open htmlcov/index.html
```

## Test Output Examples

### Successful Correctness Test
```
test_naive_vs_streaming_equivalence ... ok
test_windowed_strategies_equivalence ... ok
test_moving_average_calculation ... ok
test_signal_generation_logic ... ok
test_numerical_precision ... ok

----------------------------------------------------------------------
Ran 5 tests in 0.234s

OK
```

### Successful Performance Test
```
test_online_windowed_runtime_requirement ...
OnlineWindowedStrategy execution time: 0.1891s
ok

test_streaming_naive_runtime_requirement ...
StreamingNaiveStrategy execution time: 0.1765s
ok

test_online_windowed_memory_requirement ...
Baseline memory: 175.23 MB
OnlineWindowedStrategy memory increase: 12.80 MB
OnlineWindowedStrategy peak memory: 188.03 MB
ok

----------------------------------------------------------------------
Ran 3 tests in 45.234s

OK
```

### Successful Profiling Test
```
test_naive_strategy_hotspot_is_calculate_average ...
================================================================================
NaiveMovingAverageStrategy Profile (Top 15 Functions):
================================================================================
         191510 function calls in 2.201 seconds

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
    10000    1.308    0.000    2.614    0.000 strategies.py:37(calculate_average)
    10000    0.819    0.000    0.819    0.000 {built-in method numpy.array}
...
ok

----------------------------------------------------------------------
Ran 1 test in 2.456s

OK
```

## Test Requirements

### Dependencies

```bash
pip install pytest
pip install memory-profiler
pip install numpy
```

### Environment

- Python 3.10+
- At least 500 MB free RAM (for 100K tick tests)
- Recommended: Run performance tests on system with minimal background processes

## Test Guidelines

### For Contributors

1. **Add tests for new strategies**: All new strategies must have correctness tests
2. **Validate performance requirements**: Optimized strategies must pass performance tests
3. **Document edge cases**: Add tests for any discovered edge cases
4. **Maintain equivalence**: Optimizations must preserve correctness

### Test Organization

```
tests/
├── __init__.py              # Package initialization
├── README.md               # This file
├── test_strategy_correctness.py  # Correctness validation
├── test_performance.py     # Performance requirements
└── test_profiling.py       # Profiling validation
```

## Expected Test Results

### Correctness Tests
- **All tests should pass** ✅
- No discrepancies between baseline and optimized strategies
- All edge cases handled correctly

### Performance Tests
- **OnlineWindowedStrategy**: < 0.2s for 100K ticks
- **StreamingNaiveStrategy**: < 0.2s for 100K ticks
- **DequeWindowedStrategy**: < 0.5s for 100K ticks
- **Memory increase**: < 20 MB for strategy storage (excluding data)

### Profiling Tests
- **Baseline strategies**: Show `calculate_average` as hotspot
- **Optimized strategies**: Show `generate_signal` as primary function
- **NumPy overhead**: Visible in baseline, minimal in optimized
- **Function call reduction**: 50%+ fewer calls in optimized

## Continuous Integration

These tests are designed to run in CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run tests
  run: |
    python -m pytest tests/ -v --junitxml=test-results.xml

- name: Upload results
  uses: actions/upload-artifact@v2
  with:
    name: test-results
    path: test-results.xml
```

## Troubleshooting

### Tests Failing Due to Timing Variability

Performance tests may occasionally fail on heavily loaded systems. Solutions:

1. Close background applications
2. Run tests multiple times to verify consistency
3. Adjust performance thresholds in `test_performance.py` if needed

### Memory Tests Reporting High Baseline

Python interpreter + imports use ~175 MB baseline memory. This is normal. Tests measure the **increase** from baseline, not absolute memory.

### Profiling Tests Not Finding Functions

Ensure you're running tests from the project root directory so imports work correctly:

```bash
cd /path/to/FinancialSignalProcessing_Finm32500
python -m pytest tests/
```

## Test Metrics Summary

| Test Category | Test Count | Expected Runtime | Pass Rate |
|--------------|------------|------------------|-----------|
| Correctness | 10 tests | ~5 seconds | 100% |
| Performance | 8 tests | ~2 minutes | 100% |
| Profiling | 9 tests | ~30 seconds | 100% |
| **Total** | **27 tests** | **~3 minutes** | **100%** |

## References

- Strategy implementations: `src/strategies.py`
- Model definitions: `src/models.py`
- Profiling notebook: `profiling_benchmarks.ipynb`
- Complexity report: `complexity_report.md`
