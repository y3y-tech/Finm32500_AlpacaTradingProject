#!/bin/bash
#
# Run Crypto Multi and Adaptive Portfolio Traders
#
# This script launches both trading systems in separate tmux sessions:
# 1. Crypto Multi Trader - 19 strategies across 23 crypto pairs
# 2. Adaptive Portfolio Trader - 19 strategies on stocks/ETFs with dynamic allocation
#
# Usage:
#   ./scripts/traders/run_both_traders.sh [options]
#
# Options:
#   --min-warmup-bars N     Override warmup bars for both traders (default: 20 for multi, 70 for adaptive)
#   --log-level LEVEL       Set log level for both traders (default: INFO)
#   --initial-cash AMOUNT   Set initial cash for adaptive trader (default: 80000)
#   --kill-existing         Kill existing sessions without prompting
#   --attach-multi          Attach to multi trader session after starting
#   --attach-adaptive       Attach to adaptive trader session after starting
#

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Default values
MIN_WARMUP_BARS_MULTI=""
MIN_WARMUP_BARS_ADAPTIVE=""
LOG_LEVEL="INFO"
INITIAL_CASH="40000"
KILL_EXISTING=false
ATTACH_MULTI=false
ATTACH_ADAPTIVE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --min-warmup-bars)
            MIN_WARMUP_BARS_MULTI="$2"
            MIN_WARMUP_BARS_ADAPTIVE="$2"
            shift 2
            ;;
        --log-level)
            LOG_LEVEL="$2"
            shift 2
            ;;
        --initial-cash)
            INITIAL_CASH="$2"
            shift 2
            ;;
        --kill-existing)
            KILL_EXISTING=true
            shift
            ;;
        --attach-multi)
            ATTACH_MULTI=true
            shift
            ;;
        --attach-adaptive)
            ATTACH_ADAPTIVE=true
            shift
            ;;
        --help|-h)
            echo "Run Crypto Multi and Adaptive Portfolio Traders"
            echo ""
            echo "Usage:"
            echo "  ./scripts/traders/run_both_traders.sh [options]"
            echo ""
            echo "Options:"
            echo "  --min-warmup-bars N       Override warmup bars for both traders"
            echo "  --log-level LEVEL         Set log level (DEBUG, INFO, WARNING, ERROR)"
            echo "  --initial-cash AMOUNT     Initial cash for adaptive trader (default: 80000)"
            echo "  --kill-existing           Kill existing sessions without prompting"
            echo "  --attach-multi            Attach to multi trader after starting"
            echo "  --attach-adaptive         Attach to adaptive trader after starting"
            echo ""
            echo "Tmux Session Names:"
            echo "  - crypto_multi:        Multi-strategy crypto trader (19 strategies, 23 crypto pairs)"
            echo "  - adaptive_portfolio:  Adaptive portfolio trader (19 strategies, stocks/ETFs)"
            echo ""
            echo "Management Commands:"
            echo "  Attach to multi:     tmux attach -t crypto_multi"
            echo "  Attach to adaptive:  tmux attach -t adaptive_portfolio"
            echo "  List sessions:       tmux ls"
            echo "  Kill multi:          tmux kill-session -t crypto_multi"
            echo "  Kill adaptive:       tmux kill-session -t adaptive_portfolio"
            echo "  Kill both:           tmux kill-session -t crypto_multi && tmux kill-session -t adaptive_portfolio"
            echo ""
            echo "Examples:"
            echo "  # Start both with defaults"
            echo "  ./scripts/traders/run_both_traders.sh"
            echo ""
            echo "  # Start with debug logging and faster warmup"
            echo "  ./scripts/traders/run_both_traders.sh --log-level DEBUG --min-warmup-bars 10"
            echo ""
            echo "  # Kill existing and restart"
            echo "  ./scripts/traders/run_both_traders.sh --kill-existing"
            echo ""
            echo "  # Start and attach to multi trader"
            echo "  ./scripts/traders/run_both_traders.sh --attach-multi"
            echo ""
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Check if tmux is installed
if ! command -v tmux &> /dev/null; then
    echo "Error: tmux is not installed"
    echo "Install with: brew install tmux (macOS) or apt install tmux (Linux)"
    exit 1
fi

# Session names
SESSION_MULTI="crypto_multi"
SESSION_ADAPTIVE="adaptive_portfolio"

# Function to check and handle existing session
handle_existing_session() {
    local session_name="$1"
    if tmux has-session -t "$session_name" 2>/dev/null; then
        if $KILL_EXISTING; then
            echo "Killing existing session: $session_name"
            tmux kill-session -t "$session_name"
            return 0
        else
            echo "Session '$session_name' already exists!"
            read -p "Kill and restart? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                tmux kill-session -t "$session_name"
                echo "Killed existing session: $session_name"
                return 0
            else
                echo "Skipping $session_name (already running)"
                return 1
            fi
        fi
    fi
    return 0
}

echo "============================================================================="
echo "Starting Crypto Trading Systems"
echo "============================================================================="
echo ""
echo "Configuration:"
echo "  Log Level: $LOG_LEVEL"
[ -n "$MIN_WARMUP_BARS_MULTI" ] && echo "  Warmup Bars: $MIN_WARMUP_BARS_MULTI (both traders)"
echo "  Initial Cash (Adaptive): \$$INITIAL_CASH"
echo ""

# ============================================================================
# 1. Start Crypto Multi Trader
# ============================================================================

echo "-----------------------------------------------------------------------------"
echo "1. Crypto Multi Trader (19 strategies, 23 crypto pairs)"
echo "-----------------------------------------------------------------------------"

if handle_existing_session "$SESSION_MULTI"; then
    # Build command for multi trader
    MULTI_CMD="python scripts/traders/run_crypto_adaptive_multi.py --log-level $LOG_LEVEL"
    [ -n "$MIN_WARMUP_BARS_MULTI" ] && MULTI_CMD="$MULTI_CMD --min-warmup-bars $MIN_WARMUP_BARS_MULTI"

    echo "Starting session: $SESSION_MULTI"
    echo "Command: $MULTI_CMD"

    # Create tmux session
    tmux new-session -d -s "$SESSION_MULTI" -c "$PROJECT_DIR"
    tmux send-keys -t "$SESSION_MULTI" "source .venv/bin/activate" C-m
    tmux send-keys -t "$SESSION_MULTI" "clear" C-m
    tmux send-keys -t "$SESSION_MULTI" "$MULTI_CMD" C-m

    echo "✓ Started: $SESSION_MULTI"
else
    echo "⊘ Skipped: $SESSION_MULTI"
fi
echo ""

# ============================================================================
# 2. Start Adaptive Crypto Trader
# ============================================================================

echo "-----------------------------------------------------------------------------"
echo "2. Adaptive Portfolio Trader (19 strategies on stocks/ETFs)"
echo "-----------------------------------------------------------------------------"

if handle_existing_session "$SESSION_ADAPTIVE"; then
    # Build command for adaptive trader
    ADAPTIVE_CMD="python scripts/traders/run_adaptive_portfolio.py --log-level $LOG_LEVEL --initial-cash $INITIAL_CASH"
    [ -n "$MIN_WARMUP_BARS_ADAPTIVE" ] && ADAPTIVE_CMD="$ADAPTIVE_CMD --min-warmup-bars $MIN_WARMUP_BARS_ADAPTIVE"

    echo "Starting session: $SESSION_ADAPTIVE"
    echo "Command: $ADAPTIVE_CMD"

    # Create tmux session
    tmux new-session -d -s "$SESSION_ADAPTIVE" -c "$PROJECT_DIR"
    tmux send-keys -t "$SESSION_ADAPTIVE" "source .venv/bin/activate" C-m
    tmux send-keys -t "$SESSION_ADAPTIVE" "clear" C-m
    tmux send-keys -t "$SESSION_ADAPTIVE" "$ADAPTIVE_CMD" C-m

    echo "✓ Started: $SESSION_ADAPTIVE"
else
    echo "⊘ Skipped: $SESSION_ADAPTIVE"
fi
echo ""

# ============================================================================
# Summary
# ============================================================================

echo "============================================================================="
echo "Crypto Trading Systems Started"
echo "============================================================================="
echo ""
echo "Active Sessions:"
tmux ls 2>/dev/null | grep -E "(crypto_multi|adaptive_portfolio)" || echo "  (none active)"
echo ""
echo "Management Commands:"
echo "  View crypto multi:     tmux attach -t crypto_multi"
echo "  View adaptive:         tmux attach -t adaptive_portfolio"
echo "  List all sessions:     tmux ls"
echo "  Kill crypto multi:     tmux kill-session -t crypto_multi"
echo "  Kill adaptive:         tmux kill-session -t adaptive_portfolio"
echo ""
echo "Tmux Quick Reference:"
echo "  Detach from session:   Ctrl+b then d"
echo "  Switch windows:        Ctrl+b then n (next) or p (previous)"
echo "  Stop trader:           Ctrl+C (while attached)"
echo ""
echo "Logs saved to: logs/"
echo "============================================================================="
echo ""

# Attach to session if requested
if $ATTACH_MULTI; then
    echo "Attaching to crypto_multi session..."
    sleep 1
    tmux attach -t "$SESSION_MULTI"
elif $ATTACH_ADAPTIVE; then
    echo "Attaching to crypto_adaptive session..."
    sleep 1
    tmux attach -t "$SESSION_ADAPTIVE"
fi
