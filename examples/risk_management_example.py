"""
Example demonstrating transaction cost modeling and stop-loss risk management.

Shows how to:
1. Configure MatchingEngine with realistic transaction costs
2. Set up RiskManager with stop-loss protection
3. Integrate risk management into trading workflow
"""

from AlpacaTrading.trading import (
    MatchingEngine,
    RiskManager,
    StopLossConfig,
    TradingPortfolio,
)
from AlpacaTrading.models import Order, OrderSide, OrderType
from datetime import datetime


def example_transaction_costs():
    """Demonstrate transaction cost modeling."""
    print("=" * 60)
    print("TRANSACTION COST MODELING EXAMPLE")
    print("=" * 60)

    # Create matching engine with realistic costs
    engine = MatchingEngine(
        fill_probability=0.95,
        commission_per_share=0.0,  # Alpaca is commission-free
        commission_min=0.0,
        bid_ask_spread_bps=5.0,  # 5 basis points = 0.05%
        sec_fee_rate=0.0000278,  # SEC fee on sales
        liquidity_impact_factor=0.0001,  # 0.01% per $100k
        market_impact=0.0002,  # Base slippage of 0.02%
        random_seed=42,  # For reproducibility
    )

    print("\nEngine Configuration:")
    stats = engine.get_execution_stats()
    print(f"  Commission per share: ${stats['commission_per_share']}")
    print(f"  Bid-ask spread: {stats['bid_ask_spread_bps']} bps")
    print(f"  SEC fee rate: {stats['sec_fee_rate']:.6f}")
    print(f"  Liquidity impact factor: {stats['liquidity_impact_factor']:.4f}")
    print(f"  Market impact: {stats['market_impact']:.4f}")

    # Example 1: Small market buy order
    print("\n" + "-" * 60)
    print("Example 1: Small Market Buy Order (100 shares @ $150)")
    print("-" * 60)

    small_order = Order(
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=100,
        order_type=OrderType.MARKET,
        price=None,
    )

    market_price = 150.0
    trades = engine.execute_order(small_order, market_price)

    if trades:
        trade = trades[0]
        theoretical_cost = 100 * 150.0  # No costs
        actual_cost = trade.quantity * trade.price
        total_costs = actual_cost - theoretical_cost

        print(f"  Theoretical cost (no slippage): ${theoretical_cost:,.2f}")
        print(f"  Actual fill price: ${trade.price:.4f}")
        print(f"  Actual cost: ${actual_cost:,.2f}")
        print(f"  Total transaction costs: ${total_costs:.2f}")
        print(f"  Cost as % of trade: {(total_costs / theoretical_cost) * 100:.3f}%")

    # Example 2: Large market buy order (liquidity impact)
    print("\n" + "-" * 60)
    print("Example 2: Large Market Buy Order (1000 shares @ $150)")
    print("-" * 60)

    large_order = Order(
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=1000,
        order_type=OrderType.MARKET,
        price=None,
    )

    trades = engine.execute_order(large_order, market_price)

    if trades:
        trade = trades[0]
        theoretical_cost = 1000 * 150.0
        actual_cost = trade.quantity * trade.price
        total_costs = actual_cost - theoretical_cost

        print(f"  Theoretical cost (no slippage): ${theoretical_cost:,.2f}")
        print(f"  Actual fill price: ${trade.price:.4f}")
        print(f"  Actual cost: ${actual_cost:,.2f}")
        print(f"  Total transaction costs: ${total_costs:.2f}")
        print(f"  Cost as % of trade: {(total_costs / theoretical_cost) * 100:.3f}%")
        print("  Note: Higher cost due to liquidity impact on larger order")

    # Example 3: Market sell order (includes SEC fees)
    print("\n" + "-" * 60)
    print("Example 3: Market Sell Order (500 shares @ $150)")
    print("-" * 60)

    sell_order = Order(
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=500,
        order_type=OrderType.MARKET,
        price=None,
    )

    trades = engine.execute_order(sell_order, market_price)

    if trades:
        trade = trades[0]
        theoretical_proceeds = 500 * 150.0
        actual_proceeds = trade.quantity * trade.price
        total_costs = theoretical_proceeds - actual_proceeds
        sec_fee = (500 * 150.0) * 0.0000278

        print(f"  Theoretical proceeds (no costs): ${theoretical_proceeds:,.2f}")
        print(f"  Actual fill price: ${trade.price:.4f}")
        print(f"  Actual proceeds: ${actual_proceeds:,.2f}")
        print(f"  Total transaction costs: ${total_costs:.2f}")
        print(f"    - SEC fee: ${sec_fee:.2f}")
        print(f"    - Slippage/spread: ${total_costs - sec_fee:.2f}")
        print(
            f"  Cost as % of trade: {(total_costs / theoretical_proceeds) * 100:.3f}%"
        )


def example_stop_loss():
    """Demonstrate stop-loss risk management."""
    print("\n\n" + "=" * 60)
    print("STOP-LOSS RISK MANAGEMENT EXAMPLE")
    print("=" * 60)

    # Create portfolio
    portfolio = TradingPortfolio(initial_cash=100_000)

    # Configure stop-loss
    stop_config = StopLossConfig(
        position_stop_pct=2.0,  # 2% stop loss per position
        trailing_stop_pct=3.0,  # 3% trailing stop
        portfolio_stop_pct=5.0,  # 5% portfolio loss triggers circuit breaker
        max_drawdown_pct=10.0,  # 10% max drawdown
        use_trailing_stops=False,  # Start with fixed stops
        enable_circuit_breaker=True,
    )

    risk_manager = RiskManager(stop_config, initial_portfolio_value=100_000)

    print("\nRisk Manager Configuration:")
    status = risk_manager.get_status()
    print(f"  Position stop: {status['config']['position_stop_pct']}%")
    print(f"  Trailing stop: {status['config']['trailing_stop_pct']}%")
    print(f"  Portfolio stop: {status['config']['portfolio_stop_pct']}%")
    print(f"  Max drawdown: {status['config']['max_drawdown_pct']}%")
    print(
        f"  Circuit breaker: {'Enabled' if status['config']['enable_circuit_breaker'] else 'Disabled'}"
    )

    # Simulate buying a position
    print("\n" + "-" * 60)
    print("Scenario 1: Position Stop-Loss Triggered")
    print("-" * 60)

    # Add position stop
    entry_price = 150.0
    quantity = 100
    risk_manager.add_position_stop("AAPL", entry_price, quantity)

    print(f"\n  Entered long position: {quantity} shares @ ${entry_price}")
    print(f"  Stop-loss set at: ${entry_price * 0.98:.2f} (2% below entry)")

    # Create a mock position
    from src.models import Position, Trade

    position = Position(symbol="AAPL")
    trade = Trade(
        trade_id="1",
        order_id="order1",
        timestamp=datetime.now(),
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=quantity,
        price=entry_price,
    )
    position.update_from_trade(trade)
    portfolio.process_trade(trade)

    # Test 1: Price drops to $148 (1.33% loss) - should NOT trigger
    print("\n  Price drops to $148.00 (-1.33%)... ", end="")
    current_prices = {"AAPL": 148.0}
    portfolio.update_prices(current_prices)
    exit_orders = risk_manager.check_stops(
        current_prices, portfolio.get_total_value(), {"AAPL": position}
    )
    print(f"{'STOP TRIGGERED!' if exit_orders else 'No stop triggered'}")

    # Test 2: Price drops to $146 (2.67% loss) - SHOULD trigger
    print("  Price drops to $146.00 (-2.67%)... ", end="")
    current_prices = {"AAPL": 146.0}
    portfolio.update_prices(current_prices)
    exit_orders = risk_manager.check_stops(
        current_prices, portfolio.get_total_value(), {"AAPL": position}
    )
    if exit_orders:
        print("STOP TRIGGERED!")
        print(
            f"    Exit order generated: SELL {exit_orders[0].quantity} shares @ market"
        )
    else:
        print("No stop triggered")

    # Scenario 2: Trailing stop
    print("\n" + "-" * 60)
    print("Scenario 2: Trailing Stop-Loss")
    print("-" * 60)

    # Reset and enable trailing stops
    stop_config.use_trailing_stops = True
    risk_manager2 = RiskManager(stop_config, initial_portfolio_value=100_000)

    entry_price = 100.0
    quantity = 100
    risk_manager2.add_position_stop("TSLA", entry_price, quantity)

    print(f"\n  Entered long position: {quantity} shares @ ${entry_price}")
    print("  Trailing stop: 3% below highest price")
    print(f"  Initial stop: ${entry_price * 0.97:.2f}")

    position2 = Position(symbol="TSLA")
    trade2 = Trade(
        trade_id="2",
        order_id="order2",
        timestamp=datetime.now(),
        symbol="TSLA",
        side=OrderSide.BUY,
        quantity=quantity,
        price=entry_price,
    )
    position2.update_from_trade(trade2)

    # Price rises to $110 - stop should move up
    print("\n  Price rises to $110.00 (+10%)...")
    current_prices = {"TSLA": 110.0}
    exit_orders = risk_manager2.check_stops(
        current_prices, 100_000, {"TSLA": position2}
    )
    tsla_stop = risk_manager2.position_stops["TSLA"]
    print(f"    Trailing stop moved to: ${tsla_stop.stop_price:.2f}")
    print(f"    Status: {'STOP TRIGGERED!' if exit_orders else 'No stop triggered'}")

    # Price drops to $106 - should NOT trigger (within 3%)
    print("\n  Price drops to $106.00...")
    current_prices = {"TSLA": 106.0}
    exit_orders = risk_manager2.check_stops(
        current_prices, 100_000, {"TSLA": position2}
    )
    print(
        f"    Status: {'STOP TRIGGERED!' if exit_orders else 'No stop triggered (within 3% of peak)'}"
    )

    # Price drops to $105 - SHOULD trigger (>3% from peak)
    print("\n  Price drops to $105.00...")
    current_prices = {"TSLA": 105.0}
    exit_orders = risk_manager2.check_stops(
        current_prices, 100_000, {"TSLA": position2}
    )
    if exit_orders:
        print("    TRAILING STOP TRIGGERED!")
        print(f"    Locked in profit: ${(105 - entry_price) * quantity:.2f}")

    # Scenario 3: Circuit breaker
    print("\n" + "-" * 60)
    print("Scenario 3: Portfolio Circuit Breaker")
    print("-" * 60)

    portfolio_value = 95_000  # 5% loss from initial $100k
    print(f"\n  Portfolio value drops to ${portfolio_value:,} (-5.0%)")
    print("  Circuit breaker threshold: 5%")

    risk_manager3 = RiskManager(stop_config, initial_portfolio_value=100_000)
    exit_orders = risk_manager3.check_stops({}, portfolio_value, {})

    print(
        f"  Circuit breaker: {'TRIGGERED!' if risk_manager3.circuit_breaker_triggered else 'Not triggered'}"
    )
    if risk_manager3.circuit_breaker_triggered:
        print("  All trading halted to prevent further losses")


def main():
    """Run all examples."""
    example_transaction_costs()
    example_stop_loss()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print("\nTransaction Cost Modeling:")
    print("  ✓ Realistic bid-ask spread")
    print("  ✓ Liquidity impact based on order size")
    print("  ✓ SEC fees on sales")
    print("  ✓ Configurable commissions")
    print("\nStop-Loss Risk Management:")
    print("  ✓ Position-level stop-loss (fixed %)")
    print("  ✓ Trailing stops (lock in profits)")
    print("  ✓ Portfolio-level circuit breaker")
    print("  ✓ Max drawdown protection")
    print("\nNext Steps:")
    print("  1. Integrate RiskManager into BacktestEngine")
    print("  2. Backtest strategies with realistic costs")
    print("  3. Tune stop-loss parameters for your strategies")
    print("  4. Test in paper trading environment")
    print("\n")


if __name__ == "__main__":
    main()
