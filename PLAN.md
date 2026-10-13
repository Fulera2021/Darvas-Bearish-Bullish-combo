# Weekly Swing Breakout Backtesting Engine Implementation Plan

> **For agentic workers:** REQUIRED WORKFLOW: Implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a modular backtesting engine and Excel reporting system for the 5-tranche Weekly Swing Breakout strategy on NSE stocks, exporting plain numeric trade logs and KPI summaries.

**Architecture:** Event-driven day-by-day simulator driven by daily and weekly OHLC bars from `yfinance`. A 5-tranche portfolio manager tracks discrete share positions with 5% profit target exits, releasing capacity for future weekly cycles. Results are exported to an Excel workbook via `openpyxl`.

**Tech Stack:** Python 3.13, `pandas`, `yfinance`, `openpyxl`, `unittest`.

**Spec:** [SPECIFICATION.md](file:///c:/Users/krish/Desktop/API/Anti%20Gravity/Strategies/New%20Weekly%20Darvas%20Box/SPECIFICATION.md)

## Global Constraints
- **Workspace Boundary**: All files and operations must remain strictly inside `c:\Users\krish\Desktop\API\Anti Gravity\Strategies\New Weekly Darvas Box`.
- **Number Formatting**: All monetary figures and prices in Excel, logs, and outputs MUST be plain numbers (e.g., `100000`, `20000`, `1234.50`) without any currency symbols (no rupee `₹` sign).
- **Tranche Limit**: Maximum 5 concurrent active tranches at any time.
- **Weekly Signal Constraint**: Breakout signals are detected at weekly close (`Close > Prev Week High`). Order is evaluated on daily bars next week. Maximum 1 new tranche per week.
- **Exit Rule**: Exit on `Daily High >= Entry Price * 1.05`. Hold indefinitely until target is reached (no stop loss). Re-entry allowed only in subsequent weeks.

---

### Task 1: Configuration & Data Loader

**Files:**
- Create: `Strategies/New Weekly Darvas Box/config.py`
- Create: `Strategies/New Weekly Darvas Box/data_loader.py`
- Test: `Strategies/New Weekly Darvas Box/tests/test_data_loader.py`

**Interfaces:**
- Produces:
  - `config.BacktestConfig`: dataclass with `total_capital`, `num_parts`, `target_pct`, `entry_buffer_pct`, `start_date`, `end_date`, `symbols`.
  - `data_loader.fetch_daily_data(symbol, start_date, end_date) -> pd.DataFrame`
  - `data_loader.build_weekly_data(df_daily) -> pd.DataFrame` (resampled weekly bars with `prev_week_high` and `breakout_signal`)

- [x] **Step 1: Write unit tests for data loader and weekly resampling**
- [x] **Step 2: Run test to verify it fails**
- [x] **Step 3: Implement `config.py` and `data_loader.py`**
- [x] **Step 4: Run tests and verify they pass**

---

### Task 2: Core Event-Driven Simulation Engine

**Files:**
- Create: `Strategies/New Weekly Darvas Box/backtest_engine.py`
- Test: `Strategies/New Weekly Darvas Box/tests/test_engine.py`

**Interfaces:**
- Consumes: `BacktestConfig`, daily and weekly DataFrames from `data_loader.py`.
- Produces:
  - `backtest_engine.Tranche`: Dataclass tracking trade ID, slot index (1-5), signal date, buy date, buy price, shares, invested amount, target price, sell date, sell price, realized P&L, return %, holding days, status (`OPEN`/`CLOSED`).
  - `backtest_engine.BacktestResult`: Container with summary statistics and list of all `Tranche` records.
  - `backtest_engine.run_backtest(df_daily, df_weekly, config) -> BacktestResult`

- [x] **Step 1: Write unit tests verifying 5-slot constraint, limit buy execution, and 5% target exit**
- [x] **Step 2: Run test to verify it fails**
- [x] **Step 3: Implement `backtest_engine.py`**
- [x] **Step 4: Run tests and verify all trade lifecycle states pass**

---

### Task 3: Excel Reporter & Visual Performance Dashboard

**Files:**
- Create: `Strategies/New Weekly Darvas Box/excel_reporter.py`
- Test: `Strategies/New Weekly Darvas Box/tests/test_excel_reporter.py`

**Interfaces:**
- Consumes: `BacktestResult`, `BacktestConfig`, output path.
- Produces:
  - `excel_reporter.export_backtest_to_excel(result, output_filepath) -> str`: Formats KPI cards and full trade journal table with plain numeric format codes (`#,##0.00` and `#,##0`) without currency signs.

- [x] **Step 1: Write unit test to verify Excel file creation, tab structure, and plain numeric formatting**
- [x] **Step 2: Run test to verify it fails**
- [x] **Step 3: Implement `excel_reporter.py`**
- [x] **Step 4: Run tests and verify workbook generation**

---

### Task 4: CLI Runner & Full End-to-End Verification

**Files:**
- Create: `Strategies/New Weekly Darvas Box/run_backtest.py`
- Test: End-to-end execution on `RELIANCE.NS` over 2021 to 2026.

**Interfaces:**
- CLI arguments: `--symbol` (default: `RELIANCE.NS`), `--batch` (run all watchlist symbols), `--start` (default: `2021-01-01`), `--output` (path to Excel).

- [x] **Step 1: Implement `run_backtest.py` CLI script**
- [x] **Step 2: Execute end-to-end backtest on `RELIANCE.NS`**
- [x] **Step 3: Verify the output Excel workbook and validate trade entries, exits, and KPI summary**
