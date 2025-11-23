"""
Base class for trading strategies.

All trading strategies must inherit from TradingStrategy and implement on_market_data().
"""

from abc import ABC, abstractmethod

from AlpacaTrading.models import MarketDataPoint, Order
from AlpacaTrading.trading.portfolio import TradingPortfolio


class TradingStrategy(ABC):
    """
    Abstract base class for all trading strategies.

    Strategies receive market data ticks and portfolio state,
    then generate orders based on their logic.

    Example:
        class MyStrategy(TradingStrategy):
            def on_market_data(self, tick, portfolio):
                # Your logic here
                if should_buy:
                    return [create_buy_order(tick)]
                return []
    """

    def __init__(self, name: str | None = None):
        """
        Initialize strategy.

        Args:
            name: Strategy name (defaults to class name)
        """
        self.name = name or self.__class__.__name__

    @abstractmethod
    def on_market_data(
        self,
        tick: MarketDataPoint,
        portfolio: TradingPortfolio
    ) -> list[Order]:
        """
        Process new market data and generate trading signals.

        This method is called for each market tick during backtesting or live trading.

        Args:
            tick: New market data point (timestamp, symbol, price, volume)
            portfolio: Current portfolio state (positions, cash, P&L)

        Returns:
            List of Order objects to submit. Return empty list if no trades.

        Example:
            def on_market_data(self, tick, portfolio):
                if tick.price > self.threshold:
                    return [Order(
                        symbol=tick.symbol,
                        side=OrderSide.BUY,
                        order_type=OrderType.MARKET,
                        quantity=100
                    )]
                return []
        """
        pass

    def on_start(self, portfolio: TradingPortfolio) -> None:
        """
        Called once at the start of backtest/live trading.

        Override to initialize strategy state, load models, etc.

        Args:
            portfolio: Initial portfolio state
        """
        pass

    def on_end(self, portfolio: TradingPortfolio) -> None:
        """
        Called once at the end of backtest/live trading.

        Override to cleanup resources, save state, etc.

        Args:
            portfolio: Final portfolio state
        """
        pass

    def __repr__(self) -> str:
        return f"{self.name}()"
