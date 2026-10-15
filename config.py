"""Configuration parameters for the 5-Tranche Weekly Breakout Swing Strategy."""

from dataclasses import dataclass, field
from typing import List

@dataclass
class BacktestConfig:
    # Portfolio Capital parameters (plain numbers, no currency symbol)
    total_capital: float = 100000.0
    num_parts: int = 4
    tranche_capital: float = 25000.0
    
    # Strategy triggers
    target_pct: float = 0.05           # 5% profit target per tranche
    entry_buffer_pct: float = 0.005     # 0.5% buffer above Friday close for limit buy
    
    # Enhanced risk and filter parameters (optional variants)
    use_weekly_trailing_exit: bool = False  # Track trailing exit: sell at Friday Close if Close < Prev Week Low and in profit
    buy_only_below_last_tranche: bool = False  # Only buy new tranche if signal weekly close is below last bought tranche's buy price
    enable_magic_profit: bool = False   # Track 20-day Low breakdown on open tranches in loss and award magic profit
    magic_profit_amount: float = 500.0  # Profit amount added per event (default: 500)
    magic_profit_cooldown_days: int = 30 # Minimum days between magic profits for the same tranche (once in 30 days)
    magic_profit_lookback_days: int = 20 # Rolling low lookback (20 days upto 1 day ago)
    use_20w_low_tracking: bool = False  # Track rolling 20-week low breakdown to activate weekly breakout buying until 20-week high breakout
    lookback_weeks_tracking: int = 20   # Rolling lookback in weeks for breakdown activation and high deactivation
    stop_loss_pct: float = None         # Fixed % stop loss (e.g. 0.07 for -7%, None for no stop loss)
    max_holding_days: int = None        # Time-based exit limit in calendar days (e.g. 90, 120, None for no limit)
    use_trend_filter: bool = False      # Require Close > 20-week EMA
    trend_ema_period: int = 20          # Period for trend filter EMA
    min_spacing_up_pct: float = 0.0     # Minimum % above highest open tranche for pyramiding (0.0 to disable)
    min_spacing_down_pct: float = 0.0   # Minimum % below lowest open tranche for dip buying (0.0 to disable)
    darvas_box_weeks: int = 1           # Number of prior weeks high to break out from (1 = prev week)
    
    # Bearish + Bullish Combo parameters
    enable_bullish_combo: bool = False  # Reserve 1 tranche for 20W high breakout with simple annual return exit rule
    bullish_min_return_pct: float = 15.0 # Minimum simple profit % per annum required to exit bullish tranche on 20W low breakdown
    enable_compounding: bool = True     # Reinvest realized profits/dividends into overall capital dynamically

    # Historical date range
    start_date: str = "2021-01-01"
    end_date: str = "2026-10-11"
    
    # Default watchlist of liquid large-cap NSE stocks
    symbols: List[str] = field(default_factory=lambda: [
        "RELIANCE.NS",
        "HDFCBANK.NS",
        "INFY.NS",
        "ICICIBANK.NS",
        "TCS.NS"
    ])
    
    def __post_init__(self):
        if self.num_parts <= 0:
            raise ValueError("num_parts must be positive")
        self.tranche_capital = self.total_capital / self.num_parts
