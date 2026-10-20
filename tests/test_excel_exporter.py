import unittest
import io
import openpyxl
from pathlib import Path
import sys

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest_engine import BacktestResult, Tranche, MagicProfitEvent, MonthlySummary
from web.portfolio_simulator import PortfolioBacktestResult, StockSummary
from web.excel_exporter import export_single_stock_excel, export_portfolio_excel

class TestExcelExporter(unittest.TestCase):
    def test_export_single_stock_excel(self):
        res = BacktestResult(
            symbol="RELIANCE.NS",
            initial_capital=100000.0,
            total_realized_profit=5000.0,
            total_trades=1,
            completed_trades=1,
            open_trades=0,
            win_rate_pct=100.0,
            max_active_tranches=1,
            total_invested_capital=20000.0,
            avg_holding_days=15.0,
            open_positions_invested=0.0,
            open_positions_current_value=0.0,
            unrealized_pnl=0.0,
            total_portfolio_return_pct=5.0,
            portfolio_xirr_pct=4.8,
            deployed_xirr_pct=45.2,
            realized_trade_profit=5000.0,
            total_magic_profit=0.0,
            trades=[
                Tranche(
                    trade_id=1,
                    slot_id=1,
                    symbol="RELIANCE.NS",
                    signal_date=Path("2023-01-06"),
                    buy_date=Path("2023-01-06"),
                    buy_price=2000.0,
                    shares=10,
                    invested_amt=20000.0,
                    target_price=2100.0,
                    sell_date=Path("2023-01-20"),
                    sell_price=2100.0,
                    realized_pnl=1000.0,
                    return_pct=5.0,
                    holding_days=14,
                    status="CLOSED"
                )
            ]
        )

        stream = export_single_stock_excel(res)
        self.assertIsInstance(stream, io.BytesIO)
        stream.seek(0)
        wb = openpyxl.load_workbook(stream)
        self.assertIn("Dashboard", wb.sheetnames)
        self.assertIn("Monthly Summary", wb.sheetnames)
        self.assertIn("Trade Journal", wb.sheetnames)

    def test_export_portfolio_excel(self):
        res = PortfolioBacktestResult(
            total_capital=500000.0,
            max_active_stocks=5,
            num_parts=5,
            total_realized_profit=25000.0,
            realized_trade_profit=25000.0,
            total_magic_profit=0.0,
            unrealized_pnl=0.0,
            total_portfolio_return_pct=5.0,
            portfolio_xirr_pct=5.1,
            deployed_xirr_pct=35.0,
            max_drawdown_pct=1.5,
            win_rate_pct=100.0,
            total_trades=5,
            completed_trades=5,
            open_trades=0,
            stock_summaries=[
                StockSummary(
                    symbol="RELIANCE.NS",
                    total_trades=1,
                    completed_trades=1,
                    open_trades=0,
                    realized_trade_profit=5000.0,
                    total_magic_profit=0.0,
                    total_profit=5000.0,
                    win_rate_pct=100.0,
                    open_positions_invested=0.0,
                    unrealized_pnl=0.0
                )
            ],
            trades=[]
        )

        stream = export_portfolio_excel(res)
        self.assertIsInstance(stream, io.BytesIO)
        stream.seek(0)
        wb = openpyxl.load_workbook(stream)
        self.assertIn("Dashboard", wb.sheetnames)
        self.assertIn("Monthly Summary", wb.sheetnames)
        self.assertIn("Stock Breakdown", wb.sheetnames)

    def test_monthly_summary_sheet_content(self):
        m = MonthlySummary(
            year_mmm="2023-Jan",
            trade_realized_profit=2500.0,
            magic_profit=500.0,
            dividend_income=100.0,
            idle_interest=200.0,
            total_realized_profit=3300.0,
            month_end_unrealized=1200.0,
            net_monthly_pnl=4500.0,
            max_capital_blocked=40000.0,
            monthly_return_pct=4.5,
            max_drawdown_pct=2.1,
            month_end_drawdown_pct=1.0,
            idle_unused_cash=60000.0
        )
        res = BacktestResult(
            symbol="INFY.NS",
            initial_capital=100000.0,
            total_realized_profit=3300.0,
            total_trades=1,
            completed_trades=1,
            open_trades=0,
            win_rate_pct=100.0,
            max_active_tranches=1,
            total_invested_capital=40000.0,
            avg_holding_days=10.0,
            open_positions_invested=0.0,
            open_positions_current_value=0.0,
            unrealized_pnl=1200.0,
            total_portfolio_return_pct=4.5,
            portfolio_xirr_pct=4.5,
            deployed_xirr_pct=20.0,
            realized_trade_profit=2500.0,
            total_magic_profit=500.0,
            monthly_summaries=[m],
            trades=[]
        )

        stream = export_single_stock_excel(res)
        wb = openpyxl.load_workbook(stream)
        self.assertIn("Monthly Summary", wb.sheetnames)
        ws = wb["Monthly Summary"]

        # Check headers
        self.assertIn("Year-MMM", ws.cell(row=1, column=1).value)
        self.assertIn("Trade Realized", ws.cell(row=1, column=2).value)
        self.assertEqual(ws.cell(row=1, column=3).value, "Magic Profit")
        self.assertIn("Total Realized", ws.cell(row=1, column=6).value)
        self.assertIn("Max Capital Blocked", ws.cell(row=1, column=7).value)
        self.assertIn("Idle Unused Cash", ws.cell(row=1, column=8).value)
        self.assertIn("Monthly Return %", ws.cell(row=1, column=9).value)
        self.assertIsNone(ws.cell(row=1, column=10).value)

        # Check data row
        self.assertEqual(ws.cell(row=2, column=1).value, "2023-Jan")
        self.assertEqual(ws.cell(row=2, column=2).value, 2500.0)
        self.assertEqual(ws.cell(row=2, column=3).value, 500.0)
        self.assertEqual(ws.cell(row=2, column=6).value, 3300.0)
        self.assertEqual(ws.cell(row=2, column=7).value, 40000.0)
        self.assertEqual(ws.cell(row=2, column=8).value, 60000.0)
        # Monthly return = 3300 / 40000 = 0.0825
        self.assertAlmostEqual(ws.cell(row=2, column=9).value, 0.0825)

        # Check summary footer row
        self.assertEqual(ws.cell(row=3, column=1).value, "Total / Peak")
        self.assertEqual(ws.cell(row=3, column=6).value, 3300.0)
        self.assertEqual(ws.cell(row=3, column=7).value, 40000.0)
        self.assertEqual(ws.cell(row=3, column=8).value, 60000.0)
        self.assertAlmostEqual(ws.cell(row=3, column=9).value, 0.0825)

if __name__ == "__main__":
    unittest.main()
