#!/usr/bin/env python3
"""
Strategy Runner Script - Execute backtest with specified configuration.

Usage:
    python scripts/run_strategy.py --config momentum_aggressive --data data/equities/5min_bars.csv
    python scripts/run_strategy.py --config rsi_scalper --data data/equities/1min_bars.csv --initial-cash 50000
    python scripts/run_strategy.py --list  # List all available configs
"""

import argparse
import sys
from pathlib import Path
import logging

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from AlpacaTrading.backtesting.engine import BacktestEngine
from AlpacaTrading.gateway.data_gateway import DataGateway
from configs.strategy_configs import get_config, list_configs


def setup_logging(log_file: str | None = None):
    """Setup logging configuration."""
    handlers = [logging.StreamHandler()]

    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
    )


def run_backtest(
    config_name: str,
    data_file: str,
    initial_cash: float = 100_000,
    max_ticks: int | None = None,
    output_dir: str = "logs",
    asset_class: str = "equities",
):
    """
    Run backtest with specified configuration.

    Args:
        config_name: Name of strategy configuration
        data_file: Path to market data CSV file
        initial_cash: Initial capital
        max_ticks: Maximum ticks to process (None = all)
        output_dir: Directory for logs and results
        asset_class: 'equities' or 'crypto'

    Returns:
        BacktestResult object
    """
    # Get configuration
    config = get_config(config_name, asset_class)

    print(f"\n{'=' * 80}")
    print("BACKTEST CONFIGURATION")
    print(f"{'=' * 80}")
    print(f"Strategy: {config_name}")
    print(f"Description: {config['description']}")
    print(f"Strategy params: {config['strategy']}")
    print(f"Symbols: {', '.join(config['symbols'])}")
    print(f"Initial cash: ${initial_cash:,.2f}")
    print(f"Data file: {data_file}")
    print(f"Max ticks: {max_ticks if max_ticks else 'All'}")
    print(f"{'=' * 80}\n")

    # Setup data gateway
    data_gateway = DataGateway(data_file)

    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    order_log_file = f"{output_dir}/{config_name}_orders.csv"

    # Create backtest engine
    engine = BacktestEngine(
        data_gateway=data_gateway,
        strategy=config["strategy"],
        initial_cash=initial_cash,
        risk_config=config["risk_config"],
        order_log_file=order_log_file,
        record_equity_frequency=100,
    )

    # Run backtest
    print(f"Running backtest for {config_name}...\n")
    result = engine.run(max_ticks=max_ticks)

    # Print results
    print(f"\n{'=' * 80}")
    print(f"BACKTEST RESULTS - {config_name}")
    print(f"{'=' * 80}")
    print(f"Period: {result.start_time} to {result.end_time}")
    print(f"Total ticks processed: {result.total_ticks:,}")
    print("\nFINANCIAL METRICS:")
    print(f"  Initial cash:        ${initial_cash:,.2f}")
    print(f"  Final equity:        ${result.portfolio.get_total_equity():,.2f}")
    print(f"  Total return:        {result.performance_metrics['total_return']:.2f}%")
    print(f"  Total P&L:           ${result.performance_metrics['total_pnl']:,.2f}")
    print(f"  Max drawdown:        {result.performance_metrics['max_drawdown']:.2f}%")
    print(f"  Sharpe ratio:        {result.performance_metrics['sharpe_ratio']:.2f}")
    print("\nTRADING METRICS:")
    print(f"  Total trades:        {result.performance_metrics['total_trades']}")
    print(f"  Win rate:            {result.performance_metrics['win_rate']:.2f}%")
    print(
        f"  Avg trade P&L:       ${result.performance_metrics.get('avg_trade_pnl', 0):,.2f}"
    )

    print("\nOUTPUT FILES:")
    print(f"  Order log:           {result.order_log_path}")
    print(f"  Equity curve:        {output_dir}/{config_name}_equity.csv")
    print(f"  Trades:              {output_dir}/{config_name}_trades.csv")
    print(f"{'=' * 80}\n")

    # Save results
    result.equity_curve.to_csv(f"{output_dir}/{config_name}_equity.csv", index=False)

    import pandas as pd

    trades_df = pd.DataFrame(
        [
            {
                "timestamp": t.timestamp,
                "symbol": t.symbol,
                "side": t.side.value,
                "quantity": t.quantity,
                "price": t.price,
                "value": t.value,
            }
            for t in result.trades
        ]
    )
    trades_df.to_csv(f"{output_dir}/{config_name}_trades.csv", index=False)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Run trading strategy backtest",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all available configurations
  python scripts/run_strategy.py --list

  # Run momentum strategy
  python scripts/run_strategy.py --config momentum_aggressive --data data/equities/5min_bars.csv

  # Run RSI strategy with custom capital
  python scripts/run_strategy.py --config rsi_scalper --data data/equities/1min_bars.csv --initial-cash 50000

  # Run limited number of ticks for testing
  python scripts/run_strategy.py --config momentum_aggressive --data data/equities/5min_bars.csv --max-ticks 1000

  # Run crypto strategy
  python scripts/run_strategy.py --config btc_momentum --data data/crypto/1min_bars.csv --asset-class crypto
        """,
    )

    parser.add_argument("--config", type=str, help="Strategy configuration name")
    parser.add_argument("--data", type=str, help="Path to market data CSV file")
    parser.add_argument(
        "--initial-cash",
        type=float,
        default=100_000,
        help="Initial capital (default: 100,000)",
    )
    parser.add_argument(
        "--max-ticks", type=int, help="Maximum ticks to process (optional)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="logs",
        help="Output directory (default: logs)",
    )
    parser.add_argument("--log-file", type=str, help="Log file path (optional)")
    parser.add_argument(
        "--asset-class",
        type=str,
        default="equities",
        choices=["equities", "crypto"],
        help="Asset class",
    )
    parser.add_argument(
        "--list", action="store_true", help="List available configurations"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_file)

    # List configs if requested
    if args.list:
        print("\nEQUITIES STRATEGIES:")
        list_configs("equities")
        print("\nCRYPTO STRATEGIES:")
        list_configs("crypto")
        return

    # Validate required arguments
    if not args.config:
        parser.error("--config is required (or use --list to see available configs)")

    if not args.data:
        parser.error("--data is required")

    # Check data file exists
    if not Path(args.data).exists():
        print(f"Error: Data file not found: {args.data}")
        sys.exit(1)

    # Run backtest
    try:
        run_backtest(
            config_name=args.config,
            data_file=args.data,
            initial_cash=args.initial_cash,
            max_ticks=args.max_ticks,
            output_dir=args.output_dir,
            asset_class=args.asset_class,
        )
    except Exception as e:
        print(f"\nError running backtest: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
