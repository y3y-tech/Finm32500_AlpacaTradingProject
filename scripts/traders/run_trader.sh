#!/bin/bash
#
# Unified Live Trader Launcher
#
# This script launches any live trader in a dedicated tmux session
# for easy monitoring and background operation.
#
# Usage:
#   ./scripts/traders/run_trader.sh <path-to-trader.py> [options]
#
# Examples:
#   ./scripts/traders/run_trader.sh scripts/traders/live_adaptive_sector_trader.py
#   ./scripts/traders/run_trader.sh scripts/traders/live_adaptive_crypto_trader.py --save-data
#   ./scripts/traders/run_trader.sh scripts/traders/my_custom_trader.py --log-level DEBUG
#

# Show help
if [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]] || [[ -z "$1" ]]; then
    echo "Unified Live Trader Launcher"
    echo ""
    echo "Usage:"
    echo "  ./scripts/traders/run_trader.sh <path-to-trader.py> [options]"
    echo ""
    echo "Examples:"
    echo "  ./scripts/traders/run_trader.sh scripts/traders/live_adaptive_sector_trader.py"
    echo "  ./scripts/traders/run_trader.sh scripts/traders/live_adaptive_crypto_trader.py"
    echo "  ./scripts/traders/run_trader.sh scripts/traders/my_custom_trader.py --save-data"
    echo ""
    echo "Options (passed to trader script):"
    echo "  --save-data              Save market data to CSV"
    echo "  --min-warmup-bars N      Minimum bars before trading (default: 20)"
    echo "  --log-level LEVEL        Logging level (DEBUG, INFO, WARNING, ERROR)"
    echo "  --symbols SYM1 SYM2      Override default symbols"
    echo "  --strategies S1 S2       Override default strategies"
    echo ""
    echo "Tmux Session Management:"
    echo "  Attach to session:  tmux attach -t <session-name>"
    echo "  List sessions:      tmux ls"
    echo "  Kill session:       tmux kill-session -t <session-name>"
    echo "  Detach:             Ctrl+b then d"
    echo ""
    exit 0
fi

PYTHON_SCRIPT="$1"
shift  # Remove first argument, rest are passed to Python

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Check if Python script exists
if [[ ! -f "$PYTHON_SCRIPT" ]]; then
    echo "Error: Python script not found: $PYTHON_SCRIPT"
    exit 1
fi

# Check if tmux is installed
if ! command -v tmux &> /dev/null; then
    echo "Error: tmux is not installed"
    echo "Install with: brew install tmux (macOS) or apt install tmux (Linux)"
    exit 1
fi

# Derive session name and trader description from script filename
SCRIPT_BASENAME="$(basename "$PYTHON_SCRIPT" .py)"
SESSION_NAME="${SCRIPT_BASENAME}"
TRADER_DESC="${SCRIPT_BASENAME}"

# Check if session already exists
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "Session '$SESSION_NAME' already exists!"
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
        echo "Killed existing session"
    else
        echo "Aborting."
        exit 0
    fi
fi

# Build the Python command with arguments
PYTHON_CMD="python $PYTHON_SCRIPT"

# Add default flags (unless they're already provided in args)
if [[ ! "$*" =~ "--min-warmup-bars" ]]; then
    PYTHON_CMD="$PYTHON_CMD --min-warmup-bars 20"
fi
if [[ ! "$*" =~ "--log-level" ]]; then
    PYTHON_CMD="$PYTHON_CMD --log-level INFO"
fi
# Always save data by default (unless --no-save-data is specified)
if [[ ! "$*" =~ "--save-data" ]] && [[ ! "$*" =~ "--no-save-data" ]]; then
    PYTHON_CMD="$PYTHON_CMD --save-data"
fi

# Pass through any additional arguments
if [ $# -gt 0 ]; then
    PYTHON_CMD="$PYTHON_CMD $@"
fi

# Create new tmux session
echo "Starting $TRADER_DESC..."
echo "   Session: $SESSION_NAME"
echo "   Command: $PYTHON_CMD"
echo ""

tmux new-session -d -s "$SESSION_NAME" -c "$PROJECT_DIR"

# Set up the tmux window
tmux send-keys -t "$SESSION_NAME" "source .venv/bin/activate" C-m
tmux send-keys -t "$SESSION_NAME" "clear" C-m
tmux send-keys -t "$SESSION_NAME" "$PYTHON_CMD" C-m

echo "Session started successfully!"
echo ""
echo "To view the trader:"
echo "   tmux attach -t $SESSION_NAME"
echo ""
echo "To stop the trader:"
echo "   1. Attach to session: tmux attach -t $SESSION_NAME"
echo "   2. Press Ctrl+C to stop"
echo "   3. Detach with: Ctrl+b then d"
echo ""
echo "   Or kill session directly: tmux kill-session -t $SESSION_NAME"
echo ""
echo "Useful tmux commands:"
echo "   - Detach from session: Ctrl+b then d"
echo "   - List sessions: tmux ls"
echo "   - Kill session: tmux kill-session -t $SESSION_NAME"
echo ""
echo "Logs typically saved to: logs/"
echo ""
