# Specification: Weekly Swing Breakout Backtesting Engine

## 1. Objective
Develop an accurate, automated backtesting engine for a weekly swing trading breakout strategy. The system simulates capital management across 5 independent tranches, tracks trades on daily OHLC data, and outputs an Excel workbook containing an executive summary dashboard and a detailed trade log with plain numbers (no rupee symbols).

---

## 2. Strategy Rules & Execution Mechanics

### 2.1 Capital & Tranche Allocation
- **Total Portfolio Capital**: `100000` (1 Lakh) per stock.
- **Tranches (Slots)**: `5` equal parts.
- **Capital per Tranche**: `20000` per part.
- **Concurrent Position Limit**: Maximum `5` active tranches at any time.
- **Share Sizing**: $\lfloor 20000 / \text{Buy Price} \rfloor$.
- **Number Formatting**: All monetary figures and prices are formatted as plain numbers without currency symbols (e.g., `100000`, `20000`, `1250.50`).

### 2.2 Signal Generation (Weekly Timeframe)
- **Timeframe Resampling**: Daily OHLCV data is resampled into weekly bars ending on the last trading day of the week (typically Friday).
- **Setup Trigger**: At the close of Week $W_t$, check if:
  $$\text{Close}_{W_t} > \text{High}_{W_{t-1}}$$
- If true and current open tranches $< 5$:
  - Generate a **Pending Buy Setup** for the subsequent week $W_{t+1}$.
  - Reference Price = $\text{Close}_{W_t}$.
  - Entry Price Ceiling = $\text{Close}_{W_t} \times 1.005$ (+0.5% buffer).

### 2.3 Order Execution (Daily Timeframe in Week $W_{t+1}$)
- On each trading day of week $W_{t+1}$:
  - If a pending buy setup is active:
    - Check if `Daily Low` $\le$ Entry Price Ceiling.
    - If met:
      - **Fill Buy Tranche**:
        - Buy Date = Date of the trading day.
        - Buy Price = $\min(\text{Daily Open}, \text{Entry Price Ceiling})$.
        - Target Price = $\text{Buy Price} \times 1.05$ (+5% profit).
        - Mark setup as FILLED for this week (maximum 1 buy tranche per week).
  - If the week ends without meeting the entry condition, the pending order is cancelled ("cycle repeats").

### 2.4 Profit Exit & Slot Recycling
- **Target Rule**: Each active tranche is tracked independently.
- On each subsequent trading day:
  - Check if `Daily High` $\ge$ `Tranche Target Price`.
  - If met:
    - **Close Tranche**:
      - Sell Date = Date of the trading day.
      - Sell Price = `Tranche Target Price` (+5% gain).
      - Realized Profit = $(\text{Sell Price} - \text{Buy Price}) \times \text{Shares}$.
      - Status = `CLOSED`.
    - The tranche slot is freed up immediately, allowing future weekly breakout signals to take a new tranche starting the next week.
- **Stop Loss**: No stop loss; tranches are held until the 5% target is hit.

---

## 3. Architecture & Components

```
Strategies/New Weekly Darvas Box/
├── config.py             # Configuration parameters (Capital, parts, targets, buffers, symbols)
├── data_loader.py        # yfinance daily fetch, weekly resampler, breakout signal detector
├── backtest_engine.py    # Event-driven day-by-day simulator with 5-tranche portfolio manager
├── excel_reporter.py     # openpyxl workbook generator (KPI dashboard + Trade log with plain numbers)
├── run_backtest.py       # CLI runner supporting single symbol or batch portfolio backtests
├── tests/
│   └── test_engine.py    # Unit tests verifying signal detection, fill logic, and 5-slot constraint
└── SPECIFICATION.md      # This strategy specification document
```

### 3.1 Component Responsibilities
1. **`config.py`**:
   - `TOTAL_CAPITAL = 100000`
   - `NUM_PARTS = 5`
   - `TRANCHE_CAPITAL = 20000`
   - `PROFIT_TARGET_PCT = 0.05`
   - `ENTRY_BUFFER_PCT = 0.005`
   - Default date range: 5 years (e.g., `2021-01-01` to current date).
   - Default watchlist: `['RELIANCE.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS', 'TCS.NS']`.

2. **`data_loader.py`**:
   - Fetches historical daily data via `yfinance`.
   - Aggregates daily data into complete weekly bars (Open, High, Low, Close, Volume).
   - Computes `prev_week_high` and flags `signal = (close > prev_week_high)`.

3. **`backtest_engine.py`**:
   - Iterates chronological daily bars.
   - Maintains:
     - `available_cash` (starts at 100000).
     - `active_tranches` (list of open positions, max 5).
     - `closed_tranches` (list of completed trades).
     - `pending_weekly_order` (pending limit buy for the current week).
   - Records all trade details for reporting.

4. **`excel_reporter.py`**:
   - Creates a multi-tab or single consolidated Excel workbook (`.xlsx`).
   - Formats all numeric cells with standard comma-separated numeric formatting (`#,##0.00` or `#,##0`) **without any currency prefix**.
   - Includes:
     - **Summary Dashboard**: Total Capital, Realized Profit, Net ROI %, Max Tranches Used, Total Trades, Completed Trades, Open Trades, Win Rate %, Avg Holding Days.
     - **Trade Journal Table**: Trade #, Slot #, Signal Date, Buy Date, Buy Price, Shares, Invested Amount, Target Price, Sell Date, Sell Price, Realized P&L, Return %, Holding Days, Status.

---

## 4. Verification & Testing Plan
1. **Unit Tests (`tests/test_engine.py`)**:
   - Verify weekly breakout signal triggering when `Close > Prev Week High`.
   - Verify limit buy fill logic: triggers when `Low <= Friday Close * 1.005` with `Buy Price = min(Open, Friday Close * 1.005)`.
   - Verify that an unfilled order expires at the end of the week.
   - Verify that no more than 5 tranches can be active concurrently.
   - Verify that target exit triggers on `Daily High >= Buy Price * 1.05`.
   - Verify capital recycling: slot is released only for subsequent weeks.
2. **Integration Run**:
   - Run the engine on `RELIANCE.NS` over 2021–2026.
   - Verify generated Excel workbook contains clean plain numbers and accurate summaries.
