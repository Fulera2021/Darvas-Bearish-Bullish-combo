import unittest
import tempfile
import os
import pandas as pd
from pathlib import Path
import sys

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from web.cache_manager import (
    init_db,
    get_cached_daily_data,
    save_daily_data_to_cache,
    ensure_symbol_data
)

class TestCacheManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_cache.db")
        init_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_save_and_retrieve_cache(self):
        df = pd.DataFrame({
            "Date": pd.to_datetime(["2023-01-02", "2023-01-03"]),
            "Open": [100.0, 102.0],
            "High": [105.0, 106.0],
            "Low": [99.0, 101.0],
            "Close": [104.0, 105.0],
            "Volume": [1000.0, 1200.0]
        })
        save_daily_data_to_cache("TEST.NS", df, db_path=self.db_path)
        cached = get_cached_daily_data("TEST.NS", "2023-01-01", "2023-01-04", db_path=self.db_path)
        self.assertIsNotNone(cached)
        self.assertEqual(len(cached), 2)
        self.assertEqual(float(cached["Close"].iloc[0]), 104.0)

    def test_retrieve_empty_when_missing(self):
        cached = get_cached_daily_data("NONEXISTENT.NS", "2023-01-01", "2023-01-04", db_path=self.db_path)
        self.assertIsNone(cached)

if __name__ == "__main__":
    unittest.main()
