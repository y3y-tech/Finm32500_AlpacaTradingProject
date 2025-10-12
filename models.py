from dataclasses import dataclass
import datetime
from abc import ABC, abstractmethod


@dataclass(frozen=True)
class MarketDataPoint:

    timestamp: datetime

    symbol: str

    price: float



class Strategy(ABC):

    @abstractmethod

    def generate_signal(self, tick: MarketDataPoint) -> list:

        pass





