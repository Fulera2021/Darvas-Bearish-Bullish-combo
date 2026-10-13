import unittest
import pandas as pd
import numpy as np
import os
import tempfile
from pathlib import Path
import sys

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import BacktestConfig
from backtest_engine import run_backtest, BacktestResult, DividendEvent

class TestDividends(unittest.TestCase):
    def test_dividend_t_minus_2_rule(self):
        # 10 daily trading bars across 2 calendar weeks
        # Week 1: Day 0 (Mon Jan 2) to Day 4 (Fri Jan 6) -> 20W buy executed on Day 4 close
        # Week 2: Day 5 (Mon Jan 9), Day 6 (Tue Jan 10), Day 7 (Wed Jan 11)...
        dates = pd.date_range("2023-01-02", periods=10, freq="B")
        daily_records = []
        for i, dt in enumerate(dates):
            daily_records.append({
                "Date": dt,
                "Open": 100.0,
                "High": 102.0,
                "Low": 98.0,
                "Close": 100.0,
                "Volume": 50000.0
            })
        df_daily = pd.DataFrame(daily_records)

        # Weekly bars: Week 1 triggers 20w breakout on Friday (Day 4)
        weekly_records = [
            {
                "iso_year": 2023,
                "iso_week": 1,
                "Week_Start": dates[0],
                "Week_End": dates[4],
                "prev_week_high": 95.0,
                "rolling_20w_low": 120.0,
                "rolling_20w_high": 200.0
            },
            {
                "iso_year": 2023,
                "iso_week": 2,
                "Week_Start": dates[5],
                "Week_End": dates[9],
                "prev_week_high": 105.0,
                "rolling_20w_low": 120.0,
                "rolling_20w_high": 200.0
            }
        ]
        df_weekly = pd.DataFrame(weekly_records)

        config = BacktestConfig(
            total_capital=100000.0,
            num_parts=5,
            target_pct=0.10, # Keep target far so trade stays open
            start_date="2023-01-02",
            end_date="2023-01-13",
            use_20w_low_tracking=True
        )

        # Scenario A: Ex-Date on Day 6 (Tue 2023-01-10).
        # Buy occurred on Day 4 (Fri 2023-01-06).
        # T-2 trading day before Day 6 is Day 4 (Fri 2023-01-06).
        # Since buy_date (Day 4) <= T-2 (Day 4), trade IS eligible!
        df_div_eligible = pd.DataFrame([
            {"Date": dates[6], "Dividend": 5.0}  # Rs 5 per share
        ])

        res = run_backtest(df_daily, df_weekly, config, symbol="TESTA", df_dividends=df_div_eligible)
        self.assertEqual(len(res.trades), 1)
        t = res.trades[0]
        # Tranche capital = 20,000, buy price = 100 -> 200 shares
        expected_shares = 200
        self.assertEqual(t.shares, expected_shares)
        expected_dividend = expected_shares * 5.0  # Rs 1,000
        self.assertEqual(t.dividend_total, expected_dividend)
        self.assertEqual(res.dividend_income, expected_dividend)
        self.assertEqual(len(res.dividend_events), 1)
        ev = res.dividend_events[0]
        self.assertEqual(ev.total_payout, expected_dividend)
        self.assertEqual(ev.dividend_per_share, 5.0)

        # Total realized profit should include dividend income
        self.assertAlmostEqual(
            res.total_realized_profit,
            round(res.realized_trade_profit + res.total_magic_profit + res.idle_capital_interest + res.dividend_income, 2),
            places=2
        )

    def test_dividend_ineligible_if_bought_after_t_minus_2(self):
        # Scenario B: Ex-Date on Day 5 (Mon 2023-01-09).
        # Buy occurred on Day 4 (Fri 2023-01-06).
        # T-2 trading day before Day 5 is Day 3 (Thu 2023-01-05).
        # Since buy_date (Day 4) > T-2 (Day 3), trade is NOT eligible for dividend!
        dates = pd.date_range("2023-01-02", periods=10, freq="B")
        daily_records = []
        for dt in dates:
            daily_records.append({
                "Date": dt,
                "Open": 100.0,
                "High": 102.0,
                "Low": 98.0,
                "Close": 100.0,
                "Volume": 50000.0
            })
        df_daily = pd.DataFrame(daily_records)

        weekly_records = [
            {
                "iso_year": 2023,
                "iso_week": 1,
                "Week_Start": dates[0],
                "Week_End": dates[4],
                "prev_week_high": 95.0,
                "rolling_20w_low": 120.0,
                "rolling_20w_high": 200.0
            },
            {
                "iso_year": 2023,
                "iso_week": 2,
                "Week_Start": dates[5],
                "Week_End": dates[9],
                "prev_week_high": 105.0,
                "rolling_20w_low": 120.0,
                "rolling_20w_high": 200.0
            }
        ]
        df_weekly = pd.DataFrame(weekly_records)

        config = BacktestConfig(
            total_capital=100000.0,
            num_parts=5,
            target_pct=0.10,
            start_date="2023-01-02",
            end_date="2023-01-13",
            use_20w_low_tracking=True
        )

        df_div_ineligible = pd.DataFrame([
            {"Date": dates[5], "Dividend": 5.0}  # Ex-date on Day 5 (Mon)
        ])

        res = run_backtest(df_daily, df_weekly, config, symbol="TESTB", df_dividends=df_div_ineligible)
        self.assertEqual(len(res.trades), 1)
        t = res.trades[0]
        self.assertEqual(t.dividend_total, 0.0)
        self.assertEqual(res.dividend_income, 0.0)
        self.assertEqual(len(res.dividend_events), 0)

if __name__ == "__main__":
    unittest.main()
