import yfinance as yf
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Union


def load_equities(ticker: str, period: str = "7d", interval: str = "1m") -> tuple[str, Path]:
    """Download equity data and write a CSV into the repository's raw_data folder.

    Returns (ticker, output_path).
    """

    data = yf.download(tickers=ticker, period=period, interval=interval)
    data = data.stack(level=1).reset_index()

    data_name = f"tickers_raw.csv"

    # Build a path relative to this script (equities_data/)
    base_dir = Path(__file__).resolve().parent
    raw_dir = base_dir / "raw_data"
    raw_dir.mkdir(parents=True, exist_ok=True)

    output_path = raw_dir / data_name

    # pandas accepts path-like objects
    data.to_csv(output_path)

    return ticker, output_path


def clean_equities(ticker: str, raw_data_file_path: Union[str, Path]):

    raw_path = Path(raw_data_file_path)
    equities_df = pd.read_csv(raw_path, index_col=0)

    equities_df.ffill(inplace=True)

    equities_df["Return"] = equities_df["Close"].astype("float").pct_change()

    equities_df["Weekly Moving Average"] = equities_df["Close"].rolling(window=7).mean()

    equities_df.rename(columns={'Ticker': 'symbol'}, inplace=True)

    data_name = f"tickers_cleaned.csv"

    # Clean out starting rows that are NaN from rolling average and return calculations
    equities_df.dropna(inplace=True)

    base_dir = Path(__file__).resolve().parent
    cleaned_dir = base_dir / "cleaned_data"
    cleaned_dir.mkdir(parents=True, exist_ok=True)

    equities_df.to_csv(cleaned_dir / data_name)

if __name__ == "__main__":
    apple, path = load_equities(ticker=["AAPL", "MSFT"])
    clean_equities(apple, path)

    