"""
Trading Portfolio - Tracks positions, cash, trades, and performance metrics.

Maintains complete state of portfolio with P&L calculation and equity curve tracking.
"""

from datetime import datetime
import logging
import pandas as pd

from AlpacaTrading.models import Trade, Position, OrderSide

logger = logging.getLogger(__name__)


class TradingPortfolio:
    """
    Manages portfolio state with position tracking and P&L calculation.

    Tracks:
    - Cash balance
    - Positions by symbol
    - Trade history
    - Equity curve over time
    - Performance metrics

    Example:
        portfolio = TradingPortfolio(initial_cash=100_000)
        portfolio.process_trade(trade)
        portfolio.update_prices(current_prices)

        total_value = portfolio.get_total_value()
        metrics = portfolio.get_performance_metrics()
    """

    def __init__(self, initial_cash: float):
        """
        Initialize portfolio.

        Args:
            initial_cash: Starting cash balance
        """
        if initial_cash <= 0:
            raise ValueError("Initial cash must be positive")

        self.initial_cash = initial_cash
        self.cash = initial_cash

        # Positions by symbol
        self.positions: dict[str, Position] = {}

        # Trade history
        self.trades: list[Trade] = []

        # Equity curve: [(timestamp, total_value)]
        self.equity_curve: list[tuple[datetime, float]] = []

        # Track high water mark for drawdown calculation
        self.high_water_mark = initial_cash

    def process_trade(self, trade: Trade) -> None:
        """
        Process executed trade and update portfolio state.

        Updates:
        - Position quantity and cost basis
        - Cash balance
        - Trade history

        Args:
            trade: Executed trade to process
        """
        # Add to trade history
        self.trades.append(trade)

        # Update or create position
        if trade.symbol not in self.positions:
            self.positions[trade.symbol] = Position(symbol=trade.symbol)

        position = self.positions[trade.symbol]
        position.update_from_trade(trade)

        # Update cash
        if trade.side == OrderSide.BUY:
            # Buying: reduce cash
            self.cash -= trade.value
        else:  # SELL
            # Selling: increase cash
            self.cash += trade.value

    def update_prices(self, current_prices: dict[str, float]) -> None:
        """
        Update unrealized P&L for all positions based on current market prices.

        Args:
            current_prices: Dictionary of {symbol: price}
        """
        for symbol, position in self.positions.items():
            if symbol in current_prices:
                position.update_unrealized_pnl(current_prices[symbol])

    def record_equity(
        self, timestamp: datetime, current_prices: dict[str, float]
    ) -> None:
        """
        Record current portfolio value to equity curve.

        Args:
            timestamp: Current timestamp
            current_prices: Current market prices
        """
        self.update_prices(current_prices)
        total_value = self.get_total_value()
        self.equity_curve.append((timestamp, total_value))

        # Update high water mark
        if total_value > self.high_water_mark:
            self.high_water_mark = total_value

    def get_total_value(self) -> float:
        """
        Calculate total portfolio value (cash + positions).

        Returns:
            Total portfolio value
        """
        position_value = sum(
            pos.quantity * pos.average_cost + pos.unrealized_pnl
            for pos in self.positions.values()
        )
        return self.cash + position_value

    def get_position(self, symbol: str) -> Position | None:
        """
        Get position for a symbol.

        Args:
            symbol: Asset symbol

        Returns:
            Position object or None if no position
        """
        return self.positions.get(symbol)

    def get_total_pnl(self) -> float:
        """
        Calculate total P&L (realized + unrealized).

        Returns:
            Total P&L
        """
        return sum(pos.total_pnl for pos in self.positions.values())

    def get_realized_pnl(self) -> float:
        """
        Calculate total realized P&L.

        Returns:
            Total realized P&L
        """
        return sum(pos.realized_pnl for pos in self.positions.values())

    def get_unrealized_pnl(self) -> float:
        """
        Calculate total unrealized P&L.

        Returns:
            Total unrealized P&L
        """
        return sum(pos.unrealized_pnl for pos in self.positions.values())

    def log_metrics(self, log_file: str = "logs/portfolio_metrics.csv") -> None:
        """
        Log portfolio metrics to CSV file for monitoring and analysis.

        Args:
            log_file: Path to metrics log file (default: logs/portfolio_metrics.csv)
        """
        from pathlib import Path
        import csv

        metrics = self.get_performance_metrics()
        total_value = self.get_total_value()
        timestamp = datetime.now()

        # Create log directory if needed
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)

        # Check if file exists to write header
        file_exists = Path(log_file).exists()

        # Write metrics to CSV
        with open(log_file, "a", newline="") as f:
            writer = csv.writer(f)

            # Write header if new file
            if not file_exists:
                writer.writerow(
                    [
                        "timestamp",
                        "cash",
                        "total_value",
                        "total_return_%",
                        "total_pnl",
                        "realized_pnl",
                        "unrealized_pnl",
                        "num_positions",
                        "num_trades",
                        "win_rate_%",
                        "max_drawdown_%",
                        "current_drawdown_%",
                    ]
                )

            # Write metrics row
            writer.writerow(
                [
                    timestamp.isoformat(),
                    f"{self.cash:.2f}",
                    f"{total_value:.2f}",
                    f"{metrics['total_return']:.2f}",
                    f"{metrics['total_pnl']:.2f}",
                    f"{metrics['realized_pnl']:.2f}",
                    f"{metrics['unrealized_pnl']:.2f}",
                    len(self.positions),
                    metrics["num_trades"],
                    f"{metrics['win_rate']:.2f}",
                    f"{metrics['max_drawdown']:.2f}",
                    f"{metrics['current_drawdown']:.2f}",
                ]
            )

        logger.debug(
            f"Logged metrics: Value=${total_value:,.2f}, Return={metrics['total_return']:+.2f}%, "
            f"Drawdown={metrics['current_drawdown']:.2f}%"
        )

    def get_performance_metrics(self) -> dict:
        """
        Calculate comprehensive performance metrics.

        Returns:
            Dictionary with metrics:
            - total_return: Overall return (%)
            - total_pnl: Total P&L ($)
            - realized_pnl: Realized P&L ($)
            - unrealized_pnl: Unrealized P&L ($)
            - num_trades: Total number of trades
            - winning_trades: Number of profitable trades
            - losing_trades: Number of losing trades
            - win_rate: Percentage of winning trades
            - avg_win: Average profit on winning trades
            - avg_loss: Average loss on losing trades
            - max_drawdown: Maximum drawdown (%)
            - current_drawdown: Current drawdown from peak (%)
        """
        total_value = self.get_total_value()
        total_return = (total_value / self.initial_cash - 1) * 100

        # Trade analysis
        winning_trades = 0
        losing_trades = 0
        total_win = 0.0
        total_loss = 0.0

        # Group trades by symbol to calculate P&L
        symbol_trades: dict[str, list[Trade]] = {}
        for trade in self.trades:
            if trade.symbol not in symbol_trades:
                symbol_trades[trade.symbol] = []
            symbol_trades[trade.symbol].append(trade)

        # Simplified win/loss calculation
        for position in self.positions.values():
            if position.realized_pnl > 0:
                winning_trades += 1
                total_win += position.realized_pnl
            elif position.realized_pnl < 0:
                losing_trades += 1
                total_loss += position.realized_pnl

        win_rate = (
            (winning_trades / (winning_trades + losing_trades) * 100)
            if (winning_trades + losing_trades) > 0
            else 0
        )
        avg_win = total_win / winning_trades if winning_trades > 0 else 0
        avg_loss = total_loss / losing_trades if losing_trades > 0 else 0

        # Drawdown calculation
        max_dd = self._calculate_max_drawdown()
        current_dd = (self.high_water_mark - total_value) / self.high_water_mark * 100

        return {
            "total_return": total_return,
            "total_pnl": self.get_total_pnl(),
            "realized_pnl": self.get_realized_pnl(),
            "unrealized_pnl": self.get_unrealized_pnl(),
            "num_trades": len(self.trades),
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "max_drawdown": max_dd,
            "current_drawdown": current_dd,
        }

    def _calculate_max_drawdown(self) -> float:
        """
        Calculate maximum drawdown from equity curve.

        Returns:
            Maximum drawdown as percentage
        """
        if len(self.equity_curve) < 2:
            return 0.0

        values = [val for _, val in self.equity_curve]
        max_dd = 0.0
        peak = values[0]

        for value in values:
            if value > peak:
                peak = value
            dd = (peak - value) / peak * 100
            if dd > max_dd:
                max_dd = dd

        return max_dd

    def get_sharpe_ratio(self, risk_free_rate: float = 0.0) -> float:
        """
        Calculate annualized Sharpe ratio from equity curve.

        Args:
            risk_free_rate: Annual risk-free rate (default: 0.0)

        Returns:
            Annualized Sharpe ratio
        """
        if len(self.equity_curve) < 2:
            return 0.0

        # Convert to pandas series for easier calculation
        df = pd.DataFrame(self.equity_curve, columns=["timestamp", "value"])
        df["returns"] = df["value"].pct_change()

        # Calculate Sharpe
        mean_return = df["returns"].mean()
        std_return = df["returns"].std()

        if std_return == 0:
            return 0.0

        # Annualize (assuming daily data)
        sharpe = (mean_return - risk_free_rate / 252) / std_return * (252**0.5)
        return sharpe

    def get_equity_curve_dataframe(self) -> pd.DataFrame:
        """
        Get equity curve as pandas DataFrame.

        Returns:
            DataFrame with columns: timestamp, value
        """
        return pd.DataFrame(self.equity_curve, columns=["timestamp", "value"])

    def reset(self) -> None:
        """Reset portfolio to initial state."""
        self.cash = self.initial_cash
        self.positions.clear()
        self.trades.clear()
        self.equity_curve.clear()
        self.high_water_mark = self.initial_cash

    def __repr__(self) -> str:
        total_value = self.get_total_value()
        return (
            f"TradingPortfolio(cash=${self.cash:,.2f}, "
            f"positions={len(self.positions)}, "
            f"total_value=${total_value:,.2f}, "
            f"pnl=${self.get_total_pnl():,.2f})"
        )
