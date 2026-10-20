"""Core event-driven backtesting engine for the 5-Tranche Weekly Breakout Strategy."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Set
import numpy as np
import pandas as pd

from config import BacktestConfig

@dataclass
class MagicProfitEvent:
    event_id: int
    date: pd.Timestamp
    trade_id: int
    slot_id: int
    buy_date: pd.Timestamp
    buy_price: float
    rolling_20d_low: float
    close_price: float
    loss_pct: float
    profit_credit: float = 500.0
    open_tranches_in_loss: str = ""

@dataclass
class DividendEvent:
    event_id: int
    ex_date: pd.Timestamp
    symbol: str
    trade_id: int
    slot_id: int
    buy_date: pd.Timestamp
    shares: int
    dividend_per_share: float
    total_payout: float

@dataclass
class Tranche:
    trade_id: int
    slot_id: int                    # 1 to 5
    symbol: str
    signal_date: pd.Timestamp       # Friday close date of the signal
    buy_date: pd.Timestamp          # Actual fill date next week
    buy_price: float
    shares: int
    invested_amt: float
    target_price: float             # buy_price * 1.05
    sell_date: Optional[pd.Timestamp] = None
    sell_price: Optional[float] = None
    realized_pnl: Optional[float] = None
    return_pct: Optional[float] = None
    holding_days: Optional[int] = None
    status: str = "OPEN"            # "OPEN" or "CLOSED"
    magic_profit_total: float = 0.0
    magic_profit_count: int = 0
    magic_dates: List[pd.Timestamp] = field(default_factory=list)
    last_magic_date: Optional[pd.Timestamp] = None
    dividend_total: float = 0.0
    tranche_type: str = "BEARISH"   # "BEARISH" or "BULLISH"
    required_return_pct: Optional[float] = None
    achieved_return_pct: Optional[float] = None
    years_held: Optional[float] = None

@dataclass
class PendingOrder:
    signal_date: pd.Timestamp
    ceiling: float
    ref_close: float
    target_year: int
    target_week: int

@dataclass
class MonthlySummary:
    year_mmm: str                    # e.g. "2023-Jan"
    trade_realized_profit: float     # Realized trade profit
    magic_profit: float              # Magic profit
    dividend_income: float           # Dividend income
    idle_interest: float             # Idle cash interest
    total_realized_profit: float     # Sum of all realized profits
    month_end_unrealized: float      # Unrealized P&L at month end
    net_monthly_pnl: float           # Total realized + change in unrealized
    max_capital_blocked: float       # Max invested amount in open trades
    monthly_return_pct: float        # (net_monthly_pnl / total_capital) * 100
    max_drawdown_pct: float          # Peak drawdown % during the month
    month_end_drawdown_pct: float = 0.0 # Drawdown % at month end
    idle_unused_cash: float = 0.0    # Idle unused cash at month end

@dataclass
class BacktestResult:
    symbol: str
    initial_capital: float
    total_realized_profit: float
    total_trades: int
    completed_trades: int
    open_trades: int
    win_rate_pct: float
    max_active_tranches: int
    total_invested_capital: float
    avg_holding_days: float
    open_positions_invested: float
    open_positions_current_value: float
    unrealized_pnl: float
    total_portfolio_return_pct: float
    max_drawdown_pct: float = 0.0
    portfolio_xirr_pct: float = 0.0
    deployed_xirr_pct: float = 0.0
    realized_trade_profit: float = 0.0
    total_magic_profit: float = 0.0
    idle_capital_interest: float = 0.0
    dividend_income: float = 0.0
    ending_overall_capital: float = 0.0
    ending_tranche_amount: float = 0.0
    dividend_events: List[DividendEvent] = field(default_factory=list)
    magic_events: List[MagicProfitEvent] = field(default_factory=list)
    trades: List[Tranche] = field(default_factory=list)
    monthly_summaries: List[MonthlySummary] = field(default_factory=list)

def calculate_xirr(cash_flows: List[tuple], guess: float = 0.1, tol: float = 1e-6, max_iter: int = 100) -> float:
    """
    Calculates annualized Extended Internal Rate of Return (XIRR) in %
    from a list of (date, amount) tuples.
    Returns float rounded to 2 decimals (e.g. 15.25 for 15.25%).
    """
    if not cash_flows or len(cash_flows) < 2:
        return 0.0
    dates = [pd.to_datetime(d[0]) for d in cash_flows]
    amounts = [float(d[1]) for d in cash_flows]
    
    # Must have at least one positive and one negative cash flow
    has_pos = any(a > 0 for a in amounts)
    has_neg = any(a < 0 for a in amounts)
    if not (has_pos and has_neg):
        return 0.0
        
    d0 = min(dates)
    years = np.array([(d - d0).total_seconds() / (365.25 * 86400) for d in dates])
    amounts = np.array(amounts)
    
    r = guess
    for _ in range(max_iter):
        denom = (1.0 + r) ** years
        f_val = np.sum(amounts / denom)
        f_prime = np.sum(-years * amounts / ((1.0 + r) ** (years + 1.0)))
        if abs(f_prime) < 1e-12:
            break
        r_new = r - f_val / f_prime
        if abs(r_new - r) < tol:
            return round(float(r_new) * 100.0, 2)
        r = r_new
        if r <= -0.999:
            r = -0.99
            
    # Binary search fallback if Newton-Raphson did not converge
    low, high = -0.99, 10.0
    for _ in range(100):
        mid = (low + high) / 2.0
        f_mid = np.sum(amounts / ((1.0 + mid) ** years))
        if abs(f_mid) < tol:
            return round(float(mid) * 100.0, 2)
        f_low = np.sum(amounts / ((1.0 + low) ** years))
        if (f_low > 0 and f_mid > 0) or (f_low < 0 and f_mid < 0):
            low = mid
        else:
            high = mid
    return round(float(mid) * 100.0, 2)

def generate_monthly_summaries(
    daily_snapshots: List[dict],
    total_capital: float
) -> List[MonthlySummary]:
    """Aggregates daily performance snapshots into calendar monthly summary records."""
    if not daily_snapshots:
        return []
    
    from collections import OrderedDict
    months_map = OrderedDict()
    for s in daily_snapshots:
        ym = (s["date"].year, s["date"].month)
        if ym not in months_map:
            months_map[ym] = []
        months_map[ym].append(s)
        
    monthly_list = []
    prev_unrealized = 0.0
    for (yr, mo), snaps in months_map.items():
        dt_sample = snaps[0]["date"]
        year_mmm = dt_sample.strftime("%Y-%b")
        t_realized = sum(s["trade_realized"] for s in snaps)
        m_profit = sum(s["magic_profit"] for s in snaps)
        div_inc = sum(s["dividend"] for s in snaps)
        idle_int = sum(s["idle_interest"] for s in snaps)
        tot_realized = t_realized + m_profit + div_inc + idle_int
        
        m_end_unrealized = snaps[-1]["unrealized_pnl"]
        delta_unrealized = m_end_unrealized - prev_unrealized
        net_monthly_pnl = tot_realized + delta_unrealized
        max_blocked = max(s["open_invested"] for s in snaps)
        ret_pct = round((tot_realized / max_blocked) * 100.0, 2) if max_blocked > 0 else 0.0
        max_dd = round(max(s["drawdown_pct"] for s in snaps), 2)
        end_dd = round(snaps[-1]["drawdown_pct"], 2)
        if "idle_cash" in snaps[-1]:
            m_end_idle_cash = snaps[-1]["idle_cash"]
        else:
            m_end_idle_cash = max(0.0, total_capital - snaps[-1].get("open_invested", max_blocked))
        
        monthly_list.append(MonthlySummary(
            year_mmm=year_mmm,
            trade_realized_profit=round(t_realized, 2),
            magic_profit=round(m_profit, 2),
            dividend_income=round(div_inc, 2),
            idle_interest=round(idle_int, 2),
            total_realized_profit=round(tot_realized, 2),
            month_end_unrealized=round(m_end_unrealized, 2),
            net_monthly_pnl=round(net_monthly_pnl, 2),
            max_capital_blocked=round(max_blocked, 2),
            monthly_return_pct=ret_pct,
            max_drawdown_pct=max_dd,
            month_end_drawdown_pct=end_dd,
            idle_unused_cash=round(m_end_idle_cash, 2)
        ))
        prev_unrealized = m_end_unrealized
        
    return monthly_list

def run_backtest(
    df_daily: pd.DataFrame,
    df_weekly: pd.DataFrame,
    config: BacktestConfig,
    symbol: str = "STOCK",
    df_dividends: Optional[pd.DataFrame] = None
) -> BacktestResult:
    """
    Simulates the 5-tranche weekly breakout strategy day-by-day.
    Enforces maximum 5 active tranches, discrete share sizing, +5% target exit,
    and optional risk management rules (stop loss, time exit, anti-clustering).
    """
    df_d = df_daily.copy().sort_values("Date").reset_index(drop=True)
    df_w = df_weekly.copy().sort_values("Week_Start").reset_index(drop=True)
    
    # Map calendar week end dates and signals
    iso_daily = df_d["Date"].dt.isocalendar()
    df_d["iso_year"] = iso_daily.year
    df_d["iso_week"] = iso_daily.week
    
    # Build lookup of weekly rows by (iso_year, iso_week)
    weekly_lookup: Dict[tuple, pd.Series] = {}
    weekly_keys_list = []
    for _, w_row in df_w.iterrows():
        key = (int(w_row["iso_year"]), int(w_row["iso_week"]))
        weekly_lookup[key] = w_row
        weekly_keys_list.append(key)
        
    # Precompute rolling 20-day low (upto 1 day ago) for magic profit tracking
    df_d["rolling_20dl"] = df_d["Low"].shift(1).rolling(config.magic_profit_lookback_days, min_periods=config.magic_profit_lookback_days).min()
    start_dt_cutoff = pd.to_datetime(config.start_date)

    # State tracking
    active_tranches: Dict[int, Tranche] = {}  # slot_id -> Tranche
    available_slots: Set[int] = set(range(1, config.num_parts + 1))
    all_trades: List[Tranche] = []
    trade_counter = 0
    max_slots_used = 0
    pending_order: Optional[PendingOrder] = None
    
    # Magic profit tracking
    magic_events: List[MagicProfitEvent] = []
    magic_event_counter = 0
    total_magic_profit_accum = 0.0
    last_stock_magic_date: Optional[pd.Timestamp] = None
    is_tracking_20w: bool = False

    # Cold start: initialize tracking state from weekly history prior to start_dt_cutoff if available
    if config.use_20w_low_tracking or config.enable_bullish_combo:
        prior_w = df_w[df_w["Week_End"] < start_dt_cutoff].sort_values("Week_End")
        for _, pw_row in prior_w.iterrows():
            pw_c = float(pw_row["Close"])
            pw_r20l = pw_row.get("rolling_20w_low")
            pw_r20h = pw_row.get("rolling_20w_high")
            if not is_tracking_20w:
                if pd.notna(pw_r20l) and pw_c < float(pw_r20l):
                    is_tracking_20w = True
            if pd.notna(pw_r20h) and pw_c > float(pw_r20h):
                is_tracking_20w = False

    # Dividend distribution tracking
    dividend_events: List[DividendEvent] = []
    dividend_id_seq = 1
    total_dividend_accum = 0.0
    dividends_dict: Dict[pd.Timestamp, float] = {}
    if df_dividends is not None and not df_dividends.empty:
        for _, d_row in df_dividends.iterrows():
            d_date = pd.to_datetime(d_row["Date"]).normalize()
            dividends_dict[d_date] = float(d_row["Dividend"])

    # Portfolio equity curve tracking for max drawdown calculation
    portfolio_equity_series = []
    daily_snapshots = []
    peak_portfolio_equity = config.total_capital
    available_cash = config.total_capital
    cumulative_realized_profit = 0.0
    total_idle_interest_accum = 0.0
    prev_idle_date: Optional[pd.Timestamp] = None
    untouched_cash_buffer = config.tranche_capital

    # Identify last trading day for each week in the daily data
    week_last_days: Dict[tuple, pd.Timestamp] = {}
    for (yr, wk), group in df_d.groupby(["iso_year", "iso_week"], sort=False):
        week_last_days[(int(yr), int(wk))] = group["Date"].max()

    for idx, day in df_d.iterrows():
        day_trade_realized = 0.0
        day_magic_profit = 0.0
        day_dividend = 0.0
        curr_yr = int(day["iso_year"])
        curr_wk = int(day["iso_week"])
        curr_week_key = (curr_yr, curr_wk)
        day_date = day["Date"]
        day_open = float(day["Open"])
        day_high = float(day["High"])
        day_low = float(day["Low"])
        day_close = float(day["Close"])

        # Track max concurrent active tranches
        if len(active_tranches) > max_slots_used:
            max_slots_used = len(active_tranches)

        # -----------------------------------------------------------------
        # STEP 0: Check Dividend Distributions on Open Tranches (T-2 Rule)
        # -----------------------------------------------------------------
        day_normalized = pd.to_datetime(day_date).normalize()
        if day_normalized in dividends_dict and active_tranches:
            div_per_share = dividends_dict[day_normalized]
            # T-2 Rule: stock must have been purchased at least 2 trading days before the ex-dividend date
            if idx >= 2:
                t_minus_2_date = pd.to_datetime(df_d.loc[idx - 2, "Date"]).normalize()
            else:
                t_minus_2_date = day_normalized - pd.Timedelta(days=2)

            for slot_id in sorted(active_tranches.keys()):
                tranche = active_tranches[slot_id]
                tranche_buy_norm = pd.to_datetime(tranche.buy_date).normalize()
                if tranche_buy_norm <= t_minus_2_date:
                    payout = round(tranche.shares * div_per_share, 2)
                    tranche.dividend_total += payout
                    total_dividend_accum += payout
                    day_dividend += payout
                    available_cash += payout

                    div_ev = DividendEvent(
                        event_id=dividend_id_seq,
                        ex_date=day_date,
                        symbol=symbol,
                        trade_id=tranche.trade_id,
                        slot_id=slot_id,
                        buy_date=tranche.buy_date,
                        shares=tranche.shares,
                        dividend_per_share=div_per_share,
                        total_payout=payout
                    )
                    dividend_events.append(div_ev)
                    dividend_id_seq += 1

        # -----------------------------------------------------------------
        # STEP 1: Check Exits on Open Tranches (Target, Stop Loss, Time Exit)
        # -----------------------------------------------------------------
        for slot_id in list(active_tranches.keys()):
            tranche = active_tranches[slot_id]
            is_subsequent_day = (day_date > tranche.buy_date)
            is_same_day_target = (day_date == tranche.buy_date and day_high >= tranche.target_price)
            
            if is_subsequent_day or is_same_day_target:
                exited = False
                sell_price = None
                
                # 1. Target Hit (+5%) - only active if weekly trailing exit is NOT used and for BEARISH tranches
                if not config.use_weekly_trailing_exit:
                    if tranche.tranche_type == "BEARISH" and day_high >= tranche.target_price:
                        sell_price = tranche.target_price
                        exited = True
                
                # 2. Fixed Stop Loss Hit (if configured)
                if not exited and config.stop_loss_pct is not None and day_low <= tranche.buy_price * (1.0 - config.stop_loss_pct):
                    sell_price = round(tranche.buy_price * (1.0 - config.stop_loss_pct), 2)
                    exited = True
                # 3. Time-Based Exit Hit (if configured)
                elif not exited and config.max_holding_days is not None and (day_date - tranche.buy_date).days >= config.max_holding_days:
                    sell_price = day_close
                    exited = True
                    
                if exited:
                    tranche.sell_date = day_date
                    tranche.sell_price = sell_price
                    tranche.realized_pnl = round((tranche.sell_price - tranche.buy_price) * tranche.shares, 2)
                    tranche.return_pct = round(((tranche.sell_price - tranche.buy_price) / tranche.buy_price) * 100.0, 2)
                    tranche.holding_days = (tranche.sell_date - tranche.buy_date).days
                    tranche.status = "CLOSED"
                    
                    cumulative_realized_profit += tranche.realized_pnl
                    day_trade_realized += tranche.realized_pnl
                    available_cash += tranche.invested_amt + tranche.realized_pnl
                    
                    del active_tranches[slot_id]
                    available_slots.add(slot_id)

        # -----------------------------------------------------------------
        # STEP 1B: Magic Profit Check on Open Tranches in Loss (Added ONCE for all open tranches)
        # -----------------------------------------------------------------
        if config.enable_magic_profit and active_tranches:
            r20dl = day.get("rolling_20dl")
            if pd.notna(r20dl) and day_close < float(r20dl):
                # Identify all open tranches currently in loss (close < buy_price)
                tranches_in_loss = [t for t in active_tranches.values() if day_close < t.buy_price]
                if tranches_in_loss:
                    # Cooldown check: added once across all open tranches with 30-day cooldown
                    if last_stock_magic_date is None or (day_date - last_stock_magic_date).days >= config.magic_profit_cooldown_days:
                        magic_event_counter += 1
                        available_cash += config.magic_profit_amount
                        total_magic_profit_accum += config.magic_profit_amount
                        day_magic_profit += config.magic_profit_amount
                        last_stock_magic_date = day_date

                        # Attribute the single 500 credit to the oldest open tranche in loss
                        primary_tranche = min(tranches_in_loss, key=lambda t: t.buy_date)
                        primary_tranche.magic_profit_total += config.magic_profit_amount
                        primary_tranche.magic_profit_count += 1

                        # Record the event date on all open tranches currently in loss
                        for t in tranches_in_loss:
                            t.magic_dates.append(day_date)

                        loss_pct = round(((day_close - primary_tranche.buy_price) / primary_tranche.buy_price) * 100.0, 2)
                        loss_slots_str = ", ".join(f"Slot {t.slot_id} (Trade {t.trade_id})" for t in tranches_in_loss)

                        magic_events.append(MagicProfitEvent(
                            event_id=magic_event_counter,
                            date=day_date,
                            trade_id=primary_tranche.trade_id,
                            slot_id=primary_tranche.slot_id,
                            buy_date=primary_tranche.buy_date,
                            buy_price=primary_tranche.buy_price,
                            rolling_20d_low=round(float(r20dl), 2),
                            close_price=day_close,
                            loss_pct=loss_pct,
                            profit_credit=config.magic_profit_amount,
                            open_tranches_in_loss=loss_slots_str
                        ))

        # -----------------------------------------------------------------
        # STEP 2: Evaluate Pending Buy Order in Current Week
        # -----------------------------------------------------------------
        if pending_order is not None:
            # Check if pending order has expired past its target week
            if (curr_yr, curr_wk) > (pending_order.target_year, pending_order.target_week):
                pending_order = None
            elif (curr_yr, curr_wk) == (pending_order.target_year, pending_order.target_week):
                # We are in the execution week: check if low <= ceiling and a slot is free
                if day_date >= start_dt_cutoff and len(active_tranches) < config.num_parts and len(available_slots) > 0:
                    if day_low <= pending_order.ceiling:
                        candidate_buy_price = round(min(day_open, pending_order.ceiling), 2)
                        
                        # Anti-clustering check if configured and other tranches are open
                        allow_entry = True
                        if active_tranches and (config.min_spacing_up_pct > 0.0 or config.min_spacing_down_pct > 0.0):
                            existing_prices = [t.buy_price for t in active_tranches.values()]
                            max_p = max(existing_prices)
                            min_p = min(existing_prices)
                            up_ok = (config.min_spacing_up_pct > 0.0 and candidate_buy_price >= max_p * (1.0 + config.min_spacing_up_pct))
                            down_ok = (config.min_spacing_down_pct > 0.0 and candidate_buy_price <= min_p * (1.0 - config.min_spacing_down_pct))
                            if not (up_ok or down_ok):
                                allow_entry = False

                        # Check buy_only_below_last_tranche condition at fill time
                        if allow_entry and config.buy_only_below_last_tranche and active_tranches:
                            last_active = max(active_tranches.values(), key=lambda t: t.trade_id)
                            if candidate_buy_price >= last_active.buy_price:
                                allow_entry = False

                        if allow_entry:
                            buy_price = candidate_buy_price
                            slot_id = min(available_slots)
                            available_slots.remove(slot_id)
                            
                            # Dynamic compounding tranche capital
                            if getattr(config, "enable_compounding", True):
                                current_capital = config.total_capital + cumulative_realized_profit + total_magic_profit_accum + total_dividend_accum
                                dyn_tranche_capital = current_capital / float(config.num_parts)
                            else:
                                dyn_tranche_capital = config.tranche_capital

                            shares = int(dyn_tranche_capital // buy_price)
                            if shares > 0:
                                trade_counter += 1
                                invested = round(shares * buy_price, 2)
                                target_price = round(buy_price * (1.0 + config.target_pct), 2)
                                
                                new_tranche = Tranche(
                                    trade_id=trade_counter,
                                    slot_id=slot_id,
                                    symbol=symbol,
                                    signal_date=pending_order.signal_date,
                                    buy_date=day_date,
                                    buy_price=buy_price,
                                    shares=shares,
                                    invested_amt=invested,
                                    target_price=target_price,
                                    status="OPEN"
                                )
                                active_tranches[slot_id] = new_tranche
                                all_trades.append(new_tranche)
                                available_cash -= invested
                                
                                if len(active_tranches) > max_slots_used:
                                    max_slots_used = len(active_tranches)
                                    
                            pending_order = None

        # -----------------------------------------------------------------
        # STEP 3: Weekly Close Actions (Trailing Exit + Breakout Signal)
        # -----------------------------------------------------------------
        week_last_date = week_last_days.get(curr_week_key)
        if week_last_date is not None and day_date == week_last_date:
            w_row = weekly_lookup.get(curr_week_key)
            
            # Action 3A: Weekly Trailing Exit (Close < Prev Week Low AND in profit)
            if config.use_weekly_trailing_exit and w_row is not None:
                prev_wk_low = float(w_row.get("prev_week_low", float("-inf")))
                if prev_wk_low > float("-inf"):
                    for slot_id in list(active_tranches.keys()):
                        tranche = active_tranches[slot_id]
                        # Trailing condition: Week Close < Prev Week Low AND Week Close > Buy Price (in profit)
                        if day_close < prev_wk_low and day_close > tranche.buy_price:
                            tranche.sell_date = day_date
                            tranche.sell_price = day_close
                            tranche.realized_pnl = round((tranche.sell_price - tranche.buy_price) * tranche.shares, 2)
                            tranche.return_pct = round(((tranche.sell_price - tranche.buy_price) / tranche.buy_price) * 100.0, 2)
                            tranche.holding_days = (tranche.sell_date - tranche.buy_date).days
                            tranche.status = "CLOSED"
                            
                            cumulative_realized_profit += tranche.realized_pnl
                            day_trade_realized += tranche.realized_pnl
                            available_cash += tranche.invested_amt + tranche.realized_pnl
                            
                            del active_tranches[slot_id]
                            available_slots.add(slot_id)

            # Action 3B: 20-Week Low Tracking + Bullish Momentum Combo Execution
            if (config.use_20w_low_tracking or config.enable_bullish_combo) and w_row is not None:
                r_20wl = w_row.get("rolling_20w_low")
                r_20wh = w_row.get("rolling_20w_high")

                # 1. Bullish Tranche Exits: evaluated at Friday close
                # Sold ONLY when:
                # Condition 1: Weekly close < 20W low
                # Condition 2: Simple annualized return >= bullish_min_return_pct
                if pd.notna(r_20wl) and day_close < float(r_20wl):
                    for slot_id in list(active_tranches.keys()):
                        tranche = active_tranches[slot_id]
                        if tranche.tranche_type == "BULLISH":
                            days_held = (day_date - tranche.buy_date).days
                            years_held = max(days_held / 365.25, 0.0)
                            req_profit_pct = config.bullish_min_return_pct * years_held
                            achieved_pct = ((day_close - tranche.buy_price) / tranche.buy_price) * 100.0

                            if achieved_pct >= req_profit_pct:
                                tranche.sell_date = day_date
                                tranche.sell_price = day_close
                                tranche.realized_pnl = round((day_close - tranche.buy_price) * tranche.shares, 2)
                                tranche.return_pct = round(achieved_pct, 2)
                                tranche.required_return_pct = round(req_profit_pct, 2)
                                tranche.achieved_return_pct = round(achieved_pct, 2)
                                tranche.years_held = round(years_held, 2)
                                tranche.holding_days = days_held
                                tranche.status = "CLOSED"

                                cumulative_realized_profit += tranche.realized_pnl
                                day_trade_realized += tranche.realized_pnl
                                available_cash += tranche.invested_amt + tranche.realized_pnl

                                del active_tranches[slot_id]
                                available_slots.add(slot_id)

                # 2. Bearish Activation: Stock closes below rolling 20-week low
                if not is_tracking_20w:
                    if pd.notna(r_20wl) and day_close < float(r_20wl):
                        is_tracking_20w = True

                # 3. 20-Week High Breakout
                if pd.notna(r_20wh) and day_close > float(r_20wh):
                    # Deactivate Bearish dip tracking
                    is_tracking_20w = False

                    # Enter dedicated Bullish tranche if enabled and none currently open
                    if config.enable_bullish_combo and day_date >= start_dt_cutoff:
                        has_open_bullish = any(t.tranche_type == "BULLISH" for t in active_tranches.values())
                        if not has_open_bullish and len(active_tranches) < config.num_parts and len(available_slots) > 0:
                            slot_id = min(available_slots)
                            available_slots.remove(slot_id)

                            buy_price = round(day_close, 2)
                            if getattr(config, "enable_compounding", True):
                                current_capital = config.total_capital + cumulative_realized_profit + total_magic_profit_accum + total_dividend_accum
                                dyn_tranche_capital = current_capital / float(config.num_parts)
                            else:
                                dyn_tranche_capital = config.tranche_capital

                            shares = int(dyn_tranche_capital // buy_price)
                            if shares > 0:
                                trade_counter += 1
                                invested = round(shares * buy_price, 2)
                                # Bullish tranche does not have a 5% target; it exits on 20W low breakdown with min return
                                target_price = float("inf")

                                new_tranche = Tranche(
                                    trade_id=trade_counter,
                                    slot_id=slot_id,
                                    symbol=symbol,
                                    signal_date=day_date,
                                    buy_date=day_date,
                                    buy_price=buy_price,
                                    shares=shares,
                                    invested_amt=invested,
                                    target_price=target_price,
                                    status="OPEN",
                                    tranche_type="BULLISH"
                                )
                                active_tranches[slot_id] = new_tranche
                                all_trades.append(new_tranche)
                                available_cash -= invested

                                if len(active_tranches) > max_slots_used:
                                    max_slots_used = len(active_tranches)

                # 4. Bearish Dip-Buying Tranches (when tracking 20W low breakdown)
                elif is_tracking_20w:
                    # Bearish tranche capacity: N - 1 if combo enabled, else N
                    max_bearish = (config.num_parts - 1) if config.enable_bullish_combo else config.num_parts
                    open_bearish = sum(1 for t in active_tranches.values() if t.tranche_type == "BEARISH")

                    prev_wk_h = float(w_row.get("prev_week_high", float("inf")))
                    if day_close > prev_wk_h and open_bearish < max_bearish:
                        if day_date >= start_dt_cutoff and len(active_tranches) < config.num_parts and len(available_slots) > 0:
                            slot_id = min(available_slots)
                            available_slots.remove(slot_id)

                            buy_price = round(day_close, 2)
                            if getattr(config, "enable_compounding", True):
                                current_capital = config.total_capital + cumulative_realized_profit + total_magic_profit_accum + total_dividend_accum
                                dyn_tranche_capital = current_capital / float(config.num_parts)
                            else:
                                dyn_tranche_capital = config.tranche_capital

                            shares = int(dyn_tranche_capital // buy_price)
                            if shares > 0:
                                trade_counter += 1
                                invested = round(shares * buy_price, 2)
                                target_price = round(buy_price * (1.0 + config.target_pct), 2)

                                new_tranche = Tranche(
                                    trade_id=trade_counter,
                                    slot_id=slot_id,
                                    symbol=symbol,
                                    signal_date=day_date,
                                    buy_date=day_date,
                                    buy_price=buy_price,
                                    shares=shares,
                                    invested_amt=invested,
                                    target_price=target_price,
                                    status="OPEN",
                                    tranche_type="BEARISH"
                                )
                                active_tranches[slot_id] = new_tranche
                                all_trades.append(new_tranche)
                                available_cash -= invested

                                if len(active_tranches) > max_slots_used:
                                    max_slots_used = len(active_tranches)

            # Action 3C: Standard Breakout Signal Check for Next Week (Base and variants)
            elif not config.use_20w_low_tracking and w_row is not None and bool(w_row.get("breakout_signal", False)):
                if day_date >= start_dt_cutoff and len(active_tranches) < config.num_parts:
                    allow_schedule = True
                    # If buy_only_below_last_tranche is enabled, ensure signal close is below last bought tranche buy price
                    if config.buy_only_below_last_tranche and active_tranches:
                        last_active = max(active_tranches.values(), key=lambda t: t.trade_id)
                        if float(w_row["reference_close"]) >= last_active.buy_price:
                            allow_schedule = False

                    if allow_schedule:
                        try:
                            curr_pos = weekly_keys_list.index(curr_week_key)
                            if curr_pos + 1 < len(weekly_keys_list):
                                next_yr, next_wk = weekly_keys_list[curr_pos + 1]
                                pending_order = PendingOrder(
                                    signal_date=day_date,
                                    ceiling=float(w_row["entry_ceiling"]),
                                    ref_close=float(w_row["reference_close"]),
                                    target_year=next_yr,
                                    target_week=next_wk
                                )
                        except ValueError:
                            pass

        # Daily Equity Tracking for Maximum Drawdown & Idle Capital Interest
        if day_date >= start_dt_cutoff:
            days_elapsed = (day_date - prev_idle_date).days if prev_idle_date is not None else 1
            open_invested_cash = sum(t.invested_amt for t in active_tranches.values())
            if getattr(config, "enable_compounding", True):
                current_overall_capital = config.total_capital + cumulative_realized_profit + total_magic_profit_accum + total_dividend_accum
                dyn_tranche_cap = current_overall_capital / float(config.num_parts)
                untouched_buffer = dyn_tranche_cap
                idle_cash = max(0.0, current_overall_capital - open_invested_cash)
            else:
                untouched_buffer = untouched_cash_buffer
                idle_cash = max(0.0, config.total_capital - open_invested_cash)

            eligible_idle = max(0.0, idle_cash - untouched_buffer)
            daily_interest = eligible_idle * (0.05 / 365.0) * days_elapsed
            total_idle_interest_accum += daily_interest
            prev_idle_date = day_date

            current_open_val = sum(t.shares * day_close for t in active_tranches.values())
            daily_equity = available_cash + current_open_val + total_idle_interest_accum
            portfolio_equity_series.append(daily_equity)

            if daily_equity > peak_portfolio_equity:
                peak_portfolio_equity = daily_equity
            day_dd = ((peak_portfolio_equity - daily_equity) / peak_portfolio_equity) * 100.0 if peak_portfolio_equity > 0 else 0.0
            unrealized_pnl_day = current_open_val - open_invested_cash
            daily_snapshots.append({
                "date": day_date,
                "trade_realized": day_trade_realized,
                "magic_profit": day_magic_profit,
                "dividend": day_dividend,
                "idle_interest": daily_interest,
                "open_invested": open_invested_cash,
                "idle_cash": idle_cash,
                "unrealized_pnl": unrealized_pnl_day,
                "daily_equity": daily_equity,
                "drawdown_pct": day_dd
            })

    # -----------------------------------------------------------------
    # Compute Final Portfolio Metrics & Max Drawdown
    # -----------------------------------------------------------------
    completed_trades_list = [t for t in all_trades if t.status == "CLOSED"]
    open_trades_list = [t for t in all_trades if t.status == "OPEN"]
    
    realized_trade_profit = round(sum(t.realized_pnl for t in completed_trades_list if t.realized_pnl is not None), 2)
    total_magic_profit = round(total_magic_profit_accum, 2)
    total_idle_interest = round(total_idle_interest_accum, 2)
    total_div_income = round(total_dividend_accum, 2)
    total_realized_profit = round(realized_trade_profit + total_magic_profit + total_idle_interest + total_div_income, 2)
    completed_count = len(completed_trades_list)
    open_count = len(open_trades_list)
    total_trades_count = len(all_trades)
    
    profitable_trades_count = sum(1 for t in completed_trades_list if (t.realized_pnl or 0) > 0)
    win_rate = (profitable_trades_count / completed_count * 100.0) if completed_count > 0 else 0.0
    total_invested_capital = round(sum(t.invested_amt for t in all_trades), 2)
    
    avg_holding_days = (
        round(sum(t.holding_days for t in completed_trades_list if t.holding_days is not None) / completed_count, 1)
        if completed_count > 0 else 0.0
    )
    
    last_close = float(df_d["Close"].iloc[-1]) if not df_d.empty else 0.0
    open_positions_invested = round(sum(t.invested_amt for t in open_trades_list), 2)
    open_positions_current_val = round(sum(t.shares * last_close for t in open_trades_list), 2)
    unrealized_pnl = round(open_positions_current_val - open_positions_invested, 2)
    
    total_portfolio_return_pct = round(((total_realized_profit + unrealized_pnl) / config.total_capital) * 100.0, 2)

    # Max Drawdown Calculation
    if portfolio_equity_series:
        eq_arr = np.array(portfolio_equity_series)
        peak_arr = np.maximum.accumulate(eq_arr)
        dd_arr = (eq_arr - peak_arr) / peak_arr * 100.0
        max_drawdown_pct = round(float(np.min(dd_arr)), 2)
    else:
        max_drawdown_pct = 0.0

    # -----------------------------------------------------------------
    # Compute XIRR (Portfolio XIRR and Deployed Capital XIRR)
    # -----------------------------------------------------------------
    first_date = start_dt_cutoff
    end_date = df_d["Date"].iloc[-1] if not df_d.empty else pd.Timestamp(config.end_date)
    terminal_portfolio_equity = round(config.total_capital + total_realized_profit + unrealized_pnl, 2)

    # 1. Portfolio XIRR (Total 100k account growth)
    c_port = [(first_date, -config.total_capital), (end_date, terminal_portfolio_equity)]
    portfolio_xirr_pct = calculate_xirr(c_port)

    # 2. Deployed Capital XIRR (Internal rate of return on cash deployed to tranches)
    c_dep = []
    for t in all_trades:
        c_dep.append((t.buy_date, -t.invested_amt))
        if t.status == "CLOSED" and t.sell_date is not None and t.sell_price is not None:
            c_dep.append((t.sell_date, round(t.shares * t.sell_price, 2)))
        elif t.status == "OPEN":
            c_dep.append((end_date, round(t.shares * last_close, 2)))
    for ev in magic_events:
        c_dep.append((ev.date, ev.profit_credit))
    for ev in dividend_events:
        c_dep.append((ev.ex_date, ev.total_payout))
    deployed_xirr_pct = calculate_xirr(c_dep)

    if getattr(config, "enable_compounding", True):
        ending_overall_capital = round(config.total_capital + total_realized_profit, 2)
        ending_tranche_amount = round(ending_overall_capital / float(config.num_parts), 2)
    else:
        ending_overall_capital = round(config.total_capital, 2)
        ending_tranche_amount = round(config.tranche_capital, 2)

    return BacktestResult(
        symbol=symbol,
        initial_capital=config.total_capital,
        total_realized_profit=total_realized_profit,
        total_trades=total_trades_count,
        completed_trades=completed_count,
        open_trades=open_count,
        win_rate_pct=win_rate,
        max_active_tranches=max_slots_used,
        total_invested_capital=total_invested_capital,
        avg_holding_days=avg_holding_days,
        open_positions_invested=open_positions_invested,
        open_positions_current_value=open_positions_current_val,
        unrealized_pnl=unrealized_pnl,
        total_portfolio_return_pct=total_portfolio_return_pct,
        max_drawdown_pct=max_drawdown_pct,
        portfolio_xirr_pct=portfolio_xirr_pct,
        deployed_xirr_pct=deployed_xirr_pct,
        realized_trade_profit=realized_trade_profit,
        total_magic_profit=total_magic_profit,
        idle_capital_interest=total_idle_interest,
        dividend_income=total_div_income,
        ending_overall_capital=ending_overall_capital,
        ending_tranche_amount=ending_tranche_amount,
        dividend_events=dividend_events,
        magic_events=magic_events,
        trades=all_trades,
        monthly_summaries=generate_monthly_summaries(daily_snapshots, config.total_capital)
    )
