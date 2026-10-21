import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "price_cache.db")

EXCLUDED = ["BAGMANE.NS", "BAGMANE", "DUMMYHEG.NS", "DUMMYHEG"]

def clean_database():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    cursor = conn.cursor()
    
    placeholders = ",".join("?" for _ in EXCLUDED)
    
    # Check current records
    cursor.execute(f"SELECT symbol, count(*) FROM daily_prices WHERE symbol IN ({placeholders}) GROUP BY symbol", EXCLUDED)
    price_rows = cursor.fetchall()
    print(f"Daily price records found before deletion: {price_rows}")
    
    cursor.execute(f"SELECT symbol, count(*) FROM stock_dividends WHERE symbol IN ({placeholders}) GROUP BY symbol", EXCLUDED)
    div_rows = cursor.fetchall()
    print(f"Dividend records found before deletion: {div_rows}")
    
    # Delete from daily_prices
    cursor.execute(f"DELETE FROM daily_prices WHERE symbol IN ({placeholders})", EXCLUDED)
    deleted_p = cursor.rowcount
    
    # Delete from stock_dividends
    cursor.execute(f"DELETE FROM stock_dividends WHERE symbol IN ({placeholders})", EXCLUDED)
    deleted_d = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    print(f"Successfully deleted {deleted_p} daily price rows and {deleted_d} dividend rows for {EXCLUDED}.")

if __name__ == "__main__":
    clean_database()
