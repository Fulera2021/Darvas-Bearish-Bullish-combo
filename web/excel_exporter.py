"""Excel export streaming module for single-stock and multi-stock universe backtests."""

import io
from typing import Optional
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import pandas as pd

from backtest_engine import BacktestResult, Tranche, MagicProfitEvent
from web.portfolio_simulator import PortfolioBacktestResult, StockSummary

FONT_NAME = "Segoe UI"
FONT_TITLE = Font(name=FONT_NAME, size=14, bold=True, color="1F497D")
FONT_SUBTITLE = Font(name=FONT_NAME, size=10, italic=True, color="595959")
FONT_KPI_LABEL = Font(name=FONT_NAME, size=9, bold=False, color="595959")
FONT_KPI_VAL = Font(name=FONT_NAME, size=11, bold=True, color="000000")
FONT_TBL_HEADER = Font(name=FONT_NAME, size=10, bold=True, color="FFFFFF")
FONT_DATA = Font(name=FONT_NAME, size=9, color="000000")
FONT_DATA_BOLD = Font(name=FONT_NAME, size=9, bold=True, color="000000")

FILL_HEADER = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
FILL_ZEBRA = PatternFill(start_color="F9FAFC", end_color="F9FAFC", fill_type="solid")
FILL_KPI_BG = PatternFill(start_color="F2F5F9", end_color="F2F5F9", fill_type="solid")
FILL_STATUS_CLOSED = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
FILL_STATUS_OPEN = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")

THIN_SIDE = Side(border_style="thin", color="D9D9D9")
THIN_BORDER = Border(left=THIN_SIDE, right=THIN_SIDE, top=THIN_SIDE, bottom=THIN_SIDE)

ALIGN_CENTER = Alignment(horizontal="center", vertical="center")
ALIGN_RIGHT = Alignment(horizontal="right", vertical="center")
ALIGN_LEFT = Alignment(horizontal="left", vertical="center")

NUM_FORMAT_DECIMAL = "#,##0.00"
NUM_FORMAT_INT = "#,##0"

def _format_date(val) -> str:
    if val is None or pd.isna(val):
        return "-"
    try:
        return pd.to_datetime(val).strftime("%d-%b-%Y")
    except Exception:
        return str(val)

def export_single_stock_excel(result: BacktestResult) -> io.BytesIO:
    """Generate in-memory .xlsx workbook for a single stock backtest."""
    wb = openpyxl.Workbook()
    
    # 1. Dashboard sheet
    ws_dash = wb.active
    ws_dash.title = "Dashboard"
    ws_dash.views.sheetView[0].showGridLines = True

    ws_dash.merge_cells("A1:H1")
    ws_dash["A1"] = f"{result.symbol} — 20W Darvas Box Backtest Results"
    ws_dash["A1"].font = FONT_TITLE
    ws_dash["A1"].alignment = ALIGN_LEFT

    ws_dash.merge_cells("A2:H2")
    ws_dash["A2"] = "Weekly 20W Low Breakout Swing Strategy | All values in plain numbers (INR)"
    ws_dash["A2"].font = FONT_SUBTITLE
    ws_dash["A2"].alignment = ALIGN_LEFT

    # KPI Table
    kpis = [
        ("Start Date", _format_date(getattr(result, "start_date", "-")), None),
        ("End Date", _format_date(getattr(result, "end_date", "-")), None),
        ("Initial Capital", result.initial_capital, NUM_FORMAT_DECIMAL),
        ("Realized Trade Profit", result.realized_trade_profit, NUM_FORMAT_DECIMAL),
        ("Magic Profit (20DL)", result.total_magic_profit, NUM_FORMAT_DECIMAL),
        ("Idle Interest (5% p.a.)", result.idle_capital_interest, NUM_FORMAT_DECIMAL),
        ("Dividend Income", result.dividend_income, NUM_FORMAT_DECIMAL),
        ("Total Realized Profit", result.total_realized_profit, NUM_FORMAT_DECIMAL),
        ("Unrealized Open P&L", result.unrealized_pnl, NUM_FORMAT_DECIMAL),
        ("Total Portfolio Return Amount", result.total_realized_profit + result.unrealized_pnl, NUM_FORMAT_DECIMAL),
        ("Total Portfolio Return %", f"{result.total_portfolio_return_pct:.2f}%", None),
        ("XIRR %", f"{result.deployed_xirr_pct:.2f}%", None),
        ("Total Trades", result.total_trades, NUM_FORMAT_INT),
        ("Completed Trades", result.completed_trades, NUM_FORMAT_INT),
        ("Open Positions", result.open_trades, NUM_FORMAT_INT),
        ("Max Drawdown %", f"{result.max_drawdown_pct:.2f}%", None),
        ("Ending Net Worth (If All Sold)", getattr(result, "ending_net_worth", result.initial_capital + result.total_realized_profit + result.unrealized_pnl), NUM_FORMAT_DECIMAL),
        ("Compounded Capital Base", getattr(result, "ending_overall_capital", result.initial_capital), NUM_FORMAT_DECIMAL),
        ("Ending Tranche Buy Amount", getattr(result, "ending_tranche_amount", 0.0), NUM_FORMAT_DECIMAL),
    ]

    row_idx = 4
    for label, val, fmt in kpis:
        ws_dash.cell(row=row_idx, column=1, value=label).font = FONT_KPI_LABEL
        ws_dash.cell(row=row_idx, column=1).fill = FILL_KPI_BG
        ws_dash.cell(row=row_idx, column=1).border = THIN_BORDER

        val_cell = ws_dash.cell(row=row_idx, column=2, value=val)
        val_cell.font = FONT_KPI_VAL
        val_cell.fill = FILL_KPI_BG
        val_cell.border = THIN_BORDER
        val_cell.alignment = ALIGN_RIGHT
        if fmt:
            val_cell.number_format = fmt
        row_idx += 1

    # 2. Trade Journal sheet
    ws_journal = wb.create_sheet(title="Trade Journal")
    ws_journal.views.sheetView[0].showGridLines = True
    ws_journal.freeze_panes = "A2"

    headers = [
        "Trade ID", "Type", "Slot ID", "Symbol", "Signal Date", "Buy Date", "Buy Price",
        "Shares", "Invested Amt", "Target Price", "Sell Date", "Sell Price",
        "Realized P&L", "Return %", "Holding Days", "Status", "Magic Profit", "Dividend"
    ]

    for col_idx, h in enumerate(headers, 1):
        cell = ws_journal.cell(row=1, column=col_idx, value=h)
        cell.font = FONT_TBL_HEADER
        cell.fill = FILL_HEADER
        cell.alignment = ALIGN_CENTER
        cell.border = THIN_BORDER

    for r_idx, tr in enumerate(result.trades, 2):
        row_data = [
            tr.trade_id, tr.tranche_type, tr.slot_id, tr.symbol, _format_date(tr.signal_date),
            _format_date(tr.buy_date), round(tr.buy_price, 2), tr.shares,
            round(tr.invested_amt, 2), round(tr.target_price, 2) if tr.target_price != float("inf") else "20W Low Exit",
            _format_date(tr.sell_date), round(tr.sell_price, 2) if tr.sell_price else "-",
            round(tr.realized_pnl, 2) if tr.realized_pnl is not None else 0.0,
            round(tr.return_pct, 2) if tr.return_pct is not None else 0.0,
            tr.holding_days if tr.holding_days is not None else "-",
            tr.status, round(tr.magic_profit_total, 2), round(tr.dividend_total, 2)
        ]
        is_even = (r_idx % 2 == 0)
        for c_idx, val in enumerate(row_data, 1):
            cell = ws_journal.cell(row=r_idx, column=c_idx, value=val)
            cell.font = FONT_DATA
            cell.border = THIN_BORDER
            if is_even:
                cell.fill = FILL_ZEBRA
            if c_idx in [1, 2, 4, 5, 10, 14, 15]:
                cell.alignment = ALIGN_CENTER
            elif c_idx == 3:
                cell.alignment = ALIGN_LEFT
            else:
                cell.alignment = ALIGN_RIGHT
                if isinstance(val, (int, float)):
                    cell.number_format = NUM_FORMAT_DECIMAL

            if c_idx == 15:
                cell.fill = FILL_STATUS_CLOSED if val == "CLOSED" else FILL_STATUS_OPEN

    # 3. Magic Events sheet (if any)
    if result.magic_events:
        ws_magic = wb.create_sheet(title="Magic Events")
        ws_magic.views.sheetView[0].showGridLines = True
        ws_magic.freeze_panes = "A2"
        m_headers = [
            "Event ID", "Date", "Trade ID", "Slot ID", "Buy Date", "Buy Price",
            "Rolling 20DL", "Close Price", "Loss %", "Profit Credit", "Open Tranches in Loss"
        ]
        for col_idx, h in enumerate(m_headers, 1):
            cell = ws_magic.cell(row=1, column=col_idx, value=h)
            cell.font = FONT_TBL_HEADER
            cell.fill = FILL_HEADER
            cell.alignment = ALIGN_CENTER
            cell.border = THIN_BORDER

        for r_idx, ev in enumerate(result.magic_events, 2):
            m_row = [
                ev.event_id, _format_date(ev.date), ev.trade_id, ev.slot_id,
                _format_date(ev.buy_date), round(ev.buy_price, 2),
                round(ev.rolling_20d_low, 2), round(ev.close_price, 2),
                f"{ev.loss_pct:.2f}%", round(ev.profit_credit, 2), ev.open_tranches_in_loss
            ]
            for c_idx, val in enumerate(m_row, 1):
                cell = ws_magic.cell(row=r_idx, column=c_idx, value=val)
                cell.font = FONT_DATA
                cell.border = THIN_BORDER
                cell.alignment = ALIGN_CENTER if c_idx in [1, 2, 3, 4, 5, 11] else ALIGN_RIGHT

    # 4. Dividends sheet (if any)
    if result.dividend_events:
        ws_div = wb.create_sheet(title="Dividends")
        ws_div.views.sheetView[0].showGridLines = True
        ws_div.freeze_panes = "A2"
        d_headers = [
            "Event ID", "Ex-Date", "Symbol", "Trade ID", "Slot ID", "Buy Date",
            "Shares Held", "Dividend / Share", "Total Payout"
        ]
        for col_idx, h in enumerate(d_headers, 1):
            cell = ws_div.cell(row=1, column=col_idx, value=h)
            cell.font = FONT_TBL_HEADER
            cell.fill = FILL_HEADER
            cell.alignment = ALIGN_CENTER
            cell.border = THIN_BORDER

        for r_idx, ev in enumerate(result.dividend_events, 2):
            d_row = [
                ev.event_id, _format_date(ev.ex_date), ev.symbol, ev.trade_id, ev.slot_id,
                _format_date(ev.buy_date), ev.shares, round(ev.dividend_per_share, 2), round(ev.total_payout, 2)
            ]
            for c_idx, val in enumerate(d_row, 1):
                cell = ws_div.cell(row=r_idx, column=c_idx, value=val)
                cell.font = FONT_DATA
                cell.border = THIN_BORDER
                cell.alignment = ALIGN_CENTER if c_idx in [1, 2, 3, 4, 5, 6] else ALIGN_RIGHT
                if c_idx in [7, 8, 9] and isinstance(val, (int, float)):
                    cell.number_format = NUM_FORMAT_DECIMAL

    # Monthly Summary sheet
    _build_monthly_summary_sheet(wb, getattr(result, "monthly_summaries", []), result.initial_capital)

    # Auto-adjust column widths
    for sheet in wb.worksheets:
        for col in sheet.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            sheet.column_dimensions[col_letter].width = max(max_len + 3, 12)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf

def _build_monthly_summary_sheet(wb: openpyxl.Workbook, monthly_summaries: list, total_capital: float):
    if monthly_summaries is None:
        return
    ws = wb.create_sheet(title="Monthly Summary")
    ws.views.sheetView[0].showGridLines = True
    ws.freeze_panes = "A2"

    headers = [
        "Year-MMM\n(Calendar Month)",
        "Buys\n(New tranches)",
        "Sells\n(Tranches closed)",
        "Trade Realized\n(Profit from closed tranches)",
        "Magic Profit",
        "Dividend\n(Dividend income received)",
        "Idle Interest\n(5% p.a. accrued on cash)",
        "Total Realized\n(Sum of realized profits)",
        "Max Capital Blocked\n(Peak deployed in trades)",
        "Idle Unused Cash\n(Uninvested cash buffer)",
        "Monthly Return %\n(Total Realized / Max Blocked)"
    ]

    for c_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=c_idx, value=h)
        cell.font = FONT_TBL_HEADER
        cell.fill = FILL_HEADER
        cell.alignment = Alignment(horizontal="center" if c_idx in [1, 2, 3] else "right", vertical="center", wrap_text=True)
        cell.border = THIN_BORDER
    ws.row_dimensions[1].height = 28

    if not monthly_summaries:
        return

    sum_buys = 0
    sum_sells = 0
    sum_trade = 0.0
    sum_magic = 0.0
    sum_div = 0.0
    sum_idle = 0.0
    sum_realized = 0.0
    peak_blocked = 0.0

    for r_idx, m in enumerate(monthly_summaries, 2):
        n_buys = getattr(m, "num_buys", 0)
        n_sells = getattr(m, "num_sells", 0)
        sum_buys += n_buys
        sum_sells += n_sells
        sum_trade += m.trade_realized_profit
        sum_magic += m.magic_profit
        sum_div += m.dividend_income
        sum_idle += m.idle_interest
        sum_realized += m.total_realized_profit
        if m.max_capital_blocked > peak_blocked:
            peak_blocked = m.max_capital_blocked

        m_ret = (m.total_realized_profit / m.max_capital_blocked) if m.max_capital_blocked > 0 else 0.0
        idle_cash = getattr(m, "idle_unused_cash", 0.0)

        row_data = [
            m.year_mmm, n_buys, n_sells, m.trade_realized_profit, m.magic_profit, m.dividend_income, m.idle_interest,
            m.total_realized_profit, m.max_capital_blocked, idle_cash, m_ret
        ]
        is_even = (r_idx % 2 == 0)
        for c_idx, val in enumerate(row_data, 1):
            cell = ws.cell(row=r_idx, column=c_idx, value=val)
            cell.font = FONT_DATA
            cell.border = THIN_BORDER
            if is_even:
                cell.fill = FILL_ZEBRA
            if c_idx == 1:
                cell.alignment = ALIGN_CENTER
            elif c_idx in [2, 3]:
                cell.alignment = ALIGN_RIGHT
                cell.number_format = NUM_FORMAT_INT
            else:
                cell.alignment = ALIGN_RIGHT
                if c_idx == 11:
                    cell.number_format = "0.00%"
                else:
                    cell.number_format = NUM_FORMAT_DECIMAL

    # Summary Footer row
    tot_row = len(monthly_summaries) + 2
    overall_ret = (sum_realized / peak_blocked) if peak_blocked > 0 else 0.0
    latest_idle = getattr(monthly_summaries[-1], "idle_unused_cash", 0.0) if monthly_summaries else 0.0

    footer_data = [
        "Total / Peak", sum_buys, sum_sells, sum_trade, sum_magic, sum_div, sum_idle,
        sum_realized, peak_blocked, latest_idle, overall_ret
    ]
    for c_idx, val in enumerate(footer_data, 1):
        cell = ws.cell(row=tot_row, column=c_idx, value=val)
        cell.font = FONT_DATA_BOLD
        cell.fill = FILL_KPI_BG
        cell.border = THIN_BORDER
        if c_idx == 1:
            cell.alignment = ALIGN_CENTER
        elif c_idx in [2, 3]:
            cell.alignment = ALIGN_RIGHT
            cell.number_format = NUM_FORMAT_INT
        else:
            cell.alignment = ALIGN_RIGHT
            if c_idx == 11:
                cell.number_format = "0.00%"
            else:
                cell.number_format = NUM_FORMAT_DECIMAL

def export_portfolio_excel(result: PortfolioBacktestResult) -> io.BytesIO:
    """Generate in-memory .xlsx workbook for a multi-stock universe backtest."""
    wb = openpyxl.Workbook()

    # 1. Dashboard sheet
    ws_dash = wb.active
    ws_dash.title = "Dashboard"
    ws_dash.views.sheetView[0].showGridLines = True

    ws_dash.merge_cells("A1:H1")
    ws_dash["A1"] = "Universe Portfolio Backtest Results"
    ws_dash["A1"].font = FONT_TITLE
    ws_dash["A1"].alignment = ALIGN_LEFT

    ws_dash.merge_cells("A2:H2")
    ws_dash["A2"] = "Weekly 20W Darvas Box Strategy | Shared Portfolio Pool | Plain Numbers (INR)"
    ws_dash["A2"].font = FONT_SUBTITLE
    ws_dash["A2"].alignment = ALIGN_LEFT

    kpis = [
        ("Start Date", _format_date(getattr(result, "start_date", "-")), None),
        ("End Date", _format_date(getattr(result, "end_date", "-")), None),
        ("Total Portfolio Capital", result.total_capital, NUM_FORMAT_DECIMAL),
        ("Max Concurrent Stocks", result.max_active_stocks, NUM_FORMAT_INT),
        ("Tranches Per Stock", result.num_parts, NUM_FORMAT_INT),
        ("Realized Trade Profit", result.realized_trade_profit, NUM_FORMAT_DECIMAL),
        ("Magic Profit (20DL)", result.total_magic_profit, NUM_FORMAT_DECIMAL),
        ("Idle Interest (5% p.a.)", result.idle_capital_interest, NUM_FORMAT_DECIMAL),
        ("Dividend Income", result.dividend_income, NUM_FORMAT_DECIMAL),
        ("Total Realized Profit", result.total_realized_profit, NUM_FORMAT_DECIMAL),
        ("Unrealized Open P&L", result.unrealized_pnl, NUM_FORMAT_DECIMAL),
        ("Total Portfolio Return Amount", result.total_realized_profit + result.unrealized_pnl, NUM_FORMAT_DECIMAL),
        ("Total Portfolio Return %", f"{result.total_portfolio_return_pct:.2f}%", None),
        ("XIRR %", f"{result.deployed_xirr_pct:.2f}%", None),
        ("Max Drawdown %", f"{result.max_drawdown_pct:.2f}%", None),
        ("Total Trades", result.total_trades, NUM_FORMAT_INT),
        ("Completed Trades", result.completed_trades, NUM_FORMAT_INT),
        ("Ending Net Worth (If All Sold)", getattr(result, "ending_net_worth", result.total_capital + result.total_realized_profit + result.unrealized_pnl), NUM_FORMAT_DECIMAL),
        ("Compounded Capital Base", getattr(result, "ending_overall_capital", result.total_capital), NUM_FORMAT_DECIMAL),
        ("Ending Tranche Buy Amount", getattr(result, "ending_tranche_amount", 0.0), NUM_FORMAT_DECIMAL),
    ]

    row_idx = 4
    for label, val, fmt in kpis:
        ws_dash.cell(row=row_idx, column=1, value=label).font = FONT_KPI_LABEL
        ws_dash.cell(row=row_idx, column=1).fill = FILL_KPI_BG
        ws_dash.cell(row=row_idx, column=1).border = THIN_BORDER

        val_cell = ws_dash.cell(row=row_idx, column=2, value=val)
        val_cell.font = FONT_KPI_VAL
        val_cell.fill = FILL_KPI_BG
        val_cell.border = THIN_BORDER
        val_cell.alignment = ALIGN_RIGHT
        if fmt:
            val_cell.number_format = fmt
        row_idx += 1

    # 2. Stock Breakdown sheet
    ws_breakdown = wb.create_sheet(title="Stock Breakdown")
    ws_breakdown.views.sheetView[0].showGridLines = True
    ws_breakdown.freeze_panes = "A2"

    b_headers = [
        "Symbol", "Total Trades", "Completed Trades", "Open Trades",
        "Realized Trade Profit", "Magic Profit", "Dividend", "Total Profit",
        "Open Invested", "Unrealized P&L"
    ]

    for col_idx, h in enumerate(b_headers, 1):
        cell = ws_breakdown.cell(row=1, column=col_idx, value=h)
        cell.font = FONT_TBL_HEADER
        cell.fill = FILL_HEADER
        cell.alignment = ALIGN_CENTER
        cell.border = THIN_BORDER

    for r_idx, s in enumerate(result.stock_summaries, 2):
        row_data = [
            s.symbol, s.total_trades, s.completed_trades, s.open_trades,
            s.realized_trade_profit, s.total_magic_profit, round(s.dividend_income, 2), s.total_profit,
            s.open_positions_invested, s.unrealized_pnl
        ]
        is_even = (r_idx % 2 == 0)
        for c_idx, val in enumerate(row_data, 1):
            cell = ws_breakdown.cell(row=r_idx, column=c_idx, value=val)
            cell.font = FONT_DATA
            cell.border = THIN_BORDER
            if is_even:
                cell.fill = FILL_ZEBRA
            if c_idx == 1:
                cell.alignment = ALIGN_LEFT
            elif c_idx in [2, 3, 4]:
                cell.alignment = ALIGN_CENTER
            else:
                cell.alignment = ALIGN_RIGHT
                if isinstance(val, (int, float)):
                    cell.number_format = NUM_FORMAT_DECIMAL

    # 3. Master Trade Journal sheet (if trades exist)
    if result.trades:
        ws_journal = wb.create_sheet(title="All Trades")
        ws_journal.views.sheetView[0].showGridLines = True
        ws_journal.freeze_panes = "A2"

        j_headers = [
            "Trade ID", "Type", "Symbol", "Slot ID", "Signal Date", "Buy Date", "Buy Price",
            "Shares", "Invested Amt", "Target Price", "Sell Date", "Sell Price",
            "Realized P&L", "Return %", "Holding Days", "Status", "Magic Profit", "Dividend"
        ]
        for col_idx, h in enumerate(j_headers, 1):
            cell = ws_journal.cell(row=1, column=col_idx, value=h)
            cell.font = FONT_TBL_HEADER
            cell.fill = FILL_HEADER
            cell.alignment = ALIGN_CENTER
            cell.border = THIN_BORDER

        for r_idx, tr in enumerate(result.trades, 2):
            row_data = [
                tr.trade_id, tr.tranche_type, tr.symbol, tr.slot_id, _format_date(tr.signal_date),
                _format_date(tr.buy_date), round(tr.buy_price, 2), tr.shares,
                round(tr.invested_amt, 2), round(tr.target_price, 2) if tr.target_price != float("inf") else "20W Low Exit",
                _format_date(tr.sell_date), round(tr.sell_price, 2) if tr.sell_price else "-",
                round(tr.realized_pnl, 2) if tr.realized_pnl is not None else 0.0,
                round(tr.return_pct, 2) if tr.return_pct is not None else 0.0,
                tr.holding_days if tr.holding_days is not None else "-",
                tr.status, round(tr.magic_profit_total, 2), round(tr.dividend_total, 2)
            ]
            is_even = (r_idx % 2 == 0)
            for c_idx, val in enumerate(row_data, 1):
                cell = ws_journal.cell(row=r_idx, column=c_idx, value=val)
                cell.font = FONT_DATA
                cell.border = THIN_BORDER
                if is_even:
                    cell.fill = FILL_ZEBRA
                if c_idx in [1, 3, 4, 5, 10, 14, 15]:
                    cell.alignment = ALIGN_CENTER
                elif c_idx == 2:
                    cell.alignment = ALIGN_LEFT
                else:
                    cell.alignment = ALIGN_RIGHT
                    if isinstance(val, (int, float)):
                        cell.number_format = NUM_FORMAT_DECIMAL

                if c_idx == 15:
                    cell.fill = FILL_STATUS_CLOSED if val == "CLOSED" else FILL_STATUS_OPEN

    # 4. Dividends sheet (if any)
    if result.dividend_events:
        ws_div = wb.create_sheet(title="Dividends")
        ws_div.views.sheetView[0].showGridLines = True
        ws_div.freeze_panes = "A2"
        d_headers = [
            "Event ID", "Ex-Date", "Symbol", "Trade ID", "Slot ID", "Buy Date",
            "Shares Held", "Dividend / Share", "Total Payout"
        ]
        for col_idx, h in enumerate(d_headers, 1):
            cell = ws_div.cell(row=1, column=col_idx, value=h)
            cell.font = FONT_TBL_HEADER
            cell.fill = FILL_HEADER
            cell.alignment = ALIGN_CENTER
            cell.border = THIN_BORDER

        for r_idx, ev in enumerate(result.dividend_events, 2):
            d_row = [
                ev.event_id, _format_date(ev.ex_date), ev.symbol, ev.trade_id, ev.slot_id,
                _format_date(ev.buy_date), ev.shares, round(ev.dividend_per_share, 2), round(ev.total_payout, 2)
            ]
            for c_idx, val in enumerate(d_row, 1):
                cell = ws_div.cell(row=r_idx, column=c_idx, value=val)
                cell.font = FONT_DATA
                cell.border = THIN_BORDER
                cell.alignment = ALIGN_CENTER if c_idx in [1, 2, 3, 4, 5, 6] else ALIGN_RIGHT
                if c_idx in [7, 8, 9] and isinstance(val, (int, float)):
                    cell.number_format = NUM_FORMAT_DECIMAL

    # Monthly Summary sheet
    _build_monthly_summary_sheet(wb, getattr(result, "monthly_summaries", []), result.total_capital)

    # Auto-adjust column widths
    for sheet in wb.worksheets:
        for col in sheet.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            sheet.column_dimensions[col_letter].width = max(max_len + 3, 12)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
