import requests
import pandas as pd

def get_crypto_data(symbol: str, interval='1d', limit=200):
    """
    Fetch historical Ethereum price data from Binance
    """
    print(f"Fetching {symbol}  data...")

    url = "https://data-api.binance.vision/api/v3/klines"
    
    params = {
        'symbol': symbol,      # Ethereum/USDT
        'interval': interval,      # 1d = daily, 1h = hourly, etc.
        'limit': limit            # Number of data points
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        # Create DataFrame
        df = pd.DataFrame(data, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])

        
        # Process data
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index("timestamp", inplace=True)

        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        df['returns'] = df['close'].pct_change()
        df['volume'] = df['volume'].astype(float)
        df['MA_7'] = df['close'].rolling(window=7).mean()
        df['MA_10'] = df['close'].rolling(window=10).mean()
        
        # Keep only relevant columns
        df = df[['open','high', 'low', 'close', 'volume', 'returns', 'MA_7', 'MA_10']]

        

        df.dropna(inplace=True)

        file_name = f"{symbol}.csv"
        
        df.to_csv("./crypto_data/" + file_name)
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return None



if __name__ == "__main__":

    df = get_crypto_data(symbol ="ETHUSDT", interval='1d')
