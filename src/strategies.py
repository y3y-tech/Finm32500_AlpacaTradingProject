from typing import override

import numpy as np

from .models import MarketDataPoint, Order, Strategy


class WindowedMovingAverageStrategy(Strategy):
    def __init__(self, window: int):
        self.past_prices: dict[str, list[MarketDataPoint]] = {}
        self.window: int = window

    def update_price(self, tick: MarketDataPoint):
        if tick.symbol not in self.past_prices:
            self.past_prices[tick.symbol] = [tick]
        elif self.past_prices[tick.symbol][-1] != tick:
            self.past_prices[tick.symbol].append(tick)

    def calculate_average(self, symbol: str):
        return float(
            np.mean(
                np.array([p.price for p in self.past_prices[symbol]])[-self.window :]
            )
        )

    @override
    def generate_signal(self, tick: MarketDataPoint) -> Order:
        self.update_price(tick)
        return Order(
            timestamp=tick.timestamp,
            symbol=tick.symbol,
            price=tick.price,
            action="ask" if tick.price > self.calculate_average(tick.symbol) else "bid",
            quantity=1,
        )


class NaiveMovingAverageStrategy(WindowedMovingAverageStrategy):
    def __init__(self):
        super().__init__(window=0)
