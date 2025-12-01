"""
Strategy Configuration Templates

Defines different strategy configurations for backtesting and live trading.
Each config specifies strategy parameters, risk settings, and symbols to trade.
"""

from AlpacaTrading.strategies.momentum import MomentumStrategy
from AlpacaTrading.strategies.mean_reversion import MovingAverageCrossoverStrategy
from AlpacaTrading.strategies.rsi_strategy import RSIStrategy
from AlpacaTrading.strategies.bollinger_bands import BollingerBandsStrategy
from AlpacaTrading.strategies.volume_breakout import VolumeBreakoutStrategy
from AlpacaTrading.strategies.vwap_strategy import VWAPStrategy
from AlpacaTrading.trading.order_manager import RiskConfig


# ============================================================================
# STRATEGY CONFIGURATIONS
# ============================================================================

STRATEGY_CONFIGS = {
    # Aggressive momentum for trending markets
    "momentum_aggressive": {
        "strategy": MomentumStrategy(
            lookback_period=10,
            momentum_threshold=0.015,  # 1.5% momentum required
            position_size=15000,
            max_position=150
        ),
        "risk_config": RiskConfig(
            max_position_size=150,
            max_position_value=150_000,
            max_total_exposure=300_000,
            max_orders_per_minute=50,
            max_orders_per_symbol_per_minute=10,
            min_cash_buffer=10000
        ),
        "symbols": ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA"],
        "description": "Aggressive momentum trader for strong trends"
    },

    # Conservative momentum for stable markets
    "momentum_conservative": {
        "strategy": MomentumStrategy(
            lookback_period=20,
            momentum_threshold=0.01,  # 1% momentum
            position_size=8000,
            max_position=80
        ),
        "risk_config": RiskConfig(
            max_position_size=80,
            max_position_value=80_000,
            max_total_exposure=150_000,
            max_orders_per_minute=30,
            max_orders_per_symbol_per_minute=5,
            min_cash_buffer=20000
        ),
        "symbols": ["SPY", "QQQ", "DIA", "IWM"],
        "description": "Conservative momentum with tight risk controls"
    },

    # RSI mean reversion with profit targets
    "rsi_scalper": {
        "strategy": RSIStrategy(
            rsi_period=14,
            oversold_threshold=25,  # Very oversold
            overbought_threshold=75,  # Very overbought
            position_size=10000,
            max_position=100,
            profit_target=2.0,  # 2% profit target
            stop_loss=1.0  # 1% stop loss
        ),
        "risk_config": RiskConfig(
            max_position_size=100,
            max_position_value=100_000,
            max_total_exposure=200_000,
            max_orders_per_minute=40,
            max_orders_per_symbol_per_minute=8,
            min_cash_buffer=15000
        ),
        "symbols": ["AAPL", "MSFT", "AMZN", "META", "NFLX"],
        "description": "RSI scalper with tight profit/loss targets"
    },

    # RSI swing trader
    "rsi_swing": {
        "strategy": RSIStrategy(
            rsi_period=14,
            oversold_threshold=30,
            overbought_threshold=70,
            position_size=12000,
            max_position=120,
            profit_target=5.0,  # 5% profit target
            stop_loss=2.5  # 2.5% stop loss
        ),
        "risk_config": RiskConfig(
            max_position_size=120,
            max_position_value=120_000,
            max_total_exposure=250_000,
            max_orders_per_minute=30,
            max_orders_per_symbol_per_minute=6,
            min_cash_buffer=10000
        ),
        "symbols": ["AAPL", "TSLA", "AMD", "COIN", "SQ"],
        "description": "RSI swing trader for multi-day holds"
    },

    # Bollinger Bands breakout
    "bb_breakout": {
        "strategy": BollingerBandsStrategy(
            period=20,
            num_std_dev=2.0,
            mode='breakout',
            position_size=12000,
            max_position=120,
            band_threshold=0.002  # 0.2% beyond band
        ),
        "risk_config": RiskConfig(
            max_position_size=120,
            max_position_value=120_000,
            max_total_exposure=240_000,
            max_orders_per_minute=40,
            max_orders_per_symbol_per_minute=8,
            min_cash_buffer=12000
        ),
        "symbols": ["NVDA", "TSLA", "AMD", "SMCI", "MSTR"],
        "description": "Bollinger Bands breakout for volatile stocks"
    },

    # Bollinger Bands mean reversion
    "bb_reversion": {
        "strategy": BollingerBandsStrategy(
            period=20,
            num_std_dev=2.5,  # Wider bands
            mode='reversion',
            position_size=10000,
            max_position=100,
            band_threshold=0.001
        ),
        "risk_config": RiskConfig(
            max_position_size=100,
            max_position_value=100_000,
            max_total_exposure=200_000,
            max_orders_per_minute=35,
            max_orders_per_symbol_per_minute=7,
            min_cash_buffer=15000
        ),
        "symbols": ["SPY", "QQQ", "AAPL", "MSFT", "GOOGL"],
        "description": "Bollinger mean reversion for range-bound markets"
    },

    # Volume breakout trader
    "volume_breakout": {
        "strategy": VolumeBreakoutStrategy(
            volume_period=20,
            volume_multiplier=2.5,  # 2.5x normal volume
            price_momentum_period=5,
            min_price_change=0.012,  # 1.2% price move
            position_size=15000,
            max_position=150,
            hold_periods=30  # Hold for max 30 ticks
        ),
        "risk_config": RiskConfig(
            max_position_size=150,
            max_position_value=150_000,
            max_total_exposure=300_000,
            max_orders_per_minute=50,
            max_orders_per_symbol_per_minute=10,
            min_cash_buffer=10000
        ),
        "symbols": ["TSLA", "NVDA", "AMD", "COIN", "MSTR", "SMCI"],
        "description": "Volume breakout for news-driven moves"
    },

    # VWAP mean reversion
    "vwap_intraday": {
        "strategy": VWAPStrategy(
            deviation_threshold=0.008,  # 0.8% from VWAP
            position_size=10000,
            max_position=100,
            reset_period=390,  # Reset daily (390 minutes in trading day)
            min_samples=20
        ),
        "risk_config": RiskConfig(
            max_position_size=100,
            max_position_value=100_000,
            max_total_exposure=200_000,
            max_orders_per_minute=40,
            max_orders_per_symbol_per_minute=8,
            min_cash_buffer=15000
        ),
        "symbols": ["SPY", "QQQ", "AAPL", "MSFT", "GOOGL"],
        "description": "VWAP mean reversion for liquid stocks"
    },

    # MA Crossover trend follower
    "ma_crossover": {
        "strategy": MovingAverageCrossoverStrategy(
            short_window=10,
            long_window=30,
            position_size=12000,
            max_position=120
        ),
        "risk_config": RiskConfig(
            max_position_size=120,
            max_position_value=120_000,
            max_total_exposure=250_000,
            max_orders_per_minute=30,
            max_orders_per_symbol_per_minute=6,
            min_cash_buffer=15000
        ),
        "symbols": ["SPY", "QQQ", "AAPL", "MSFT", "AMZN"],
        "description": "Classic MA crossover trend follower"
    },

    # Multi-strategy portfolio (for comparison)
    "balanced_portfolio": {
        # This would use a portfolio of strategies (future enhancement)
        "strategy": RSIStrategy(
            rsi_period=14,
            oversold_threshold=30,
            overbought_threshold=70,
            position_size=10000,
            max_position=100
        ),
        "risk_config": RiskConfig(
            max_position_size=100,
            max_position_value=100_000,
            max_total_exposure=200_000,
            max_orders_per_minute=40,
            max_orders_per_symbol_per_minute=8,
            min_cash_buffer=15000
        ),
        "symbols": ["SPY", "QQQ", "AAPL", "MSFT", "GOOGL", "TSLA", "NVDA"],
        "description": "Balanced multi-asset portfolio"
    }
}


# ============================================================================
# CRYPTO-SPECIFIC CONFIGURATIONS (for crypto competition)
# ============================================================================

CRYPTO_CONFIGS = {
    "btc_momentum": {
        "strategy": MomentumStrategy(
            lookback_period=15,
            momentum_threshold=0.02,  # 2% for crypto volatility
            position_size=5000,
            max_position=0.5  # BTC fractions
        ),
        "risk_config": RiskConfig(
            max_position_size=1.0,
            max_position_value=50_000,
            max_total_exposure=100_000,
            max_orders_per_minute=30,
            max_orders_per_symbol_per_minute=5,
            min_cash_buffer=5000
        ),
        "symbols": ["BTC/USD", "ETH/USD"],
        "description": "Bitcoin momentum trader"
    },

    "crypto_rsi": {
        "strategy": RSIStrategy(
            rsi_period=14,
            oversold_threshold=20,  # More extreme for crypto
            overbought_threshold=80,
            position_size=3000,
            max_position=0.3,
            profit_target=3.0,
            stop_loss=2.0
        ),
        "risk_config": RiskConfig(
            max_position_size=1.0,
            max_position_value=40_000,
            max_total_exposure=80_000,
            max_orders_per_minute=40,
            max_orders_per_symbol_per_minute=8,
            min_cash_buffer=10000
        ),
        "symbols": ["BTC/USD", "ETH/USD", "SOL/USD"],
        "description": "Crypto RSI with wide thresholds for volatility"
    },

    "crypto_vwap": {
        "strategy": VWAPStrategy(
            deviation_threshold=0.015,  # 1.5% for crypto
            position_size=4000,
            max_position=0.4,
            reset_period=0,  # Never reset (24/7 trading)
            min_samples=30
        ),
        "risk_config": RiskConfig(
            max_position_size=1.0,
            max_position_value=45_000,
            max_total_exposure=90_000,
            max_orders_per_minute=35,
            max_orders_per_symbol_per_minute=7,
            min_cash_buffer=8000
        ),
        "symbols": ["BTC/USD", "ETH/USD"],
        "description": "VWAP mean reversion for crypto 24/7"
    }
}


# ============================================================================
# DATA FILE PATHS (customize for your setup)
# ============================================================================

DATA_FILES = {
    "equities_1min": "data/equities/1min_bars.csv",
    "equities_5min": "data/equities/5min_bars.csv",
    "equities_daily": "data/equities/daily_bars.csv",
    "crypto_1min": "data/crypto/1min_bars.csv",
    "crypto_5min": "data/crypto/5min_bars.csv",
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_config(config_name: str, asset_class: str = 'equities'):
    """
    Get a strategy configuration by name.

    Args:
        config_name: Name of the configuration (e.g., 'momentum_aggressive')
        asset_class: 'equities' or 'crypto'

    Returns:
        Configuration dictionary

    Example:
        config = get_config('momentum_aggressive')
        strategy = config['strategy']
        risk_config = config['risk_config']
    """
    configs = CRYPTO_CONFIGS if asset_class == 'crypto' else STRATEGY_CONFIGS

    if config_name not in configs:
        available = ', '.join(configs.keys())
        raise ValueError(f"Unknown config '{config_name}'. Available: {available}")

    return configs[config_name]


def list_configs(asset_class: str = 'equities'):
    """
    List all available configurations with descriptions.

    Args:
        asset_class: 'equities' or 'crypto'
    """
    configs = CRYPTO_CONFIGS if asset_class == 'crypto' else STRATEGY_CONFIGS

    print(f"\nAvailable {asset_class.upper()} Configurations:")
    print("=" * 80)

    for name, config in configs.items():
        print(f"\n{name}:")
        print(f"  Strategy: {config['strategy']}")
        print(f"  Symbols: {', '.join(config['symbols'])}")
        print(f"  Description: {config['description']}")

    print("\n" + "=" * 80)
