"""
Compare CAR Method vs No CAR (Baseline) using the EXACT Web Portfolio Simulator Engine & Parameters:
- Target Universe: Nifty 50 (50 Stocks)
- Overall Capital: Rs. 50,00,000 (Rs. 50 Lakhs)
- Max Concurrent Stocks: 50
- Tranches per Stock: 4 (Per Tranche Base: Rs. 25,000)
- Start Date: 2020-01-01
- End Date: 2026-10-17
- Bearish Target: 5.0%
- Bullish Exit Min Return % P.A.: 15.0%
- Strategy: Vanilla Strategy (Compounding=True, Idle Interest=5% p.a., Dividends Included, Magic Profit=False)
"""

import os
import sys
import copy
from typing import List, Dict, Optional, Tuple, Set
import pandas as pd
import numpy as np

from config import BacktestConfig
from data_loader import build_weekly_data, add_weekly_signals
from backtest_engine import Tranche, DividendEvent, calculate_xirr
from web.universe_data import get_universe_symbols, normalize_symbol
from web.cache_manager import ensure_symbol_data, ensure_symbol_dividends, DEFAULT_DB_PATH
from web.portfolio_simulator import run_portfolio_universe_simulation, PortfolioBacktestResult, StockSummary

def compute_daily_car_indicator(df_daily: pd.DataFrame, lookback_days: int = 252) -> pd.DataFrame:
    """Computes Mahesh Chandra Kaushik 52W-High anchored CAR indicator and 10-day rising flag."""
    df = df_daily.copy().sort_values("Date").reset_index(drop=True)
    n = len(df)
    car_rising_flags = [False] * n
    car_values_list = [np.nan] * n
    
    highs = df["High"].values
    closes = df["Close"].values
    
    for i in range(n):
        if i < lookback_days:
            continue
            
        start_idx = max(0, i - lookback_days + 1)
        sub_highs = highs[start_idx : i + 1]
        rel_high_idx = int(np.argmax(sub_highs))
        high_idx = start_idx + rel_high_idx
        
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
        
    df["car_value"] = car_values_list
    df["car_rising_10d"] = car_rising_flags
    return df

def run_portfolio_universe_simulation_car(
    symbols: List[str],
    config: BacktestConfig,
    max_active_stocks: int = 50,
    db_path: str = DEFAULT_DB_PATH
) -> PortfolioBacktestResult:
    """
    Executes identical shared-capital universe portfolio simulation as web/portfolio_simulator.py,
    but enforces the 10-day rising CAR filter on all buy entries (Bullish & Bearish).
    """
    if max_active_stocks <= 0:
        max_active_stocks = 50
    if config.num_parts <= 0:
        config.num_parts = 4

    stock_capital = config.total_capital / float(max_active_stocks)
    tranche_capital = stock_capital / float(config.num_parts)
    norm_symbols = [normalize_symbol(s) for s in symbols]
    
    stock_data: Dict[str, Dict[str, pd.DataFrame]] = {}
    all_dates_set: Set[pd.Timestamp] = set()

    warmup_start_dt = (pd.to_datetime(config.start_date) - pd.Timedelta(days=500)).strftime("%Y-%m-%d")
    for sym in norm_symbols:
        try:
            df_daily = ensure_symbol_data(sym, warmup_start_dt, config.end_date, db_path)
            if df_daily is None or len(df_daily) < 50:
                continue
            
            # Compute CAR indicator on daily data
            df_daily = compute_daily_car_indicator(df_daily, lookback_days=252)
            
            df_weekly = build_weekly_data(df_daily)
            if len(df_weekly) < 22:
                continue
            df_weekly_signals = add_weekly_signals(
                df_weekly,
                entry_buffer_pct=config.entry_buffer_pct,
                use_trend_filter=config.use_trend_filter,
                trend_ema_period=config.trend_ema_period,
                darvas_box_weeks=config.darvas_box_weeks
            )
            daily_dict = {row["Date"]: row for _, row in df_daily.iterrows()}
            all_dates_set.update(df_daily["Date"])

            df_div = ensure_symbol_dividends(sym, warmup_start_dt, config.end_date, db_path)
            dividends_dict = {}
            if df_div is not None and not df_div.empty:
                for _, d_row in df_div.iterrows():
                    dividends_dict[pd.to_datetime(d_row["Date"]).normalize()] = float(d_row["Dividend"])

            daily_dates_list = [pd.to_datetime(d).normalize() for d in df_daily["Date"]]

            stock_data[sym] = {
                "daily": df_daily,
                "weekly_signals": df_weekly_signals,
                "daily_dict": daily_dict,
                "dividends_dict": dividends_dict,
                "daily_dates_list": daily_dates_list
            }
        except Exception as e:
            continue

    all_dates = sorted(list(all_dates_set))
    start_dt_cutoff = pd.to_datetime(config.start_date)

    open_tranches: Dict[str, List[Tranche]] = {s: [] for s in stock_data}
    is_tracking_20w: Dict[str, bool] = {s: False for s in stock_data}
    last_known_close: Dict[str, float] = {s: 0.0 for s in stock_data}

    # Cold start tracking
    for s in stock_data:
        w_df_sym = stock_data[s]["weekly_signals"]
        prior_w = w_df_sym[w_df_sym["Week_End"] < start_dt_cutoff].sort_values("Week_End")
        for _, pw_row in prior_w.iterrows():
            pw_c = float(pw_row["Close"])
            pw_r20l = pw_row.get("rolling_20w_low")
            pw_r20h = pw_row.get("rolling_20w_high")
            if not is_tracking_20w[s] and pd.notna(pw_r20l) and pw_c < float(pw_r20l):
                is_tracking_20w[s] = True
            if pd.notna(pw_r20h) and pw_c > float(pw_r20h):
                is_tracking_20w[s] = False

    all_trades: List[Tranche] = []
    trade_id_seq = 1

    weekly_events_by_date: Dict[pd.Timestamp, List[Tuple[str, pd.Series]]] = {}
    for sym, data in stock_data.items():
        w_df = data["weekly_signals"]
        for _, w_row in w_df.iterrows():
            w_end = w_row["Week_End"]
            if w_end not in weekly_events_by_date:
                weekly_events_by_date[w_end] = []
            weekly_events_by_date[w_end].append((sym, w_row))

    portfolio_cash_flows: List[Tuple[pd.Timestamp, float]] = [
        (start_dt_cutoff, -config.total_capital)
    ]
    deployed_cash_flows: List[Tuple[pd.Timestamp, float]] = []

    cumulative_realized_profit = 0.0
    cumulative_idle_interest = 0.0
    cumulative_dividend_income = 0.0
    all_dividend_events: List[DividendEvent] = []
    dividend_id_seq = 1
    prev_idle_date: Optional[pd.Timestamp] = None
    untouched_cash_buffer = tranche_capital * max_active_stocks
    peak_portfolio_value = config.total_capital
    max_drawdown_pct = 0.0

    for current_date in all_dates:
        day_trade_realized = 0.0
        day_dividend = 0.0
        
        # A0. Dividends (T-2 Rule)
        for sym, t_list in list(open_tranches.items()):
            if not t_list:
                continue
            div_dict = stock_data[sym]["dividends_dict"]
            curr_norm = pd.to_datetime(current_date).normalize()
            if curr_norm in div_dict:
                div_per_share = div_dict[curr_norm]
                sym_dates = stock_data[sym]["daily_dates_list"]
                try:
                    sym_idx = sym_dates.index(curr_norm)
                    t_minus_2_date = sym_dates[sym_idx - 2] if sym_idx >= 2 else (curr_norm - pd.Timedelta(days=2))
                except ValueError:
                    t_minus_2_date = curr_norm - pd.Timedelta(days=2)

                for tr in t_list:
                    tr_buy_norm = pd.to_datetime(tr.buy_date).normalize()
                    if tr_buy_norm <= t_minus_2_date:
                        payout = round(tr.shares * div_per_share, 2)
                        tr.dividend_total += payout
                        cumulative_dividend_income += payout
                        day_dividend += payout
                        deployed_cash_flows.append((current_date, payout))

                        d_ev = DividendEvent(
                            event_id=dividend_id_seq,
                            ex_date=current_date,
                            symbol=sym,
                            trade_id=tr.trade_id,
                            slot_id=tr.slot_id,
                            buy_date=tr.buy_date,
                            shares=tr.shares,
                            dividend_per_share=div_per_share,
                            total_payout=payout
                        )
                        all_dividend_events.append(d_ev)
                        dividend_id_seq += 1

        # A. Target Exits (Bearish tranches at +5.0%)
        for sym, t_list in list(open_tranches.items()):
            if not t_list:
                continue
            daily_dict = stock_data[sym]["daily_dict"]
            if current_date not in daily_dict:
                continue

            day_bar = daily_dict[current_date]
            day_high = float(day_bar["High"])
            day_close = float(day_bar["Close"])
            last_known_close[sym] = day_close

            remaining_tranches = []
            for tr in t_list:
                if tr.status == "OPEN" and tr.tranche_type == "BEARISH" and day_high >= tr.target_price:
                    tr.status = "CLOSED"
                    tr.sell_date = current_date
                    tr.sell_price = tr.target_price
                    tr.holding_days = (current_date - tr.buy_date).days
                    tr.realized_pnl = round((tr.sell_price - tr.buy_price) * tr.shares, 2)
                    tr.return_pct = round(((tr.sell_price / tr.buy_price) - 1.0) * 100.0, 2)

                    cumulative_realized_profit += tr.realized_pnl
                    day_trade_realized += tr.realized_pnl
                    deployed_cash_flows.append((current_date, tr.shares * tr.sell_price))
                else:
                    remaining_tranches.append(tr)
            open_tranches[sym] = remaining_tranches

        # B. Weekly Bar Signals
        if current_date in weekly_events_by_date:
            weekly_signals = weekly_events_by_date[current_date]

            # 1. Bullish Tranche Exits at Friday close
            for sym, w_row in weekly_signals:
                w_close = float(w_row["Close"])
                last_known_close[sym] = w_close
                r_20w_low = w_row["rolling_20w_low"]

                if pd.notna(r_20w_low) and w_close < float(r_20w_low):
                    surviving = []
                    for tr in open_tranches[sym]:
                        if tr.status == "OPEN" and tr.tranche_type == "BULLISH":
                            days_held = (current_date - tr.buy_date).days
                            years_held = max(days_held / 365.25, 0.0)
                            req_profit_pct = config.bullish_min_return_pct * years_held
                            achieved_pct = ((w_close - tr.buy_price) / tr.buy_price) * 100.0

                            if achieved_pct >= req_profit_pct:
                                tr.status = "CLOSED"
                                tr.sell_date = current_date
                                tr.sell_price = w_close
                                tr.holding_days = days_held
                                tr.realized_pnl = round((w_close - tr.buy_price) * tr.shares, 2)
                                tr.return_pct = round(achieved_pct, 2)
                                tr.required_return_pct = round(req_profit_pct, 2)
                                tr.achieved_return_pct = round(achieved_pct, 2)
                                tr.years_held = round(years_held, 2)

                                cumulative_realized_profit += tr.realized_pnl
                                day_trade_realized += tr.realized_pnl
                                deployed_cash_flows.append((current_date, tr.shares * tr.sell_price))
                            else:
                                surviving.append(tr)
                        else:
                            surviving.append(tr)
                    open_tranches[sym] = surviving

            # 2. Collect buy candidates
            buy_candidates: List[Tuple[str, float, str]] = []

            for sym, w_row in weekly_signals:
                w_close = float(w_row["Close"])
                r_20w_low = w_row["rolling_20w_low"]
                r_20w_high = w_row["rolling_20w_high"]
                breakout = bool(w_row["breakout_signal"])

                # Check CAR Rising Flag for this symbol on current Friday
                day_bar = stock_data[sym]["daily_dict"].get(current_date)
                car_rising = bool(day_bar["car_rising_10d"]) if (day_bar is not None and "car_rising_10d" in day_bar and pd.notna(day_bar["car_rising_10d"])) else False

                # Low breakdown activation
                if pd.notna(r_20w_low) and w_close < float(r_20w_low):
                    is_tracking_20w[sym] = True

                # High breakout deactivation
                if pd.notna(r_20w_high) and w_close > float(r_20w_high):
                    is_tracking_20w[sym] = False

                    # Bullish candidate (REQUIRES CAR RISING 10D)
                    if config.enable_bullish_combo and car_rising:
                        has_open_bullish = any(t.tranche_type == "BULLISH" for t in open_tranches[sym])
                        if not has_open_bullish and len(open_tranches[sym]) < config.num_parts:
                            p_high_20 = float(r_20w_high)
                            pct_breakout_high = (w_close - p_high_20) / p_high_20 if p_high_20 > 0 else 0.0
                            buy_candidates.append((sym, pct_breakout_high, "BULLISH"))

                # Bearish dip candidate (REQUIRES CAR RISING 10D)
                elif is_tracking_20w[sym] and breakout and car_rising:
                    max_bearish = (config.num_parts - 1) if config.enable_bullish_combo else config.num_parts
                    open_bearish = sum(1 for t in open_tranches[sym] if t.tranche_type == "BEARISH")
                    if open_bearish < max_bearish and len(open_tranches[sym]) < config.num_parts:
                        p_high = float(w_row["prev_week_high"])
                        pct_breakout = (w_close - p_high) / p_high if p_high > 0 else 0.0
                        buy_candidates.append((sym, pct_breakout, "BEARISH"))

            # Sort by breakout strength ascending
            buy_candidates.sort(key=lambda x: x[1], reverse=False)

            # 3. Execute buys
            if current_date >= start_dt_cutoff:
                currently_active_stocks = {s for s, trs in open_tranches.items() if len(trs) > 0}

                for sym, _, t_type in buy_candidates:
                    num_open_tranches = len(open_tranches[sym])
                    if num_open_tranches >= config.num_parts:
                        continue

                    if t_type == "BULLISH":
                        if any(t.tranche_type == "BULLISH" for t in open_tranches[sym]):
                            continue
                    else:
                        max_bearish = (config.num_parts - 1) if config.enable_bullish_combo else config.num_parts
                        open_bearish = sum(1 for t in open_tranches[sym] if t.tranche_type == "BEARISH")
                        if open_bearish >= max_bearish:
                            continue

                    is_already_active = (sym in currently_active_stocks)
                    if not is_already_active and len(currently_active_stocks) >= max_active_stocks:
                        continue

                    day_bar = stock_data[sym]["daily_dict"][current_date]
                    buy_price = float(day_bar["Close"])
                    if buy_price <= 0:
                        continue

                    if getattr(config, "enable_compounding", True):
                        current_overall_capital = config.total_capital + cumulative_realized_profit + cumulative_dividend_income
                        current_tranche_capital = current_overall_capital / float(max_active_stocks * config.num_parts)
                    else:
                        current_tranche_capital = tranche_capital

                    shares = int(current_tranche_capital // buy_price)
                    if shares <= 0:
                        shares = 1

                    invested_amt = round(shares * buy_price, 2)
                    tgt_price = round(buy_price * (1.0 + config.target_pct), 2) if t_type == "BEARISH" else float("inf")

                    new_tranche = Tranche(
                        trade_id=trade_id_seq,
                        slot_id=num_open_tranches + 1,
                        symbol=sym,
                        signal_date=current_date,
                        buy_date=current_date,
                        buy_price=buy_price,
                        shares=shares,
                        invested_amt=invested_amt,
                        target_price=tgt_price,
                        status="OPEN",
                        tranche_type=t_type
                    )
                    trade_id_seq += 1

                    open_tranches[sym].append(new_tranche)
                    all_trades.append(new_tranche)
                    currently_active_stocks.add(sym)
                    deployed_cash_flows.append((current_date, -invested_amt))

        # C. Idle Capital Interest (5% p.a.)
        if current_date >= start_dt_cutoff:
            if prev_idle_date is not None:
                days_diff = (current_date - prev_idle_date).days
                if days_diff > 0:
                    daily_interest = untouched_cash_buffer * (0.05 / 365.25) * days_diff
                    cumulative_idle_interest += daily_interest
            prev_idle_date = current_date

        # D. Portfolio Peak & Drawdown
        if current_date >= start_dt_cutoff:
            tot_invested = sum(tr.shares * tr.buy_price for trs in open_tranches.values() for tr in trs)
            tot_mkt_val = sum(tr.shares * last_known_close.get(s, tr.buy_price) for s, trs in open_tranches.items() for tr in trs)
            day_unrealized = tot_mkt_val - tot_invested
            current_portfolio_value = config.total_capital + cumulative_realized_profit + cumulative_idle_interest + cumulative_dividend_income + day_unrealized

            if current_portfolio_value > peak_portfolio_value:
                peak_portfolio_value = current_portfolio_value
            elif peak_portfolio_value > 0:
                dd_pct = ((peak_portfolio_value - current_portfolio_value) / peak_portfolio_value) * 100.0
                if dd_pct > max_drawdown_pct:
                    max_drawdown_pct = dd_pct

    # End-of-backtest valuation
    final_date = all_dates[-1] if all_dates else start_dt_cutoff
    final_invested = sum(tr.shares * tr.buy_price for trs in open_tranches.values() for tr in trs)
    final_market_value = sum(tr.shares * last_known_close.get(s, tr.buy_price) for s, trs in open_tranches.items() for tr in trs)
    final_unrealized_pnl = round(final_market_value - final_invested, 2)

    total_realized_all = cumulative_realized_profit + cumulative_idle_interest + cumulative_dividend_income
    ending_capital = config.total_capital + total_realized_all
    ending_tranche_amt = ending_capital / float(max_active_stocks * config.num_parts) if (max_active_stocks * config.num_parts) > 0 else tranche_capital

    total_net_profit = total_realized_all + final_unrealized_pnl
    total_ret_pct = round((total_net_profit / config.total_capital) * 100.0, 2)

    portfolio_cash_flows.append((final_date, config.total_capital + total_net_profit))
    deployed_cash_flows.append((final_date, final_market_value))

    port_xirr = calculate_xirr(portfolio_cash_flows)
    dep_xirr = calculate_xirr(deployed_cash_flows)

    completed = [t for t in all_trades if t.status == "CLOSED"]
    opened = [t for t in all_trades if t.status == "OPEN"]
    winning = [t for t in completed if t.realized_pnl > 0]
    win_rate = (len(winning) / len(completed) * 100.0) if completed else 0.0

    return PortfolioBacktestResult(
        total_capital=config.total_capital,
        max_active_stocks=max_active_stocks,
        num_parts=config.num_parts,
        total_realized_profit=round(total_realized_all, 2),
        realized_trade_profit=round(cumulative_realized_profit, 2),
        total_magic_profit=0.0,
        idle_capital_interest=round(cumulative_idle_interest, 2),
        dividend_income=round(cumulative_dividend_income, 2),
        unrealized_pnl=final_unrealized_pnl,
        total_portfolio_return_pct=total_ret_pct,
        portfolio_xirr_pct=round(port_xirr, 2),
        deployed_xirr_pct=round(dep_xirr, 2),
        max_drawdown_pct=round(max_drawdown_pct, 2),
        win_rate_pct=round(win_rate, 2),
        total_trades=len(all_trades),
        completed_trades=len(completed),
        open_trades=len(opened),
        ending_overall_capital=round(ending_capital, 2),
        ending_tranche_amount=round(ending_tranche_amt, 2),
        stock_summaries=[],
        trades=all_trades,
        magic_events=[],
        dividend_events=all_dividend_events
    )

def main():
    print("=" * 80)
    print("RUNNING SHARED-CAPITAL UNIVERSE BACKTEST (WEB ENGINE PARAMETERS)")
    print("Universe: Nifty 50 | Capital: Rs. 50 Lakhs | Max Concurrent: 50 | 4 Tranches")
    print("Period: 01-Jan-2020 to 17-Oct-2026 (6.8 Years)")
    print("=" * 80)

    cfg = BacktestConfig(
        start_date="2020-01-01",
        end_date="2026-10-17",
        total_capital=5000000.0,
        num_parts=4,
        target_pct=0.05,
        bullish_min_return_pct=15.0,
        enable_bullish_combo=True,
        enable_magic_profit=False,
        enable_compounding=True
    )

    symbols = get_universe_symbols("Nifty 50")

    print("\n1. Running WITHOUT CAR (Baseline Web Engine)...")
    base_res = run_portfolio_universe_simulation(symbols, cfg, max_active_stocks=50, db_path=DEFAULT_DB_PATH)
    print("Baseline simulation completed.")

    print("\n2. Running WITH CAR Filter (10-Day Consecutive Rise Required)...")
    car_res = run_portfolio_universe_simulation_car(symbols, cfg, max_active_stocks=50, db_path=DEFAULT_DB_PATH)
    print("CAR simulation completed.")

    print("\n" + "=" * 96)
    print(f"{'PARAMETER / METRIC':<36} | {'WITH CAR FILTER':<26} | {'WITHOUT CAR (BASELINE)':<26}")
    print("=" * 96)
    
    rows = [
        ("Total Portfolio Return Amount", f"Rs. {car_res.total_realized_profit + car_res.unrealized_pnl:,.2f}", f"Rs. {base_res.total_realized_profit + base_res.unrealized_pnl:,.2f}"),
        ("Total Portfolio Return %", f"+{car_res.total_portfolio_return_pct:.2f}%", f"+{base_res.total_portfolio_return_pct:.2f}%"),
        ("Total Realized Profit", f"Rs. {car_res.total_realized_profit:,.2f}", f"Rs. {base_res.total_realized_profit:,.2f}"),
        ("  - Trade Realized Profit", f"Rs. {car_res.realized_trade_profit:,.2f}", f"Rs. {base_res.realized_trade_profit:,.2f}"),
        ("  - Idle Interest (5% p.a.)", f"Rs. {car_res.idle_capital_interest:,.2f}", f"Rs. {base_res.idle_capital_interest:,.2f}"),
        ("  - Dividend Income", f"Rs. {car_res.dividend_income:,.2f}", f"Rs. {base_res.dividend_income:,.2f}"),
        ("Unrealized Open P&L", f"Rs. {car_res.unrealized_pnl:,.2f}", f"Rs. {base_res.unrealized_pnl:,.2f}"),
        ("Trades (Closed / Total)", f"{car_res.completed_trades} / {car_res.total_trades}", f"{base_res.completed_trades} / {base_res.total_trades}"),
        ("  - Bullish Tranches", f"{sum(1 for t in car_res.trades if t.tranche_type == 'BULLISH')}", f"{sum(1 for t in base_res.trades if t.tranche_type == 'BULLISH')}"),
        ("  - Bearish Dip Tranches", f"{sum(1 for t in car_res.trades if t.tranche_type == 'BEARISH')}", f"{sum(1 for t in base_res.trades if t.tranche_type == 'BEARISH')}"),
        ("Deployed XIRR %", f"{car_res.deployed_xirr_pct:.2f}%", f"{base_res.deployed_xirr_pct:.2f}%"),
        ("Portfolio XIRR %", f"{car_res.portfolio_xirr_pct:.2f}%", f"{base_res.portfolio_xirr_pct:.2f}%"),
        ("Max Drawdown %", f"{car_res.max_drawdown_pct:.2f}%", f"{base_res.max_drawdown_pct:.2f}%"),
        ("Ending Overall Capital", f"Rs. {car_res.ending_overall_capital:,.2f}", f"Rs. {base_res.ending_overall_capital:,.2f}"),
        ("Ending Tranche Buy Amount", f"Rs. {car_res.ending_tranche_amount:,.2f}", f"Rs. {base_res.ending_tranche_amount:,.2f}")
    ]

    for label, c_val, b_val in rows:
        print(f"{label:<36} | {c_val:<26} | {b_val:<26}")
    print("=" * 96)

if __name__ == "__main__":
    main()
