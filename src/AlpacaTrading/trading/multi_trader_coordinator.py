"""Multi-Trader Coordinator for running multiple strategies with shared Alpaca connection."""

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

import pandas as pd
from alpaca.data.live import CryptoDataStream, StockDataStream
from alpaca.data.models import Bar
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

from ..strategies.base import TradingStrategy

logger = logging.getLogger(__name__)


@dataclass
class RiskConfig:
    """Risk management configuration."""

    max_position_size: Optional[float] = None
    max_daily_loss: Optional[float] = None
    max_daily_trades: Optional[int] = None
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None


@dataclass
class StrategyInstance:
    """Tracks state for a single strategy within the coordinator."""

    name: str
    strategy: TradingStrategy
    tickers: List[str]
    initial_cash: float
    min_warmup_bars: int
    risk_config: RiskConfig
    is_crypto: bool = False

    # State tracking
    data_buffers: Dict[str, deque] = field(default_factory=dict)
    bar_counts: Dict[str, int] = field(default_factory=dict)
    is_warmed_up: bool = False
    current_positions: Dict[str, float] = field(default_factory=dict)
    available_cash: float = 0.0
    daily_trades: int = 0
    daily_pnl: float = 0.0
    last_trade_date: Optional[str] = None
    last_warmup_log_time: float = 0.0  # Track when we last logged warmup progress

    def __post_init__(self):
        """Initialize data structures."""
        self.available_cash = self.initial_cash
        for ticker in self.tickers:
            self.data_buffers[ticker] = deque(maxlen=1000)
            self.bar_counts[ticker] = 0


class MultiTraderCoordinator:
    """Coordinates multiple trading strategies sharing a single Alpaca connection."""

    def __init__(
        self,
        strategies: List[Dict[str, Any]],
        api_key: str,
        api_secret: str,
        paper: bool = True,
        save_data: bool = False,
        data_file: Optional[str] = None,
    ):
        """
        Initialize the multi-trader coordinator.

        Args:
            strategies: List of strategy configs, each containing:
                - name: str - Unique strategy identifier
                - strategy: TradingStrategy - Strategy instance
                - tickers: List[str] - Tickers to trade
                - initial_cash: float - Starting capital
                - min_warmup_bars: int - Bars needed before trading
                - risk_config: RiskConfig - Risk management settings
            api_key: Alpaca API key
            api_secret: Alpaca API secret
            paper: Use paper trading (default: True)
            save_data: Save market data to file
            data_file: Path to data file
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.paper = paper
        self.save_data = save_data
        self.data_file = data_file

        # Initialize strategy instances
        self.strategy_instances: Dict[str, StrategyInstance] = {}
        for config in strategies:
            instance = StrategyInstance(
                name=config["name"],
                strategy=config["strategy"],
                tickers=config["tickers"],
                initial_cash=config.get("initial_cash", 50000.0),
                min_warmup_bars=config.get("min_warmup_bars", 50),
                risk_config=config.get("risk_config", RiskConfig()),
                is_crypto=self._detect_crypto_tickers(config["tickers"]),
            )
            self.strategy_instances[config["name"]] = instance

        # Determine which type of data stream to use
        self.has_crypto = any(si.is_crypto for si in self.strategy_instances.values())
        self.has_stocks = any(not si.is_crypto for si in self.strategy_instances.values())

        # Initialize Alpaca clients
        self.trading_client = TradingClient(
            api_key=api_key, secret_key=api_secret, paper=paper
        )

        # Create appropriate data streams
        self.crypto_stream: Optional[CryptoDataStream] = None
        self.stock_stream: Optional[StockDataStream] = None

        if self.has_crypto:
            self.crypto_stream = CryptoDataStream(
                api_key=api_key, secret_key=api_secret
            )
        if self.has_stocks:
            self.stock_stream = StockDataStream(api_key=api_key, secret_key=api_secret)

        # Build ticker -> strategy mapping for efficient routing
        self.ticker_to_strategies: Dict[str, List[str]] = {}
        for name, instance in self.strategy_instances.items():
            for ticker in instance.tickers:
                if ticker not in self.ticker_to_strategies:
                    self.ticker_to_strategies[ticker] = []
                self.ticker_to_strategies[ticker].append(name)

        logger.info(
            f"Initialized MultiTraderCoordinator with {len(self.strategy_instances)} strategies"
        )
        logger.info(f"Total unique tickers: {len(self.ticker_to_strategies)}")
        logger.info(f"Has crypto: {self.has_crypto}, Has stocks: {self.has_stocks}")

    def _detect_crypto_tickers(self, tickers: List[str]) -> bool:
        """Detect if tickers are crypto based on format."""
        return any("/" in ticker for ticker in tickers)

    async def _handle_bar(self, bar: Bar):
        """Handle incoming bar data and route to relevant strategies."""
        ticker = bar.symbol

        # Find all strategies interested in this ticker
        strategy_names = self.ticker_to_strategies.get(ticker, [])
        if not strategy_names:
            return

        # Convert bar to dict for easier handling
        bar_dict = {
            "timestamp": bar.timestamp,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
        }

        # Route bar to each interested strategy
        for strategy_name in strategy_names:
            instance = self.strategy_instances[strategy_name]
            await self._process_bar_for_strategy(instance, ticker, bar_dict)

    async def _process_bar_for_strategy(
        self, instance: StrategyInstance, ticker: str, bar_dict: Dict[str, Any]
    ):
        """Process a bar for a specific strategy instance."""
        # Add bar to buffer
        instance.data_buffers[ticker].append(bar_dict)
        instance.bar_counts[ticker] += 1

        # Check if warmup is complete for this ticker
        if instance.bar_counts[ticker] < instance.min_warmup_bars:
            logger.debug(
                f"[{instance.name}] Warming up {ticker}: "
                f"{instance.bar_counts[ticker]}/{instance.min_warmup_bars}"
            )

            # Log periodic INFO-level warmup progress (every 10 seconds)
            current_time = time.time()
            if current_time - instance.last_warmup_log_time > 10:
                instance.last_warmup_log_time = current_time
                # Calculate overall warmup progress
                total_bars = sum(instance.bar_counts.values())
                total_needed = len(instance.tickers) * instance.min_warmup_bars
                progress_pct = (total_bars / total_needed * 100) if total_needed > 0 else 0

                # Show per-ticker progress
                ticker_progress = ", ".join(
                    f"{t}:{instance.bar_counts.get(t, 0)}/{instance.min_warmup_bars}"
                    for t in sorted(instance.tickers)[:5]  # Show first 5 tickers
                )
                more_tickers = len(instance.tickers) - 5
                if more_tickers > 0:
                    ticker_progress += f" (+{more_tickers} more)"

                logger.info(
                    f"[{instance.name}] Warmup progress: {progress_pct:.1f}% "
                    f"({total_bars}/{total_needed} bars) | {ticker_progress}"
                )
            return

        # Check if all tickers are warmed up
        if not instance.is_warmed_up:
            if all(
                count >= instance.min_warmup_bars
                for count in instance.bar_counts.values()
            ):
                instance.is_warmed_up = True
                logger.info(f"[{instance.name}] ✓ Warmup complete - TRADING ACTIVE")
            else:
                return

        # Generate signals and execute trades
        await self._execute_strategy(instance, ticker, bar_dict)

    async def _execute_strategy(
        self, instance: StrategyInstance, ticker: str, bar_dict: Dict[str, Any]
    ):
        """Execute strategy logic and place orders if needed."""
        # Reset daily counters if new day
        current_date = bar_dict["timestamp"].date().isoformat()
        if instance.last_trade_date != current_date:
            instance.daily_trades = 0
            instance.daily_pnl = 0.0
            instance.last_trade_date = current_date

        # Check risk limits
        if not self._check_risk_limits(instance):
            return

        # Convert buffer to DataFrame for strategy
        df = pd.DataFrame(list(instance.data_buffers[ticker]))
        df.set_index("timestamp", inplace=True)

        # Generate signal
        signal = instance.strategy.generate_signal(df)

        if signal is None or signal == 0:
            return

        # Get current position
        current_position = instance.current_positions.get(ticker, 0.0)

        # Determine action
        if signal > 0 and current_position <= 0:
            await self._execute_buy(instance, ticker, bar_dict["close"])
        elif signal < 0 and current_position >= 0:
            await self._execute_sell(instance, ticker, bar_dict["close"])

    def _check_risk_limits(self, instance: StrategyInstance) -> bool:
        """Check if strategy is within risk limits."""
        risk = instance.risk_config

        # Check max daily trades
        if risk.max_daily_trades and instance.daily_trades >= risk.max_daily_trades:
            logger.warning(
                f"[{instance.name}] Max daily trades reached: {instance.daily_trades}"
            )
            return False

        # Check max daily loss
        if risk.max_daily_loss and instance.daily_pnl <= -risk.max_daily_loss:
            logger.warning(
                f"[{instance.name}] Max daily loss reached: ${instance.daily_pnl:.2f}"
            )
            return False

        return True

    async def _execute_buy(
        self, instance: StrategyInstance, ticker: str, price: float
    ):
        """Execute a buy order for a strategy."""
        # Calculate position size
        position_size = self._calculate_position_size(instance, ticker, price)
        if position_size <= 0:
            return

        try:
            # Determine time_in_force based on asset type
            # Crypto requires GTC or IOC, stocks typically use DAY
            time_in_force = TimeInForce.GTC if instance.is_crypto else TimeInForce.DAY

            # Place market order
            order_request = MarketOrderRequest(
                symbol=ticker,
                qty=position_size,
                side=OrderSide.BUY,
                time_in_force=time_in_force,
            )

            order = self.trading_client.submit_order(order_request)

            # Update instance state
            instance.current_positions[ticker] = position_size
            instance.available_cash -= position_size * price
            instance.daily_trades += 1

            logger.info(
                f"[{instance.name}] 🟢 BUY {position_size:.4f} {ticker} @ ${price:.2f} "
                f"(Order ID: {order.id})"
            )

        except Exception as e:
            logger.error(f"[{instance.name}] Failed to execute BUY: {e}")

    async def _execute_sell(
        self, instance: StrategyInstance, ticker: str, price: float
    ):
        """Execute a sell order for a strategy."""
        # Get current position
        position_size = instance.current_positions.get(ticker, 0.0)
        if position_size <= 0:
            return

        try:
            # Determine time_in_force based on asset type
            # Crypto requires GTC or IOC, stocks typically use DAY
            time_in_force = TimeInForce.GTC if instance.is_crypto else TimeInForce.DAY

            # Place market order
            order_request = MarketOrderRequest(
                symbol=ticker,
                qty=position_size,
                side=OrderSide.SELL,
                time_in_force=time_in_force,
            )

            order = self.trading_client.submit_order(order_request)

            # Update instance state
            instance.available_cash += position_size * price
            instance.current_positions[ticker] = 0.0
            instance.daily_trades += 1

            logger.info(
                f"[{instance.name}] 🔴 SELL {position_size:.4f} {ticker} @ ${price:.2f} "
                f"(Order ID: {order.id})"
            )

        except Exception as e:
            logger.error(f"[{instance.name}] Failed to execute SELL: {e}")

    def _calculate_position_size(
        self, instance: StrategyInstance, ticker: str, price: float
    ) -> float:
        """Calculate position size based on available capital and risk limits."""
        if price <= 0:
            return 0.0

        # Calculate max position based on available cash
        max_shares = instance.available_cash / price

        # Apply max position size limit if configured
        if instance.risk_config.max_position_size:
            max_value = instance.initial_cash * instance.risk_config.max_position_size
            max_shares = min(max_shares, max_value / price)

        # For crypto, round to 4 decimals; for stocks, use integers
        if instance.is_crypto:
            return round(max_shares, 4)
        else:
            return int(max_shares)

    async def run(self):
        """Run the multi-trader coordinator."""
        logger.info("=" * 80)
        logger.info("Starting MultiTraderCoordinator")
        logger.info(f"Paper Trading: {self.paper}")
        logger.info(f"Strategies: {len(self.strategy_instances)}")
        logger.info("=" * 80)

        for name, instance in self.strategy_instances.items():
            logger.info(f"  [{name}]")
            logger.info(f"    Tickers: {', '.join(instance.tickers)}")
            logger.info(f"    Initial Cash: ${instance.initial_cash:,.2f}")
            logger.info(f"    Warmup Bars: {instance.min_warmup_bars}")
            logger.info(f"    Asset Type: {'Crypto' if instance.is_crypto else 'Stock'}")

        logger.info("=" * 80)

        try:
            # Subscribe to tickers and run streams
            tasks = []

            if self.crypto_stream:
                crypto_tickers = [
                    ticker
                    for ticker, strategies in self.ticker_to_strategies.items()
                    if any(
                        self.strategy_instances[s].is_crypto for s in strategies
                    )
                ]
                self.crypto_stream.subscribe_bars(self._handle_bar, *crypto_tickers)
                tasks.append(asyncio.create_task(self.crypto_stream._run_forever()))
                logger.info(f"Subscribed to {len(crypto_tickers)} crypto tickers")

            if self.stock_stream:
                stock_tickers = [
                    ticker
                    for ticker, strategies in self.ticker_to_strategies.items()
                    if any(
                        not self.strategy_instances[s].is_crypto for s in strategies
                    )
                ]
                self.stock_stream.subscribe_bars(self._handle_bar, *stock_tickers)
                tasks.append(asyncio.create_task(self.stock_stream._run_forever()))
                logger.info(f"Subscribed to {len(stock_tickers)} stock tickers")

            # Run all streams concurrently
            await asyncio.gather(*tasks)

        except KeyboardInterrupt:
            logger.info("\n\nShutting down gracefully...")
            self._print_summary()
        except Exception as e:
            logger.error(f"Error in coordinator: {e}", exc_info=True)
            raise

    def _print_summary(self):
        """Print summary of all strategy performances."""
        logger.info("\n" + "=" * 80)
        logger.info("MULTI-TRADER COORDINATOR SUMMARY")
        logger.info("=" * 80)

        total_pnl = 0.0
        for name, instance in self.strategy_instances.items():
            # Calculate unrealized PnL
            position_value = sum(instance.current_positions.values())
            total_value = instance.available_cash + position_value
            pnl = total_value - instance.initial_cash
            total_pnl += pnl

            logger.info(f"\n[{name}]")
            logger.info(f"  Initial Cash: ${instance.initial_cash:,.2f}")
            logger.info(f"  Available Cash: ${instance.available_cash:,.2f}")
            logger.info(f"  Total Value: ${total_value:,.2f}")
            logger.info(f"  PnL: ${pnl:,.2f} ({pnl/instance.initial_cash*100:+.2f}%)")
            logger.info(f"  Daily Trades: {instance.daily_trades}")
            logger.info(f"  Active Positions: {len([p for p in instance.current_positions.values() if p > 0])}")

        logger.info("\n" + "=" * 80)
        logger.info(f"TOTAL PnL ACROSS ALL STRATEGIES: ${total_pnl:,.2f}")
        logger.info("=" * 80)
