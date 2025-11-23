import csv
from datetime import datetime
from pathlib import Path

from .models import MarketDataPoint


def market_data_loader(data_file: str) -> list[MarketDataPoint]:
    """
    Parses market_data.csv into a list of MarketDataPoints
    """
    res = []

    data_filepath = Path(data_file)

    if data_filepath.exists():
        with data_filepath.open(mode="r", newline="") as f:
            reader = csv.DictReader(f)

            for row in reader:
                timestamp = row["timestamp"]
                symbol = row["symbol"]
                price = float(row["price"])
                data_point = MarketDataPoint(
                    timestamp=datetime.fromisoformat(timestamp),
                    symbol=symbol,
                    price=price,
                )
                res.append(data_point)

        res.sort(key=lambda x: x.timestamp)

    return res
