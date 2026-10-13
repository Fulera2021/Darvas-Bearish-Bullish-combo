import os
import sys
import unittest
import openpyxl
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import BacktestConfig
from backtest_engine import BacktestResult, Tranche
from excel_reporter import export_backtest_to_excel

class TestExcelReporter(unittest.TestCase):
    def test_excel_export_and_plain_numbers(self):
        output_path = os.path.join(os.path.dirname(__file__), "test_output.xlsx")
        if os.path.exists(output_path):
            os.remove(output_path)

        trade = Tranche(
            trade_id=1,
            slot_id=1,
            symbol="RELIANCE.NS",
            signal_date=pd.Timestamp("2024-01-12"),
            buy_date=pd.Timestamp("2024-01-15"),
            buy_price=2500.0,
            shares=8,
            invested_amt=20000.0,
            target_price=2625.0,
            sell_date=pd.Timestamp("2024-01-25"),
            sell_price=2625.0,
            realized_pnl=1000.0,
            return_pct=5.0,
            holding_days=10,
            status="CLOSED"
        )
        result = BacktestResult(
            symbol="RELIANCE.NS",
            initial_capital=100000.0,
            total_realized_profit=1000.0,
            total_trades=1,
            completed_trades=1,
            open_trades=0,
            win_rate_pct=100.0,
            max_active_tranches=1,
            total_invested_capital=20000.0,
            avg_holding_days=10.0,
            open_positions_invested=0.0,
            open_positions_current_value=0.0,
            unrealized_pnl=0.0,
            total_portfolio_return_pct=1.0,
            trades=[trade]
        )
        cfg = BacktestConfig()

        filepath = export_backtest_to_excel(result, cfg, output_path)
        self.assertTrue(os.path.exists(filepath))

        # Inspect workbook
        wb = openpyxl.load_workbook(filepath)
        ws = wb.active

        # Check that NO cells contain the rupee symbol
        found_rupee = False
        for row in ws.iter_rows(values_only=True):
            for cell_val in row:
                if cell_val is not None and "₹" in str(cell_val):
                    found_rupee = True
                    break
        self.assertFalse(found_rupee, "Excel output should not contain any rupee symbols")

        wb.close()
        if os.path.exists(output_path):
            os.remove(output_path)

if __name__ == "__main__":
    unittest.main()
