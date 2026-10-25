"""FastAPI asynchronous web application for Weekly 20W Darvas Box backtesting."""

import os
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any
import logging
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

from config import BacktestConfig
from data_loader import build_weekly_data, add_weekly_signals
from backtest_engine import run_backtest, BacktestResult
from web.universe_data import get_all_universes, get_universe_symbols, normalize_symbol
from web.cache_manager import ensure_symbol_data, ensure_symbol_dividends, init_db, DEFAULT_DB_PATH
from web.portfolio_simulator import run_portfolio_universe_simulation, PortfolioBacktestResult
from web.excel_exporter import export_single_stock_excel, export_portfolio_excel

logger = logging.getLogger(__name__)

# Base paths
BASE_DIR = Path(__file__).parent.parent
STATIC_DIR = BASE_DIR / "web" / "static"
TEMPLATES_DIR = BASE_DIR / "web" / "templates"

app = FastAPI(title="Weekly 20W Darvas Box Backtester", version="1.0.0")

# Mount static folder
os.makedirs(STATIC_DIR / "css", exist_ok=True)
os.makedirs(STATIC_DIR / "js", exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Initialize SQLite database cache on startup
init_db(DEFAULT_DB_PATH)

# In-memory storage for generated export workbooks
EXPORT_CACHE: Dict[str, Any] = {}

class BacktestRequest(BaseModel):
    mode: str = Field(default="stock", description="'stock' or 'universe'")
    variant: str = Field(default="vanilla", description="'vanilla' or 'magic'")
    symbol: Optional[str] = Field(default="RELIANCE", description="Ticker symbol for individual stock")
    universe: Optional[str] = Field(default="Nifty 50", description="Universe name")
    total_capital: float = Field(default=1000000.0, ge=1000.0)
    max_active_stocks: int = Field(default=25, ge=1, le=250)
    num_parts: int = Field(default=4, ge=2, le=5)
    start_date: str = Field(default="2021-01-01")
    end_date: str = Field(default="2026-10-11")
    target_pct: float = Field(default=5.0, gt=0.0, le=100.0)
    bullish_min_return_pct: float = Field(default=15.0, ge=0.0, le=100.0, description="Minimum simple return % p.a. for Bullish tranche exit")
    enable_compounding: bool = Field(default=True, description="Enable dynamic compounding into overall capital")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = TEMPLATES_DIR / "index.html"
    if not index_file.exists():
        return HTMLResponse("<h3>Darvas Bearish + Bullish Combo UI initializing...</h3>", status_code=200)
    return HTMLResponse(content=index_file.read_text(encoding="utf-8"))

@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "service": "Darvas Bearish + Bullish Combo Backtest Engine",
        "cache_db": DEFAULT_DB_PATH
    }

@app.get("/api/universes")
async def get_universes():
    return {
        "universes": get_all_universes()
    }

@app.post("/api/backtest")
async def execute_backtest(req: BacktestRequest):
    try:
        enable_magic = (req.variant.lower() == "magic")
        target_decimal = req.target_pct / 100.0
        run_id = str(uuid.uuid4())

        cfg = BacktestConfig(
            total_capital=req.total_capital,
            num_parts=req.num_parts,
            target_pct=target_decimal,
            enable_magic_profit=enable_magic,
            use_20w_low_tracking=True,
            enable_bullish_combo=True,
            bullish_min_return_pct=req.bullish_min_return_pct,
            enable_compounding=req.enable_compounding,
            start_date=req.start_date,
            end_date=req.end_date
        )

        if req.mode == "stock":
            if not req.symbol:
                raise HTTPException(status_code=400, detail="Stock symbol must be specified.")
            norm_sym = normalize_symbol(req.symbol)
            warmup_start_dt = (pd.to_datetime(req.start_date) - pd.Timedelta(days=365)).strftime("%Y-%m-%d")
            df_daily = ensure_symbol_data(norm_sym, warmup_start_dt, req.end_date, DEFAULT_DB_PATH)
            if df_daily is None or df_daily.empty:
                raise HTTPException(status_code=404, detail=f"No price data available for {norm_sym}.")

            df_weekly = build_weekly_data(df_daily)
            df_weekly_signals = add_weekly_signals(
                df_weekly,
                entry_buffer_pct=cfg.entry_buffer_pct,
                use_trend_filter=cfg.use_trend_filter,
                trend_ema_period=cfg.trend_ema_period,
                darvas_box_weeks=cfg.darvas_box_weeks
            )

            df_div = ensure_symbol_dividends(norm_sym, warmup_start_dt, req.end_date, DEFAULT_DB_PATH)
            result: BacktestResult = run_backtest(df_daily, df_weekly_signals, cfg, symbol=norm_sym, df_dividends=df_div)
            EXPORT_CACHE[run_id] = ("stock", result)

            # Format trade records for JSON response
            trades_json = []
            for t in result.trades:
                trades_json.append({
                    "trade_id": t.trade_id,
                    "slot_id": t.slot_id,
                    "symbol": t.symbol,
                    "signal_date": t.signal_date.strftime("%d-%b-%Y") if t.signal_date else "-",
                    "buy_date": t.buy_date.strftime("%d-%b-%Y") if t.buy_date else "-",
                    "buy_price": round(t.buy_price, 2),
                    "shares": t.shares,
                    "invested_amt": round(t.invested_amt, 2),
                    "target_price": round(t.target_price, 2) if t.target_price != float("inf") else "20W Low Exit",
                    "sell_date": t.sell_date.strftime("%d-%b-%Y") if t.sell_date else "-",
                    "sell_price": round(t.sell_price, 2) if t.sell_price else None,
                    "realized_pnl": round(t.realized_pnl, 2) if t.realized_pnl is not None else 0.0,
                    "return_pct": round(t.return_pct, 2) if t.return_pct is not None else 0.0,
                    "holding_days": t.holding_days if t.holding_days is not None else "-",
                    "status": t.status,
                    "magic_profit": round(t.magic_profit_total, 2),
                    "dividend": round(t.dividend_total, 2),
                    "tranche_type": t.tranche_type,
                    "required_return_pct": round(t.required_return_pct, 2) if t.required_return_pct is not None else None,
                    "achieved_return_pct": round(t.achieved_return_pct, 2) if t.achieved_return_pct is not None else None,
                    "years_held": round(t.years_held, 2) if t.years_held is not None else None
                })

            magic_events_json = []
            for ev in result.magic_events:
                magic_events_json.append({
                    "event_id": ev.event_id,
                    "date": ev.date.strftime("%d-%b-%Y"),
                    "trade_id": ev.trade_id,
                    "slot_id": ev.slot_id,
                    "buy_price": round(ev.buy_price, 2),
                    "rolling_20d_low": round(ev.rolling_20d_low, 2),
                    "close_price": round(ev.close_price, 2),
                    "loss_pct": round(ev.loss_pct, 2),
                    "profit_credit": round(ev.profit_credit, 2),
                    "open_tranches_in_loss": ev.open_tranches_in_loss
                })

            dividend_events_json = []
            for ev in result.dividend_events:
                dividend_events_json.append({
                    "event_id": ev.event_id,
                    "date": ev.ex_date.strftime("%d-%b-%Y"),
                    "symbol": ev.symbol,
                    "trade_id": ev.trade_id,
                    "slot_id": ev.slot_id,
                    "buy_date": ev.buy_date.strftime("%d-%b-%Y"),
                    "shares": ev.shares,
                    "dividend_per_share": round(ev.dividend_per_share, 2),
                    "total_payout": round(ev.total_payout, 2)
                })

            monthly_summary_json = [
                {
                    "year_mmm": m.year_mmm,
                    "num_buys": getattr(m, "num_buys", 0),
                    "num_sells": getattr(m, "num_sells", 0),
                    "trade_realized_profit": round(m.trade_realized_profit, 2),
                    "magic_profit": round(m.magic_profit, 2),
                    "dividend_income": round(m.dividend_income, 2),
                    "idle_interest": round(m.idle_interest, 2),
                    "total_realized_profit": round(m.total_realized_profit, 2),
                    "month_end_unrealized": round(m.month_end_unrealized, 2),
                    "net_monthly_pnl": round(m.net_monthly_pnl, 2),
                    "max_capital_blocked": round(m.max_capital_blocked, 2),
                    "idle_unused_cash": round(getattr(m, "idle_unused_cash", 0.0), 2),
                    "monthly_return_pct": round(m.monthly_return_pct, 2),
                    "max_drawdown_pct": round(m.max_drawdown_pct, 2),
                    "month_end_drawdown_pct": round(m.month_end_drawdown_pct, 2)
                }
                for m in getattr(result, "monthly_summaries", [])
            ]

            return {
                "run_id": run_id,
                "mode": "stock",
                "variant": req.variant,
                "symbol": norm_sym,
                "summary": {
                    "total_capital": round(result.initial_capital, 2),
                    "realized_trade_profit": round(result.realized_trade_profit, 2),
                    "total_magic_profit": round(result.total_magic_profit, 2),
                    "idle_capital_interest": round(result.idle_capital_interest, 2),
                    "dividend_income": round(result.dividend_income, 2),
                    "total_realized_profit": round(result.total_realized_profit, 2),
                    "unrealized_pnl": round(result.unrealized_pnl, 2),
                    "total_portfolio_return_amount": round(result.total_realized_profit + result.unrealized_pnl, 2),
                    "total_portfolio_return_pct": round(result.total_portfolio_return_pct, 2),
                    "deployed_xirr_pct": round(result.deployed_xirr_pct, 2),
                    "xirr_pct": round(result.deployed_xirr_pct, 2),
                    "total_trades": result.total_trades,
                    "completed_trades": result.completed_trades,
                    "open_trades": result.open_trades,
                    "win_rate_pct": round(result.win_rate_pct, 2),
                    "max_drawdown_pct": round(result.max_drawdown_pct, 2),
                    "avg_holding_days": round(result.avg_holding_days, 1),
                    "ending_overall_capital": round(result.ending_overall_capital, 2),
                    "ending_tranche_amount": round(result.ending_tranche_amount, 2)
                },
                "trades": trades_json,
                "magic_events": magic_events_json,
                "dividend_events": dividend_events_json,
                "monthly_summary": monthly_summary_json
            }

        else:
            # Universe Mode
            universe_name = req.universe or "Nifty 50"
            symbols = get_universe_symbols(universe_name)
            p_res: PortfolioBacktestResult = run_portfolio_universe_simulation(
                symbols=symbols,
                config=cfg,
                max_active_stocks=req.max_active_stocks,
                db_path=DEFAULT_DB_PATH
            )
            EXPORT_CACHE[run_id] = ("universe", p_res)

            stock_summaries_json = []
            for s in p_res.stock_summaries:
                stock_summaries_json.append({
                    "symbol": s.symbol,
                    "total_trades": s.total_trades,
                    "completed_trades": s.completed_trades,
                    "open_trades": s.open_trades,
                    "realized_trade_profit": round(s.realized_trade_profit, 2),
                    "total_magic_profit": round(s.total_magic_profit, 2),
                    "dividend_income": round(s.dividend_income, 2),
                    "total_profit": round(s.total_profit, 2),
                    "win_rate_pct": round(s.win_rate_pct, 2),
                    "open_positions_invested": round(s.open_positions_invested, 2),
                    "unrealized_pnl": round(s.unrealized_pnl, 2)
                })

            trades_json = []
            for t in p_res.trades:
                trades_json.append({
                    "trade_id": t.trade_id,
                    "symbol": t.symbol,
                    "slot_id": t.slot_id,
                    "signal_date": t.signal_date.strftime("%d-%b-%Y") if t.signal_date else "-",
                    "buy_date": t.buy_date.strftime("%d-%b-%Y") if t.buy_date else "-",
                    "buy_price": round(t.buy_price, 2),
                    "shares": t.shares,
                    "invested_amt": round(t.invested_amt, 2),
                    "target_price": round(t.target_price, 2) if t.target_price != float("inf") else "20W Low Exit",
                    "sell_date": t.sell_date.strftime("%d-%b-%Y") if t.sell_date else "-",
                    "sell_price": round(t.sell_price, 2) if t.sell_price else None,
                    "realized_pnl": round(t.realized_pnl, 2) if t.realized_pnl is not None else 0.0,
                    "return_pct": round(t.return_pct, 2) if t.return_pct is not None else 0.0,
                    "holding_days": t.holding_days if t.holding_days is not None else "-",
                    "status": t.status,
                    "magic_profit": round(t.magic_profit_total, 2),
                    "dividend": round(t.dividend_total, 2),
                    "tranche_type": t.tranche_type,
                    "required_return_pct": round(t.required_return_pct, 2) if t.required_return_pct is not None else None,
                    "achieved_return_pct": round(t.achieved_return_pct, 2) if t.achieved_return_pct is not None else None,
                    "years_held": round(t.years_held, 2) if t.years_held is not None else None
                })

            dividend_events_json = []
            for ev in p_res.dividend_events:
                dividend_events_json.append({
                    "event_id": ev.event_id,
                    "date": ev.ex_date.strftime("%d-%b-%Y"),
                    "symbol": ev.symbol,
                    "trade_id": ev.trade_id,
                    "slot_id": ev.slot_id,
                    "buy_date": ev.buy_date.strftime("%d-%b-%Y"),
                    "shares": ev.shares,
                    "dividend_per_share": round(ev.dividend_per_share, 2),
                    "total_payout": round(ev.total_payout, 2)
                })

            monthly_summary_json = [
                {
                    "year_mmm": m.year_mmm,
                    "num_buys": getattr(m, "num_buys", 0),
                    "num_sells": getattr(m, "num_sells", 0),
                    "trade_realized_profit": round(m.trade_realized_profit, 2),
                    "magic_profit": round(m.magic_profit, 2),
                    "dividend_income": round(m.dividend_income, 2),
                    "idle_interest": round(m.idle_interest, 2),
                    "total_realized_profit": round(m.total_realized_profit, 2),
                    "month_end_unrealized": round(m.month_end_unrealized, 2),
                    "net_monthly_pnl": round(m.net_monthly_pnl, 2),
                    "max_capital_blocked": round(m.max_capital_blocked, 2),
                    "idle_unused_cash": round(getattr(m, "idle_unused_cash", 0.0), 2),
                    "monthly_return_pct": round(m.monthly_return_pct, 2),
                    "max_drawdown_pct": round(m.max_drawdown_pct, 2),
                    "month_end_drawdown_pct": round(m.month_end_drawdown_pct, 2)
                }
                for m in getattr(p_res, "monthly_summaries", [])
            ]

            return {
                "run_id": run_id,
                "mode": "universe",
                "universe": universe_name,
                "variant": req.variant,
                "summary": {
                    "total_capital": round(p_res.total_capital, 2),
                    "max_active_stocks": p_res.max_active_stocks,
                    "num_parts": p_res.num_parts,
                    "realized_trade_profit": round(p_res.realized_trade_profit, 2),
                    "total_magic_profit": round(p_res.total_magic_profit, 2),
                    "idle_capital_interest": round(p_res.idle_capital_interest, 2),
                    "dividend_income": round(p_res.dividend_income, 2),
                    "total_realized_profit": round(p_res.total_realized_profit, 2),
                    "unrealized_pnl": round(p_res.unrealized_pnl, 2),
                    "total_portfolio_return_amount": round(p_res.total_realized_profit + p_res.unrealized_pnl, 2),
                    "total_portfolio_return_pct": round(p_res.total_portfolio_return_pct, 2),
                    "deployed_xirr_pct": round(p_res.deployed_xirr_pct, 2),
                    "xirr_pct": round(p_res.deployed_xirr_pct, 2),
                    "max_drawdown_pct": round(p_res.max_drawdown_pct, 2),
                    "win_rate_pct": round(p_res.win_rate_pct, 2),
                    "total_trades": p_res.total_trades,
                    "completed_trades": p_res.completed_trades,
                    "open_trades": p_res.open_trades,
                    "ending_overall_capital": round(p_res.ending_overall_capital, 2),
                    "ending_tranche_amount": round(p_res.ending_tranche_amount, 2)
                },
                "stock_summaries": stock_summaries_json,
                "trades": trades_json,
                "dividend_events": dividend_events_json,
                "monthly_summary": monthly_summary_json
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error executing backtest")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/export-excel")
async def download_excel(run_id: str = Query(..., description="Run ID returned by /api/backtest")):
    if run_id not in EXPORT_CACHE:
        raise HTTPException(status_code=404, detail="Run ID not found or export expired.")

    mode, res = EXPORT_CACHE[run_id]
    if mode == "stock":
        stream = export_single_stock_excel(res)
        filename = f"{res.symbol}_darvas_backtest.xlsx"
    else:
        stream = export_portfolio_excel(res)
        filename = f"universe_darvas_backtest.xlsx"

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"'
    }
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web.app:app", host="0.0.0.0", port=8005, reload=True)
