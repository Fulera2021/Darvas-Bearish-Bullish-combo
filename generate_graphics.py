"""
Generate high-resolution visual chart graphics for INFY.NS strategy presentation.
Produces:
1. infy_price_chart.png: Stock price with 20-week bands and trade callouts
2. infy_equity_curve.png: Portfolio equity growth from 40k to 80k+
3. tranche_architecture.png: 4-tranche visual allocation infographic
4. radar_workflow.png: Visual state machine for tracking and exits
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from data_loader import fetch_daily_data, build_weekly_data, add_weekly_signals

def generate_charts():
    os.makedirs("graphics", exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    plt.rcParams["font.sans-serif"] = ["Segoe UI", "DejaVu Sans", "Arial"]
    plt.rcParams["axes.edgecolor"] = "#CBD5E1"
    plt.rcParams["axes.linewidth"] = 0.8

    # 1. Load Data for INFY from 2019 (1 yr warmup) to 2026
    print("Loading data for INFY...")
    df_daily = fetch_daily_data("INFY.NS", "2019-01-01", "2026-10-17")
    df_weekly = build_weekly_data(df_daily)
    df_weekly = add_weekly_signals(df_weekly)
    
    # Filter to 2020-01-01 onwards for plotting
    df_w = df_weekly[df_weekly["Week_End"] >= "2020-01-01"].copy().reset_index(drop=True)

    # -------------------------------------------------------------
    # CHART 1: INFY Price Chart with 20W Bands & Key Strategy Trades
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(13.0, 6.2), dpi=300)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#F8FAFC")

    # Plot Price, 20W High, 20W Low
    ax.plot(df_w["Week_End"], df_w["Close"], color="#0F172A", linewidth=2.2, label="INFY Weekly Close (NSE)", zorder=3)
    ax.plot(df_w["Week_End"], df_w["rolling_20w_high"], color="#10B981", linestyle="--", linewidth=1.6, label="20-Week High (Darvas Ceiling / Bullish Trigger)", alpha=0.9, zorder=2)
    ax.plot(df_w["Week_End"], df_w["rolling_20w_low"], color="#EF4444", linestyle="--", linewidth=1.6, label="20-Week Low (Darvas Floor / Bearish Trigger)", alpha=0.9, zorder=2)
    
    # Fill between bands
    ax.fill_between(df_w["Week_End"], df_w["rolling_20w_low"], df_w["rolling_20w_high"], color="#E2E8F0", alpha=0.35, zorder=1)

    # Highlight Bullish Tranche (Trade #10): July 2020 to April 2022
    t10_buy_date = pd.to_datetime("2020-07-17")
    t10_buy_price = 903.15
    t10_sell_date = pd.to_datetime("2022-04-22")
    t10_sell_price = 1585.45
    
    ax.scatter([t10_buy_date], [t10_buy_price], color="#059669", s=160, marker="^", edgecolors="#064E3B", linewidths=1.5, zorder=6, label="Slot 1 Bullish Buy (17-Jul-2020 @ Rs. 903)")
    ax.scatter([t10_sell_date], [t10_sell_price], color="#D97706", s=160, marker="v", edgecolors="#78350F", linewidths=1.5, zorder=6, label="Slot 1 Bullish Exit (22-Apr-2022 @ Rs. 1,585)")

    # Connect buy and sell with a clean dashed green arc/line
    ax.plot([t10_buy_date, t10_sell_date], [t10_buy_price, t10_sell_price], color="#059669", linestyle=":", linewidth=2.0, alpha=0.75, zorder=4)

    # 1. Bullish Tranche Callout (Placed high in open headroom at y=2080)
    ax.annotate(
        "SLOT 1: BULLISH MACRO COMPOUNDER (Trade #10)\n"
        "- Bought: 17-Jul-2020 @ Rs. 903.15 (Breakout > 20W High)\n"
        "- Sold: 22-Apr-2022 @ Rs. 1,585.45 (20W Low & >=15% p.a.)\n"
        "- Realized Gain: +75.55% (+Rs. 8,187.60 Profit) | Held 644 Days",
        xy=(pd.to_datetime("2021-06-01"), 1450),
        xytext=(pd.to_datetime("2021-01-01"), 2080),
        arrowprops=dict(facecolor="#059669", edgecolor="#065F46", width=1.5, headwidth=7, headlength=7, shrink=0.08),
        fontsize=9.5, fontweight="bold", color="#064E3B",
        bbox=dict(boxstyle="round,pad=0.6", facecolor="#ECFDF5", edgecolor="#10B981", linewidth=1.5, alpha=0.98),
        zorder=7,
        ha="center"
    )

    # 2. COVID Dip Harvester Callout (Placed top-left at y=1520)
    ax.annotate(
        "COVID-19 DIP BOUNCE CYCLE (Mar - Jul 2020)\n"
        "- 6 Bearish Tranches Harvested @ +5% Each\n"
        "- Fast Turnaround: Exited in 5 to 38 Days\n"
        "- Systematically bought pullbacks without panic",
        xy=(pd.to_datetime("2020-04-24"), 658),
        xytext=(pd.to_datetime("2020-05-01"), 1520),
        arrowprops=dict(facecolor="#2563EB", edgecolor="#1E40AF", width=1.5, headwidth=7, headlength=7, shrink=0.08),
        fontsize=9.0, fontweight="bold", color="#1E3A8A",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#EFF6FF", edgecolor="#3B82F6", linewidth=1.5, alpha=0.98),
        zorder=7,
        ha="center"
    )

    # 3. 2022-2023 Tech Pullback Callout (Placed at top right at y=2080)
    ax.annotate(
        "2022-2023 TECH CONSOLIDATION\n"
        "- 8 Dip Tranches Deployed & Exited @ +5%\n"
        "- Independent Slots Averaging Down Safely\n"
        "- Generated continuous cash in a sideways market",
        xy=(pd.to_datetime("2023-03-31"), 1428),
        xytext=(pd.to_datetime("2023-11-01"), 2080),
        arrowprops=dict(facecolor="#D97706", edgecolor="#92400E", width=1.5, headwidth=7, headlength=7, shrink=0.08),
        fontsize=9.0, fontweight="bold", color="#78350F",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#FEF3C7", edgecolor="#F59E0B", linewidth=1.5, alpha=0.98),
        zorder=7,
        ha="center"
    )

    ax.set_title("INFY (Infosys Ltd) 2020-2026: Visualizing the Dual-Engine Backtesting Strategy", fontsize=14, fontweight="bold", pad=14, color="#0F172A")
    ax.set_ylabel("Price on National Stock Exchange (Rs.)", fontsize=11, fontweight="bold", color="#334155")
    ax.set_ylim(350, 2450)
    ax.set_xlim(pd.to_datetime("2019-12-01"), pd.to_datetime("2026-11-01"))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.grid(True, linestyle="--", alpha=0.45, color="#CBD5E1")

    # Legend moved to BOTTOM RIGHT
    legend = ax.legend(
        loc="lower right",
        frameon=True,
        facecolor="#FFFFFF",
        edgecolor="#94A3B8",
        fontsize=9.0,
        framealpha=0.96,
        borderpad=0.8,
        labelspacing=0.6
    )
    legend.get_frame().set_linewidth(1.0)
    legend.set_zorder(10)

    plt.tight_layout()
    chart1_path = "graphics/infy_price_chart.png"
    plt.savefig(chart1_path, dpi=300)
    plt.close()
    print(f"Saved: {chart1_path}")

    # -------------------------------------------------------------
    # CHART 2: Wealth Compounding Curve (Initial 40k to 80k+)
    # -------------------------------------------------------------
    df_m_raw = pd.read_excel("output/Bearish + Bullish Combo/Weekly_Breakout_Combo_INFY.xlsx", sheet_name="Monthly Summary", header=None)
    # Row 4 is header, row 5+ is data
    df_monthly = df_m_raw.iloc[5:].copy().reset_index(drop=True)
    df_monthly = df_monthly.rename(columns={
        1: "Month",
        2: "Trade_Realized",
        6: "Total_Realized",
        7: "Max_Blocked"
    })
    df_monthly["Trade_Realized"] = pd.to_numeric(df_monthly["Trade_Realized"], errors="coerce").fillna(0.0)
    df_monthly["Total_Realized"] = pd.to_numeric(df_monthly["Total_Realized"], errors="coerce").fillna(0.0)
    
    df_monthly = df_monthly[df_monthly["Month"].str.match(r"^\d{4}-[A-Za-z]{3}$", na=False)].copy()
    df_monthly["cum_realized"] = df_monthly["Total_Realized"].cumsum()
    df_monthly["cash_cum_realized"] = 40000.0 + df_monthly["cum_realized"]

    fig, ax = plt.subplots(figsize=(10, 5), dpi=300)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#F8FAFC")

    dates = pd.to_datetime(df_monthly["Month"], format="%Y-%b")
    
    # Baseline 40,000
    ax.axhline(40000, color="#94A3B8", linestyle=":", linewidth=1.5, label="Initial Capital (Rs. 40,000)")
    
    # Cumulative Realized Cash Profit
    ax.plot(dates, df_monthly["cash_cum_realized"], color="#10B981", linewidth=2.8, label="Total Realized Capital (Principal + Profits)", zorder=3)
    ax.fill_between(dates, 40000, df_monthly["cash_cum_realized"], color="#ECFDF5", alpha=0.6)

    # End point annotation
    final_cash = df_monthly["cash_cum_realized"].iloc[-1]
    final_dt = dates.iloc[-1]
    ax.scatter([final_dt], [final_cash], color="#059669", s=110, zorder=5)
    ax.annotate(
        f"Final Realized Capital: Rs. {final_cash:,.0f}\n(+Rs. 40,724 Realized Profit / +101.8% Gain!)\n100% Win Rate on 33 Closed Trades",
        xy=(final_dt, final_cash),
        xytext=(pd.to_datetime("2023-06-01"), final_cash - 9000),
        arrowprops=dict(facecolor="#059669", edgecolor="#059669", width=1.5, headwidth=7),
        fontsize=9.5, fontweight="bold", color="#065F46",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#ECFDF5", edgecolor="#10B981")
    )

    ax.set_title("Capital Growth: Rs. 40,000 Multiplied to Rs. 80,724 in Cash Profits (INFY 2020-2026)", fontsize=13, fontweight="bold", pad=12, color="#0F172A")
    ax.set_ylabel("Portfolio Capital in Indian Rupees (Rs.)", fontsize=10.5, fontweight="bold", color="#334155")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper left", frameon=True, facecolor="#FFFFFF", edgecolor="#CBD5E1", fontsize=9.5)

    plt.tight_layout()
    chart2_path = "graphics/infy_equity_curve.png"
    plt.savefig(chart2_path, dpi=300)
    plt.close()
    print(f"Saved: {chart2_path}")

    # -------------------------------------------------------------
    # CHART 3: 4-Tranche Architecture Visual Graphic
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(10, 4.2), dpi=300)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FFFFFF")
    ax.axis("off")

    # Draw 4 visual tranche cards as a custom diagram
    boxes = [
        ("TRANCHE 1 (SLOT 1)", "BULLISH TREND", "Base: Rs. 10,000", "• Rides 20W High Breakouts\n• Uncapped Compounding\n• Sold only on 20W Low &\n  Annual Return >= 15%", "#059669", "#ECFDF5"),
        ("TRANCHE 2 (SLOT 2)", "BEARISH DIP 1", "Base: Rs. 10,000", "• Weekly Swing Breakout\n• Strict +5.0% Profit Exit\n• Immediate Slot Recycling\n• Average 20-45 day hold", "#2563EB", "#EFF6FF"),
        ("TRANCHE 3 (SLOT 3)", "BEARISH DIP 2", "Base: Rs. 10,000", "• Subsequent Weekly Bounce\n• Strict +5.0% Profit Exit\n• Independent Position\n• Systematic Averaging", "#2563EB", "#EFF6FF"),
        ("TRANCHE 4 (SLOT 4)", "BEARISH DIP 3", "Base: Rs. 10,000", "• Deep Correction Harvester\n• Strict +5.0% Profit Exit\n• Maximum Safety Reserve\n• Never Margin, Pure Cash", "#2563EB", "#EFF6FF"),
    ]

    for idx, (title, mode, cap, details, col, bg) in enumerate(boxes):
        x = 0.03 + idx * 0.245
        rect = plt.Rectangle((x, 0.1), 0.22, 0.8, facecolor=bg, edgecolor=col, linewidth=2, transform=ax.transAxes)
        ax.add_patch(rect)
        
        ax.text(x + 0.11, 0.83, title, fontsize=9.5, fontweight="bold", color=col, ha="center", transform=ax.transAxes)
        ax.text(x + 0.11, 0.74, mode, fontsize=11, fontweight="bold", color="#0F172A", ha="center", transform=ax.transAxes)
        ax.text(x + 0.11, 0.65, cap, fontsize=10.5, fontweight="bold", color="#1E3A8A", ha="center", transform=ax.transAxes)
        ax.plot([x + 0.02, x + 0.20], [0.60, 0.60], color=col, linewidth=1, transform=ax.transAxes)
        ax.text(x + 0.02, 0.54, details, fontsize=8.5, color="#334155", va="top", transform=ax.transAxes, linespacing=1.4)

    plt.title("TOTAL CAPITAL: Rs. 40,000 EQUALLY DIVIDED INTO 4 INDEPENDENT SLOTS", fontsize=12, fontweight="bold", color="#0F172A", pad=10)
    plt.tight_layout()
    chart3_path = "graphics/tranche_architecture.png"
    plt.savefig(chart3_path, dpi=300)
    plt.close()
    print(f"Saved: {chart3_path}")

    # -------------------------------------------------------------
    # CHART 4: Visual Radar State Diagram
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(10, 4.2), dpi=300)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FFFFFF")
    ax.axis("off")

    stages = [
        ("1. IDLE STATE", "Stock within 20W Range\n100% Cash Buffer Safe\nZero Market Risk", "#64748B", "#F1F5F9"),
        ("2. BEARISH RADAR", "Friday Close < 20W Low\nCorrection Confirmed\nDip-Buying System ON", "#D97706", "#FEF3C7"),
        ("3. DIP ENTRY", "Close > Prev Week High\nTranche filled @ +0.5% limit\nMax 1 Tranche Per Week", "#2563EB", "#EFF6FF"),
        ("4. 5% TARGET EXIT", "High >= Buy Price * 1.05\nLocked +5% Realized Profit\nSlot Recycled Immediately", "#059669", "#ECFDF5"),
    ]

    for idx, (title, details, col, bg) in enumerate(stages):
        x = 0.03 + idx * 0.245
        rect = plt.Rectangle((x, 0.15), 0.22, 0.7, facecolor=bg, edgecolor=col, linewidth=2, transform=ax.transAxes)
        ax.add_patch(rect)
        
        ax.text(x + 0.11, 0.77, title, fontsize=10, fontweight="bold", color=col, ha="center", transform=ax.transAxes)
        ax.plot([x + 0.02, x + 0.20], [0.70, 0.70], color=col, linewidth=1, transform=ax.transAxes)
        ax.text(x + 0.02, 0.63, details, fontsize=8.5, color="#1E293B", va="top", transform=ax.transAxes, linespacing=1.5)
        
        if idx < 3:
            # Draw connector arrow
            ax.annotate("", xy=(x + 0.24, 0.5), xytext=(x + 0.225, 0.5),
                        arrowprops=dict(facecolor="#94A3B8", edgecolor="#94A3B8", width=1.5, headwidth=6),
                        transform=ax.transAxes)

    plt.title("HOW A DIP-HARVESTER TRANCHE CYCLES FROM RADAR TO RECYCLED CASH", fontsize=12, fontweight="bold", color="#0F172A", pad=10)
    plt.tight_layout()
    chart4_path = "graphics/radar_workflow.png"
    plt.savefig(chart4_path, dpi=300)
    plt.close()
    print(f"Saved: {chart4_path}")

if __name__ == "__main__":
    generate_charts()
