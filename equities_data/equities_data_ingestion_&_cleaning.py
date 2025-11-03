import yfinance as yf
import pandas as pd
import numpy as np


def load_equities(ticker: str, period = "7d", interval = "1m"):

    data = yf.download(tickers = ticker, period = period, interval = interval)

    data_name = f"{ticker}_raw.csv"

    output_path = "./data/raw_data/" + data_name

    data.to_csv(output_path)

    return ticker, output_path


def clean_equities(ticker: str, raw_data_file_path: str):

    equities_df = pd.read_csv(raw_data_file_path)


    #Drop the first two rows since the first two rows contain unnecesssary information
    equities_df = equities_df.iloc[2:]

    equities_df.dropna(inplace=True)

    equities_df.set_index("Price", inplace=True)

    equities_df["Return"] = equities_df["Close"].astype("float").pct_change()

    equities_df["Weekly Moving Average"] = equities_df["Close"].rolling(window=7).mean()

    data_name = f"{ticker}_cleaned.csv"

    # Clean out starting rows that are NaN from rolling average and return calculations

    equities_df.dropna(inplace=True)

    equities_df.to_csv("./data/cleaned_data/" + data_name)

if __name__ == "__main__":
    
    apple, path = load_equities(ticker = "AAPL")
    clean_equities(apple, path)

    