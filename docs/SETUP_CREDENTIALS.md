# Setting Up Alpaca API Credentials

## For Team Members

1. **Copy the example environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Get your Alpaca API keys:**
   - Go to [Alpaca Paper Trading Dashboard](https://app.alpaca.markets/paper/dashboard/overview)
   - Create an account or log in
   - Generate your API keys (View -> Regenerate if needed)

3. **Fill in your `.env` file:**
   ```
   ALPACA_API_KEY=your_actual_key_here
   APCA-API-SECRET-KEY=your_actual_secret_here
   ALPACA_PAPER=true
   ```

4. **Use in your Python code:**

   **Option A: Using our AlpacaTrader class (Recommended):**
   ```python
   from src.live import AlpacaConfig, AlpacaTrader

   # Load credentials from .env automatically
   config = AlpacaConfig.from_env()

   # Initialize trader
   trader = AlpacaTrader(config)

   # Get account info
   account = trader.get_account()
   print(f"Buying power: ${account['buying_power']}")

   # Get positions
   positions = trader.get_positions()
   for pos in positions:
       print(f"{pos['symbol']}: {pos['quantity']} shares")
   ```

   **Option B: Using alpaca-py SDK directly:**
   ```python
   from dotenv import load_dotenv
   import os
   from alpaca.trading.client import TradingClient

   # Load environment variables
   load_dotenv()

   # Initialize Alpaca API (using new alpaca-py SDK)
   trading_client = TradingClient(
       api_key=os.getenv('ALPACA_API_KEY'),
       secret_key=os.getenv('APCA-API-SECRET-KEY'),
       paper=True  # Use paper trading
   )

   # Get account
   account = trading_client.get_account()
   print(f"Cash: ${account.cash}")
   ```

## Important Notes

- **NEVER commit your `.env` file** - it's already in `.gitignore`
- Each team member should use their own paper trading account
- The `.env` file stays local on your machine only
- If you accidentally commit credentials, regenerate them immediately at Alpaca
- We use the **new `alpaca-py` SDK** (not the deprecated `alpaca-trade-api`)

## Testing Your Setup

Run this quick test to verify your credentials work:

```bash
uv run python -c "from src.live import AlpacaConfig, AlpacaTrader; trader = AlpacaTrader(AlpacaConfig.from_env()); print(trader.get_account())"
```

You should see your account details printed (cash, buying power, equity, etc.).
