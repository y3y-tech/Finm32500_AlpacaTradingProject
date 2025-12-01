import timeit
from strategies import NaiveMovingAverageStrategy
from models import MarketDataPoint
import datetime

def run_strategy_with_mock():
    # Create mock market data
    mock_data = [
        MarketDataPoint(datetime.datetime.now(), "AAPL", 150.0)]* 1000
    
    strategy = NaiveMovingAverageStrategy()
    
    for tick in mock_data:
        strategy.update_price(tick)
        strategy.generate_signal(tick)

execution_time = timeit.timeit(run_strategy_with_mock, number=10) / 10
print(f"Average execution time: {execution_time:.4f} seconds")