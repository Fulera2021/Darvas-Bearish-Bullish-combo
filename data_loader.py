"""Data loader and weekly resampling module for historical stock price data."""

import logging
from typing import Optional
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

def fetch_daily_data(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Fetch daily OHLCV historical data using yfinance for the specified symbol and dates.
    Returns a clean DataFrame with columns: ['Date', 'Open', 'High', 'Low', 'Close', 'Volume'].
    """
    logger.info(f"Downloading daily data for {symbol} from {start_date} to {end_date}...")
    # Add .NS suffix if not already present and not an index like ^NSEI
    ticker = symbol if symbol.endswith(".NS") or symbol.startswith("^") else f"{symbol}.NS"
    
    df = yf.download(ticker, start=start_date, end=end_date, auto_adjust=False, progress=False)
    if df.empty:
        raise ValueError(f"No price data found for symbol '{symbol}' ({ticker}) between {start_date} and {end_date}.")
    
    # Flatten MultiIndex columns if returned by yfinance
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    df = df.reset_index()
    # Normalize Date column
    if "Date" not in df.columns and "Datetime" in df.columns:
        df = df.rename(columns={"Datetime": "Date"})
    
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
    # Ensure standard column names
    required_cols = ["Date", "Open", "High", "Low", "Close", "Volume"]
    for col in required_cols:
        if col not in df.columns:
            raise KeyError(f"Missing required column '{col}' in downloaded data for {symbol}.")
            
    df = df[required_cols].sort_values("Date").reset_index(drop=True)
    df = df.dropna().reset_index(drop=True)
    return df

def fetch_dividend_data(symbol: str) -> pd.DataFrame:
    """
    Fetch historical corporate dividend distributions for the specified symbol via yfinance.
    Returns DataFrame with columns ['Date', 'Dividend'] where Date is normalized to midnight.
    """
    ticker = symbol if symbol.endswith(".NS") or symbol.startswith("^") else f"{symbol}.NS"
    try:
        t = yf.Ticker(ticker)
        divs = t.dividends
        if divs is None or divs.empty:
            return pd.DataFrame(columns=["Date", "Dividend"])
        df = divs.reset_index()
        df.columns = ["Date", "Dividend"]
        df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None).dt.normalize()
        df["Dividend"] = df["Dividend"].astype(float)
        df = df[df["Dividend"] > 0].sort_values("Date").reset_index(drop=True)
        return df
    except Exception as e:
        logger.warning(f"Could not fetch dividends for {symbol}: {e}")
        return pd.DataFrame(columns=["Date", "Dividend"])

def build_weekly_data(df_daily: pd.DataFrame) -> pd.DataFrame:
    """
    Resample daily price bars into weekly bars (Monday to Friday / last trading day of week).
    Aggregations:
      - Week_Start: First trading day of the week
      - Week_End: Last trading day of the week (e.g. Friday)
      - Open: First trading day Open
      - High: Highest High of the week
      - Low: Lowest Low of the week
      - Close: Last trading day Close
      - Volume: Sum of Volume
    """
    df = df_daily.copy()
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
    df = df.sort_values("Date").reset_index(drop=True)
    
    # Group by calendar ISO year and week
    # Note: Using dt.isocalendar() ensures proper calendar week grouping
    iso = df["Date"].dt.isocalendar()
    df["iso_year"] = iso.year
    df["iso_week"] = iso.week
    
    weekly_records = []
    for (year, week), group in df.groupby(["iso_year", "iso_week"], sort=False):
        group_sorted = group.sort_values("Date")
        rec = {
            "iso_year": year,
            "iso_week": week,
            "Week_Start": group_sorted["Date"].iloc[0],
            "Week_End": group_sorted["Date"].iloc[-1],
            "Open": float(group_sorted["Open"].iloc[0]),
            "High": float(group_sorted["High"].max()),
            "Low": float(group_sorted["Low"].min()),
            "Close": float(group_sorted["Close"].iloc[-1]),
            "Volume": float(group_sorted["Volume"].sum()),
            "Trading_Days": len(group_sorted)
        }
        weekly_records.append(rec)
        
    df_weekly = pd.DataFrame(weekly_records)
    return df_weekly

def add_weekly_signals(
    df_weekly: pd.DataFrame,
    entry_buffer_pct: float = 0.005,
    use_trend_filter: bool = False,
    trend_ema_period: int = 20,
    darvas_box_weeks: int = 1
) -> pd.DataFrame:
    """
    Calculate the breakout signal and execution limits on weekly bars:
      - prev_week_high: High of the preceding consolidation box (1 or N weeks)
      - breakout_signal: True if Close > prev_week_high (and optionally Close > EMA if use_trend_filter=True)
      - reference_close: Friday Close price
      - entry_ceiling: reference_close * (1 + entry_buffer_pct)
    """
    df = df_weekly.copy()
    
    if darvas_box_weeks <= 1:
        df["prev_week_high"] = df["High"].shift(1)
    else:
        df["prev_week_high"] = df["High"].shift(1).rolling(darvas_box_weeks, min_periods=1).max()
    
    # Breakout signal: Week Close > Previous Week High
    signal = (df["Close"] > df["prev_week_high"]) & df["prev_week_high"].notna()
    
    # Optional Trend Filter (e.g. Close > 20-week EMA)
    if use_trend_filter:
        df["trend_ema"] = df["Close"].ewm(span=trend_ema_period, adjust=False).mean()
        signal = signal & (df["Close"] > df["trend_ema"])
        
    df["prev_week_low"] = df["Low"].shift(1)
    df["breakout_signal"] = signal
    df["reference_close"] = df["Close"]
    df["entry_ceiling"] = df["Close"] * (1.0 + entry_buffer_pct)
    
    # 20-week rolling low and high (strictly prior 20 weeks excluding current week)
    df["rolling_20w_low"] = df["Low"].shift(1).rolling(20, min_periods=20).min()
    df["rolling_20w_high"] = df["High"].shift(1).rolling(20, min_periods=20).max()
    
    return df

