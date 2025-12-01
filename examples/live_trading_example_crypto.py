"""
Live Trading Example (Crypto) - Demonstrates real-time trading with Alpaca.

This example shows how to:
1. Configure and connect to Alpaca API for Crypto
2. Set up a trading strategy
3. Configure risk management for fractional assets
4. Run live trading engine with BTC/USD
5. Monitor positions and P&L

IMPORTANT: This uses PAPER TRADING by default. Ensure your .env is configured correctly.
"""

from AlpacaTrading.live.live_engine_crypto import LiveTradingEngine, LiveEngineConfig
from AlpacaTrading.live.alpaca_trader_crypto import AlpacaTrader, AlpacaConfig
from AlpacaTrading.strategies import MomentumStrategy
from AlpacaTrading.trading import RiskConfig, StopLossConfig


def example_alpaca_connection():
    """Example 1: Test Alpaca connection and get account info."""
    print("=" * 60)
    print("EXAMPLE 1: Alpaca Connection Test")
    print("=" * 60)

    try:
        # Load credentials from .env
        config = AlpacaConfig.from_env()
        config.crypto = True  # IMPORTANT: Enable crypto mode

        trader = AlpacaTrader(config)

        # Get account info
        print("\n📊 Account Information:")
        account = trader.get_account()
        print(f"  Cash: ${account['cash']:,.2f}")
        print(f"  Portfolio Value: ${account['portfolio_value']:,.2f}")
        print(f"  Buying Power: ${account['buying_power']:,.2f}")
        print(f"  Equity: ${account['equity']:,.2f}")

        # Get positions (if any)
        positions = trader.get_positions()
        if positions:
            print(f"\n📦 Current Positions ({len(positions)}):")
            for pos in positions:
                pnl = pos["unrealized_pl"]
                pnl_pct = pos["unrealized_plpc"] * 100
                print(
                    f"  {pos['symbol']}: {pos['quantity']} @ ${pos['avg_entry_price']:.2f}"
                )
                print(
                    f"    Current: ${pos['current_price']:.2f} | P&L: ${pnl:+,.2f} ({pnl_pct:+.2f}%)"
                )
        else:
            print("\n📦 No open positions")

        print("\n✅ Connection successful!")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure:")
        print("  1. You have a .env file with APCA_API_KEY_ID and APCA_API_SECRET_KEY")
        print("  2. Your API keys are valid")


def example_live_trading_dry_run():
    """Example 2: Run live trading in DRY RUN mode (no actual orders)."""
    print("\n\n" + "=" * 60)
    print("EXAMPLE 2: Live Crypto Trading Dry Run")
    print("=" * 60)
    print("\nThis will stream live BTC/USD trades and generate signals,")
    print("but will NOT submit actual orders (enable_trading=False).")
    print("\nPress Ctrl+C to stop.\n")

    input("Press Enter to continue or Ctrl+C to skip...")

    try:
        # Configure Alpaca
        alpaca_config = AlpacaConfig.from_env()
        alpaca_config.crypto = True  # Enable crypto streaming

        # Configure risk management (adjusted for Crypto)
        risk_config = RiskConfig(
            max_position_size=1.0,  # Max 1.0 BTC (adjusted for high price)
            max_position_value=50_000,  # Max $50k per position
            max_total_exposure=100_000,  # Max $100k total
            max_orders_per_minute=10,
            max_orders_per_symbol_per_minute=5,
            min_cash_buffer=1000,
        )

        # Configure stop-loss
        stop_config = StopLossConfig(
            position_stop_pct=2.0,
            trailing_stop_pct=3.0,
            portfolio_stop_pct=5.0,
            max_drawdown_pct=10.0,
            use_trailing_stops=False,
            enable_circuit_breaker=True,
        )

        # Create engine config
        engine_config = LiveEngineConfig(
            alpaca_config=alpaca_config,
            risk_config=risk_config,
            stop_loss_config=stop_config,
            enable_trading=False,  # DRY RUN - no actual orders
            enable_stop_loss=True,
            log_orders=True,
            order_log_path="dry_run_crypto_orders.csv",
        )

        # Create strategy
        strategy = MomentumStrategy(
            lookback_period=20,
            momentum_threshold=0.005,  # 0.5% velocity threshold (crypto is volatile)
            position_size=5000,  # $5k position size
            max_position=1,  # Max 1 unit (will be limited by value anyway)
        )

        # Create engine
        engine = LiveTradingEngine(engine_config, strategy)

        # Run (blocking call - press Ctrl+C to stop)
        engine.run(
            symbols=["BTC/USD"],
            data_type="trades",  # Use real-time trades
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
    print("EXAMPLE 3: Live Paper Trading (Crypto)")
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
        alpaca_config.crypto = True  # Enable crypto streaming

        # Verify we're in paper mode
        if not alpaca_config.paper:
            print("\n❌ ERROR: Not in paper trading mode!")
            print("Set ALPACA_PAPER=true in your .env file")
            return

        # Configure risk management (conservative for high-volatility crypto)
        risk_config = RiskConfig(
            max_position_size=0.5,  # Max 0.5 BTC
            max_position_value=25_000,  # Max $25k per position
            max_total_exposure=50_000,  # Max $50k total
            max_orders_per_minute=5,
            max_orders_per_symbol_per_minute=2,
            min_cash_buffer=5000,
        )

        # Configure stop-loss
        stop_config = StopLossConfig(
            position_stop_pct=3.0,  # Wider stop for crypto volatility
            trailing_stop_pct=5.0,  # Wider trailing stop
            portfolio_stop_pct=5.0,
            max_drawdown_pct=10.0,
            use_trailing_stops=True,  # Use trailing stops to lock in crypto gains
            enable_circuit_breaker=True,
        )

        # Create engine config
        engine_config = LiveEngineConfig(
            alpaca_config=alpaca_config,
            risk_config=risk_config,
            stop_loss_config=stop_config,
            enable_trading=True,  # REAL TRADING ENABLED
            enable_stop_loss=True,
            log_orders=True,
            order_log_path="paper_crypto_orders.csv",
        )

        # Create strategy
        strategy = MomentumStrategy(
            lookback_period=30,
            momentum_threshold=0.01,  # 1% threshold
            position_size=1000,  # $1000 per trade
            max_position=1,  # Max 1 position count per symbol
        )

        # Create engine
        engine = LiveTradingEngine(engine_config, strategy)

        # Run (blocking call - press Ctrl+C to stop)
        print("Starting engine for BTC/USD...")
        engine.run(symbols=["BTC/USD"], data_type="trades")

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
║      LIVE CRYPTO TRADING WITH ALPACA - EXAMPLES          ║
╚══════════════════════════════════════════════════════════╝

Choose an example to run:

1. Test Alpaca Connection (safe - read-only)
2. Live Trading Dry Run (safe - no orders submitted)
3. Paper Trading (⚠️  submits real paper orders)

0. Exit
    """)

    while True:
        choice = input("\nEnter your choice (0-3): ").strip()

        if choice == "0":
            print("\nGoodbye!")
            break
        elif choice == "1":
            example_alpaca_connection()
        elif choice == "2":
            example_live_trading_dry_run()
        elif choice == "3":
            example_live_trading_paper()
        else:
            print("Invalid choice. Please enter 0-3.")


if __name__ == "__main__":
    # Check if .env exists
    import os

    if not os.path.exists(".env"):
        print("❌ ERROR: .env file not found!")
        print("\nPlease create a .env file with your Alpaca credentials:")
        print("  APCA_API_KEY_ID=...")
        print("  APCA_API_SECRET_KEY=...")
        print("  ALPACA_PAPER=true")
        print("  ALPACA_CRYPTO=true")
        exit(1)

    main()
