import numpy as np

from models import Strategy, MarketDataPoint, Order


class NaiveMovingAverageStrategy(Strategy):

    def __init__(self):
        self.past_prices = {}

    def update_price(self, data_point: MarketDataPoint):
        if data_point.symbol in self.past_prices:
            self.past_prices[data_point.symbol].append(data_point.price)
        else:
            self.past_prices[data_point.symbol] = [data_point.price]


    def calculateAverage(self, symbol: str):
        return float(np.mean(np.array(self.past_prices[symbol])))


    def generate_signal(self, tick: MarketDataPoint) -> list[Order]:
        mean = self.calculateAverage(tick.symbol)

        current_price = tick.price
        
        if current_price > mean:
            return Order(tick.timestamp, tick.symbol, tick.price, "ask", 1)
        else:
            return Order(tick.timestamp, tick.symbol, tick.price, "bid", 1)






        
