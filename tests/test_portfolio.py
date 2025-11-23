import numpy as np
import pytest

from AlpacaTrading.trading.portfolio import TradingPortfolio


class TestErrorHandling:
    def test_initial_cash_positive(self):
        with pytest.raises(ValueError, match="Initial cash must be positive"):
            tp = TradingPortfolio(-10)
            


class TestProcessTrade:
    pass