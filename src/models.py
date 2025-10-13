from dataclasses import dataclass
import datetime
from abc import ABC, abstractmethod


@dataclass(frozen=True)
class MarketDataPoint:
    timestamp: datetime.datetime
    symbol: str
    price: float


@dataclass
class Order:
    timestamp: datetime.datetime
    symbol: str
    price: float
    action: str
    quantity: float


class Position:
    def __init__(self, symbol: str, quantity: float, pnl: float):
        self.symbol: str = symbol
        self.quantity: float = quantity
        self.pnl: float = pnl


class Portfolio:
    def __init__(self, initial_cash: float):
        self.cash: float = initial_cash
        self.positions: dict[str, Position] = {}
        self.order_history: list[Order] = []

    def calculate_pnl(self, order: Order) -> float:
        if order.action == "bid":
            return -order.price * order.quantity
        else:
            return order.price * order.quantity

    def update_position(self, order: Order):
        if order.symbol not in self.positions:
            self.positions[order.symbol] = Position(
                symbol=order.symbol,
                quantity=order.quantity,
                pnl=self.calculate_pnl(order),
            )

        else:
            if order.action == "bid":
                self.positions[order.symbol].quantity += order.quantity
            else:
                self.positions[order.symbol].quantity -= order.quantity

            self.positions[order.symbol].pnl += self.calculate_pnl(order)

        self.cash += self.calculate_pnl(order)
        self.order_history.append(order)


class Strategy(ABC):
    @abstractmethod
    def generate_signal(self, tick: MarketDataPoint) -> Order:
        pass
