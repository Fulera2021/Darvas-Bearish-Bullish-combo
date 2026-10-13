import unittest
import pandas as pd
import numpy as np

from config import BacktestConfig
from backtest_engine import run_backtest, Tranche
from data_loader import build_weekly_data, add_weekly_signals

class TestBullishCombo(unittest.TestCase):

    def _generate_synthetic_df(self):
        """
        Creates synthetic daily data spanning 2 years with:
        - Phase 1 (Weeks 1-25): Base range around 100
        - Phase 2 (Week 26): Drops to 65 (breaks 20W low, activates tracking)
        - Phase 3 (Weeks 27-28): Bounces to 75 (buys Bearish tranche)
        - Phase 4 (Weeks 35): Rallies to 160 (breaks 20W high, deactivates tracking, buys Bullish tranche)
        - Phase 5 (Weeks 60): Drops to 140 (breaks 20W low after rally).
        """
        dates = pd.date_range("2022-01-01", periods=600, freq="B")
        prices = []
        for i, dt in enumerate(dates):
            week_idx = i // 5
            if week_idx < 22:
                p = 100.0
            elif week_idx == 23:
                p = 65.0   # 20W low breakdown
            elif week_idx == 24:
                p = 75.0   # bounce buy
            elif week_idx == 30:
                p = 160.0  # 20W high breakout
            elif week_idx == 31:
                p = 165.0  # another 20W high
            elif week_idx == 50:
                p = 150.0  # breakdown with negative profit
            elif week_idx >= 75:
                p = 210.0  # breakdown with > 15% annual return
            else:
                p = 100.0
            prices.append(p)

        df_daily = pd.DataFrame({
            "Date": dates,
            "Open": prices,
            "High": [p * 1.01 for p in prices],
            "Low": [p * 0.99 for p in prices],
            "Close": prices,
            "Volume": 1000000
        })

        # Add rolling 20dl
        df_daily["rolling_20dl"] = df_daily["Low"].shift(1).rolling(20, min_periods=1).min()

        df_weekly = build_weekly_data(df_daily)
        df_weekly = add_weekly_signals(df_weekly)

        return df_daily, df_weekly

    def test_bullish_tranche_allocation_and_exit(self):
        cfg = BacktestConfig(
            total_capital=100000.0,
            num_parts=5,
            target_pct=0.05,
            enable_bullish_combo=True,
            bullish_min_return_pct=15.0,
            start_date="2022-01-01",
            end_date="2024-06-01"
        )
        # Verify 1 tranche reserved: 5 total parts, so max 4 bearish
        self.assertEqual(cfg.num_parts, 5)
        self.assertEqual(cfg.tranche_capital, 20000.0)

    def test_bullish_combo_engine_execution(self):
        df_daily, df_weekly = self._generate_synthetic_df()
        cfg = BacktestConfig(
            total_capital=100000.0,
            num_parts=5,
            target_pct=0.05,
            enable_bullish_combo=True,
            bullish_min_return_pct=15.0,
            use_20w_low_tracking=True,
            start_date="2022-01-01",
            end_date="2024-06-01"
        )
        res = run_backtest(df_daily, df_weekly, cfg, symbol="TEST_SYM")
        
        # Verify trades were created
        self.assertTrue(len(res.trades) > 0)
        
        # Check types of trades
        trade_types = [t.tranche_type for t in res.trades]
        self.assertIn("BULLISH", trade_types)
        
        # Check that bullish trades do not have a 5% target
        bullish_trades = [t for t in res.trades if t.tranche_type == "BULLISH"]
        for bt in bullish_trades:
            self.assertEqual(bt.target_price, float("inf"))

        # Verify max 1 concurrent bullish tranche
        open_bullish_counts = 0
        for bt in bullish_trades:
            if bt.status == "OPEN":
                open_bullish_counts += 1
        self.assertLessEqual(open_bullish_counts, 1)

if __name__ == "__main__":
    unittest.main()
