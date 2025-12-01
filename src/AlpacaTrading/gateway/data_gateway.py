"""
Data Gateway - Streams historical market data to simulate live feed.

Supports CSV files with configurable replay speed and multi-symbol streaming.
"""

import csv
from datetime import datetime
import logging
from pathlib import Path
from typing import Iterator
import pandas as pd

from AlpacaTrading.models import MarketDataPoint

logger = logging.getLogger(__name__)


class DataGateway:
    """
    Streams market data from CSV files row-by-row to simulate live feed.

    CSV Format Expected:
    - Must have columns: timestamp (or Datetime), symbol, price
    - Optional: volume, open, high, low, close
    - Timestamps should be ISO format or parseable by pandas

    Usage:
        gateway = DataGateway("data/market_data.csv")
        for tick in gateway.stream():
            # Process tick
            pass
    """

    def __init__(self, data_source: str, timestamp_column: str = "timestamp"):
        """
        Initialize data gateway.

        Args:
            data_source: Path to CSV file with market data
            timestamp_column: Name of timestamp column (default: 'timestamp')
        """
        self.data_source = Path(data_source)
        self.timestamp_column = timestamp_column
        self.current_prices: dict[str, float] = {}
        self._validate_file()

    def _validate_file(self) -> None:
        """Validate that data file exists and has required columns."""
        if not self.data_source.exists():
            raise FileNotFoundError(f"Data file not found: {self.data_source}")

        # Read first row to check columns
        with self.data_source.open('r') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            if headers is None:
                raise ValueError(f"CSV file {self.data_source} has no headers")

            # Check for required columns (case-insensitive)
            headers_lower = [h.lower() for h in headers]

            # Timestamp column (accept various names)
            timestamp_names = ['timestamp', 'datetime', 'date', 'time']
            if not any(ts in headers_lower for ts in timestamp_names):
                raise ValueError(
                    f"CSV must have a timestamp column. Found: {headers}. "
                    f"Expected one of: {timestamp_names}"
                )

            # Symbol column
            if 'symbol' not in headers_lower:
                raise ValueError(f"CSV must have 'symbol' column. Found: {headers}")

            # Price column (or Close)
            if 'price' not in headers_lower and 'close' not in headers_lower:
                raise ValueError(
                    f"CSV must have 'price' or 'close' column. Found: {headers}"
                )

    def stream(self) -> Iterator[MarketDataPoint]:
        """
        Stream market data points one at a time.

        Yields:
            MarketDataPoint: Next market tick

        Example:
            for tick in gateway.stream():
                print(f"{tick.timestamp}: {tick.symbol} @ {tick.price}")
        """
        with self.data_source.open('r') as f:
            reader = csv.DictReader(f)

            for row in reader:
                # Handle various timestamp column names
                timestamp_str = None
                for ts_name in ['timestamp', 'Datetime', 'datetime', 'Date', 'Time']:
                    if ts_name in row:
                        timestamp_str = row[ts_name]
                        break

                if timestamp_str is None:
                    raise ValueError(f"Could not find timestamp in row: {row}")

                # Parse timestamp
                try:
                    timestamp = datetime.fromisoformat(timestamp_str)
                except ValueError:
                    # Try pandas parser as fallback
                    timestamp = pd.to_datetime(timestamp_str).to_pydatetime()

                # Get symbol
                symbol = row.get('symbol') or row.get('Symbol')
                if symbol is None:
                    raise ValueError(f"Could not find symbol in row: {row}")

                # Get price (try 'price' first, then 'Close', then 'close')
                price_str = row.get('price') or row.get('Close') or row.get('close')
                if price_str is None:
                    raise ValueError(f"Could not find price in row: {row}")
                price = float(price_str)

                # Get volume if available
                volume_str = row.get('volume') or row.get('Volume') or '0'
                volume = float(volume_str)

                # Create and yield market data point
                tick = MarketDataPoint(
                    timestamp=timestamp,
                    symbol=symbol,
                    price=price,
                    volume=volume
                )

                # Update current price cache
                self.current_prices[symbol] = price

                yield tick

    def get_current_price(self, symbol: str) -> float | None:
        """
        Get the most recent price for a symbol.

        Args:
            symbol: Asset symbol

        Returns:
            Latest price or None if symbol not seen yet
        """
        return self.current_prices.get(symbol)

    def load_all(self) -> list[MarketDataPoint]:
        """
        Load all data into memory at once.

        Returns:
            List of all market data points

        Note:
            Use stream() for memory efficiency with large files.
        """
        return list(self.stream())

    def get_symbols(self) -> set[str]:
        """
        Get all unique symbols in the data file.

        Returns:
            Set of symbol strings
        """
        symbols = set()
        with self.data_source.open('r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                symbol = row.get('symbol') or row.get('Symbol')
                if symbol:
                    symbols.add(symbol)
        return symbols

    def get_date_range(self) -> tuple[datetime, datetime]:
        """
        Get the date range covered by the data file.

        Returns:
            Tuple of (start_date, end_date)
        """
        timestamps = []
        with self.data_source.open('r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                timestamp_str = None
                for ts_name in ['timestamp', 'Datetime', 'datetime', 'Date']:
                    if ts_name in row:
                        timestamp_str = row[ts_name]
                        break
                if timestamp_str:
                    try:
                        timestamps.append(datetime.fromisoformat(timestamp_str))
                    except ValueError:
                        timestamps.append(pd.to_datetime(timestamp_str).to_pydatetime())

        if not timestamps:
            raise ValueError("No valid timestamps found in data file")

        return min(timestamps), max(timestamps)

    def __repr__(self) -> str:
        return f"DataGateway(source={self.data_source}, symbols={len(self.get_symbols())})"
