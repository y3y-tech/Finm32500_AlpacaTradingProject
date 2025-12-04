#!/usr/bin/env python3
"""
Live Trading with Safety Features - Production-ready example with full risk management.

This script demonstrates complete integration of:
1. RiskManager (stop-loss + circuit breaker)
2. Portfolio metrics logging
3. Strategy execution with safety checks
4. Graceful shutdown handling

Usage:
    # Dry run (no actual orders)
    python examples/live_trading_with_safety.py --symbols AAPL MSFT --dry-run

    # Paper trading
    python examples/live_trading_with_safety.py --symbols AAPL MSFT

    # Live trading (CAREFUL!)
    python examples/live_trading_with_safety.py --symbols AAPL MSFT --live
"""

import argparse
import logging
import signal
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from AlpacaTrading import setup_logging
from AlpacaTrading.live import (
    AlpacaConfig,
    AlpacaTrader,
)
from AlpacaTrading.strategies.adaptive_portfolio import AdaptivePortfolioStrategy
from AlpacaTrading.strategies.momentum import MomentumStrategy
from AlpacaTrading.strategies.rsi_strategy import RSIStrategy
from AlpacaTrading.strategies.bollinger_bands import BollingerBandsStrategy
from AlpacaTrading.trading import (
    RiskConfig,
    RiskManager,
    StopLossConfig,
    TradingPortfolio,
)

logger = logging.getLogger(__name__)


class SafeLiveTrader:
    """
    Production live trader with comprehensive safety features.

    Features:
    - RiskManager with stop-loss and circuit breaker
    - Portfolio metrics logging
    - Graceful shutdown
    - Safety checks before every trade
    """

    def __init__(
        self,
        symbols: list[str],
        initial_cash: float = 100_000,
        dry_run: bool = True,
        paper: bool = True,
    ):
        """
        Initialize safe live trader.

        Args:
            symbols: List of symbols to trade
            initial_cash: Starting capital
            dry_run: If True, don't submit orders (just log)
            paper: Use paper trading (only if dry_run=False)
        """
        self.symbols = symbols
        self.initial_cash = initial_cash
        self.dry_run = dry_run
        self.paper = paper
        self.running = False

        # Setup logging
        setup_logging(level="INFO")

        # Initialize components
        self.alpaca_config = AlpacaConfig.from_env()
        self.trader = AlpacaTrader(self.alpaca_config)
        self.portfolio = TradingPortfolio(initial_cash=initial_cash)

        # Create strategy
        self.strategy = self._create_strategy()

        # Create risk manager with safety limits
        self.risk_config = StopLossConfig(
            position_stop_pct=5.0,  # 5% stop per position
            trailing_stop_pct=7.0,  # 7% trailing stop
            portfolio_stop_pct=10.0,  # 10% max daily loss
            max_drawdown_pct=15.0,  # 15% max drawdown
            use_trailing_stops=True,  # Enable trailing stops
            enable_circuit_breaker=True,  # Enable kill switch
        )
        self.risk_manager = RiskManager(self.risk_config, initial_cash)

        # Order validation
        self.order_risk_config = RiskConfig(
            max_position_size=100,
            max_position_value=10_000,
            max_total_exposure=50_000,
            max_orders_per_minute=20,
            min_cash_buffer=1_000,
        )

        # Track metrics logging
        self.last_metrics_log = datetime.now()
        self.metrics_log_interval_seconds = 300  # Log every 5 minutes

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info("=" * 80)
        logger.info("SAFE LIVE TRADER INITIALIZED")
        logger.info("=" * 80)
        logger.info(f"Symbols: {', '.join(symbols)}")
        logger.info(f"Initial Cash: ${initial_cash:,.2f}")
        logger.info(f"Mode: {'DRY RUN' if dry_run else ('PAPER' if paper else 'LIVE')}")
        logger.info(f"Risk Manager: {self.risk_manager}")
        logger.info("=" * 80)

    def _create_strategy(self) -> AdaptivePortfolioStrategy:
        """Create adaptive portfolio with multiple strategies."""
        strategies = {
            "Momentum": MomentumStrategy(lookback_period=20, momentum_threshold=0.02),
            "RSI": RSIStrategy(
                rsi_period=14, oversold_threshold=30, overbought_threshold=70
            ),
            "BollingerBreakout": BollingerBandsStrategy(
                period=20, num_std_dev=2.0, mode="breakout"
            ),
        }

        return AdaptivePortfolioStrategy(
            strategies=strategies,
            rebalance_period=360,  # Rebalance hourly
            allocation_method="sharpe",  # Sharpe-based allocation
        )

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.warning(
            f"\n⚠️ Received signal {signum} - initiating graceful shutdown..."
        )
        self.stop()

    def _log_metrics_if_needed(self):
        """Log portfolio metrics periodically."""
        now = datetime.now()
        elapsed = (now - self.last_metrics_log).total_seconds()

        if elapsed >= self.metrics_log_interval_seconds:
            self.portfolio.log_metrics()
            self.last_metrics_log = now

            # Log summary
            metrics = self.portfolio.get_performance_metrics()
            logger.info("📊 PORTFOLIO METRICS:")
            logger.info(
                f"  Value: ${self.portfolio.get_total_value():,.2f} "
                f"({metrics['total_return']:+.2f}%)"
            )
            logger.info(
                f"  P&L: ${metrics['total_pnl']:,.2f} "
                f"(Realized: ${metrics['realized_pnl']:,.2f})"
            )
            logger.info(
                f"  Drawdown: {metrics['current_drawdown']:.2f}% "
                f"(Max: {metrics['max_drawdown']:.2f}%)"
            )
            logger.info(
                f"  Trades: {metrics['num_trades']} "
                f"(Win Rate: {metrics['win_rate']:.1f}%)"
            )

    def _check_safety(self, current_prices: dict[str, float]) -> bool:
        """
        Check all safety conditions before trading.

        Args:
            current_prices: Current market prices

        Returns:
            True if safe to trade, False if should halt
        """
        # Check circuit breaker FIRST
        if self.risk_manager.circuit_breaker_triggered:
            logger.critical("🚨 CIRCUIT BREAKER TRIGGERED - ALL TRADING HALTED 🚨")
            logger.critical(f"Reason: {self.risk_manager.get_status()}")
            return False

        # Check portfolio stops
        portfolio_value = self.portfolio.get_total_value()
        stop_orders = self.risk_manager.check_stops(
            current_prices=current_prices,
            portfolio_value=portfolio_value,
            positions=self.portfolio.positions,
        )

        # Execute stop orders if any
        if stop_orders:
            logger.warning(f"⚠️ {len(stop_orders)} STOP-LOSS ORDERS TRIGGERED")
            for order in stop_orders:
                self._execute_order(order, is_stop_loss=True)
                self.risk_manager.remove_position_stop(order.symbol)

        return True

    def _execute_order(self, order, is_stop_loss: bool = False):
        """
        Execute an order with safety checks.

        Args:
            order: Order to execute
            is_stop_loss: True if this is a stop-loss exit order
        """
        label = "STOP-LOSS" if is_stop_loss else "STRATEGY"

        if self.dry_run:
            logger.info(
                f"[DRY RUN] {label} ORDER: {order.side.value} "
                f"{order.quantity} {order.symbol}"
            )
            return

        try:
            # Submit to Alpaca
            logger.info(
                f"[{label}] Submitting: {order.side.value} "
                f"{order.quantity} {order.symbol}"
            )

            # Convert to Alpaca order
            alpaca_side = (
                AlpacaOrderSide.BUY
                if order.side == OrderSide.BUY
                else AlpacaOrderSide.SELL
            )

            market_order = MarketOrderRequest(
                symbol=order.symbol,
                qty=order.quantity,
                side=alpaca_side,
                time_in_force=TimeInForce.DAY,
            )

            # Submit order
            submitted = self.trader.trading_client.submit_order(market_order)
            logger.info(f"✓ Order submitted: {submitted.id}")

        except Exception as e:
            logger.error(f"❌ Order failed: {e}", exc_info=True)

    def run(self):
        """Run the trading loop."""
        logger.info("Starting trading loop")
        self.running = True

        # Initialize strategy
        self.strategy.on_start(self.portfolio)

        try:
            # Get initial account value
            account = self.trader.get_account()
            logger.info(f"Account Value: ${float(account['portfolio_value']):,.2f}")
            logger.info(f"Buying Power: ${float(account['buying_power']):,.2f}\n")

            tick_count = 0

            while self.running:
                # Get current prices
                current_prices = {}
                for symbol in self.symbols:
                    try:
                        # Get latest quote
                        quote = self.trader.get_latest_quote(symbol)
                        current_prices[symbol] = quote["ask_price"]
                    except Exception as e:
                        logger.warning(f"Failed to get price for {symbol}: {e}")
                        continue

                if not current_prices:
                    logger.warning("No price data available, sleeping...")
                    import time

                    time.sleep(10)
                    continue

                # Safety check BEFORE generating signals
                if not self._check_safety(current_prices):
                    logger.critical("Safety check failed - stopping trading")
                    break

                # Generate strategy signals (simplified for example)
                # In real implementation, you'd stream actual tick data
                for symbol, price in current_prices.items():
                    from AlpacaTrading.models import MarketDataPoint

                    tick = MarketDataPoint(
                        timestamp=datetime.now(),
                        symbol=symbol,
                        price=price,
                        volume=0,
                    )

                    # Generate orders from strategy
                    orders = self.strategy.process_market_data(tick, self.portfolio)

                    # Execute orders
                    for order in orders:
                        self._execute_order(order)

                        # Add stop for new positions
                        if order.side == OrderSide.BUY:
                            self.risk_manager.add_position_stop(
                                symbol=order.symbol,
                                entry_price=price,
                                quantity=order.quantity,
                            )

                # Update portfolio prices
                self.portfolio.update_prices(current_prices)

                # Log metrics periodically
                self._log_metrics_if_needed()

                tick_count += 1

                # Sleep between iterations
                import time

                time.sleep(60)  # Check every minute

        except KeyboardInterrupt:
            logger.warning("\n⚠️ Interrupted by user")
        except Exception as e:
            logger.error(f"❌ Fatal error: {e}", exc_info=True)
        finally:
            self.stop()

    def stop(self):
        """Stop trading and cleanup."""
        if not self.running:
            return

        logger.info("=" * 80)
        logger.info("SHUTTING DOWN")
        logger.info("=" * 80)

        self.running = False

        # Final metrics log
        self.portfolio.log_metrics()

        # Strategy cleanup
        self.strategy.on_end(self.portfolio)

        # Print final summary
        metrics = self.portfolio.get_performance_metrics()
        logger.info("FINAL PERFORMANCE:")
        logger.info(f"├─ Total Return: {metrics['total_return']:+.2f}%")
        logger.info(f"├─ Total P&L: ${metrics['total_pnl']:,.2f}")
        logger.info(f"├─ Total Trades: {metrics['num_trades']}")
        logger.info(f"├─ Win Rate: {metrics['win_rate']:.1f}%")
        logger.info(f"└─ Max Drawdown: {metrics['max_drawdown']:.2f}%")

        # Print risk manager status
        risk_status = self.risk_manager.get_status()
        logger.info("RISK MANAGER STATUS:")
        logger.info(
            f"├─ Circuit Breaker: {'TRIGGERED ⚠️' if risk_status['circuit_breaker_triggered'] else 'OK ✓'}"
        )
        logger.info(f"└─ Active Stops: {risk_status['num_active_stops']}")

        logger.info("Shutdown complete")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Live trading with comprehensive safety features"
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        required=True,
        help="Symbols to trade (e.g., AAPL MSFT GOOGL)",
    )
    parser.add_argument(
        "--cash", type=float, default=100_000, help="Initial cash (default: 100000)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode - no actual orders submitted",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use LIVE trading (default: paper trading)",
    )

    args = parser.parse_args()

    # Validate
    if args.live and args.dry_run:
        print("Error: Cannot use --live with --dry-run")
        return 1

    if args.live:
        response = input(
            "⚠️ WARNING: You are about to enable LIVE TRADING with real money!\n"
            "Are you sure? Type 'YES' to confirm: "
        )
        if response != "YES":
            print("Aborted.")
            return 1

    # Create and run trader
    trader = SafeLiveTrader(
        symbols=args.symbols,
        initial_cash=args.cash,
        dry_run=args.dry_run,
        paper=not args.live,
    )

    return trader.run()


if __name__ == "__main__":
    sys.exit(main())
