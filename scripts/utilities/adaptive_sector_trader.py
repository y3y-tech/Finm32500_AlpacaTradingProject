#!/usr/bin/env python3
"""
Adaptive Sector ETF Trader

Multi-strategy portfolio that:
- Runs ALL strategies simultaneously on SPDR sector ETFs
- Max budget: $10,000
- Rebalances every hour (360 ticks @ 10-sec bars, 60 ticks @ 1-min bars)
- Winners get more capital, losers get less
- Automatic performance tracking and adaptation

SPDR Sector ETFs:
- XLF  (Financial)
- XLI  (Industrial)
- XLRE (Real Estate)
- XLB  (Materials)
- XLC  (Communication)
- XLE  (Energy)
- XLK  (Technology)
- XLP  (Consumer Staples)
- XLV  (Health Care)
- XLU  (Utilities)
- XLY  (Consumer Discretionary)
"""

import sys
from pathlib import Path
import logging
import argparse

from AlpacaTrading.backtesting.engine import BacktestEngine
from AlpacaTrading.gateway.data_gateway import DataGateway
from AlpacaTrading.strategies.base import TradingStrategy
from AlpacaTrading.trading.order_manager import RiskConfig
from AlpacaTrading.strategies.adaptive_portfolio import AdaptivePortfolioStrategy
from AlpacaTrading.strategies.momentum import MomentumStrategy
from AlpacaTrading.strategies.mean_reversion import MovingAverageCrossoverStrategy
from AlpacaTrading.strategies.rsi_strategy import RSIStrategy
from AlpacaTrading.strategies.bollinger_bands import BollingerBandsStrategy
from AlpacaTrading.strategies.volume_breakout import VolumeBreakoutStrategy
from AlpacaTrading.strategies.vwap_strategy import VWAPStrategy
from AlpacaTrading.strategies.cross_sectional_momentum import (
    CrossSectionalMomentumStrategy,
)


# SPDR Sector ETFs
SECTOR_ETFS = [
    "XLF",  # Financial
    "XLI",  # Industrial
    "XLRE",  # Real Estate
    "XLB",  # Materials
    "XLC",  # Communication
    "XLE",  # Energy
    "XLK",  # Technology
    "XLP",  # Consumer Staples
    "XLV",  # Health Care
    "XLU",  # Utilities
    "XLY",  # Consumer Discretionary
]


def create_adaptive_portfolio(
    rebalance_period: int = 60, allocation_method: str = "pnl"
) -> AdaptivePortfolioStrategy:
    """
    Create adaptive portfolio with all strategies.

    Args:
        rebalance_period: Ticks between rebalances (60 = 1 hour @ 1-min bars)
        allocation_method: 'pnl', 'sharpe', or 'win_rate'

    Returns:
        AdaptivePortfolioStrategy configured with all strategies
    """
    # Create all strategies (tuned for ETF trading)
    strategies: dict[str, TradingStrategy] = {
        # Momentum strategies
        "momentum_fast": MomentumStrategy(
            lookback_period=10,
            momentum_threshold=0.008,  # 0.8% for ETFs (less volatile than stocks)
            position_size=1000,
            max_position=15,
        ),
        "momentum_slow": MomentumStrategy(
            lookback_period=20,
            momentum_threshold=0.005,  # 0.5%
            position_size=1000,
            max_position=15,
        ),
        # Mean reversion strategies
        "ma_cross_fast": MovingAverageCrossoverStrategy(
            short_window=5, long_window=15, position_size=1000, max_position=15
        ),
        "ma_cross_slow": MovingAverageCrossoverStrategy(
            short_window=10, long_window=30, position_size=1000, max_position=15
        ),
        # RSI strategies
        "rsi_aggressive": RSIStrategy(
            rsi_period=14,
            oversold_threshold=25,  # Very oversold
            overbought_threshold=75,  # Very overbought
            position_size=1000,
            max_position=15,
            profit_target=1.5,  # 1.5% profit target
            stop_loss=0.75,  # 0.75% stop loss
        ),
        "rsi_conservative": RSIStrategy(
            rsi_period=14,
            oversold_threshold=30,
            overbought_threshold=70,
            position_size=1000,
            max_position=15,
            profit_target=2.0,
            stop_loss=1.0,
        ),
        # Bollinger Bands strategies
        "bb_breakout": BollingerBandsStrategy(
            period=20,
            num_std_dev=2.0,
            mode="breakout",
            position_size=1000,
            max_position=15,
            band_threshold=0.002,
        ),
        "bb_reversion": BollingerBandsStrategy(
            period=20,
            num_std_dev=2.5,
            mode="reversion",
            position_size=1000,
            max_position=15,
            band_threshold=0.001,
        ),
        # Volume strategy
        "volume_breakout": VolumeBreakoutStrategy(
            volume_period=20,
            volume_multiplier=2.0,  # 2x volume for ETFs
            price_momentum_period=5,
            min_price_change=0.008,  # 0.8%
            position_size=1000,
            max_position=15,
            hold_periods=30,
        ),
        # VWAP strategy
        "vwap": VWAPStrategy(
            deviation_threshold=0.005,  # 0.5% from VWAP
            position_size=1000,
            max_position=15,
            reset_period=0,  # Never reset for continuous trading
            min_samples=20,
        ),
        # Cross-sectional (trades across all sectors)
        "cross_sectional": CrossSectionalMomentumStrategy(
            lookback_period=20,
            rebalance_period=30,  # More frequent rebalancing
            long_percentile=0.27,  # Top 3 out of 11 ETFs (~27%)
            short_percentile=0.0,  # Long-only
            enable_shorting=False,
            position_size=1000,
            max_position_per_stock=15,
            min_stocks=5,
        ),
    }

    # Create adaptive portfolio
    adaptive = AdaptivePortfolioStrategy(
        strategies=strategies,
        rebalance_period=rebalance_period,
        min_allocation=0.03,  # Min 3% per strategy
        max_allocation=0.25,  # Max 25% per strategy
        performance_lookback=rebalance_period,
        allocation_method=allocation_method,
    )

    return adaptive


def main():
    parser = argparse.ArgumentParser(
        description="Adaptive Sector ETF Trader with Multi-Strategy Portfolio",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run on 1-minute bars (rebalance every 60 ticks = 1 hour)
  python scripts/adaptive_sector_trader.py --data data/sector_etfs_1min.csv

  # Run on 10-second bars (rebalance every 360 ticks = 1 hour)
  python scripts/adaptive_sector_trader.py --data data/sector_etfs_10sec.csv --rebalance-period 360

  # Use different allocation method
  python scripts/adaptive_sector_trader.py --data data/sector_etfs_1min.csv --allocation-method sharpe

  # Test with limited ticks
  python scripts/adaptive_sector_trader.py --data data/sector_etfs_1min.csv --max-ticks 5000
        """,
    )

    parser.add_argument(
        "--data", type=str, required=True, help="Path to sector ETF data CSV"
    )
    parser.add_argument(
        "--initial-cash",
        type=float,
        default=10000,
        help="Initial capital (default: 10,000)",
    )
    parser.add_argument(
        "--rebalance-period",
        type=int,
        default=60,
        help="Ticks between rebalances (default: 60)",
    )
    parser.add_argument(
        "--allocation-method",
        type=str,
        default="pnl",
        choices=["pnl", "sharpe", "win_rate"],
        help="Allocation method (default: pnl)",
    )
    parser.add_argument(
        "--max-ticks", type=int, help="Maximum ticks to process (optional)"
    )
    parser.add_argument(
        "--output-dir", type=str, default="logs/adaptive", help="Output directory"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING"],
        help="Log level",
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f"{args.output_dir}/adaptive_sector_trader.log"),
        ],
    )

    # Create output directory
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    print(f"\n{'=' * 80}")
    print("ADAPTIVE SECTOR ETF TRADER")
    print(f"{'=' * 80}")
    print(f"Initial capital:     ${args.initial_cash:,.2f}")
    print(f"Data file:           {args.data}")
    print(f"Rebalance period:    Every {args.rebalance_period} ticks")
    print(f"Allocation method:   {args.allocation_method}")
    print(f"Sector ETFs:         {', '.join(SECTOR_ETFS)}")
    print(f"Output directory:    {args.output_dir}")
    print(f"{'=' * 80}\n")

    # Check data file exists
    if not Path(args.data).exists():
        print(f"Error: Data file not found: {args.data}")
        sys.exit(1)

    # Create adaptive portfolio strategy
    strategy = create_adaptive_portfolio(
        rebalance_period=args.rebalance_period, allocation_method=args.allocation_method
    )

    # Create data gateway
    data_gateway = DataGateway(args.data)

    # Create risk config (conservative for $10k budget)
    risk_config = RiskConfig(
        max_position_size=20,  # Max 20 shares per ETF
        max_position_value=2000,  # Max $2k per ETF
        max_total_exposure=9000,  # Max $9k total exposure (keep some cash)
        max_orders_per_minute=50,
        max_orders_per_symbol_per_minute=10,
        min_cash_buffer=500,  # Keep $500 buffer
    )

    # Create backtest engine
    engine = BacktestEngine(
        data_gateway=data_gateway,
        strategy=strategy,
        initial_cash=args.initial_cash,
        risk_config=risk_config,
        order_log_file=f"{args.output_dir}/orders.csv",
        record_equity_frequency=100,
    )

    # Run backtest
    print("Running adaptive multi-strategy backtest...\n")
    result = engine.run(max_ticks=args.max_ticks)

    # Print results
    print(f"\n{'=' * 80}")
    print("FINAL RESULTS")
    print(f"{'=' * 80}")
    print(f"Period:              {result.start_time} to {result.end_time}")
    print(f"Total ticks:         {result.total_ticks:,}")
    print("\nPERFORMANCE:")
    print(f"  Initial cash:      ${args.initial_cash:,.2f}")
    print(f"  Final equity:      ${result.portfolio.get_total_value():,.2f}")
    print(f"  Total return:      {result.performance_metrics['total_return']:.2f}%")
    print(f"  Total P&L:         ${result.performance_metrics['total_pnl']:,.2f}")
    print(f"  Max drawdown:      {result.performance_metrics['max_drawdown']:.2f}%")
    print(f"  Sharpe ratio:      {result.performance_metrics['sharpe_ratio']:.2f}")
    print(f"  Win rate:          {result.performance_metrics['win_rate']:.2f}%")
    print(f"  Total trades:      {result.performance_metrics['total_trades']}")
    print("\nOUTPUT FILES:")
    print(f"  Orders:            {args.output_dir}/orders.csv")
    print(f"  Equity curve:      {args.output_dir}/equity_curve.csv")
    print(f"  Trades:            {args.output_dir}/trades.csv")
    print(f"  Log:               {args.output_dir}/adaptive_sector_trader.log")
    print(f"{'=' * 80}\n")

    # Save results
    result.equity_curve.to_csv(f"{args.output_dir}/equity_curve.csv", index=False)

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
    trades_df.to_csv(f"{args.output_dir}/trades.csv", index=False)

    print("Adaptive sector ETF trader completed successfully!")


if __name__ == "__main__":
    main()
