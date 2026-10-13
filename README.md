---
title: Darvas Bearish + Bullish Combo Backtester
emoji: 📈
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 8005
pinned: false
---

# Darvas Bearish + Bullish Combo Algorithmic Backtester

A dedicated, multi-user quantitative backtesting web application for the **5-Tranche Darvas Bearish Dip-Buying + Dedicated Bullish Momentum Strategy** on Indian Equities (NSE).

---

## Strategy Mechanics

1. **Tranche & Capital Allocation**:
   - Total stock capital is divided into $N$ parts (default 5 tranches).
   - **$N - 1$ parts** (e.g. 4 tranches) are reserved for **Bearish Dip-Buying**.
   - **1 part** (e.g. 1 tranche) is dedicated to **Bullish Momentum Riding**.

2. **Bearish Strategy (Dip-Buying)**:
   - **Activation**: Triggers when weekly close drops below the rolling 20-week low (`Close < 20W Low`).
   - **Buying**: Buys at Friday close on Darvas breakout (`Close > Prev_Week_High`), up to a maximum of $N - 1$ tranches.
   - **Deactivation**: Stops buying when weekly close crosses above the 20-week high (`Close > 20W High`).
   - **Exit**: Independent 5% profit target per tranche.

3. **Bullish Strategy (Momentum Trend Ride)**:
   - **Entry**: When weekly close breaks above the rolling 20-week high (`Close > 20W High`), buy **1 Bullish Tranche** at Friday close (maximum 1 active Bullish tranche per stock).
   - **Exit**: Evaluated on Friday weekly close. Sold at Friday close **only when both conditions are met**:
     1. Weekly close breaks below rolling 20-week low (`Close < 20W Low`).
     2. Simple annualized return requirement is satisfied:
        $$\frac{\text{Weekly Close} - \text{Buy Price}}{\text{Buy Price}} \ge \left(X\% \times \frac{\text{Days Held}}{365.25}\right)$$
        *(where $X\%$ is configurable, default **15.0% per annum**).*
     - If condition 1 is met but condition 2 is not, the position continues to be held.

4. **Shared Mechanics**:
   - **Magic Profit**: Rs 500 per stock applied once across any open tranches in loss when rolling 20DL is breached.
   - **Idle Capital Interest**: 5% p.a. pro-rata return on unused cash beyond 1 tranche buffer.
   - **Corporate Dividends**: Accrued under the strict T-2 trading days settlement eligibility rule.
   - **Universe Concurrency & Breakout Prioritization**: Candidate ranking by breakout percentage above reference price.

---

## Running Locally

To launch on your local machine:

```bash
# In this directory:
run_web.bat
# Or manually via python:
python -m uvicorn web.app:app --host 0.0.0.0 --port 8005 --reload
```

Open your browser to: `http://localhost:8005`
