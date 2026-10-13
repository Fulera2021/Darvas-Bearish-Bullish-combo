import os
import sys
import unittest
import pandas as pd
from datetime import datetime, timedelta

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import BacktestConfig
from data_loader import build_weekly_data, add_weekly_signals

class TestDataLoader(unittest.TestCase):
    def test_default_config(self):
        cfg = BacktestConfig()
        self.assertEqual(cfg.total_capital, 100000.0)
        self.assertEqual(cfg.num_parts, 5)
        self.assertEqual(cfg.tranche_capital, 20000.0)
        self.assertEqual(cfg.target_pct, 0.05)
        self.assertEqual(cfg.entry_buffer_pct, 0.005)

    def test_weekly_aggregation_and_signals(self):
        # Create 3 weeks of mock daily data (Monday to Friday)
        dates = pd.date_range("2024-01-01", periods=15, freq="B")
        # Week 1: 5 days, prices 100 to 110. Week 1 High = 110, Close = 108
        # Week 2: prices 105 to 115. Week 2 Close = 112 (> 110, so Signal!)
        # Week 3: prices 110 to 120. Week 3 Close = 111 (< 115, No Signal)
        daily_records = []
        for i, dt in enumerate(dates):
            if i < 5:
                # Week 1
                daily_records.append({
                    "Date": dt, "Open": 100 + i, "High": 102 + i * 2, "Low": 99 + i, "Close": 100 + i * 2, "Volume": 1000
                })
            elif i < 10:
                # Week 2: ensure Close on Friday exceeds Week 1 High
                daily_records.append({
                    "Date": dt, "Open": 105 + i, "High": 108 + i, "Low": 104, "Close": 112 if i == 9 else 107 + i, "Volume": 1000
                })
            else:
                # Week 3
                daily_records.append({
                    "Date": dt, "Open": 110, "High": 115, "Low": 109, "Close": 111, "Volume": 1000
                })

        df_daily = pd.DataFrame(daily_records)
        df_weekly = build_weekly_data(df_daily)
        df_signals = add_weekly_signals(df_weekly, entry_buffer_pct=0.005)

        self.assertEqual(len(df_weekly), 3)
        # Week 2 should trigger signal because close > week 1 high
        self.assertTrue(df_signals.iloc[1]["breakout_signal"])
        self.assertAlmostEqual(df_signals.iloc[1]["entry_ceiling"], df_signals.iloc[1]["Close"] * 1.005, places=4)
        # Week 3 should not trigger signal
        self.assertFalse(df_signals.iloc[2]["breakout_signal"])

if __name__ == "__main__":
    unittest.main()
