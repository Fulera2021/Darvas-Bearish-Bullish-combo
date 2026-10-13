"""Comparative Backtest Runner: Baseline vs Without-SL Enhancements vs With-SL Risk Controls.
Runs all variants across liquid stocks and generates a side-by-side comparison report.
"""

import os
import sys
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from config import BacktestConfig
from data_loader import fetch_daily_data, build_weekly_data, add_weekly_signals
from backtest_engine import run_backtest, BacktestResult

def run_all_variants():
    symbols = ["RELIANCE.NS", "ICICIBANK.NS", "HDFCBANK.NS", "TCS.NS", "INFY.NS"]
    start_date = "2021-01-01"
    end_date = "2026-10-11"
    
    # 1. Preload data for all symbols
    data_cache = {}
    print("Pre-loading historical data for all symbols...")
    for sym in symbols:
        df_d = fetch_daily_data(sym, start_date, end_date)
        df_w_raw = build_weekly_data(df_d)
        data_cache[sym] = (df_d, df_w_raw)

    # 2. Define Variants
    variants = [
        {
            "id": "Baseline",
            "name": "Baseline (Pure Breakout, No SL, No Filter)",
            "config": BacktestConfig(start_date=start_date, end_date=end_date),
            "use_trend": False,
            "box_weeks": 1
        },
        {
            "id": "V1_NoSL_Filter",
            "name": "V1 (No SL): Anti-Cluster + 20w EMA Trend",
            "config": BacktestConfig(
                start_date=start_date, end_date=end_date,
                use_trend_filter=True,
                min_spacing_up_pct=0.04,
                min_spacing_down_pct=0.07
            ),
            "use_trend": True,
            "box_weeks": 1
        },
        {
            "id": "V2_FixedSL_7pct",
            "name": "V2 (With SL): Fixed -7% Stop Loss",
            "config": BacktestConfig(
                start_date=start_date, end_date=end_date,
                stop_loss_pct=0.07
            ),
            "use_trend": False,
            "box_weeks": 1
        },
        {
            "id": "V3_TimeExit_90d",
            "name": "V3 (With SL): 90-Day Capital Velocity Exit",
            "config": BacktestConfig(
                start_date=start_date, end_date=end_date,
                max_holding_days=90
            ),
            "use_trend": False,
            "box_weeks": 1
        },
        {
            "id": "V4_Hybrid_Optimal",
            "name": "V4 (Hybrid): Trend + Anti-Cluster + 90d Exit / -8% SL",
            "config": BacktestConfig(
                start_date=start_date, end_date=end_date,
                use_trend_filter=True,
                min_spacing_up_pct=0.04,
                min_spacing_down_pct=0.07,
                max_holding_days=90,
                stop_loss_pct=0.08
            ),
            "use_trend": True,
            "box_weeks": 1
        }
    ]

    all_results = []
    
    print("\nRunning Backtest across variants and symbols...")
    for v in variants:
        v_id = v["id"]
        v_name = v["name"]
        cfg = v["config"]
        use_trend = v["use_trend"]
        box_weeks = v["box_weeks"]

        sym_results = []
        for sym in symbols:
            df_d, df_w_raw = data_cache[sym]
            df_w = add_weekly_signals(
                df_w_raw,
                entry_buffer_pct=cfg.entry_buffer_pct,
                use_trend_filter=use_trend,
                darvas_box_weeks=box_weeks
            )
            res = run_backtest(df_d, df_w, cfg, symbol=sym)
            sym_results.append(res)
            
            # Record individual stock row
            trapped_count = sum(1 for t in res.trades if (t.status == "OPEN" and (df_d["Date"].iloc[-1] - t.buy_date).days > 180) or (t.holding_days or 0) > 180)
            all_results.append({
                "Variant_ID": v_id,
                "Variant_Name": v_name,
                "Symbol": sym,
                "Total_Capital": res.initial_capital,
                "Realized_Profit": res.total_realized_profit,
                "Unrealized_PnL": res.unrealized_pnl,
                "Net_Portfolio_Return_Pct": res.total_portfolio_return_pct,
                "Max_Drawdown_Pct": res.max_drawdown_pct,
                "Total_Trades": res.total_trades,
                "Completed_Trades": res.completed_trades,
                "Open_Trades": res.open_trades,
                "Win_Rate_Pct": res.win_rate_pct,
                "Avg_Holding_Days": res.avg_holding_days,
                "Trapped_Trades_180d": trapped_count
            })

    df_details = pd.DataFrame(all_results)

    # 3. Aggregate Portfolio-Level Summary across all 5 stocks (500,000 total capital)
    portfolio_summary = []
    for v in variants:
        v_id = v["id"]
        sub = df_details[df_details["Variant_ID"] == v_id]
        tot_cap = sub["Total_Capital"].sum()
        tot_realized = sub["Realized_Profit"].sum()
        tot_unrealized = sub["Unrealized_PnL"].sum()
        net_ret_pct = round(((tot_realized + tot_unrealized) / tot_cap) * 100.0, 2)
        worst_dd = sub["Max_Drawdown_Pct"].min()
        tot_trades = sub["Total_Trades"].sum()
        tot_completed = sub["Completed_Trades"].sum()
        tot_open = sub["Open_Trades"].sum()
        tot_trapped = sub["Trapped_Trades_180d"].sum()
        avg_hold = round(sub["Avg_Holding_Days"].mean(), 1)
        avg_win_rate = round(sub["Win_Rate_Pct"].mean(), 1)
        
        portfolio_summary.append({
            "Variant_ID": v_id,
            "Strategy Variant": v["name"],
            "Total Capital": tot_cap,
            "Realized Profit": tot_realized,
            "Unrealized P&L": tot_unrealized,
            "Net Return %": net_ret_pct,
            "Max Drawdown %": worst_dd,
            "Win Rate %": avg_win_rate,
            "Total Trades": tot_trades,
            "Completed": tot_completed,
            "Open Active": tot_open,
            "Trapped (>180d)": tot_trapped,
            "Avg Holding Days": avg_hold
        })

    df_portfolio = pd.DataFrame(portfolio_summary)

    # 4. Print Summary Table
    print("\n" + "=" * 115)
    print("                    PORTFOLIO PERFORMANCE COMPARISON (5 STOCKS | CAPITAL: 500,000)")
    print("=" * 115)
    for idx, row in df_portfolio.iterrows():
        print(f"[{row['Variant_ID']}] {row['Strategy Variant']}")
        print(f"   Net Return: {row['Net Return %']:>6.2f}% | Realized Profit: {row['Realized Profit']:>10,.2f} | Unrealized P&L: {row['Unrealized P&L']:>10,.2f}")
        print(f"   Max Drawdown: {row['Max Drawdown %']:>6.2f}% | Win Rate: {row['Win Rate %']:>5.1f}% | Total Trades: {row['Total Trades']:>3} (Completed: {row['Completed']:>3}, Open: {row['Open Active']:>2})")
        print(f"   Avg Hold: {row['Avg Holding Days']:>5.1f} days | Trapped Positions (>180d): {row['Trapped (>180d)']}")
        print("-" * 115)

    # 5. Export to Styled Excel Comparison Workbook
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, "Strategy_Variants_Comparison.xlsx")

    wb = openpyxl.Workbook()
    # Sheet 1: Portfolio Comparison
    ws1 = wb.active
    ws1.title = "Executive Summary"
    ws1.views.sheetView[0].showGridLines = True
    
    font_fam = "Segoe UI"
    font_title = Font(name=font_fam, size=14, bold=True, color="1F497D")
    font_hdr = Font(name=font_fam, size=10, bold=True, color="FFFFFF")
    font_cell = Font(name=font_fam, size=9)
    fill_hdr = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
    fill_alt = PatternFill(start_color="F9FAFC", end_color="F9FAFC", fill_type="solid")
    thin_side = Side(border_style="thin", color="D9D9D9")
    thin_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

    ws1["B2"] = "STRATEGY VARIANTS COMPARISON - PORTFOLIO EXECUTIVE SUMMARY"
    ws1["B2"].font = font_title
    ws1["B3"] = "Testing 5 Liquid Stocks (RELIANCE, ICICIBANK, HDFCBANK, TCS, INFY) | 2021 to 2026 | Capital: 100,000 / stock"
    ws1["B3"].font = Font(name=font_fam, size=10, italic=True, color="595959")

    # Table 1: Portfolio Summary
    start_r = 5
    p_cols = list(df_portfolio.columns[1:]) # Skip Variant_ID
    for c_i, col_name in enumerate(p_cols, start=2):
        c = ws1.cell(start_r, c_i, col_name)
        c.font = font_hdr
        c.fill = fill_hdr
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = thin_border

    curr_r = start_r + 1
    for _, row in df_portfolio.iterrows():
        is_alt = (curr_r % 2 == 0)
        for c_i, col_name in enumerate(p_cols, start=2):
            val = row[col_name]
            c = ws1.cell(curr_r, c_i, val)
            c.font = font_cell
            c.border = thin_border
            if is_alt:
                c.fill = fill_alt
            # Formats
            if "Profit" in col_name or "P&L" in col_name or "Capital" in col_name:
                c.number_format = "#,##0.00"
                c.alignment = Alignment(horizontal="right")
            elif "%" in col_name:
                c.number_format = "0.00" if "Net" in col_name or "Max" in col_name else "0.0"
                c.alignment = Alignment(horizontal="right")
            elif "Days" in col_name:
                c.number_format = "0.0"
                c.alignment = Alignment(horizontal="right")
            elif isinstance(val, (int, float)):
                c.number_format = "#,##0"
                c.alignment = Alignment(horizontal="right")
            else:
                c.alignment = Alignment(horizontal="left")
        curr_r += 1

    # Sheet 2: Stock-by-stock Breakdown
    ws2 = wb.create_sheet(title="Stock Level Breakdown")
    ws2.views.sheetView[0].showGridLines = True
    ws2["B2"] = "STOCK-BY-STOCK METRICS ACROSS ALL VARIANTS"
    ws2["B2"].font = font_title

    start_r2 = 4
    d_cols = [c for c in df_details.columns if c != "Variant_ID"]
    for c_i, col_name in enumerate(d_cols, start=2):
        c = ws2.cell(start_r2, c_i, col_name.replace("_", " "))
        c.font = font_hdr
        c.fill = fill_hdr
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = thin_border

    curr_r2 = start_r2 + 1
    for _, row in df_details.iterrows():
        is_alt = (curr_r2 % 2 == 0)
        for c_i, col_name in enumerate(d_cols, start=2):
            val = row[col_name]
            c = ws2.cell(curr_r2, c_i, val)
            c.font = font_cell
            c.border = thin_border
            if is_alt:
                c.fill = fill_alt
            if "Profit" in col_name or "PnL" in col_name or "Capital" in col_name:
                c.number_format = "#,##0.00"
                c.alignment = Alignment(horizontal="right")
            elif "Pct" in col_name:
                c.number_format = "0.00"
                c.alignment = Alignment(horizontal="right")
            elif "Days" in col_name:
                c.number_format = "0.0"
                c.alignment = Alignment(horizontal="right")
            elif isinstance(val, (int, float)):
                c.number_format = "#,##0"
                c.alignment = Alignment(horizontal="right")
            else:
                c.alignment = Alignment(horizontal="left")
        curr_r2 += 1

    # Auto-width
    for sheet in [ws1, ws2]:
        for col in sheet.columns:
            letter = get_column_letter(col[0].column)
            if col[0].column == 1:
                sheet.column_dimensions[letter].width = 3
                continue
            max_l = max(len(str(cell.value or "")) for cell in col if cell.row >= 4)
            sheet.column_dimensions[letter].width = max(max_l + 4, 12)

    try:
        wb.save(out_path)
    except PermissionError:
        out_path = os.path.join(output_dir, "Strategy_Variants_Comparison_new.xlsx")
        wb.save(out_path)
        
    print(f"\nExcel Comparison report generated: {out_path}")
    return df_portfolio, df_details

if __name__ == "__main__":
    run_all_variants()
