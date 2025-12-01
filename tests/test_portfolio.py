import numpy as np
import pytest
from datetime import datetime, timedelta

from AlpacaTrading.trading.portfolio import TradingPortfolio
from AlpacaTrading.models import Trade, Position, OrderSide


# Helper function to create trades with auto-generated IDs
_trade_counter = 0

def create_trade(symbol, side, quantity, price, timestamp=None):
    """Helper to create Trade with auto-generated IDs"""
    global _trade_counter
    _trade_counter += 1
    return Trade(
        trade_id=f"t{_trade_counter}",
        order_id=f"o{_trade_counter}",
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
        timestamp=timestamp or datetime.now()
    )


class TestErrorHandling:
    def test_initial_cash_positive(self):
        with pytest.raises(ValueError, match="Initial cash must be positive"):
            TradingPortfolio(-10)

    def test_initial_cash_zero(self):
        with pytest.raises(ValueError, match="Initial cash must be positive"):
            TradingPortfolio(0)


class TestInitialization:
    def test_valid_initialization(self):
        portfolio = TradingPortfolio(100_000)
        assert portfolio.initial_cash == 100_000
        assert portfolio.cash == 100_000
        assert len(portfolio.positions) == 0
        assert len(portfolio.trades) == 0
        assert len(portfolio.equity_curve) == 0
        assert portfolio.high_water_mark == 100_000

    def test_initialization_preserves_initial_cash(self):
        initial = 50_000
        portfolio = TradingPortfolio(initial)
        portfolio.cash = 30_000
        assert portfolio.initial_cash == initial


class TestProcessTrade:
    def test_process_buy_trade_creates_position(self):
        portfolio = TradingPortfolio(100_000)
        trade = create_trade("AAPL", OrderSide.BUY, 100, 150.0)

        portfolio.process_trade(trade)

        assert "AAPL" in portfolio.positions
        position = portfolio.get_position("AAPL")
        assert position.quantity == 100
        assert position.average_cost == 150.0
        assert portfolio.cash == 100_000 - 15_000
        assert len(portfolio.trades) == 1

    def test_process_sell_trade(self):
        portfolio = TradingPortfolio(100_000)

        # First buy
        buy_trade = create_trade("AAPL", OrderSide.BUY, 100, 150.0)
        portfolio.process_trade(buy_trade)

        # Then sell
        sell_trade = create_trade("AAPL", OrderSide.SELL, 50, 160.0)
        portfolio.process_trade(sell_trade)

        position = portfolio.get_position("AAPL")
        assert position.quantity == 50
        assert portfolio.cash == 100_000 - 15_000 + 8_000
        assert len(portfolio.trades) == 2

    def test_process_multiple_buys_averages_cost(self):
        portfolio = TradingPortfolio(100_000)

        trade1 = create_trade("AAPL", OrderSide.BUY, 100, 150.0)
        trade2 = create_trade("AAPL", OrderSide.BUY, 100, 160.0)

        portfolio.process_trade(trade1)
        portfolio.process_trade(trade2)

        position = portfolio.get_position("AAPL")
        assert position.quantity == 200
        assert position.average_cost == 155.0  # (150*100 + 160*100) / 200

    def test_process_multiple_symbols(self):
        portfolio = TradingPortfolio(100_000)

        trade1 = create_trade("AAPL", OrderSide.BUY, 100, 150.0)
        trade2 = create_trade("MSFT", OrderSide.BUY, 50, 300.0)

        portfolio.process_trade(trade1)
        portfolio.process_trade(trade2)

        assert len(portfolio.positions) == 2
        assert portfolio.get_position("AAPL").quantity == 100
        assert portfolio.get_position("MSFT").quantity == 50
        assert portfolio.cash == 100_000 - 15_000 - 15_000


class TestUpdatePrices:
    def test_update_prices_single_position(self):
        portfolio = TradingPortfolio(100_000)
        trade = create_trade("AAPL", OrderSide.BUY, 100, 150.0)
        portfolio.process_trade(trade)

        portfolio.update_prices({"AAPL": 160.0})

        position = portfolio.get_position("AAPL")
        assert position.unrealized_pnl == 1000.0  # 100 * (160 - 150)

    def test_update_prices_multiple_positions(self):
        portfolio = TradingPortfolio(100_000)

        trade1 = create_trade("AAPL", OrderSide.BUY, 100, 150.0)
        trade2 = create_trade("MSFT", OrderSide.BUY, 50, 300.0)

        portfolio.process_trade(trade1)
        portfolio.process_trade(trade2)

        portfolio.update_prices({"AAPL": 155.0, "MSFT": 310.0})

        assert portfolio.get_position("AAPL").unrealized_pnl == 500.0
        assert portfolio.get_position("MSFT").unrealized_pnl == 500.0

    def test_update_prices_missing_symbol(self):
        portfolio = TradingPortfolio(100_000)
        trade = create_trade("AAPL", OrderSide.BUY, 100, 150.0)
        portfolio.process_trade(trade)

        # Update with different symbol - should not error
        portfolio.update_prices({"MSFT": 300.0})

        position = portfolio.get_position("AAPL")
        assert position.unrealized_pnl == 0.0  # Not updated


class TestRecordEquity:
    def test_record_equity_updates_curve(self):
        portfolio = TradingPortfolio(100_000)
        trade = create_trade("AAPL", OrderSide.BUY, 100, 150.0)
        portfolio.process_trade(trade)

        timestamp = datetime.now()
        portfolio.record_equity(timestamp, {"AAPL": 160.0})

        assert len(portfolio.equity_curve) == 1
        assert portfolio.equity_curve[0][0] == timestamp
        assert portfolio.equity_curve[0][1] == 100_000 + 1000  # Cash + unrealized P&L

    def test_record_equity_updates_high_water_mark(self):
        portfolio = TradingPortfolio(100_000)

        # Price goes up
        trade = create_trade("AAPL", OrderSide.BUY, 100, 150.0)
        portfolio.process_trade(trade)
        portfolio.record_equity(datetime.now(), {"AAPL": 160.0})

        assert portfolio.high_water_mark == 101_000

    def test_record_equity_high_water_mark_doesnt_decrease(self):
        portfolio = TradingPortfolio(100_000)
        trade = create_trade("AAPL", OrderSide.BUY, 100, 150.0)
        portfolio.process_trade(trade)

        portfolio.record_equity(datetime.now(), {"AAPL": 160.0})
        high_water = portfolio.high_water_mark

        portfolio.record_equity(datetime.now(), {"AAPL": 140.0})

        assert portfolio.high_water_mark == high_water  # Doesn't decrease


class TestGetTotalValue:
    def test_total_value_cash_only(self):
        portfolio = TradingPortfolio(100_000)
        assert portfolio.get_total_value() == 100_000

    def test_total_value_with_positions(self):
        portfolio = TradingPortfolio(100_000)
        trade = create_trade("AAPL", OrderSide.BUY, 100, 150.0)
        portfolio.process_trade(trade)

        # Cash: 85,000, Position: 100 * 150 = 15,000
        assert portfolio.get_total_value() == 100_000

    def test_total_value_with_unrealized_pnl(self):
        portfolio = TradingPortfolio(100_000)
        trade = create_trade("AAPL", OrderSide.BUY, 100, 150.0)
        portfolio.process_trade(trade)
        portfolio.update_prices({"AAPL": 160.0})

        # Cash: 85,000, Position value: 15,000, Unrealized P&L: 1,000
        assert portfolio.get_total_value() == 101_000


class TestGetPosition:
    def test_get_position_exists(self):
        portfolio = TradingPortfolio(100_000)
        trade = create_trade("AAPL", OrderSide.BUY, 100, 150.0)
        portfolio.process_trade(trade)

        position = portfolio.get_position("AAPL")
        assert position is not None
        assert position.symbol == "AAPL"

    def test_get_position_not_exists(self):
        portfolio = TradingPortfolio(100_000)
        position = portfolio.get_position("AAPL")
        assert position is None


class TestPnLCalculations:
    def test_unrealized_pnl(self):
        portfolio = TradingPortfolio(100_000)
        trade = create_trade("AAPL", OrderSide.BUY, 100, 150.0)
        portfolio.process_trade(trade)
        portfolio.update_prices({"AAPL": 160.0})

        assert portfolio.get_unrealized_pnl() == 1000.0

    def test_realized_pnl(self):
        portfolio = TradingPortfolio(100_000)

        buy_trade = create_trade("AAPL", OrderSide.BUY, 100, 150.0)
        sell_trade = create_trade("AAPL", OrderSide.SELL, 100, 160.0)

        portfolio.process_trade(buy_trade)
        portfolio.process_trade(sell_trade)

        assert portfolio.get_realized_pnl() == 1000.0

    def test_total_pnl(self):
        portfolio = TradingPortfolio(100_000)

        # Buy AAPL and sell half at profit
        buy_trade = create_trade("AAPL", OrderSide.BUY, 100, 150.0)
        sell_trade = create_trade("AAPL", OrderSide.SELL, 50, 160.0)

        portfolio.process_trade(buy_trade)
        portfolio.process_trade(sell_trade)
        portfolio.update_prices({"AAPL": 165.0})

        # Realized: 50 * (160-150) = 500
        # Unrealized: 50 * (165-150) = 750
        total_pnl = portfolio.get_total_pnl()
        assert total_pnl == 1250.0

    def test_pnl_multiple_positions(self):
        portfolio = TradingPortfolio(100_000)

        trade1 = create_trade("AAPL", OrderSide.BUY, 100, 150.0)
        trade2 = create_trade("MSFT", OrderSide.BUY, 50, 300.0)

        portfolio.process_trade(trade1)
        portfolio.process_trade(trade2)
        portfolio.update_prices({"AAPL": 155.0, "MSFT": 310.0})

        assert portfolio.get_unrealized_pnl() == 1000.0  # 500 + 500


class TestPerformanceMetrics:
    def test_performance_metrics_initial_state(self):
        portfolio = TradingPortfolio(100_000)
        metrics = portfolio.get_performance_metrics()

        assert metrics['total_return'] == 0.0
        assert metrics['total_pnl'] == 0.0
        assert metrics['num_trades'] == 0
        assert metrics['win_rate'] == 0.0
        assert metrics['max_drawdown'] == 0.0

    def test_performance_metrics_with_trades(self):
        portfolio = TradingPortfolio(100_000)

        buy_trade = create_trade("AAPL", OrderSide.BUY, 100, 150.0)
        sell_trade = create_trade("AAPL", OrderSide.SELL, 100, 160.0)

        portfolio.process_trade(buy_trade)
        portfolio.process_trade(sell_trade)

        metrics = portfolio.get_performance_metrics()

        assert metrics['num_trades'] == 2
        assert metrics['realized_pnl'] == 1000.0
        assert abs(metrics['total_return'] - 1.0) < 0.0001  # 1% return (allow for floating point precision)

    def test_performance_metrics_win_rate(self):
        portfolio = TradingPortfolio(100_000)

        # Winning trade
        buy1 = create_trade("AAPL", OrderSide.BUY, 100, 150.0)
        sell1 = create_trade("AAPL", OrderSide.SELL, 100, 160.0)

        # Losing trade
        buy2 = create_trade("MSFT", OrderSide.BUY, 50, 300.0)
        sell2 = create_trade("MSFT", OrderSide.SELL, 50, 290.0)

        portfolio.process_trade(buy1)
        portfolio.process_trade(sell1)
        portfolio.process_trade(buy2)
        portfolio.process_trade(sell2)

        metrics = portfolio.get_performance_metrics()

        assert metrics['winning_trades'] == 1
        assert metrics['losing_trades'] == 1
        assert metrics['win_rate'] == 50.0
        assert metrics['avg_win'] == 1000.0
        assert metrics['avg_loss'] == -500.0


class TestMaxDrawdown:
    def test_max_drawdown_no_equity_curve(self):
        portfolio = TradingPortfolio(100_000)
        assert portfolio._calculate_max_drawdown() == 0.0

    def test_max_drawdown_one_point(self):
        portfolio = TradingPortfolio(100_000)
        portfolio.equity_curve.append((datetime.now(), 100_000))
        assert portfolio._calculate_max_drawdown() == 0.0

    def test_max_drawdown_calculation(self):
        portfolio = TradingPortfolio(100_000)

        # Create equity curve: 100k -> 110k -> 95k -> 105k
        base_time = datetime.now()
        portfolio.equity_curve.append((base_time, 100_000))
        portfolio.equity_curve.append((base_time + timedelta(days=1), 110_000))
        portfolio.equity_curve.append((base_time + timedelta(days=2), 95_000))
        portfolio.equity_curve.append((base_time + timedelta(days=3), 105_000))

        max_dd = portfolio._calculate_max_drawdown()

        # Max drawdown: (110k - 95k) / 110k = 13.636%
        assert abs(max_dd - 13.636) < 0.01

    def test_current_drawdown_in_metrics(self):
        portfolio = TradingPortfolio(100_000)

        trade = create_trade("AAPL", OrderSide.BUY, 100, 150.0)
        portfolio.process_trade(trade)

        # Price goes up, then down
        portfolio.record_equity(datetime.now(), {"AAPL": 160.0})
        portfolio.record_equity(datetime.now(), {"AAPL": 145.0})

        metrics = portfolio.get_performance_metrics()

        # High water mark = 101k, current = 99.5k
        # Current DD = (101k - 99.5k) / 101k ≈ 1.49%
        assert metrics['current_drawdown'] > 0


class TestSharpeRatio:
    def test_sharpe_ratio_no_equity_curve(self):
        portfolio = TradingPortfolio(100_000)
        assert portfolio.get_sharpe_ratio() == 0.0

    def test_sharpe_ratio_one_point(self):
        portfolio = TradingPortfolio(100_000)
        portfolio.equity_curve.append((datetime.now(), 100_000))
        assert portfolio.get_sharpe_ratio() == 0.0

    def test_sharpe_ratio_calculation(self):
        portfolio = TradingPortfolio(100_000)

        # Create upward trending equity curve
        base_time = datetime.now()
        for i in range(10):
            value = 100_000 + i * 1000
            portfolio.equity_curve.append((base_time + timedelta(days=i), value))

        sharpe = portfolio.get_sharpe_ratio()

        # Should be positive for upward trend
        assert sharpe > 0

    def test_sharpe_ratio_with_risk_free_rate(self):
        portfolio = TradingPortfolio(100_000)

        base_time = datetime.now()
        for i in range(10):
            value = 100_000 + i * 1000
            portfolio.equity_curve.append((base_time + timedelta(days=i), value))

        sharpe_no_rf = portfolio.get_sharpe_ratio(risk_free_rate=0.0)
        sharpe_with_rf = portfolio.get_sharpe_ratio(risk_free_rate=0.02)

        # Sharpe should be lower with risk-free rate
        assert sharpe_with_rf < sharpe_no_rf


class TestEquityCurveDataFrame:
    def test_equity_curve_dataframe_empty(self):
        portfolio = TradingPortfolio(100_000)
        df = portfolio.get_equity_curve_dataframe()

        assert len(df) == 0
        assert list(df.columns) == ['timestamp', 'value']

    def test_equity_curve_dataframe_with_data(self):
        portfolio = TradingPortfolio(100_000)

        base_time = datetime.now()
        portfolio.equity_curve.append((base_time, 100_000))
        portfolio.equity_curve.append((base_time + timedelta(days=1), 101_000))

        df = portfolio.get_equity_curve_dataframe()

        assert len(df) == 2
        assert df['value'].iloc[0] == 100_000
        assert df['value'].iloc[1] == 101_000


class TestReset:
    def test_reset_clears_all_state(self):
        portfolio = TradingPortfolio(100_000)

        # Add some trades and positions
        trade = create_trade("AAPL", OrderSide.BUY, 100, 150.0)
        portfolio.process_trade(trade)
        portfolio.record_equity(datetime.now(), {"AAPL": 160.0})

        # Reset
        portfolio.reset()

        assert portfolio.cash == 100_000
        assert len(portfolio.positions) == 0
        assert len(portfolio.trades) == 0
        assert len(portfolio.equity_curve) == 0
        assert portfolio.high_water_mark == 100_000

    def test_reset_preserves_initial_cash(self):
        initial = 75_000
        portfolio = TradingPortfolio(initial)

        trade = create_trade("AAPL", OrderSide.BUY, 100, 150.0)
        portfolio.process_trade(trade)

        portfolio.reset()

        assert portfolio.initial_cash == initial
        assert portfolio.cash == initial


class TestRepr:
    def test_repr_initial_state(self):
        portfolio = TradingPortfolio(100_000)
        repr_str = repr(portfolio)

        assert "cash=$100,000.00" in repr_str
        assert "positions=0" in repr_str
        assert "total_value=$100,000.00" in repr_str
        assert "pnl=$0.00" in repr_str

    def test_repr_with_positions(self):
        portfolio = TradingPortfolio(100_000)

        trade = create_trade("AAPL", OrderSide.BUY, 100, 150.0)
        portfolio.process_trade(trade)
        portfolio.update_prices({"AAPL": 160.0})

        repr_str = repr(portfolio)

        assert "positions=1" in repr_str
        assert "pnl=$1,000.00" in repr_str
