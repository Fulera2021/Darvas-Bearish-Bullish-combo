"""
Generate Full HD (1920x1080) colourful presentation graphic comparing:
'WITH CAR Filter (10d Rising)' vs 'WITHOUT CAR Filter (Baseline)'
Based on the Nifty 50 Darvas Strategy backtest data (Win Rate % removed).
Saves output to: graphics/CAR vs No CAR.png
"""

import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch
import numpy as np

def create_graphic():
    os.makedirs("graphics", exist_ok=True)
    out_path = os.path.join("graphics", "CAR vs No CAR.png")
    
    # 1920 x 1080 at 100 dpi gives exactly 1920x1080 pixels
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1920)
    ax.set_ylim(0, 1080)
    ax.axis("off")
    
    # -------------------------------------------------------------
    # 1. BACKGROUND WITH MODERN DARK THEME GRADIENT & GLOW
    # -------------------------------------------------------------
    # Deep midnight slate base
    fig.patch.set_facecolor("#080D1A")
    ax.set_facecolor("#080D1A")
    
    # Subtle radial/linear ambient glow in the background
    y_vals = np.linspace(0, 1080, 200)
    for i in range(len(y_vals) - 1):
        ratio = y_vals[i] / 1080.0
        # Dark rich navy to deep charcoal gradient
        r = int(9 + 8 * (1 - ratio))
        g = int(14 + 12 * (1 - ratio))
        b = int(28 + 22 * (1 - ratio))
        hex_col = f"#{r:02x}{g:02x}{b:02x}"
        ax.axhspan(y_vals[i], y_vals[i+1], color=hex_col, zorder=0)

    # Ambient glow patches
    glow1 = patches.Circle((250, 950), 380, color="#0EA5E9", alpha=0.06, zorder=1)
    glow2 = patches.Circle((1650, 920), 400, color="#8B5CF6", alpha=0.05, zorder=1)
    glow3 = patches.Circle((960, 200), 450, color="#10B981", alpha=0.04, zorder=1)
    ax.add_patch(glow1)
    ax.add_patch(glow2)
    ax.add_patch(glow3)

    # -------------------------------------------------------------
    # 2. HEADER SECTION
    # -------------------------------------------------------------
    # Top badge pill
    tag_bg = FancyBboxPatch(
        (80, 1000), 420, 36,
        boxstyle="round,pad=0,rounding_size=18",
        facecolor="#0F2942", edgecolor="#0284C7", linewidth=1.5, zorder=2
    )
    ax.add_patch(tag_bg)
    ax.text(
        290, 1018, "DARVAS BOX SYSTEM  •  NIFTY 50 UNIVERSE (2020 – 2026)",
        color="#38BDF8", fontsize=11, fontweight="bold",
        fontfamily="Segoe UI", ha="center", va="center", zorder=3
    )

    # Title
    ax.text(
        80, 955, "CAR vs No CAR: Executive Profit Comparison",
        color="#F8FAFC", fontsize=32, fontweight="bold",
        fontfamily="Segoe UI", ha="left", va="center", zorder=3
    )
    
    # Subtitle with description
    ax.text(
        80, 915, "Why Baseline (No CAR) is the Decisive Winner: Nearly 2x Net Profit Easily Absorbs Unrealized Drawdown",
        color="#94A3B8", fontsize=14, fontweight="normal",
        fontfamily="Segoe UI", ha="left", va="center", zorder=3
    )

    # Winner Crown Badge on Top Right
    winner_bg = FancyBboxPatch(
        (1480, 930), 360, 56,
        boxstyle="round,pad=0,rounding_size=14",
        facecolor="#78350F", edgecolor="#F59E0B", linewidth=2.0, zorder=2
    )
    ax.add_patch(winner_bg)
    ax.text(
        1660, 958, "PROFIT WINNER: BASELINE (NO CAR)",
        color="#FDE68A", fontsize=13, fontweight="bold",
        fontfamily="Segoe UI", ha="center", va="center", zorder=3
    )

    # -------------------------------------------------------------
    # 3. TOP 3 CONDENSED SUMMARY CARDS
    # -------------------------------------------------------------
    kpis = [
        {
            "x": 80, "w": 550, "h": 96, "y": 795,
            "border": "#F59E0B", "bg": "#2A1705", "glow": "#FBBF24",
            "tag": "TOTAL NET PROFIT (CASH + OPEN)", "value": "+₹14.78 Lakhs Extra (+92%)",
            "desc": "Baseline ₹30.89L (+61.8%) vs CAR ₹16.11L (+32.2%)"
        },
        {
            "x": 685, "w": 550, "h": 96, "y": 795,
            "border": "#10B981", "bg": "#062E20", "glow": "#34D399",
            "tag": "REALIZED BANKED PROFIT", "value": "+₹18.51 Lakhs Extra Cash",
            "desc": "Baseline ₹33.93L in bank easily dwarfs the -₹3.04L open dip"
        },
        {
            "x": 1290, "w": 550, "h": 96, "y": 795,
            "border": "#38BDF8", "bg": "#0B253F", "glow": "#7DD3FC",
            "tag": "DIP HARVESTING POWER", "value": "1,091 vs 117 Dip Wins",
            "desc": "No CAR systematically harvested repetitive +5% profit bounces"
        }
    ]

    for k in kpis:
        card = FancyBboxPatch(
            (k["x"], k["y"]), k["w"], k["h"],
            boxstyle="round,pad=0,rounding_size=16",
            facecolor=k["bg"], edgecolor=k["border"], linewidth=1.8, zorder=2
        )
        ax.add_patch(card)
        
        ax.text(
            k["x"] + 24, k["y"] + 70, k["tag"],
            color=k["glow"], fontsize=11, fontweight="bold",
            fontfamily="Segoe UI", ha="left", va="center", zorder=3
        )
        ax.text(
            k["x"] + 24, k["y"] + 42, k["value"],
            color="#FFFFFF", fontsize=22, fontweight="bold",
            fontfamily="Segoe UI", ha="left", va="center", zorder=3
        )
        ax.text(
            k["x"] + 24, k["y"] + 18, k["desc"],
            color="#CBD5E1", fontsize=11.5, fontweight="normal",
            fontfamily="Segoe UI", ha="left", va="center", zorder=3
        )

    # -------------------------------------------------------------
    # 4. CONDENSED COMPARISON TABLE CONTAINER
    # -------------------------------------------------------------
    tbl_x, tbl_y, tbl_w, tbl_h = 80, 150, 1760, 615
    
    tbl_card = FancyBboxPatch(
        (tbl_x, tbl_y), tbl_w, tbl_h,
        boxstyle="round,pad=0,rounding_size=20",
        facecolor="#0D1527", edgecolor="#1E293B", linewidth=2.0, zorder=2
    )
    ax.add_patch(tbl_card)

    col_c1 = 130
    col_c2 = 800
    col_c3 = 1200
    col_c4 = 1600

    # Header Row
    hdr_h = 68
    hdr_y = tbl_y + tbl_h - hdr_h - 12
    hdr_bg = FancyBboxPatch(
        (tbl_x + 12, hdr_y), tbl_w - 24, hdr_h,
        boxstyle="round,pad=0,rounding_size=14",
        facecolor="#131E36", edgecolor="#223354", linewidth=1.2, zorder=3
    )
    ax.add_patch(hdr_bg)

    ax.text(col_c1, hdr_y + 34, "Key Performance Indicator", color="#94A3B8", fontsize=15, fontweight="bold", fontfamily="Segoe UI", ha="left", va="center", zorder=4)
    
    # Header WITH CAR
    car_pill = FancyBboxPatch(
        (col_c2 - 165, hdr_y + 14), 330, 42,
        boxstyle="round,pad=0,rounding_size=10",
        facecolor="#064E3B", edgecolor="#10B981", linewidth=1.5, zorder=4
    )
    ax.add_patch(car_pill)
    ax.text(col_c2, hdr_y + 35, "WITH CAR Filter", color="#A7F3D0", fontsize=14, fontweight="bold", fontfamily="Segoe UI", ha="center", va="center", zorder=5)

    # Header WITHOUT CAR (WINNER HIGHLIGHT)
    base_pill = FancyBboxPatch(
        (col_c3 - 175, hdr_y + 12), 350, 46,
        boxstyle="round,pad=0,rounding_size=10",
        facecolor="#78350F", edgecolor="#F59E0B", linewidth=2.2, zorder=4
    )
    ax.add_patch(base_pill)
    ax.text(col_c3, hdr_y + 35, "WITHOUT CAR (Baseline) [WINNER]", color="#FEF08A", fontsize=14, fontweight="bold", fontfamily="Segoe UI", ha="center", va="center", zorder=5)

    # Header Difference / Impact
    diff_pill = FancyBboxPatch(
        (col_c4 - 150, hdr_y + 14), 300, 42,
        boxstyle="round,pad=0,rounding_size=10",
        facecolor="#2E1065", edgecolor="#8B5CF6", linewidth=1.5, zorder=4
    )
    ax.add_patch(diff_pill)
    ax.text(col_c4, hdr_y + 35, "Baseline Advantage", color="#DDD6FE", fontsize=14, fontweight="bold", fontfamily="Segoe UI", ha="center", va="center", zorder=5)

    # -------------------------------------------------------------
    # 5. CONDENSED DATA ROWS (Simplified to 6 Core Essential Rows)
    # -------------------------------------------------------------
    condensed_rows = [
        {
            "metric": "1. Total Net Profit (Realized + Open)",
            "sub": "The true bottom line after all losses & open equity",
            "car": "₹16,11,302  (+32.2%)",
            "car_col": "#94A3B8",
            "base": "₹30,89,095  (+61.8%)",
            "base_col": "#FBBF24",
            "diff": "+₹14.78 Lakhs (+92% Higher)",
            "style": "gold_badge"
        },
        {
            "metric": "2. Banked Realized Profit",
            "sub": "Actual booked cash profits transferred to wallet",
            "car": "₹15,41,838",
            "car_col": "#94A3B8",
            "base": "₹33,92,960",
            "base_col": "#34D399",
            "diff": "+₹18.51 Lakhs (+120% More Cash)",
            "style": "green_badge"
        },
        {
            "metric": "3. End-Date Open Unrealized P&L",
            "sub": "Temporary mark-to-market floating position on 14-Oct-2026",
            "car": "+₹69,464  (Floating profit)",
            "car_col": "#34D399",
            "base": "-₹3,03,865  (Temporary dip)",
            "base_col": "#F87171",
            "diff": "Easily offset by +₹18.51L Cash",
            "style": "purple_badge"
        },
        {
            "metric": "4. Bearish Dip-Harvesting Wins",
            "sub": "Number of +5% dip bounces successfully captured",
            "car": "117  trades",
            "car_col": "#94A3B8",
            "base": "1,091  trades",
            "base_col": "#38BDF8",
            "diff": "974 Extra 5% Profit Pulses",
            "style": "cyan_badge"
        },
        {
            "metric": "5. Macro Bullish Tranches",
            "sub": "Long-term compounder breakouts (>20W High)",
            "car": "83  trades",
            "car_col": "#94A3B8",
            "base": "111  trades",
            "base_col": "#F8FAFC",
            "diff": "+28 Additional Trends",
            "style": "neutral_badge"
        },
        {
            "metric": "6. Average Maximum Drawdown",
            "sub": "Portfolio peak-to-trough temporary decline",
            "car": "13.32%",
            "car_col": "#34D399",
            "base": "20.48%",
            "base_col": "#CBD5E1",
            "diff": "+7.16% Drawdown for 2x Profit",
            "style": "amber_text"
        }
    ]

    row_h = 76
    start_y = hdr_y - 8

    for i, r in enumerate(condensed_rows):
        curr_y = start_y - (i + 1) * row_h
        
        # Subtle zebra striping
        if i % 2 == 0:
            row_bg = FancyBboxPatch(
                (tbl_x + 12, curr_y + 4), tbl_w - 24, row_h - 8,
                boxstyle="round,pad=0,rounding_size=10",
                facecolor="#111B30", edgecolor="none", zorder=3
            )
            ax.add_patch(row_bg)
            
        if i == 0:  # Highlight row 1 (Net Profit)
            net_hl = FancyBboxPatch(
                (tbl_x + 12, curr_y + 4), tbl_w - 24, row_h - 8,
                boxstyle="round,pad=0,rounding_size=10",
                facecolor="#2A1B07", edgecolor="#F59E0B", linewidth=1.5, zorder=3
            )
            ax.add_patch(net_hl)

        # 1. Metric Column (Title + Subtext)
        ax.text(
            col_c1, curr_y + 45, r["metric"],
            color="#FFFFFF" if i == 0 else "#F1F5F9", fontsize=14,
            fontweight="bold", fontfamily="Segoe UI", ha="left", va="center", zorder=4
        )
        ax.text(
            col_c1, curr_y + 22, r["sub"],
            color="#64748B", fontsize=11,
            fontweight="normal", fontfamily="Segoe UI", ha="left", va="center", zorder=4
        )

        # 2. WITH CAR Column
        ax.text(
            col_c2, curr_y + 36, r["car"],
            color=r["car_col"], fontsize=15, fontweight="bold",
            fontfamily="Segoe UI", ha="center", va="center", zorder=4
        )

        # 3. WITHOUT CAR Column (Larger, prominent)
        ax.text(
            col_c3, curr_y + 36, r["base"],
            color=r["base_col"], fontsize=16 if i < 2 else 15, fontweight="bold",
            fontfamily="Segoe UI", ha="center", va="center", zorder=4
        )

        # 4. Difference / Impact Badge
        st = r["style"]
        dt = r["diff"]
        
        if st == "gold_badge":
            pill_w = 280
            pill = FancyBboxPatch(
                (col_c4 - pill_w/2, curr_y + 18), pill_w, 38,
                boxstyle="round,pad=0,rounding_size=10",
                facecolor="#78350F", edgecolor="#F59E0B", linewidth=1.5, zorder=4
            )
            ax.add_patch(pill)
            ax.text(col_c4, curr_y + 37, dt, color="#FEF08A", fontsize=13.5, fontweight="bold", fontfamily="Segoe UI", ha="center", va="center", zorder=5)
            
        elif st == "green_badge":
            pill_w = 280
            pill = FancyBboxPatch(
                (col_c4 - pill_w/2, curr_y + 18), pill_w, 38,
                boxstyle="round,pad=0,rounding_size=10",
                facecolor="#064E3B", edgecolor="#10B981", linewidth=1.5, zorder=4
            )
            ax.add_patch(pill)
            ax.text(col_c4, curr_y + 37, dt, color="#6EE7B7", fontsize=13, fontweight="bold", fontfamily="Segoe UI", ha="center", va="center", zorder=5)
            
        elif st == "purple_badge":
            pill_w = 290
            pill = FancyBboxPatch(
                (col_c4 - pill_w/2, curr_y + 18), pill_w, 38,
                boxstyle="round,pad=0,rounding_size=10",
                facecolor="#3B0764", edgecolor="#A855F7", linewidth=1.2, zorder=4
            )
            ax.add_patch(pill)
            ax.text(col_c4, curr_y + 37, dt, color="#E9D5FF", fontsize=12.5, fontweight="bold", fontfamily="Segoe UI", ha="center", va="center", zorder=5)
            
        elif st == "cyan_badge":
            pill_w = 260
            pill = FancyBboxPatch(
                (col_c4 - pill_w/2, curr_y + 18), pill_w, 38,
                boxstyle="round,pad=0,rounding_size=10",
                facecolor="#0C4A6E", edgecolor="#0284C7", linewidth=1.2, zorder=4
            )
            ax.add_patch(pill)
            ax.text(col_c4, curr_y + 37, dt, color="#7DD3FC", fontsize=13, fontweight="bold", fontfamily="Segoe UI", ha="center", va="center", zorder=5)
            
        elif st == "neutral_badge":
            pill_w = 240
            pill = FancyBboxPatch(
                (col_c4 - pill_w/2, curr_y + 18), pill_w, 38,
                boxstyle="round,pad=0,rounding_size=10",
                facecolor="#1E293B", edgecolor="#475569", linewidth=1.0, zorder=4
            )
            ax.add_patch(pill)
            ax.text(col_c4, curr_y + 37, dt, color="#CBD5E1", fontsize=12.5, fontweight="600", fontfamily="Segoe UI", ha="center", va="center", zorder=5)
            
        else:
            ax.text(col_c4, curr_y + 36, dt, color="#F59E0B", fontsize=13, fontweight="600", fontfamily="Segoe UI", ha="center", va="center", zorder=4)

    # -------------------------------------------------------------
    # 6. BOTTOM TAKEAWAY: CLEAR VERDICT
    # -------------------------------------------------------------
    ftr_x, ftr_y, ftr_w, ftr_h = 80, 30, 1760, 95
    ftr_bg = FancyBboxPatch(
        (ftr_x, ftr_y), ftr_w, ftr_h,
        boxstyle="round,pad=0,rounding_size=16",
        facecolor="#111B30", edgecolor="#334155", linewidth=1.5, zorder=2
    )
    ax.add_patch(ftr_bg)

    ax.text(
        ftr_x + 30, ftr_y + 64, "FINAL STRATEGY VERDICT: WHY NO CAR (BASELINE) WINS HANDS DOWN",
        color="#FDE047", fontsize=12.5, fontweight="bold", fontfamily="Segoe UI", ha="left", va="center", zorder=3
    )
    
    verdict_text = (
        "• Cash is King: Baseline banked Rs. 33.93 Lakhs in realized cash vs Rs. 15.42 Lakhs (+Rs. 18.51 Lakhs extra).\n"
        "• Unrealized Dip is Negligible: The Rs. 3.04 Lakhs floating dip on the end date is just a 9% friction against the massive Rs. 33.93 Lakhs profit cushion.\n"
        "• CAR Filter Was Too Restrictive: Requiring 10 continuous rising days killed 974 profitable 5% dip-bounces, sacrificing almost HALF the total profit."
    )
    ax.text(
        ftr_x + 30, ftr_y + 26, verdict_text,
        color="#E2E8F0", fontsize=11, fontweight="normal", fontfamily="Segoe UI", ha="left", va="center", zorder=3, linespacing=1.4
    )

    # -------------------------------------------------------------
    # 7. SAVE TO FILE WITH EXACT 1920x1080 RESOLUTION
    # -------------------------------------------------------------
    plt.savefig(out_path, dpi=100, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close()
    print(f"FHD graphic successfully saved to: {out_path}")

if __name__ == "__main__":
    create_graphic()
