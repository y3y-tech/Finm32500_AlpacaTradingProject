#!/bin/bash
# Helper script to check for active trader connections

echo "Checking for active live trader processes..."
PROCS=$(ps aux | grep -i "live_adaptive" | grep -v grep | grep -v check_connections)

if [ -z "$PROCS" ]; then
    echo "✅ No active trader processes found"
    echo ""
    echo "It's safe to start trading now. Try:"
    echo "  python scripts/traders/live_adaptive_trader.py --tickers BTC/USD ETH/USD --min-warmup-bars 5"
else
    echo "⚠️  Found active processes:"
    echo "$PROCS"
    echo ""
    echo "Kill them with: kill -9 <PID>"
    echo "Then wait 30-60 seconds before reconnecting"
fi
