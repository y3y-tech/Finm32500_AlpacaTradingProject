#!/usr/bin/env python3
"""
Parallel Strategy Runner - Execute multiple strategies concurrently.

Runs multiple strategy configurations in parallel using multiprocessing.
Useful for parameter optimization and strategy comparison.

Usage:
    python scripts/run_parallel.py --data data/equities/5min_bars.csv --configs momentum_aggressive rsi_scalper bb_breakout
    python scripts/run_parallel.py --data data/equities/5min_bars.csv --all-equities
"""

import argparse
import sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
import logging

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from run_strategy import run_backtest
from configs.strategy_configs import STRATEGY_CONFIGS, CRYPTO_CONFIGS


def run_single_backtest(args_tuple):
    """
    Wrapper for running a single backtest (for multiprocessing).

    Args:
        args_tuple: Tuple of (config_name, data_file, initial_cash, max_ticks, output_dir, asset_class)

    Returns:
        Tuple of (config_name, result_summary)
    """
    config_name, data_file, initial_cash, max_ticks, output_dir, asset_class = args_tuple

    try:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Starting backtest: {config_name}")

        # Run backtest
        result = run_backtest(
            config_name=config_name,
            data_file=data_file,
            initial_cash=initial_cash,
            max_ticks=max_ticks,
            output_dir=f"{output_dir}/{config_name}",
            asset_class=asset_class
        )

        # Extract summary
        summary = {
            'config': config_name,
            'total_return': result.performance_metrics['total_return'],
            'total_pnl': result.performance_metrics['total_pnl'],
            'sharpe_ratio': result.performance_metrics['sharpe_ratio'],
            'max_drawdown': result.performance_metrics['max_drawdown'],
            'win_rate': result.performance_metrics['win_rate'],
            'total_trades': result.performance_metrics['total_trades'],
            'final_equity': result.portfolio.get_total_equity()
        }

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Completed: {config_name} - Return: {summary['total_return']:.2f}%")

        return config_name, summary, None

    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR in {config_name}: {e}")
        return config_name, None, str(e)


def run_parallel_backtests(
    config_names: list[str],
    data_file: str,
    initial_cash: float = 100_000,
    max_ticks: int | None = None,
    output_dir: str = "logs/parallel",
    asset_class: str = 'equities',
    max_workers: int | None = None
):
    """
    Run multiple backtests in parallel.

    Args:
        config_names: List of configuration names to run
        data_file: Path to market data CSV
        initial_cash: Initial capital for each strategy
        max_ticks: Maximum ticks to process (optional)
        output_dir: Output directory
        asset_class: 'equities' or 'crypto'
        max_workers: Maximum parallel workers (default: CPU count)

    Returns:
        Dictionary of {config_name: summary_dict}
    """
    print(f"\n{'='*80}")
    print(f"PARALLEL BACKTEST EXECUTION")
    print(f"{'='*80}")
    print(f"Strategies: {', '.join(config_names)}")
    print(f"Data file: {data_file}")
    print(f"Initial cash: ${initial_cash:,.2f}")
    print(f"Max ticks: {max_ticks if max_ticks else 'All'}")
    print(f"Max workers: {max_workers if max_workers else 'Auto (CPU count)'}")
    print(f"Output dir: {output_dir}")
    print(f"{'='*80}\n")

    # Prepare arguments for each backtest
    backtest_args = [
        (config_name, data_file, initial_cash, max_ticks, output_dir, asset_class)
        for config_name in config_names
    ]

    # Run in parallel
    results = {}
    errors = {}

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        futures = {
            executor.submit(run_single_backtest, args): args[0]
            for args in backtest_args
        }

        # Collect results as they complete
        for future in as_completed(futures):
            config_name = futures[future]
            try:
                name, summary, error = future.result()
                if error:
                    errors[name] = error
                else:
                    results[name] = summary
            except Exception as e:
                print(f"ERROR in future for {config_name}: {e}")
                errors[config_name] = str(e)

    return results, errors


def print_comparison(results: dict):
    """Print comparison table of results."""
    print(f"\n{'='*80}")
    print(f"STRATEGY COMPARISON")
    print(f"{'='*80}\n")

    # Sort by total return
    sorted_results = sorted(
        results.items(),
        key=lambda x: x[1]['total_return'],
        reverse=True
    )

    # Print table header
    print(f"{'Strategy':<25} {'Return':>10} {'P&L':>12} {'Sharpe':>8} {'MaxDD':>8} {'Win%':>7} {'Trades':>8}")
    print(f"{'-'*25} {'-'*10} {'-'*12} {'-'*8} {'-'*8} {'-'*7} {'-'*8}")

    # Print each strategy
    for config_name, summary in sorted_results:
        print(
            f"{config_name:<25} "
            f"{summary['total_return']:>9.2f}% "
            f"${summary['total_pnl']:>11,.0f} "
            f"{summary['sharpe_ratio']:>8.2f} "
            f"{summary['max_drawdown']:>7.2f}% "
            f"{summary['win_rate']:>6.1f}% "
            f"{summary['total_trades']:>8}"
        )

    print(f"\n{'='*80}\n")

    # Save to CSV
    import pandas as pd
    df = pd.DataFrame([
        {
            'Strategy': name,
            'Total Return (%)': s['total_return'],
            'Total P&L ($)': s['total_pnl'],
            'Sharpe Ratio': s['sharpe_ratio'],
            'Max Drawdown (%)': s['max_drawdown'],
            'Win Rate (%)': s['win_rate'],
            'Total Trades': s['total_trades'],
            'Final Equity ($)': s['final_equity']
        }
        for name, s in sorted_results
    ])

    csv_path = "logs/parallel/strategy_comparison.csv"
    df.to_csv(csv_path, index=False)
    print(f"Comparison saved to: {csv_path}\n")


def main():
    parser = argparse.ArgumentParser(
        description='Run multiple strategy backtests in parallel',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run specific strategies
  python scripts/run_parallel.py --data data/equities/5min_bars.csv --configs momentum_aggressive rsi_scalper

  # Run all equity strategies
  python scripts/run_parallel.py --data data/equities/5min_bars.csv --all-equities

  # Run all crypto strategies
  python scripts/run_parallel.py --data data/crypto/1min_bars.csv --all-crypto

  # Limit parallel workers
  python scripts/run_parallel.py --data data/equities/5min_bars.csv --all-equities --max-workers 4
        """
    )

    parser.add_argument('--data', type=str, required=True, help='Path to market data CSV file')
    parser.add_argument('--configs', nargs='+', help='Specific strategy configurations to run')
    parser.add_argument('--all-equities', action='store_true', help='Run all equity strategies')
    parser.add_argument('--all-crypto', action='store_true', help='Run all crypto strategies')
    parser.add_argument('--initial-cash', type=float, default=100_000, help='Initial capital (default: 100,000)')
    parser.add_argument('--max-ticks', type=int, help='Maximum ticks to process (optional)')
    parser.add_argument('--output-dir', type=str, default='logs/parallel', help='Output directory')
    parser.add_argument('--max-workers', type=int, help='Maximum parallel workers (default: CPU count)')

    args = parser.parse_args()

    # Determine which configs to run
    if args.all_equities:
        config_names = list(STRATEGY_CONFIGS.keys())
        asset_class = 'equities'
    elif args.all_crypto:
        config_names = list(CRYPTO_CONFIGS.keys())
        asset_class = 'crypto'
    elif args.configs:
        config_names = args.configs
        asset_class = 'equities'  # Default, will be detected from config
    else:
        parser.error("Must specify --configs, --all-equities, or --all-crypto")

    # Check data file exists
    if not Path(args.data).exists():
        print(f"Error: Data file not found: {args.data}")
        sys.exit(1)

    # Run parallel backtests
    try:
        results, errors = run_parallel_backtests(
            config_names=config_names,
            data_file=args.data,
            initial_cash=args.initial_cash,
            max_ticks=args.max_ticks,
            output_dir=args.output_dir,
            asset_class=asset_class,
            max_workers=args.max_workers
        )

        # Print comparison
        if results:
            print_comparison(results)

        # Print errors
        if errors:
            print("\nERRORS:")
            for config, error in errors.items():
                print(f"  {config}: {error}")

        # Exit code
        if errors and not results:
            sys.exit(1)

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
