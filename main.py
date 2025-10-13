from data_loader import market_data_loader
from strategies import NaiveMovingAverageStrategy
from models import Order, Portfolio, MarketDataPoint


'''
Main structure of the main():

- Load the data, create a new portfolio with no positions
- Iterate through the data, create orders based on the strategies
- Fill the orders by updating the positions in the portfolio (and calculate pnL and cash internally)


'''


def main(data_path: str, initial_cash: float, portion_of_data: float):

    # Create a portfolio and market data_points

    simulation_portfolio = Portfolio(initial_cash=initial_cash)

    market_data = market_data_loader(data_filepath=data_path)[:portion_of_data]


    # Add more strategies below:

    Naive_Strat = NaiveMovingAverageStrategy()

    for tick in market_data:
        # For Naive Strategy: - first update the averages and then generate an order
        
        Naive_Strat.update_price(tick)
        Naive_Order = Naive_Strat.generate_signal(tick)
        simulation_portfolio.update_position(Naive_Order)


        # For other strategies, enter below:




    return simulation_portfolio.cash



if __name__ == "__main__":
    main(data_path="data/assignment3_market_data.csv", initial_cash=1000000, portion_of_data=100000)
