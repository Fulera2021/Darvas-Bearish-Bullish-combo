"""Script to pre-cache all historical OHLCV data and dividends for Nifty 500 stocks
from 2019-01-01 till yesterday into data/price_cache.db.
"""

import os
import sys
import json
import time
import logging
import sqlite3
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import requests
import yfinance as yf

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("precache_nifty500")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "price_cache.db")
NIFTY500_JSON_PATH = os.path.join(DATA_DIR, "nifty500_symbols.json")

# Start date requested: 1 Jan 2019
START_DATE = "2019-01-01"
# End date: yesterday
YESTERDAY = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

NSE_INDICES_URL = "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv"
ARCHIVES_NSE_URL = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"

# Symbols with no historical data or dummy tickers to permanently exclude
EXCLUDED_SYMBOLS = {"BAGMANE.NS", "BAGMANE", "DUMMYHEG.NS", "DUMMYHEG"}

def init_db(db_path: str = DB_PATH):
    """Ensure SQLite database schema and indexes exist."""
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=60.0)
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
    
    # Purge excluded tickers
    placeholders = ",".join("?" for _ in EXCLUDED_SYMBOLS)
    cursor.execute(f"DELETE FROM daily_prices WHERE symbol IN ({placeholders})", list(EXCLUDED_SYMBOLS))
    cursor.execute(f"DELETE FROM stock_dividends WHERE symbol IN ({placeholders})", list(EXCLUDED_SYMBOLS))
    
    conn.commit()
    conn.close()

def fetch_nifty500_symbols() -> list:
    """Fetch current Nifty 500 constituent symbols from NSE with fallback."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    symbols = []
    
    # Try niftyindices.com
    try:
        logger.info(f"Downloading Nifty 500 constituent list from {NSE_INDICES_URL}...")
        resp = requests.get(NSE_INDICES_URL, headers=headers, timeout=15)
        if resp.status_code == 200 and "Symbol" in resp.text:
            lines = resp.text.strip().splitlines()
            df = pd.read_csv(pd.io.common.StringIO(resp.text))
            if "Symbol" in df.columns:
                symbols = [f"{str(s).strip().upper()}.NS" for s in df["Symbol"] if str(s).strip() and str(s).strip() != "nan"]
                logger.info(f"Successfully fetched {len(symbols)} Nifty 500 constituents from NiftyIndices.")
    except Exception as e:
        logger.warning(f"Failed to fetch from NiftyIndices: {e}")

    # Fallback to archives.nseindia.com
    if not symbols or len(symbols) < 400:
        try:
            logger.info(f"Trying fallback URL: {ARCHIVES_NSE_URL}...")
            resp = requests.get(ARCHIVES_NSE_URL, headers=headers, timeout=15)
            if resp.status_code == 200 and "Symbol" in resp.text:
                df = pd.read_csv(pd.io.common.StringIO(resp.text))
                if "Symbol" in df.columns:
                    symbols = [f"{str(s).strip().upper()}.NS" for s in df["Symbol"] if str(s).strip() and str(s).strip() != "nan"]
                    logger.info(f"Successfully fetched {len(symbols)} symbols from NSE archives.")
        except Exception as e:
            logger.warning(f"Failed to fetch from NSE archives: {e}")

    # Check if local cached json exists
    if (not symbols or len(symbols) < 400) and os.path.exists(NIFTY500_JSON_PATH):
        try:
            with open(NIFTY500_JSON_PATH, "r", encoding="utf-8") as f:
                symbols = json.load(f)
            logger.info(f"Loaded {len(symbols)} symbols from existing {NIFTY500_JSON_PATH}.")
        except Exception as e:
            logger.warning(f"Could not read local {NIFTY500_JSON_PATH}: {e}")

    # Deduplicate, sort, and filter out excluded/dummy symbols
    symbols = sorted(list(set(s for s in symbols if s not in EXCLUDED_SYMBOLS and s.replace(".NS", "") not in EXCLUDED_SYMBOLS)))

    # Save to json for fast offline reuse
    if symbols and len(symbols) >= 400:
        with open(NIFTY500_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(symbols, f, indent=2)
        logger.info(f"Saved {len(symbols)} Nifty 500 constituents to {NIFTY500_JSON_PATH}.")

    return symbols

def get_already_cached_symbols(db_path: str = DB_PATH, target_start: str = START_DATE, target_end: str = YESTERDAY) -> set:
    """Return set of symbols that already have complete data from target_start to target_end."""
    if not os.path.exists(db_path):
        return set()

    conn = sqlite3.connect(db_path, timeout=30.0)
    query = """
        SELECT symbol, MIN(date) as min_dt, MAX(date) as max_dt, COUNT(*) as count
        FROM daily_prices
        GROUP BY symbol
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        return set()

    target_start_dt = pd.to_datetime(target_start)
    target_end_dt = pd.to_datetime(target_end)

    valid_symbols = set()
    for _, row in df.iterrows():
        sym = row["symbol"]
        min_dt = pd.to_datetime(row["min_dt"])
        max_dt = pd.to_datetime(row["max_dt"])
        # If cache starts within 15 days of target_start (or earlier) and ends within 5 days of target_end (or later)
        # Note: newly listed IPOs might start later, but if max_dt is up to date and row count is reasonable, mark done
        if (target_end_dt - max_dt).days <= 5 and (min_dt <= target_start_dt + pd.Timedelta(days=15)):
            valid_symbols.add(sym)

    return valid_symbols

def save_symbol_daily_and_dividends(symbol: str, df_daily: pd.DataFrame, df_divs: pd.DataFrame, db_path: str = DB_PATH):
    """Upsert daily prices and dividends for a symbol into SQLite with retry."""
    if df_daily.empty:
        return

    price_records = []
    for _, row in df_daily.iterrows():
        dt_str = pd.to_datetime(row["Date"]).strftime("%Y-%m-%d")
        price_records.append((
            symbol,
            dt_str,
            float(row["Open"]),
            float(row["High"]),
            float(row["Low"]),
            float(row["Close"]),
            float(row["Volume"])
        ))

    div_records = []
    if df_divs is not None and not df_divs.empty:
        for _, row in df_divs.iterrows():
            dt_str = pd.to_datetime(row["Date"]).strftime("%Y-%m-%d")
            div_records.append((
                symbol,
                dt_str,
                float(row["Dividend"])
            ))

    # Retry loop for SQLite concurrency locks
    for attempt in range(5):
        try:
            conn = sqlite3.connect(db_path, timeout=60.0)
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT OR REPLACE INTO daily_prices (symbol, date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, price_records)

            if div_records:
                cursor.executemany("""
                    INSERT OR REPLACE INTO stock_dividends (symbol, date, dividend)
                    VALUES (?, ?, ?)
                """, div_records)

            conn.commit()
            conn.close()
            return
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() and attempt < 4:
                time.sleep(0.5 * (attempt + 1))
            else:
                raise

def fetch_single_ticker(symbol: str, start_date: str, end_date: str) -> tuple:
    """Fetch daily data and dividends for a single ticker via yfinance."""
    # Download daily price
    df = yf.download(symbol, start=start_date, end=end_date, auto_adjust=False, progress=False)
    if df.empty:
        return symbol, pd.DataFrame(), pd.DataFrame(), "No price data returned"

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.reset_index()
    if "Date" not in df.columns and "Datetime" in df.columns:
        df = df.rename(columns={"Datetime": "Date"})

    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
    required_cols = ["Date", "Open", "High", "Low", "Close", "Volume"]
    for col in required_cols:
        if col not in df.columns:
            return symbol, pd.DataFrame(), pd.DataFrame(), f"Missing column {col}"

    df = df[required_cols].sort_values("Date").dropna().reset_index(drop=True)

    # Fetch dividends
    df_div = pd.DataFrame(columns=["Date", "Dividend"])
    try:
        t = yf.Ticker(symbol)
        divs = t.dividends
        if divs is not None and not divs.empty:
            d_df = divs.reset_index()
            d_df.columns = ["Date", "Dividend"]
            d_df["Date"] = pd.to_datetime(d_df["Date"]).dt.tz_localize(None).dt.normalize()
            d_df["Dividend"] = d_df["Dividend"].astype(float)
            df_div = d_df[d_df["Dividend"] > 0].sort_values("Date").reset_index(drop=True)
    except Exception:
        pass

    return symbol, df, df_div, None

def precache_all(max_workers: int = 4):
    """Main execution function to precache Nifty 500 stocks."""
    logger.info("=" * 70)
    logger.info("NIFTY 500 HISTORICAL DATA PRE-CACHING")
    logger.info(f"Date Range: {START_DATE} to {YESTERDAY}")
    logger.info(f"Target DB:  {DB_PATH}")
    logger.info("=" * 70)

    init_db(DB_PATH)

    symbols = fetch_nifty500_symbols()
    if not symbols:
        logger.error("Could not obtain Nifty 500 constituent symbols list. Exiting.")
        return

    logger.info(f"Total symbols in universe: {len(symbols)}")

    already_cached = get_already_cached_symbols(DB_PATH, START_DATE, YESTERDAY)
    logger.info(f"Already fully cached up to {YESTERDAY}: {len(already_cached)} symbols.")

    to_fetch = [s for s in symbols if s not in already_cached]
    logger.info(f"Remaining symbols to fetch: {len(to_fetch)}")

    if not to_fetch:
        logger.info("ALL Nifty 500 stocks are already cached! Nothing to download.")
        return

    total = len(to_fetch)
    completed = 0
    errors = 0

    logger.info(f"Starting parallel download with {max_workers} worker threads...")
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_single_ticker, sym, START_DATE, YESTERDAY): sym for sym in to_fetch}

        for future in as_completed(futures):
            sym = futures[future]
            completed += 1
            pct = (completed / total) * 100
            try:
                symbol, df_daily, df_divs, err = future.result()
                if err or df_daily.empty:
                    logger.warning(f"[{completed}/{total}] ({pct:.1f}%) {sym}: Failed ({err})")
                    errors += 1
                else:
                    save_symbol_daily_and_dividends(symbol, df_daily, df_divs, DB_PATH)
                    bars = len(df_daily)
                    divs = len(df_divs) if df_divs is not None else 0
                    logger.info(f"[{completed}/{total}] ({pct:.1f}%) {sym}: Saved {bars} daily bars, {divs} dividends.")
            except Exception as e:
                logger.error(f"[{completed}/{total}] ({pct:.1f}%) {sym}: Exception: {e}")
                errors += 1

    elapsed = time.time() - start_time
    logger.info("=" * 70)
    logger.info(f"PRE-CACHING COMPLETE in {elapsed:.1f} seconds ({elapsed / 60:.1f} minutes)!")
    logger.info(f"Processed: {completed} | Errors/Skipped: {errors}")
    logger.info(f"Database path: {DB_PATH}")
    logger.info("=" * 70)

if __name__ == "__main__":
    workers = 4
    if len(sys.argv) > 1:
        try:
            workers = int(sys.argv[1])
        except ValueError:
            pass
    precache_all(max_workers=workers)
