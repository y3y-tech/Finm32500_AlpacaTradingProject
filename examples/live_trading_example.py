"""
Live Trading Example - Demonstrates real-time trading with Alpaca.

This example shows how to:
1. Configure and connect to Alpaca API
2. Set up a trading strategy
3. Configure risk management
4. Run live trading engine
5. Monitor positions and P&L

IMPORTANT: This uses PAPER TRADING by default. Ensure your .env is configured correctly.
"""

import sys
from pathlib import Path

# Add src to path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))


from AlpacaTrading.live import AlpacaConfig, AlpacaTrader, LiveTradingEngine, LiveEngineConfig
from AlpacaTrading.strategies.momentum import MomentumStrategy
from AlpacaTrading.trading import RiskConfig, StopLossConfig


def example_alpaca_connection():
    """Example 1: Test Alpaca connection and get account info."""
    print("=" * 60)
    print("EXAMPLE 1: Alpaca Connection Test")
    print("=" * 60)

    try:
        # Load credentials from .env
        config = AlpacaConfig.from_env()
        trader = AlpacaTrader(config)

        # Get account info
        print("\n📊 Account Information:")
        account = trader.get_account()
        print(f"  Cash: ${account['cash']:,.2f}")
        print(f"  Portfolio Value: ${account['portfolio_value']:,.2f}")
        print(f"  Buying Power: ${account['buying_power']:,.2f}")
        print(f"  Equity: ${account['equity']:,.2f}")
        print(f"  Pattern Day Trader: {account['pattern_day_trader']}")

        # Get positions (if any)
        positions = trader.get_positions()
        if positions:
            print(f"\n📦 Current Positions ({len(positions)}):")
            for pos in positions:
                pnl = pos['unrealized_pl']
                pnl_pct = pos['unrealized_plpc'] * 100
                print(f"  {pos['symbol']}: {pos['quantity']} @ ${pos['avg_entry_price']:.2f}")
                print(f"    Current: ${pos['current_price']:.2f} | P&L: ${pnl:+,.2f} ({pnl_pct:+.2f}%)")
        else:
            print("\n📦 No open positions")

        # Get open orders (if any)
        orders = trader.get_open_orders()
        if orders:
            print(f"\n📋 Open Orders ({len(orders)}):")
            for order in orders:
                print(f"  {order['side']} {order['qty']} {order['symbol']} @ {order['order_type']}")
        else:
            print("\n📋 No open orders")

        print("\n✅ Connection successful!")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure:")
        print("  1. You have a .env file with ALPACA_API_KEY and ALPACA_SECRET_KEY")
        print("  2. Your API keys are valid")
        print("  3. You're using paper trading credentials")


def example_live_trading_dry_run():
    """Example 2: Run live trading in DRY RUN mode (no actual orders)."""
    print("\n\n" + "=" * 60)
    print("EXAMPLE 2: Live Trading Dry Run")
    print("=" * 60)
    print("\nThis will stream live market data and generate signals,")
    print("but will NOT submit actual orders (enable_trading=False).")
    print("\nPress Ctrl+C to stop.\n")

    input("Press Enter to continue or Ctrl+C to skip...")

    try:
        # Configure Alpaca
        alpaca_config = AlpacaConfig.from_env()

        # Configure risk management
        risk_config = RiskConfig(
            max_position_size=100,  # Max 100 shares per position
            max_position_value=10_000,  # Max $10k per position
            max_total_exposure=50_000,  # Max $50k total
            max_orders_per_minute=10,  # Max 10 orders/minute
            max_orders_per_symbol_per_minute=2,  # Max 2 orders/symbol/minute
            min_cash_buffer=1000  # Keep $1k cash buffer
        )

        # Configure stop-loss
        stop_config = StopLossConfig(
            position_stop_pct=2.0,  # 2% stop loss
            trailing_stop_pct=3.0,  # 3% trailing stop
            portfolio_stop_pct=5.0,  # 5% portfolio circuit breaker
            max_drawdown_pct=10.0,  # 10% max drawdown
            use_trailing_stops=False,  # Use fixed stops for now
            enable_circuit_breaker=True
        )

        # Create engine config
        engine_config = LiveEngineConfig(
            alpaca_config=alpaca_config,
            risk_config=risk_config,
            stop_loss_config=stop_config,
            enable_trading=False,  # DRY RUN - no actual orders
            enable_stop_loss=True,
            log_orders=True,
            order_log_path="dry_run_orders.csv"
        )

        # Create strategy
        strategy = MomentumStrategy(
            lookback_period=20,
            momentum_threshold=0.02,  # 2% velocity threshold
            max_position=3
        )

        # Create engine
        engine = LiveTradingEngine(engine_config, strategy)

        # Run (blocking call - press Ctrl+C to stop)
        engine.run(
            symbols=["AAPL", "MSFT", "GOOGL"],
            data_type="trades"  # Use real-time trades
        )

    except KeyboardInterrupt:
        print("\n\nDry run stopped by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


def example_live_trading_paper():
    """Example 3: Run REAL live trading in PAPER mode."""
    print("\n\n" + "=" * 60)
    print("EXAMPLE 3: Live Paper Trading")
    print("=" * 60)
    print("\n⚠️  WARNING: This will submit REAL orders to your paper account!")
    print("Make sure you understand the risks and have tested in dry run mode first.")
    print("\nPress Ctrl+C to stop.\n")

    response = input("Type 'YES' to continue with paper trading: ")
    if response != "YES":
        print("Cancelled.")
        return

    try:
        # Configure Alpaca
        alpaca_config = AlpacaConfig.from_env()

        # Verify we're in paper mode
        if not alpaca_config.paper:
            print("\n❌ ERROR: Not in paper trading mode!")
            print("Set ALPACA_PAPER=true in your .env file")
            return

        # Configure risk management (more conservative for real trading)
        risk_config = RiskConfig(
            max_position_size=50,  # Max 50 shares
            max_position_value=5_000,  # Max $5k per position
            max_total_exposure=25_000,  # Max $25k total
            max_orders_per_minute=5,  # Max 5 orders/minute
            max_orders_per_symbol_per_minute=1,  # Max 1 order/symbol/minute
            min_cash_buffer=5000  # Keep $5k buffer
        )

        # Configure stop-loss
        stop_config = StopLossConfig(
            position_stop_pct=2.0,  # 2% stop loss
            trailing_stop_pct=3.0,  # 3% trailing stop
            portfolio_stop_pct=3.0,  # 3% portfolio circuit breaker (conservative)
            max_drawdown_pct=5.0,  # 5% max drawdown (conservative)
            use_trailing_stops=False,
            enable_circuit_breaker=True
        )

        # Create engine config
        engine_config = LiveEngineConfig(
            alpaca_config=alpaca_config,
            risk_config=risk_config,
            stop_loss_config=stop_config,
            enable_trading=True,  # REAL TRADING ENABLED
            enable_stop_loss=True,
            log_orders=True,
            order_log_path="paper_trading_orders.csv"
        )

        # Create strategy (conservative settings)
        strategy = MomentumStrategy(
            lookback_period=30,
            momentum_threshold=0.03,  # Higher threshold = fewer trades
            max_positions=2  # Limit to 2 positions
        )

        # Create engine
        engine = LiveTradingEngine(engine_config, strategy)

        # Run (blocking call - press Ctrl+C to stop)
        engine.run(
            symbols=["AAPL", "MSFT"],  # Start with just 2 liquid stocks
            data_type="trades"
        )

    except KeyboardInterrupt:
        print("\n\nPaper trading stopped by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Run all examples (interactive)."""
    print("""
╔══════════════════════════════════════════════════════════╗
║         LIVE TRADING WITH ALPACA - EXAMPLES              ║
╚══════════════════════════════════════════════════════════╝

Choose an example to run:

1. Test Alpaca Connection (safe - read-only)
2. Live Trading Dry Run (safe - no orders submitted)
3. Paper Trading (⚠️  submits real paper orders)
4. Run all examples in sequence

0. Exit
    """)

    while True:
        choice = input("\nEnter your choice (0-4): ").strip()

        if choice == "0":
            print("\nGoodbye!")
            break
        elif choice == "1":
            example_alpaca_connection()
        elif choice == "2":
            example_live_trading_dry_run()
        elif choice == "3":
            example_live_trading_paper()
        elif choice == "4":
            example_alpaca_connection()
            example_live_trading_dry_run()
            example_live_trading_paper()
        else:
            print("Invalid choice. Please enter 0-4.")


if __name__ == "__main__":
    # Check if .env exists
    import os
    if not os.path.exists(".env"):
        print("❌ ERROR: .env file not found!")
        print("\nPlease create a .env file with your Alpaca credentials:")
        print("  cp .env.example .env")
        print("  # Then edit .env with your actual API keys")
        print("\nSee SETUP_CREDENTIALS.md for details.")
        exit(1)

    main()
