from src.data_loader import market_data_loader
from src.strategies import NaiveMovingAverageStrategy, WindowedMovingAverageStrategy
from src.models import Portfolio


"""
Main structure of the main():

- Load the data, create a new portfolio with no positions
- Iterate through the data, create orders based on the strategies
- Fill the orders by updating the positions in the portfolio (and calculate pnL and cash internally)


"""


def main(data_path: str, initial_cash: float, n_ticks: int | None = None):
    # Create a portfolio and market data_points

    simulation_portfolio = Portfolio(initial_cash=initial_cash)

    market_data = market_data_loader(data_file=data_path)[:n_ticks]

    strats = [
        NaiveMovingAverageStrategy(),
        WindowedMovingAverageStrategy(20),
    ]

    for tick in market_data:
        print(f"Running tick {tick}\nCurrent cash is ${simulation_portfolio.cash:,.2f}")
        for strat in strats:
            simulation_portfolio.update_position(strat.generate_signal(tick))

    return simulation_portfolio.cash


if __name__ == "__main__":
    main(data_path="data/assignment3_market_data.csv", initial_cash=1000000, portion_of_data=100000)
