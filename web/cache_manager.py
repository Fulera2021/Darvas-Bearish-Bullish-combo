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

def ensure_symbol_data(symbol: str, start_date: str, end_date: str, db_path: str = DEFAULT_DB_PATH) -> pd.DataFrame:
    """
    Retrieve price data from cache; if cache is missing or covers insufficient range,
    fetch via yfinance, update cache, and return DataFrame.
    """
    norm_symbol = normalize_symbol(symbol)
    cached_df = get_cached_daily_data(norm_symbol, start_date, end_date, db_path)
    
    # Check if cached data covers required range with minimal trading day density
    req_start = pd.to_datetime(start_date)
    req_end = pd.to_datetime(end_date)
    
    needs_download = False
    if cached_df is None or cached_df.empty:
        needs_download = True
    else:
        cached_min = cached_df["Date"].min()
        cached_max = cached_df["Date"].max()
        # If cache starts more than 10 calendar days after requested start, or ends > 5 days before requested end
        if (cached_min - req_start).days > 10 or (req_end - cached_max).days > 5:
            needs_download = True
            
    if needs_download:
        logger.info(f"Downloading {norm_symbol} from yfinance for range {start_date} to {end_date}...")
        fresh_df = fetch_daily_data(norm_symbol, start_date, end_date)
        save_daily_data_to_cache(norm_symbol, fresh_df, db_path)
        return fresh_df
        
    return cached_df

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
