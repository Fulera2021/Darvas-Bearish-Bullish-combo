"""
Generate 4 high-converting YouTube Thumbnail iterations (1920x1080 Full HD)
for the Darvas Bearish + Bullish Combo Strategy, featuring the user's cutout photo.
Fixes all glyph warnings, pill padding, and text overlaps.
"""

import os
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, Polygon
import matplotlib.patheffects as pe

USER_PHOTO_PATH = r"C:/Users/krish/.gemini/antigravity/brain/478e326f-f240-466b-ad74-af41bc53a865/.user_uploaded/media_1793605619889_b98f8ee2.png"
ARTIFACT_DIR = r"C:/Users/krish/.gemini/antigravity/brain/478e326f-f240-466b-ad74-af41bc53a865"
WORKSPACE_OUT_DIR = os.path.join(os.getcwd(), "graphics", "thumbnails")

os.makedirs(ARTIFACT_DIR, exist_ok=True)
os.makedirs(WORKSPACE_OUT_DIR, exist_ok=True)


def load_and_style_user_photo(outline_color=(255, 255, 255, 255), outline_size=7, glow_color=(56, 189, 248, 160), glow_radius=18):
    """
    Loads the user's transparent PNG cutout, crops excess horizontal whitespace,
    boosts contrast/sharpness for YouTube thumbnail pop, and adds a crisp outline + glow.
    """
    img = Image.open(USER_PHOTO_PATH).convert("RGBA")
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)

    new_w = int(img.width * 2.2)
    new_h = int(img.height * 2.2)
    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    rgb = img.convert("RGB")
    alpha = img.split()[3]
    rgb = ImageEnhance.Contrast(rgb).enhance(1.12)
    rgb = ImageEnhance.Color(rgb).enhance(1.10)
    rgb = ImageEnhance.Sharpness(rgb).enhance(1.35)
    img = Image.merge("RGBA", (*rgb.split(), alpha))

    pad = glow_radius * 2 + outline_size + 10
    canvas = Image.new("RGBA", (new_w + 2 * pad, new_h + 2 * pad), (0, 0, 0, 0))

    if glow_radius > 0:
        glow_mask = alpha.filter(ImageFilter.MaxFilter(outline_size * 2 + 1))
        glow_mask = glow_mask.filter(ImageFilter.GaussianBlur(glow_radius))
        glow_layer = Image.new("RGBA", img.size, glow_color)
        glow_alpha = glow_mask.point(lambda p: int(p * (glow_color[3] / 255.0)))
        glow_layer.putalpha(glow_alpha)
        canvas.paste(glow_layer, (pad, pad), glow_layer)

    if outline_size > 0:
        stroke_mask = alpha.filter(ImageFilter.MaxFilter(outline_size * 2 + 1))
        stroke_mask = stroke_mask.filter(ImageFilter.GaussianBlur(1.2))
        stroke_layer = Image.new("RGBA", img.size, outline_color)
        stroke_layer.putalpha(stroke_mask)
        canvas.paste(stroke_layer, (pad, pad), stroke_layer)

    canvas.paste(img, (pad, pad), img)
    return canvas


def draw_candlesticks(ax, x_start, x_end, y_base, y_amp, n_candles=16, trend="down", color_up="#10B981", color_down="#EF4444", alpha=0.35, zorder=1):
    xs = np.linspace(x_start, x_end, n_candles)
    w = (x_end - x_start) / (n_candles * 1.65)
    np.random.seed(42 if trend == "down" else 99)

    prices = [y_base]
    for i in range(1, n_candles):
        if trend == "down":
            step = -y_amp / n_candles + np.sin(i * 0.9) * (y_amp * 0.14)
        else:
            step = +y_amp / n_candles + np.sin(i * 0.7) * (y_amp * 0.08)
        prices.append(prices[-1] + step)

    for i, x in enumerate(xs):
        open_p = prices[i]
        if trend == "down":
            is_green = (i % 3 == 2)
            delta = (y_amp * 0.11) if is_green else -(y_amp * 0.13)
        else:
            is_green = (i % 4 != 1)
            delta = (y_amp * 0.14) if is_green else -(y_amp * 0.07)

        close_p = open_p + delta
        high_p = max(open_p, close_p) + abs(delta) * 0.45
        low_p = min(open_p, close_p) - abs(delta) * 0.45
        col = color_up if close_p >= open_p else color_down

        ax.plot([x, x], [low_p, high_p], color=col, linewidth=2.2, alpha=alpha, zorder=zorder)
        body_y = min(open_p, close_p)
        body_h = max(abs(close_p - open_p), 6)
        rect = FancyBboxPatch(
            (x - w / 2, body_y), w, body_h,
            boxstyle="round,pad=0,rounding_size=2",
            facecolor=col, edgecolor=col, linewidth=1, alpha=alpha, zorder=zorder
        )
        ax.add_patch(rect)


def save_both(fig, filename):
    p1 = os.path.join(ARTIFACT_DIR, filename)
    p2 = os.path.join(WORKSPACE_OUT_DIR, filename)
    fig.savefig(p1, dpi=100, facecolor=fig.get_facecolor(), edgecolor="none")
    fig.savefig(p2, dpi=100, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    print(f"Saved: {filename}")


# ==============================================================================
# ITERATION 1: "The Dual Engine Balance" (Split Red Bear vs Green Bull)
# ==============================================================================
def make_iteration_1():
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1920)
    ax.set_ylim(0, 1080)
    ax.axis("off")
    fig.patch.set_facecolor("#070B14")

    # Split background: Left Deep Crimson-Navy, Right Deep Emerald-Navy
    left_poly = Polygon([[0, 0], [990, 0], [930, 1080], [0, 1080]], closed=True, facecolor="#1A0912", edgecolor="none", zorder=0)
    right_poly = Polygon([[990, 0], [1920, 0], [1920, 1080], [930, 1080]], closed=True, facecolor="#061A17", edgecolor="none", zorder=0)
    ax.add_patch(left_poly)
    ax.add_patch(right_poly)

    # Ambient glows
    ax.add_patch(patches.Circle((340, 520), 480, color="#EF4444", alpha=0.14, zorder=1))
    ax.add_patch(patches.Circle((1580, 520), 480, color="#10B981", alpha=0.15, zorder=1))
    ax.add_patch(patches.Circle((960, 350), 420, color="#38BDF8", alpha=0.12, zorder=1))

    # Center split line
    ax.plot([990, 930], [0, 1080], color="#FBBF24", linewidth=3.5, alpha=0.6, zorder=2)

    # Background candlesticks
    draw_candlesticks(ax, 60, 780, 620, 260, n_candles=14, trend="down", alpha=0.32, zorder=1)
    draw_candlesticks(ax, 1140, 1860, 340, 310, n_candles=14, trend="up", alpha=0.32, zorder=1)

    # Darvas Box overlay on Left & Right
    darvas_l = FancyBboxPatch((80, 420), 660, 190, boxstyle="round,pad=0,rounding_size=8",
                              facecolor="#EF4444", alpha=0.08, edgecolor="#F87171", linewidth=2, linestyle="--", zorder=1)
    darvas_r = FancyBboxPatch((1180, 430), 660, 220, boxstyle="round,pad=0,rounding_size=8",
                              facecolor="#10B981", alpha=0.08, edgecolor="#34D399", linewidth=2, linestyle="--", zorder=1)
    ax.add_patch(darvas_l)
    ax.add_patch(darvas_r)

    # TOP HEADER BANNER (Extra wide padding)
    top_pill = FancyBboxPatch((440, 962), 1040, 78, boxstyle="round,pad=0,rounding_size=22",
                              facecolor="#0F172A", edgecolor="#F59E0B", linewidth=3.0, zorder=5)
    ax.add_patch(top_pill)
    ax.text(960, 1001, "2-IN-1 SYSTEMATIC DARVAS STRATEGY", color="#FDE047", fontsize=30, fontweight="black",
            fontfamily="Segoe UI", ha="center", va="center", zorder=6,
            path_effects=[pe.withStroke(linewidth=4, foreground="#000000")])

    # MAIN HUGE HEADLINE
    t1 = ax.text(960, 862, "WIN IN BOTH MARKETS!", color="#FFFFFF", fontsize=68, fontweight="black",
                 fontfamily="Segoe UI", ha="center", va="center", zorder=6)
    t1.set_path_effects([pe.withStroke(linewidth=10, foreground="#000000")])

    # User Cutout in Center
    user_img = load_and_style_user_photo(outline_color=(255, 255, 255, 255), outline_size=7, glow_color=(250, 204, 21, 140), glow_radius=20)
    ax.imshow(user_img, extent=[250, 1670, -25, 675], aspect="auto", zorder=8)

    # LEFT FLOATING CARD (Above Left Palm)
    l_card = FancyBboxPatch((55, 455), 575, 290, boxstyle="round,pad=0,rounding_size=24",
                            facecolor="#280911", edgecolor="#F43F5E", linewidth=4.0, zorder=9)
    ax.add_patch(l_card)

    l_badge = FancyBboxPatch((85, 675), 515, 46, boxstyle="round,pad=0,rounding_size=12",
                             facecolor="#881337", edgecolor="#FB7185", linewidth=1.5, zorder=10)
    ax.add_patch(l_badge)
    ax.text(342, 698, "ENGINE 1: BEARISH DIP HARVESTER", color="#FFE4E6", fontsize=17, fontweight="bold",
            fontfamily="Segoe UI", ha="center", va="center", zorder=11)

    t_l1 = ax.text(342, 605, "BUY THE DIPS", color="#FFFFFF", fontsize=42, fontweight="black",
                   fontfamily="Segoe UI", ha="center", va="center", zorder=11)
    t_l1.set_path_effects([pe.withStroke(linewidth=6, foreground="#000000")])

    ax.text(342, 535, "+5% TARGET PER TRANCHE", color="#FDA4AF", fontsize=23, fontweight="bold",
            fontfamily="Segoe UI", ha="center", va="center", zorder=11)
    ax.text(342, 485, "• 1,091 Profitable Bounces!", color="#FDE047", fontsize=20, fontweight="bold",
            fontfamily="Segoe UI", ha="center", va="center", zorder=11)

    ax.annotate("", xy=(380, 365), xytext=(342, 450),
                arrowprops=dict(facecolor="#F43F5E", edgecolor="#FFE4E6", width=8, headwidth=24, headlength=18), zorder=10)

    # RIGHT FLOATING CARD (Above Right Palm)
    r_card = FancyBboxPatch((1290, 455), 575, 290, boxstyle="round,pad=0,rounding_size=24",
                            facecolor="#05261C", edgecolor="#10B981", linewidth=4.0, zorder=9)
    ax.add_patch(r_card)

    r_badge = FancyBboxPatch((1320, 675), 515, 46, boxstyle="round,pad=0,rounding_size=12",
                             facecolor="#065F46", edgecolor="#34D399", linewidth=1.5, zorder=10)
    ax.add_patch(r_badge)
    ax.text(1577, 698, "ENGINE 2: BULLISH TREND RIDER", color="#D1FAE5", fontsize=17, fontweight="bold",
            fontfamily="Segoe UI", ha="center", va="center", zorder=11)

    t_r1 = ax.text(1577, 605, "RIDE BREAKOUTS", color="#FFFFFF", fontsize=39, fontweight="black",
                   fontfamily="Segoe UI", ha="center", va="center", zorder=11)
    t_r1.set_path_effects([pe.withStroke(linewidth=6, foreground="#000000")])

    ax.text(1577, 535, "UNCAPPED MACRO GAINS", color="#6EE7B7", fontsize=23, fontweight="bold",
            fontfamily="Segoe UI", ha="center", va="center", zorder=11)
    ax.text(1577, 485, "• 20-Week High Breakout!", color="#FDE047", fontsize=20, fontweight="bold",
            fontfamily="Segoe UI", ha="center", va="center", zorder=11)

    ax.annotate("", xy=(1520, 315), xytext=(1577, 450),
                arrowprops=dict(facecolor="#10B981", edgecolor="#D1FAE5", width=8, headwidth=24, headlength=18), zorder=10)

    # BOTTOM KPI RIBBON OVERLAY (Generous width so text fits inside cleanly)
    bot_card = FancyBboxPatch((330, 26), 1260, 88, boxstyle="round,pad=0,rounding_size=20",
                              facecolor="#090D16", edgecolor="#FBBF24", linewidth=3.5, zorder=12)
    ax.add_patch(bot_card)
    t_b = ax.text(960, 70, "NIFTY 50 BACKTEST: ₹33.93 LAKHS REALIZED PROFIT!",
                  color="#FDE047", fontsize=29, fontweight="black", fontfamily="Segoe UI", ha="center", va="center", zorder=13)
    t_b.set_path_effects([pe.withStroke(linewidth=5, foreground="#000000")])

    save_both(fig, "thumbnail_v1_dual_engine.png")


# ==============================================================================
# ITERATION 2: "Big Numbers & Bold Proof" (Left Heavy Text + Right Cutout)
# ==============================================================================
def make_iteration_2():
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1920)
    ax.set_ylim(0, 1080)
    ax.axis("off")
    fig.patch.set_facecolor("#060B19")

    # Ambient glows
    ax.add_patch(patches.Circle((450, 600), 650, color="#10B981", alpha=0.11, zorder=0))
    ax.add_patch(patches.Circle((1450, 480), 550, color="#0EA5E9", alpha=0.15, zorder=0))
    ax.add_patch(patches.Circle((900, 900), 450, color="#F59E0B", alpha=0.10, zorder=0))

    # Rising equity curve in background
    xs = np.linspace(50, 1870, 60)
    np.random.seed(7)
    ys = 180 + np.linspace(0, 680, 60) + np.cumsum(np.random.normal(0, 18, 60))
    ax.fill_between(xs, 0, ys, color="#10B981", alpha=0.07, zorder=1)
    ax.plot(xs, ys, color="#10B981", linewidth=4, alpha=0.35, zorder=1)

    # Top-left Tag (Wider so text breathes)
    tag = FancyBboxPatch((65, 945), 780, 74, boxstyle="round,pad=0,rounding_size=18",
                         facecolor="#78350F", edgecolor="#FBBF24", linewidth=3.0, zorder=4)
    ax.add_patch(tag)
    ax.text(455, 982, "DARVAS BEARISH + BULLISH COMBO", color="#FEF08A", fontsize=27, fontweight="black",
            fontfamily="Segoe UI", ha="center", va="center", zorder=5,
            path_effects=[pe.withStroke(linewidth=3, foreground="#000000")])

    # MASSIVE TEXT BLOCK ON LEFT (Unobstructed!)
    t1 = ax.text(65, 825, "₹33.93 LAKHS", color="#4ADE80", fontsize=88, fontweight="black",
                 fontfamily="Segoe UI", ha="left", va="center", zorder=6)
    t1.set_path_effects([pe.withStroke(linewidth=12, foreground="#022C22")])

    t2 = ax.text(65, 705, "BANKED CASH PROFIT!", color="#FFFFFF", fontsize=52, fontweight="black",
                 fontfamily="Segoe UI", ha="left", va="center", zorder=6)
    t2.set_path_effects([pe.withStroke(linewidth=9, foreground="#000000")])

    # 3 Horizontal Power Bullets on Left (Width 720 so Right Cutout's left hand doesn't collide)
    bullets = [
        ("4 BEARISH TRANCHES", "Harvester: +5% Per Dip Bounce", "#F43F5E", "#3F0B1B"),
        ("1 BULLISH TRANCHE", "Compounder: Ride 20W Highs", "#10B981", "#052E22"),
        ("1,091 WINNING DIPS", "Zero Emotion • 100% Rule-Based", "#38BDF8", "#0A2742"),
    ]
    for idx, (b_title, b_sub, b_col, b_bg) in enumerate(bullets):
        by = 485 - idx * 150
        card = FancyBboxPatch((65, by), 710, 122, boxstyle="round,pad=0,rounding_size=20",
                              facecolor=b_bg, edgecolor=b_col, linewidth=3.5, zorder=5)
        ax.add_patch(card)
        bar = FancyBboxPatch((83, by + 18), 14, 86, boxstyle="round,pad=0,rounding_size=6",
                             facecolor=b_col, edgecolor="none", zorder=6)
        ax.add_patch(bar)
        ax.text(115, by + 78, b_title, color="#FFFFFF", fontsize=28, fontweight="black",
                fontfamily="Segoe UI", ha="left", va="center", zorder=6,
                path_effects=[pe.withStroke(linewidth=4, foreground="#000000")])
        ax.text(115, by + 34, b_sub, color="#E2E8F0", fontsize=20, fontweight="bold",
                fontfamily="Segoe UI", ha="left", va="center", zorder=6)

    # Place User Cutout on Right Side
    user_img = load_and_style_user_photo(outline_color=(255, 255, 255, 255), outline_size=8, glow_color=(56, 189, 248, 170), glow_radius=22)
    ax.imshow(user_img, extent=[790, 1950, -20, 610], aspect="auto", zorder=8)

    # Left Palm Callout (Placed high above left palm at x=825..1245, y=540..680)
    lp_box = FancyBboxPatch((825, 540), 420, 140, boxstyle="round,pad=0,rounding_size=22",
                            facecolor="#3B0764", edgecolor="#C084FC", linewidth=3.5, zorder=9)
    ax.add_patch(lp_box)
    ax.text(1035, 636, "MARKET CORRECTION?", color="#E9D5FF", fontsize=20, fontweight="bold",
            fontfamily="Segoe UI", ha="center", va="center", zorder=10)
    ax.text(1035, 580, "Harvest +5% Swings!", color="#FDE047", fontsize=25, fontweight="black",
            fontfamily="Segoe UI", ha="center", va="center", zorder=10,
            path_effects=[pe.withStroke(linewidth=4, foreground="#000000")])
    ax.annotate("", xy=(990, 345), xytext=(1025, 535),
                arrowprops=dict(facecolor="#C084FC", edgecolor="#FFFFFF", width=6, headwidth=20, headlength=16), zorder=10)

    # Right Palm Callout (Placed cleanly to the right of the head at x=1490..1895, y=540..680)
    rp_box = FancyBboxPatch((1490, 540), 405, 140, boxstyle="round,pad=0,rounding_size=22",
                            facecolor="#064E3B", edgecolor="#34D399", linewidth=3.5, zorder=9)
    ax.add_patch(rp_box)
    ax.text(1692, 636, "BULL MARKET RALLY?", color="#A7F3D0", fontsize=20, fontweight="bold",
            fontfamily="Segoe UI", ha="center", va="center", zorder=10)
    ax.text(1692, 580, "Hold Uncapped Trend!", color="#4ADE80", fontsize=24, fontweight="black",
            fontfamily="Segoe UI", ha="center", va="center", zorder=10,
            path_effects=[pe.withStroke(linewidth=4, foreground="#000000")])
    ax.annotate("", xy=(1760, 295), xytext=(1710, 535),
                arrowprops=dict(facecolor="#34D399", edgecolor="#FFFFFF", width=6, headwidth=20, headlength=16), zorder=10)

    # Top Right Badge (Centered above user's head at x=1060..1880, y=765..990)
    tr_badge = FancyBboxPatch((1060, 765), 820, 225, boxstyle="round,pad=0,rounding_size=26",
                              facecolor="#1E1B4B", edgecolor="#F59E0B", linewidth=3.5, zorder=6)
    ax.add_patch(tr_badge)
    ax.text(1470, 932, "NIFTY 50 UNIVERSE (2020 – 2026)", color="#FDE047", fontsize=25, fontweight="black",
            fontfamily="Segoe UI", ha="center", va="center", zorder=7)
    ax.text(1470, 865, "6-Year Quantitative Backtest", color="#FFFFFF", fontsize=30, fontweight="black",
            fontfamily="Segoe UI", ha="center", va="center", zorder=7,
            path_effects=[pe.withStroke(linewidth=4, foreground="#000000")])
    ax.text(1470, 805, "100% Systematic • No Guesswork", color="#38BDF8", fontsize=22, fontweight="bold",
            fontfamily="Segoe UI", ha="center", va="center", zorder=7)

    save_both(fig, "thumbnail_v2_big_numbers.png")


# ==============================================================================
# ITERATION 3: "The 70% vs 30% Market Secret" (High Curiosity / Story Hook)
# ==============================================================================
def make_iteration_3():
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1920)
    ax.set_ylim(0, 1080)
    ax.axis("off")
    fig.patch.set_facecolor("#090D16")

    # Background grid lines
    for gx in range(0, 1920, 120):
        ax.axvline(gx, color="#1E293B", linewidth=1, alpha=0.45, zorder=0)
    for gy in range(0, 1080, 120):
        ax.axhline(gy, color="#1E293B", linewidth=1, alpha=0.45, zorder=0)

    # Glowing orbs
    ax.add_patch(patches.Circle((350, 620), 460, color="#F59E0B", alpha=0.14, zorder=1))
    ax.add_patch(patches.Circle((1570, 620), 460, color="#10B981", alpha=0.14, zorder=1))
    ax.add_patch(patches.Circle((960, 280), 450, color="#6366F1", alpha=0.16, zorder=1))

    # Draw 20-Week Darvas Channel wave in middle background
    wx = np.linspace(60, 1860, 200)
    wy_mid = 540 + 110 * np.sin(wx / 220.0)
    wy_high = wy_mid + 120
    wy_low = wy_mid - 120
    ax.fill_between(wx, wy_low, wy_high, color="#38BDF8", alpha=0.06, zorder=1)
    ax.plot(wx, wy_high, color="#10B981", linestyle="--", linewidth=2.5, alpha=0.5, zorder=2)
    ax.plot(wx, wy_low, color="#EF4444", linestyle="--", linewidth=2.5, alpha=0.5, zorder=2)

    # TOP YELLOW WARNING / SECRET BANNER (Extra wide so text fits comfortably inside)
    banner = FancyBboxPatch((190, 938), 1540, 92, boxstyle="round,pad=0,rounding_size=22",
                            facecolor="#FACC15", edgecolor="#FFFFFF", linewidth=3.5, zorder=6)
    ax.add_patch(banner)
    ax.text(960, 984, "STOP GETTING TRAPPED IN MARKET CRASHES!", color="#090D16", fontsize=38, fontweight="black",
            fontfamily="Segoe UI", ha="center", va="center", zorder=7)

    # SUB-HEADLINE
    sub = ax.text(960, 855, "THE 5-TRANCHE DARVAS COMBO SYSTEM", color="#FFFFFF", fontsize=55, fontweight="black",
                  fontfamily="Segoe UI", ha="center", va="center", zorder=6)
    sub.set_path_effects([pe.withStroke(linewidth=10, foreground="#000000")])

    # User Cutout in Center
    user_img = load_and_style_user_photo(outline_color=(250, 204, 21, 255), outline_size=7, glow_color=(99, 102, 241, 160), glow_radius=20)
    ax.imshow(user_img, extent=[270, 1650, -25, 665], aspect="auto", zorder=8)

    # LEFT PALM VISUAL: "70% OF THE TIME: SIDEWAYS & DIPS"
    l_box = FancyBboxPatch((50, 420), 565, 340, boxstyle="round,pad=0,rounding_size=26",
                           facecolor="#1E1306", edgecolor="#F59E0B", linewidth=4.0, zorder=9)
    ax.add_patch(l_box)

    l_top = FancyBboxPatch((80, 680), 505, 54, boxstyle="round,pad=0,rounding_size=14",
                           facecolor="#B45309", edgecolor="#FBBF24", linewidth=1.5, zorder=10)
    ax.add_patch(l_top)
    ax.text(332, 707, "70% TIME: CHOPPY / PULLBACKS", color="#FEF08A", fontsize=19, fontweight="black",
            fontfamily="Segoe UI", ha="center", va="center", zorder=11)

    t_70 = ax.text(332, 595, "4 DIP TRANCHES", color="#FFFFFF", fontsize=40, fontweight="black",
                   fontfamily="Segoe UI", ha="center", va="center", zorder=11)
    t_70.set_path_effects([pe.withStroke(linewidth=6, foreground="#000000")])

    ax.text(332, 520, "Triggers < 20-Week Low", color="#FDBA74", fontsize=23, fontweight="bold",
            fontfamily="Segoe UI", ha="center", va="center", zorder=11)
    ax.text(332, 462, "Quick +5% Cash Exits!", color="#4ADE80", fontsize=26, fontweight="black",
            fontfamily="Segoe UI", ha="center", va="center", zorder=11,
            path_effects=[pe.withStroke(linewidth=4, foreground="#000000")])

    # RIGHT PALM VISUAL: "30% OF THE TIME: BULL RUNS"
    r_box = FancyBboxPatch((1305, 420), 565, 340, boxstyle="round,pad=0,rounding_size=26",
                           facecolor="#04221B", edgecolor="#10B981", linewidth=4.0, zorder=9)
    ax.add_patch(r_box)

    r_top = FancyBboxPatch((1335, 680), 505, 54, boxstyle="round,pad=0,rounding_size=14",
                           facecolor="#047857", edgecolor="#34D399", linewidth=1.5, zorder=10)
    ax.add_patch(r_top)
    ax.text(1587, 707, "30% TIME: MEGA BULL TRENDS", color="#D1FAE5", fontsize=19, fontweight="black",
            fontfamily="Segoe UI", ha="center", va="center", zorder=11)

    t_30 = ax.text(1587, 595, "1 BULL TRANCHE", color="#FFFFFF", fontsize=40, fontweight="black",
                   fontfamily="Segoe UI", ha="center", va="center", zorder=11)
    t_30.set_path_effects([pe.withStroke(linewidth=6, foreground="#000000")])

    ax.text(1587, 520, "Triggers > 20-Week High", color="#6EE7B7", fontsize=23, fontweight="bold",
            fontfamily="Segoe UI", ha="center", va="center", zorder=11)
    ax.text(1587, 462, "Ride Multi-Year Gains!", color="#FDE047", fontsize=26, fontweight="black",
            fontfamily="Segoe UI", ha="center", va="center", zorder=11,
            path_effects=[pe.withStroke(linewidth=4, foreground="#000000")])

    # Bottom Center Pill (Wider so text has generous left/right margin)
    b_pill = FancyBboxPatch((390, 26), 1140, 84, boxstyle="round,pad=0,rounding_size=20",
                            facecolor="#0F172A", edgecolor="#38BDF8", linewidth=3.0, zorder=12)
    ax.add_patch(b_pill)
    ax.text(960, 68, "COMPLETE RULEBOOK + BACKTEST RESULTS INSIDE", color="#7DD3FC", fontsize=26, fontweight="black",
            fontfamily="Segoe UI", ha="center", va="center", zorder=13,
            path_effects=[pe.withStroke(linewidth=4, foreground="#000000")])

    save_both(fig, "thumbnail_v3_market_secret.png")


# ==============================================================================
# ITERATION 4: "CAR vs No-CAR Showdown" (The 2X Profit Revelation)
# ==============================================================================
def make_iteration_4():
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1920)
    ax.set_ylim(0, 1080)
    ax.axis("off")
    fig.patch.set_facecolor("#080B12")

    # Left vs Right dramatic lighting
    ax.add_patch(patches.Circle((360, 550), 480, color="#64748B", alpha=0.15, zorder=0))
    ax.add_patch(patches.Circle((1560, 550), 520, color="#F59E0B", alpha=0.18, zorder=0))
    ax.add_patch(patches.Circle((960, 350), 420, color="#10B981", alpha=0.12, zorder=0))

    # Top Title Pill (Wider so text breathes)
    top_p = FancyBboxPatch((400, 955), 1120, 80, boxstyle="round,pad=0,rounding_size=20",
                           facecolor="#1E293B", edgecolor="#38BDF8", linewidth=3.0, zorder=5)
    ax.add_patch(top_p)
    ax.text(960, 995, "DARVAS STRATEGY: THE ULTIMATE BACKTEST", color="#38BDF8", fontsize=30, fontweight="black",
            fontfamily="Segoe UI", ha="center", va="center", zorder=6,
            path_effects=[pe.withStroke(linewidth=4, foreground="#000000")])

    # Main Question Headline
    q_txt = ax.text(960, 855, "WHICH SYSTEM DOUBLED THE PROFIT?", color="#FFFFFF", fontsize=60, fontweight="black",
                    fontfamily="Segoe UI", ha="center", va="center", zorder=6)
    q_txt.set_path_effects([pe.withStroke(linewidth=10, foreground="#000000")])

    # User Cutout in Center
    user_img = load_and_style_user_photo(outline_color=(255, 255, 255, 255), outline_size=7, glow_color=(245, 158, 11, 160), glow_radius=20)
    ax.imshow(user_img, extent=[250, 1670, -25, 675], aspect="auto", zorder=8)

    # LEFT CARD: WITH CAR FILTER (Over Left Palm)
    l_card = FancyBboxPatch((55, 435), 565, 325, boxstyle="round,pad=0,rounding_size=24",
                            facecolor="#131C2E", edgecolor="#64748B", linewidth=3.5, zorder=9)
    ax.add_patch(l_card)

    l_hdr = FancyBboxPatch((85, 680), 505, 52, boxstyle="round,pad=0,rounding_size=12",
                           facecolor="#334155", edgecolor="#94A3B8", linewidth=1.5, zorder=10)
    ax.add_patch(l_hdr)
    ax.text(337, 706, "OPTION A: WITH CAR FILTER", color="#E2E8F0", fontsize=20, fontweight="black",
            fontfamily="Segoe UI", ha="center", va="center", zorder=11)

    t_la = ax.text(337, 595, "₹16.11 LAKHS", color="#CBD5E1", fontsize=46, fontweight="black",
                   fontfamily="Segoe UI", ha="center", va="center", zorder=11)
    t_la.set_path_effects([pe.withStroke(linewidth=6, foreground="#000000")])

    ax.text(337, 520, "Total Net Profit (+32.2%)", color="#94A3B8", fontsize=22, fontweight="bold",
            fontfamily="Segoe UI", ha="center", va="center", zorder=11)
    ax.text(337, 468, "Only 117 Dip Wins Captured", color="#F87171", fontsize=20, fontweight="bold",
            fontfamily="Segoe UI", ha="center", va="center", zorder=11)

    # RIGHT CARD: WITHOUT CAR BASELINE - WINNER! (Over Right Palm)
    r_card = FancyBboxPatch((1300, 435), 565, 325, boxstyle="round,pad=0,rounding_size=24",
                            facecolor="#271705", edgecolor="#F59E0B", linewidth=4.5, zorder=9)
    ax.add_patch(r_card)

    r_hdr = FancyBboxPatch((1330, 680), 505, 52, boxstyle="round,pad=0,rounding_size=12",
                           facecolor="#92400E", edgecolor="#FDE047", linewidth=2.0, zorder=10)
    ax.add_patch(r_hdr)
    ax.text(1582, 706, "OPTION B: NO CAR [WINNER]", color="#FEF08A", fontsize=20, fontweight="black",
            fontfamily="Segoe UI", ha="center", va="center", zorder=11)

    t_rb = ax.text(1582, 595, "₹30.89 LAKHS", color="#4ADE80", fontsize=48, fontweight="black",
                   fontfamily="Segoe UI", ha="center", va="center", zorder=11)
    t_rb.set_path_effects([pe.withStroke(linewidth=6, foreground="#000000")])

    ax.text(1582, 520, "Total Net Profit (+61.8%)", color="#FDE047", fontsize=23, fontweight="bold",
            fontfamily="Segoe UI", ha="center", va="center", zorder=11)
    ax.text(1582, 468, "1,091 Dip Wins (+92% More Profit!)", color="#6EE7B7", fontsize=20, fontweight="bold",
            fontfamily="Segoe UI", ha="center", va="center", zorder=11)

    # VS Circle Badge on chest/top-center
    vs_circle = patches.Circle((960, 725), 54, facecolor="#DC2626", edgecolor="#FEF08A", linewidth=3.5, zorder=10)
    ax.add_patch(vs_circle)
    ax.text(960, 725, "VS", color="#FFFFFF", fontsize=30, fontweight="black",
            fontfamily="Segoe UI", ha="center", va="center", zorder=11,
            path_effects=[pe.withStroke(linewidth=4, foreground="#000000")])

    # Bottom Verdict Ribbon
    bot_v = FancyBboxPatch((380, 26), 1160, 86, boxstyle="round,pad=0,rounding_size=20",
                           facecolor="#064E3B", edgecolor="#34D399", linewidth=3.5, zorder=12)
    ax.add_patch(bot_v)
    ax.text(960, 69, "+₹18.51 LAKHS EXTRA REALIZED CASH IN BANK!", color="#FEF08A", fontsize=30, fontweight="black",
            fontfamily="Segoe UI", ha="center", va="center", zorder=13,
            path_effects=[pe.withStroke(linewidth=5, foreground="#000000")])

    save_both(fig, "thumbnail_v4_showdown.png")


if __name__ == "__main__":
    make_iteration_1()
    make_iteration_2()
    make_iteration_3()
    make_iteration_4()
    print("All 4 YouTube thumbnail iterations regenerated cleanly!")
