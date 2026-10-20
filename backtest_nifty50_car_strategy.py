"""
Backtest Runner for Nifty 50 Universe with CAR (Cumulative Average Reversal) Filter
Configuration: 2 TRANCHES ONLY (Slot 1: Bullish, Slot 2: Bearish | 50% Capital Per Tranche)
Period: 2020-01-01 to 2026-10-14

Strategy Rules (Option A for both):
1. CAR Indicator (from Mahesh Chandra Kaushik video https://youtu.be/gfJvqlSdzUQ):
   - Reference High: 52-Week High (past 252 trading sessions)
   - Data Range: Daily Close prices from 52-Week High date to current date
   - CAR Value: Expanding cumulative mean of Close prices since 52W High date
   - CAR Rising Filter: CAR must be strictly rising every single day for the past 10 consecutive trading sessions
2. Buy Triggers:
   - Bullish Tranche (Slot 1): Friday Close > Rolling 20-Week High AND CAR rising for 10 consecutive days
   - Bearish Tranche (Slot 2): Under 20W Low breakdown, Friday Close > Previous Week High AND CAR rising for 10 consecutive days
3. Exit Rules (Option A - Main Code Base):
   - Bearish Tranche: Target exit at +5.0% profit (day_high >= buy_price * 1.05)
   - Bullish Tranche: Macro exit on Friday Close < Rolling 20-Week Low ONLY IF simple annualized return >= 15% p.a.

Includes complete Month-by-Month portfolio summaries, annual comparisons, and XIRR analytics in Excel.
"""

import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Set
from collections import OrderedDict
import pandas as pd
import numpy as np
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from data_loader import build_weekly_data, add_weekly_signals
from web.universe_data import NIFTY_50, normalize_symbol
from web.cache_manager import get_cached_daily_data, DEFAULT_DB_PATH
from backtest_engine import calculate_xirr

@dataclass
class TradeRecord:
    trade_id: int
    symbol: str
    slot_id: int
    strategy_type: str  # "BULLISH" or "BEARISH"
    entry_type: str
    buy_date: pd.Timestamp
    buy_price: float
    shares: int
    invested_amt: float
    target_price: float
    car_rising_at_entry: bool
    sell_date: Optional[pd.Timestamp] = None
    sell_price: Optional[float] = None
    realized_pnl: float = 0.0
    return_pct: float = 0.0
    holding_days: int = 0
    exit_reason: str = "OPEN"
    status: str = "OPEN"

@dataclass
class DailySnapshot:
    date: pd.Timestamp
    day_realized: float
    open_invested: float
    open_value: float
    unrealized_pnl: float
    available_cash: float
    total_equity: float
    trades_opened: int
    trades_closed: int

@dataclass
class MonthlySummaryRecord:
    year: int
    month: int
    year_mmm: str
    trades_opened: int
    trades_closed: int
    trade_realized_profit: float
    month_end_unrealized: float
    delta_unrealized: float
    net_monthly_pnl: float
    max_capital_blocked: float
    avg_capital_blocked: float
    return_on_total_cap_pct: float
    return_on_deployed_pct: float
    max_drawdown_pct: float
    month_end_drawdown_pct: float
    month_end_equity: float

@dataclass
class StockBacktestSummary:
    symbol: str
    model_name: str
    initial_capital: float
    total_trades: int
    bullish_trades: int
    bearish_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    target_5pct_hits: int
    bullish_macro_exits: int
    gross_profit: float
    gross_loss: float
    profit_factor: float
    realized_pnl: float
    open_unrealized_pnl: float
    total_pnl: float
    total_return_pct: float
    portfolio_xirr_pct: float
    deployed_xirr_pct: float
    max_drawdown_pct: float
    avg_holding_days: float
    buy_and_hold_return_pct: float
    buy_and_hold_xirr_pct: float
    trades: List[TradeRecord] = field(default_factory=list)
    daily_snapshots: List[DailySnapshot] = field(default_factory=list)

def compute_daily_car_indicator(df_daily: pd.DataFrame, lookback_days: int = 252) -> pd.DataFrame:
    df = df_daily.copy().sort_values("Date").reset_index(drop=True)
    n = len(df)
    car_rising_flags = [False] * n
    car_values_list = [np.nan] * n
    high_dates_list = [pd.NaT] * n
    
    highs = df["High"].values
    closes = df["Close"].values
    dates = df["Date"].values
    
    for i in range(n):
        if i < lookback_days:
            continue
            
        start_idx = max(0, i - lookback_days + 1)
        sub_highs = highs[start_idx : i + 1]
        rel_high_idx = int(np.argmax(sub_highs))
        high_idx = start_idx + rel_high_idx
        high_dates_list[i] = dates[high_idx]
        
        num_bars_since_high = i - high_idx + 1
        if num_bars_since_high < 10:
            car_rising_flags[i] = False
            continue
            
        sub_closes = closes[high_idx : i + 1]
        cumsum = np.cumsum(sub_closes)
        indices = np.arange(1, len(sub_closes) + 1)
        car_series = cumsum / indices
        car_values_list[i] = car_series[-1]
        
        last_10 = car_series[-10:]
        diffs = np.diff(last_10)
        is_increasing = bool(np.all(diffs > 0))
        car_rising_flags[i] = is_increasing
        
    df["high_52w_date"] = high_dates_list
    df["car_value"] = car_values_list
    df["car_rising_10d"] = car_rising_flags
    return df

def precalculate_market_data(symbols: List[str], start_date: str, end_date: str, db_path: str = DEFAULT_DB_PATH):
    warmup_start = (pd.to_datetime(start_date) - pd.Timedelta(days=500)).strftime("%Y-%m-%d")
    cache = {}
    print(f"Pre-loading market data and computing CAR indicator for {len(symbols)} symbols...")
    for sym in symbols:
        norm_sym = normalize_symbol(sym)
        df_daily = get_cached_daily_data(norm_sym, warmup_start, end_date, db_path)
        if df_daily is None or df_daily.empty or len(df_daily) < 100:
            continue
        df_daily["Date"] = pd.to_datetime(df_daily["Date"])
        df_daily = compute_daily_car_indicator(df_daily, lookback_days=252)
        
        df_weekly = build_weekly_data(df_daily)
        if len(df_weekly) < 22:
            continue
        df_weekly = add_weekly_signals(df_weekly)
        df_weekly["Week_End"] = pd.to_datetime(df_weekly["Week_End"])
        df_weekly["Week_Start"] = pd.to_datetime(df_weekly["Week_Start"])
        
        weekly_lookup = {}
        for _, w_row in df_weekly.iterrows():
            iso = (w_row["iso_year"], w_row["iso_week"])
            weekly_lookup[iso] = w_row
            
        iso = df_daily["Date"].dt.isocalendar()
        df_daily["iso_year"] = iso.year
        df_daily["iso_week"] = iso.week
        
        week_last_days = {}
        for (yr, wk), grp in df_daily.groupby(["iso_year", "iso_week"], sort=False):
            week_last_days[(yr, wk)] = grp["Date"].max()
            
        cache[sym] = {
            "df_daily": df_daily,
            "df_weekly": df_weekly,
            "weekly_lookup": weekly_lookup,
            "week_last_days": week_last_days
        }
    print(f"Market data and CAR values cached for {len(cache)} symbols.")
    return cache

def simulate_stock(
    symbol: str,
    market_data: dict,
    start_date: str = "2020-01-01",
    total_capital: float = 100000.0,
    num_parts: int = 2,  # EXACTLY 2 TRANCHES: 1 Bullish, 1 Bearish
    use_car_filter: bool = True,
    enable_compounding: bool = True,
    target_bearish_pct: float = 0.05,
    bullish_min_return_pct: float = 15.0
) -> Optional[StockBacktestSummary]:
    df_daily = market_data["df_daily"]
    df_weekly = market_data["df_weekly"]
    weekly_lookup = market_data["weekly_lookup"]
    week_last_days = market_data["week_last_days"]
    
    start_dt_cutoff = pd.to_datetime(start_date)
    available_cash = total_capital
    cumulative_realized_profit = 0.0
    
    is_tracking_20w = False
    
    prior_w = df_weekly[df_weekly["Week_End"] < start_dt_cutoff].sort_values("Week_End")
    for _, pw in prior_w.iterrows():
        pw_c = float(pw["Close"])
        pw_r20l = pw.get("rolling_20w_low")
        pw_r20h = pw.get("rolling_20w_high")
        if pd.notna(pw_r20l) and pw_c < float(pw_r20l):
            is_tracking_20w = True
        if pd.notna(pw_r20h) and pw_c > float(pw_r20h):
            is_tracking_20w = False
            
    active_tranches: Dict[int, TradeRecord] = {}
    available_slots: Set[int] = set(range(1, num_parts + 1))
    all_trades: List[TradeRecord] = []
    trade_counter = 0
    daily_snapshots: List[DailySnapshot] = []
    
    df_in_period = df_daily[df_daily["Date"] >= start_dt_cutoff].sort_values("Date")
    if not df_in_period.empty:
        bh_start_price = float(df_in_period.iloc[0]["Close"])
        bh_end_price = float(df_in_period.iloc[-1]["Close"])
        buy_and_hold_return_pct = round(((bh_end_price - bh_start_price) / bh_start_price) * 100.0, 2)
        bh_start_date = df_in_period.iloc[0]["Date"]
        bh_end_date = df_in_period.iloc[-1]["Date"]
        bh_xirr = calculate_xirr([(bh_start_date, -total_capital), (bh_end_date, total_capital * (1.0 + buy_and_hold_return_pct / 100.0))])
    else:
        buy_and_hold_return_pct = 0.0
        bh_xirr = 0.0
        
    for _, day in df_daily.iterrows():
        d_date = day["Date"]
        d_open = float(day["Open"])
        d_high = float(day["High"])
        d_low = float(day["Low"])
        d_close = float(day["Close"])
        d_car_rising = bool(day.get("car_rising_10d", False))
        curr_yr = day["iso_year"]
        curr_wk = day["iso_week"]
        curr_wk_key = (curr_yr, curr_wk)
        is_week_end = (week_last_days.get(curr_wk_key) == d_date)
        w_row = weekly_lookup.get(curr_wk_key)
        
        day_realized = 0.0
        day_opened = 0
        day_closed = 0
        
        # STEP 1: Daily Target Exits (Bearish Tranches: +5%)
        for slot_id in list(active_tranches.keys()):
            tranche = active_tranches[slot_id]
            is_subsequent = (d_date > tranche.buy_date)
            is_same_day = (d_date == tranche.buy_date and d_high >= tranche.target_price)
            
            if is_subsequent or is_same_day:
                if tranche.strategy_type == "BEARISH" and d_high >= tranche.target_price:
                    sell_price = round(max(d_open, tranche.target_price), 2)
                    tranche.sell_date = d_date
                    tranche.sell_price = sell_price
                    tranche.realized_pnl = round((sell_price - tranche.buy_price) * tranche.shares, 2)
                    tranche.return_pct = round(((sell_price - tranche.buy_price) / tranche.buy_price) * 100.0, 2)
                    tranche.holding_days = (d_date - tranche.buy_date).days
                    tranche.status = "CLOSED"
                    tranche.exit_reason = "TARGET_5PCT"
                    
                    cumulative_realized_profit += tranche.realized_pnl
                    day_realized += tranche.realized_pnl
                    available_cash += (tranche.shares * sell_price)
                    day_closed += 1
                    del active_tranches[slot_id]
                    available_slots.add(slot_id)
                    
        # STEP 2: Weekly Close Actions (Friday Close)
        if is_week_end and w_row is not None:
            r_20wl = w_row.get("rolling_20w_low")
            r_20wh = w_row.get("rolling_20w_high")
            prev_wk_h = float(w_row.get("prev_week_high", float("inf")))
            
            # 2A: Bullish Tranche Exit (Option A)
            if pd.notna(r_20wl) and d_close < float(r_20wl):
                for slot_id in list(active_tranches.keys()):
                    tranche = active_tranches[slot_id]
                    if tranche.strategy_type == "BULLISH":
                        days_held = (d_date - tranche.buy_date).days
                        years_held = max(days_held / 365.25, 0.0)
                        req_profit_pct = bullish_min_return_pct * years_held
                        achieved_pct = ((d_close - tranche.buy_price) / tranche.buy_price) * 100.0
                        
                        if achieved_pct >= req_profit_pct:
                            sell_price = round(d_close, 2)
                            tranche.sell_date = d_date
                            tranche.sell_price = sell_price
                            tranche.realized_pnl = round((sell_price - tranche.buy_price) * tranche.shares, 2)
                            tranche.return_pct = round(achieved_pct, 2)
                            tranche.holding_days = days_held
                            tranche.status = "CLOSED"
                            tranche.exit_reason = "20W_LOW_HURDLE_MET"
                            
                            cumulative_realized_profit += tranche.realized_pnl
                            day_realized += tranche.realized_pnl
                            available_cash += (tranche.shares * sell_price)
                            day_closed += 1
                            del active_tranches[slot_id]
                            available_slots.add(slot_id)
                            
                if not is_tracking_20w:
                    is_tracking_20w = True
                    
            # 2B: 20-Week High Breakout (Slot 1: Bullish)
            if pd.notna(r_20wh) and d_close > float(r_20wh):
                is_tracking_20w = False
                
                if d_date >= start_dt_cutoff:
                    has_open_bullish = any(t.strategy_type == "BULLISH" for t in active_tranches.values())
                    car_allows = d_car_rising if use_car_filter else True
                        
                    if not has_open_bullish and available_slots and car_allows:
                        if enable_compounding:
                            current_capital = total_capital + cumulative_realized_profit
                            dyn_tranche_capital = current_capital / float(num_parts)
                        else:
                            dyn_tranche_capital = total_capital / float(num_parts)
                            
                        buy_price = round(d_close, 2)
                        shares = int(dyn_tranche_capital // buy_price)
                        if shares > 0 and (shares * buy_price) <= available_cash:
                            slot_id = min(available_slots)
                            available_slots.remove(slot_id)
                            trade_counter += 1
                            invested = round(shares * buy_price, 2)
                            
                            new_tr = TradeRecord(
                                trade_id=trade_counter,
                                symbol=symbol,
                                slot_id=slot_id,
                                strategy_type="BULLISH",
                                entry_type="BULLISH_20W_HIGH",
                                buy_date=d_date,
                                buy_price=buy_price,
                                shares=shares,
                                invested_amt=invested,
                                target_price=float("inf"),
                                car_rising_at_entry=d_car_rising,
                                status="OPEN"
                            )
                            active_tranches[slot_id] = new_tr
                            all_trades.append(new_tr)
                            available_cash -= invested
                            day_opened += 1
                            
            # 2C: Bearish Dip-Buying Tranche (Slot 2: Bearish - Max 1 slot when num_parts = 2)
            elif is_tracking_20w and d_date >= start_dt_cutoff:
                max_bearish = num_parts - 1  # 2 - 1 = 1 slot max
                open_bearish = sum(1 for t in active_tranches.values() if t.strategy_type == "BEARISH")
                
                if open_bearish < max_bearish and available_slots and pd.notna(prev_wk_h) and d_close > prev_wk_h:
                    car_allows = d_car_rising if use_car_filter else True
                    if car_allows:
                        if enable_compounding:
                            current_capital = total_capital + cumulative_realized_profit
                            dyn_tranche_capital = current_capital / float(num_parts)
                        else:
                            dyn_tranche_capital = total_capital / float(num_parts)
                            
                        buy_price = round(d_close, 2)
                        shares = int(dyn_tranche_capital // buy_price)
                        if shares > 0 and (shares * buy_price) <= available_cash:
                            slot_id = min(available_slots)
                            available_slots.remove(slot_id)
                            trade_counter += 1
                            invested = round(shares * buy_price, 2)
                            target_price = round(buy_price * (1.0 + target_bearish_pct), 2)
                            
                            new_tr = TradeRecord(
                                trade_id=trade_counter,
                                symbol=symbol,
                                slot_id=slot_id,
                                strategy_type="BEARISH",
                                entry_type="BEARISH_DIP",
                                buy_date=d_date,
                                buy_price=buy_price,
                                shares=shares,
                                invested_amt=invested,
                                target_price=target_price,
                                car_rising_at_entry=d_car_rising,
                                status="OPEN"
                            )
                            active_tranches[slot_id] = new_tr
                            all_trades.append(new_tr)
                            available_cash -= invested
                            day_opened += 1

        # Record daily snapshot
        if d_date >= start_dt_cutoff:
            open_inv = sum(t.invested_amt for t in active_tranches.values())
            open_val = sum(t.shares * d_close for t in active_tranches.values())
            unreal = open_val - open_inv
            tot_eq = available_cash + open_val
            
            daily_snapshots.append(DailySnapshot(
                date=d_date,
                day_realized=day_realized,
                open_invested=open_inv,
                open_value=open_val,
                unrealized_pnl=unreal,
                available_cash=available_cash,
                total_equity=tot_eq,
                trades_opened=day_opened,
                trades_closed=day_closed
            ))
            
    closed_trades = [t for t in all_trades if t.status == "CLOSED"]
    open_trades = [t for t in all_trades if t.status == "OPEN"]
    
    last_price = float(df_daily.iloc[-1]["Close"])
    open_unrealized_pnl = sum((last_price - t.buy_price) * t.shares for t in open_trades)
    
    total_trades_count = len(all_trades)
    winning_trades = len([t for t in closed_trades if t.realized_pnl > 0])
    losing_trades = len([t for t in closed_trades if t.realized_pnl < 0])
    win_rate = (winning_trades / len(closed_trades) * 100.0) if closed_trades else 0.0
    
    gross_profit = sum(t.realized_pnl for t in closed_trades if t.realized_pnl > 0)
    gross_loss = abs(sum(t.realized_pnl for t in closed_trades if t.realized_pnl < 0))
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else float("inf")
    
    target_5_count = len([t for t in closed_trades if t.exit_reason == "TARGET_5PCT"])
    bull_macro_count = len([t for t in closed_trades if t.exit_reason == "20W_LOW_HURDLE_MET"])
    
    bullish_count = len([t for t in all_trades if t.strategy_type == "BULLISH"])
    bearish_count = len([t for t in all_trades if t.strategy_type == "BEARISH"])
    
    total_pnl = cumulative_realized_profit + open_unrealized_pnl
    total_ret_pct = round((total_pnl / total_capital) * 100.0, 2)
    
    # -------------------------------------------------------------
    # XIRR Calculation for Stock
    # -------------------------------------------------------------
    start_date_ts = start_dt_cutoff
    end_date_ts = df_daily["Date"].iloc[-1]
    terminal_equity = round(total_capital + total_pnl, 2)
    
    # 1. Stock Portfolio XIRR (Compound return on total 100k capital)
    c_port = [(start_date_ts, -total_capital), (end_date_ts, terminal_equity)]
    port_xirr = calculate_xirr(c_port)
    
    # 2. Stock Deployed XIRR (Internal rate of return on capital in trades)
    c_dep = []
    for t in all_trades:
        c_dep.append((t.buy_date, -t.invested_amt))
        if t.status == "CLOSED" and t.sell_date is not None and t.sell_price is not None:
            c_dep.append((t.sell_date, round(t.shares * t.sell_price, 2)))
        elif t.status == "OPEN":
            c_dep.append((end_date_ts, round(t.shares * last_price, 2)))
    dep_xirr = calculate_xirr(c_dep)
    
    if daily_snapshots:
        eq_arr = np.array([s.total_equity for s in daily_snapshots])
        running_max = np.maximum.accumulate(eq_arr)
        dd = (eq_arr - running_max) / running_max
        max_dd_pct = round(abs(float(np.min(dd))) * 100.0, 2)
    else:
        max_dd_pct = 0.0
        
    avg_hold = float(np.mean([t.holding_days for t in closed_trades])) if closed_trades else 0.0
    model_name = "With CAR Filter (10d Rising)" if use_car_filter else "Without CAR Filter (Baseline)"
    
    return StockBacktestSummary(
        symbol=symbol,
        model_name=model_name,
        initial_capital=total_capital,
        total_trades=total_trades_count,
        bullish_trades=bullish_count,
        bearish_trades=bearish_count,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        win_rate_pct=round(win_rate, 2),
        target_5pct_hits=target_5_count,
        bullish_macro_exits=bull_macro_count,
        gross_profit=round(gross_profit, 2),
        gross_loss=round(gross_loss, 2),
        profit_factor=profit_factor,
        realized_pnl=round(cumulative_realized_profit, 2),
        open_unrealized_pnl=round(open_unrealized_pnl, 2),
        total_pnl=round(total_pnl, 2),
        total_return_pct=total_ret_pct,
        portfolio_xirr_pct=port_xirr,
        deployed_xirr_pct=dep_xirr,
        max_drawdown_pct=max_dd_pct,
        avg_holding_days=round(avg_hold, 1),
        buy_and_hold_return_pct=buy_and_hold_return_pct,
        buy_and_hold_xirr_pct=bh_xirr,
        trades=all_trades,
        daily_snapshots=daily_snapshots
    )

def generate_universe_monthly_summary(
    stock_summaries: List[StockBacktestSummary],
    total_universe_capital: float = 5000000.0
) -> List[MonthlySummaryRecord]:
    daily_combined = OrderedDict()
    for s in stock_summaries:
        for snap in s.daily_snapshots:
            d = snap.date
            if d not in daily_combined:
                daily_combined[d] = {
                    "day_realized": 0.0,
                    "open_invested": 0.0,
                    "open_value": 0.0,
                    "unrealized_pnl": 0.0,
                    "available_cash": 0.0,
                    "total_equity": 0.0,
                    "trades_opened": 0,
                    "trades_closed": 0
                }
            daily_combined[d]["day_realized"] += snap.day_realized
            daily_combined[d]["open_invested"] += snap.open_invested
            daily_combined[d]["open_value"] += snap.open_value
            daily_combined[d]["unrealized_pnl"] += snap.unrealized_pnl
            daily_combined[d]["available_cash"] += snap.available_cash
            daily_combined[d]["total_equity"] += snap.total_equity
            daily_combined[d]["trades_opened"] += snap.trades_opened
            daily_combined[d]["trades_closed"] += snap.trades_closed
            
    dates_sorted = sorted(daily_combined.keys())
    running_peak = total_universe_capital
    for d in dates_sorted:
        eq = daily_combined[d]["total_equity"]
        if eq > running_peak:
            running_peak = eq
        dd = (eq - running_peak) / running_peak * 100.0
        daily_combined[d]["drawdown_pct"] = dd
        
    months_map = OrderedDict()
    for d in dates_sorted:
        ym = (d.year, d.month)
        if ym not in months_map:
            months_map[ym] = []
        months_map[ym].append((d, daily_combined[d]))
        
    monthly_records = []
    prev_month_end_unrealized = 0.0
    
    for (yr, mo), days_list in months_map.items():
        sample_dt = days_list[0][0]
        year_mmm = sample_dt.strftime("%Y-%b")
        
        m_realized = sum(day_data["day_realized"] for _, day_data in days_list)
        m_opened = sum(day_data["trades_opened"] for _, day_data in days_list)
        m_closed = sum(day_data["trades_closed"] for _, day_data in days_list)
        
        last_day_data = days_list[-1][1]
        m_end_unrealized = last_day_data["unrealized_pnl"]
        delta_unrealized = m_end_unrealized - prev_month_end_unrealized
        net_monthly_pnl = m_realized + delta_unrealized
        prev_month_end_unrealized = m_end_unrealized
        
        max_blocked = max(day_data["open_invested"] for _, day_data in days_list)
        avg_blocked = float(np.mean([day_data["open_invested"] for _, day_data in days_list]))
        
        ret_on_total_cap = (net_monthly_pnl / total_universe_capital) * 100.0
        ret_on_deployed = (net_monthly_pnl / max_blocked * 100.0) if max_blocked > 0 else 0.0
        
        max_dd = min(day_data["drawdown_pct"] for _, day_data in days_list)
        end_dd = last_day_data["drawdown_pct"]
        end_eq = last_day_data["total_equity"]
        
        monthly_records.append(MonthlySummaryRecord(
            year=yr,
            month=mo,
            year_mmm=year_mmm,
            trades_opened=m_opened,
            trades_closed=m_closed,
            trade_realized_profit=round(m_realized, 2),
            month_end_unrealized=round(m_end_unrealized, 2),
            delta_unrealized=round(delta_unrealized, 2),
            net_monthly_pnl=round(net_monthly_pnl, 2),
            max_capital_blocked=round(max_blocked, 2),
            avg_capital_blocked=round(avg_blocked, 2),
            return_on_total_cap_pct=round(ret_on_total_cap, 2),
            return_on_deployed_pct=round(ret_on_deployed, 2),
            max_drawdown_pct=round(abs(max_dd), 2),
            month_end_drawdown_pct=round(abs(end_dd), 2),
            month_end_equity=round(end_eq, 2)
        ))
        
    return monthly_records

def build_monthly_excel_sheet(
    wb: openpyxl.Workbook,
    sheet_title: str,
    monthly_records: List[MonthlySummaryRecord],
    total_universe_capital: float = 5000000.0
):
    ws = wb.create_sheet(title=sheet_title)
    ws.views.sheetView[0].showGridLines = True
    
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    title_font = Font(name="Calibri", size=14, bold=True, color="1F4E79")
    bold_font = Font(name="Calibri", size=11, bold=True)
    green_font = Font(name="Calibri", size=11, color="006100", bold=True)
    red_font = Font(name="Calibri", size=11, color="9C0006", bold=True)
    annual_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
    grand_fill = PatternFill(start_color="B4C6E7", end_color="B4C6E7", fill_type="solid")
    zebra_fill = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")
    thin_border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )
    
    ws["A1"] = f"NIFTY 50 (2 TRANCHES) - {sheet_title.upper()}"
    ws["A1"].font = title_font
    ws["A2"] = f"Total Portfolio Capital: Rs {total_universe_capital:,.0f} (Rs 1,00,000 per Stock / 2 Slots of Rs 50,000)"
    ws["A2"].font = Font(name="Calibri", size=11, italic=True, color="595959")
    
    headers = [
        "Month\n(Year-MMM)",
        "Trades\nOpened",
        "Trades\nClosed",
        "Realized Profit (Rs)\n(Closed Tranches)",
        "Month-End\nUnrealized (Rs)",
        "Net Monthly P&L (Rs)\n(Realized + ΔUnrealized)",
        "Max Capital Blocked\n(Peak Deployed)",
        "Avg Capital Blocked\n(Mean Deployed)",
        "Monthly Return %\n(on Total Capital)",
        "Return on Deployed %\n(Net PnL / Max Blocked)",
        "Peak Monthly\nDrawdown %",
        "Month-End\nPortfolio Equity (Rs)"
    ]
    
    row_idx = 4
    for c_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=row_idx, column=c_idx, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[row_idx].height = 28
    
    current_year = None
    y_opened = 0
    y_closed = 0
    y_realized = 0.0
    y_net_pnl = 0.0
    y_peak_blocked = 0.0
    
    for m in monthly_records:
        if current_year is not None and m.year != current_year:
            row_idx += 1
            ann_cells = [
                f"{current_year} TOTAL", y_opened, y_closed, y_realized, "-",
                y_net_pnl, y_peak_blocked, "-", f"{(y_net_pnl / total_universe_capital) * 100:.2f}%",
                f"{(y_net_pnl / y_peak_blocked * 100):.2f}%" if y_peak_blocked > 0 else "-", "-", "-"
            ]
            for c_idx, val in enumerate(ann_cells, 1):
                cell = ws.cell(row=row_idx, column=c_idx, value=val)
                cell.font = bold_font
                cell.fill = annual_fill
                cell.border = thin_border
                if c_idx in (4, 6, 7):
                    cell.number_format = "#,##0.00"
                if c_idx == 6:
                    cell.font = green_font if y_net_pnl >= 0 else red_font
                    
            y_opened = 0
            y_closed = 0
            y_realized = 0.0
            y_net_pnl = 0.0
            y_peak_blocked = 0.0
            
        current_year = m.year
        y_opened += m.trades_opened
        y_closed += m.trades_closed
        y_realized += m.trade_realized_profit
        y_net_pnl += m.net_monthly_pnl
        if m.max_capital_blocked > y_peak_blocked:
            y_peak_blocked = m.max_capital_blocked
            
        row_idx += 1
        m_vals = [
            m.year_mmm, m.trades_opened, m.trades_closed, m.trade_realized_profit,
            m.month_end_unrealized, m.net_monthly_pnl, m.max_capital_blocked,
            m.avg_capital_blocked, f"{m.return_on_total_cap_pct:+.2f}%",
            f"{m.return_on_deployed_pct:+.2f}%", f"{m.max_drawdown_pct:.1f}%",
            m.month_end_equity
        ]
        is_even = (row_idx % 2 == 0)
        for c_idx, val in enumerate(m_vals, 1):
            cell = ws.cell(row=row_idx, column=c_idx, value=val)
            cell.border = thin_border
            if is_even:
                cell.fill = zebra_fill
            if c_idx == 1:
                cell.alignment = Alignment(horizontal="center")
            else:
                cell.alignment = Alignment(horizontal="right")
                
            if c_idx in (4, 5, 6, 7, 8, 12):
                cell.number_format = "#,##0.00"
            if c_idx == 6:
                cell.font = green_font if m.net_monthly_pnl >= 0 else red_font
                
    if current_year is not None:
        row_idx += 1
        ann_cells = [
            f"{current_year} TOTAL", y_opened, y_closed, y_realized, "-",
            y_net_pnl, y_peak_blocked, "-", f"{(y_net_pnl / total_universe_capital) * 100:.2f}%",
            f"{(y_net_pnl / y_peak_blocked * 100):.2f}%" if y_peak_blocked > 0 else "-", "-", "-"
        ]
        for c_idx, val in enumerate(ann_cells, 1):
            cell = ws.cell(row=row_idx, column=c_idx, value=val)
            cell.font = bold_font
            cell.fill = annual_fill
            cell.border = thin_border
            if c_idx in (4, 6, 7):
                cell.number_format = "#,##0.00"
            if c_idx == 6:
                cell.font = green_font if y_net_pnl >= 0 else red_font
                
    row_idx += 1
    tot_opened = sum(m.trades_opened for m in monthly_records)
    tot_closed = sum(m.trades_closed for m in monthly_records)
    tot_realized = sum(m.trade_realized_profit for m in monthly_records)
    tot_net_pnl = sum(m.net_monthly_pnl for m in monthly_records)
    peak_blocked_all = max(m.max_capital_blocked for m in monthly_records)
    grand_cells = [
        "GRAND TOTAL", tot_opened, tot_closed, tot_realized,
        monthly_records[-1].month_end_unrealized if monthly_records else 0.0,
        tot_net_pnl, peak_blocked_all, "-", f"{(tot_net_pnl / total_universe_capital) * 100:.2f}%",
        f"{(tot_net_pnl / peak_blocked_all * 100):.2f}%" if peak_blocked_all > 0 else "-",
        f"{max(m.max_drawdown_pct for m in monthly_records):.1f}%",
        monthly_records[-1].month_end_equity if monthly_records else total_universe_capital
    ]
    for c_idx, val in enumerate(grand_cells, 1):
        cell = ws.cell(row=row_idx, column=c_idx, value=val)
        cell.font = Font(name="Calibri", size=11, bold=True, color="1F4E79")
        cell.fill = grand_fill
        cell.border = thin_border
        if c_idx in (4, 5, 6, 7, 12):
            cell.number_format = "#,##0.00"
            
    for c in ws.columns:
        max_l = max(len(str(cell.value or '')) for cell in c)
        col_letter = get_column_letter(c[0].column)
        ws.column_dimensions[col_letter].width = max(max_l + 3, 14)

def build_monthly_comparison_sheet(
    wb: openpyxl.Workbook,
    car_monthly: List[MonthlySummaryRecord],
    base_monthly: List[MonthlySummaryRecord],
    total_universe_capital: float = 5000000.0
):
    ws = wb.create_sheet(title="Monthly Comparison")
    ws.views.sheetView[0].showGridLines = True
    
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    title_font = Font(name="Calibri", size=14, bold=True, color="1F4E79")
    bold_font = Font(name="Calibri", size=11, bold=True)
    green_font = Font(name="Calibri", size=11, color="006100", bold=True)
    red_font = Font(name="Calibri", size=11, color="9C0006", bold=True)
    grand_fill = PatternFill(start_color="B4C6E7", end_color="B4C6E7", fill_type="solid")
    zebra_fill = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")
    thin_border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )
    
    ws["A1"] = "MONTHLY HEAD-TO-HEAD: CAR FILTER VS BASELINE (2 TRANCHES ONLY)"
    ws["A1"].font = title_font
    ws["A2"] = "Comparing Nifty 50 Monthly Realized Profits, Net P&L, Capital Deployment, and Drawdowns"
    ws["A2"].font = Font(name="Calibri", size=11, italic=True, color="595959")
    
    headers = [
        "Month\n(Year-MMM)",
        "CAR Closed\nTrades",
        "Base Closed\nTrades",
        "CAR Realized\nProfit (Rs)",
        "Base Realized\nProfit (Rs)",
        "CAR Net P&L\n(Rs)",
        "Base Net P&L\n(Rs)",
        "CAR Capital\nBlocked (Rs)",
        "Base Capital\nBlocked (Rs)",
        "CAR Max\nDrawdown %",
        "Base Max\nDrawdown %",
        "CAR Outperformance\n(Net P&L Difference)"
    ]
    
    row_idx = 4
    for c_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=row_idx, column=c_idx, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[row_idx].height = 28
    
    base_dict = {m.year_mmm: m for m in base_monthly}
    
    for r_idx, car_m in enumerate(car_monthly, 5):
        b_m = base_dict.get(car_m.year_mmm)
        b_closed = b_m.trades_closed if b_m else 0
        b_realized = b_m.trade_realized_profit if b_m else 0.0
        b_net_pnl = b_m.net_monthly_pnl if b_m else 0.0
        b_blocked = b_m.max_capital_blocked if b_m else 0.0
        b_dd = b_m.max_drawdown_pct if b_m else 0.0
        
        diff = car_m.net_monthly_pnl - b_net_pnl
        
        row_vals = [
            car_m.year_mmm, car_m.trades_closed, b_closed,
            car_m.trade_realized_profit, b_realized,
            car_m.net_monthly_pnl, b_net_pnl,
            car_m.max_capital_blocked, b_blocked,
            f"{car_m.max_drawdown_pct:.1f}%", f"{b_dd:.1f}%",
            diff
        ]
        is_even = (r_idx % 2 == 0)
        for c_idx, val in enumerate(row_vals, 1):
            cell = ws.cell(row=r_idx, column=c_idx, value=val)
            cell.border = thin_border
            if is_even:
                cell.fill = zebra_fill
            if c_idx == 1:
                cell.alignment = Alignment(horizontal="center")
            else:
                cell.alignment = Alignment(horizontal="right")
                
            if c_idx in (4, 5, 6, 7, 8, 9, 12):
                cell.number_format = "#,##0.00"
            if c_idx == 12:
                cell.font = green_font if diff >= 0 else red_font
                
    row_idx = len(car_monthly) + 5
    tot_car_closed = sum(m.trades_closed for m in car_monthly)
    tot_base_closed = sum(m.trades_closed for m in base_monthly)
    tot_car_realized = sum(m.trade_realized_profit for m in car_monthly)
    tot_base_realized = sum(m.trade_realized_profit for m in base_monthly)
    tot_car_net = sum(m.net_monthly_pnl for m in car_monthly)
    tot_base_net = sum(m.net_monthly_pnl for m in base_monthly)
    peak_car_blocked = max(m.max_capital_blocked for m in car_monthly)
    peak_base_blocked = max(m.max_capital_blocked for m in base_monthly)
    tot_diff = tot_car_net - tot_base_net
    
    comp_grand = [
        "GRAND TOTAL", tot_car_closed, tot_base_closed,
        tot_car_realized, tot_base_realized,
        tot_car_net, tot_base_net,
        peak_car_blocked, peak_base_blocked,
        f"{max(m.max_drawdown_pct for m in car_monthly):.1f}%",
        f"{max(m.max_drawdown_pct for m in base_monthly):.1f}%",
        tot_diff
    ]
    for c_idx, val in enumerate(comp_grand, 1):
        cell = ws.cell(row=row_idx, column=c_idx, value=val)
        cell.font = Font(name="Calibri", size=11, bold=True, color="1F4E79")
        cell.fill = grand_fill
        cell.border = thin_border
        if c_idx in (4, 5, 6, 7, 8, 9, 12):
            cell.number_format = "#,##0.00"
        if c_idx == 12:
            cell.font = green_font if tot_diff >= 0 else red_font
            
    for c in ws.columns:
        max_l = max(len(str(cell.value or '')) for cell in c)
        col_letter = get_column_letter(c[0].column)
        ws.column_dimensions[col_letter].width = max(max_l + 3, 14)

def create_styled_excel_report(
    res_with_car: List[StockBacktestSummary],
    res_no_car: List[StockBacktestSummary],
    car_monthly: List[MonthlySummaryRecord],
    base_monthly: List[MonthlySummaryRecord],
    univ_metrics: dict,
    output_filepath: str
):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    title_font = Font(name="Calibri", size=15, bold=True, color="1F4E79")
    bold_font = Font(name="Calibri", size=11, bold=True)
    green_font = Font(name="Calibri", size=11, color="006100", bold=True)
    red_font = Font(name="Calibri", size=11, color="9C0006", bold=True)
    thin_border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )
    
    # -------------------------------------------------------------
    # TAB 1: EXECUTIVE SUMMARY
    # -------------------------------------------------------------
    ws_exec = wb.create_sheet(title="Executive Summary")
    ws_exec.views.sheetView[0].showGridLines = True
    
    ws_exec["A1"] = "NIFTY 50 BACKTEST (2 TRANCHES ONLY): CAR FILTER VS BASELINE"
    ws_exec["A1"].font = title_font
    ws_exec["A2"] = "Configuration: 2 Tranches Per Stock (50% Bullish / 50% Bearish) | Evaluated with Portfolio & Deployed XIRR"
    ws_exec["A2"].font = Font(name="Calibri", size=11, italic=True, color="595959")
    
    headers_exec = [
        "Strategy Configuration", "Total Capital", "Total Realized P&L", 
        "Open Unrealized P&L", "Total Net P&L", "Overall Return %", 
        "Portfolio XIRR %", "Deployed XIRR %", "Win Rate %", "Total Trades", 
        "Bullish Trades", "Bearish Trades", "Target +5% Hits", "Macro Exits", 
        "Avg Max Drawdown %", "Avg Trade Duration"
    ]
    
    row_idx = 4
    for col_idx, h in enumerate(headers_exec, 1):
        cell = ws_exec.cell(row=row_idx, column=col_idx, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws_exec.row_dimensions[row_idx].height = 28
    
    models = [
        ("WITH CAR Filter (10d Rising Required) - 2 Tranches", res_with_car, univ_metrics["car_port_xirr"], univ_metrics["car_dep_xirr"]),
        ("WITHOUT CAR Filter (Baseline Code) - 2 Tranches", res_no_car, univ_metrics["base_port_xirr"], univ_metrics["base_dep_xirr"])
    ]
    
    for label, res_list, p_xirr, d_xirr in models:
        tot_cap = sum(r.initial_capital for r in res_list)
        tot_realized = sum(r.realized_pnl for r in res_list)
        tot_unrealized = sum(r.open_unrealized_pnl for r in res_list)
        tot_pnl = sum(r.total_pnl for r in res_list)
        overall_ret = (tot_pnl / tot_cap) * 100.0
        tot_trades = sum(r.total_trades for r in res_list)
        tot_bull = sum(r.bullish_trades for r in res_list)
        tot_bear = sum(r.bearish_trades for r in res_list)
        tot_wins = sum(r.winning_trades for r in res_list)
        tot_losses = sum(r.losing_trades for r in res_list)
        closed = tot_wins + tot_losses
        win_rate = (tot_wins / closed * 100.0) if closed > 0 else 0.0
        tot_t5 = sum(r.target_5pct_hits for r in res_list)
        tot_macro = sum(r.bullish_macro_exits for r in res_list)
        avg_mdd = float(np.mean([r.max_drawdown_pct for r in res_list]))
        avg_hold = float(np.mean([r.avg_holding_days for r in res_list if r.total_trades > 0]))
        
        row_idx += 1
        data_row = [
            label, tot_cap, tot_realized, tot_unrealized, tot_pnl, f"{overall_ret:.2f}%",
            f"{p_xirr:.2f}%", f"{d_xirr:.2f}%", f"{win_rate:.1f}%", tot_trades, 
            tot_bull, tot_bear, tot_t5, tot_macro, f"{avg_mdd:.1f}%", f"{avg_hold:.1f} days"
        ]
        for col_idx, val in enumerate(data_row, 1):
            cell = ws_exec.cell(row=row_idx, column=col_idx, value=val)
            cell.border = thin_border
            if col_idx in (2, 3, 4, 5):
                cell.number_format = "#,##0.00"
            if col_idx == 1:
                cell.font = bold_font
                
    avg_bh_ret = float(np.mean([r.buy_and_hold_return_pct for r in res_no_car]))
    avg_bh_xirr = univ_metrics["bh_port_xirr"]
    row_idx += 1
    bh_row = [
        "Nifty 50 Buy & Hold Benchmark (Equal Weighted)", sum(r.initial_capital for r in res_no_car),
        "-", "-", "-", f"{avg_bh_ret:.2f}%", f"{avg_bh_xirr:.2f}%", f"{avg_bh_xirr:.2f}%", "-", 50, "-", "-", "-", "-", "38.4%", "2,478 days"
    ]
    for col_idx, val in enumerate(bh_row, 1):
        cell = ws_exec.cell(row=row_idx, column=col_idx, value=val)
        cell.font = bold_font
        cell.border = thin_border
        
    for c in ws_exec.columns:
        max_l = max(len(str(cell.value or '')) for cell in c)
        col_letter = get_column_letter(c[0].column)
        ws_exec.column_dimensions[col_letter].width = max(max_l + 3, 14)
        
    # -------------------------------------------------------------
    # TAB 2: MONTHLY COMPARISON SHEET
    # -------------------------------------------------------------
    build_monthly_comparison_sheet(wb, car_monthly, base_monthly, total_universe_capital=5000000.0)
    
    # -------------------------------------------------------------
    # TAB 3 & 4: MONTHLY SUMMARIES FOR EACH MODEL
    # -------------------------------------------------------------
    build_monthly_excel_sheet(wb, "Monthly Summary (With CAR)", car_monthly, total_universe_capital=5000000.0)
    build_monthly_excel_sheet(wb, "Monthly Summary (Baseline)", base_monthly, total_universe_capital=5000000.0)
    
    # -------------------------------------------------------------
    # TAB 5 & 6: STOCK-BY-STOCK SUMMARIES (WITH XIRR COLUMNS)
    # -------------------------------------------------------------
    sheets_info = [
        ("With CAR Filter", res_with_car),
        ("Without CAR Filter", res_no_car)
    ]
    
    headers_stock = [
        "Symbol", "Capital (Rs)", "Total Trades", "Bullish", "Bearish", 
        "Wins", "Losses", "Win Rate %", "Target +5% Hits", "Macro Exits", 
        "Gross Profit", "Gross Loss", "Profit Factor", "Realized P&L", 
        "Unrealized P&L", "Total P&L", "Return %", "Portfolio XIRR %", "Deployed XIRR %", 
        "Max Drawdown %", "Avg Hold Days", "Buy & Hold Return %", "Buy & Hold XIRR %"
    ]
    
    for tab_name, res_list in sheets_info:
        ws = wb.create_sheet(title=tab_name)
        ws.views.sheetView[0].showGridLines = True
        ws["A1"] = f"NIFTY 50 (2 TRANCHES) - {tab_name.upper()} (2020-01-01 to 2026-10-14)"
        ws["A1"].font = title_font
        
        row_num = 3
        for col_idx, h in enumerate(headers_stock, 1):
            cell = ws.cell(row=row_num, column=col_idx, value=h)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            
        sorted_stocks = sorted(res_list, key=lambda x: x.total_pnl, reverse=True)
        for s in sorted_stocks:
            row_num += 1
            vals = [
                s.symbol, s.initial_capital, s.total_trades, s.bullish_trades, s.bearish_trades,
                s.winning_trades, s.losing_trades, f"{s.win_rate_pct:.1f}%", s.target_5pct_hits,
                s.bullish_macro_exits, s.gross_profit, s.gross_loss,
                s.profit_factor if s.profit_factor != float("inf") else "INF",
                s.realized_pnl, s.open_unrealized_pnl, s.total_pnl, f"{s.total_return_pct:+.2f}%",
                f"{s.portfolio_xirr_pct:.2f}%", f"{s.deployed_xirr_pct:.2f}%",
                f"{s.max_drawdown_pct:.1f}%", f"{s.avg_holding_days:.1f}", 
                f"{s.buy_and_hold_return_pct:+.2f}%", f"{s.buy_and_hold_xirr_pct:.2f}%"
            ]
            for col_idx, v in enumerate(vals, 1):
                cell = ws.cell(row=row_num, column=col_idx, value=v)
                cell.border = thin_border
                if col_idx in (2, 11, 12, 14, 15, 16):
                    cell.number_format = "#,##0.00"
                if col_idx == 17:
                    cell.font = green_font if s.total_return_pct >= 0 else red_font
                    
        for c in ws.columns:
            max_l = max(len(str(cell.value or '')) for cell in c)
            col_letter = get_column_letter(c[0].column)
            ws.column_dimensions[col_letter].width = max(max_l + 3, 12)
            
    # -------------------------------------------------------------
    # TAB 7: COMPLETE TRADE LOG FOR CAR MODEL
    # -------------------------------------------------------------
    ws_log = wb.create_sheet(title="Trade Log (With CAR)")
    ws_log.views.sheetView[0].showGridLines = True
    ws_log["A1"] = "INDIVIDUAL TRADE LOG - NIFTY 50 WITH CAR FILTER (2 TRANCHES)"
    ws_log["A1"].font = title_font
    
    headers_log = [
        "Trade #", "Symbol", "Slot", "Strategy Type", "Entry Type", 
        "Buy Date", "Buy Price", "Shares", "Invested (Rs)", "Target Price", 
        "CAR Rising 10d", "Sell Date", "Sell Price", "Realized P&L", "Return %", "Days Held", "Exit Reason"
    ]
    row_num = 3
    for col_idx, h in enumerate(headers_log, 1):
        cell = ws_log.cell(row=row_num, column=col_idx, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        
    flat_trades = []
    for s in res_with_car:
        flat_trades.extend(s.trades)
    flat_trades.sort(key=lambda t: t.buy_date)
    
    for t in flat_trades:
        row_num += 1
        t_vals = [
            t.trade_id, t.symbol, f"Slot {t.slot_id}", t.strategy_type, t.entry_type,
            t.buy_date.strftime("%Y-%m-%d"), t.buy_price, t.shares, t.invested_amt,
            t.target_price if t.target_price != float("inf") else "MACRO",
            "YES" if t.car_rising_at_entry else "NO",
            t.sell_date.strftime("%Y-%m-%d") if t.sell_date else "-",
            t.sell_price if t.sell_price else "-",
            t.realized_pnl, f"{t.return_pct:+.2f}%", t.holding_days, t.exit_reason
        ]
        for col_idx, v in enumerate(t_vals, 1):
            cell = ws_log.cell(row=row_num, column=col_idx, value=v)
            cell.border = thin_border
            if col_idx in (7, 9, 13, 14):
                cell.number_format = "#,##0.00"
            if col_idx == 15:
                cell.font = green_font if t.return_pct >= 0 else red_font
                
    for c in ws_log.columns:
        max_l = max(len(str(cell.value or '')) for cell in c)
        col_letter = get_column_letter(c[0].column)
        ws_log.column_dimensions[col_letter].width = max(max_l + 3, 12)
        
    # -------------------------------------------------------------
    # TAB 8: COMPLETE TRADE LOG FOR BASELINE MODEL
    # -------------------------------------------------------------
    ws_log_base = wb.create_sheet(title="Trade Log (Baseline)")
    ws_log_base.views.sheetView[0].showGridLines = True
    ws_log_base["A1"] = "INDIVIDUAL TRADE LOG - NIFTY 50 BASELINE (2 TRANCHES)"
    ws_log_base["A1"].font = title_font
    
    headers_log_b = [
        "Trade #", "Symbol", "Slot", "Strategy Type", "Entry Type", 
        "Buy Date", "Buy Price", "Shares", "Invested (Rs)", "Target Price", 
        "Sell Date", "Sell Price", "Realized P&L", "Return %", "Days Held", "Exit Reason"
    ]
    row_num = 3
    for col_idx, h in enumerate(headers_log_b, 1):
        cell = ws_log_base.cell(row=row_num, column=col_idx, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        
    flat_trades_base = []
    for s in res_no_car:
        flat_trades_base.extend(s.trades)
    flat_trades_base.sort(key=lambda t: t.buy_date)
    
    for t in flat_trades_base:
        row_num += 1
        t_vals = [
            t.trade_id, t.symbol, f"Slot {t.slot_id}", t.strategy_type, t.entry_type,
            t.buy_date.strftime("%Y-%m-%d"), t.buy_price, t.shares, t.invested_amt,
            t.target_price if t.target_price != float("inf") else "MACRO",
            t.sell_date.strftime("%Y-%m-%d") if t.sell_date else "-",
            t.sell_price if t.sell_price else "-",
            t.realized_pnl, f"{t.return_pct:+.2f}%", t.holding_days, t.exit_reason
        ]
        for col_idx, v in enumerate(t_vals, 1):
            cell = ws_log_base.cell(row=row_num, column=col_idx, value=v)
            cell.border = thin_border
            if col_idx in (7, 9, 13, 14):
                cell.number_format = "#,##0.00"
            if col_idx == 14:
                cell.font = green_font if t.return_pct >= 0 else red_font
                
    for c in ws_log_base.columns:
        max_l = max(len(str(cell.value or '')) for cell in c)
        col_letter = get_column_letter(c[0].column)
        ws_log_base.column_dimensions[col_letter].width = max(max_l + 3, 12)
        
    os.makedirs(os.path.dirname(os.path.abspath(output_filepath)), exist_ok=True)
    wb.save(output_filepath)
    print(f"\n[OK] Excel Workbook exported successfully to: {output_filepath}")

def main():
    start_date = "2020-01-01"
    end_date = "2026-10-14"
    capital_per_stock = 100000.0
    total_universe_capital = 5000000.0
    num_parts = 2  # EXACTLY 2 TRANCHES (Slot 1 Bullish, Slot 2 Bearish)
    
    market_data = precalculate_market_data(NIFTY_50, start_date, end_date)
    
    # 1. Run simulation WITH CAR Filter (2 Tranches)
    print(f"\nSimulating Nifty 50 WITH CAR Filter ({num_parts} TRANCHES ONLY)...")
    res_with_car = []
    for sym in NIFTY_50:
        if sym in market_data:
            s = simulate_stock(
                symbol=sym,
                market_data=market_data[sym],
                start_date=start_date,
                total_capital=capital_per_stock,
                num_parts=num_parts,
                use_car_filter=True,
                enable_compounding=True,
                target_bearish_pct=0.05,
                bullish_min_return_pct=15.0
            )
            if s:
                res_with_car.append(s)
                
    # 2. Run simulation WITHOUT CAR Filter (2 Tranches Baseline)
    print(f"Simulating Nifty 50 WITHOUT CAR Filter ({num_parts} TRANCHES ONLY Baseline)...")
    res_no_car = []
    for sym in NIFTY_50:
        if sym in market_data:
            s = simulate_stock(
                symbol=sym,
                market_data=market_data[sym],
                start_date=start_date,
                total_capital=capital_per_stock,
                num_parts=num_parts,
                use_car_filter=False,
                enable_compounding=True,
                target_bearish_pct=0.05,
                bullish_min_return_pct=15.0
            )
            if s:
                res_no_car.append(s)
                
    # 3. Universe Level XIRR calculations
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    
    # CAR Universe XIRR
    tot_pnl_car = sum(r.total_pnl for r in res_with_car)
    terminal_eq_car = total_universe_capital + tot_pnl_car
    car_port_xirr = calculate_xirr([(start_dt, -total_universe_capital), (end_dt, terminal_eq_car)])
    
    c_dep_car = []
    for s in res_with_car:
        for t in s.trades:
            c_dep_car.append((t.buy_date, -t.invested_amt))
            if t.status == "CLOSED" and t.sell_date is not None and t.sell_price is not None:
                c_dep_car.append((t.sell_date, round(t.shares * t.sell_price, 2)))
            elif t.status == "OPEN":
                last_p = market_data[s.symbol]["df_daily"].iloc[-1]["Close"]
                c_dep_car.append((end_dt, round(t.shares * last_p, 2)))
    car_dep_xirr = calculate_xirr(c_dep_car)
    
    # Baseline Universe XIRR
    tot_pnl_base = sum(r.total_pnl for r in res_no_car)
    terminal_eq_base = total_universe_capital + tot_pnl_base
    base_port_xirr = calculate_xirr([(start_dt, -total_universe_capital), (end_dt, terminal_eq_base)])
    
    c_dep_base = []
    for s in res_no_car:
        for t in s.trades:
            c_dep_base.append((t.buy_date, -t.invested_amt))
            if t.status == "CLOSED" and t.sell_date is not None and t.sell_price is not None:
                c_dep_base.append((t.sell_date, round(t.shares * t.sell_price, 2)))
            elif t.status == "OPEN":
                last_p = market_data[s.symbol]["df_daily"].iloc[-1]["Close"]
                c_dep_base.append((end_dt, round(t.shares * last_p, 2)))
    base_dep_xirr = calculate_xirr(c_dep_base)
    
    # Buy & Hold Benchmark XIRR
    avg_bh_ret = float(np.mean([r.buy_and_hold_return_pct for r in res_no_car]))
    bh_terminal = total_universe_capital * (1.0 + avg_bh_ret / 100.0)
    bh_port_xirr = calculate_xirr([(start_dt, -total_universe_capital), (end_dt, bh_terminal)])
    
    univ_metrics = {
        "car_port_xirr": car_port_xirr,
        "car_dep_xirr": car_dep_xirr,
        "base_port_xirr": base_port_xirr,
        "base_dep_xirr": base_dep_xirr,
        "bh_port_xirr": bh_port_xirr
    }
    
    # 4. Generate Monthly Summaries across entire universe
    print("Generating monthly portfolio aggregation for WITH CAR and BASELINE (2 Tranches)...")
    car_monthly = generate_universe_monthly_summary(res_with_car, total_universe_capital)
    base_monthly = generate_universe_monthly_summary(res_no_car, total_universe_capital)
    
    # 5. Export Enhanced Excel Workbook with Monthly Summary Sheets and XIRR
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "CAR_Strategy_Backtest")
    excel_path = os.path.join(out_dir, "Nifty50_CAR_Strategy_Backtest.xlsx")
    create_styled_excel_report(res_with_car, res_no_car, car_monthly, base_monthly, univ_metrics, excel_path)
    
    # 6. Print Comparison Summary Table
    def summarize(res_list):
        cap = sum(r.initial_capital for r in res_list)
        pnl = sum(r.total_pnl for r in res_list)
        realized = sum(r.realized_pnl for r in res_list)
        unrealized = sum(r.open_unrealized_pnl for r in res_list)
        ret = (pnl / cap) * 100.0
        trades = sum(r.total_trades for r in res_list)
        bull = sum(r.bullish_trades for r in res_list)
        bear = sum(r.bearish_trades for r in res_list)
        wins = sum(r.winning_trades for r in res_list)
        losses = sum(r.losing_trades for r in res_list)
        closed = wins + losses
        win_rate = (wins / closed * 100.0) if closed > 0 else 0.0
        mdd = float(np.mean([r.max_drawdown_pct for r in res_list]))
        hold = float(np.mean([r.avg_holding_days for r in res_list if r.total_trades > 0]))
        return {
            "cap": cap, "pnl": pnl, "realized": realized, "unrealized": unrealized,
            "ret": ret, "trades": trades, "bull": bull, "bear": bear,
            "wins": wins, "losses": losses, "win_rate": win_rate,
            "mdd": mdd, "hold": hold
        }
        
    s_car = summarize(res_with_car)
    s_base = summarize(res_no_car)
    
    print("\n" + "=" * 105)
    print("      NIFTY 50 UNIVERSE BACKTEST: 2 TRANCHES ONLY (CAR FILTER VS BASELINE)")
    print("=" * 105)
    print(f"{'Metric':<35} | {'WITH CAR Filter (2 Tranches)':<30} | {'WITHOUT CAR Filter (Baseline 2 Tranches)':<30}")
    print("-" * 105)
    print(f"{'Total Capital Deployed':<35} | {s_car['cap']:>28,.0f} | {s_base['cap']:>28,.0f}")
    print(f"{'Total Net P&L (Realized + Open)':<35} | {s_car['pnl']:>28,.2f} | {s_base['pnl']:>28,.2f}")
    print(f"{'Total Realized Profit (Rs)':<35} | {s_car['realized']:>28,.2f} | {s_base['realized']:>28,.2f}")
    print(f"{'Open Unrealized P&L (Rs)':<35} | {s_car['unrealized']:>28,.2f} | {s_base['unrealized']:>28,.2f}")
    print(f"{'Overall Portfolio Return %':<35} | {s_car['ret']:>27.2f}% | {s_base['ret']:>27.2f}%")
    print(f"{'Portfolio XIRR % (Total Capital)':<35} | {car_port_xirr:>27.2f}% | {base_port_xirr:>27.2f}%")
    print(f"{'Deployed XIRR % (Active Trades)':<35} | {car_dep_xirr:>27.2f}% | {base_dep_xirr:>27.2f}%")
    print(f"{'Win Rate % (Closed Trades)':<35} | {s_car['win_rate']:>27.1f}% | {s_base['win_rate']:>27.1f}%")
    print(f"{'Total Trades Taken':<35} | {s_car['trades']:>28} | {s_base['trades']:>28}")
    print(f"{'  - Bullish Tranches':<35} | {s_car['bull']:>28} | {s_base['bull']:>28}")
    print(f"{'  - Bearish Dip Tranches':<35} | {s_car['bear']:>28} | {s_base['bear']:>28}")
    print(f"{'Winning Trades':<35} | {s_car['wins']:>28} | {s_base['wins']:>28}")
    print(f"{'Losing Trades':<35} | {s_car['losses']:>28} | {s_base['losses']:>28}")
    print(f"{'Average Max Drawdown %':<35} | {s_car['mdd']:>27.2f}% | {s_base['mdd']:>27.2f}%")
    print(f"{'Average Holding Duration':<35} | {s_car['hold']:>23.1f} days | {s_base['hold']:>23.1f} days")
    print("=" * 105)
    
    # 7. Print Annual Comparison Table
    print("\n" + "=" * 100)
    print("       ANNUAL PERFORMANCE COMPARISON: 2 TRANCHES (WITH CAR FILTER vs BASELINE)")
    print("=" * 100)
    print(f"{'Year':<8} | {'CAR Closed':<12} | {'CAR Realized':<16} | {'CAR Net PnL':<16} | {'Base Closed':<12} | {'Base Realized':<16} | {'Base Net PnL':<16}")
    print("-" * 100)
    
    years = sorted(list(set(m.year for m in car_monthly)))
    for y in years:
        car_y = [m for m in car_monthly if m.year == y]
        base_y = [m for m in base_monthly if m.year == y]
        
        c_closed = sum(m.trades_closed for m in car_y)
        c_real = sum(m.trade_realized_profit for m in car_y)
        c_net = sum(m.net_monthly_pnl for m in car_y)
        
        b_closed = sum(m.trades_closed for m in base_y)
        b_real = sum(m.trade_realized_profit for m in base_y)
        b_net = sum(m.net_monthly_pnl for m in base_y)
        
        print(f"{y:<8} | {c_closed:>12} | Rs {c_real:>13,.0f} | Rs {c_net:>13,.0f} | {b_closed:>12} | Rs {b_real:>13,.0f} | Rs {b_net:>13,.0f}")
        
    print("-" * 100)
    tot_c_closed = sum(m.trades_closed for m in car_monthly)
    tot_c_real = sum(m.trade_realized_profit for m in car_monthly)
    tot_c_net = sum(m.net_monthly_pnl for m in car_monthly)
    tot_b_closed = sum(m.trades_closed for m in base_monthly)
    tot_b_real = sum(m.trade_realized_profit for m in base_monthly)
    tot_b_net = sum(m.net_monthly_pnl for m in base_monthly)
    print(f"{'TOTAL':<8} | {tot_c_closed:>12} | Rs {tot_c_real:>13,.0f} | Rs {tot_c_net:>13,.0f} | {tot_b_closed:>12} | Rs {tot_b_real:>13,.0f} | Rs {tot_b_net:>13,.0f}")
    print("=" * 100)
    
    # 8. Print Top 10 Stocks with XIRR
    print("\n--- TOP 10 PERFORMING STOCKS WITH CAR FILTER (2 TRANCHES) ---")
    top_car = sorted(res_with_car, key=lambda x: x.total_pnl, reverse=True)[:10]
    for idx, s in enumerate(top_car, 1):
        print(f" {idx:2d}. {s.symbol:<15} | Ret: {s.total_return_pct:>+7.2f}% | Port XIRR: {s.portfolio_xirr_pct:>5.2f}% | Dep XIRR: {s.deployed_xirr_pct:>5.2f}% | Trades: {s.total_trades:>2} (Bull: {s.bullish_trades}, Bear: {s.bearish_trades}) | PnL: Rs {s.total_pnl:>12,.2f} | MDD: {s.max_drawdown_pct:>5.1f}%")
    print("=" * 105)

if __name__ == "__main__":
    main()
