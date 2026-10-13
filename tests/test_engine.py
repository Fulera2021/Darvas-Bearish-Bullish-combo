import os
import sys
import unittest
import pandas as pd
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import BacktestConfig
from data_loader import build_weekly_data, add_weekly_signals
from backtest_engine import run_backtest, BacktestResult, Tranche

class TestBacktestEngine(unittest.TestCase):
    def setUp(self):
        self.config = BacktestConfig(
            total_capital=100000.0,
            num_parts=5,
            tranche_capital=20000.0,
            target_pct=0.05,
            entry_buffer_pct=0.005
        )

    def test_single_trade_lifecycle(self):
        # 3 weeks daily data
        # Week 1: High 100, Close 95
        # Week 2: Friday Close = 105 (> Week 1 High 100 -> Signal!)
        # Week 3 Day 1 (Monday): Opens at 105.2, Low 104.5 -> Fills! Buy price = min(105.2, 105*1.005=105.525) = 105.2
        # Target = 105.2 * 1.05 = 110.46
        # Week 3 Day 3: High reaches 111.0 -> Target hit! Exits at 110.46
        daily_records = []
        # Week 1 (2024-01-01 to 2024-01-05)
        for i, dt in enumerate(pd.date_range("2024-01-01", periods=5, freq="B")):
            daily_records.append({"Date": dt, "Open": 95, "High": 100 if i==2 else 96, "Low": 92, "Close": 95, "Volume": 1000})
        # Week 2 (2024-01-08 to 2024-01-12)
        for i, dt in enumerate(pd.date_range("2024-01-08", periods=5, freq="B")):
            close_p = 105.0 if i == 4 else 98.0
            daily_records.append({"Date": dt, "Open": 98, "High": close_p, "Low": 97, "Close": close_p, "Volume": 1000})
        # Week 3 (2024-01-15 to 2024-01-19)
        # Day 1: fill
        daily_records.append({"Date": pd.Timestamp("2024-01-15"), "Open": 105.2, "High": 106.0, "Low": 104.5, "Close": 105.5, "Volume": 1000})
        # Day 2: hold
        daily_records.append({"Date": pd.Timestamp("2024-01-16"), "Open": 105.5, "High": 108.0, "Low": 105.0, "Close": 107.0, "Volume": 1000})
        # Day 3: target reached (High 111.0)
        daily_records.append({"Date": pd.Timestamp("2024-01-17"), "Open": 107.0, "High": 111.0, "Low": 106.5, "Close": 110.5, "Volume": 1000})
        # Day 4 & 5
        daily_records.append({"Date": pd.Timestamp("2024-01-18"), "Open": 110.0, "High": 112.0, "Low": 109.0, "Close": 111.0, "Volume": 1000})
        daily_records.append({"Date": pd.Timestamp("2024-01-19"), "Open": 111.0, "High": 113.0, "Low": 110.0, "Close": 112.0, "Volume": 1000})

        df_daily = pd.DataFrame(daily_records)
        df_weekly = build_weekly_data(df_daily)
        df_weekly = add_weekly_signals(df_weekly, entry_buffer_pct=self.config.entry_buffer_pct)

        result = run_backtest(df_daily, df_weekly, self.config, symbol="TEST")
        self.assertEqual(len(result.trades), 1)
        trade = result.trades[0]
        self.assertEqual(trade.status, "CLOSED")
        self.assertEqual(trade.slot_id, 1)
        self.assertAlmostEqual(trade.buy_price, 105.2, places=2)
        self.assertEqual(trade.buy_date.strftime("%Y-%m-%d"), "2024-01-15")
        self.assertEqual(trade.sell_date.strftime("%Y-%m-%d"), "2024-01-17")
        self.assertAlmostEqual(trade.sell_price, 105.2 * 1.05, places=2)
        self.assertGreater(trade.realized_pnl, 0)
        self.assertEqual(result.completed_trades, 1)
        self.assertEqual(result.open_trades, 0)

    def test_max_5_tranches_enforced(self):
        # Test that if 5 tranches are open and NEVER reach target (+5%), a 6th signal cannot buy
        # We simulate 8 consecutive weeks where each week's close is slightly higher than previous week's high,
        # but the total gain never exceeds 3% so no tranche ever hits the 5% target.
        # Week 1: 100.0 to 100.2
        # Week 2: 100.3 to 100.5 (> 100.2)
        # Week 3: 100.6 to 100.8
        # Week 4: 100.9 to 101.1
        # Week 5: 101.2 to 101.4
        # Week 6: 101.5 to 101.7
        # Week 7: 101.8 to 102.0
        # Week 8: 102.1 to 102.3
        dates = pd.date_range("2024-01-01", periods=45, freq="B")
        daily_records = []
        for i, dt in enumerate(dates):
            wk_idx = i // 5
            base_p = 100.0 + wk_idx * 0.3
            daily_records.append({
                "Date": dt,
                "Open": base_p,
                "High": base_p + 0.2,
                "Low": base_p - 0.1,
                "Close": base_p + 0.15,
                "Volume": 1000
            })
        df_daily = pd.DataFrame(daily_records)
        df_weekly = build_weekly_data(df_daily)
        df_weekly = add_weekly_signals(df_weekly, entry_buffer_pct=self.config.entry_buffer_pct)

        result = run_backtest(df_daily, df_weekly, self.config, symbol="TEST_MAX")
        self.assertLessEqual(result.max_active_tranches, 5)
        # Exactly 5 tranches filled and remained open, and no 6th was taken
        self.assertEqual(len(result.trades), 5)
        self.assertEqual(result.open_trades, 5)
        self.assertEqual(result.completed_trades, 0)

    def test_weekly_trailing_exit(self):
        # Test that with use_weekly_trailing_exit=True:
        # Week 0: High 90
        # Week 1: Close 95 > 90 -> Signal!
        # Week 2: Buys on Monday at 95. Friday Close 105.
        # Week 3: Friday Close 110. Low 106.
        # Week 4: Friday Close 102. Prev week Low was 106.
        # Condition: Week 4 Close (102) < Prev Week Low (106) AND Close (102) > Buy Price (95) -> EXITS in profit!
        cfg = BacktestConfig(use_weekly_trailing_exit=True)
        records = []
        # W0: 2023-12-25 to 2023-12-29
        for i, dt in enumerate(pd.date_range("2023-12-25", periods=5, freq="B")):
            records.append({"Date": dt, "Open": 88, "High": 90, "Low": 85, "Close": 89, "Volume": 1000})
        # W1: 2024-01-01 to 2024-01-05 (Close 95 > 90 -> Signal)
        for i, dt in enumerate(pd.date_range("2024-01-01", periods=5, freq="B")):
            records.append({"Date": dt, "Open": 91, "High": 95, "Low": 90, "Close": 95 if i==4 else 92, "Volume": 1000})
        # W2: 2024-01-08 to 2024-01-12 (Buy at 95 on Day 1, Close 105)
        for i, dt in enumerate(pd.date_range("2024-01-08", periods=5, freq="B")):
            records.append({"Date": dt, "Open": 95 if i==0 else 100, "High": 106, "Low": 94, "Close": 105 if i==4 else 101, "Volume": 1000})
        # W3: 2024-01-15 to 2024-01-19 (Hold, Low 106, Close 110)
        for i, dt in enumerate(pd.date_range("2024-01-15", periods=5, freq="B")):
            records.append({"Date": dt, "Open": 106, "High": 112, "Low": 106, "Close": 110 if i==4 else 108, "Volume": 1000})
        # W4: 2024-01-22 to 2024-01-26 (Close 102 < W3 Low 106, and 102 > Buy Price 95 -> Exits on Friday!)
        for i, dt in enumerate(pd.date_range("2024-01-22", periods=5, freq="B")):
            records.append({"Date": dt, "Open": 108, "High": 109, "Low": 100, "Close": 102 if i==4 else 104, "Volume": 1000})

        df_d = pd.DataFrame(records)
        df_w = add_weekly_signals(build_weekly_data(df_d))
        res = run_backtest(df_d, df_w, cfg, symbol="TEST_TRAIL")
        
        # Verify Trade 1 closed in profit at 102
        trade1 = [t for t in res.trades if t.buy_date.strftime("%Y-%m-%d") == "2024-01-08"][0]
        self.assertEqual(trade1.status, "CLOSED")
        self.assertEqual(trade1.sell_price, 102.0)
        self.assertEqual(trade1.sell_date.strftime("%Y-%m-%d"), "2024-01-26")
        self.assertGreater(trade1.realized_pnl, 0)

    def test_magic_profit_tracking(self):
        cfg = BacktestConfig(
            enable_magic_profit=True,
            magic_profit_amount=500.0,
            magic_profit_cooldown_days=30,
            magic_profit_lookback_days=20
        )
        records = []
        # W1: 2024-01-01 to 2024-01-05 (Baseline, High 95, Low 90, Close 92)
        for i, dt in enumerate(pd.date_range("2024-01-01", periods=5, freq="B")):
            records.append({"Date": dt, "Open": 91, "High": 95, "Low": 90, "Close": 92, "Volume": 1000})
        # W2: 2024-01-08 to 2024-01-12 (Baseline, High 95, Low 90, Close 92)
        for i, dt in enumerate(pd.date_range("2024-01-08", periods=5, freq="B")):
            records.append({"Date": dt, "Open": 91, "High": 95, "Low": 90, "Close": 92, "Volume": 1000})
        # W3: 2024-01-15 to 2024-01-19 (Baseline, High 95, Low 90, Close 92)
        for i, dt in enumerate(pd.date_range("2024-01-15", periods=5, freq="B")):
            records.append({"Date": dt, "Open": 91, "High": 95, "Low": 90, "Close": 92, "Volume": 1000})
        # W4: 2024-01-22 to 2024-01-26 (Baseline, High 95, Low 90, Close 92)
        for i, dt in enumerate(pd.date_range("2024-01-22", periods=5, freq="B")):
            records.append({"Date": dt, "Open": 91, "High": 95, "Low": 90, "Close": 92, "Volume": 1000})
        # W5: 2024-01-29 to 2024-02-02 (Close 100 > Prev High 95 -> Signal!)
        for i, dt in enumerate(pd.date_range("2024-01-29", periods=5, freq="B")):
            records.append({"Date": dt, "Open": 93, "High": 101, "Low": 91, "Close": 100 if i==4 else 94, "Volume": 1000})
        # W6: 2024-02-05 to 2024-02-09 (Buys on Day 1 at 100; Day 3 drops to 86 < 20DL 90 and in loss < 100)
        for i, dt in enumerate(pd.date_range("2024-02-05", periods=5, freq="B")):
            if i == 0:
                records.append({"Date": dt, "Open": 100, "High": 100.2, "Low": 98, "Close": 99, "Volume": 1000})
            elif i == 2:
                # Breakdown day! 20DL is 90. Close is 86. Tranche buy price is 100.
                records.append({"Date": dt, "Open": 92, "High": 92, "Low": 85, "Close": 86, "Volume": 1000})
            else:
                records.append({"Date": dt, "Open": 95, "High": 96, "Low": 91, "Close": 92, "Volume": 1000})

        df_d = pd.DataFrame(records)
        df_w = add_weekly_signals(build_weekly_data(df_d))
        res = run_backtest(df_d, df_w, cfg, symbol="TEST_MAGIC")

        # Verify magic profit events
        self.assertEqual(len(res.magic_events), 1)
        self.assertEqual(res.total_magic_profit, 500.0)
        ev1 = res.magic_events[0]
        self.assertEqual(ev1.profit_credit, 500.0)
        self.assertEqual(ev1.close_price, 86.0)
        self.assertLess(ev1.close_price, ev1.buy_price)
        self.assertLess(ev1.close_price, ev1.rolling_20d_low)

    def test_20w_low_tracking_strategy(self):
        cfg = BacktestConfig(use_20w_low_tracking=True)
        records = []
        base_start = pd.Timestamp("2023-01-02")
        
        # 20 weeks baseline: High 110, Low 90, Close 100
        for wk in range(20):
            wk_dates = pd.date_range(base_start + pd.Timedelta(weeks=wk), periods=5, freq="B")
            for i, dt in enumerate(wk_dates):
                records.append({"Date": dt, "Open": 95, "High": 110, "Low": 90, "Close": 100, "Volume": 1000})

        # Week 21: Breakdown below 20WL (90) -> Close 88 < 90 -> Activates tracking!
        w21_dates = pd.date_range(base_start + pd.Timedelta(weeks=20), periods=5, freq="B")
        for i, dt in enumerate(w21_dates):
            records.append({"Date": dt, "Open": 90, "High": 92, "Low": 86, "Close": 88 if i==4 else 89, "Volume": 1000})

        # Week 22: Inside week -> High 91, Low 85, Close 87 (does not break out above W21 High 92)
        w22_dates = pd.date_range(base_start + pd.Timedelta(weeks=21), periods=5, freq="B")
        for i, dt in enumerate(w22_dates):
            records.append({"Date": dt, "Open": 88, "High": 91, "Low": 85, "Close": 87 if i==4 else 88, "Volume": 1000})

        # Week 23: Breakout candle -> High 93, Close 92 > W22 High 91 -> Buys Tranche 1 at 92.00! Target = 96.60
        w23_dates = pd.date_range(base_start + pd.Timedelta(weeks=22), periods=5, freq="B")
        for i, dt in enumerate(w23_dates):
            records.append({"Date": dt, "Open": 88, "High": 93, "Low": 87, "Close": 92 if i==4 else 90, "Volume": 1000})

        # Week 24: Hits target! Day 2 High reaches 98.00 >= 96.60 -> Tranche 1 EXITS
        w24_dates = pd.date_range(base_start + pd.Timedelta(weeks=23), periods=5, freq="B")
        for i, dt in enumerate(w24_dates):
            records.append({"Date": dt, "Open": 92, "High": 98 if i==1 else 94, "Low": 91, "Close": 95, "Volume": 1000})

        # Week 25: Massive rally above 20WH (110) -> Close 115 > 110 -> Deactivates tracking!
        w25_dates = pd.date_range(base_start + pd.Timedelta(weeks=24), periods=5, freq="B")
        for i, dt in enumerate(w25_dates):
            records.append({"Date": dt, "Open": 100, "High": 116, "Low": 99, "Close": 115 if i==4 else 108, "Volume": 1000})

        # Week 26: Breakout above W25 High, but tracking is deactivated -> should NOT buy!
        w26_dates = pd.date_range(base_start + pd.Timedelta(weeks=25), periods=5, freq="B")
        for i, dt in enumerate(w26_dates):
            records.append({"Date": dt, "Open": 116, "High": 120, "Low": 114, "Close": 119 if i==4 else 117, "Volume": 1000})

        df_d = pd.DataFrame(records)
        df_w = add_weekly_signals(build_weekly_data(df_d))
        res = run_backtest(df_d, df_w, cfg, symbol="TEST_20W")

        # Verify: Exactly 2 trades taken and successfully closed in profit (and week 26 didn't buy because tracking deactivated)
        self.assertEqual(res.total_trades, 2)
        self.assertEqual(res.completed_trades, 2)
        self.assertEqual(res.open_trades, 0)
        self.assertEqual(res.trades[0].buy_price, 92.00)
        self.assertEqual(res.trades[0].status, "CLOSED")
        self.assertAlmostEqual(res.trades[0].sell_price, 92.00 * 1.05, places=2)
        self.assertEqual(res.trades[1].buy_price, 95.00)
        self.assertEqual(res.trades[1].status, "CLOSED")
        self.assertAlmostEqual(res.trades[1].sell_price, 95.00 * 1.05, places=2)

if __name__ == "__main__":
    unittest.main()


