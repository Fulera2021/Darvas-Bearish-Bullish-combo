import unittest
import pandas as pd

from config import BacktestConfig
from data_loader import build_weekly_data, add_weekly_signals
from backtest_engine import run_backtest
from web.cache_manager import ensure_symbol_data, ensure_symbol_dividends, DEFAULT_DB_PATH
from web.portfolio_simulator import run_portfolio_universe_simulation

class TestColdStartLogic(unittest.TestCase):
    def test_mfsl_cold_start_catches_buy_signal_on_21_aug_2026(self):
        """
        Verify that when MFSL is backtested from 2026-08-01:
        1. The cold start warmup detects the 20W low breakdown from April 2026.
        2. MFSL enters 20W low tracking mode.
        3. On 2026-08-21 (Close=1585.0 > Prev_Week_High=1574.9), a Bearish buy signal triggers.
        """
        start_date = "2026-08-01"
        end_date = "2026-10-15"
        norm_sym = "MFSL.NS"

        cfg = BacktestConfig(
            total_capital=40000.0,
            num_parts=4,
            target_pct=0.05,
            enable_magic_profit=False,
            use_20w_low_tracking=True,
            enable_bullish_combo=True,
            bullish_min_return_pct=15.0,
            enable_compounding=True,
            start_date=start_date,
            end_date=end_date
        )

        warmup_start_dt = (pd.to_datetime(start_date) - pd.Timedelta(days=365)).strftime("%Y-%m-%d")
        df_daily = ensure_symbol_data(norm_sym, warmup_start_dt, end_date, DEFAULT_DB_PATH)
        self.assertIsNotNone(df_daily)
        self.assertFalse(df_daily.empty)

        df_weekly = build_weekly_data(df_daily)
        df_weekly_signals = add_weekly_signals(df_weekly, entry_buffer_pct=cfg.entry_buffer_pct)
        df_div = ensure_symbol_dividends(norm_sym, warmup_start_dt, end_date, DEFAULT_DB_PATH)

        # 1. Run via single-stock backtest engine
        res = run_backtest(df_daily, df_weekly_signals, cfg, symbol=norm_sym, df_dividends=df_div)
        self.assertGreater(len(res.trades), 0, "Expected at least one trade for MFSL")

        first_trade = res.trades[0]
        self.assertEqual(first_trade.tranche_type, "BEARISH")
        self.assertEqual(first_trade.signal_date.strftime("%Y-%m-%d"), "2026-08-21")
        self.assertEqual(first_trade.buy_date.strftime("%Y-%m-%d"), "2026-08-21")
        self.assertEqual(round(first_trade.buy_price, 2), 1585.0)

        # 2. Run via portfolio simulator
        port_res = run_portfolio_universe_simulation([norm_sym], cfg, max_active_stocks=1, db_path=DEFAULT_DB_PATH)
        self.assertGreater(len(port_res.trades), 0, "Expected at least one trade in portfolio simulation")
        port_first_trade = port_res.trades[0]
        self.assertEqual(port_first_trade.signal_date.strftime("%Y-%m-%d"), "2026-08-21")
        self.assertEqual(round(port_first_trade.buy_price, 2), 1585.0)

if __name__ == "__main__":
    unittest.main()
