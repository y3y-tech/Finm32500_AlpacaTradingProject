from dataclasses import dataclass
import datetime
from abc import ABC, abstractmethod


@dataclass(frozen=True)
class MarketDataPoint:
    timestamp: datetime
    symbol: str
    price: float

@dataclass
class Order:
    timestamp: datetime
    symbol: str
    price: float
    action: str
    quantity: float


class Position:

    def __init__(self, symbol: str, quantity: float, average_price:float, realized_pnl:float):
        self.symbol = symbol
        self.quantity = quantity
        self.average_price = average_price
        self.realized_pnl = realized_pnl


class Portfolio:

    def __init__(self, initial_cash: float):
        self.cash = initial_cash
        self.positions: dict[str, Position] = {}
        self.order_history: list[Order] = []


class Strategy(ABC):

    @abstractmethod

    def generate_signal(self, tick: MarketDataPoint) -> list:

        pass







