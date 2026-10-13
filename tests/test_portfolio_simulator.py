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
from web.portfolio_simulator import (
    PortfolioBacktestResult,
    run_portfolio_universe_simulation
)
from web.cache_manager import init_db, save_daily_data_to_cache

class TestPortfolioSimulator(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_cache.db")
        init_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_synthetic_stock(self, symbol: str):
        # 60 weeks of daily bars (from 2022-01-01 to 2023-03-31)
        dates = pd.date_range("2022-01-03", "2023-03-31", freq="B")
        data = []
        base = 200.0
        for i, dt in enumerate(dates):
            # Weeks 0-25: steady down from 200 to 100
            if i < 130:
                p = base - (i * 0.7)
            # Weeks 26-30: sharp reversal up jumping past previous highs
            elif i < 150:
                p = 100.0 + ((i - 130) * 3.0)
            # Weeks 31+: rally higher to hit 5% targets
            else:
                p = 160.0 + ((i - 150) * 2.0)
            
            high = p + 2.0
            low = p - 2.0
            close = p
            open_p = p - 0.5
            vol = 100000.0
            data.append({
                "Date": dt,
                "Open": open_p,
                "High": high,
                "Low": low,
                "Close": close,
                "Volume": vol
            })
        df = pd.DataFrame(data)
        save_daily_data_to_cache(symbol, df, db_path=self.db_path)

    def test_run_portfolio_universe_simulation(self):
        self._create_synthetic_stock("STOCKA.NS")
        self._create_synthetic_stock("STOCKB.NS")
        self._create_synthetic_stock("STOCKC.NS")

        config = BacktestConfig(
            total_capital=300000.0,
            num_parts=3,
            target_pct=0.05,
            start_date="2022-07-01",
            end_date="2023-03-30",
            use_20w_low_tracking=True
        )

        res = run_portfolio_universe_simulation(
            symbols=["STOCKA.NS", "STOCKB.NS", "STOCKC.NS"],
            config=config,
            max_active_stocks=2,
            db_path=self.db_path
        )

        self.assertIsInstance(res, PortfolioBacktestResult)
        self.assertEqual(res.total_capital, 300000.0)
        self.assertEqual(res.max_active_stocks, 2)
        self.assertGreater(res.total_trades, 0)
        self.assertGreater(res.completed_trades, 0)
        self.assertGreater(res.total_realized_profit, 0)
        self.assertGreater(res.idle_capital_interest, 0.0)
        self.assertAlmostEqual(
            res.total_realized_profit,
            round(res.realized_trade_profit + res.total_magic_profit + res.idle_capital_interest, 2),
            places=2
        )
        self.assertEqual(len(res.stock_summaries), 3)

if __name__ == "__main__":
    unittest.main()
