"""
Base class for trading strategies.

All trading strategies must inherit from TradingStrategy and implement on_market_data().
"""

from abc import ABC, abstractmethod
import logging

from AlpacaTrading.models import MarketDataPoint, Order
from AlpacaTrading.trading.portfolio import TradingPortfolio

logger = logging.getLogger(__name__)


class TradingStrategy(ABC):
    """
    Abstract base class for all trading strategies.

    Strategies receive market data ticks and portfolio state,
    then generate orders based on their logic.

    The base class provides error handling to ensure strategies
    never crash the trading system due to unexpected exceptions.

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
        self._error_count = 0
        self._max_consecutive_errors = 10

    @abstractmethod
    def on_market_data(
        self, tick: MarketDataPoint, portfolio: TradingPortfolio
    ) -> list[Order]:
        """
        Process new market data and generate trading signals.

        This method is called for each market tick during backtesting or live trading.

        IMPORTANT: This method should never raise exceptions. The base class will
        catch and log any exceptions, returning an empty order list.

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

    def process_market_data(
        self, tick: MarketDataPoint, portfolio: TradingPortfolio
    ) -> list[Order]:
        """
        Wrapper for on_market_data with error handling.

        This method is called by the backtesting/live trading engine.
        It wraps on_market_data() with try/except to prevent strategy
        errors from crashing the system.

        Args:
            tick: New market data point
            portfolio: Current portfolio state

        Returns:
            List of orders (empty if error occurred)
        """
        try:
            orders = self.on_market_data(tick, portfolio)

            # Validate return type
            if not isinstance(orders, list):
                logger.error(
                    f"{self.name}: on_market_data must return list, got {type(orders).__name__}"
                )
                return []

            # Reset error count on success
            self._error_count = 0

            return orders

        except Exception as e:
            self._error_count += 1
            logger.error(
                f"{self.name} error processing {tick.symbol} at {tick.timestamp}: {e}",
                exc_info=True,
            )

            # Warn if too many consecutive errors
            if self._error_count >= self._max_consecutive_errors:
                logger.critical(
                    f"{self.name} has {self._error_count} consecutive errors. "
                    f"Strategy may be broken!"
                )

            return []

    def on_start(self, portfolio: TradingPortfolio) -> None:
        """
        Called once at the start of backtest/live trading.

        Override to initialize strategy state, load models, etc.

        Args:
            portfolio: Initial portfolio state
        """
        logger.info(f"{self.name} started with initial cash: ${portfolio.cash:,.2f}")

    def on_end(self, portfolio: TradingPortfolio) -> None:
        """
        Called once at the end of backtest/live trading.

        Override to cleanup resources, save state, etc.

        Args:
            portfolio: Final portfolio state
        """
        logger.info(
            f"{self.name} ended with final equity: ${portfolio.get_total_equity():,.2f}, "
            f"total P&L: ${portfolio.get_total_pnl():,.2f}"
        )

    def __repr__(self) -> str:
        return f"{self.name}()"
