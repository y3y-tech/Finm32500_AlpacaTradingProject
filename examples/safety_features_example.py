"""
Safety Features Example - Demonstrates stop-loss and circuit breaker integration.

This example shows how to integrate RiskManager (stop-loss + circuit breaker)
into your live trading system for robust risk management.

Features demonstrated:
1. Per-position stop-loss (fixed and trailing)
2. Portfolio-level circuit breaker (daily loss, max drawdown)
3. Automatic exit order generation
4. Risk status monitoring
"""

import logging
from pathlib import Path
import sys

# Add src to path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from AlpacaTrading import setup_logging
from AlpacaTrading.trading import (
    RiskManager,
    StopLossConfig,
    TradingPortfolio,
)

logger = logging.getLogger(__name__)


def example_stop_loss_usage():
    """Example 1: Basic stop-loss usage."""
    print("=" * 80)
    print("EXAMPLE 1: Stop-Loss Manager")
    print("=" * 80)

    # Configure risk management
    config = StopLossConfig(
        position_stop_pct=5.0,  # 5% stop-loss per position
        trailing_stop_pct=7.0,  # 7% trailing stop
        portfolio_stop_pct=10.0,  # 10% max daily portfolio loss
        max_drawdown_pct=15.0,  # 15% max drawdown
        use_trailing_stops=False,  # Use fixed stops
        enable_circuit_breaker=True,  # Enable portfolio protection
    )

    # Initialize risk manager
    initial_value = 100_000
    risk_mgr = RiskManager(config, initial_portfolio_value=initial_value)
    portfolio = TradingPortfolio(initial_cash=initial_value)

    print(f"\n✓ Risk Manager initialized: {risk_mgr}")
    print(f"  Position stop: {config.position_stop_pct}%")
    print(f"  Portfolio stop: {config.portfolio_stop_pct}%")
    print(f"  Max drawdown: {config.max_drawdown_pct}%")

    # Simulate entering a position
    symbol = "AAPL"
    entry_price = 150.0
    quantity = 100

    # Add stop for position
    risk_mgr.add_position_stop(
        symbol=symbol, entry_price=entry_price, quantity=quantity
    )

    print(f"\n✓ Position entered: {quantity} shares of {symbol} @ ${entry_price:.2f}")
    print(f"  Stop-loss will trigger at: ${entry_price * 0.95:.2f} (5% loss)")

    # Simulate price movement - stop NOT triggered
    current_prices = {symbol: 148.0}  # 1.33% loss - not enough to stop
    exit_orders = risk_mgr.check_stops(
        current_prices=current_prices,
        portfolio_value=portfolio.get_total_value(),
        positions=portfolio.positions,
    )

    print(f"\n📉 Price dropped to ${current_prices[symbol]:.2f}")
    print(f"  Loss: {((150.0 - 148.0) / 150.0 * 100):.2f}%")
    print(f"  Stop triggered: {len(exit_orders) > 0}")

    # Simulate price movement - stop TRIGGERED
    current_prices = {symbol: 142.0}  # 5.33% loss - stop triggered!
    exit_orders = risk_mgr.check_stops(
        current_prices=current_prices,
        portfolio_value=portfolio.get_total_value(),
        positions=portfolio.positions,
    )

    print(f"\n🚨 Price dropped to ${current_prices[symbol]:.2f}")
    print(f"  Loss: {((150.0 - 142.0) / 150.0 * 100):.2f}%")
    print(f"  Stop triggered: {len(exit_orders) > 0}")

    if exit_orders:
        for order in exit_orders:
            print(f"  EXIT ORDER: {order.side.value} {order.quantity} {order.symbol}")


def example_trailing_stop():
    """Example 2: Trailing stop-loss."""
    print("\n\n" + "=" * 80)
    print("EXAMPLE 2: Trailing Stop-Loss")
    print("=" * 80)

    # Configure with trailing stops
    config = StopLossConfig(
        position_stop_pct=5.0,
        trailing_stop_pct=7.0,  # 7% trailing stop
        portfolio_stop_pct=10.0,
        max_drawdown_pct=15.0,
        use_trailing_stops=True,  # Enable trailing stops
        enable_circuit_breaker=True,
    )

    risk_mgr = RiskManager(config, initial_portfolio_value=100_000)
    portfolio = TradingPortfolio(initial_cash=100_000)

    # Enter position
    symbol = "TSLA"
    entry_price = 200.0
    quantity = 50

    risk_mgr.add_position_stop(
        symbol=symbol, entry_price=entry_price, quantity=quantity
    )

    print(f"\n✓ Position entered: {quantity} shares of {symbol} @ ${entry_price:.2f}")
    print(f"  Initial trailing stop: ${entry_price * 0.93:.2f} (7% below entry)")

    # Price moves UP - trailing stop moves UP
    print("\n📈 Price increases:")
    for price in [210, 220, 230]:
        current_prices = {symbol: float(price)}
        risk_mgr.check_stops(
            current_prices=current_prices,
            portfolio_value=portfolio.get_total_value(),
            positions=portfolio.positions,
        )
        stop_price = risk_mgr.position_stops[symbol].stop_price
        print(f"  ${price:.2f} → Trailing stop now at ${stop_price:.2f}")

    # Price drops - stop triggered
    current_prices = {symbol: 213.0}  # Drops below trailing stop
    exit_orders = risk_mgr.check_stops(
        current_prices=current_prices,
        portfolio_value=portfolio.get_total_value(),
        positions=portfolio.positions,
    )

    print(f"\n🚨 Price dropped to ${current_prices[symbol]:.2f}")
    print(f"  Trailing stop triggered: {len(exit_orders) > 0}")
    print(f"  Profit locked in: ${(230 - 200) * quantity:,.2f}")


def example_circuit_breaker():
    """Example 3: Portfolio circuit breaker."""
    print("\n\n" + "=" * 80)
    print("EXAMPLE 3: Portfolio Circuit Breaker")
    print("=" * 80)

    config = StopLossConfig(
        position_stop_pct=10.0,  # High position stop (won't trigger)
        portfolio_stop_pct=5.0,  # 5% portfolio stop
        max_drawdown_pct=10.0,  # 10% max drawdown
        enable_circuit_breaker=True,
    )

    initial_value = 100_000
    risk_mgr = RiskManager(config, initial_portfolio_value=initial_value)
    portfolio = TradingPortfolio(initial_cash=initial_value)

    print(f"\n✓ Portfolio initialized: ${initial_value:,.2f}")
    print(f"  Circuit breaker will trigger at: ${initial_value * 0.95:,.2f} (5% loss)")

    # Simulate portfolio losing value
    print("\n📉 Portfolio declining:")

    portfolio_values = [98_000, 96_000, 94_000]  # -2%, -4%, -6%
    for value in portfolio_values:
        loss_pct = (initial_value - value) / initial_value * 100

        # Check circuit breaker
        exit_orders = risk_mgr.check_stops(
            current_prices={},
            portfolio_value=value,
            positions=portfolio.positions,
        )

        status = "🚨 CIRCUIT BREAKER TRIGGERED" if exit_orders else "✓ OK"
        print(f"  ${value:,} (-{loss_pct:.1f}%) → {status}")

        if exit_orders:
            print("\n⚠️ ALL TRADING HALTED")
            print(
                f"  Reason: Portfolio loss exceeded {config.portfolio_stop_pct}% limit"
            )
            break


def example_integration_with_strategy():
    """Example 4: Integrating RiskManager with trading strategy."""
    print("\n\n" + "=" * 80)
    print("EXAMPLE 4: Integration with Trading Strategy")
    print("=" * 80)

    # Setup
    config = StopLossConfig(
        position_stop_pct=5.0,
        portfolio_stop_pct=10.0,
        max_drawdown_pct=15.0,
        use_trailing_stops=True,
    )

    risk_mgr = RiskManager(config, initial_portfolio_value=100_000)
    portfolio = TradingPortfolio(initial_cash=100_000)

    print("✓ Trading system initialized with risk management")
    print(f"  Risk config: {config}")

    # Example trading loop integration
    print("\n📊 Sample Trading Loop:")
    print("""
    while trading:
        # 1. Get market data
        tick = get_market_data()

        # 2. Check circuit breaker FIRST
        if risk_mgr.circuit_breaker_triggered:
            logger.critical("Circuit breaker active - halting trading")
            break

        # 3. Generate strategy signals
        orders = strategy.on_market_data(tick, portfolio)

        # 4. Check stops and generate exit orders
        current_prices = {sym: get_price(sym) for sym in portfolio.positions}
        exit_orders = risk_mgr.check_stops(
            current_prices=current_prices,
            portfolio_value=portfolio.get_total_value(),
            positions=portfolio.positions
        )

        # 5. Execute exit orders FIRST (risk management priority)
        for order in exit_orders:
            execute_order(order)
            risk_mgr.remove_position_stop(order.symbol)

        # 6. Execute strategy orders
        for order in orders:
            if validate_order(order):
                execute_order(order)
                # Add stop for new position
                if order.side == OrderSide.BUY:
                    risk_mgr.add_position_stop(
                        symbol=order.symbol,
                        entry_price=tick.price,
                        quantity=order.quantity
                    )

        # 7. Update portfolio metrics
        portfolio.log_metrics()
    """)

    print("\n✅ Key Integration Points:")
    print("  1. Check circuit breaker before each trade cycle")
    print("  2. Generate exit orders from risk manager")
    print("  3. Execute exit orders BEFORE strategy orders (priority)")
    print("  4. Add stops when opening new positions")
    print("  5. Remove stops when positions are closed")


def example_risk_status_monitoring():
    """Example 5: Monitoring risk status."""
    print("\n\n" + "=" * 80)
    print("EXAMPLE 5: Risk Status Monitoring")
    print("=" * 80)

    config = StopLossConfig(
        position_stop_pct=5.0,
        portfolio_stop_pct=10.0,
        max_drawdown_pct=15.0,
    )

    risk_mgr = RiskManager(config, initial_portfolio_value=100_000)

    # Add some stops
    risk_mgr.add_position_stop("AAPL", 150.0, 100)
    risk_mgr.add_position_stop("TSLA", 200.0, 50)
    risk_mgr.add_position_stop("MSFT", 300.0, 30)

    # Get status
    status = risk_mgr.get_status()

    print("\n📊 Risk Manager Status:")
    print(
        f"  Circuit Breaker: {'TRIGGERED ⚠️' if status['circuit_breaker_triggered'] else 'ACTIVE ✓'}"
    )
    print(f"  Active Stops: {status['num_active_stops']}")
    print(f"  High Water Mark: ${status['high_water_mark']:,.2f}")
    print(f"  Daily Start Value: ${status['daily_start_value']:,.2f}")

    print("\n⚙️ Configuration:")
    for key, value in status["config"].items():
        print(f"  {key}: {value}")


def main():
    """Run all examples."""
    # Setup logging
    setup_logging(level="INFO")

    print("\n" + "=" * 80)
    print("SAFETY FEATURES DEMONSTRATION")
    print("Stop-Loss Manager + Circuit Breaker Integration")
    print("=" * 80)

    try:
        example_stop_loss_usage()
        example_trailing_stop()
        example_circuit_breaker()
        example_integration_with_strategy()
        example_risk_status_monitoring()

        print("\n\n" + "=" * 80)
        print("✅ ALL EXAMPLES COMPLETED")
        print("=" * 80)
        print("\nKey Takeaways:")
        print("  1. Always initialize RiskManager with your safety thresholds")
        print("  2. Check stops BEFORE executing strategy orders")
        print("  3. Execute exit orders with highest priority")
        print("  4. Add stops when opening positions, remove when closing")
        print("  5. Monitor circuit breaker status regularly")
        print("  6. Log portfolio metrics for post-mortem analysis")
        print("\n🚀 You're ready to trade safely!")

    except Exception as e:
        logger.error(f"Example failed: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
