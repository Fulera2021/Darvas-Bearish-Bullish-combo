import unittest
from pathlib import Path
import sys
import os
import tempfile
import pandas as pd
from datetime import datetime

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import BacktestConfig
from data_loader import build_weekly_data, add_weekly_signals
from backtest_engine import generate_monthly_summaries, MonthlySummary, run_backtest
from web.portfolio_simulator import run_portfolio_universe_simulation, PortfolioBacktestResult
from web.cache_manager import init_db, save_daily_data_to_cache
from web.app import app
from fastapi.testclient import TestClient

class TestMonthlySummary(unittest.TestCase):
    def test_generate_monthly_summaries_calculation(self):
        # Create mock daily snapshots across 2 months
        snapshots = [
            # January 2023
            {
                "date": datetime(2023, 1, 5),
                "trade_realized": 1000.0,
                "magic_profit": 500.0,
                "dividend": 50.0,
                "idle_interest": 100.0,
                "open_invested": 50000.0,
                "unrealized_pnl": 200.0,
                "daily_equity": 101850.0,
                "drawdown_pct": 0.5
            },
            {
                "date": datetime(2023, 1, 20),
                "trade_realized": 2000.0,
                "magic_profit": 0.0,
                "dividend": 0.0,
                "idle_interest": 100.0,
                "open_invested": 75000.0,
                "unrealized_pnl": 1000.0,
                "daily_equity": 103750.0,
                "drawdown_pct": 1.8
            },
            # February 2023
            {
                "date": datetime(2023, 2, 10),
                "trade_realized": 500.0,
                "magic_profit": 200.0,
                "dividend": 0.0,
                "idle_interest": 80.0,
                "open_invested": 40000.0,
                "unrealized_pnl": 1500.0,
                "daily_equity": 105000.0,
                "drawdown_pct": 0.8
            }
        ]

        total_capital = 100000.0
        summaries = generate_monthly_summaries(snapshots, total_capital)

        self.assertEqual(len(summaries), 2)

        # Verify Jan 2023
        jan = summaries[0]
        self.assertEqual(jan.year_mmm, "2023-Jan")
        self.assertAlmostEqual(jan.trade_realized_profit, 3000.0)
        self.assertAlmostEqual(jan.magic_profit, 500.0)
        self.assertAlmostEqual(jan.dividend_income, 50.0)
        self.assertAlmostEqual(jan.idle_interest, 200.0)
        self.assertAlmostEqual(jan.total_realized_profit, 3750.0)
        self.assertAlmostEqual(jan.max_capital_blocked, 75000.0)
        # Monthly return % = (3750 / 75000) * 100 = 5.0%
        self.assertAlmostEqual(jan.monthly_return_pct, 5.0)
        self.assertAlmostEqual(jan.max_drawdown_pct, 1.8)
        self.assertAlmostEqual(jan.idle_unused_cash, 25000.0)

        # Verify Feb 2023
        feb = summaries[1]
        self.assertEqual(feb.year_mmm, "2023-Feb")
        self.assertAlmostEqual(feb.trade_realized_profit, 500.0)
        self.assertAlmostEqual(feb.magic_profit, 200.0)
        self.assertAlmostEqual(feb.dividend_income, 0.0)
        self.assertAlmostEqual(feb.idle_interest, 80.0)
        self.assertAlmostEqual(feb.total_realized_profit, 780.0)
        self.assertAlmostEqual(feb.max_capital_blocked, 40000.0)
        # Monthly return % = (780 / 40000) * 100 = 1.95%
        self.assertAlmostEqual(feb.monthly_return_pct, 1.95)
        self.assertAlmostEqual(feb.max_drawdown_pct, 0.8)
        self.assertAlmostEqual(feb.idle_unused_cash, 60000.0)

    def test_single_stock_monthly_summary_generated(self):
        daily_records = []
        for i, dt in enumerate(pd.date_range("2024-01-01", periods=10, freq="B")):
            daily_records.append({"Date": dt, "Open": 95, "High": 100 if i==2 else 96, "Low": 92, "Close": 95, "Volume": 1000})
        df_daily = pd.DataFrame(daily_records)
        df_weekly = build_weekly_data(df_daily)
        df_weekly = add_weekly_signals(df_weekly, entry_buffer_pct=0.005)
        config = BacktestConfig(total_capital=100000.0, num_parts=5)

        res = run_backtest(df_daily, df_weekly, config, symbol="TEST")
        self.assertIsInstance(res.monthly_summaries, list)
        self.assertGreater(len(res.monthly_summaries), 0)
        first_m = res.monthly_summaries[0]
        self.assertRegex(first_m.year_mmm, r"^\d{4}-[A-Z][a-z]{2}$")

    def test_portfolio_monthly_summary_generated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test_cache.db")
            init_db(db_path)

            dates = pd.date_range("2022-01-03", "2023-03-31", freq="B")
            data = []
            for dt in dates:
                data.append({
                    "Date": dt,
                    "Open": 100.0,
                    "High": 105.0,
                    "Low": 95.0,
                    "Close": 102.0,
                    "Volume": 1000
                })
            df = pd.DataFrame(data)
            save_daily_data_to_cache("TEST_STOCK.NS", df, db_path=db_path)

            config = BacktestConfig(
                total_capital=100000.0,
                num_parts=5,
                start_date="2022-07-01",
                end_date="2023-03-30"
            )
            res = run_portfolio_universe_simulation(
                symbols=["TEST_STOCK.NS"],
                config=config,
                max_active_stocks=1,
                db_path=db_path
            )
            self.assertIsInstance(res.monthly_summaries, list)
            self.assertGreater(len(res.monthly_summaries), 0)

    def test_web_api_includes_monthly_summary(self):
        client = TestClient(app)
        payload = {
            "mode": "stock",
            "symbol": "RELIANCE.NS",
            "start_date": "2023-01-01",
            "end_date": "2023-06-30",
            "capital": 100000.0,
            "num_parts": 5,
            "target_pct": 5.0,
            "trailing_stop_pct": 3.0,
            "enable_bearish": True,
            "bearish_target_pct": 5.0,
            "bearish_trailing_stop_pct": 3.0,
            "enable_magic_profit": False,
            "magic_profit_threshold": 0.0,
            "enable_dividends": True,
            "enable_idle_interest": True,
            "interest_rate_pct": 5.0
        }
        response = client.post("/api/backtest", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("monthly_summary", data)
        self.assertIsInstance(data["monthly_summary"], list)
        self.assertGreater(len(data["monthly_summary"]), 0)
        item = data["monthly_summary"][0]
        self.assertIn("year_mmm", item)
        self.assertIn("trade_realized_profit", item)
        self.assertIn("total_realized_profit", item)
        self.assertIn("net_monthly_pnl", item)
        self.assertIn("max_capital_blocked", item)
        self.assertIn("idle_unused_cash", item)
        self.assertIn("monthly_return_pct", item)
        self.assertIn("max_drawdown_pct", item)

if __name__ == "__main__":
    unittest.main()
