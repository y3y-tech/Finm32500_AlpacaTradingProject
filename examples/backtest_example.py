"""
Example: Complete Backtesting Workflow

This script demonstrates how to use the trading system to backtest a strategy.

Steps:
1. Load market data
2. Configure strategy
3. Set up risk parameters
4. Run backtest
5. Analyze results
6. Visualize performance
"""

import sys
from pathlib import Path

# Add src to path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.gateway.data_gateway import DataGateway
from src.trading.order_manager import RiskConfig
from src.trading.matching_engine import MatchingEngine
from src.backtesting.engine import BacktestEngine
from src.strategies.momentum import MomentumStrategy
from src.strategies.mean_reversion import MovingAverageCrossoverStrategy


def run_momentum_backtest():
    """Run backtest with momentum strategy."""
    print("\n" + "=" * 80)
    print("MOMENTUM STRATEGY BACKTEST")
    print("=" * 80)

    # 1. Load market data
    data_gateway = DataGateway(BASE_DIR / "equities_data" / "cleaned_data" / "tickers_cleaned.csv")

    print(f"Data source: {data_gateway.data_source}")
    print(f"Date range: {data_gateway.get_date_range()}")
    print(f"Symbols: {data_gateway.get_symbols()}")

    # 2. Configure strategy
    strategy = MomentumStrategy(
        lookback_period=20,
        momentum_threshold=0.015,  # 1.5% momentum threshold
        position_size=5000,  # $5k per position
        max_position=50  # Max 50 shares per symbol
    )

    # 3. Configure risk parameters
    risk_config = RiskConfig(
        max_position_size=100,
        max_position_value=50_000,
        max_total_exposure=200_000,
        max_orders_per_minute=50,
        max_orders_per_symbol_per_minute=10,
        min_cash_buffer=5000
    )

    # 4. Configure execution simulator
    matching_engine = MatchingEngine(
        fill_probability=0.90,
        partial_fill_probability=0.08,
        cancel_probability=0.02,
        market_impact=0.0001  # 0.01% slippage
    )

    # 5. Create backtest engine
    engine = BacktestEngine(
        data_gateway=data_gateway,
        strategy=strategy,
        initial_cash=100_000,
        risk_config=risk_config,
        matching_engine=matching_engine,
        order_log_file=BASE_DIR / "logs" / "momentum_backtest_orders.csv",
        record_equity_frequency=100
    )

    # 6. Run backtest
    result = engine.run(max_ticks=10000)  # Limit to 10k ticks for quick test

    return result


def run_ma_crossover_backtest():
    """Run backtest with moving average crossover strategy."""
    print("\n" + "=" * 80)
    print("MOVING AVERAGE CROSSOVER STRATEGY BACKTEST")
    print("=" * 80)

    # Load data
    data_gateway = DataGateway(BASE_DIR / "data" / "assignment3_market_data.csv")

    # Configure MA crossover strategy
    strategy = MovingAverageCrossoverStrategy(
        short_window=10,
        long_window=30,
        position_size=8000,
        max_position=75
    )

    # Risk config
    risk_config = RiskConfig(
        max_position_size=100,
        max_position_value=50_000,
        max_total_exposure=200_000,
        max_orders_per_minute=30
    )

    # Create engine
    engine = BacktestEngine(
        data_gateway=data_gateway,
        strategy=strategy,
        initial_cash=100_000,
        risk_config=risk_config,
        order_log_file=BASE_DIR / "logs" / "ma_crossover_orders.csv"
    )

    # Run
    result = engine.run(max_ticks=10000)

    return result


def compare_strategies():
    """Compare multiple strategies side-by-side."""
    print("\n" + "=" * 80)
    print("STRATEGY COMPARISON")
    print("=" * 80)

    # Run both strategies
    print("\nRunning Momentum Strategy...")
    momentum_result = run_momentum_backtest()

    print("\n" + "-" * 80)
    print("\nRunning MA Crossover Strategy...")
    ma_result = run_ma_crossover_backtest()

    # Compare results
    print("\n" + "=" * 80)
    print("COMPARISON SUMMARY")
    print("=" * 80)

    print("\n{:<25} {:>20} {:>20}".format(
        "Metric", "Momentum", "MA Crossover"
    ))
    print("-" * 70)

    metrics_to_compare = [
        ('total_return', '%'),
        ('total_pnl', '$'),
        ('num_trades', ''),
        ('win_rate', '%'),
        ('max_drawdown', '%'),
        ('sharpe_ratio', '')
    ]

    for metric, unit in metrics_to_compare:
        mom_val = momentum_result.performance_metrics.get(metric, 0)
        ma_val = ma_result.performance_metrics.get(metric, 0)

        if unit == '%':
            print("{:<25} {:>19.2f}% {:>19.2f}%".format(
                metric.replace('_', ' ').title(),
                mom_val,
                ma_val
            ))
        elif unit == '$':
            print("{:<25} {:>18,.2f}{} {:>18,.2f}{}".format(
                metric.replace('_', ' ').title(),
                mom_val, unit,
                ma_val, unit
            ))
        else:
            print("{:<25} {:>20.2f} {:>20.2f}".format(
                metric.replace('_', ' ').title(),
                mom_val,
                ma_val
            ))

    print("=" * 80)


def save_results(result, filename: str = "backtest_results.csv"):
    """Save equity curve to CSV."""
    output_path = BASE_DIR / "results" / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)

    result.equity_curve.to_csv(output_path, index=False)
    print(f"\nEquity curve saved to: {output_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run trading strategy backtests")
    parser.add_argument(
        "--strategy",
        choices=["momentum", "ma_crossover", "compare"],
        default="momentum",
        help="Strategy to backtest"
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save equity curve to CSV"
    )

    args = parser.parse_args()

    # Create necessary directories
    (BASE_DIR / "logs").mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "results").mkdir(parents=True, exist_ok=True)

    # Run requested backtest
    if args.strategy == "momentum":
        result = run_momentum_backtest()
        if args.save:
            save_results(result, "momentum_equity.csv")

    elif args.strategy == "ma_crossover":
        result = run_ma_crossover_backtest()
        if args.save:
            save_results(result, "ma_crossover_equity.csv")

    elif args.strategy == "compare":
        compare_strategies()

    print("\n✅ Backtest complete!")
    print(f"\nNext steps:")
    print(f"1. Review order logs in {BASE_DIR / 'logs'} directory")
    print("2. Analyze equity curves")
    print("3. Tune strategy parameters")
    print("4. Run on full dataset (remove max_ticks limit)")
