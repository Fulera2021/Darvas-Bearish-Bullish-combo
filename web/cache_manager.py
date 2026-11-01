"""SQLite caching layer for historical daily stock data with WAL concurrency."""

import os
import sqlite3
import logging
from typing import Optional
from pathlib import Path
import pandas as pd

from data_loader import fetch_daily_data, fetch_dividend_data
from web.universe_data import normalize_symbol

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = str(Path(__file__).parent.parent / "data" / "price_cache.db")

def init_db(db_path: str = DEFAULT_DB_PATH):
    """Initialize SQLite database schema and enable WAL mode for multi-user concurrency."""
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_prices (
            symbol TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume REAL NOT NULL,
            PRIMARY KEY (symbol, date)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_symbol_date ON daily_prices (symbol, date);")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_dividends (
            symbol TEXT NOT NULL,
            date TEXT NOT NULL,
            dividend REAL NOT NULL,
            PRIMARY KEY (symbol, date)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_dividends_symbol_date ON stock_dividends (symbol, date);")
    
    # Purge any non-historical / dummy ticker symbols
    excluded_symbols = ('BAGMANE.NS', 'BAGMANE', 'DUMMYHEG.NS', 'DUMMYHEG')
    placeholders = ','.join('?' for _ in excluded_symbols)
    cursor.execute(f"DELETE FROM daily_prices WHERE symbol IN ({placeholders})", excluded_symbols)
    cursor.execute(f"DELETE FROM stock_dividends WHERE symbol IN ({placeholders})", excluded_symbols)
    
    conn.commit()
    conn.close()

def save_daily_data_to_cache(symbol: str, df: pd.DataFrame, db_path: str = DEFAULT_DB_PATH):
    """Upsert daily OHLCV dataframe into SQLite."""
    if df.empty:
        return
    norm_symbol = normalize_symbol(symbol)
    init_db(db_path)
    
    records = []
    for _, row in df.iterrows():
        dt_str = pd.to_datetime(row["Date"]).strftime("%Y-%m-%d")
        records.append((
            norm_symbol,
            dt_str,
            float(row["Open"]),
            float(row["High"]),
            float(row["Low"]),
            float(row["Close"]),
            float(row["Volume"])
        ))
        
    conn = sqlite3.connect(db_path, timeout=30.0)
    cursor = conn.cursor()
    cursor.executemany("""
        INSERT OR REPLACE INTO daily_prices (symbol, date, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, records)
    conn.commit()
    conn.close()

def get_cached_daily_data(symbol: str, start_date: str, end_date: str, db_path: str = DEFAULT_DB_PATH) -> Optional[pd.DataFrame]:
    """Retrieve cached daily prices for symbol within date range. Returns None if no records exist."""
    if not os.path.exists(db_path):
        return None
        
    norm_symbol = normalize_symbol(symbol)
    start_str = pd.to_datetime(start_date).strftime("%Y-%m-%d")
    end_str = pd.to_datetime(end_date).strftime("%Y-%m-%d")
    
    conn = sqlite3.connect(db_path, timeout=30.0)
    query = """
        SELECT date, open, high, low, close, volume
        FROM daily_prices
        WHERE symbol = ? AND date >= ? AND date <= ?
        ORDER BY date ASC
    """
    df = pd.read_sql_query(query, conn, params=(norm_symbol, start_str, end_str))
    conn.close()
    
    if df.empty:
        return None
        
    df = df.rename(columns={
        "date": "Date",
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume"
    })
    df["Date"] = pd.to_datetime(df["Date"])
    return df

def _last_expected_trading_day(dt: pd.Timestamp) -> pd.Timestamp:
    """Adjust weekend dates (Saturday/Sunday) back to Friday so cache checks don't re-fetch on weekends."""
    wd = dt.weekday()
    if wd == 5:  # Saturday -> Friday
        return dt - pd.Timedelta(days=1)
    if wd == 6:  # Sunday -> Friday
        return dt - pd.Timedelta(days=2)
    return dt

def ensure_symbol_data(symbol: str, start_date: str, end_date: str, db_path: str = DEFAULT_DB_PATH) -> pd.DataFrame:
    """
    Retrieve price data from cache; if cache is missing or covers insufficient range,
    fetch only the missing delta (or full range if starting earlier), update cache,
    refresh dividends if new trailing days were added, and return DataFrame.
    """
    norm_symbol = normalize_symbol(symbol)
    cached_df = get_cached_daily_data(norm_symbol, start_date, end_date, db_path)
    
    req_start = pd.to_datetime(start_date).normalize()
    req_end = pd.to_datetime(end_date).normalize()
    effective_end = _last_expected_trading_day(req_end)
    
    # yfinance end parameter is exclusive, so add 1 day when downloading
    yf_end_str = (req_end + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    
    if cached_df is None or cached_df.empty:
        try:
            logger.info(f"Downloading full history for {norm_symbol} ({start_date} to {end_date})...")
            fresh_df = fetch_daily_data(norm_symbol, start_date, yf_end_str)
            save_daily_data_to_cache(norm_symbol, fresh_df, db_path)
            df_div = fetch_dividend_data(norm_symbol)
            if not df_div.empty:
                save_dividends_to_cache(norm_symbol, df_div, db_path)
            return fresh_df[(fresh_df["Date"] >= req_start) & (fresh_df["Date"] <= req_end)].reset_index(drop=True)
        except Exception as e:
            raise
            
    cached_min = cached_df["Date"].min().normalize()
    cached_max = cached_df["Date"].max().normalize()
    
    # 1. Check if earlier historical data before cached_min is needed
    # (Skip if stock is a newer IPO already starting at its earliest available date in DB)
    need_earlier = False
    if (cached_min - req_start).days > 15:
        # Check global min date in DB for this symbol
        conn = sqlite3.connect(db_path, timeout=30.0)
        cur = conn.cursor()
        cur.execute("SELECT MIN(date) FROM daily_prices WHERE symbol = ?", (norm_symbol,))
        row = cur.fetchone()
        conn.close()
        db_min = pd.to_datetime(row[0]).normalize() if (row and row[0]) else cached_min
        if (db_min - req_start).days > 15 and req_start < pd.Timestamp("2019-01-01"):
            need_earlier = True

    if need_earlier:
        try:
            logger.info(f"Downloading earlier history for {norm_symbol} ({start_date} to {cached_min.strftime('%Y-%m-%d')})...")
            early_end_str = (cached_min + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
            early_df = fetch_daily_data(norm_symbol, start_date, early_end_str)
            save_daily_data_to_cache(norm_symbol, early_df, db_path)
        except Exception as e:
            logger.warning(f"Could not download earlier history for {norm_symbol}: {e}")

    # 2. Check if newer trailing data after cached_max is needed (e.g., running test after 1 month)
    if cached_max < effective_end:
        delta_start_str = cached_max.strftime("%Y-%m-%d")
        try:
            logger.info(f"Incremental update for {norm_symbol}: fetching new bars from {delta_start_str} to {end_date}...")
            delta_df = fetch_daily_data(norm_symbol, delta_start_str, yf_end_str)
            if not delta_df.empty:
                save_daily_data_to_cache(norm_symbol, delta_df, db_path)
            # Also refresh dividends for newly elapsed period
            df_div = fetch_dividend_data(norm_symbol)
            if not df_div.empty:
                save_dividends_to_cache(norm_symbol, df_div, db_path)
        except Exception as e:
            logger.warning(f"Incremental update for {norm_symbol} returned no new bars ({e}); using cached data up to {cached_max.strftime('%Y-%m-%d')}.")

    updated_df = get_cached_daily_data(norm_symbol, start_date, end_date, db_path)
    return updated_df if (updated_df is not None and not updated_df.empty) else cached_df

def save_dividends_to_cache(symbol: str, df: pd.DataFrame, db_path: str = DEFAULT_DB_PATH):
    """Upsert historical dividend records into SQLite."""
    if df.empty:
        return
    norm_symbol = normalize_symbol(symbol)
    init_db(db_path)
    records = []
    for _, row in df.iterrows():
        dt_str = pd.to_datetime(row["Date"]).strftime("%Y-%m-%d")
        records.append((
            norm_symbol,
            dt_str,
            float(row["Dividend"])
        ))
    conn = sqlite3.connect(db_path, timeout=30.0)
    cursor = conn.cursor()
    cursor.executemany("""
        INSERT OR REPLACE INTO stock_dividends (symbol, date, dividend)
        VALUES (?, ?, ?)
    """, records)
    conn.commit()
    conn.close()

def get_cached_dividends(symbol: str, start_date: str, end_date: str, db_path: str = DEFAULT_DB_PATH) -> Optional[pd.DataFrame]:
    """Retrieve cached dividend records for symbol within date range."""
    if not os.path.exists(db_path):
        return None
    norm_symbol = normalize_symbol(symbol)
    start_str = pd.to_datetime(start_date).strftime("%Y-%m-%d")
    end_str = pd.to_datetime(end_date).strftime("%Y-%m-%d")
    conn = sqlite3.connect(db_path, timeout=30.0)
    query = """
        SELECT date, dividend
        FROM stock_dividends
        WHERE symbol = ? AND date >= ? AND date <= ?
        ORDER BY date ASC
    """
    df = pd.read_sql_query(query, conn, params=(norm_symbol, start_str, end_str))
    conn.close()
    if df.empty:
        return None
    df = df.rename(columns={"date": "Date", "dividend": "Dividend"})
    df["Date"] = pd.to_datetime(df["Date"])
    return df

def ensure_symbol_dividends(symbol: str, start_date: str, end_date: str, db_path: str = DEFAULT_DB_PATH) -> pd.DataFrame:
    """Retrieve dividend data from cache; if cache is missing, fetch from yfinance and save."""
    norm_symbol = normalize_symbol(symbol)
    cached_df = get_cached_dividends(norm_symbol, start_date, end_date, db_path)
    if cached_df is not None:
        return cached_df
    # Fetch from yfinance
    df_div = fetch_dividend_data(norm_symbol)
    if not df_div.empty:
        save_dividends_to_cache(norm_symbol, df_div, db_path)
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        return df_div[(df_div["Date"] >= start_dt) & (df_div["Date"] <= end_dt)].reset_index(drop=True)
    return pd.DataFrame(columns=["Date", "Dividend"])
