#!/bin/bash
#
# Live Adaptive Sector ETF Trader Launcher
#
# This script launches the live sector ETF trader in a dedicated tmux session
# for easy monitoring and background operation.
#
# NOTE: This trader only works during market hours (9:30 AM - 4:00 PM ET, Mon-Fri)
#
# Usage:
#   ./scripts/run_sector_trader.sh              # Start with default settings
#   ./scripts/run_sector_trader.sh --save-data  # Save data to CSV
#   ./scripts/run_sector_trader.sh --help       # Show help
#

SESSION_NAME="sector_trader"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Check if tmux is installed
if ! command -v tmux &> /dev/null; then
    echo "❌ Error: tmux is not installed"
    echo "Install with: brew install tmux (macOS) or apt install tmux (Linux)"
    exit 1
fi

# Check if session already exists
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "⚠️  Session '$SESSION_NAME' already exists!"
    echo ""
    echo "Options:"
    echo "  1. Attach to existing session: tmux attach -t $SESSION_NAME"
    echo "  2. Kill existing session: tmux kill-session -t $SESSION_NAME"
    echo "  3. Use a different session name"
    echo ""
    read -p "Kill existing session and restart? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        tmux kill-session -t "$SESSION_NAME"
        echo "✅ Killed existing session"
    else
        echo "Aborting."
        exit 0
    fi
fi

# Build the Python command with arguments
PYTHON_CMD="python scripts/traders/live_adaptive_sector_trader.py"

# Add default flags for optimal sector ETF trading
PYTHON_CMD="$PYTHON_CMD --min-warmup-bars 30"  # 30 bars warmup
PYTHON_CMD="$PYTHON_CMD --save-data"            # Always save data
PYTHON_CMD="$PYTHON_CMD --log-level INFO"       # INFO level logging

# Pass through any additional arguments
if [ $# -gt 0 ]; then
    PYTHON_CMD="$PYTHON_CMD $@"
fi

# Create new tmux session
echo "🚀 Starting Live Adaptive Sector ETF Trader..."
echo "   Session: $SESSION_NAME"
echo "   Command: $PYTHON_CMD"
echo ""
echo "⚠️  REMINDER: Stock markets are only open 9:30 AM - 4:00 PM ET, Mon-Fri"
echo "   Pre-market: 4:00 AM - 9:30 AM ET"
echo "   After-hours: 4:00 PM - 8:00 PM ET"
echo ""

tmux new-session -d -s "$SESSION_NAME" -c "$PROJECT_DIR"

# Set up the tmux window
tmux send-keys -t "$SESSION_NAME" "source .venv/bin/activate" C-m
tmux send-keys -t "$SESSION_NAME" "clear" C-m
tmux send-keys -t "$SESSION_NAME" "$PYTHON_CMD" C-m

echo "✅ Session started successfully!"
echo ""
echo "📊 To view the trader:"
echo "   tmux attach -t $SESSION_NAME"
echo ""
echo "🛑 To stop the trader:"
echo "   1. Attach to session: tmux attach -t $SESSION_NAME"
echo "   2. Press Ctrl+C to stop"
echo "   3. Detach with: Ctrl+b then d"
echo ""
echo "   Or kill session directly: tmux kill-session -t $SESSION_NAME"
echo ""
echo "📋 Useful tmux commands:"
echo "   - Detach from session: Ctrl+b then d"
echo "   - List sessions: tmux ls"
echo "   - Kill session: tmux kill-session -t $SESSION_NAME"
echo ""
echo "📝 Logs saved to: logs/live_adaptive_trader.log"
echo "💾 Data saved to: logs/live_session_$(date +%Y%m%d).csv"
echo ""
