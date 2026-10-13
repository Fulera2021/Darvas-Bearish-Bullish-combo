"""Multi-stock shared-capital universe portfolio backtest simulator."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Set
import logging
import pandas as pd
import numpy as np

from config import BacktestConfig
from data_loader import build_weekly_data, add_weekly_signals
from backtest_engine import Tranche, MagicProfitEvent, DividendEvent, calculate_xirr
from web.cache_manager import ensure_symbol_data, ensure_symbol_dividends, DEFAULT_DB_PATH
from web.universe_data import normalize_symbol

logger = logging.getLogger(__name__)

@dataclass
class StockSummary:
    symbol: str
    total_trades: int
    completed_trades: int
    open_trades: int
    realized_trade_profit: float
    total_magic_profit: float
    total_profit: float
    win_rate_pct: float
    open_positions_invested: float
    unrealized_pnl: float
    dividend_income: float = 0.0

@dataclass
class PortfolioBacktestResult:
    total_capital: float
    max_active_stocks: int
    num_parts: int
    total_realized_profit: float
    realized_trade_profit: float
    total_magic_profit: float
    idle_capital_interest: float = 0.0
    dividend_income: float = 0.0
    unrealized_pnl: float = 0.0
    total_portfolio_return_pct: float = 0.0
    portfolio_xirr_pct: float = 0.0
    deployed_xirr_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate_pct: float = 0.0
    total_trades: int = 0
    completed_trades: int = 0
    open_trades: int = 0
    stock_summaries: List[StockSummary] = field(default_factory=list)
    trades: List[Tranche] = field(default_factory=list)
    magic_events: List[MagicProfitEvent] = field(default_factory=list)
    dividend_events: List[DividendEvent] = field(default_factory=list)

def run_portfolio_universe_simulation(
    symbols: List[str],
    config: BacktestConfig,
    max_active_stocks: int = 5,
    db_path: str = DEFAULT_DB_PATH
) -> PortfolioBacktestResult:
    """
    Executes a shared-capital portfolio simulation across a universe of stocks.
    - Capital per stock = total_capital / max_active_stocks
    - Capital per tranche = (total_capital / max_active_stocks) / num_parts
    - Enforces maximum concurrent distinct stocks in portfolio.
    """
    if max_active_stocks <= 0:
        max_active_stocks = 5
    if config.num_parts <= 0:
        config.num_parts = 5

    stock_capital = config.total_capital / float(max_active_stocks)
    tranche_capital = stock_capital / float(config.num_parts)

    norm_symbols = [normalize_symbol(s) for s in symbols]
    
    # 1. Load and prepare daily and weekly data for all symbols
    stock_data: Dict[str, Dict[str, pd.DataFrame]] = {}
    all_dates_set: Set[pd.Timestamp] = set()

    warmup_start_dt = (pd.to_datetime(config.start_date) - pd.Timedelta(days=180)).strftime("%Y-%m-%d")
    for sym in norm_symbols:
        try:
            df_daily = ensure_symbol_data(sym, warmup_start_dt, config.end_date, db_path)
            if df_daily is None or len(df_daily) < 30:
                continue
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
            # Map daily date -> row for fast O(1) lookup
            daily_dict = {row["Date"]: row for _, row in df_daily.iterrows()}
            all_dates_set.update(df_daily["Date"])

            # Load dividends for symbol
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
            logger.warning(f"Could not load data for {sym}: {e}")
            continue

    if not stock_data:
        # Return empty result
        return PortfolioBacktestResult(
            total_capital=config.total_capital,
            max_active_stocks=max_active_stocks,
            num_parts=config.num_parts,
            total_realized_profit=0.0,
            realized_trade_profit=0.0,
            total_magic_profit=0.0,
            unrealized_pnl=0.0,
            total_portfolio_return_pct=0.0,
            portfolio_xirr_pct=0.0,
            deployed_xirr_pct=0.0,
            max_drawdown_pct=0.0,
            win_rate_pct=0.0,
            total_trades=0,
            completed_trades=0,
            open_trades=0,
            stock_summaries=[],
            trades=[],
            magic_events=[]
        )

    # Sorted list of all trading dates across the universe
    all_dates = sorted(list(all_dates_set))

    # Tracking states
    # Symbol -> List of open Tranche
    open_tranches: Dict[str, List[Tranche]] = {s: [] for s in stock_data}
    is_tracking_20w: Dict[str, bool] = {s: False for s in stock_data}
    last_magic_date: Dict[str, Optional[pd.Timestamp]] = {s: None for s in stock_data}
    last_known_close: Dict[str, float] = {s: 0.0 for s in stock_data}

    all_trades: List[Tranche] = []
    all_magic_events: List[MagicProfitEvent] = []
    trade_id_seq = 1
    magic_id_seq = 1

    # Map week_end -> list of weekly signals
    weekly_events_by_date: Dict[pd.Timestamp, List[Tuple[str, pd.Series]]] = {}
    for sym, data in stock_data.items():
        w_df = data["weekly_signals"]
        for _, w_row in w_df.iterrows():
            w_end = w_row["Week_End"]
            if w_end not in weekly_events_by_date:
                weekly_events_by_date[w_end] = []
            weekly_events_by_date[w_end].append((sym, w_row))

    start_dt_cutoff = pd.to_datetime(config.start_date)
    # Daily cash flows for XIRR
    portfolio_cash_flows: List[Tuple[pd.Timestamp, float]] = [
        (start_dt_cutoff, -config.total_capital)
    ]
    deployed_cash_flows: List[Tuple[pd.Timestamp, float]] = []

    # Portfolio peak equity tracking for Max Drawdown
    cumulative_realized_profit = 0.0
    cumulative_magic_profit = 0.0
    cumulative_idle_interest = 0.0
    cumulative_dividend_income = 0.0
    all_dividend_events: List[DividendEvent] = []
    dividend_id_seq = 1
    prev_idle_date: Optional[pd.Timestamp] = None
    untouched_cash_buffer = tranche_capital * max_active_stocks
    peak_portfolio_value = config.total_capital
    max_drawdown_pct = 0.0

    # 2. Step through each trading date
    for current_date in all_dates:
        # A0. Check Dividends across all open tranches (T-2 Rule)
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
                    if sym_idx >= 2:
                        t_minus_2_date = sym_dates[sym_idx - 2]
                    else:
                        t_minus_2_date = curr_norm - pd.Timedelta(days=2)
                except ValueError:
                    t_minus_2_date = curr_norm - pd.Timedelta(days=2)

                for tr in t_list:
                    tr_buy_norm = pd.to_datetime(tr.buy_date).normalize()
                    if tr_buy_norm <= t_minus_2_date:
                        payout = round(tr.shares * div_per_share, 2)
                        tr.dividend_total += payout
                        cumulative_dividend_income += payout
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

        # A. Check Target Exits & 20DL Magic Profit across all open tranches
        for sym, t_list in list(open_tranches.items()):
            if not t_list:
                continue
            daily_dict = stock_data[sym]["daily_dict"]
            if current_date not in daily_dict:
                continue

            day_bar = daily_dict[current_date]
            day_high = float(day_bar["High"])
            day_low = float(day_bar["Low"])
            day_close = float(day_bar["Close"])
            last_known_close[sym] = day_close

            # Target Exits (BEARISH tranches only; BULLISH tranches exit on weekly 20W low breakdown)
            remaining_tranches = []
            for tr in t_list:
                if tr.status == "OPEN" and tr.tranche_type == "BEARISH" and day_high >= tr.target_price:
                    # Sell at target price
                    tr.status = "CLOSED"
                    tr.sell_date = current_date
                    tr.sell_price = tr.target_price
                    tr.holding_days = (current_date - tr.buy_date).days
                    tr.realized_pnl = round((tr.sell_price - tr.buy_price) * tr.shares, 2)
                    tr.return_pct = round(((tr.sell_price / tr.buy_price) - 1.0) * 100.0, 2)

                    cumulative_realized_profit += tr.realized_pnl
                    deployed_cash_flows.append((current_date, tr.shares * tr.sell_price))
                else:
                    remaining_tranches.append(tr)
            open_tranches[sym] = remaining_tranches

            # Magic Profit check
            if config.enable_magic_profit and open_tranches[sym] and current_date >= start_dt_cutoff:
                # Check cooldown
                lmd = last_magic_date[sym]
                can_magic = (lmd is None) or ((current_date - lmd).days >= config.magic_profit_cooldown_days)
                if can_magic:
                    # Check if any tranche in loss
                    tranches_in_loss = [t for t in open_tranches[sym] if day_close < t.buy_price]
                    if tranches_in_loss:
                        # Check rolling 20DL upto 1 day ago
                        # Find index in daily dataframe
                        sym_daily = stock_data[sym]["daily"]
                        curr_idx = sym_daily.index[sym_daily["Date"] == current_date]
                        if len(curr_idx) > 0 and curr_idx[0] >= 20:
                            idx_val = curr_idx[0]
                            prior_20d_low = float(sym_daily["Low"].iloc[idx_val-20:idx_val].min())
                            if day_close < prior_20d_low:
                                # Credit 500 magic profit once
                                credit = config.magic_profit_amount
                                cumulative_magic_profit += credit
                                last_magic_date[sym] = current_date
                                deployed_cash_flows.append((current_date, credit))

                                # Associate event
                                first_loss = tranches_in_loss[0]
                                first_loss.magic_profit_total += credit
                                first_loss.magic_profit_count += 1
                                first_loss.magic_dates.append(current_date)

                                m_event = MagicProfitEvent(
                                    event_id=magic_id_seq,
                                    date=current_date,
                                    trade_id=first_loss.trade_id,
                                    slot_id=first_loss.slot_id,
                                    buy_date=first_loss.buy_date,
                                    buy_price=first_loss.buy_price,
                                    rolling_20d_low=prior_20d_low,
                                    close_price=day_close,
                                    loss_pct=round(((day_close / first_loss.buy_price) - 1.0) * 100.0, 2),
                                    profit_credit=credit,
                                    open_tranches_in_loss=",".join([str(t.slot_id) for t in tranches_in_loss])
                                )
                                all_magic_events.append(m_event)
                                magic_id_seq += 1

        # B. Check Weekly Bar Signals occurring on current_date
        if current_date in weekly_events_by_date:
            weekly_signals = weekly_events_by_date[current_date]

            # 1. Evaluate Bullish Tranche Exits at Friday close
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
                                deployed_cash_flows.append((current_date, tr.shares * tr.sell_price))
                            else:
                                surviving.append(tr)
                        else:
                            surviving.append(tr)
                    open_tranches[sym] = surviving

            # 2. Update tracking states & collect buy candidates (Bearish & Bullish)
            buy_candidates: List[Tuple[str, float, str]] = []

            for sym, w_row in weekly_signals:
                w_close = float(w_row["Close"])
                r_20w_low = w_row["rolling_20w_low"]
                r_20w_high = w_row["rolling_20w_high"]
                breakout = bool(w_row["breakout_signal"])

                # Low breakdown activation
                if pd.notna(r_20w_low) and w_close < float(r_20w_low):
                    is_tracking_20w[sym] = True

                # High breakout deactivation
                if pd.notna(r_20w_high) and w_close > float(r_20w_high):
                    is_tracking_20w[sym] = False

                    # Check Bullish candidate entry
                    if config.enable_bullish_combo:
                        has_open_bullish = any(t.tranche_type == "BULLISH" for t in open_tranches[sym])
                        if not has_open_bullish and len(open_tranches[sym]) < config.num_parts:
                            p_high_20 = float(r_20w_high)
                            pct_breakout_high = (w_close - p_high_20) / p_high_20 if p_high_20 > 0 else 0.0
                            buy_candidates.append((sym, pct_breakout_high, "BULLISH"))

                # Bearish dip candidate
                elif is_tracking_20w[sym] and breakout:
                    max_bearish = (config.num_parts - 1) if config.enable_bullish_combo else config.num_parts
                    open_bearish = sum(1 for t in open_tranches[sym] if t.tranche_type == "BEARISH")
                    if open_bearish < max_bearish and len(open_tranches[sym]) < config.num_parts:
                        p_high = float(w_row["prev_week_high"])
                        pct_breakout = (w_close - p_high) / p_high if p_high > 0 else 0.0
                        buy_candidates.append((sym, pct_breakout, "BEARISH"))

            # Sort buy candidates by breakout strength descending
            buy_candidates.sort(key=lambda x: x[1], reverse=True)

            # 3. Evaluate and execute buys respecting max_active_stocks and tranche limits
            if current_date >= start_dt_cutoff:
                currently_active_stocks = {s for s, trs in open_tranches.items() if len(trs) > 0}

                for sym, _, t_type in buy_candidates:
                    num_open_tranches = len(open_tranches[sym])
                    if num_open_tranches >= config.num_parts:
                        continue  # Already reached max tranches for this stock

                    if t_type == "BULLISH":
                        if any(t.tranche_type == "BULLISH" for t in open_tranches[sym]):
                            continue
                    else:
                        max_bearish = (config.num_parts - 1) if config.enable_bullish_combo else config.num_parts
                        open_bearish = sum(1 for t in open_tranches[sym] if t.tranche_type == "BEARISH")
                        if open_bearish >= max_bearish:
                            continue

                    is_already_active = (sym in currently_active_stocks)
                    # If not currently active, can only enter if active stocks < max_active_stocks
                    if not is_already_active and len(currently_active_stocks) >= max_active_stocks:
                        continue  # Slot limit reached

                    # Execute buy at current Friday close
                    day_bar = stock_data[sym]["daily_dict"][current_date]
                    buy_price = float(day_bar["Close"])
                    if buy_price <= 0:
                        continue

                    shares = int(tranche_capital // buy_price)
                    if shares <= 0:
                        shares = 1

                    invested_amt = round(shares * buy_price, 2)
                    target_price = float("inf") if t_type == "BULLISH" else round(buy_price * (1.0 + config.target_pct), 2)
                    slot_id = num_open_tranches + 1

                    new_tranche = Tranche(
                        trade_id=trade_id_seq,
                        slot_id=slot_id,
                        symbol=sym,
                        signal_date=current_date,
                        buy_date=current_date,
                        buy_price=buy_price,
                        shares=shares,
                        invested_amt=invested_amt,
                        target_price=target_price,
                        status="OPEN",
                        tranche_type=t_type
                    )
                    open_tranches[sym].append(new_tranche)
                    currently_active_stocks.add(sym)
                    all_trades.append(new_tranche)
                    trade_id_seq += 1

                    deployed_cash_flows.append((current_date, -invested_amt))

        # C. Track Portfolio Drawdown & Accrue Idle Capital Interest
        if current_date >= start_dt_cutoff:
            days_elapsed = (current_date - prev_idle_date).days if prev_idle_date is not None else 1
            total_open_invested = sum(
                t.invested_amt for trs in open_tranches.values() for t in trs
            )
            idle_cash = max(0.0, config.total_capital - total_open_invested)
            eligible_idle = max(0.0, idle_cash - untouched_cash_buffer)
            daily_interest = eligible_idle * (0.05 / 365.0) * days_elapsed
            cumulative_idle_interest += daily_interest
            prev_idle_date = current_date

            total_open_value = sum(
                t.shares * (last_known_close[t.symbol] if last_known_close[t.symbol] > 0 else t.buy_price)
                for trs in open_tranches.values() for t in trs
            )
            current_unrealized = total_open_value - total_open_invested
            cash_balance = config.total_capital + cumulative_realized_profit + cumulative_magic_profit + cumulative_idle_interest + cumulative_dividend_income - total_open_invested
            total_portfolio_equity = cash_balance + total_open_value

            if total_portfolio_equity > peak_portfolio_value:
                peak_portfolio_value = total_portfolio_equity
            dd = ((peak_portfolio_value - total_portfolio_equity) / peak_portfolio_value) * 100.0
            if dd > max_drawdown_pct:
                max_drawdown_pct = round(dd, 2)

    # 3. Final Portfolio valuation & XIRR
    end_date = all_dates[-1]
    final_open_invested = sum(
        t.invested_amt for trs in open_tranches.values() for t in trs
    )
    final_open_value = sum(
        t.shares * (last_known_close[t.symbol] if last_known_close[t.symbol] > 0 else t.buy_price)
        for trs in open_tranches.values() for t in trs
    )
    final_unrealized_pnl = round(final_open_value - final_open_invested, 2)
    final_idle_interest = round(cumulative_idle_interest, 2)
    final_dividend_income = round(cumulative_dividend_income, 2)
    final_cash_balance = config.total_capital + cumulative_realized_profit + cumulative_magic_profit + final_idle_interest + final_dividend_income - final_open_invested
    final_total_portfolio_value = round(final_cash_balance + final_open_value, 2)

    # Final cash flows for XIRR
    portfolio_cash_flows.append((end_date, final_total_portfolio_value))
    portfolio_xirr_pct = calculate_xirr(portfolio_cash_flows)

    if final_open_value > 0:
        deployed_cash_flows.append((end_date, final_open_value))
    deployed_xirr_pct = calculate_xirr(deployed_cash_flows)

    total_realized_profit = round(cumulative_realized_profit + cumulative_magic_profit + final_idle_interest + final_dividend_income, 2)
    total_portfolio_return_pct = round(((total_realized_profit + final_unrealized_pnl) / config.total_capital) * 100.0, 2)

    completed_trades = [t for t in all_trades if t.status == "CLOSED"]
    open_trades_list = [t for t in all_trades if t.status == "OPEN"]
    win_trades = [t for t in completed_trades if (t.realized_pnl or 0) > 0]
    win_rate_pct = round((len(win_trades) / len(completed_trades)) * 100.0, 2) if completed_trades else 0.0

    # 4. Generate Stock Summaries
    stock_summaries: List[StockSummary] = []
    for sym in norm_symbols:
        s_trades = [t for t in all_trades if t.symbol == sym]
        s_completed = [t for t in s_trades if t.status == "CLOSED"]
        s_open = [t for t in s_trades if t.status == "OPEN"]
        s_realized_trade = sum(t.realized_pnl or 0.0 for t in s_completed)
        s_magic = sum(t.magic_profit_total for t in s_trades)
        s_dividends = sum(t.dividend_total for t in s_trades)
        s_win = [t for t in s_completed if (t.realized_pnl or 0.0) > 0]
        s_win_rate = round((len(s_win) / len(s_completed)) * 100.0, 2) if s_completed else 0.0
        s_open_inv = sum(t.invested_amt for t in s_open)
        s_open_val = sum(t.shares * (last_known_close[sym] if last_known_close[sym] > 0 else t.buy_price) for t in s_open)

        stock_summaries.append(StockSummary(
            symbol=sym,
            total_trades=len(s_trades),
            completed_trades=len(s_completed),
            open_trades=len(s_open),
            realized_trade_profit=round(s_realized_trade, 2),
            total_magic_profit=round(s_magic, 2),
            total_profit=round(s_realized_trade + s_magic + s_dividends, 2),
            win_rate_pct=s_win_rate,
            open_positions_invested=round(s_open_inv, 2),
            unrealized_pnl=round(s_open_val - s_open_inv, 2),
            dividend_income=round(s_dividends, 2)
        ))

    # Sort stock summaries by total profit descending
    stock_summaries.sort(key=lambda s: s.total_profit, reverse=True)

    return PortfolioBacktestResult(
        total_capital=config.total_capital,
        max_active_stocks=max_active_stocks,
        num_parts=config.num_parts,
        total_realized_profit=total_realized_profit,
        realized_trade_profit=round(cumulative_realized_profit, 2),
        total_magic_profit=round(cumulative_magic_profit, 2),
        idle_capital_interest=final_idle_interest,
        dividend_income=final_dividend_income,
        unrealized_pnl=final_unrealized_pnl,
        total_portfolio_return_pct=total_portfolio_return_pct,
        portfolio_xirr_pct=portfolio_xirr_pct,
        deployed_xirr_pct=deployed_xirr_pct,
        max_drawdown_pct=max_drawdown_pct,
        win_rate_pct=win_rate_pct,
        total_trades=len(all_trades),
        completed_trades=len(completed_trades),
        open_trades=len(open_trades_list),
        stock_summaries=stock_summaries,
        trades=all_trades,
        magic_events=all_magic_events,
        dividend_events=all_dividend_events
    )
