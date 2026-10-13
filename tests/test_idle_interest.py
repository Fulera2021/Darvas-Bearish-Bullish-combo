import unittest
import pandas as pd
from pathlib import Path
import sys

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import BacktestConfig
from backtest_engine import run_backtest, BacktestResult

class TestIdleInterest(unittest.TestCase):
    def test_idle_interest_accumulation(self):
        # 30 business days where stock does not trade, capital stays idle
        dates = pd.date_range("2023-01-02", periods=30, freq="B")
        df_daily = pd.DataFrame({
            "Date": dates,
            "Open": [100.0] * 30,
            "High": [100.5] * 30,
            "Low": [99.5] * 30,
            "Close": [100.0] * 30,
            "Volume": [10000.0] * 30
        })
        df_weekly = pd.DataFrame([{
            "iso_year": 2023, "iso_week": 1,
            "Week_Start": dates[0], "Week_End": dates[-1],
            "Open": 100.0, "High": 100.5, "Low": 99.5, "Close": 100.0, "Volume": 300000.0,
            "Trading_Days": 30,
            "prev_week_high": 110.0, "breakout_signal": False,
            "reference_close": 100.0, "entry_ceiling": 100.5,
            "rolling_20w_low": None, "rolling_20w_high": None
        }])

        config = BacktestConfig(
            total_capital=100000.0,
            num_parts=5, # tranche capital = 20,000; untouched buffer = 20,000; eligible = 80,000
            start_date="2023-01-02",
            end_date="2023-02-15"
        )

        res = run_backtest(df_daily, df_weekly, config, symbol="IDLETEST.NS")
        self.assertTrue(hasattr(res, "idle_capital_interest"))
        self.assertGreater(res.idle_capital_interest, 0.0)

if __name__ == "__main__":
    unittest.main()
